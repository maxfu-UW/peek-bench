#!/bin/bash
# CF-P11 re-run under the revised prompt -- 3 models x 3 repeats = 9 runs. QUEUED behind p18_v2.
#
# WHY. CF-P11 is the corpus's hardest figure case (4 'MPa' mentions in the text layer for 17
# tensile values) but its previous scores were dominated by two artefacts, not by model skill:
#   1. UNDISCLOSED SCOPE. GT is exactly the three OFAT sweeps (nozzle dia 0.2-1.0, temp 390-430,
#      infill angle 0-90) all at 2 wt% SCF. The paper also reports bare PEEK and 5% SCF, and the
#      prompt says "keep neat PEEK and carbon-fibre PEEK" -- so a compliant model extracted rows
#      GT never contained. Fixed with a paper_scope.json note (2% SCF sweeps only).
#   2. VALUE REPLICATION (not invented conditions). qwen emitted 52-57 rows. Those CONDITIONS are
#      real: Figure 4 sweeps all three materials, so the full design is 3 x (5 dia + 5 temp +
#      7 angle) = 51 rows plus 6 Figure-2 summary bars = 57, exactly qwen-r3's count. Its error was
#      in the VALUES -- 17-18 bare-PEEK rows repeat one number (65 MPa) rather than reading each
#      curve. Rule 2 now forbids copying a value across sweep levels to fill a grid.
# NOT given an out_of_scope.json entry: CF-P11's excluded values collide with its in-scope ones
# inside the UTS tolerance (58 is both an excluded summary bar AND a real GT row), so a value-keyed
# exclusion would forgive genuine GT rows. See _why_CF-P11_is_absent in out_of_scope.json.
#
# Prediction: predicted rows fall from ~15-57 toward 17, precision rises sharply, and the
# gemma/mistral raster collapse (raster_angle=0 on every row) is UNCHANGED -- that is a genuine
# vision failure the scope note cannot fix, and it is the result CF-P11 exists to measure.
set -u
export PATH="$HOME/.lmstudio/bin:$PATH"
B="${PEEKBENCH_ROOT:?set PEEKBENCH_ROOT to the project root}"
C="$B/campaign"; P="$B/group_truth_excel_file/P2-data-source-papers"
R="$C/results_p11_v2"; mkdir -p "$R"; LOG="$C/p11_v2.log"
exec >>"$LOG" 2>&1

# Filename resolved from the index, never hand-typed (a truncated literal killed an earlier run).
PDF=$(python3 - "$P" <<'PYEOF'
import json, sys
from pathlib import Path
PD = Path(sys.argv[1])
idx = {p["cf_paper_id"]: p for p in json.loads((PD / "SUPPLEMENTARY-INDEX.json").read_text())["papers"]}
f = idx["CF-P11"]["use_document"]
assert (PD / f).exists(), f"missing {f}"
print(f)
PYEOF
)
[ -n "$PDF" ] || { echo "FATAL: could not resolve CF-P11 pdf"; exit 1; }
echo "===== CF-P11 v2 queued $(date), waiting for CF-P18 v2 ====="
while pgrep -f "p18_v2.sh" >/dev/null; do sleep 30; done
while pgrep -f "extract10.py" >/dev/null; do sleep 20; done
lms unload --all >/dev/null 2>&1
echo "===== CF-P11 v2 (revised prompt) started $(date) ====="
echo "  pdf: $PDF"

MODELS=(
"gemma|gemma-3-27b-it|40960"
"mistral|mistral-small-3.1-24b-instruct-2503|32768"
"qwen|qwen3-vl-32b-instruct|65536"
)
for M in "${MODELS[@]}"; do
  IFS='|' read -r key mid ctx <<< "$M"
  todo=0; for r in 1 2 3; do [ -f "$R/CF-P11__${key}-r${r}.json" ] || todo=1; done
  [ "$todo" = 0 ] && { echo "[skip] $key complete"; continue; }
  echo "======== $key ctx=$ctx $(date +%H:%M:%S) ========"
  lms unload --all >/dev/null 2>&1
  lms load "$mid" --context-length "$ctx" --gpu max -y 2>&1 | tail -1
  for r in 1 2 3; do
    OUT="$R/CF-P11__${key}-r${r}.json"
    [ -f "$OUT" ] && { echo "  skip r$r"; continue; }
    echo "  --- CF-P11 repeat $r  $(date +%H:%M:%S) ---"
    python3 "$C/extract10.py" --cf-id CF-P11 --pdf "$P/$PDF" \
      --model "$mid" --max-tokens 16000 --out "$OUT" 2>&1 \
      | grep -E '^\[done\]|^\[abort\]|^\[recovered\]|^\[render\]|Error|Traceback|FATAL|No such'
  done
  lms unload --all >/dev/null 2>&1
done
echo "======== SCORING $(date +%H:%M:%S) ========"
python3 "$C/score10.py" --pred "$R"/*.json --out "$C/CF-P11-v2.xlsx" 2>&1 | tail -22
echo "===== finished $(date) ====="
