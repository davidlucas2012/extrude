# Keychain Extrusion Project

## Overview
FreeCAD Python scripts that generate personalized letter keychains — a big initial letter as the 3D base, with the full name extruded inside it and a keyring loop attached.

## Core Rules

### Big Letter is the Base
- The big letter bounding box is the absolute boundary of the model footprint.
- The name text must **never exceed** the big letter's bounding box (XMin, XMax, YMin, YMax).
- If the name or keyring would hit an edge, scale or reposition it to fit within bounds before exporting.

### Letter-by-Letter Approach
- Each letter (initial) may need its own tuned placement for name and keyring.
- We tackle one letter at a time, perfecting name offset and rotation per letter before moving on.

### Per-Letter Variable Declarations
Every letter configuration must declare explicit variables for easy adjustment:

```python
# Per-letter placement variables
name_x        = 0.0   # X offset of name text inside letter
name_y        = 0.0   # Y offset of name text inside letter
name_rotation = 90.0  # rotation of name text (degrees, CCW around Z)

keyring_x        = 0.0  # X center of keyring loop
keyring_y        = 0.0  # Y center of keyring loop
keyring_rotation = 0.0  # rotation of keyring (degrees, CCW around Z)
```

These variables must be declared close together and clearly labeled so they can be adjusted per letter without hunting through logic code.

### Scripting Standards
- All FreeCAD scripting must follow the official FreeCAD documentation:
  https://wiki.freecad.org/Power_users_hub
- Use `Part`, `Draft`, `Mesh`, and `App` (FreeCAD) APIs as documented.
- Avoid undocumented or GUI-only FreeCAD APIs.
- Always call `doc.recompute()` after modifying document objects.

## Output
- Single combined STL exported to Desktop: `{name}_keychain.stl`
- All three components (letter body, name text, keyring loop) fused into one solid before export.
