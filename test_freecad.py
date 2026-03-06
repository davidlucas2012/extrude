import sys
import FreeCAD as App
import Draft
import Part
import Mesh

doc = App.newDocument("KeychainDoc")

name = sys.argv[2] if len(sys.argv) > 2 else "David"
initial = name[0].upper()
font_path = "/Users/davidlucas/Downloads/Calistoga_Merriweather/Calistoga/Calistoga-Regular.ttf"

LETTER_SIZE   = 60    # reference font size — auto-corrected below to hit TARGET_DIM
TARGET_DIM    = 55.0  # the larger of (width, height) will equal this
LETTER_DEPTH = 5.0   # big letter extrusion height (units)
NAME_DEPTH   = 6.0   # name extrusion height — 1 unit taller than letter
RING_DEPTH   = 3.0   # keyring ring extrusion height

# ─── BIG LETTER ──────────────────────────────────────────────────────────────
# Create at reference size, measure, then rescale so max(w, h) == TARGET_DIM.
big_letter_draft = Draft.makeShapeString(
    String=initial, FontFile=font_path, Size=LETTER_SIZE, Tracking=0
)
doc.recompute()
big_obj = doc.getObject(big_letter_draft.Name)
ref_bb  = big_obj.Shape.BoundBox
max_dim = max(ref_bb.XMax - ref_bb.XMin, ref_bb.YMax - ref_bb.YMin)
letter_size = LETTER_SIZE * (TARGET_DIM / max_dim)

if abs(letter_size - LETTER_SIZE) > 0.01:
    doc.removeObject(big_letter_draft.Name)
    big_letter_draft = Draft.makeShapeString(
        String=initial, FontFile=font_path, Size=letter_size, Tracking=0
    )
    doc.recompute()
    big_obj = doc.getObject(big_letter_draft.Name)

big_bb   = big_obj.Shape.BoundBox
letter_w = big_bb.XMax - big_bb.XMin
letter_h = big_bb.YMax - big_bb.YMin
print(f"Letter size: {letter_size:.2f}, dims: {letter_w:.1f} × {letter_h:.1f}")

big_extrude = doc.addObject("Part::Extrusion", "BigLetterExtrude")
big_extrude.Base = big_obj
big_extrude.Dir = App.Vector(0, 0, LETTER_DEPTH)
big_extrude.Solid = True
doc.recompute()

# ─── FIND MAIN STROKE (thickest vertical column) ─────────────────────────────
# Divide the letter's bounding box into N vertical strips.
# Intersect each strip with the letter solid and measure volume.
# The peak region is the main stroke (e.g. the vertical bar of "L").
N_STRIPS = 40
strip_w = letter_w / N_STRIPS
volumes = []

for i in range(N_STRIPS):
    x0 = big_bb.XMin + i * strip_w + strip_w * 0.05   # slight inset avoids edge noise
    strip_box = Part.makeBox(
        strip_w * 0.90,
        letter_h,
        LETTER_DEPTH,
        App.Vector(x0, big_bb.YMin, 0)
    )
    try:
        sect = big_extrude.Shape.common(strip_box)
        volumes.append(sect.Volume)
    except Exception:
        volumes.append(0.0)

# Peak strip index
peak_i   = max(range(N_STRIPS), key=lambda i: volumes[i])
peak_vol = volumes[peak_i]

if peak_vol == 0:
    # Fallback: use bounding-box center
    stroke_width = letter_w * 0.30
    stroke_x_min = (big_bb.XMin + big_bb.XMax) / 2 - stroke_width / 2
    stroke_x_max = stroke_x_min + stroke_width
    stroke_cx    = (big_bb.XMin + big_bb.XMax) / 2
    print("WARNING: volume sampling returned 0 — falling back to bbox center")
else:
    # Expand left/right from peak while volume stays above 50 % of peak
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
    print(f"Main stroke: x={stroke_x_min:.1f}–{stroke_x_max:.1f}, width={stroke_width:.1f}")

# ─── NAME TEXT ───────────────────────────────────────────────────────────────
# Rule 1: cap-height capped at 7 units (first letter height ≤ 7).
# Rule 2: full name length (X extent before rotation = height after 90° rotation)
#         must fit within 85% of the letter's height — scale down if not.
name_size = max(4.0, min(stroke_width * 0.70, 7.0))

# Create at initial size to measure actual rendered text length
name_draft = Draft.makeShapeString(
    String=name, FontFile=font_path, Size=name_size, Tracking=0
)
doc.recompute()
name_obj = doc.getObject(name_draft.Name)

text_length = name_obj.Shape.BoundBox.XMax - name_obj.Shape.BoundBox.XMin
max_name_height = letter_h * 0.85   # max vertical extent once rotated

if text_length > max_name_height:
    name_size = max(4.0, name_size * (max_name_height / text_length))
    doc.removeObject(name_draft.Name)
    name_draft = Draft.makeShapeString(
        String=name, FontFile=font_path, Size=name_size, Tracking=0
    )
    doc.recompute()
    name_obj = doc.getObject(name_draft.Name)

print(f"Name size: {name_size:.2f} units")
# Rotate 90° CCW so the name runs bottom-to-top inside the letter
name_obj.Placement.Rotation = App.Rotation(App.Vector(0, 0, 1), 90)
doc.recompute()

name_bb = name_obj.Shape.BoundBox

# Horizontally: center inside the main stroke
# Vertically:   center inside the full letter bounding box
target_x = stroke_cx - (name_bb.XMin + name_bb.XMax) / 2
target_y = (big_bb.YMin + big_bb.YMax) / 2 - (name_bb.YMin + name_bb.YMax) / 2

name_obj.Placement.Base = App.Vector(target_x, target_y, 0)
doc.recompute()

name_extrude = doc.addObject("Part::Extrusion", "NameExtrude")
name_extrude.Base = name_obj
name_extrude.Dir = App.Vector(0, 0, NAME_DEPTH)
name_extrude.Solid = True
doc.recompute()

# ─── KEYRING LOOP ────────────────────────────────────────────────────────────
# No bridge/stem. Ring sits directly on the letter with its bottom ¼ inserted
# into the letter top as the structural anchor (4th-quadrant embed).
# Diameter = 8 units (outer_r=4); wall = 2 units (inner_r=2), matches tube spec.
outer_r = 4.0
inner_r = 2.0

# Horizontal: find the leftmost vertex in the top 15% of the letter height,
# then offset right by outer_r so the ring center sits over solid material.
verts = big_obj.Shape.Vertexes
y_tol = letter_h * 0.15
top_verts = [v for v in verts if v.Y >= big_bb.YMax - y_tol]
top_left_x = min(v.X for v in top_verts) if top_verts else big_bb.XMin
# Shift center diagonally into the letter so ~half the ring is embedded
loop_cx = top_left_x + outer_r * 0.2   # 1 unit right (into the letter)
ring_cy = big_bb.YMax - outer_r * 0.2  # 1 unit down  (into the letter)

outer_disk = Part.makeCylinder(
    outer_r, RING_DEPTH,
    App.Vector(loop_cx, ring_cy, 0), App.Vector(0, 0, 1)
)
hole = Part.makeCylinder(
    inner_r, RING_DEPTH,
    App.Vector(loop_cx, ring_cy, 0), App.Vector(0, 0, 1)
)
keyring_shape = outer_disk.cut(hole)

keyring_feat = doc.addObject("Part::Feature", "KeyringLoop")
keyring_feat.Shape = keyring_shape
doc.recompute()

# ─── EXPORT ──────────────────────────────────────────────────────────────────
# Two separate STLs for dual-color printing in Bambu Studio:
#   *_letter.stl  → body filament (e.g. orange)
#   *_text.stl    → name filament (e.g. blue)
letter_stl = f"/Users/davidlucas/Desktop/{name}_letter.stl"
text_stl   = f"/Users/davidlucas/Desktop/{name}_text.stl"

Mesh.export([doc.getObject("BigLetterExtrude"), doc.getObject("KeyringLoop")], letter_stl)
Mesh.export([doc.getObject("NameExtrude")], text_stl)

print(f"Exported letter body : {letter_stl}")
print(f"Exported name text   : {text_stl}")
print("Done!")
