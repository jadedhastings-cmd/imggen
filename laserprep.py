import argparse
import json
import os
import re
import random
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
import svgwrite
import cairosvg

FILE_TO_PREP  = "shapes1.json"
APPELLATION   = "laser"
TAPER_PX      = 1                # pixels shrunk per side per layer above the base
ASSEMBLY_MODE = "subtractive"    # "subtractive" | "additive"


# --- Load input data ---

def load_shapes(filepath):
    with open(filepath) as f:
        data = json.load(f)
    return tuple(data["canvas_size"]), data["shapes"], os.path.splitext(os.path.basename(filepath))[0]


# --- Geometry construction ---

def to_shapely(shape):
    """Convert a shape dict to (fill, ring). Ring is None if stroke_width == 0."""
    sw = shape["stroke_width"]
    if shape["type"] == "circle":
        base_fill = Point(shape["cx"], shape["cy"]).buffer(shape["r"])
    elif shape["type"] in ("polygon", "star", "cross"):
        base_fill = Polygon(shape["points"])
    else:  # contour-based types
        polys = []
        for c in shape["contours"]:
            if len(c) >= 3:
                try:
                    p = Polygon(c)
                    if not p.is_valid:
                        p = p.buffer(0)
                    if p.area > 0:
                        polys.append(p)
                except Exception:
                    pass
        if not polys:
            return Polygon(), None
        polys.sort(key=lambda p: p.area, reverse=True)
        outers, holes = [], []
        for p in polys:
            (holes if any(o.contains(p.centroid) for o in outers) else outers).append(p)
        base_fill = unary_union(outers)
        for h in holes:
            base_fill = base_fill.difference(h)

    if sw == 0:
        ring = None
    else:
        ring = base_fill.buffer(sw / 2).difference(base_fill.buffer(-sw / 2))

    return (Polygon(), ring) if shape.get("fill_transparent") else (base_fill, ring)


def build_geometries(shapes):
    pairs = [to_shapely(s) for s in shapes]
    return [p[0] for p in pairs], [p[1] for p in pairs]


def _full_geom(i, geometries, rings):
    """Union of fill and ring for shape i."""
    return geometries[i].union(rings[i]) if rings[i] is not None else geometries[i]


def _above_covers(geometries, rings):
    """For each index i, compute the union of all shapes at indices > i. O(N)."""
    n, covers, running = len(geometries), [None] * len(geometries), Polygon()
    for i in range(n - 1, -1, -1):
        covers[i] = running if not running.is_empty else None
        running = running.union(_full_geom(i, geometries, rings))
    return covers


# --- Occlusion filtering and ordering ---

def filter_visible(shapes, geometries, rings):
    covers = _above_covers(geometries, rings)
    visible_indices, visible_areas = [], {}
    for i in range(len(shapes)):
        full = _full_geom(i, geometries, rings)
        visible = full.difference(covers[i]) if covers[i] is not None else full
        if visible.area >= 1e-6:
            visible_indices.append(i)
            visible_areas[i] = visible.area
    return visible_indices, visible_areas


def build_nest_groups(shapes):
    raw = {}
    for i, shape in enumerate(shapes):
        if gid := shape.get("nest_group"):
            raw.setdefault(gid, []).append((shape.get("nest_ring_index", 0), i))
    return {gid: [idx for _, idx in sorted(members)] for gid, members in raw.items()}


def compute_ordering(visible_indices, visible_areas, geometries, rings, shapes, nest_groups):
    """Order visible shapes outermost-to-innermost (smallest visible area first).
    Nest groups are placed atomically in outermost-first order.
    Returns indices deepest-first (last = lord1 = shallowest).
    """
    shape_nest = {i: s["nest_group"] for i, s in enumerate(shapes)
                  if (gid := s.get("nest_group")) and gid in nest_groups}

    remaining, remaining_set = list(visible_indices), set(visible_indices)
    orders = []

    while remaining:
        combined    = unary_union([_full_geom(i, geometries, rings) for i in remaining])
        boundary    = combined.boundary
        eligible    = [i for i in remaining if _full_geom(i, geometries, rings).intersects(boundary)] or remaining
        next_idx    = min(eligible, key=lambda i: visible_areas[i])

        if gid := shape_nest.get(next_idx):
            for idx in [idx for idx in nest_groups[gid] if idx in remaining_set]:
                orders.append(idx)
                remaining_set.discard(idx)
            remaining = [i for i in remaining if i in remaining_set]
        else:
            orders.append(next_idx)
            remaining.remove(next_idx)
            remaining_set.discard(next_idx)

    orders.reverse()
    return orders


# --- Layer generation ---

def _compute_visible_geometries(orders, geometries, rings):
    """Clip each shape's ring and fill to its JSON-visible portion. O(N) cover pass."""
    covers = _above_covers(geometries, rings)
    vis_ring, vis_fill = {}, {}
    for idx in orders:
        cover = covers[idx]
        if rings[idx] is not None:
            inner = geometries[idx].difference(rings[idx])
            vis_ring[idx] = rings[idx].difference(cover) if cover else rings[idx]
            vis_fill[idx] = inner.difference(cover) if cover else inner
        else:
            vis_ring[idx] = None
            vis_fill[idx] = geometries[idx].difference(cover) if cover else geometries[idx]
    return vis_ring, vis_fill


def build_layers_subtractive(orders, geometries, rings, canvas):
    """Each lord layer is a full canvas rectangle with progressive holes cut out."""
    vis_ring, vis_fill = _compute_visible_geometries(orders, geometries, rings)

    all_vis = [g for i in orders for g in (vis_ring[i], vis_fill[i]) if g is not None and not g.is_empty]
    window_hole  = unary_union(all_vis)
    current_hole = window_hole
    layers = [(canvas.difference(window_hole), "window", False)]

    for lord, idx in enumerate(reversed(orders), 1):
        for geom, is_ring in [(vis_ring[idx], True), (vis_fill[idx], False)]:
            if geom is not None and not geom.is_empty:
                current_hole = current_hole.difference(geom)
                layers.append((canvas.difference(current_hole), lord, is_ring))

    layers.append((canvas, "base", False))
    return layers


def build_layers_additive(visible_indices, geometries, rings, canvas):
    """Layers are cumulative unions built top-shape-first (reversed JSON order).
    No ordering computation needed — render order is the lord order.
    """
    window_hole   = unary_union([_full_geom(i, geometries, rings) for i in visible_indices])
    current_solid = Polygon()
    layers = [(canvas.difference(window_hole), "window", False)]

    for lord, idx in enumerate(reversed(visible_indices), 1):
        ring       = rings[idx]
        inner_fill = geometries[idx].difference(ring) if ring is not None else geometries[idx]
        for geom, is_ring in [(ring, True), (inner_fill, False)]:
            if geom is not None and not geom.is_empty:
                current_solid = current_solid.union(geom)
                layers.append((current_solid, lord, is_ring))

    layers.append((canvas, "base", False))
    return layers


# --- Tapering ---

def apply_taper(layers, canvas_size, taper_px):
    if taper_px == 0:
        return layers
    w, h, n = *canvas_size, len(layers)
    def taper(i, geom):
        shrink = (n - 1 - i) * taper_px
        return geom if shrink == 0 else geom.intersection(box(shrink, shrink, w - shrink, h - shrink))
    return [(taper(i, g), lord, is_ring) for i, (g, lord, is_ring) in enumerate(layers)]


# --- SVG/PNG output ---

def save_layer_svg(geometry, canvas_size, filename):
    w, h = canvas_size
    ds = re.findall(r'd="([^"]+)"', geometry.svg())
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
           f'<path fill-rule="evenodd" d="{" ".join(ds)}" fill="black"/></svg>')
    with open(filename, "w") as f:
        f.write(svg)


def save_all_layers(layers, canvas_size, base_name, appellation, output_dir):
    for pos, (layer, lord, is_ring) in enumerate(layers):
        ring_part = "_ring" if is_ring else ""
        lord_part = lord if lord in ("base", "window") else f"lord{lord}"
        stem      = f"{pos+1:03d}_{base_name}_{appellation}_{lord_part}{ring_part}"
        svg_path  = os.path.join(output_dir, f"{stem}.svg")
        png_path  = os.path.join(output_dir, f"{stem}.png")
        save_layer_svg(layer, canvas_size, svg_path)
        cairosvg.svg2png(url=svg_path, write_to=png_path, background_color="white")


def save_preview_png(shapes, canvas_size, filename, visible_indices, orders, output_dir):
    def rand_color():
        return "rgb({},{},{})".format(*[random.randint(0, 255) for _ in range(3)])

    lord_map = {idx: len(orders) - pos for pos, idx in enumerate(orders)}
    w, h     = canvas_size
    filepath = os.path.join(output_dir, filename)
    dwg      = svgwrite.Drawing(filepath.replace(".png", ".svg"), size=(w, h))
    labels   = []

    for idx in visible_indices:
        shape  = shapes[idx]
        sw     = shape["stroke_width"]
        fill   = "none" if shape.get("fill_transparent") else rand_color()
        stroke = rand_color()

        if shape["type"] == "circle":
            dwg.add(dwg.circle(center=(shape["cx"], shape["cy"]), r=shape["r"],
                               fill=fill, stroke=stroke, stroke_width=sw))
            lx, ly = shape["cx"], shape["cy"]
        elif shape["type"] in ("text", "constellation", "bumped_polygon", "daisy", "petal", "line"):
            path_d = " ".join(
                f"M {pts[0][0]:.2f},{pts[0][1]:.2f} " +
                " ".join(f"L {p[0]:.2f},{p[1]:.2f}" for p in pts[1:]) + " Z"
                for pts in shape["contours"])
            dwg.add(dwg.path(d=path_d, fill=fill, fill_rule="evenodd", stroke=stroke, stroke_width=sw))
            lx, ly = shape["cx"], shape["cy"]
        else:
            pts = shape["points"]
            dwg.add(dwg.polygon(points=pts, fill=fill, stroke=stroke, stroke_width=sw))
            lx = sum(p[0] for p in pts) / len(pts)
            ly = sum(p[1] for p in pts) / len(pts)
        labels.append((str(lord_map[idx]), lx, ly))

    text_style = dict(text_anchor="middle", dominant_baseline="central",
                      font_size="12pt", font_family="Arial", font_weight="bold")
    for text, lx, ly in labels:
        dwg.add(dwg.text(text, insert=(lx, ly), fill="red", **text_style))
    dwg.add(dwg.text("DEBUG PREVIEW: Proposed Output Order", insert=(8, 20), fill="red", **text_style))

    dwg.save()
    cairosvg.svg2png(url=filepath.replace(".png", ".svg"), write_to=filepath, background_color="white")


# --- Main ---

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file",  default=FILE_TO_PREP)
    parser.add_argument("--app",   default=APPELLATION)
    parser.add_argument("--taper", default=TAPER_PX, type=float)
    parser.add_argument("--mode",  default=ASSEMBLY_MODE, choices=["subtractive", "additive"])
    args = parser.parse_args()

    canvas_size, shapes, base_name = load_shapes(args.file)
    canvas     = box(0, 0, *canvas_size)
    output_dir = os.path.join("output", f"{base_name}_layers")
    os.makedirs(output_dir, exist_ok=True)

    geometries, rings          = build_geometries(shapes)
    visible_indices, vis_areas = filter_visible(shapes, geometries, rings)

    if args.mode == "additive":
        layers = build_layers_additive(visible_indices, geometries, rings, canvas)
        orders = list(reversed(visible_indices))
    else:
        nest_groups = build_nest_groups(shapes)
        orders      = compute_ordering(visible_indices, vis_areas, geometries, rings, shapes, nest_groups)
        layers      = build_layers_subtractive(orders, geometries, rings, canvas)

    layers = apply_taper(layers, canvas_size, args.taper)
    save_preview_png(shapes, canvas_size, f"{base_name}_{args.app}_preview.png", visible_indices, orders, output_dir)
    save_all_layers(layers, canvas_size, base_name, args.app, output_dir)


if __name__ == "__main__":
    main()
