#!/bin/bash
# GEMMA-3-27B REPEAT SWEEP -- second independent sweep of the arm that carries the top point of
# the capacity curve. Run 1 lives in results_dev13/*__gemma-r*.json (alongside mistral and qwen);
# this writes to its own directory so neither can contaminate the other.
#
# WHY: two arms have now each swung >50% relative on a headline metric between IDENTICAL sweeps --
# gemma-3-4b UTS MAPE 40.85/17.47/36.36 (CV 39.3%), and gemma-3-12b row F1 0.288 -> 0.437. The 27B
# is the last unrepeated arm and currently carries the monotonicity claim on a single sample.
#
# CONFIG PARITY with run 1, from dev13_sweep.sh:35 -- gemma-3-27b-it @ ctx 40960, extract10.py,
# --max-tokens 16000, temperature default (0.1), same frozen prompt, same paper order.
set -u
export PATH="$HOME/.lmstudio/bin:$PATH"
B="/Users/maxfu/Library/CloudStorage/GoogleDrive-fuhuilong2012@gmail.com/My Drive/peek_bench_2026"
C="$B/campaign"; P="$B/group_truth_excel_file/P2-data-source-papers"
R="$C/results_dev13_g27b_run2"; mkdir -p "$R"; LOG="$C/g27b_run2.log"
MID="gemma-3-27b-it"; CTX=40960
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
[ ${#PAPERS[@]} -eq 13 ] || { echo "FATAL: resolved ${#PAPERS[@]} papers, expected 13"; exit 1; }

# The 12B repeat lost its first launch to a stopped server (lms unload had killed it) and failed
# every run with connection-refused. Check before loading, and check again before every run.
lms server start >/dev/null 2>&1
curl -sS -m 8 http://localhost:1234/v1/models >/dev/null 2>&1 || { echo "FATAL: no server on :1234"; exit 1; }

echo "===== G27B REPEAT SWEEP started $(date) -- 13 papers x 3 repeats = 39 runs ====="
lms unload --all >/dev/null 2>&1
lms load "$MID" --context-length "$CTX" --gpu max -y 2>&1 | tail -1
for PP in "${PAPERS[@]}"; do
  IFS='|' read -r cid pdf <<< "$PP"
  for r in 1 2 3; do
    OUT="$R/${cid}__gemma27b-r${r}.json"
    [ -f "$OUT" ] && { echo "  skip $cid r$r"; continue; }
    curl -sS -m 8 http://localhost:1234/v1/models >/dev/null 2>&1 || {
      echo "  FATAL: server vanished at $cid r$r $(date +%H:%M:%S) -- stopping so partial results"
      echo "         cannot silently enter a table. Completed runs resume on relaunch."; exit 1; }
    echo "  --- $cid gemma27b repeat $r  $(date +%H:%M:%S) ---"
    python3 "$C/extract10.py" --cf-id "$cid" --pdf "$P/$pdf" \
      --model "$MID" --max-tokens 16000 --out "$OUT" 2>&1 \
      | grep -E '^\[done\]|^\[abort\]|^\[recovered\]|Error|Traceback|FATAL|No such'
  done
done
echo "======== SCORING $(date +%H:%M:%S) ========"
python3 "$C/score10.py" --pred "$R"/*.json --out "$C/G27B-repeat.xlsx" 2>&1 | tail -30
echo "===== G27B REPEAT SWEEP finished $(date) ====="
