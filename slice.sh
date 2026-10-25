#!/usr/bin/env bash
# Slice every case's tag.stl with PrusaSlicer 2.9.2 (image habs-slicer:0.2, the same image solidcraft-tipping-lab uses),
# stock bundled presets resolved by resolve_preset.py (a copy of solidcraft-tipping-lab/slicer/resolve_preset.py):
#   print "0.20mm SPEED @MK4S 0.4", filament "Prusament PLA @MK4S", printer "Original Prusa MK4S 0.4 nozzle".
# The one override: --binary-gcode=0 (the MK4S presets set binary_gcode = 1), so the G-code is plain text with ;WIDTH: tags.
#   bash slice.sh [CASE ...]      (default: all 8)
set -euo pipefail
cd "$(dirname "$0")"
EXP="$(pwd -W 2>/dev/null || pwd)"
CASES=${*:-"raised-h2 raised-h3 raised-h4 raised-h5 engraved-h2 engraved-h3 engraved-h4 engraved-h5"}
MSYS_NO_PATHCONV=1 docker run --rm -v "$EXP:/w" -w /w habs-slicer:0.2 sh -c "
  set -e
  python3 resolve_preset.py /usr/share/PrusaSlicer/profiles/PrusaResearch.ini '0.20mm SPEED @MK4S 0.4' \
    'Prusament PLA @MK4S' 'Original Prusa MK4S 0.4 nozzle' > out/preset-resolved.ini
  prusa-slicer --help | head -1 > out/slicer-version.txt
  grep -m1 '^config_version' /usr/share/PrusaSlicer/profiles/PrusaResearch.ini >> out/slicer-version.txt
  for c in $CASES; do
    prusa-slicer --load out/preset-resolved.ini --binary-gcode=0 --center 125,105 \
      --export-gcode -o out/\$c/tag.gcode out/\$c/tag.stl > out/\$c/slice-log.txt 2>&1
    echo \"\$c \$(grep -c ';WIDTH:' out/\$c/tag.gcode) WIDTH tags\"
  done
"
