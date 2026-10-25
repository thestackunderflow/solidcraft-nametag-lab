#!/usr/bin/env bash
# Slice one run's exported design (score/tag.stl) with the probe's stock presets (resolve_preset.py; only
# --binary-gcode=0), as slice.sh does for the probe cases.   bash claude-run/slice_run.sh out/runs/run-N
set -euo pipefail
cd "$(dirname "$0")/.."
EXP="$(pwd -W 2>/dev/null || pwd)"
S=$1
MSYS_NO_PATHCONV=1 docker run --rm -v "$EXP:/w" -w /w habs-slicer:0.2 sh -c "
  set -e
  python3 resolve_preset.py /usr/share/PrusaSlicer/profiles/PrusaResearch.ini '0.20mm SPEED @MK4S 0.4' \
    'Prusament PLA @MK4S' 'Original Prusa MK4S 0.4 nozzle' > $S/score/preset-resolved.ini
  prusa-slicer --load $S/score/preset-resolved.ini --binary-gcode=0 --center 125,105 \
    --export-gcode -o $S/score/tag.gcode $S/score/tag.stl > $S/score/slice-log.txt 2>&1
  echo \"$S \$(grep -c ';WIDTH:' $S/score/tag.gcode) WIDTH tags\"
"
