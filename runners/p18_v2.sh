#!/bin/bash
# CF-P18 re-run under the REVISED PROMPT -- 3 models x 3 repeats = 9 runs.
#
# WHY CF-P18 ALONE. CF-P19 was dropped: all 9 of its runs matched 12/12 GT rows with UTS MAPE
# 0.01-2.24%, a ceiling effect that cannot separate models. CF-P18 does the opposite -- its
# values exist only as printed labels on a raster bar chart (Fig. 4a), and only qwen read them
# (9/9 labels vs 0-1/9 for gemma and mistral). Three repeats matches the protocol used for every other paper in the
# campaign, keeping results poolable.
#
# PROMPT CHANGES UNDER TEST. Two are CORPUS-WIDE rules in INCLUSION CRITERIA:
#   ROUTE       exclude non-FFF reference specimens (CNC, injection-moulded) even from the same
#               authors -- Fig. 4a's legend marks these "Plain PEEK (CNC)".
#   FIBRE TYPE  carbon NANOTUBE-filled PEEK is fiber_weight_fraction = 0, not a CF grade.
# The third is a PAPER-SPECIFIC note from paper_scope.json, applied to CF-P18 only:
#   "extract ONLY the room-temperature results; exclude 110 C and 130 C."
# It is per-paper rather than global because a global room-temperature rule would delete 4 of
# CF-P06's 5 GT rows -- that paper IS a temperature sweep (25 to -175 C) and sits in the FROZEN
# TEST split. Both papers study temperature, so no corpus-wide rule can separate them.
# COST: CF-P18 no longer sees the same prompt as the rest of the corpus; footnote it.
# Prediction: predicted rows fall from ~9 to ~2 without losing the correct room-temperature
# values, so precision rises while UTS accuracy holds. If qwen's UTS MAPE degrades, the added
# rules are costing attention rather than focusing it.
set -u
export PATH="$HOME/.lmstudio/bin:$PATH"
B="${PEEKBENCH_ROOT:?set PEEKBENCH_ROOT to the project root}"
C="$B/campaign"; P="$B/group_truth_excel_file/P2-data-source-papers"
R="$C/results_p18_v2"; mkdir -p "$R"; LOG="$C/p18_v2.log"
exec >>"$LOG" 2>&1

# Filename resolved from the index, never hand-typed (a truncated literal killed an earlier run).
PDF=$(python3 - "$P" <<'PYEOF'
import json, sys
from pathlib import Path
PD = Path(sys.argv[1])
idx = {p["cf_paper_id"]: p for p in json.loads((PD / "SUPPLEMENTARY-INDEX.json").read_text())["papers"]}
f = idx["CF-P18"]["use_document"]
assert (PD / f).exists(), f"missing {f}"
print(f)
PYEOF
)
[ -n "$PDF" ] || { echo "FATAL: could not resolve CF-P18 pdf"; exit 1; }
echo "===== CF-P18 v2 (revised prompt) started $(date) ====="
echo "  pdf: $PDF"

MODELS=(
"gemma|gemma-3-27b-it|40960"
"mistral|mistral-small-3.1-24b-instruct-2503|32768"
"qwen|qwen3-vl-32b-instruct|65536"
)
for M in "${MODELS[@]}"; do
  IFS='|' read -r key mid ctx <<< "$M"
  todo=0; for r in 1 2 3; do [ -f "$R/CF-P18__${key}-r${r}.json" ] || todo=1; done
  [ "$todo" = 0 ] && { echo "[skip] $key complete"; continue; }
  echo "======== $key ctx=$ctx $(date +%H:%M:%S) ========"
  lms unload --all >/dev/null 2>&1
  lms load "$mid" --context-length "$ctx" --gpu max -y 2>&1 | tail -1
  for r in 1 2 3; do
    OUT="$R/CF-P18__${key}-r${r}.json"
    [ -f "$OUT" ] && { echo "  skip r$r"; continue; }
    echo "  --- CF-P18 repeat $r  $(date +%H:%M:%S) ---"
    python3 "$C/extract10.py" --cf-id CF-P18 --pdf "$P/$PDF" \
      --model "$mid" --max-tokens 16000 --out "$OUT" 2>&1 \
      | grep -E '^\[done\]|^\[abort\]|^\[recovered\]|^\[render\]|Error|Traceback|FATAL|No such'
  done
  lms unload --all >/dev/null 2>&1
done
echo "======== SCORING $(date +%H:%M:%S) ========"
python3 "$C/score10.py" --pred "$R"/*.json --out "$C/CF-P18-v2.xlsx" 2>&1 | tail -22
echo "===== finished $(date) ====="
