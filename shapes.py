import svgwrite
import cairosvg
import random
import argparse
import math
import json
import os
import glob
from shapely.geometry import box as _shapely_box, Point as _ShapelyPoint, Polygon as _ShapelyPolygon
from shapely.affinity import rotate as _shapely_rotate, translate as _shapely_translate
from shapely.ops import unary_union as _shapely_union
import matplotlib
matplotlib.use('Agg')
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
import numpy as np

DEBUG_MODE = False

#Number of outputs
NUM_FILES = 5

#number of shapes to be generated
NUM_SHAPES = 10

#What to name the output files
OUTPUT_NAME = "shapes"

# Canvas size
CANVAS_WIDTH_IN = 8
CANVAS_HEIGHT_IN = 8
RESOLUTION = 100  # pixels per inch

CANVAS_SIZE = (CANVAS_WIDTH_IN * RESOLUTION, CANVAS_HEIGHT_IN * RESOLUTION)

# Profiles — loaded from PROFILE_*.json files in the same directory
PROFILES = []
for _profile_file in sorted(glob.glob("PROFILE_*.json")):
    with open(_profile_file) as _f:
        _data = json.load(_f)
        if isinstance(_data, list):
            PROFILES.extend(_data)
        else:
            PROFILES.append(_data)

if not PROFILES:
    raise RuntimeError("No profiles loaded. Add at least one PROFILE_*.json file.")


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

def make_star_points(cx, cy, r, inner_r, sides, rotation):
    points = []
    for i in range(sides):
        outer_angle = rotation + (2 * math.pi * i / sides)
        points.append((cx + r * math.cos(outer_angle), cy + r * math.sin(outer_angle)))
        inner_angle = rotation + (2 * math.pi * (i + 0.5) / sides)
        points.append((cx + inner_r * math.cos(inner_angle), cy + inner_r * math.sin(inner_angle)))
    return points

def make_cross_points(cx, cy, r, arm_width, num_arms):
    arm = _shapely_box(-arm_width / 2, 0, arm_width / 2, r)
    arms = []
    for i in range(num_arms):
        angle_deg = i * 360 / num_arms
        rotated = _shapely_rotate(arm, angle_deg, origin=(0, 0))
        rotated = _shapely_translate(rotated, cx, cy)
        arms.append(rotated)
    cross = _shapely_union(arms)
    return list(cross.exterior.coords[:-1])

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
    fill_color = "none" if p.get("fill_transparent") else random_color(p, "fill")
    dwg.add(dwg.circle(
            center=(cx, cy), r=r,
            fill=fill_color,
            stroke=random_color(p,"stroke"),
            stroke_width=stroke_width1,
    ))
    result = {"type": "circle", "cx": cx, "cy": cy, "r": r, "stroke_width": stroke_width1}
    if p.get("fill_transparent"):
        result["fill_transparent"] = True
    return result

def draw_polygon(dwg, p):
    # picks random position/size/sides/rotation, calls dwg.add()
    cx, cy, r = random_geometry(p)
    stroke_width2=random.randint(p["stroke_width_min"],p["stroke_width_max"])
    sides = random.randint(p["sides_min"], p["sides_max"])
    rotation = random.uniform(0, 2 * math.pi)
    points = make_polygon_points(cx, cy, r, sides, rotation)
    fill_color = "none" if p.get("fill_transparent") else random_color(p, "fill")
    dwg.add(dwg.polygon(
        points=points,
        fill=fill_color,
        stroke=random_color(p, "stroke"),
        stroke_width=stroke_width2
    ))
    result = {"type": "polygon", "points": points, "stroke_width": stroke_width2}
    if p.get("fill_transparent"):
        result["fill_transparent"] = True
    return result
    

def draw_star(dwg, p):
    cx, cy, r = random_geometry(p)
    inner_r = r * random.uniform(p["inner_r_ratio_min"], p["inner_r_ratio_max"])
    sides = random.randint(p["sides_min"], p["sides_max"])
    rotation = random.uniform(0, 2 * math.pi)
    stroke_width = random.randint(p["stroke_width_min"], p["stroke_width_max"])
    points = make_star_points(cx, cy, r, inner_r, sides, rotation)
    fill_color = "none" if p.get("fill_transparent") else random_color(p, "fill")
    dwg.add(dwg.polygon(
        points=points,
        fill=fill_color,
        stroke=random_color(p, "stroke"),
        stroke_width=stroke_width,
    ))
    result = {"type": "star", "points": points, "stroke_width": stroke_width}
    if p.get("fill_transparent"):
        result["fill_transparent"] = True
    return result

def draw_cross(dwg, p):
    cx, cy, r = random_geometry(p)
    arm_width = random.randint(p["arm_width_min"], p["arm_width_max"])
    num_arms = random.randint(p["sides_min"], p["sides_max"])
    stroke_width = random.randint(p["stroke_width_min"], p["stroke_width_max"])
    points = make_cross_points(cx, cy, r, arm_width, num_arms)
    fill_color = "none" if p.get("fill_transparent") else random_color(p, "fill")
    dwg.add(dwg.polygon(
        points=points,
        fill=fill_color,
        stroke=random_color(p, "stroke"),
        stroke_width=stroke_width,
    ))
    result = {"type": "cross", "points": points, "stroke_width": stroke_width}
    if p.get("fill_transparent"):
        result["fill_transparent"] = True
    return result

def _make_font_props(font_family):
    if os.path.isfile(font_family):
        return FontProperties(fname=font_family)
    return FontProperties(family=font_family, weight='bold')

def _center_and_flip(raw_polys, cx, cy):
    """Flip y axis and center the polygon group at (cx, cy)."""
    all_pts = np.vstack(raw_polys)
    bbox_cx = (all_pts[:, 0].min() + all_pts[:, 0].max()) / 2
    bbox_cy = (all_pts[:, 1].min() + all_pts[:, 1].max()) / 2
    return [
        [(float(pt[0] - bbox_cx + cx), float(-(pt[1] - bbox_cy) + cy)) for pt in poly]
        for poly in raw_polys
    ]

def make_text_contours(text, cx, cy, font_size, font_family="DejaVu Sans"):
    fp = _make_font_props(font_family)
    tp = TextPath((0, 0), text, size=font_size, prop=fp)
    raw_polys = tp.to_polygons()
    if not raw_polys:
        return []
    return _center_and_flip(raw_polys, cx, cy)

def make_letter_contours(text, cx, cy, font_size, font_family="DejaVu Sans", letter_spacing=0.08):
    """Returns list of (char, contours) tuples, one per non-space character,
    laid out side-by-side and centered as a group at (cx, cy)."""
    fp = _make_font_props(font_family)
    raw_letters = []
    x_cursor = 0.0
    for char in text:
        if char == ' ':
            x_cursor += font_size * 0.3
            continue
        tp = TextPath((0, 0), char, size=font_size, prop=fp)
        polys = tp.to_polygons()
        if polys:
            all_pts = np.vstack(polys)
            char_min_x = all_pts[:, 0].min()
            char_max_x = all_pts[:, 0].max()
            shifted = [[(float(pt[0] - char_min_x + x_cursor), float(pt[1])) for pt in poly] for poly in polys]
            raw_letters.append((char, shifted))
            x_cursor += (char_max_x - char_min_x) + font_size * letter_spacing
        else:
            x_cursor += font_size * 0.3

    if not raw_letters:
        return []

    # Center the whole group and flip y
    all_flat = [pt for _, group in raw_letters for poly in group for pt in poly]
    all_arr = np.array(all_flat)
    bbox_cx = (all_arr[:, 0].min() + all_arr[:, 0].max()) / 2
    bbox_cy = (all_arr[:, 1].min() + all_arr[:, 1].max()) / 2
    result = []
    for char, contours in raw_letters:
        flipped = [[(float(pt[0] - bbox_cx + cx), float(-(pt[1] - bbox_cy) + cy)) for pt in poly] for poly in contours]
        result.append((char, flipped))
    return result

def rotate_contours(contours, cx, cy, angle_deg):
    angle_rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
    return [
        [(cos_a * (x - cx) - sin_a * (y - cy) + cx,
          sin_a * (x - cx) + cos_a * (y - cy) + cy) for x, y in pts]
        for pts in contours
    ]

def _text_path_d(contours):
    return " ".join(
        f"M {pts[0][0]:.2f},{pts[0][1]:.2f} " +
        " ".join(f"L {pt[0]:.2f},{pt[1]:.2f}" for pt in pts[1:]) + " Z"
        for pts in contours
    )

def _text_shape_dict(char, cx, cy, font_size, rotation, contours, stroke_width, fill_transparent):
    result = {
        "type": "text",
        "text": char,
        "cx": cx, "cy": cy,
        "font_size": font_size,
        "rotation": rotation,
        "contours": [list(pts) for pts in contours],
        "stroke_width": stroke_width,
    }
    if fill_transparent:
        result["fill_transparent"] = True
    return result

def draw_text_shape(dwg, p):
    cx = random.randint(p["x_min"], p["x_max"])
    cy = random.randint(p["y_min"], p["y_max"])
    font_size = random.randint(p["font_size_min"], p["font_size_max"])
    font_family = p.get("font_family", "DejaVu Sans")
    stroke_width = random.randint(p["stroke_width_min"], p["stroke_width_max"])
    fill_transparent = bool(p.get("fill_transparent"))
    rotation = random.uniform(p.get("rotation_min", 0), p.get("rotation_max", 0))

    if p.get("letter_layers"):
        letters = make_letter_contours(p["text"], cx, cy, font_size, font_family)
        if not letters:
            return None
        if rotation != 0:
            letters = [(char, rotate_contours(contours, cx, cy, rotation)) for char, contours in letters]
        results = []
        for char, contours in letters:
            fill_color = "none" if fill_transparent else random_color(p, "fill")
            dwg.add(dwg.path(
                d=_text_path_d(contours),
                fill=fill_color,
                fill_rule="evenodd",
                stroke=random_color(p, "stroke"),
                stroke_width=stroke_width,
            ))
            letter_cx = sum(pt[0] for poly in contours for pt in poly) / max(sum(len(poly) for poly in contours), 1)
            letter_cy = sum(pt[1] for poly in contours for pt in poly) / max(sum(len(poly) for poly in contours), 1)
            results.append(_text_shape_dict(char, letter_cx, letter_cy, font_size, rotation, contours, stroke_width, fill_transparent))
        return results
    else:
        contours = make_text_contours(p["text"], cx, cy, font_size, font_family)
        if not contours:
            return None
        if rotation != 0:
            contours = rotate_contours(contours, cx, cy, rotation)
        fill_color = "none" if fill_transparent else random_color(p, "fill")
        dwg.add(dwg.path(
            d=_text_path_d(contours),
            fill=fill_color,
            fill_rule="evenodd",
            stroke=random_color(p, "stroke"),
            stroke_width=stroke_width,
        ))
        return _text_shape_dict(p["text"], cx, cy, font_size, rotation, contours, stroke_width, fill_transparent)

# --- Compound shape helpers ---

def _build_weighted_subs(sub_profiles):
    weighted = []
    for sp in sub_profiles:
        weighted.extend([sp] * sp.get("weight", 1))
    return weighted

def _scale_profile(p, scale):
    p = dict(p)
    for key in ("r_min", "r_max", "font_size_min", "font_size_max",
                "radius_min", "radius_max", "arm_width_min", "arm_width_max"):
        if key in p:
            p[key] = max(1, int(p[key] * scale))
    return p

def _geometry_to_contours(geom):
    contours = []
    if geom.geom_type == 'Polygon':
        if not geom.is_empty:
            contours.append([list(c) for c in geom.exterior.coords[:-1]])
            for interior in geom.interiors:
                contours.append([list(c) for c in interior.coords[:-1]])
    elif geom.geom_type in ('MultiPolygon', 'GeometryCollection'):
        for g in geom.geoms:
            contours.extend(_geometry_to_contours(g))
    return contours

def _contours_to_svg_path_d(contours):
    return " ".join(
        f"M {pts[0][0]:.2f},{pts[0][1]:.2f} " +
        " ".join(f"L {pt[0]:.2f},{pt[1]:.2f}" for pt in pts[1:]) + " Z"
        for pts in contours if pts
    )

def _profile_to_geometry(p, cx, cy):
    """Compute shapely geometry for a profile at (cx, cy) without SVG drawing."""
    shape = p["shape"]
    if shape == "circle":
        r = random.randint(p["r_min"], p["r_max"])
        return _ShapelyPoint(cx, cy).buffer(r)
    elif shape == "polygon":
        r = random.randint(p["r_min"], p["r_max"])
        sides = random.randint(p["sides_min"], p["sides_max"])
        rotation = random.uniform(0, 2 * math.pi)
        return _ShapelyPolygon(make_polygon_points(cx, cy, r, sides, rotation))
    elif shape == "star":
        r = random.randint(p["r_min"], p["r_max"])
        inner_r = r * random.uniform(p["inner_r_ratio_min"], p["inner_r_ratio_max"])
        sides = random.randint(p["sides_min"], p["sides_max"])
        rotation = random.uniform(0, 2 * math.pi)
        return _ShapelyPolygon(make_star_points(cx, cy, r, inner_r, sides, rotation))
    elif shape == "cross":
        r = random.randint(p["r_min"], p["r_max"])
        arm_width = random.randint(p["arm_width_min"], p["arm_width_max"])
        num_arms = random.randint(p["sides_min"], p["sides_max"])
        return _ShapelyPolygon(make_cross_points(cx, cy, r, arm_width, num_arms))
    elif shape == "text":
        font_size = random.randint(p["font_size_min"], p["font_size_max"])
        font_family = p.get("font_family", "DejaVu Sans")
        rotation = random.uniform(p.get("rotation_min", 0), p.get("rotation_max", 0))
        contours = make_text_contours(p["text"], cx, cy, font_size, font_family)
        if rotation != 0:
            contours = rotate_contours(contours, cx, cy, rotation)
        polys = [_ShapelyPolygon(c) for c in contours if len(c) >= 3]
        if not polys:
            return _ShapelyPolygon()
        polys.sort(key=lambda poly: poly.area, reverse=True)
        outer, holes = [], []
        for poly in polys:
            if any(op.contains(poly.centroid) for op in outer):
                holes.append(poly)
            else:
                outer.append(poly)
        result = _shapely_union(outer)
        for h in holes:
            result = result.difference(h)
        return result
    elif shape == "constellation":
        return _constellation_geometry(p, cx, cy)
    elif shape == "nest":
        return _nest_geometry(p, cx, cy)
    return _ShapelyPolygon()

def _constellation_geometry(p, cx, cy):
    radius = random.randint(p["radius_min"], p["radius_max"])
    count = random.randint(p["count_min"], p["count_max"])
    start_angle = random.uniform(0, 2 * math.pi)
    weighted_subs = _build_weighted_subs(p["sub_profiles"])
    geoms = []
    for i in range(count):
        angle = start_angle + (2 * math.pi * i / count)
        geom = _profile_to_geometry(dict(random.choice(weighted_subs)),
                                    cx + radius * math.cos(angle),
                                    cy + radius * math.sin(angle))
        if not geom.is_empty:
            geoms.append(geom)
    return _shapely_union(geoms) if geoms else _ShapelyPolygon()

def _nest_geometry(p, cx, cy):
    count = random.randint(p["count_min"], p["count_max"])
    scale_factor = random.uniform(p["scale_factor_min"], p["scale_factor_max"])
    sub_p = dict(random.choice(_build_weighted_subs(p["sub_profiles"])))
    geoms = []
    scale = 1.0
    for _ in range(count):
        geom = _profile_to_geometry(_scale_profile(sub_p, scale), cx, cy)
        if not geom.is_empty:
            geoms.append(geom)
        scale *= scale_factor
    return _shapely_union(geoms) if geoms else _ShapelyPolygon()

def draw_constellation(dwg, p):
    cx = random.randint(p["x_min"], p["x_max"])
    cy = random.randint(p["y_min"], p["y_max"])
    radius = random.randint(p["radius_min"], p["radius_max"])
    count = random.randint(p["count_min"], p["count_max"])
    start_angle = random.uniform(0, 2 * math.pi)
    one_layer = p.get("one_layer", False)
    fill_transparent = bool(p.get("fill_transparent"))
    weighted_subs = _build_weighted_subs(p["sub_profiles"])

    if one_layer:
        stroke_width = random.randint(p["stroke_width_min"], p["stroke_width_max"])
        fill_color = "none" if fill_transparent else random_color(p, "fill")
        geoms = []
        for i in range(count):
            angle = start_angle + (2 * math.pi * i / count)
            geom = _profile_to_geometry(dict(random.choice(weighted_subs)),
                                        cx + radius * math.cos(angle),
                                        cy + radius * math.sin(angle))
            if not geom.is_empty:
                geoms.append(geom)
        union = _shapely_union(geoms) if geoms else None
        if union is None or union.is_empty:
            return None
        contours = _geometry_to_contours(union)
        if not contours:
            return None
        dwg.add(dwg.path(
            d=_contours_to_svg_path_d(contours),
            fill=fill_color,
            fill_rule="evenodd",
            stroke=random_color(p, "stroke"),
            stroke_width=stroke_width,
        ))
        result = {"type": "constellation", "cx": cx, "cy": cy,
                  "contours": contours, "stroke_width": stroke_width}
        if fill_transparent:
            result["fill_transparent"] = True
        return result
    else:
        results = []
        for i in range(count):
            angle = start_angle + (2 * math.pi * i / count)
            sub_p = dict(random.choice(weighted_subs))
            sub_p["x_min"] = sub_p["x_max"] = int(cx + radius * math.cos(angle))
            sub_p["y_min"] = sub_p["y_max"] = int(cy + radius * math.sin(angle))
            result = draw_shape(dwg, sub_p)
            if result is None:
                continue
            if isinstance(result, list):
                results.extend(result)
            else:
                results.append(result)
        return results if results else None

def draw_nest(dwg, p):
    cx = random.randint(p["x_min"], p["x_max"])
    cy = random.randint(p["y_min"], p["y_max"])
    count = random.randint(p["count_min"], p["count_max"])
    scale_factor = random.uniform(p["scale_factor_min"], p["scale_factor_max"])
    sub_p_base = dict(random.choice(_build_weighted_subs(p["sub_profiles"])))
    results = []
    scale = 1.0
    for _ in range(count):
        scaled_p = _scale_profile(sub_p_base, scale)
        scaled_p["x_min"] = scaled_p["x_max"] = cx
        scaled_p["y_min"] = scaled_p["y_max"] = cy
        result = draw_shape(dwg, scaled_p)
        if result is not None:
            if isinstance(result, list):
                results.extend(result)
            else:
                results.append(result)
        scale *= scale_factor
    return results if results else None

def draw_debug_label(dwg, shape_data, idx):
    if shape_data["type"] in ("circle", "text", "constellation"):
        tx, ty = shape_data["cx"], shape_data["cy"]
    elif "contours" in shape_data:
        all_pts = [pt for contour in shape_data["contours"] for pt in contour]
        tx = sum(pt[0] for pt in all_pts) / len(all_pts)
        ty = sum(pt[1] for pt in all_pts) / len(all_pts)
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
    elif p["shape"] == "star":
        return draw_star(dwg, p)
    elif p["shape"] == "cross":
        return draw_cross(dwg, p)
    elif p["shape"] == "text":
        return draw_text_shape(dwg, p)
    elif p["shape"] == "constellation":
        return draw_constellation(dwg, p)
    elif p["shape"] == "nest":
        return draw_nest(dwg, p)


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

    # Find the highest existing output subfolder number to avoid overwriting
    os.makedirs("output", exist_ok=True)
    existing_dirs = glob.glob(f"output/{OUTPUT_NAME}*/")
    existing_nums = []
    for d in existing_dirs:
        name = os.path.basename(os.path.normpath(d))
        suffix = name[len(OUTPUT_NAME):]
        if suffix.isdigit():
            existing_nums.append(int(suffix))
    start = max(existing_nums) + 1 if existing_nums else 1

    # SVG
    for i in range(start, start + NUM_FILES):
        name = f"{OUTPUT_NAME}{i}"
        out_dir = f"output/{name}"
        os.makedirs(out_dir, exist_ok=True)

        dwg = svgwrite.Drawing(f"{out_dir}/{name}.svg", size=CANVAS_SIZE)
        shapes = []

        for idx in range(num_shapes):
            p = random.choice(weighted_profiles)
            result = draw_shape(dwg, p)
            if result is None:
                continue
            if isinstance(result, list):
                for item in result:
                    shapes.append({"initial_layer": len(shapes), **item})
            else:
                shapes.append({"initial_layer": len(shapes), **result})

        if DEBUG_MODE:
            for idx, shape_data in enumerate(shapes):
                draw_debug_label(dwg, shape_data, idx)

        dwg.save()
        cairosvg.svg2png(url=f"{out_dir}/{name}.svg", write_to=f"output/{name}.png", background_color="white")
        export_json(shapes, f"{out_dir}/{name}.json")

main()