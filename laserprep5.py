import argparse
import json
import random
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.geometry import box
import svgwrite
import cairosvg

FILE_TO_PREP = "shapes1.json"
APPELLATION = "laser"


parser = argparse.ArgumentParser()
parser.add_argument("--file", type=str, default=FILE_TO_PREP)
parser.add_argument("--app", type=str, default=APPELLATION)
args = parser.parse_args()
prepfile = args.file
appellation = args.app


with open(prepfile, "r") as f:
    shapes_data = json.load(f)

canvas_size = tuple(shapes_data["canvas_size"])
shapes = shapes_data["shapes"]
base_name = prepfile.replace(".json", "")

geometries = []
rings = []

def to_shapely(shape):
    sw = shape["stroke_width"]
    if shape["type"] == "circle":
        fill = Point(shape["cx"], shape["cy"]).buffer(shape["r"])
    elif shape["type"] == "polygon":
        fill = Polygon(shape["points"])

    outer = fill.buffer(sw / 2)
    inner = fill.buffer(-sw / 2)
    ring = outer.difference(inner)
    return fill, ring

def save_layer_svg(geometry, filename):
    w, h = canvas_size
    path_data = geometry.svg()
    import re
    d = re.search(r'd="([^"]+)"', path_data).group(1)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><path d="{d}" fill="black"/></svg>'
    with open(filename, "w") as f:
        f.write(svg)

for shape in shapes:
    fill, ring = to_shapely(shape)
    geometries.append(fill)
    if shape["stroke_width"] == 0:
        rings.append(None)
    else:
        rings.append(ring)

# Discard shapes that are entirely covered by shapes drawn on top of them.
# A shape is visible if any part of its geometry (fill + ring) is not covered
# by the union of all shapes with a higher index (drawn later = on top).
visible_indices = []
for i in range(len(shapes)):
    shapes_above = [geometries[j] for j in range(i + 1, len(shapes))]
    shapes_above += [rings[j] for j in range(i + 1, len(shapes)) if rings[j] is not None]
    if shapes_above:
        cover = unary_union(shapes_above)
        shape_area = geometries[i]
        if rings[i] is not None:
            shape_area = shape_area.union(rings[i])
        visible = shape_area.difference(cover)
        if visible.area < 1e-6:
            continue
    visible_indices.append(i)

with open("containers.txt", "w") as f:
    f.write("visible indices after occlusion filter: " + str(visible_indices))

# orders starts from the visible indices in their original order
orders = list(visible_indices)

with open("orders.txt", "w") as f:
    f.write(str(orders))

canvas = box(0, 0, canvas_size[0], canvas_size[1])
accumulated_holes = canvas
# layers stores (geometry, lord_position, is_ring)
layers = []

for order_pos, idx in enumerate(orders):
    lord = len(orders) - order_pos
    accumulated_holes = accumulated_holes.difference(geometries[idx])
    layers.append((accumulated_holes, lord, False))
    if rings[idx] is not None:
        accumulated_holes = accumulated_holes.difference(rings[idx])
        layers.append((accumulated_holes, lord, True))

layers.insert(0, (canvas, "base", False))


def save_preview_png(shapes, canvas_size, filename, orders):
    def random_color():
        return "rgb({},{},{})".format(random.randint(0,255), random.randint(0,255), random.randint(0,255))
    w, h = canvas_size
    dwg = svgwrite.Drawing(filename.replace(".png", ".svg"), size=(w, h))

    labels = []
    for order_pos, idx in enumerate(orders):
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
        elif shape["type"] == "polygon":
            dwg.add(dwg.polygon(
                points=shape["points"],
                fill=fill,
                stroke=stroke,
                stroke_width=sw,
            ))
            pts = shape["points"]
            label_x = sum(p[0] for p in pts) / len(pts)
            label_y = sum(p[1] for p in pts) / len(pts)
        labels.append((str(order_pos + 1), label_x, label_y))

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

save_preview_png(shapes, canvas_size, f"{base_name}_{appellation}_preview.png", orders)

for abs_pos, (layer, lord, is_ring) in enumerate(reversed(layers)):
    ring_part = "_ring" if is_ring else ""
    lord_part = f"lord{lord}" if lord != "base" else "base"
    stem = f"{abs_pos+1:03d}_{base_name}_{appellation}_{lord_part}{ring_part}"
    svg_name = f"{stem}.svg"
    png_name = f"{stem}.png"
    save_layer_svg(layer, svg_name)
    cairosvg.svg2png(url=svg_name, write_to=png_name, background_color="white")
