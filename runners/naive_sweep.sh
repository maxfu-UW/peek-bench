#!/bin/bash
# NAIVE BASELINE -- 13 dev papers x 3 local models x 1 repeat = 39 runs.
#
# Mimics a first attempt by someone who has not yet discovered this corpus's failure modes:
# the prompt asks for the columns and says "use null if not given", and nothing else. No field
# disambiguations, no inclusion criteria, no "charts count", no "never invent combinations",
# no per-paper scope notes, no method. 869 chars vs the engineered prompt's 6,820.
#
# 1 repeat only (the user's choice, to save time). NOTE: this campaign showed large run-to-run
# variance, so these numbers carry no error bars and should be read as directional.
set -u
export PATH="$HOME/.lmstudio/bin:$PATH"
B="${PEEKBENCH_ROOT:-${PEEKBENCH_ROOT:?set PEEKBENCH_ROOT}}"
C="$B/campaign"; P="$B/group_truth_excel_file/P2-data-source-papers"
R="$C/results_naive"; mkdir -p "$R"; LOG="$C/naive.log"
exec >>"$LOG" 2>&1

PAPERS=()
while IFS= read -r __ln; do PAPERS+=("$__ln"); done < <(python3 - "$P" "$B" <<'PYEOF'
import json, sys
from pathlib import Path
PD, B = Path(sys.argv[1]), Path(sys.argv[2])
idx = {p["cf_paper_id"]: p for p in json.loads((PD / "SUPPLEMENTARY-INDEX.json").read_text())["papers"]}
dev = json.loads((B / "splits/splits_v3_dev_test.json").read_text())["dev"]
for e in sorted(dev, key=lambda x: -x["uts"]):
    cid = e["id"]; f = idx[cid]["use_document"]
    assert (PD / f).exists(), f"missing {f}"
    print(f"{cid}|{f}")
PYEOF
)
[ ${#PAPERS[@]} -eq 13 ] || { echo "FATAL: resolved ${#PAPERS[@]} papers"; exit 1; }
echo "===== NAIVE BASELINE started $(date) -- 13 papers x 3 models x 1 repeat ====="

MODELS=(
"gemma|gemma-3-27b-it|40960"
"mistral|mistral-small-3.1-24b-instruct-2503|65536"
"qwen|qwen3-vl-32b-instruct|65536"
)
for M in "${MODELS[@]}"; do
  IFS='|' read -r key mid ctx <<< "$M"
  echo "======== MODEL $key ctx=$ctx $(date +%H:%M:%S) ========"
  lms unload --all >/dev/null 2>&1
  lms load "$mid" --context-length "$ctx" --gpu max -y 2>&1 | tail -1
  for PP in "${PAPERS[@]}"; do
    IFS='|' read -r cid pdf <<< "$PP"
    OUT="$R/${cid}__${key}-r1.json"
    [ -f "$OUT" ] && { echo "  skip $cid $key"; continue; }
    echo "  --- $cid $key  $(date +%H:%M:%S) ---"
    python3 "$C/extract_naive.py" --cf-id "$cid" --pdf "$P/$pdf" \
      --model "$mid" --max-tokens 16000 --out "$OUT" 2>&1 \
      | grep -E '^\[done\]|^\[abort\]|Error|Traceback|FATAL'
  done
  lms unload --all >/dev/null 2>&1
done
echo "======== SCORING $(date +%H:%M:%S) ========"
python3 "$C/score10.py" --pred "$R"/*.json --out "$C/NAIVE-baseline.xlsx" 2>&1 | tail -20
echo "===== NAIVE BASELINE finished $(date) ====="
