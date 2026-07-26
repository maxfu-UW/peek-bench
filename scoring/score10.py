#!/usr/bin/env python3
"""
Score PEEK-Bench predictions (9 params + UTS) against the curated GT and write an Excel workbook.

GT = PEEK2-CF-main-2026May17-CF-P27d.xlsx / Sheet1, with the SAME four filters the P2 notebook applies:
  1. tensile_strength notna   2. cf_paper_id notna
  3. coupon_orientation != 'vertical'   4. source in the 23-paper whitelist
This reproduces the paper's 232 datapoints exactly.

Metrics
  * Hungarian row alignment on the 9 design parameters
  * row precision / recall / F1; misses vs hallucinations
  * tolerance-aware cell accuracy (design 1%, UTS 5% — UTS is often a chart read)
  * UTS MAPE
  * FALSE-FILL RATE: of GT-blank cells (paper does not report the value), how often did the model
    invent one? Max's imputation defaults (0.4mm / +-45 / 100% / 130C) are exactly what a model
    would guess, so this separates reading from convention-guessing.

Usage:
  python score10.py --pred results10/CF-P05__gemma.json ... --out compare.xlsx
"""
import argparse, hashlib, json, os, re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

# Ground truth is NOT distributed with this repo (it is the curated research dataset).
# Point PEEKBENCH_GT_DIR at a directory holding PEEK2-CF-main-*-peekbench-v*.xlsx.
GT_DIR = Path(os.environ.get("PEEKBENCH_GT_DIR", "./ground_truth"))


def resolve_gt(directory=None):
    """Newest peekbench-versioned ground truth, or the legacy file if none exists yet.

    Max re-versions the GT after each curation change (…-peekbench-v1b.xlsx, then v1c …).
    Pinning one filename would silently score against a STALE file — which fails as plausible
    numbers rather than as an error, the worst failure mode for a benchmark. Resolving the
    highest version and printing it (with a hash) on every run makes the binding visible.
    """
    d = Path(directory or GT_DIR)
    cands = [f for f in d.glob("PEEK2-CF-main-*-peekbench-v*.xlsx") if not f.name.startswith("~$")]
    if cands:
        def key(f):
            m = re.search(r"-peekbench-v(\d+)([a-z]*)\.xlsx$", f.name)
            return (int(m.group(1)), m.group(2)) if m else (-1, "")
        return max(cands, key=key)
    return d / "PEEK2-CF-main-2026May17-CF-P27d.xlsx"


GT_XLSX = str(resolve_gt())
WHITELIST = {"Adarsh et al. 2025","Allouch et al. 2024","Bala Santhosh et al. 2025","Bashir et al. 2025",
 "Cui et al. 2025","de Carvalho et al. 2023","Fu et al. 2023","Gupta et al. 2023","Han et al. 2019",
 "Hu et al. 2021","Hu et al. 2024","Li et al. 2023","Lv et al. 2024","Megersa et al. 2026",
 "Mutyala et al. 2022","Naganaboyina et al. 2023","Nyman et al. 2024","Rehekampff et al. 2019",
 "Subramani et al. 2024","Vasu et al. 2026","Wang et al. 2020","Wang et al. 2021","Wang et al. 2022"}

NUMERIC = ["nozzle_diameter","nozzle_temp","printing_speed","fiber_weight_fraction",
           "infill_percentage","specimen_thickness","layer_thickness","platform_temp"]
TEXT = ["raster_angle"]
OUTPUT = ["tensile_strength"]
SCORED = NUMERIC + TEXT + OUTPUT
TOL = {c: (0.01, 0.5) for c in NUMERIC}
TOL["tensile_strength"] = (0.05, 1.0)


FIND_MAP = None


def load_findability():
    """Per-cell answerability map from audit_findability.py (None if not generated)."""
    global FIND_MAP
    if FIND_MAP is None:
        f = Path(__file__).parent / "findability.json"
        FIND_MAP = json.loads(f.read_text()) if f.exists() else {}
    return FIND_MAP


OOS_MAP = None


def load_out_of_scope():
    """Conditions the paper reports but the curator deliberately excluded (out_of_scope.json)."""
    global OOS_MAP
    if OOS_MAP is None:
        f = Path(__file__).parent / "out_of_scope.json"
        OOS_MAP = (json.loads(f.read_text()).get("papers", {}) if f.exists() else {})
    return OOS_MAP


def load_gt(path=GT_XLSX):
    df = pd.read_excel(path, sheet_name="Sheet1").dropna(how="all")
    df = df.dropna(subset=["tensile_strength"]).dropna(subset=["cf_paper_id"])
    df = df[df["coupon_orientation"] != "vertical"]
    df = df[df["source"].isin(WHITELIST)]
    return df.reset_index(drop=True)


def norm_raster(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = str(v).strip().lower().replace("°", "").replace(" ", "").replace("±", "+-").replace("+/-", "+-")
    s = re.sub(r"^\+-", "", s)
    s = re.sub(r"^\[|\]$", "", s)
    return s or None


def num(v):
    if v is None or isinstance(v, bool):
        return np.nan if v is None else float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def cell_match(col, p, g):
    """True / False / None(GT blank -> excluded from accuracy)."""
    if col in TEXT:
        gn, pn = norm_raster(g), norm_raster(p)
        if gn is None:
            return None
        return pn == gn
    gv, pv = num(g), num(p)
    if np.isnan(gv):
        return None
    if np.isnan(pv):
        return False
    rel, ab = TOL[col]
    return abs(pv - gv) <= max(ab, rel * abs(gv))


def ident_key(row, col):
    """Hashable identity value for a column, respecting its type."""
    if col in TEXT:
        return norm_raster(row.get(col))
    v = num(row.get(col))
    return None if np.isnan(v) else v


def varying_cols(gt_rows, pred_rows=()):
    """Columns that ACTUALLY carry row identity — NO fallback. Empty means the rows are
    genuinely indistinguishable, which callers need to know; identity_cols() hides that
    behind a fallback because the matcher still needs some column list to work with.

    Includes TEXT columns. raster_angle was previously omitted because the loop ran over
    NUMERIC only, which made CF-P09 and CF-P02 look degenerate when their rows are in fact
    uniquely labelled by raster angle, and left CF-P19 with 7 distinct conditions instead
    of 12.
    """
    out = []
    for c in NUMERIC + TEXT:
        gv = {k for k in (ident_key(g, c) for g in gt_rows) if k is not None}
        pv = {k for k in (ident_key(p, c) for p in pred_rows) if k is not None}
        # Varying in GT always counts. Varying only in the PREDICTION counts ONLY if GT has
        # at least one value in that column: a column GT leaves entirely blank cannot identify
        # a GT row, and selecting it makes every distance 1.0 so nothing matches at all.
        # CF-P10 hit this -- the paper states 0 wt% (neat PEEK) and 5 wt% (CFR-PEEK) but GT is
        # blank for both, so a model that read it CORRECTLY scored matched=0 and all-None.
        if len(gv) > 1 or (len(pv) > 1 and len(gv) >= 1):
            out.append(c)
    return out


def identity_cols(gt_rows, pred_rows=()):
    """Columns that carry row identity: those varying in GT **or** in the predictions.

    Varying-in-GT gives the experimental design's real factors, so a wrong value in a
    column that is constant anyway cannot veto an otherwise perfect match.
    Varying-in-PRED is equally necessary: CF-P24's GT is all fiber_weight_fraction=5.0
    (CF arm only), but a model may also extract neat-PEEK and GF rows. Without this clause
    those rows are indistinguishable from the CF rows and get mis-assigned, scoring a
    correct extraction as wrong. Constant columns are still fully scored for cell accuracy.
    """
    vc = varying_cols(gt_rows, pred_rows)
    if not vc:
        return list(NUMERIC)
    # A categorical column alone cannot carry alignment: one wrong or null raster_angle then
    # makes EVERY pair distance 1.0, nothing matches, and the paper reports cell_acc=None --
    # which silently vanishes from a mean instead of being penalised. Keep the numeric fields
    # in the basis so a raster disagreement costs a cell, not the whole paper.
    if not any(c in NUMERIC for c in vc):
        return vc + list(NUMERIC)
    return vc


def alignment_diagnosis(gt_rows, pred_rows=()):
    """Can GT rows be told apart at all by the columns the matcher compares?

    When two GT rows share an identity tuple the Hungarian assignment between them is
    arbitrary, so per-row UTS is a coin flip dressed as a measurement. Four papers
    (CF-P04/P06/P10/P14) vary only factors outside this schema — chamber temperature,
    annealing temperature — so no column distinguishes their rows at all.

    Two distinct conditions, deliberately not conflated:
      alignment_degenerate  NO column varies at all -> every pairing is arbitrary and row_f1
                            carries no information. Only sorted UTS is meaningful.
      ambiguous_rows        SOME rows share an identity tuple. Row F1 still measures something
                            real for the rest of the paper; only the colliding subset is a
                            coin flip. Reported as a fraction so it can be footnoted, not
                            treated as a failure.
    """
    vc = varying_cols(gt_rows, pred_rows)
    cols = vc or list(NUMERIC)
    counts = {}
    for g in gt_rows:
        k = tuple(ident_key(g, c) for c in cols)
        counts[k] = counts.get(k, 0) + 1
    colliding = sum(v for v in counts.values() if v > 1)
    full = (not vc) and len(gt_rows) > 1
    return {"align_cols": ",".join(vc) if vc else "(none vary)",
            "gt_conditions": len(counts),
            "colliding_gt_rows": colliding,
            "ambiguous_row_frac": round(colliding / len(gt_rows), 3) if gt_rows else 0.0,
            "alignment_degenerate": full}


def row_distance(p, g, cols=None):
    """Record-linkage distance over CO-PRESENT fields, plus a bounded coverage penalty.

    Charging a full penalty per null would make any under-extracted row unmatchable, which
    hides real cell-level errors behind a fake 0% row recall. Alignment should answer
    "which GT row is this prediction about"; whether fields are missing is then measured
    by cell accuracy, not by refusing to align. UTS is weighted x2 as the most
    discriminative field.
    """
    # ALIGN ON INPUT PARAMETERS ONLY. Including the output (UTS) in the distance makes the
    # matcher pair rows that already agree on UTS and then score UTS as correct — circular,
    # and it manufactures near-perfect UTS accuracy from a wrong extraction.
    comparable, missing, gt_present = [], 0, 0
    for c in (cols if cols is not None else NUMERIC):
        if c in TEXT:
            # String identity: raster angle is categorical, so distance is 0 or 1. Without
            # this branch the column was silently skipped and papers distinguished only by
            # raster angle became unalignable.
            gv, pv = norm_raster(g.get(c)), norm_raster(p.get(c))
            if gv is not None:
                gt_present += 1
            if gv is None or pv is None:
                if gv is not None:
                    missing += 1
                continue
            # Weight 0.5: a categorical mismatch is all-or-nothing (1.0) whereas a numeric
            # mismatch is a bounded ratio -- nozzle_temp 400 vs 440 scores just 0.09. At equal
            # weight one raster disagreement outvotes several correct numeric fields and
            # unmatches the row, which hides the error instead of scoring it.
            comparable.append((0.5, 0.0 if pv == gv else 1.0))
            continue
        gv, pv = num(g.get(c)), num(p.get(c))
        if not np.isnan(gv):
            gt_present += 1
        if np.isnan(gv) or np.isnan(pv):
            if not np.isnan(gv):
                missing += 1
            continue
        comparable.append((1.0, min(abs(pv - gv) / max(abs(gv), 1.0), 1.0)))
    # Require 2 co-present fields normally, but only 1 when the paper's design HAS only one
    # varying factor (e.g. CF-P13 sweeps fibre wt% with everything else fixed). Demanding 2
    # unconditionally makes every single-factor paper unmatchable and scores a correct
    # extraction as F1=0.
    need = min(2, len(cols) if cols is not None else 2)
    if len(comparable) < max(need, 1):
        return 1.0
    wsum = sum(w for w, _ in comparable)
    d = sum(w * x for w, x in comparable) / wsum
    cov = (missing / gt_present) if gt_present else 0.0
    return min(d + 0.15 * cov, 1.0)


def score_one(pred_rows, gt_rows, label, cf_id=None):
    P, G = len(pred_rows), len(gt_rows)
    # GT ONLY. Degeneracy is a property of the paper's experimental design, not of the
    # prediction: passing pred_rows lets a model that hallucinates a varying column mask a
    # genuinely degenerate paper and reclaim a row_f1 that means nothing. identity_cols()
    # still sees predictions, because for MATCHING a pred-varying column is real signal.
    diag = alignment_diagnosis(gt_rows)
    pairs, mp, mg = [], set(), set()
    if P and G:
        idc = identity_cols(gt_rows, pred_rows)
        # A predicted row with NO tensile_strength is not a row at all: the task's first
        # inclusion criterion is "has a reported UTS; no UTS => not a row", and CRITICAL RULE 1
        # requires every row to carry one. Left matchable, such rows align on process parameters
        # alone and score full marks for identifying conditions while reporting no measurement --
        # CF-P11 gemma-r3 posted the paper's BEST row_f1 (0.895) with all 21 values null, beating
        # a run that read 52 rows at 47% UTS accuracy. They stay in the precision denominator
        # (they were claimed) but can never match.
        C = np.array([[(1.0 if np.isnan(num(p.get("tensile_strength")))
                        else row_distance(p, g, idc)) for g in gt_rows] for p in pred_rows])
        for i, j in zip(*linear_sum_assignment(C)):
            if C[i, j] < 0.5:
                pairs.append((i, j, C[i, j])); mp.add(i); mg.add(j)
    # CHANGE 2 -- OUT-OF-SCOPE PREDICTIONS ARE NOT HALLUCINATIONS.
    # CF-P18 demonstrated the failure: a model that transcribed all 9 of Fig. 4a's printed bar
    # labels correctly (2 in scope, 7 deliberately excluded) scored row_f1 0.364, while a model
    # returning 3 rows with values wrong by 8-13 MPa scored 0.800. Counting correctly-read but
    # curator-excluded conditions as hallucinations rewards narrowness over accuracy. Such rows
    # leave the precision denominator; they earn no credit either.
    oos_vals = (load_out_of_scope().get(cf_id) or {}).get("excluded_uts", []) if cf_id else []
    oos_hits = 0
    if oos_vals:
        rel, ab = TOL["tensile_strength"]
        for i in range(P):
            if i in mp:
                continue
            v = num(pred_rows[i].get("tensile_strength"))
            if not np.isnan(v) and any(abs(v - x) <= max(ab, rel * abs(x)) for x in oos_vals):
                oos_hits += 1
    p_eff = P - oos_hits
    prec = len(pairs)/p_eff if p_eff else 0.0
    rec = len(pairs)/G if G else 0.0
    f1 = 2*prec*rec/(prec+rec) if (prec+rec) else 0.0

    fmap = (load_findability().get(cf_id) or {}).get("cells", {}) if cf_id else {}
    ceiling = (load_findability().get(cf_id) or {}).get("ceiling")
    unanswerable = 0
    per = {c: [0, 0] for c in SCORED}
    fill = {c: [0, 0] for c in SCORED}      # [filled_when_blank, blank_cells]
    detail, errs = [], []
    for i, j, d in pairs:
        p, g = pred_rows[i], gt_rows[j]
        row = {"run": label, "gt_row": j, "match_dist": round(d, 4)}
        for c in SCORED:
            m = cell_match(c, p.get(c), g.get(c))
            row[f"{c}__pred"], row[f"{c}__gt"] = p.get(c), g.get(c)
            row[f"{c}__ok"] = "" if m is None else ("OK" if m else "MISS")
            # A GT value that appears in NO source document cannot be extracted; scoring it
            # punishes faithful models. Treat like a GT blank (excluded), but count it so the
            # per-paper ceiling is visible rather than silently absorbed.
            if m is not None and c in NUMERIC and fmap.get(str(j), {}).get(c) is False:
                unanswerable += 1
                row[f"{c}__ok"] = "UNANSWERABLE"
                continue
            if m is None:                      # GT blank -> false-fill opportunity
                fill[c][1] += 1
                filled = (norm_raster(p.get(c)) is not None) if c in TEXT else (not np.isnan(num(p.get(c))))
                fill[c][0] += int(filled)
            else:
                per[c][1] += 1; per[c][0] += int(m)
        for c in OUTPUT:
            gv, pv = num(g.get(c)), num(p.get(c))
            if not np.isnan(gv) and not np.isnan(pv) and gv:
                errs.append(abs(pv-gv)/abs(gv)*100)
        detail.append(row)

    # SET-LEVEL UTS. When GT rows collide on the identity columns, Hungarian pairs them
    # arbitrarily and per-row UTS_MAPE measures output ORDER, not extraction quality: a
    # perfect answer emitted in reverse can score worse than a uniformly wrong one. Sorting
    # both value lists removes the ordering dependence. Reported for every run so the two are
    # comparable, but only authoritative where alignment_degenerate is True — elsewhere it is
    # optimistically biased, since sorting hands the model an alignment it did not earn.
    gu = sorted(v for v in (num(g.get("tensile_strength")) for g in gt_rows) if not np.isnan(v))
    pu = sorted(v for v in (num(p.get("tensile_strength")) for p in pred_rows) if not np.isnan(v))
    serr = [abs(pu[k] - gu[k]) / abs(gu[k]) * 100 for k in range(min(len(gu), len(pu))) if gu[k]]

    tc = sum(v[0] for v in per.values()); tn = sum(v[1] for v in per.values())
    dc = sum(per[c][0] for c in NUMERIC+TEXT); dn = sum(per[c][1] for c in NUMERIC+TEXT)
    uc = sum(per[c][0] for c in OUTPUT); un = sum(per[c][1] for c in OUTPUT)
    ff = sum(v[0] for v in fill.values()); fb = sum(v[1] for v in fill.values())
    summary = {"run": label, "pred_rows": P, "gt_rows": G, "matched": len(pairs),
               "row_precision": round(prec,3), "row_recall": round(rec,3), "row_f1": round(f1,3),
               "missed_gt": G-len(mg), "hallucinated": P-len(mp),
               "cell_acc": round(tc/tn,3) if tn else None, "cells_scored": tn,
               "param_acc": round(dc/dn,3) if dn else None,
               # CHANGE 3 -- per-row UTS is withheld when no column distinguishes the GT rows:
               # the Hungarian pairing is then arbitrary, so UTS_acc/MAPE measure output ORDER
               # rather than extraction. UTS_sorted_MAPE_pct below is the order-free replacement.
               "UTS_acc": (None if diag["alignment_degenerate"]
                           else (round(uc/un,3) if un else None)),
               "UTS_MAPE_pct": (None if diag["alignment_degenerate"]
                                else (round(float(np.mean(errs)),2) if errs else None)),
               "UTS_medAPE_pct": (None if diag["alignment_degenerate"]
                                  else (round(float(np.median(errs)),2) if errs else None)),
               "false_fill_rate": round(ff/fb,3) if fb else None,
               "blank_gt_cells": fb, "falsely_filled": ff,
               "answerability_ceiling": ceiling,
               "unanswerable_cells_excluded": unanswerable,
               "out_of_scope_excluded": oos_hits,
               "pred_rows_in_scope": p_eff,
               "UTS_sorted_MAPE_pct": round(float(np.mean(serr)), 2) if serr else None,
               "UTS_metric_to_use": "sorted" if diag["alignment_degenerate"] else "per-row",
               **diag}
    colrows = [{"run": label, "column": c, "correct": per[c][0], "scored": per[c][1],
                "accuracy": round(per[c][0]/per[c][1],3) if per[c][1] else None,
                "blank_gt": fill[c][1], "falsely_filled": fill[c][0]} for c in SCORED]
    unmatched = ([{"run":label,"kind":"MISSED_GT","gt_row":j,
                   "tensile_strength":gt_rows[j].get("tensile_strength")} for j in range(G) if j not in mg] +
                 [{"run":label,"kind":"HALLUCINATED","sample_id":pred_rows[i].get("sample_id"),
                   "tensile_strength":pred_rows[i].get("tensile_strength")} for i in range(P) if i not in mp])
    return summary, colrows, detail, unmatched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", nargs="+", required=True)
    ap.add_argument("--gt", default=GT_XLSX)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    gt_all = load_gt(args.gt)
    gt_hash = hashlib.md5(Path(args.gt).read_bytes()).hexdigest()[:12]
    print(f"GT file  : {Path(args.gt).name}")
    print(f"GT md5   : {gt_hash}")
    print(f"GT loaded: {len(gt_all)} datapoints / {gt_all.cf_paper_id.nunique()} papers "
          f"(expect 232 / 23)")
    S, CA, DE, UN, PR, GR = [], [], [], [], [], []
    for f in args.pred:
        d = json.loads(Path(f).read_text())
        cid = d["cf_paper_id"]; rows = d.get("rows", [])
        label = f"{cid}__{Path(f).stem.split('__')[-1]}"
        g = gt_all[gt_all.cf_paper_id == cid]
        grows = [{k: (None if pd.isna(v) else v) for k, v in r.items()} for r in g.to_dict("records")]
        s, ca, de, un = score_one(rows, grows, label, cid)
        s["model"] = d.get("model"); s["wall_min"] = d.get("wall_clock_min")
        s["pages_viewed"] = str(d.get("pages_viewed"))
        S.append(s); CA += ca; DE += de; UN += un
        PR += [{"run": label, **r} for r in rows]
        GR += [{"cf_paper_id": cid, **r} for r in grows]
        if s["alignment_degenerate"]:
            deg = ("  [DEGENERATE: no column varies, all %d rows interchangeable; row_f1/UTS_acc "
                   "are artefacts -- use sorted MAPE %s]" % (s["gt_rows"], s["UTS_sorted_MAPE_pct"]))
        elif s["colliding_gt_rows"]:
            deg = "  [%d/%d rows ambiguous, %d conditions]" % (
                s["colliding_gt_rows"], s["gt_rows"], s["gt_conditions"])
        else:
            deg = ""
        print(f"  {label}: rows {s['pred_rows']}/{s['gt_rows']} matched={s['matched']} "
              f"F1={s['row_f1']} cell={s['cell_acc']} UTS={s['UTS_acc']} "
              f"MAPE={s['UTS_MAPE_pct']} false_fill={s['false_fill_rate']}{deg}")

    with pd.ExcelWriter(args.out, engine="openpyxl") as w:
        pd.DataFrame(S).assign(gt_file=Path(args.gt).name, gt_md5=gt_hash) \
            .to_excel(w, sheet_name="summary", index=False)
        pd.DataFrame(CA).to_excel(w, sheet_name="per_column", index=False)
        pd.DataFrame(DE).to_excel(w, sheet_name="matched_pairs", index=False)
        pd.DataFrame(PR).to_excel(w, sheet_name="predicted", index=False)
        pd.DataFrame(GR).to_excel(w, sheet_name="ground_truth", index=False)
        pd.DataFrame(UN).to_excel(w, sheet_name="unmatched", index=False)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
