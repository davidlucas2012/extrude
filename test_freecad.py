#!/usr/bin/env freecadcmd
"""
Keychain generator — headless FreeCAD script.
Usage: freecadcmd test_freecad.py [Name]
Ref:   https://wiki.freecad.org/Power_users_hub
"""
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

# ─── NAME TEXT ────────────────────────────────────────────────────────────────
MAX_NAME_HEIGHT = 7.0  # cap-height of name letters must never exceed this (units)

name_size = max(4.0, min(stroke_width * 0.70, MAX_NAME_HEIGHT))

name_2d = make_text_shape(name, font_path, name_size)

# Clamp cap-height using only the first letter (not the full name bounding rect)
first_char_2d = make_text_shape(name[0].upper(), font_path, name_size)
first_char_h  = first_char_2d.BoundBox.YMax - first_char_2d.BoundBox.YMin
if first_char_h > MAX_NAME_HEIGHT:
    name_size = name_size * (MAX_NAME_HEIGHT / first_char_h)
    name_2d   = make_text_shape(name, font_path, name_size)

# Clamp rotated text length to 85% of letter height
text_length = name_2d.BoundBox.XMax - name_2d.BoundBox.XMin
max_name_h  = letter_h * 0.85

if text_length > max_name_h:
    name_size = max(4.0, name_size * (max_name_h / text_length))
    name_2d   = make_text_shape(name, font_path, name_size)

print(f"Name size: {name_size:.2f} units")

# ── Per-letter placement variables ──
name_rotation = 90.0   # degrees CCW around Z
name_2d_rotated = place_shape(name_2d, rotation_deg=name_rotation)
name_bb = name_2d_rotated.BoundBox

name_x = stroke_cx - (name_bb.XMin + name_bb.XMax) / 2
name_y = (big_bb.YMin + big_bb.YMax) / 2 - (name_bb.YMin + name_bb.YMax) / 2

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
