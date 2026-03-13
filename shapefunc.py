import svgwrite
import cairosvg
import random
import argparse
import math

#Number of outputs
NUM_FILES = 3

#number of shapes to be generated
NUM_SHAPES = 20

#What to name the output files
OUTPUT_NAME = "shapes"

# Canvas size
CANVAS_SIZE = (800, 800)

# Profiles
PROFILES = [{
        "weight": 3,
        "shape": "circle",
        "x_min": 50, "x_max": 750,
        "y_min": 50, "y_max": 750,
        "r_min": 10, "r_max": 20,
        "fill_r_min": 0, "fill_r_max": 255,
        "fill_g_min": 0, "fill_g_max": 255,
        "fill_b_min": 0, "fill_b_max": 255,
        "stroke_r_min": 0, "stroke_r_max": 255,
        "stroke_g_min": 0, "stroke_g_max": 255,
        "stroke_b_min": 0, "stroke_b_max": 255,
        "stroke_width_min": 1, "stroke_width_max":10
    },
    {
        "weight": 1,
        "shape": "circle",
        "x_min": 50, "x_max": 750,
        "y_min": 50, "y_max": 750,
        "r_min": 100, "r_max": 200,
        "fill_r_min": 0, "fill_r_max": 255,
        "fill_g_min": 0, "fill_g_max": 255,
        "fill_b_min": 0, "fill_b_max": 255,
        "stroke_r_min": 0, "stroke_r_max": 255,
        "stroke_g_min": 0, "stroke_g_max": 255,
        "stroke_b_min": 0, "stroke_b_max": 255,
        "stroke_width_min": 1, "stroke_width_max":10
    },
    {
        "weight": 2,
        "shape": "polygon",
        "x_min": 50, "x_max": 750,
        "y_min": 50, "y_max": 750,
        "r_min": 20, "r_max": 80,
        "sides_min": 3, "sides_max": 8,
        "fill_r_min": 0, "fill_r_max": 255,
        "fill_g_min": 0, "fill_g_max": 255,
        "fill_b_min": 0, "fill_b_max": 255,
        "stroke_r_min": 0, "stroke_r_max": 255,
        "stroke_g_min": 0, "stroke_g_max": 255,
        "stroke_b_min": 0, "stroke_b_max": 255,
        "stroke_width_min": 1, "stroke_width_max":10
    },]  # same as before

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
    dwg.add(dwg.circle(
            center=(cx, cy), r=r,
            fill=random_color(p,"fill"),
            stroke=random_color(p,"stroke"),
            stroke_width=random.randint(p["stroke_width_min"],p["stroke_width_max"])
    ))
def draw_polygon(dwg, p):
    # picks random position/size/sides/rotation, calls dwg.add()
    cx, cy, r = random_geometry(p)
    sides = random.randint(p["sides_min"], p["sides_max"])
    rotation = random.uniform(0, 2 * math.pi)
    points = make_polygon_points(cx, cy, r, sides, rotation)
    dwg.add(dwg.polygon(
        points=points,
        fill=random_color(p, "fill"),
        stroke=random_color(p, "stroke"),
        stroke_width=random.randint(p["stroke_width_min"],p["stroke_width_max"])
    ))
    

def draw_shape(dwg, p):
    # routes to the right function based on p["shape"]
    if p["shape"] == "circle":
        draw_circle(dwg,p)
    elif p["shape"] == "polygon":
        draw_polygon(dwg, p)
    

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

    # SVG
    for i in range(1, NUM_FILES + 1):
        dwg = svgwrite.Drawing(f"{OUTPUT_NAME}{i}.svg", size=CANVAS_SIZE)

        for _ in range(num_shapes):
            p = random.choice(weighted_profiles)
            draw_shape(dwg, p)

        dwg.save()
        cairosvg.svg2png(url=f"{OUTPUT_NAME}{i}.svg", write_to=f"{OUTPUT_NAME}{i}.png", background_color="white")
    

main()