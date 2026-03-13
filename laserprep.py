import argparse
import json
import os
import re
import random
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
import svgwrite
import cairosvg

FILE_TO_PREP = "shapes1.json"
APPELLATION = "laser"
TAPER_PX = 2  # pixels shrunk per side per layer above the base


# --- Load input data ---

def load_shapes(filepath):
    """Load canvas size and shape list from a JSON file produced by shapefuncJSON.py."""
    with open(filepath, "r") as f:
        data = json.load(f)
    canvas_size = tuple(data["canvas_size"])
    shapes = data["shapes"]
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    return canvas_size, shapes, base_name


# --- Geometry construction ---

def to_shapely(shape):
    """Convert a shape dict to Shapely fill and ring geometries.
    The ring is the stroke area: an annulus of width stroke_width centered on the shape boundary.
    Returns (fill, ring). Ring is None if stroke_width is 0.
    """
    sw = shape["stroke_width"]
    if shape["type"] == "circle":
        fill = Point(shape["cx"], shape["cy"]).buffer(shape["r"])
    elif shape["type"] in ("polygon", "star", "cross"):
        fill = Polygon(shape["points"])

    if sw == 0:
        return fill, None

    outer = fill.buffer(sw / 2)
    inner = fill.buffer(-sw / 2)
    ring = outer.difference(inner)
    return fill, ring


def build_geometries(shapes):
    """Build parallel lists of Shapely fill and ring geometries for all shapes."""
    geometries = []
    rings = []
    for shape in shapes:
        fill, ring = to_shapely(shape)
        geometries.append(fill)
        rings.append(ring)
    return geometries, rings


# --- Occlusion filtering and ordering ---

def filter_visible(shapes, geometries, rings):
    """Discard shapes that are entirely covered by shapes drawn on top of them.
    Shapes are drawn in index order, so a higher index = drawn later = on top.
    A shape is visible if any part of its area (fill + ring) is not covered
    by the union of all geometries with a higher index.
    Also computes and returns each visible shape's actual visible area (the portion
    not covered by shapes above it), used later for ordering.
    Returns (visible_indices, visible_areas) where visible_areas is a dict {index: area}.
    """
    visible_indices = []
    visible_areas = {}
    for i in range(len(shapes)):
        shapes_above = [geometries[j] for j in range(i + 1, len(shapes))]
        shapes_above += [rings[j] for j in range(i + 1, len(shapes)) if rings[j] is not None]
        shape_area = geometries[i]
        if rings[i] is not None:
            shape_area = shape_area.union(rings[i])
        if shapes_above:
            cover = unary_union(shapes_above)
            visible = shape_area.difference(cover)
            if visible.area < 1e-6:
                continue
            visible_areas[i] = visible.area
        else:
            visible_areas[i] = shape_area.area
        visible_indices.append(i)
    return visible_indices, visible_areas


def compute_ordering(visible_indices, visible_areas, geometries, rings):
    """Order visible shapes from outermost to innermost, smallest first.

    At each step:
    1. Compute the combined silhouette of all remaining unplaced shapes.
    2. Find eligible shapes: those whose geometry touches the outer boundary
       of that silhouette. Fully interior shapes must wait.
    3. Among eligible shapes, place the one with the smallest visible area first
       (it will become the shallowest unassigned lord layer).

    Returns a list of shape indices ordered from deepest to shallowest,
    matching the order that build_layers expects (last in list = lord1 = shallowest).
    """
    def combined_geom(i):
        return geometries[i] if rings[i] is None else geometries[i].union(rings[i])

    remaining = list(visible_indices)
    orders = []

    while remaining:
        # Build combined silhouette of all remaining shapes
        remaining_geoms = [geometries[i] for i in remaining]
        remaining_geoms += [rings[i] for i in remaining if rings[i] is not None]
        combined = unary_union(remaining_geoms)
        outer_boundary = combined.boundary

        # Eligible shapes are those touching the outer boundary
        eligible = [i for i in remaining if combined_geom(i).intersects(outer_boundary)]

        # Fallback: if nothing qualifies (shouldn't happen), use all remaining
        if not eligible:
            eligible = remaining

        # Place the eligible shape with the smallest visible area next (it goes shallowest)
        next_idx = min(eligible, key=lambda i: visible_areas[i])
        orders.append(next_idx)
        remaining.remove(next_idx)

    # orders is currently shallowest-first; build_layers expects deepest-first
    orders.reverse()
    return orders


# --- Layer generation ---

def compute_visible_geometries(orders, geometries, rings):
    """Compute the JSON-visible ring and inner_fill for each visible shape.
    A shape's visible portion = its geometry minus all shapes drawn on top of it
    (higher JSON index). This is independent of lord order.
    Returns (vis_ring, vis_fill): dicts mapping shape index to clipped geometry.
    vis_ring[idx] is None for shapes with no ring (stroke_width == 0).
    """
    n = len(geometries)
    vis_ring = {}
    vis_fill = {}

    for idx in orders:
        above = [geometries[j] for j in range(idx + 1, n)]
        above += [rings[j] for j in range(idx + 1, n) if rings[j] is not None]
        cover = unary_union(above) if above else None

        if rings[idx] is not None:
            inner_fill = geometries[idx].difference(rings[idx])
            vis_ring[idx] = rings[idx].difference(cover) if cover else rings[idx]
            vis_fill[idx] = inner_fill.difference(cover) if cover else inner_fill
        else:
            vis_ring[idx] = None
            vis_fill[idx] = geometries[idx].difference(cover) if cover else geometries[idx]

    return vis_ring, vis_fill


def build_layers(orders, geometries, rings, canvas):
    """Generate the ordered stack of laser cut layers using a top-down approach.
    Lord order (outside-in) determines which shape is rendered at each layer depth.
    JSON order determines what is rendered: each shape's contribution is clipped to
    its JSON-visible portion via compute_visible_geometries.
    Starts with the top window (union of all visible extents), then progressively
    fills in each shape's ring then fill, shallowest lord first.
    Returns a list of (geometry, lord_label, is_ring) tuples, shallowest to deepest.
    """
    vis_ring, vis_fill = compute_visible_geometries(orders, geometries, rings)

    # Window = union of all visible shape extents (vis_ring + vis_fill covers full extent)
    all_vis = [vis_fill[i] for i in orders] + [vis_ring[i] for i in orders if vis_ring[i] is not None]
    window_hole = unary_union([g for g in all_vis if not g.is_empty])

    current_hole = window_hole
    layers = [(canvas.difference(window_hole), "window", False)]

    lord_number = 1
    for idx in reversed(orders):  # orders is deepest-first; reverse = shallowest-first
        vring = vis_ring[idx]
        vfill = vis_fill[idx]

        if vring is not None:
            # Ring fills in first (shallower), then inner fill (deeper)
            current_hole = current_hole.difference(vring)
            layers.append((canvas.difference(current_hole), lord_number, True))
            current_hole = current_hole.difference(vfill)
            layers.append((canvas.difference(current_hole), lord_number, False))
        else:
            current_hole = current_hole.difference(vfill)
            layers.append((canvas.difference(current_hole), lord_number, False))

        lord_number += 1

    # Base layer: solid canvas at the bottom
    layers.append((canvas, "base", False))
    return layers


# --- Tapering ---

def apply_taper(layers, canvas_size, taper_px):
    """Shrink each layer's geometry inward by taper_px per side per step above the base.
    The base layer (last) is full size. Each layer above loses taper_px pixels per side.
    """
    if taper_px == 0:
        return layers
    w, h = canvas_size
    n = len(layers)
    tapered = []
    for i, (geom, lord, is_ring) in enumerate(layers):
        depth_from_base = n - 1 - i  # base=0, window/shallowest=n-1
        shrink = depth_from_base * taper_px
        if shrink == 0:
            tapered.append((geom, lord, is_ring))
        else:
            clip = box(shrink, shrink, w - shrink, h - shrink)
            tapered.append((geom.intersection(clip), lord, is_ring))
    return tapered


# --- SVG/PNG output ---

def save_layer_svg(geometry, canvas_size, filename):
    """Write a single layer geometry as a black-filled SVG, then render to PNG."""
    w, h = canvas_size
    path_data = geometry.svg()
    ds = re.findall(r'd="([^"]+)"', path_data)
    combined_d = " ".join(ds)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><path fill-rule="evenodd" d="{combined_d}" fill="black"/></svg>'
    with open(filename, "w") as f:
        f.write(svg)


def save_all_layers(layers, canvas_size, base_name, appellation, output_dir):
    """Save all layers as SVG and PNG files inside output_dir.
    Files are named: [abs_layer_number]_[base_name]_[appellation]_[lord]_[ring if applicable]
    Layer 001 is the shallowest (top window), the final layer is the solid base.
    """
    for abs_pos, (layer, lord, is_ring) in enumerate(layers):
        ring_part = "_ring" if is_ring else ""
        lord_part = lord if lord in ("base", "window") else f"lord{lord}"
        stem = f"{abs_pos+1:03d}_{base_name}_{appellation}_{lord_part}{ring_part}"
        svg_name = os.path.join(output_dir, f"{stem}.svg")
        png_name = os.path.join(output_dir, f"{stem}.png")
        save_layer_svg(layer, canvas_size, svg_name)
        cairosvg.svg2png(url=svg_name, write_to=png_name, background_color="white")


def save_preview_png(shapes, canvas_size, filename, visible_indices, orders, output_dir):
    """Render a debug preview PNG showing all visible shapes in random colors.
    Shapes are drawn in their original JSON index order so the image matches
    the shapefuncJSON-generated PNG visually, just with randomised colors.
    Labels reflect each shape's assigned lord number and are drawn in a second
    pass so they always appear on top.
    """
    def random_color():
        return "rgb({},{},{})".format(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

    # Build lookup: shape index -> lord number (lord1 = shallowest = last in orders)
    lord_map = {idx: len(orders) - pos for pos, idx in enumerate(orders)}

    w, h = canvas_size
    filename = os.path.join(output_dir, filename)
    dwg = svgwrite.Drawing(filename.replace(".png", ".svg"), size=(w, h))

    labels = []
    for idx in visible_indices:
        shape = shapes[idx]
        sw = shape["stroke_width"]
        fill = random_color()
        stroke = random_color()
        if shape["type"] == "circle":
            dwg.add(dwg.circle(
                center=(shape["cx"], shape["cy"]),
                r=shape["r"],
                fill=fill,
                stroke=stroke,
                stroke_width=sw,
            ))
            label_x, label_y = shape["cx"], shape["cy"]
        elif "points" in shape:
            dwg.add(dwg.polygon(
                points=shape["points"],
                fill=fill,
                stroke=stroke,
                stroke_width=sw,
            ))
            pts = shape["points"]
            label_x = sum(p[0] for p in pts) / len(pts)
            label_y = sum(p[1] for p in pts) / len(pts)
        labels.append((str(lord_map[idx]), label_x, label_y))

    for text, label_x, label_y in labels:
        dwg.add(dwg.text(
            text,
            insert=(label_x, label_y),
            text_anchor="middle",
            dominant_baseline="central",
            font_size="12pt",
            font_family="Arial",
            font_weight="bold",
            fill="red",
        ))

    dwg.add(dwg.text(
        "DEBUG PREVIEW: Proposed Output Order",
        insert=(8, 20),
        font_size="12pt",
        font_family="Arial",
        font_weight="bold",
        fill="red",
    ))

    dwg.save()
    cairosvg.svg2png(url=filename.replace(".png", ".svg"), write_to=filename, background_color="white")


# --- Main ---

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, default=FILE_TO_PREP)
    parser.add_argument("--app", type=str, default=APPELLATION)
    parser.add_argument("--taper", type=int, default=TAPER_PX)
    args = parser.parse_args()

    canvas_size, shapes, base_name = load_shapes(args.file)
    canvas = box(0, 0, canvas_size[0], canvas_size[1])

    output_dir = os.path.join("output", f"{base_name}_layers")
    os.makedirs(output_dir, exist_ok=True)

    geometries, rings = build_geometries(shapes)
    visible_indices, visible_areas = filter_visible(shapes, geometries, rings)
    orders = compute_ordering(visible_indices, visible_areas, geometries, rings)
    layers = build_layers(orders, geometries, rings, canvas)
    layers = apply_taper(layers, canvas_size, args.taper)

    save_preview_png(shapes, canvas_size, f"{base_name}_{args.app}_preview.png", visible_indices, orders, output_dir)
    save_all_layers(layers, canvas_size, base_name, args.app, output_dir)


if __name__ == "__main__":
    main()
