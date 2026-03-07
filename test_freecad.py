#!/usr/bin/env freecadcmd
"""
Keychain generator — headless FreeCAD script.
Usage: freecadcmd test_freecad.py [Name]
Ref:   https://wiki.freecad.org/Power_users_hub
"""

# ./run.sh Monique emboss

import sys
import FreeCAD as App
import Part
import Mesh

doc = App.newDocument("KeychainDoc")

name      = sys.argv[2] if len(sys.argv) > 2 else "David"
initial   = name[0].upper()
isEngrave = sys.argv[3].lower() == "engrave" if len(sys.argv) > 3 else True
font_path = "/Users/davidlucas/Downloads/Calistoga_Merriweather/Calistoga/Calistoga-Regular.ttf"



LETTER_SIZE   = 60    # reference font size — rescaled below to hit TARGET_DIM
TARGET_DIM    = 55.0  # the larger of (width, height) will equal this
LETTER_DEPTH  = 5.0   # big letter extrusion height
EMBOSS_DEPTH  = 6.0   # name extrusion height when embossed (1 unit taller than letter)
ENGRAVE_DEPTH = 1.0   # how deep the name is cut into the letter top surface when engraved
RING_DEPTH    = 3.0   # keyring ring extrusion height

NAME_MODE = "engrave" if isEngrave else "emboss"  # "engrave" | "emboss"


def make_text_shape(text, font_file, size):
    """
    Headless-safe 2D compound face shape for the given text.
    Uses Part.makeWireString — no FreeCADGui required.
    Ref: https://wiki.freecad.org/Part_API
    """
    wires_per_char = Part.makeWireString(text, font_file, size, 0)
    faces = []
    for char_wires in wires_per_char:
        if not char_wires:
            continue
        # Sort wires by enclosed area, largest first (outer contour, then holes)
        ordered = []
        for w in char_wires:
            try:
                ordered.append((Part.Face(w).Area, w))
            except Exception:
                ordered.append((0.0, w))
        ordered.sort(key=lambda x: x[0], reverse=True)
        sorted_wires = [w for _, w in ordered]
        try:
            faces.append(Part.Face(sorted_wires))
        except Exception:
            try:
                faces.append(Part.Face(sorted_wires[0]))
            except Exception:
                pass
    if not faces:
        raise RuntimeError(f"No faces generated for: {text!r}")
    return Part.makeCompound(faces)


def place_shape(shape, rotation_deg=0.0, x=0.0, y=0.0, z=0.0):
    """Return a transformed copy of shape: rotate around Z then translate."""
    pl = App.Placement()
    pl.Rotation = App.Rotation(App.Vector(0, 0, 1), rotation_deg)
    pl.Base = App.Vector(x, y, z)
    return shape.transformGeometry(pl.toMatrix())


# ─── BIG LETTER ───────────────────────────────────────────────────────────────
letter_2d = make_text_shape(initial, font_path, LETTER_SIZE)
ref_bb    = letter_2d.BoundBox
max_dim   = max(ref_bb.XMax - ref_bb.XMin, ref_bb.YMax - ref_bb.YMin)
letter_size = LETTER_SIZE * (TARGET_DIM / max_dim)

if abs(letter_size - LETTER_SIZE) > 0.01:
    letter_2d = make_text_shape(initial, font_path, letter_size)

big_bb   = letter_2d.BoundBox
letter_w = big_bb.XMax - big_bb.XMin
letter_h = big_bb.YMax - big_bb.YMin
print(f"Letter size: {letter_size:.2f}, dims: {letter_w:.1f} x {letter_h:.1f}")

big_extrude_shape = letter_2d.extrude(App.Vector(0, 0, LETTER_DEPTH))

# ─── FIND MAIN STROKE (thickest vertical column) ──────────────────────────────
N_STRIPS = 40
strip_w  = letter_w / N_STRIPS
volumes  = []

for i in range(N_STRIPS):
    x0 = big_bb.XMin + i * strip_w + strip_w * 0.05
    strip_box = Part.makeBox(
        strip_w * 0.90, letter_h, LETTER_DEPTH,
        App.Vector(x0, big_bb.YMin, 0)
    )
    try:
        volumes.append(big_extrude_shape.common(strip_box).Volume)
    except Exception:
        volumes.append(0.0)

peak_i   = max(range(N_STRIPS), key=lambda i: volumes[i])
peak_vol = volumes[peak_i]

if peak_vol == 0:
    stroke_width = letter_w * 0.30
    stroke_cx    = (big_bb.XMin + big_bb.XMax) / 2
    print("WARNING: volume sampling returned 0 — falling back to bbox center")
else:
    threshold = peak_vol * 0.50
    left_i, right_i = peak_i, peak_i
    while left_i  > 0           and volumes[left_i  - 1] >= threshold:
        left_i  -= 1
    while right_i < N_STRIPS-1  and volumes[right_i + 1] >= threshold:
        right_i += 1
    stroke_x_min = big_bb.XMin + left_i  * strip_w
    stroke_x_max = big_bb.XMin + (right_i + 1) * strip_w
    stroke_width  = stroke_x_max - stroke_x_min
    stroke_cx     = (stroke_x_min + stroke_x_max) / 2
    print(f"Main stroke: x={stroke_x_min:.1f}-{stroke_x_max:.1f}, width={stroke_width:.1f}")

# ─── FIND USABLE HEIGHT AT MAIN STROKE ────────────────────────────────────────
# The letter bbox ≠ actual solid. For curved letters (C, G, O) the stroke is
# only solid for a portion of the bbox height. Probe at stroke_cx to find it.
N_Y_STRIPS  = 40
strip_h_val = letter_h / N_Y_STRIPS
# Use a narrow fixed probe at stroke_cx — this detects whether the arc's leftmost
# edge is actually solid at each Y level. A wide probe (e.g. stroke_width * 0.80)
# catches thick serifs at the C tips and falsely extends usable_h.
probe_w     = 2.0

y_vols = []
for i in range(N_Y_STRIPS):
    y0   = big_bb.YMin + i * strip_h_val + strip_h_val * 0.05
    ybox = Part.makeBox(
        probe_w, strip_h_val * 0.90, LETTER_DEPTH,
        App.Vector(stroke_cx - probe_w / 2, y0, 0)
    )
    try:
        y_vols.append(big_extrude_shape.common(ybox).Volume)
    except Exception:
        y_vols.append(0.0)

y_peak = max(y_vols) if y_vols else 0
if y_peak > 0:
    y_thresh        = y_peak * 0.40
    filled          = [i for i, v in enumerate(y_vols) if v >= y_thresh]
    usable_y_min    = big_bb.YMin + min(filled) * strip_h_val
    usable_y_max    = big_bb.YMin + (max(filled) + 1) * strip_h_val
    usable_h        = usable_y_max - usable_y_min
    usable_y_center = (usable_y_min + usable_y_max) / 2
else:
    usable_y_min    = big_bb.YMin
    usable_y_max    = big_bb.YMax
    usable_h        = letter_h
    usable_y_center = (big_bb.YMin + big_bb.YMax) / 2
print(f"Usable stroke height: {usable_h:.1f} (y={usable_y_min:.1f}-{usable_y_max:.1f})")

# Find the X center of the stroke material at the Y midpoint.
# For curved letters (C, G, O) the arc cross-section at mid-height is narrower
# and shifted relative to stroke_cx (the widest column center). Slicing there
# gives a better centering target for the name.
slice_h   = strip_h_val * 2
# Probe only within the detected stroke column — prevents horizontal arms (E, F)
# and spurs (G) from corrupting the bounding box and pulling arc_cx off-centre.
slice_box = Part.makeBox(
    stroke_width, slice_h, LETTER_DEPTH,
    App.Vector(stroke_x_min, usable_y_center - slice_h / 2, 0)
)
try:
    mid_slice = big_extrude_shape.common(slice_box)
    mid_bb    = mid_slice.BoundBox
    arc_cx    = (mid_bb.XMin + mid_bb.XMax) / 2
    if arc_cx < stroke_x_min or arc_cx > stroke_x_max:
        arc_cx = stroke_cx
except Exception:
    arc_cx = stroke_cx
print(f"Arc center at Y midpoint: {arc_cx:.1f} (stroke_cx={stroke_cx:.1f})")

# ─── NAME TEXT ────────────────────────────────────────────────────────────────
MAX_NAME_HEIGHT = 7.0  # cap-height of name letters must never exceed this (units)

name_size = max(3.0,min(stroke_width * 0.70, MAX_NAME_HEIGHT))

name_2d = make_text_shape(name, font_path, name_size)

# Clamp cap-height using only the first letter (not the full name bounding rect)
first_char_2d = make_text_shape(name[0].upper(), font_path, name_size)
first_char_h  = first_char_2d.BoundBox.YMax - first_char_2d.BoundBox.YMin
if first_char_h > MAX_NAME_HEIGHT:
    name_size = name_size * (MAX_NAME_HEIGHT / first_char_h)
    name_2d   = make_text_shape(name, font_path, name_size)

# Clamp rotated text length to 85% of the actual filled stroke height (not full bbox)
text_length = name_2d.BoundBox.XMax - name_2d.BoundBox.XMin
max_name_h  = usable_h * 0.80

if text_length > max_name_h:
    name_size = max(3.0,name_size * (max_name_h / text_length))
    name_2d   = make_text_shape(name, font_path, name_size)

print(f"Name size: {name_size:.2f} units")

# ── Per-letter placement variables ──
if initial == "A":
    name_rotation = 285.0  # degrees CCW around Z
    name_x_offset =   1.0  # X nudge applied after auto-center (positive = right)
elif initial == "M":
    name_rotation = 291.0  # degrees CCW around Z
    name_x_offset =   13.0  # X nudge applied after auto-center (positive = right)
elif initial == "N":
    name_rotation = 303.0  # degrees CCW around Z
    name_x_offset =   -17.0  # X nudge applied after auto-center (positive = right)
else:
    name_rotation = 90.0   # degrees CCW around Z
    name_x_offset =  0.0
# Iterative fit: nudge the name rightward first (moves it deeper into the arc body
# where the stroke is thicker), then scale down only once shifting is exhausted.
SHIFT_STEP   = 1.0
MAX_SHIFT    = min(stroke_width * 0.35, 6.0)
name_x_shift = 0.0
name_x = name_y = 0.0

for _attempt in range(12):
    name_2d_rotated = place_shape(name_2d, rotation_deg=name_rotation)
    name_bb  = name_2d_rotated.BoundBox
    name_x   = arc_cx - (name_bb.XMin + name_bb.XMax) / 2 + name_x_offset + name_x_shift
    name_y   = usable_y_center - (name_bb.YMin + name_bb.YMax) / 2

    test_shape = place_shape(name_2d, rotation_deg=name_rotation, x=name_x, y=name_y)
    test_solid = test_shape.extrude(App.Vector(0, 0, LETTER_DEPTH))
    try:
        total_vol  = test_solid.Volume
        inside_vol = test_solid.common(big_extrude_shape).Volume
        fit_ratio  = inside_vol / total_vol if total_vol > 0 else 1.0
    except Exception:
        fit_ratio  = 1.0

    name_cx = (name_bb.XMin + name_bb.XMax) / 2 + name_x
    print(f"Fit check {_attempt + 1}: {fit_ratio:.1%} inside (size={name_size:.2f}, cx={name_cx:.1f}, shift={name_x_shift:+.1f})")
    if fit_ratio >= 0.99:
        break

    # Prefer shifting right over scaling — only scale once shift budget is spent
    if name_x_shift + SHIFT_STEP <= MAX_SHIFT:
        name_x_shift += SHIFT_STEP
    else:
        name_x_shift = 0.0          # reset shift for new font size
        if name_size <= 3.0:
            break
        name_size = max(3.0, name_size * 0.88)
        name_2d   = make_text_shape(name, font_path, name_size)

if NAME_MODE == "engrave":
    name_2d_placed = place_shape(name_2d, rotation_deg=name_rotation, x=name_x, y=name_y, z=LETTER_DEPTH)
    name_tool_shape = name_2d_placed.extrude(App.Vector(0, 0, -ENGRAVE_DEPTH))
else:  # emboss
    name_2d_placed = place_shape(name_2d, rotation_deg=name_rotation, x=name_x, y=name_y)
    name_tool_shape = name_2d_placed.extrude(App.Vector(0, 0, EMBOSS_DEPTH))

# ─── KEYRING LOOP ─────────────────────────────────────────────────────────────
outer_r = 4.0
inner_r = 2.0

verts      = letter_2d.Vertexes
y_tol      = letter_h * 0.15
top_verts  = [v for v in verts if v.Y >= big_bb.YMax - y_tol]
top_left_x = min(v.X for v in top_verts) if top_verts else big_bb.XMin

# ── Per-letter placement variables ──
keyring_x        = top_left_x + outer_r * 0.2
keyring_y        = big_bb.YMax - outer_r * 0.2
keyring_rotation = 0.0   # reserved for future per-letter tuning

outer_disk    = Part.makeCylinder(outer_r, RING_DEPTH, App.Vector(keyring_x, keyring_y, 0), App.Vector(0, 0, 1))
hole          = Part.makeCylinder(inner_r, RING_DEPTH, App.Vector(keyring_x, keyring_y, 0), App.Vector(0, 0, 1))
keyring_shape = outer_disk.cut(hole)

# ─── COMBINE & EXPORT ─────────────────────────────────────────────────────────
if NAME_MODE == "engrave":
    combined_shape = big_extrude_shape.cut(name_tool_shape).fuse(keyring_shape)
else:  # emboss
    combined_shape = big_extrude_shape.fuse(name_tool_shape).fuse(keyring_shape)
combined_feat  = doc.addObject("Part::Feature", "KeychainCombined")
combined_feat.Shape = combined_shape
doc.recompute()

output_stl = f"/Users/davidlucas/Desktop/{name}_keychain.stl"
Mesh.export([combined_feat], output_stl)
print(f"Exported: {output_stl}")
print("Done!")
sys.exit(0)
