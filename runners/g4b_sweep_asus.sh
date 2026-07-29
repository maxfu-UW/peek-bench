#!/bin/bash
# GEMMA-3-4B ARM -- engineered prompt, on the ASUS A2000 via remote LM Studio.
#
# Third point on the CAPACITY axis at FIXED image tokens. Gemma 3 spends 258 tok/page at every
# size (token-delta measured on 4B, 12B and 27B independently), so this varies parameters alone:
#     4B  (this run, A2000)  |  12B (results_dev13_g12b, M4 Pro)  |  27B (results_dev13, M4 Pro)
#
# PRE-FLIGHT, image-inclusive, run before launch (the check that was missing when the 12B@32k and
# qwen3-vl-8b@40k attempts both died with the vision encoder unallocatable):
#     one full-res page image      -> OK, 258 tok
#     CF-P15 full text + 4 images  -> 27,694 of 40,960; 11,466 headroom (room for 44 more images)
#
# Harness: extract10_remote.py -- byte-identical to extract10.py except for --host (see `diff`).
set -u
B="/Users/maxfu/Library/CloudStorage/GoogleDrive-fuhuilong2012@gmail.com/My Drive/peek_bench_2026"
C="$B/campaign"; P="$B/group_truth_excel_file/P2-data-source-papers"
R="$C/results_dev13_g4b"; mkdir -p "$R"; LOG="$C/g4b.log"
HOST="192.168.1.116"; MID="google/gemma-3-4b"
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

# Guard BEFORE EVERY RUN, not just at launch. The 12B arm was destroyed by the server silently
# reloading at a smaller context mid-sweep; a launch-only check cannot catch that.
check_server () {
  curl -sS -m 10 "http://$HOST:1234/api/v0/models" 2>/dev/null | python3 -c "
import sys,json
try: d=json.load(sys.stdin)
except Exception: sys.exit(1)
for m in d.get('data',[]):
    if m.get('state')=='loaded' and m.get('id')=='$MID' and m.get('loaded_context_length')==40960:
        print('OK'); sys.exit(0)
sys.exit(1)
" 2>/dev/null
}

echo "===== G4B (A2000) SWEEP started $(date) -- 13 papers x 3 repeats = 39 runs ====="
for PP in "${PAPERS[@]}"; do
  IFS='|' read -r cid pdf <<< "$PP"
  for r in 1 2 3; do
    OUT="$R/${cid}__g4b-r${r}.json"
    [ -f "$OUT" ] && { echo "  skip $cid r$r"; continue; }
    if [ "$(check_server)" != "OK" ]; then
      echo "  FATAL: $MID @40960 not served at $cid r$r $(date +%H:%M:%S) -- STOPPING so partial"
      echo "         results cannot silently enter a table. Reload and re-run; completed runs resume."
      exit 1
    fi
    echo "  --- $cid g4b repeat $r  $(date +%H:%M:%S) ---"
    python3 "$C/extract10_remote.py" --cf-id "$cid" --pdf "$P/$pdf" \
      --model "$MID" --host "$HOST" --max-tokens 16000 --out "$OUT" 2>&1 \
      | grep -E '^\[done\]|^\[abort\]|^\[recovered\]|Error|Traceback|FATAL|No such'
  done
done
echo "======== SCORING $(date +%H:%M:%S) ========"
python3 "$C/score10.py" --pred "$R"/*.json --out "$C/G4B-sweep.xlsx" 2>&1 | tail -30
echo "===== G4B SWEEP finished $(date) ====="
