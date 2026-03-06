#!/bin/zsh
# Usage: ./run.sh [Name] [engrave|emboss]
# Example: ./run.sh David engrave

FREECAD="/Applications/FreeCAD.app/Contents/MacOS/FreeCAD"
SCRIPT="$(dirname "$0")/test_freecad.py"

NAME="${1:-David}"
MODE="${2:-engrave}"

"$FREECAD" "$SCRIPT" "$NAME" "$MODE" --console
