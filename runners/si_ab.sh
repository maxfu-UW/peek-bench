#!/bin/bash
# CF-P13 SUPPLEMENTARY-INFORMATION A/B, v2 -- 2 arms x 3 models x 3 repeats = 18 runs.
#
# WHY BOTH ARMS RE-RUN. v1 compared a main-only control against a +SI treatment and found a
# large effect, but two of nine runs died: one on turn exhaustion (21-page doc, fixed 14-turn
# budget) and one on invalid JSON (`"printing_speed": 20/60,  // mm/s`). Three harness fixes
# followed -- strict-JSON instruction, an output sanitiser, and a page-scaled turn budget.
# All three change model behaviour in BOTH arms, so re-running only the treatment would
# confound "document completeness" with "harness version". The control is re-collected here.
#
#   CONTROL   main article only, 11 pages. Parameter answerability ceiling 83%.
#   TREATMENT main + supplementary merged, 21 pages. Ceiling 100%.
# Only the input document differs between arms; model, harness, prompt, schema, GT identical.
set -u
export PATH="$HOME/.lmstudio/bin:$PATH"
B="${PEEKBENCH_ROOT:?set PEEKBENCH_ROOT to the project root}"
C="$B/campaign"; P="$B/group_truth_excel_file/P2-data-source-papers"
R="$C/results_si_ab"; mkdir -p "$R"; LOG="$C/si_ab.log"
exec >>"$LOG" 2>&1
echo "===== CF-P13 SI A/B v2 (18 runs, fixed harness) started $(date) ====="

MAIN="Li-2023-Improving mechanical performances at r.pdf"
SI="Li-2023-Improving mechanical performances at r-WITH-SI.pdf"
for f in "$MAIN" "$SI"; do [ -f "$P/$f" ] || { echo "FATAL: missing $f"; exit 1; }; done

MODELS=(
"gemma|gemma-3-27b-it|40960"
"mistral|mistral-small-3.1-24b-instruct-2503|32768"
"qwen|qwen3-vl-32b-instruct|65536"
)

for M in "${MODELS[@]}"; do
  IFS='|' read -r key mid ctx <<< "$M"
  todo=0
  for arm in main si; do for r in 1 2 3; do
    [ -f "$R/CF-P13__${key}-${arm}-r${r}.json" ] || todo=1
  done; done
  [ "$todo" = 0 ] && { echo "[skip] $key complete"; continue; }
  echo "======== $key ctx=$ctx $(date +%H:%M:%S) ========"
  lms unload --all >/dev/null 2>&1
  lms load "$mid" --context-length "$ctx" --gpu max -y 2>&1 | tail -1
  # Both arms under one model load: 3 loads total, not 6.
  for arm in main si; do
    [ "$arm" = main ] && PDF="$MAIN" || PDF="$SI"
    for r in 1 2 3; do
      OUT="$R/CF-P13__${key}-${arm}-r${r}.json"
      [ -f "$OUT" ] && { echo "  skip $arm r$r"; continue; }
      echo "  --- CF-P13 [$arm] repeat $r  $(date +%H:%M:%S) ---"
      # no --max-turns: extract10.py now scales it with page count (11pg->21, 21pg->31)
      python3 "$C/extract10.py" --cf-id CF-P13 --pdf "$P/$PDF" \
        --model "$mid" --max-tokens 16000 --out "$OUT" 2>&1 \
        | grep -E '^\[done\]|^\[abort\]|^\[recovered\]|^\[render\]|Error|Traceback|No such'
    done
  done
  lms unload --all >/dev/null 2>&1
done

echo "======== SCORING both arms $(date +%H:%M:%S) ========"
python3 "$C/score10.py" --pred "$R"/*.json --out "$C/CF-P13-SI-AB-v2.xlsx" 2>&1 | tail -30
echo "===== finished $(date) ====="
