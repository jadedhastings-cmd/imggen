import svgwrite
import cairosvg
import random
import argparse
import math
import json
import os
import glob

DEBUG_MODE = True

#Number of outputs
NUM_FILES = 5

#number of shapes to be generated
NUM_SHAPES = 10

#What to name the output files
OUTPUT_NAME = "shapes"

# Canvas size
CANVAS_SIZE = (800, 800)

# Profiles
PROFILES = [{
        "weight": 1,
        "shape": "circle",
        "x_min": 200, "x_max": 600,
        "y_min": 200, "y_max": 600,
        "r_min": 50, "r_max": 100,
        "fill_r_min": 0, "fill_r_max": 255,
        "fill_g_min": 0, "fill_g_max": 255,
        "fill_b_min": 0, "fill_b_max": 255,
        "stroke_r_min": 0, "stroke_r_max": 255,
        "stroke_g_min": 0, "stroke_g_max": 255,
        "stroke_b_min": 0, "stroke_b_max": 255,
        "stroke_width_min": 10, "stroke_width_max":20
    },
    {
        "weight": 1,
        "shape": "circle",
        "x_min": 300, "x_max": 500,
        "y_min": 300, "y_max": 500,
        "r_min": 100, "r_max": 200,
        "fill_r_min": 0, "fill_r_max": 255,
        "fill_g_min": 0, "fill_g_max": 255,
        "fill_b_min": 0, "fill_b_max": 255,
        "stroke_r_min": 0, "stroke_r_max": 255,
        "stroke_g_min": 0, "stroke_g_max": 255,
        "stroke_b_min": 0, "stroke_b_max": 255,
        "stroke_width_min": 10, "stroke_width_max":50
    },
    {
        "weight": 0,
        "shape": "polygon",
        "x_min": 300, "x_max": 500,
        "y_min": 300, "y_max": 500,
        "r_min": 40, "r_max": 220,
        "sides_min": 3, "sides_max": 10,
        "fill_r_min": 0, "fill_r_max": 255,
        "fill_g_min": 0, "fill_g_max": 255,
        "fill_b_min": 0, "fill_b_max": 255,
        "stroke_r_min": 0, "stroke_r_max": 255,
        "stroke_g_min": 0, "stroke_g_max": 255,
        "stroke_b_min": 0, "stroke_b_max": 255,
        "stroke_width_min": 10, "stroke_width_max":20
    },]  # same as before


def export_json(shapes, filename):
    data = {
        "canvas_size": CANVAS_SIZE,
        "shapes": shapes
    }

    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

def make_polygon_points(cx, cy, r, sides, rotation):
    points = []
    for i in range(sides):
        angle = rotation + (2 * math.pi * i / sides)
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))
    return points

def random_color(p, prefix="fill"):
    return "rgb({},{},{})".format(
        random.randint(p[f"{prefix}_r_min"], p[f"{prefix}_r_max"]),
        random.randint(p[f"{prefix}_g_min"], p[f"{prefix}_g_max"]),
        random.randint(p[f"{prefix}_b_min"], p[f"{prefix}_b_max"]),
    )


def random_geometry(p):
    cx = random.randint(p["x_min"], p["x_max"])
    cy = random.randint(p["y_min"], p["y_max"])
    r = random.randint(p["r_min"], p["r_max"])
    return cx, cy, r

def draw_circle(dwg, p):
    # picks random position/size, calls dwg.add()
    cx, cy, r = random_geometry(p)
    stroke_width1=random.randint(p["stroke_width_min"],p["stroke_width_max"])
    dwg.add(dwg.circle(
            center=(cx, cy), r=r,
            fill=random_color(p,"fill"),
            stroke=random_color(p,"stroke"),
            stroke_width=stroke_width1,
    ))
    return{
        "type": "circle",
        "cx": cx,
        "cy": cy,
        "r": r,
        "stroke_width": stroke_width1,
    }

def draw_polygon(dwg, p):
    # picks random position/size/sides/rotation, calls dwg.add()
    cx, cy, r = random_geometry(p)
    stroke_width2=random.randint(p["stroke_width_min"],p["stroke_width_max"])
    sides = random.randint(p["sides_min"], p["sides_max"])
    rotation = random.uniform(0, 2 * math.pi)
    points = make_polygon_points(cx, cy, r, sides, rotation)
    dwg.add(dwg.polygon(
        points=points,
        fill=random_color(p, "fill"),
        stroke=random_color(p, "stroke"),
        stroke_width=stroke_width2
    ))
    return {
        "type": "polygon",
        "points": points,
        "stroke_width": stroke_width2,
    }
    

def draw_debug_label(dwg, shape_data, idx):
    if shape_data["type"] == "circle":
        tx, ty = shape_data["cx"], shape_data["cy"]
    else:
        pts = shape_data["points"]
        tx = sum(pt[0] for pt in pts) / len(pts)
        ty = sum(pt[1] for pt in pts) / len(pts)
    dwg.add(dwg.text(
        str(idx),
        insert=(tx, ty),
        fill="red",
        font_size="12pt",
        font_family="Arial",
        font_weight="bold",
        text_anchor="middle",
        dominant_baseline="central",
    ))

def draw_shape(dwg, p):
    # routes to the right function based on p["shape"]
    if p["shape"] == "circle":
       return draw_circle(dwg,p)

    elif p["shape"] == "polygon":
        return draw_polygon(dwg, p)
    

def main():
    # parse args, build weighted list, loop, save, convert
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=NUM_SHAPES)
    args = parser.parse_args()
    num_shapes = args.count

    # Build weighted profile list
    weighted_profiles = []
    for profile in PROFILES:
        weighted_profiles.extend([profile] * profile["weight"])

    # Find the highest existing file number to avoid overwriting
    existing = glob.glob(f"{OUTPUT_NAME}*.json")
    existing_nums = []
    for f in existing:
        stem = os.path.splitext(os.path.basename(f))[0]
        suffix = stem[len(OUTPUT_NAME):]
        if suffix.isdigit():
            existing_nums.append(int(suffix))
    start = max(existing_nums) + 1 if existing_nums else 1

    # SVG
    for i in range(start, start + NUM_FILES):
        dwg = svgwrite.Drawing(f"{OUTPUT_NAME}{i}.svg", size=CANVAS_SIZE)
        shapes = []

        for idx in range(num_shapes):
            p = random.choice(weighted_profiles)
            shape_data = {"initial_layer": idx, **draw_shape(dwg, p)}
            shapes.append(shape_data)

        if DEBUG_MODE:
            for idx, shape_data in enumerate(shapes):
                draw_debug_label(dwg, shape_data, idx)

        dwg.save()
        cairosvg.svg2png(url=f"{OUTPUT_NAME}{i}.svg", write_to=f"{OUTPUT_NAME}{i}.png", background_color="white")
        export_json(shapes, f"{OUTPUT_NAME}{i}.json")

main()