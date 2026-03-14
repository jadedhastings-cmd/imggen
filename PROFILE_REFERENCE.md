# Profile Reference Manual

Profiles are JSON files named `PROFILE_*.json` in the imggen directory. Each file contains a JSON array of profile objects. All loaded profiles are pooled together and one is chosen at random per shape drawn.

---

## Common Fields (all shape types)

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `shape` | string | yes | Shape type: `circle`, `polygon`, `star`, `cross`, `text`, `constellation`, `nest`, `bumped_polygon`, `daisy`, `line` |
| `weight` | int | no (default 1) | Relative probability of this profile being chosen. Higher = more frequent. |
| `x_min` / `x_max` | int | yes | Horizontal range for the shape center (pixels) |
| `y_min` / `y_max` | int | yes | Vertical range for the shape center (pixels) |
| `fill_transparent` | bool | no (default false) | If true, fill is omitted (only stroke is drawn) |
| `fill_r_min` / `fill_r_max` | int 0–255 | yes* | Red channel range for fill color. *Not required if `fill_transparent: true` |
| `fill_g_min` / `fill_g_max` | int 0–255 | yes* | Green channel range for fill color |
| `fill_b_min` / `fill_b_max` | int 0–255 | yes* | Blue channel range for fill color |
| `stroke_r_min` / `stroke_r_max` | int 0–255 | yes* | Red channel range for stroke color. *Not required if stroke_width is always 0 |
| `stroke_g_min` / `stroke_g_max` | int 0–255 | yes* | Green channel range for stroke color |
| `stroke_b_min` / `stroke_b_max` | int 0–255 | yes* | Blue channel range for stroke color |
| `stroke_width_min` / `stroke_width_max` | int | yes | Stroke width range in pixels. Set both to 0 for no stroke. |
| `rotation_min` / `rotation_max` | float (degrees) | no | Rotation range in degrees. Defaults vary by shape — see per-shape notes. |

Canvas default is 800×800 px (8 in × 8 in at 100 px/in).

---

## circle

A filled circle.

| Key | Required | Description |
|-----|----------|-------------|
| `r_min` / `r_max` | yes | Radius range in pixels |

**Notes:** No rotation (circles are rotationally symmetric).

**Example:**
```json
{
  "shape": "circle",
  "x_min": 100, "x_max": 700,
  "y_min": 100, "y_max": 700,
  "r_min": 20, "r_max": 80,
  "fill_r_min": 0, "fill_r_max": 255,
  "fill_g_min": 0, "fill_g_max": 255,
  "fill_b_min": 0, "fill_b_max": 255,
  "stroke_r_min": 0, "stroke_r_max": 0,
  "stroke_g_min": 0, "stroke_g_max": 0,
  "stroke_b_min": 0, "stroke_b_max": 0,
  "stroke_width_min": 0, "stroke_width_max": 0
}
```

---

## polygon

A regular convex polygon.

| Key | Required | Description |
|-----|----------|-------------|
| `r_min` / `r_max` | yes | Circumradius range in pixels |
| `sides_min` / `sides_max` | yes | Number of sides (e.g. 3=triangle, 6=hexagon, 8=octagon) |
| `rotation_min` / `rotation_max` | no | Rotation range in degrees. Default: 0–360 (fully random) |

**Notes:** `r` is the distance from center to vertex (circumradius), not the apothem (center to edge midpoint).

---

## star

A star polygon with alternating outer and inner vertices.

| Key | Required | Description |
|-----|----------|-------------|
| `r_min` / `r_max` | yes | Outer vertex radius range in pixels |
| `inner_r_ratio_min` / `inner_r_ratio_max` | yes | Inner vertex radius as a fraction of outer radius (e.g. 0.4–0.6) |
| `sides_min` / `sides_max` | yes | Number of points |
| `rotation_min` / `rotation_max` | no | Rotation range in degrees. Default: 0–360 |

---

## cross

A cross/asterisk shape built from arms radiating from center.

| Key | Required | Description |
|-----|----------|-------------|
| `r_min` / `r_max` | yes | Arm length range in pixels |
| `arm_width_min` / `arm_width_max` | yes | Arm width range in pixels |
| `sides_min` / `sides_max` | yes | Number of arms (2=line, 4=plus, 6=asterisk, etc.) |
| `rotation_min` / `rotation_max` | no | Rotation range in degrees. Default: 0–360 |

---

## text

Renders a text string as a filled shape using vector font outlines.

| Key | Required | Description |
|-----|----------|-------------|
| `text` | yes | The string to render |
| `font_size_min` / `font_size_max` | yes | Font size range in points |
| `font_family` | no (default `"DejaVu Sans"`) | Font family name or path to a .ttf file |
| `letter_layers` | no (default false) | If true, each character is a separate laserprep shape (individual ordering). If false, the whole word is one shape. |
| `rotation_min` / `rotation_max` | no (default 0–0) | Rotation range in degrees. Unlike other shapes, text defaults to 0 (no rotation) unless specified. |

**Notes:** Text outlines are rendered as filled vector paths. Holes in letters (e.g. inside 'O', 'B') are handled automatically.

---

## bumped_polygon

A regular polygon with circular arc bumps on each edge — the bumps can curve outward or inward.

| Key | Required | Description |
|-----|----------|-------------|
| `r_min` / `r_max` | yes | Circumradius range in pixels |
| `sides_min` / `sides_max` | yes | Number of sides |
| `rotation_min` / `rotation_max` | no (default 0) | Rotation range in degrees |
| `bump_mode` | no (default `"all_out"`) | How bumps are assigned: `"all_out"`, `"all_in"`, `"alternate"` (alternating in/out), `"random"` (each edge random) |
| `bump_ratio_min` / `bump_ratio_max` | yes | Arc sagitta as a fraction of edge length. 0 = flat edge, ~0.5 = semicircle bump. |

**Warnings:**
- `bump_mode` of `all_in`, `alternate`, or `random` with `stroke_width > 0` may produce antenna artifacts at near-self-intersecting boundaries. Set stroke to 0 to avoid.
- `bump_ratio_max > 0.4` with inward bump modes risks bumps meeting at the center, causing self-intersecting geometry.

---

## constellation

Arranges sub-shapes in a ring (evenly spaced around a circle). Sub-shapes are drawn from `sub_profiles`.

| Key | Required | Description |
|-----|----------|-------------|
| `radius_min` / `radius_max` | yes | Radius of the arrangement ring in pixels |
| `count_min` / `count_max` | yes | Number of sub-shapes to place |
| `rotation_min` / `rotation_max` | no | Starting angle range in degrees. Default: 0–360 (fully random start) |
| `one_layer` | no (default false) | If true, all sub-shapes are unioned into a single laserprep shape. If false, each sub-shape is an independent laserprep shape. |
| `uniform_size` | no (default false) | If true, all sub-shapes use the same randomly chosen size. If false, each is sized independently. |
| `sub_profiles` | yes | Array of sub-profile objects (any shape type). Each must have `weight`. Position keys (`x_min` etc.) are overridden — center is placed on the ring automatically. |

**Notes:** The `stroke_width` / color keys on the constellation profile itself only apply when `one_layer: true`. For `one_layer: false`, each sub-shape uses its own profile's colors.

---

## daisy

Teardrop-shaped petals arranged in a ring, like a flower. Each petal is a convex hull of a circle and a tip point.

| Key | Required | Description |
|-----|----------|-------------|
| `radius_min` / `radius_max` | yes | Distance from center to each petal's tip (pixels) |
| `petal_r_min` / `petal_r_max` | yes | Radius of the round end of each petal (controls petal width) |
| `petal_length_ratio_min` / `petal_length_ratio_max` | yes | Petal length multiplier. `petal_length = 2 × petal_r × length_ratio`. Higher = longer petals. |
| `count_min` / `count_max` | yes | Number of petals |
| `point_inward` | no (default true) | If true, petal tips point toward center, round ends face out. If false, reversed. |
| `rotation_min` / `rotation_max` | no | Starting angle range in degrees. Default: 0–360 |
| `one_layer` | no (default false) | If true, all petals union into one laserprep shape. If false, each petal is independent. |

**Overall size:** Outer radius ≈ `arm_r + petal_r × (2 × length_ratio + 1)` (with `point_inward: true`).

**Notes:** `x_min`/`x_max`/`y_min`/`y_max` set the center of the entire daisy. `radius_min`/`radius_max` (`arm_r`) is the distance from that center to each petal tip.

---

## nest

Concentric copies of a sub-shape, shrinking from outermost to innermost.

| Key | Required | Description |
|-----|----------|-------------|
| `count_min` / `count_max` | yes | Maximum number of rings |
| `uniform_adjustment` | no (default true) | See below |
| `sub_profiles` | yes | Array of sub-profile objects. One is chosen at random and used for all rings. Position keys are overridden. |
| `ring_rotation` | no (default `"random"`) | How rotation is applied across rings: `"none"` (all rings at 0°), `"random"` (each ring uses sub-profile's own rotation range), `"coordinated"` (rings step evenly, 360/N per ring, so the last ring realigns with the first) |
| `rotation_base_min` / `rotation_base_max` | no (default 0–360) | Starting angle range for `ring_rotation: "coordinated"` |

### uniform_adjustment: true (default)

Rings step by a fixed pixel amount.

| Key | Required | Description |
|-----|----------|-------------|
| `ring_width_min` / `ring_width_max` | yes | Step size between rings in pixels |

The outermost ring uses a random size from the sub-profile's `r_min`/`r_max` (or `radius_min`/`radius_max`). Each subsequent ring is reduced by `ring_width`. Rings stop when radius ≤ 0 or `count_max` is reached.

### uniform_adjustment: false

Rings scale multiplicatively.

| Key | Required | Description |
|-----|----------|-------------|
| `scale_factor_min` / `scale_factor_max` | yes | Scale multiplier applied cumulatively per ring (e.g. 0.7–0.9 shrinks each ring to 70–90% of the previous) |

**Laserprep ordering:** Rings are placed outermost-first (shallowest lord = outermost ring). The global algorithm decides when to begin a nest relative to other shapes, then all rings of that nest are placed in sequence before moving on.

---

## line

A straight or squiggly line with rounded (semicircle) ends. Built by buffering a polyline by `width/2`, so the fill IS the line body — stroke is an optional additional ring around it. A straight line (`squiggle_amp=0`) produces a perfect capsule shape.

| Key | Required | Description |
|-----|----------|-------------|
| `length_min` / `length_max` | yes | Line length range in pixels (tip-to-tip before rounding) |
| `width_min` / `width_max` | yes | Line width range in pixels (full diameter of the rounded ends) |
| `rotation_min` / `rotation_max` | no (default 0–360) | Rotation range in degrees |
| `squiggle_amp_min` / `squiggle_amp_max` | no (default 0) | Amplitude of the sine-wave squiggle in pixels, measured perpendicular to the line axis. 0 = straight. |
| `squiggle_freq_min` / `squiggle_freq_max` | no (default 1) | Number of complete sine-wave cycles along the line length. Higher = more waves. |
| `margin` | no (default 0) | Clips the line geometry to stay within this many pixels from each canvas edge. Useful since a rotated line can extend well beyond its center point. |

**Size note:** The total bounding extent of a straight line from its center is approximately `length/2 + width/2` along the line axis, and `width/2` perpendicular. With rotation, the worst-case radius from center is `sqrt((length/2)² + (width/2)²)`. Use `margin` to prevent clipping at canvas edges rather than restricting `x/y` ranges.

**Squiggle tips:**
- `squiggle_amp` of 0–10 with freq 1–2: gently wavy
- `squiggle_amp` of 15–30 with freq 2–4: clearly squiggly
- `squiggle_amp` of 40–60 with freq 4–8: chaotic/tight waves
- If `squiggle_amp` exceeds `width/2`, the line body will self-overlap and produce a filled blob at crossover points

**Example:**
```json
{
  "shape": "line",
  "x_min": 50, "x_max": 350,
  "y_min": 50, "y_max": 350,
  "length_min": 80, "length_max": 200,
  "width_min": 5, "width_max": 15,
  "rotation_min": 0, "rotation_max": 360,
  "squiggle_amp_min": 10, "squiggle_amp_max": 20,
  "squiggle_freq_min": 2, "squiggle_freq_max": 4,
  "margin": 20,
  "fill_r_min": 30, "fill_r_max": 180,
  "fill_g_min": 30, "fill_g_max": 180,
  "fill_b_min": 30, "fill_b_max": 180,
  "stroke_width_min": 0, "stroke_width_max": 0
}
```

---

## Sub-profile notes

Sub-profiles (used by `constellation`, `nest`) are profile objects nested under the `sub_profiles` key. They support all the same fields as top-level profiles, with these differences:

- `x_min` / `x_max` / `y_min` / `y_max` are **overridden** by the parent shape (set to the computed placement position). You can set them to 0.
- `weight` controls relative probability of being chosen when multiple sub-profiles are listed.
- Sub-profiles can themselves be compound types (e.g. a nest of constellations, a constellation of daisies).

---

## Color fields

All color ranges use separate R/G/B channels, each 0–255:

```
fill_r_min / fill_r_max
fill_g_min / fill_g_max
fill_b_min / fill_b_max

stroke_r_min / stroke_r_max
stroke_g_min / stroke_g_max
stroke_b_min / stroke_b_max
```

To get a fixed color, set min == max. To get grayscale, keep R/G/B ranges identical.

---

## Multiple profiles in one file

A single `PROFILE_*.json` file can contain an array of multiple profile objects. All profiles across all files are pooled. Use `weight` to control relative frequency.

```json
[
  { "weight": 3, "shape": "circle", ... },
  { "weight": 1, "shape": "star", ... }
]
```

This would produce circles ~75% of the time and stars ~25%.
