import svgwrite
import cairosvg
import random
import argparse
import math
import json
import os
import glob

_nest_counter = [0]
from shapely.geometry import box as _shapely_box, Point as _ShapelyPoint, Polygon as _ShapelyPolygon, MultiPoint as _ShapelyMultiPoint, MultiPolygon as _ShapelyMultiPolygon, LineString as _ShapelyLineString
from shapely.affinity import rotate as _shapely_rotate, translate as _shapely_translate
from shapely.ops import unary_union as _shapely_union
from shapely.validation import make_valid as _shapely_make_valid
import matplotlib
matplotlib.use('Agg')
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
import numpy as np

DEBUG_MODE = False

#Number of outputs
NUM_FILES = 20

#number of shapes to be generated
NUM_SHAPES = 50

#What to name the output files
OUTPUT_NAME = "2026_03_14_shapes"

# Canvas size
CANVAS_WIDTH_IN = 4
CANVAS_HEIGHT_IN = 4
RESOLUTION = 100  # pixels per inch

CANVAS_SIZE = (CANVAS_WIDTH_IN * RESOLUTION, CANVAS_HEIGHT_IN * RESOLUTION)

# Profiles — loaded from PROFILE_*.json files in the same directory
PROFILES = []
for _profile_file in sorted(glob.glob("PROFILE_*.json")):
    with open(_profile_file) as _f:
        try:
            _data = json.load(_f)
        except json.JSONDecodeError as _e:
            raise json.JSONDecodeError(f"{_profile_file}: {_e.msg}", _e.doc, _e.pos) from None
        if isinstance(_data, list):
            PROFILES.extend(_data)
        else:
            PROFILES.append(_data)

if not PROFILES:
    raise RuntimeError("No profiles loaded. Add at least one PROFILE_*.json file.")

# --- Profile validation warnings ---
for _p in PROFILES:
    _shape = _p.get("shape", "")
    _sw_min = _p.get("stroke_width_min", 0)
    _sw_max = _p.get("stroke_width_max", 0)
    _mode = _p.get("bump_mode", "")
    _ratio_max = _p.get("bump_ratio_max", 0)

    if _shape == "bumped_polygon":
        if _mode in ("alternate", "all_in", "random") and _sw_max > 0:
            print(f"WARNING: profile bump_mode='{_mode}' with stroke_width_max={_sw_max} "
                  f"— inward bumps with positive stroke widths may produce antenna artifacts "
                  f"at near-self-intersecting boundaries. Set stroke_width_min/max to 0 to avoid.")
        if _mode in ("alternate", "all_in", "random") and _ratio_max > 0.4:
            print(f"WARNING: profile bump_mode='{_mode}' with bump_ratio_max={_ratio_max} "
                  f"— values above 0.4 risk inward bumps meeting at center, causing "
                  f"self-intersecting geometry and stroke artifacts.")


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

def make_cross_points(cx, cy, r, arm_width, num_arms, rotation_deg=0):
    arm = _shapely_box(-arm_width / 2, 0, arm_width / 2, r)
    arms = []
    for i in range(num_arms):
        angle_deg = rotation_deg + i * 360 / num_arms
        rotated = _shapely_rotate(arm, angle_deg, origin=(0, 0))
        rotated = _shapely_translate(rotated, cx, cy)
        arms.append(rotated)
    cross = _shapely_union(arms)
    return list(cross.exterior.coords[:-1])

def random_color(p, prefix="fill"):
    if f"{prefix}_r_min" not in p:
        return "rgb(0,0,0)"
    return "rgb({},{},{})".format(
        random.randint(p[f"{prefix}_r_min"], p[f"{prefix}_r_max"]),
        random.randint(p[f"{prefix}_g_min"], p[f"{prefix}_g_max"]),
        random.randint(p[f"{prefix}_b_min"], p[f"{prefix}_b_max"]),
    )


def _result(type_, stroke_width, fill_transparent, **kwargs):
    d = {"type": type_, "stroke_width": stroke_width, **kwargs}
    if fill_transparent:
        d["fill_transparent"] = True
    return d


def _random_start_angle(p):
    rot_min = math.radians(p["rotation_min"]) if "rotation_min" in p else 0
    rot_max = math.radians(p["rotation_max"]) if "rotation_max" in p else 2 * math.pi
    return random.uniform(rot_min, rot_max)


def random_geometry(p):
    cx = random.randint(p["x_min"], p["x_max"])
    cy = random.randint(p["y_min"], p["y_max"])
    r = random.randint(p["r_min"], p["r_max"])
    return cx, cy, r

def draw_circle(dwg, p):
    cx, cy, r = random_geometry(p)
    stroke_width = random.randint(p["stroke_width_min"], p["stroke_width_max"])
    fill_color = "none" if p.get("fill_transparent") else random_color(p, "fill")
    dwg.add(dwg.circle(center=(cx, cy), r=r, fill=fill_color,
                       stroke=random_color(p, "stroke"), stroke_width=stroke_width))
    return _result("circle", stroke_width, p.get("fill_transparent"), cx=cx, cy=cy, r=r)

def draw_polygon(dwg, p):
    cx, cy, r = random_geometry(p)
    stroke_width = random.randint(p["stroke_width_min"], p["stroke_width_max"])
    sides = random.randint(p["sides_min"], p["sides_max"])
    rotation = math.radians(random.uniform(p.get("rotation_min", 0), p.get("rotation_max", 360)))
    points = make_polygon_points(cx, cy, r, sides, rotation)
    fill_color = "none" if p.get("fill_transparent") else random_color(p, "fill")
    dwg.add(dwg.polygon(points=points, fill=fill_color,
                        stroke=random_color(p, "stroke"), stroke_width=stroke_width))
    return _result("polygon", stroke_width, p.get("fill_transparent"), points=points)


def draw_star(dwg, p):
    cx, cy, r = random_geometry(p)
    inner_r = r * random.uniform(p["inner_r_ratio_min"], p["inner_r_ratio_max"])
    sides = random.randint(p["sides_min"], p["sides_max"])
    rotation = math.radians(random.uniform(p.get("rotation_min", 0), p.get("rotation_max", 360)))
    stroke_width = random.randint(p["stroke_width_min"], p["stroke_width_max"])
    points = make_star_points(cx, cy, r, inner_r, sides, rotation)
    fill_color = "none" if p.get("fill_transparent") else random_color(p, "fill")
    dwg.add(dwg.polygon(points=points, fill=fill_color,
                        stroke=random_color(p, "stroke"), stroke_width=stroke_width))
    return _result("star", stroke_width, p.get("fill_transparent"), points=points)

def draw_cross(dwg, p):
    cx, cy, r = random_geometry(p)
    arm_width = random.randint(p["arm_width_min"], p["arm_width_max"])
    num_arms = random.randint(p["sides_min"], p["sides_max"])
    stroke_width = random.randint(p["stroke_width_min"], p["stroke_width_max"])
    rotation_deg = random.uniform(p.get("rotation_min", 0), p.get("rotation_max", 360))
    points = make_cross_points(cx, cy, r, arm_width, num_arms, rotation_deg)
    fill_color = "none" if p.get("fill_transparent") else random_color(p, "fill")
    dwg.add(dwg.polygon(points=points, fill=fill_color,
                        stroke=random_color(p, "stroke"), stroke_width=stroke_width))
    return _result("cross", stroke_width, p.get("fill_transparent"), points=points)

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
    return _result("text", stroke_width, fill_transparent,
                   text=char, cx=cx, cy=cy, font_size=font_size,
                   rotation=rotation, contours=[list(pts) for pts in contours])

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
    return [sp for sp in sub_profiles for _ in range(sp.get("weight", 1))]

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
    elif shape == "bumped_polygon":
        r = random.randint(p["r_min"], p["r_max"])
        sides = random.randint(p["sides_min"], p["sides_max"])
        rotation = random.uniform(p.get("rotation_min", 0), p.get("rotation_max", 360))
        bump_mode = p.get("bump_mode", "all_out")
        bump_ratio = random.uniform(p["bump_ratio_min"], p["bump_ratio_max"])
        return _make_bumped_polygon(cx, cy, r, sides, rotation, bump_mode, bump_ratio)
    elif shape == "daisy":
        count = random.randint(p["count_min"], p["count_max"])
        arm_r = random.randint(p["radius_min"], p["radius_max"])
        petal_r = random.randint(p["petal_r_min"], p["petal_r_max"])
        length_ratio = random.uniform(p["petal_length_ratio_min"], p["petal_length_ratio_max"])
        point_inward = p.get("point_inward", True)
        rot_min = math.radians(p["rotation_min"]) if "rotation_min" in p else 0
        rot_max = math.radians(p["rotation_max"]) if "rotation_max" in p else 2 * math.pi
        start_angle = random.uniform(rot_min, rot_max)
        petal_local = _make_petal(petal_r, length_ratio)
        geoms = [_place_petal(petal_local, cx, cy, arm_r,
                              start_angle + 2*math.pi*i/count, point_inward)
                 for i in range(count)]
        geoms = [g for g in geoms if not g.is_empty]
        return _shapely_union(geoms) if geoms else _ShapelyPolygon()
    elif shape == "line":
        length = random.randint(p["length_min"], p["length_max"])
        width = random.randint(p["width_min"], p["width_max"])
        rotation_deg = random.uniform(p.get("rotation_min", 0), p.get("rotation_max", 360))
        squiggle_amp = random.uniform(p.get("squiggle_amp_min", 0), p.get("squiggle_amp_max", 0))
        squiggle_freq = random.uniform(p.get("squiggle_freq_min", 1), p.get("squiggle_freq_max", 1))
        margin = p.get("margin", 0)
        return _make_line_geometry(cx, cy, length, width, rotation_deg, squiggle_amp, squiggle_freq, margin)
    return _ShapelyPolygon()

def _constellation_geometry(p, cx, cy):
    radius = random.randint(p["radius_min"], p["radius_max"])
    count = random.randint(p["count_min"], p["count_max"])
    start_angle = _random_start_angle(p)
    weighted_subs = _build_weighted_subs(p["sub_profiles"])
    uniform_size = p.get("uniform_size", False)
    fixed_size = None
    if uniform_size:
        sample = dict(random.choice(weighted_subs))
        r_key = "radius_min" if "radius_min" in sample else "r_min"
        r_key_max = "radius_max" if "radius_max" in sample else "r_max"
        fixed_size = (r_key, r_key_max, random.randint(sample[r_key], sample[r_key_max]))
    geoms = []
    for i in range(count):
        angle = start_angle + (2 * math.pi * i / count)
        sub_p = dict(random.choice(weighted_subs))
        if fixed_size:
            sub_p[fixed_size[0]] = sub_p[fixed_size[1]] = fixed_size[2]
        geom = _profile_to_geometry(sub_p, cx + radius * math.cos(angle),
                                    cy + radius * math.sin(angle))
        if not geom.is_empty:
            geoms.append(geom)
    return _shapely_union(geoms) if geoms else _ShapelyPolygon()

def _nest_geometry(p, cx, cy):
    uniform = p.get("uniform_adjustment", True)
    sub_p = dict(random.choice(_build_weighted_subs(p["sub_profiles"])))
    max_count = random.randint(p["count_min"], p["count_max"])
    geoms = []
    if uniform:
        r_key = "radius_min" if "radius_min" in sub_p else "r_min"
        r_key_max = "radius_max" if "radius_max" in sub_p else "r_max"
        ring_width = random.randint(p["ring_width_min"], p["ring_width_max"])
        base_r = random.randint(sub_p[r_key], sub_p[r_key_max])
        for i in range(max_count):
            r = base_r - i * ring_width
            if r <= 0:
                break
            sp = dict(sub_p)
            sp[r_key] = sp[r_key_max] = r
            geom = _profile_to_geometry(sp, cx, cy)
            if not geom.is_empty:
                geoms.append(geom)
    else:
        scale = 1.0
        for _ in range(max_count):
            geom = _profile_to_geometry(_scale_profile(sub_p, scale), cx, cy)
            if not geom.is_empty:
                geoms.append(geom)
            scale *= random.uniform(p["scale_factor_min"], p["scale_factor_max"])
    return _shapely_union(geoms) if geoms else _ShapelyPolygon()

def draw_constellation(dwg, p):
    cx = random.randint(p["x_min"], p["x_max"])
    cy = random.randint(p["y_min"], p["y_max"])
    radius = random.randint(p["radius_min"], p["radius_max"])
    count = random.randint(p["count_min"], p["count_max"])
    start_angle = _random_start_angle(p)
    one_layer = p.get("one_layer", False)
    fill_transparent = bool(p.get("fill_transparent"))
    weighted_subs = _build_weighted_subs(p["sub_profiles"])

    uniform_size = p.get("uniform_size", False)
    fixed_size = None
    if uniform_size:
        sample = dict(random.choice(weighted_subs))
        r_key = "radius_min" if "radius_min" in sample else "r_min"
        r_key_max = "radius_max" if "radius_max" in sample else "r_max"
        fixed_size = (r_key, r_key_max, random.randint(sample[r_key], sample[r_key_max]))

    if one_layer:
        stroke_width = random.randint(p["stroke_width_min"], p["stroke_width_max"])
        geoms = []
        for i in range(count):
            angle = start_angle + (2 * math.pi * i / count)
            sub_p = dict(random.choice(weighted_subs))
            if fixed_size:
                sub_p[fixed_size[0]] = sub_p[fixed_size[1]] = fixed_size[2]
            geom = _profile_to_geometry(sub_p, cx + radius * math.cos(angle),
                                        cy + radius * math.sin(angle))
            if not geom.is_empty:
                geoms.append(geom)
        union = _shapely_union(geoms) if geoms else None
        if union is None or union.is_empty:
            return None
        contours = _add_contour_paths(dwg, union, stroke_width, fill_transparent, p)
        if not contours:
            return None
        return _result("constellation", stroke_width, fill_transparent,
                       cx=cx, cy=cy, contours=contours)
    else:
        results = []
        for i in range(count):
            angle = start_angle + (2 * math.pi * i / count)
            sub_p = dict(random.choice(weighted_subs))
            if fixed_size:
                sub_p[fixed_size[0]] = sub_p[fixed_size[1]] = fixed_size[2]
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
    _nest_counter[0] += 1
    nest_id = f"nest_{_nest_counter[0]}"
    cx = random.randint(p["x_min"], p["x_max"])
    cy = random.randint(p["y_min"], p["y_max"])
    uniform = p.get("uniform_adjustment", True)
    max_count = random.randint(p["count_min"], p["count_max"])
    sub_p_base = dict(random.choice(_build_weighted_subs(p["sub_profiles"])))
    ring_rotation = p.get("ring_rotation", "random")  # "random", "none", "coordinated"
    results = []

    def _tag(r, ring_index):
        r["nest_group"] = nest_id
        r["nest_ring_index"] = ring_index

    def _apply_ring_rotation(sp, i, n):
        """Set rotation on a sub-profile copy based on ring_rotation mode."""
        if ring_rotation == "none":
            sp["rotation_min"] = sp["rotation_max"] = 0
        elif ring_rotation == "coordinated":
            base = random.uniform(
                p.get("rotation_base_min", 0), p.get("rotation_base_max", 360)
            ) if i == 0 else _apply_ring_rotation._base
            if i == 0:
                _apply_ring_rotation._base = base
            angle = (_apply_ring_rotation._base + i * (360 / n)) % 360
            sp["rotation_min"] = sp["rotation_max"] = angle
        # "random": leave sp rotation keys as-is (sub_profile controls it)

    if uniform:
        r_key = "radius_min" if "radius_min" in sub_p_base else "r_min"
        r_key_max = "radius_max" if "radius_max" in sub_p_base else "r_max"
        ring_width = random.randint(p["ring_width_min"], p["ring_width_max"])
        base_r = random.randint(sub_p_base[r_key], sub_p_base[r_key_max])
        n_rings = max(1, base_r // ring_width) if ring_width > 0 else max_count
        for i in range(max_count):
            r = base_r - i * ring_width
            if r <= 0:
                break
            sp = dict(sub_p_base)
            sp[r_key] = sp[r_key_max] = r
            sp["x_min"] = sp["x_max"] = cx
            sp["y_min"] = sp["y_max"] = cy
            _apply_ring_rotation(sp, i, n_rings)
            result = draw_shape(dwg, sp)
            if result is not None:
                if isinstance(result, list):
                    for item in result:
                        _tag(item, i)
                    results.extend(result)
                else:
                    _tag(result, i)
                    results.append(result)
    else:
        scale = 1.0
        for i in range(max_count):
            scaled_p = _scale_profile(sub_p_base, scale)
            scaled_p["x_min"] = scaled_p["x_max"] = cx
            scaled_p["y_min"] = scaled_p["y_max"] = cy
            _apply_ring_rotation(scaled_p, i, max_count)
            result = draw_shape(dwg, scaled_p)
            if result is not None:
                if isinstance(result, list):
                    for item in result:
                        _tag(item, i)
                    results.extend(result)
                else:
                    _tag(result, i)
                    results.append(result)
            scale *= random.uniform(p["scale_factor_min"], p["scale_factor_max"])
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

def _add_contour_paths(dwg, geom, stroke_width, fill_transparent, p):
    """Draw a Shapely geometry as explicit filled SVG paths.
    Stroke rendered by drawing outer buffer in stroke color first, then fill on top.
    This avoids buffer(-sw/2) which causes ghost edges on concave shapes.
    Returns contours list, or None if geometry is empty.
    """
    contours = _geometry_to_contours(geom)
    if not contours:
        return None
    if stroke_width > 0:
        ring = geom.boundary.buffer(stroke_width / 2)
        if not ring.is_empty:
            ring_contours = _geometry_to_contours(ring)
            if ring_contours:
                dwg.add(dwg.path(
                    d=_contours_to_svg_path_d(ring_contours),
                    fill=random_color(p, "stroke"),
                    fill_rule="evenodd",
                    stroke="none",
                ))
    if not fill_transparent:
        dwg.add(dwg.path(
            d=_contours_to_svg_path_d(contours),
            fill=random_color(p, "fill"),
            fill_rule="nonzero",
            stroke="none",
        ))
    return contours


def _make_bumped_polygon(cx, cy, r, sides, rotation_deg, bump_mode, bump_ratio):
    """Polygon with circular arc bumps on each edge.
    bump_ratio: arc sagitta as fraction of edge length (0.5 = semicircle).
    bump_mode: 'all_out', 'all_in', 'alternate', 'random'.
    """
    rot = math.radians(rotation_deg)
    verts = [(cx + r * math.cos(rot + 2*math.pi*i/sides),
              cy + r * math.sin(rot + 2*math.pi*i/sides))
             for i in range(sides)]
    result = _ShapelyPolygon(verts)
    first_outward = random.choice([True, False])
    FAR = r * 20 + 1000

    for i in range(sides):
        A = verts[i]
        B = verts[(i+1) % sides]
        if bump_mode == "all_out":
            outward = True
        elif bump_mode == "all_in":
            outward = False
        elif bump_mode == "alternate":
            outward = (i % 2 == 0) == first_outward
        else:
            outward = random.choice([True, False])

        mx, my = (A[0]+B[0])/2, (A[1]+B[1])/2
        edge_len = math.hypot(B[0]-A[0], B[1]-A[1])
        half_chord = edge_len / 2
        dx, dy = B[0]-A[0], B[1]-A[1]
        norm_len = math.hypot(dx, dy)
        edx, edy = dx/norm_len, dy/norm_len
        nx, ny = -edy, edx
        if (mx - cx)*nx + (my - cy)*ny < 0:
            nx, ny = -nx, -ny

        h = bump_ratio * edge_len * (1 if outward else -1)
        if abs(h) < 1e-6:
            continue

        k = (h**2 - half_chord**2) / (2*h)
        arc_r = math.sqrt(half_chord**2 + k**2)
        arc_cx, arc_cy = mx + k*nx, my + k*ny
        disk = _ShapelyPoint(arc_cx, arc_cy).buffer(arc_r)

        apex_nx, apex_ny = (nx, ny) if h > 0 else (-nx, -ny)
        hp = _ShapelyPolygon([
            A, B,
            (B[0] + FAR*edx + FAR*apex_nx, B[1] + FAR*edy + FAR*apex_ny),
            (A[0] - FAR*edx + FAR*apex_nx, A[1] - FAR*edy + FAR*apex_ny),
        ])
        cap = disk.intersection(hp)
        result = result.union(cap) if h > 0 else result.difference(cap)

    return result.buffer(0)


def _make_petal(petal_r, length_ratio):
    """Teardrop petal in local coords: tip at origin, round end in +y direction."""
    petal_length = 2 * petal_r * length_ratio
    circle_pts = [(petal_r * math.cos(2*math.pi*i/48),
                   petal_length + petal_r * math.sin(2*math.pi*i/48))
                  for i in range(48)]
    return _ShapelyMultiPoint([(0.0, 0.0)] + circle_pts).convex_hull


def _place_petal(petal_geom, cx, cy, arm_r, arm_angle_rad, point_inward):
    """Rotate and translate petal so its tip sits at arm_r from (cx,cy).
    point_inward=True: tip faces center, round end faces out.
    point_inward=False: round end faces center, tip faces out.
    """
    arm_deg = math.degrees(arm_angle_rad)
    rotation = (arm_deg - 90) if point_inward else (arm_deg + 90)
    rotated = _shapely_rotate(petal_geom, rotation, origin=(0, 0))
    tip_x = cx + arm_r * math.cos(arm_angle_rad)
    tip_y = cy + arm_r * math.sin(arm_angle_rad)
    return _shapely_translate(rotated, tip_x, tip_y)


def draw_bumped_polygon(dwg, p):
    cx = random.randint(p["x_min"], p["x_max"])
    cy = random.randint(p["y_min"], p["y_max"])
    r = random.randint(p["r_min"], p["r_max"])
    sides = random.randint(p["sides_min"], p["sides_max"])
    rotation = random.uniform(p.get("rotation_min", 0), p.get("rotation_max", 360))
    bump_mode = p.get("bump_mode", "all_out")
    bump_ratio = random.uniform(p["bump_ratio_min"], p["bump_ratio_max"])
    stroke_width = random.randint(p["stroke_width_min"], p["stroke_width_max"])
    fill_transparent = bool(p.get("fill_transparent"))

    if bump_mode in ("alternate", "all_in", "random") and stroke_width > 0:
        print(f"  NOTE: bumped_polygon bump_mode='{bump_mode}' stroke_width={stroke_width} "
              f"bump_ratio={bump_ratio:.2f} — stroke artifacts possible on inward bumps.")

    geom = _make_bumped_polygon(cx, cy, r, sides, rotation, bump_mode, bump_ratio)
    if geom.is_empty:
        return None
    contours = _add_contour_paths(dwg, geom, stroke_width, fill_transparent, p)
    if not contours:
        return None
    return _result("bumped_polygon", stroke_width, fill_transparent,
                   cx=cx, cy=cy, contours=contours)


def draw_daisy(dwg, p):
    cx = random.randint(p["x_min"], p["x_max"])
    cy = random.randint(p["y_min"], p["y_max"])
    count = random.randint(p["count_min"], p["count_max"])
    arm_r = random.randint(p["radius_min"], p["radius_max"])
    petal_r = random.randint(p["petal_r_min"], p["petal_r_max"])
    length_ratio = random.uniform(p["petal_length_ratio_min"], p["petal_length_ratio_max"])
    point_inward = p.get("point_inward", True)
    one_layer = p.get("one_layer", False)
    fill_transparent = bool(p.get("fill_transparent"))
    stroke_width = random.randint(p["stroke_width_min"], p["stroke_width_max"])
    start_angle = _random_start_angle(p)
    petal_local = _make_petal(petal_r, length_ratio)

    if one_layer:
        geoms = []
        for i in range(count):
            angle = start_angle + 2*math.pi*i/count
            geom = _place_petal(petal_local, cx, cy, arm_r, angle, point_inward)
            if not geom.is_empty:
                geoms.append(geom)
        union = _shapely_union(geoms) if geoms else None
        if union is None or union.is_empty:
            return None
        contours = _add_contour_paths(dwg, union, stroke_width, fill_transparent, p)
        if not contours:
            return None
        return _result("daisy", stroke_width, fill_transparent, cx=cx, cy=cy, contours=contours)
    else:
        results = []
        for i in range(count):
            angle = start_angle + 2*math.pi*i/count
            geom = _place_petal(petal_local, cx, cy, arm_r, angle, point_inward)
            if geom.is_empty:
                continue
            contours = _add_contour_paths(dwg, geom, stroke_width, fill_transparent, p)
            if not contours:
                continue
            petal_cx = cx + arm_r * math.cos(angle)
            petal_cy = cy + arm_r * math.sin(angle)
            results.append(_result("petal", stroke_width, fill_transparent,
                                   cx=petal_cx, cy=petal_cy, contours=contours))
        return results if results else None


def _make_line_geometry(cx, cy, length, width, rotation_deg, squiggle_amp, squiggle_freq, margin):
    """Build a capsule or squiggly-line Shapely geometry centered at (cx, cy).
    squiggle_amp=0 gives a straight capsule. squiggle_amp>0 adds a sine-wave
    offset perpendicular to the line direction with the given number of cycles.
    margin clips the result to the canvas inset by margin pixels.
    """
    rot_rad = math.radians(rotation_deg)
    dx, dy = math.cos(rot_rad), math.sin(rot_rad)
    nx, ny = -dy, dx  # perpendicular (left of travel direction)

    # Resolution: enough points to capture squiggle detail
    n_pts = max(4, int(length / 3))
    if squiggle_amp > 0 and squiggle_freq > 0:
        n_pts = max(n_pts, int(squiggle_freq * 20))

    pts = []
    for i in range(n_pts):
        t = i / (n_pts - 1)
        along = (t - 0.5) * length
        perp = squiggle_amp * math.sin(squiggle_freq * t * 2 * math.pi) if squiggle_amp > 0 else 0
        pts.append((cx + along * dx + perp * nx, cy + along * dy + perp * ny))

    geom = _ShapelyLineString(pts).buffer(width / 2)  # cap_style round by default

    if margin > 0:
        clip = _shapely_box(margin, margin, CANVAS_SIZE[0] - margin, CANVAS_SIZE[1] - margin)
        geom = geom.intersection(clip)

    return geom


def draw_line(dwg, p):
    cx = random.randint(p["x_min"], p["x_max"])
    cy = random.randint(p["y_min"], p["y_max"])
    length = random.randint(p["length_min"], p["length_max"])
    width = random.randint(p["width_min"], p["width_max"])
    rotation_deg = random.uniform(p.get("rotation_min", 0), p.get("rotation_max", 360))
    squiggle_amp = random.uniform(p.get("squiggle_amp_min", 0), p.get("squiggle_amp_max", 0))
    squiggle_freq = random.uniform(p.get("squiggle_freq_min", 1), p.get("squiggle_freq_max", 1))
    margin = p.get("margin", 0)
    stroke_width = random.randint(p["stroke_width_min"], p["stroke_width_max"])
    fill_transparent = bool(p.get("fill_transparent"))

    geom = _make_line_geometry(cx, cy, length, width, rotation_deg, squiggle_amp, squiggle_freq, margin)
    if geom.is_empty:
        return None

    contours = _add_contour_paths(dwg, geom, stroke_width, fill_transparent, p)
    if not contours:
        return None
    return _result("line", stroke_width, fill_transparent, cx=cx, cy=cy, contours=contours)


_DRAW = {
    "circle": draw_circle, "polygon": draw_polygon, "star": draw_star,
    "cross": draw_cross, "text": draw_text_shape, "constellation": draw_constellation,
    "nest": draw_nest, "bumped_polygon": draw_bumped_polygon,
    "daisy": draw_daisy, "line": draw_line,
}

def draw_shape(dwg, p):
    return _DRAW[p["shape"]](dwg, p)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=NUM_SHAPES)
    args = parser.parse_args()
    num_shapes = args.count

    weighted_profiles = _build_weighted_subs(PROFILES)

    os.makedirs("output", exist_ok=True)
    existing_nums = [
        int(sfx)
        for d in glob.glob(f"output/{OUTPUT_NAME}*/")
        if (sfx := os.path.basename(os.path.normpath(d))[len(OUTPUT_NAME):]).isdigit()
    ]
    start = max(existing_nums, default=0) + 1

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