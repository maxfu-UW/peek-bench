#!/usr/bin/env python3
"""Per-CELL answerability audit: is each GT parameter value actually present in the source document?

Motivation: CF-P13's process parameters live in SI Table S1, not the main article, so every
model correctly returned null and was scored wrong. CF-P17/P12/P11/P22 have GT values that
appear in NO document (curator inference from datasheets). Scoring those cells penalises
faithful extraction, and three of them sit in the frozen test split.

Emits findability.json:
  {cf_paper_id: {"doc": <file used>, "cells": {"<gt_row_idx>": {col: true/false}},
                 "ceiling": <findable/total>}}

SCOPE AND LIMITS (deliberate):
  * Applies ONLY to the 9 input parameters. tensile_strength is EXCLUDED from this audit —
    it is frequently figure-sourced, so absence from the text layer says nothing about whether
    a model could read it off a chart. Excluding UTS cells would gut the benchmark.
  * Text-layer string match is OPTIMISTIC: a bare "400" anywhere counts as found. So the real
    ceiling is at or below what this reports. It is a floor on unanswerability, not a precise
    measure.
  * Uses `use_document` from SUPPLEMENTARY-INDEX.json, i.e. the merged WITH-SI pdf where one
    exists — so CF-P13 is audited against the document the harness will actually be given.
"""
import json, os, re, sys, unicodedata
from pathlib import Path

import fitz
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import importlib.util
spec = importlib.util.spec_from_file_location("s", HERE / "score10.py")
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)

PAPERS_DIR = (HERE.parent / "group_truth_excel_file" / "P2-data-source-papers")
INDEX = PAPERS_DIR / "SUPPLEMENTARY-INDEX.json"
PARAMS = ["nozzle_diameter", "nozzle_temp", "printing_speed", "fiber_weight_fraction",
          "infill_percentage", "specimen_thickness", "layer_thickness", "platform_temp"]


def norm(s):
    return unicodedata.normalize("NFKD", s).replace("ﬁ", "fi").replace("ﬂ", "fl")


def candidates(v):
    """String forms a value might legitimately take in a paper."""
    out = {f"{v:g}"}
    if float(v).is_integer():
        out |= {str(int(v)), f"{int(v)}.0", f"{int(v):,}"}
    else:
        out |= {f"{v:.1f}", f"{v:.2f}", f"{v:g}".lstrip("0")}
    return {c for c in out if c}


def main():
    idx = json.loads(INDEX.read_text())
    gt = S.load_gt()
    out = {}
    for rec in idx["papers"]:
        cid, doc = rec["cf_paper_id"], rec["use_document"]
        p = PAPERS_DIR / doc
        if not p.exists():
            print(f"  !! missing {doc}"); continue
        d = fitz.open(p)
        text = norm("".join(d.load_page(i).get_text() for i in range(d.page_count)))
        d.close()
        g = gt[gt.cf_paper_id == cid].reset_index(drop=True)
        cells, tot, found = {}, 0, 0
        for i, row in g.iterrows():
            flags = {}
            for c in PARAMS:
                v = pd.to_numeric(row[c], errors="coerce")
                if pd.isna(v):
                    continue                      # GT blank: already excluded by the scorer
                ok = any(s in text for s in candidates(v))
                flags[c] = bool(ok); tot += 1; found += int(ok)
            cells[str(i)] = flags
        out[cid] = {"doc": doc, "cells": cells,
                    "param_cells": tot, "findable": found,
                    "ceiling": round(found / tot, 4) if tot else 1.0}
        print(f"  {cid:8} {found:>4}/{tot:<4} = {out[cid]['ceiling']:>6.1%}  {doc[:46]}")
    (HERE / "findability.json").write_text(json.dumps(out, indent=2))
    ceil = sum(v["findable"] for v in out.values()) / sum(v["param_cells"] for v in out.values())
    print(f"\ncorpus-wide parameter answerability ceiling: {ceil:.1%}")
    print(f"wrote {HERE/'findability.json'}")


if __name__ == "__main__":
    main()
