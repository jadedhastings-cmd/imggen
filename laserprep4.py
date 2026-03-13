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

geometries =[]
rings =[]

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
    # Extract just the d="..." value
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

#create a dictionary of shapes and which shapes are contained within them
containers = {i: [] for i in range(len(geometries))}

#loop comparing shapes to fill in the containers dictionary
for i, shape in enumerate(shapes):

    for j, shape in enumerate(shapes):
        if i==j:
            continue
        else:
            if geometries[i].contains(geometries[j]):
                 containers[i].append(j)

#debug file containing the results of the containers test
with open("containers.txt", "w") as f:
    f.write(str(containers))

#orders will be the actual order for layers to be created. It starts in the default order
orders = list(range(len(geometries)))

#orders is then resorted
changed = True
while changed:
    changed = False
    for i, contained_list in containers.items():
        for j in contained_list:
            if orders.index(i) < orders.index(j):
                orders.remove(i)
                orders.insert(orders.index(j) + 1, i)
                changed = True

#debug file containing the results of the containers test
with open("orders.txt", "w") as f:
    f.write(str(orders))

canvas = box(0, 0, canvas_size[0], canvas_size[1])
accumulated_holes = canvas
layers = []

for idx in orders:
    accumulated_holes = accumulated_holes.difference(geometries[idx])
    layers.append(accumulated_holes)
    if rings[idx] is not None:
        accumulated_holes = accumulated_holes.difference(rings[idx])
        layers.append(accumulated_holes)


def save_preview_png(shapes, canvas_size, filename, orders):
    def random_color():
        return "rgb({},{},{})".format(random.randint(0,255), random.randint(0,255), random.randint(0,255))
    w, h = canvas_size
    dwg = svgwrite.Drawing(filename.replace(".png", ".svg"), size=(w, h))

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

        dwg.add(dwg.text(
            str(order_pos + 1),
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

for i, layer in enumerate(layers):
    svg_name = f"{base_name}_{appellation}_layer{i+1}.svg"
    png_name = f"{base_name}_{appellation}_layer{i+1}.png"
    save_layer_svg(layer, svg_name)
    cairosvg.svg2png(url=svg_name, write_to=png_name, background_color="white")
