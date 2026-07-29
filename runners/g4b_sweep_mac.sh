#!/bin/bash
# GEMMA-3-4B ARM -- ON THE MAC. Closes two confounds the A2000 arm carried:
#   publisher: A2000 served google/gemma-3-4b; the 12B and 27B arms are BOTH
#              lmstudio-community. This uses lmstudio-community/gemma-3-4b-it-Q4_K_M.gguf.
#   backend:   A2000 = llama.cpp CUDA; 12B/27B = llama.cpp Metal. Different kernels and
#              float reduction orders can diverge over ~3k output tokens.
# Result: 4B / 12B / 27B become same publisher, same backend, same machine, same ctx 40,960,
# same 258 image tok/page -- varying PARAMETERS alone.
#
# Uses extract10.py (the arm-defining harness), NOT extract10_remote.py -- local, so identical.
set -u
export PATH="$HOME/.lmstudio/bin:$PATH"
B="/Users/maxfu/Library/CloudStorage/GoogleDrive-fuhuilong2012@gmail.com/My Drive/peek_bench_2026"
C="$B/campaign"; P="$B/group_truth_excel_file/P2-data-source-papers"
R="$C/results_dev13_g4b_mac"; mkdir -p "$R"; LOG="$C/g4b_mac.log"
MID="gemma-3-4b-it"; CTX=40960
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

echo "===== G4B-MAC SWEEP started $(date) -- 13 papers x 3 repeats = 39 runs ====="
lms unload --all >/dev/null 2>&1
lms load "$MID" --context-length "$CTX" --gpu max -y 2>&1 | tail -1
for PP in "${PAPERS[@]}"; do
  IFS='|' read -r cid pdf <<< "$PP"
  for r in 1 2 3; do
    OUT="$R/${cid}__g4bmac-r${r}.json"
    [ -f "$OUT" ] && { echo "  skip $cid r$r"; continue; }
    echo "  --- $cid g4b-mac repeat $r  $(date +%H:%M:%S) ---"
    python3 "$C/extract10.py" --cf-id "$cid" --pdf "$P/$pdf" \
      --model "$MID" --max-tokens 16000 --out "$OUT" 2>&1 \
      | grep -E '^\[done\]|^\[abort\]|^\[recovered\]|Error|Traceback|FATAL|No such'
  done
done
echo "======== SCORING $(date +%H:%M:%S) ========"
python3 "$C/score10.py" --pred "$R"/*.json --out "$C/G4B-MAC-sweep.xlsx" 2>&1 | tail -30
echo "===== G4B-MAC SWEEP finished $(date) ====="
