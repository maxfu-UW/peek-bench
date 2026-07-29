#!/usr/bin/env python3
"""Live progress: gemma-3 CAPACITY CURVE at fixed image tokens (258 tok/page, measured at all sizes).

  4B  MAC   results_dev13_g4b_mac/   lmstudio-community  Metal   <- LIVE, closes the confound
  4B  A2000 results_dev13_g4b/       google              CUDA    <- done; publisher+backend differ
  12B MAC   results_dev13_g12b/      lmstudio-community  Metal   <- done
  27B MAC   results_dev13/           lmstudio-community  Metal   <- done

RECALL is shown next to row F1 deliberately: a model that under-extracts scores F1 on a small
self-selected subset, so F1 can invert while recall does not (docs/failure-modes.md sec.3).
"""
import glob, json, os, re, time, ast
from datetime import datetime
from pathlib import Path
import fitz, importlib.util, pandas as pd

C = Path(__file__).parent
PD = C.parent / "group_truth_excel_file" / "P2-data-source-papers"
IDX = {p["cf_paper_id"]: p for p in json.loads((PD/"SUPPLEMENTARY-INDEX.json").read_text())["papers"]}
DEV = json.loads((C.parent/"splits/splits_v3_dev_test.json").read_text())["dev"]
ORDER = [e["id"] for e in sorted(DEV, key=lambda x: -x["uts"])]
UTS = {e["id"]: e["uts"] for e in DEV}
_pg = {}
def pages(cid):
    if cid not in _pg:
        d = fitz.open(PD/IDX[cid]["use_document"]); _pg[cid] = d.page_count; d.close()
    return _pg[cid]

_s = importlib.util.spec_from_file_location("s10", C/"score10.py")
S10 = importlib.util.module_from_spec(_s); _s.loader.exec_module(S10)
_GT = S10.load_gt(); _GR = {}
def gt_rows(cid):
    if cid not in _GR:
        g = _GT[_GT.cf_paper_id == cid]
        _GR[cid] = [{k: (None if pd.isna(v) else v) for k, v in r.items()} for r in g.to_dict("records")]
    return _GR[cid]

ARMS = [
    ("4B  MACr3", C/"results_dev13_g4b_mac",      r"(CF-P\d+)__g4bmac-r(\d)\.json", C/"g4b_mac.log", True),
    ("4B  MACr2", C/"results_dev13_g4b_mac_run2", r"(CF-P\d+)__g4bmac-r(\d)\.json", C/"g4b_mac_run2.log", False),
    ("4B  MACr1", C/"results_dev13_g4b_mac_run1", r"(CF-P\d+)__g4bmac-r(\d)\.json", C/"g4b_mac.log", False),
    ("4B  A2000", C/"results_dev13_g4b",          r"(CF-P\d+)__g4b-r(\d)\.json",    C/"g4b.log",     False),
    ("12B MAC  ", C/"results_dev13_g12b",         r"(CF-P\d+)__g12b-r(\d)\.json",   C/"g12b.log",    False),
]

def collect(rdir, pat):
    got, met = {}, {}
    for f in glob.glob(str(rdir/"*.json")):
        m = re.match(pat, os.path.basename(f))
        if not m: continue
        try: j = json.load(open(f))
        except Exception: continue
        rows = j.get("submitted_full") or j.get("rows") or []
        got[(m.group(1), int(m.group(2)))] = (j.get("wall_clock_min", 0), len(rows), len(j.get("pages_viewed") or []))
        try: met[(m.group(1), int(m.group(2)))] = S10.score_one(rows, gt_rows(m.group(1)), "x", m.group(1))[0]
        except Exception: pass
    return got, met

_MON = {m: i+1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}

def _stamp(ln, kind):
    m = re.search(rf"SWEEP {kind} \w+ (\w+) +(\d+) (\d+):(\d+):(\d+) \w+ (\d+)", ln)
    if not m:
        return None
    mon, day, hh, mm, ss, yr = m.groups()
    return datetime(int(yr), _MON[mon], int(day), int(hh), int(mm), int(ss))

def span(log):
    """(start, finish|None) from the banner lines.

    Parses the FULL date, not just the clock. Two bugs this fixes:
      - a completed arm was timed as now-start, so its duration grew as the night went on
        (the 12B arm read 9h53m for a run that took 2h48m);
      - the old same-day-then-subtract-one hack mis-dated any sweep crossing midnight, which
        both of tonight's arms did.
    """
    st = fi = None
    try:
        for ln in open(log):
            if st is None:
                st = _stamp(ln, "started")
            f = _stamp(ln, "finished")
            if f:
                fi = f
    except Exception:
        pass
    return st, fi

def agg(ms, k):
    v = [m[k] for m in ms if m.get(k) is not None]
    return sum(v)/len(v) if v else None
def f(x, d=3): return "  -  " if x is None else "%.*f" % (d, x)
hm = lambda x: "%dh%02dm" % (int(x)//60, int(x)%60) if x >= 60 else "%dm" % int(x)

B27 = None
try:
    b = pd.read_excel(C/"DEV13-sweep.xlsx", sheet_name="summary"); b = b[b["run"].notna()]
    b = b[b.model == "gemma-3-27b-it"].copy()
    b["paper"] = b["run"].astype(str).str.extract(r"(CF-P\d+)")
    def nv(v):
        try: return len(ast.literal_eval(str(v)))
        except Exception: return 0
    b["views"] = b.pages_viewed.map(nv); B27 = b
except Exception: pass

print()
DATA = []
for name, rdir, pat, log, live in ARMS:
    got, met = collect(rdir, pat); DATA.append((name, got, met))
    n = len(got); pct = n/39; W = 28
    bar = "#"*int(W*pct) + "."*(W-int(W*pct))
    bar = bar.replace("#", "█").replace(".", "░")
    st, fi = span(log)
    el = ((fi or datetime.now()) - st).total_seconds()/60 if st else 0
    obs = {}
    for (c, _), (t, _, _) in got.items(): obs.setdefault(c, []).append(t/pages(c))
    rate = (sum(sum(v)/len(v) for v in obs.values())/len(obs)) if obs else 0.10
    rem = sum(rate*pages(c)*(3-sum(1 for (p_, _) in got if p_ == c)) for c in ORDER)
    tag = "  <-- LIVE" if live and n < 39 else ""
    if n >= 39:
        print(f"  gemma-3-{name} [{bar}] {n}/39 100%  COMPLETE in {hm(el)}{tag}")
    else:
        eta = time.strftime("%H:%M", time.localtime(time.time()+rem*60))
        print(f"  gemma-3-{name} [{bar}] {n}/39 {pct*100:3.0f}%  elapsed {hm(el):>5s} left ~{hm(rem):>5s} eta {eta}{tag}")

print(f"\n  CAPACITY CURVE -- 258 img tok/page, engineered prompt, ctx 40,960")
print(f"  {'arm':11s}{'pub/backend':>20s}{'runs':>7s}{'row F1':>8s}{'RECALL':>8s}{'prec':>7s}{'cell':>7s}{'MAPE':>8s}{'rows':>6s}{'views':>7s}")
META = {"4B  MACr3": "lmstudio/Metal", "4B  MACr2": "lmstudio/Metal", "4B  MACr1": "lmstudio/Metal",
        "4B  A2000": "google/CUDA", "12B MAC  ": "lmstudio/Metal"}
for name, got, met in DATA:
    ms = list(met.values()); v=[x[2] for x in got.values()]; rw=[x[1] for x in got.values()]
    print(f"  {name:11s}{META.get(name,''):>20s}{len(got):>3d}/39{f(agg(ms,'row_f1')):>8s}{f(agg(ms,'row_recall')):>8s}"
          f"{f(agg(ms,'row_precision')):>7s}{f(agg(ms,'cell_acc')):>7s}{f(agg(ms,'UTS_MAPE_pct'),2):>8s}"
          f"{(sum(rw)/len(rw)) if rw else 0:>6.1f}{(sum(v)/len(v)) if v else 0:>7.2f}")
if B27 is not None:
    print(f"  {'27B MAC':11s}{'lmstudio/Metal':>20s}{len(B27):>3d}/39{B27.row_f1.mean():>8.3f}{B27.row_recall.mean():>8.3f}"
          f"{B27.row_precision.mean():>7.3f}{B27.cell_acc.mean():>7.3f}{B27.UTS_MAPE_pct.mean():>8.2f}"
          f"{B27.pred_rows.mean():>6.1f}{B27.views.mean():>7.2f}")

print(f"\n  {'paper':9s}{'pts':>4s}{'pg':>4s}  {'4B-mac':<7s}{'4B-a2k':<7s}{'12B':<7s}"
      f"{'recall 4Bmac/4Ba2k/12B':<26s}{'MAPE 4Bmac/4Ba2k/12B':<24s}")
for cid in ORDER:
    cells = []
    for _, got, _ in DATA:
        cells.append("".join("x" if (cid, r) in got and got[(cid, r)][1] == 0
                             else ("●" if (cid, r) in got else "·") for r in (1, 2, 3)))
    mm = [[v for k, v in D[2].items() if k[0] == cid] for D in DATA]
    print(f"  {cid:9s}{UTS[cid]:>4d}{pages(cid):>4d}  {cells[0]:<7s}{cells[1]:<7s}{cells[2]:<7s}"
          f"{'/'.join(f(agg(m,'row_recall')) for m in mm):<26s}"
          f"{'/'.join(f(agg(m,'UTS_MAPE_pct'),2) for m in mm):<24s}")

