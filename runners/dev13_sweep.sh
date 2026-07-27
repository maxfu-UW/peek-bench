#!/bin/bash
# FULL DEV-13 SWEEP -- 13 papers x 3 models x 3 repeats = 117 runs.
#
# Every dev paper under ONE frozen prompt version. Earlier dev results came from mixed prompt
# versions (pre-ROUTE, post-ROUTE, plus per-paper scope notes added mid-campaign), so they are not
# poolable; this sweep re-runs all 13 including the six already done.
#
# MODEL-OUTER loop: 3 model loads total instead of 39, cutting ~2 h of load overhead to ~9 min.
# Paper list and PDF filenames resolve from SUPPLEMENTARY-INDEX.json -- never hand-typed, after a
# truncated literal silently killed an earlier run.
set -u
export PATH="$HOME/.lmstudio/bin:$PATH"
B="${PEEKBENCH_ROOT:?set PEEKBENCH_ROOT to the project root}"
C="$B/campaign"; P="$B/group_truth_excel_file/P2-data-source-papers"
R="$C/results_dev13"; mkdir -p "$R"; LOG="$C/dev13.log"
exec >>"$LOG" 2>&1

PAPERS=()
while IFS= read -r __ln; do PAPERS+=("$__ln"); done < <(python3 - "$P" "$B" <<'PYEOF'
import json, sys
from pathlib import Path
PD, B = Path(sys.argv[1]), Path(sys.argv[2])
idx = {p["cf_paper_id"]: p for p in json.loads((PD / "SUPPLEMENTARY-INDEX.json").read_text())["papers"]}
dev = json.loads((B / "splits/splits_v3_dev_test.json").read_text())["dev"]
for e in sorted(dev, key=lambda x: -x["uts"]):          # biggest papers first: fail fast, informative early
    cid = e["id"]; f = idx[cid]["use_document"]
    assert (PD / f).exists(), f"missing {f}"
    print(f"{cid}|{f}")
PYEOF
)
[ ${#PAPERS[@]} -eq 13 ] || { echo "FATAL: resolved ${#PAPERS[@]} papers, expected 13"; exit 1; }
echo "===== DEV-13 SWEEP started $(date) -- ${#PAPERS[@]} papers x 3 models x 3 repeats ====="

MODELS=(
"gemma|gemma-3-27b-it|40960"
"mistral|mistral-small-3.1-24b-instruct-2503|32768"
"qwen|qwen3-vl-32b-instruct|65536"
)
for M in "${MODELS[@]}"; do
  IFS='|' read -r key mid ctx <<< "$M"
  echo "======== MODEL $key ctx=$ctx $(date +%H:%M:%S) ========"
  lms unload --all >/dev/null 2>&1
  lms load "$mid" --context-length "$ctx" --gpu max -y 2>&1 | tail -1
  for PP in "${PAPERS[@]}"; do
    IFS='|' read -r cid pdf <<< "$PP"
    for r in 1 2 3; do
      OUT="$R/${cid}__${key}-r${r}.json"
      [ -f "$OUT" ] && { echo "  skip $cid $key r$r"; continue; }
      echo "  --- $cid $key repeat $r  $(date +%H:%M:%S) ---"
      python3 "$C/extract10.py" --cf-id "$cid" --pdf "$P/$pdf" \
        --model "$mid" --max-tokens 16000 --out "$OUT" 2>&1 \
        | grep -E '^\[done\]|^\[abort\]|^\[recovered\]|Error|Traceback|FATAL|No such'
    done
  done
  lms unload --all >/dev/null 2>&1
done

echo "======== SCORING $(date +%H:%M:%S) ========"
python3 "$C/score10.py" --pred "$R"/*.json --out "$C/DEV13-sweep.xlsx" 2>&1 | tail -30
echo "===== DEV-13 SWEEP finished $(date) ====="
