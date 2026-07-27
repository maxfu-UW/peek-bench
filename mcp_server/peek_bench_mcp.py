#!/usr/bin/env python3
"""PEEK-Bench MCP server — serve the corpus and score submissions WITHOUT exposing ground truth.

Why this exists
---------------
The benchmark harness is bespoke Python driving a local LM Studio endpoint, which makes the
benchmark hard to run against anything else and forces the ground truth to sit on the same machine
as the model. Serving it over MCP fixes both:

  * ANY MCP-capable agent can be evaluated on identical tooling.
  * `submit_extraction` scores server-side and returns METRICS ONLY. Ground truth never reaches the
    client, so a held-out split can be published rather than spent.

Tools
-----
  list_papers()                    corpus + page counts + split (no answers)
  get_paper_text(cf_id, page=None) text layer, whole paper or one page
  get_page_image(cf_id, page)      PNG of one page at native resolution
  get_answerability(cf_id)         per-paper ceiling, so a 0.75 reads as "at ceiling"
  submit_extraction(cf_id, rows)   score against GT, return metrics only
  get_scope_note(cf_id)            per-paper scope note, if one exists

Design notes that came out of the benchmark itself
--------------------------------------------------
  * Images are returned at NATIVE resolution and the client downsamples. The headline finding is
    about what survives downsampling, so the server must not pre-degrade them.
  * Scope notes travel with the paper, not in a separate prompt, so a scored run always used the
    scope the scorer assumes.
  * Every submission is logged with a hash of the rows. Unlimited scored submissions turn a
    held-out split into a training signal; the log makes that visible.

Run
---
  export PEEKBENCH_ROOT=/path/to/peek_bench_2026
  python mcp/peek_bench_mcp.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

import fitz
import pandas as pd
from mcp.server.fastmcp import FastMCP, Image

ROOT = Path(os.environ.get("PEEKBENCH_ROOT", Path(__file__).resolve().parent.parent.parent))
CAMPAIGN = ROOT / "campaign"
PAPERS_DIR = ROOT / "group_truth_excel_file" / "P2-data-source-papers"
SPLITS = ROOT / "splits" / "splits_v3_dev_test.json"
SUBMIT_LOG = CAMPAIGN / "mcp_submissions.jsonl"

mcp = FastMCP("peek-bench")

_spec = importlib.util.spec_from_file_location("score10", CAMPAIGN / "score10.py")
S10 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S10)

_INDEX = {p["cf_paper_id"]: p for p in
          json.loads((PAPERS_DIR / "SUPPLEMENTARY-INDEX.json").read_text())["papers"]}
_SPLIT = {}
if SPLITS.exists():
    _s = json.loads(SPLITS.read_text())
    for name in ("dev", "test"):
        for e in _s.get(name, []):
            _SPLIT[e["id"]] = name

_gt_cache = None
_doc_cache: dict[str, fitz.Document] = {}


def _gt():
    global _gt_cache
    if _gt_cache is None:
        _gt_cache = S10.load_gt()
    return _gt_cache


def _doc(cf_id: str) -> fitz.Document:
    if cf_id not in _doc_cache:
        rec = _INDEX.get(cf_id)
        if rec is None:
            raise ValueError(f"unknown cf_paper_id {cf_id!r}")
        _doc_cache[cf_id] = fitz.open(PAPERS_DIR / rec["use_document"])
    return _doc_cache[cf_id]


def _gt_rows(cf_id: str) -> list[dict]:
    g = _gt()[_gt().cf_paper_id == cf_id]
    return [{k: (None if pd.isna(v) else v) for k, v in r.items()} for r in g.to_dict("records")]


@mcp.tool()
def list_papers() -> dict:
    """Every paper in the corpus with its page count and split. Contains NO answers."""
    out = []
    for cid in sorted(_INDEX):
        try:
            n = _doc(cid).page_count
        except Exception:
            n = None
        out.append({"cf_paper_id": cid, "pages": n, "split": _SPLIT.get(cid),
                    "has_supplementary": bool(_INDEX[cid].get("si_pdf") or _INDEX[cid].get("si_docx")),
                    "document": _INDEX[cid]["use_document"]})
    return {"count": len(out), "papers": out}


@mcp.tool()
def get_paper_text(cf_id: str, page: int | None = None) -> dict:
    """Text layer of a paper. Omit `page` for the whole document, or pass a 1-indexed page.

    Note: many tensile values in this corpus are NOT in the text layer — they exist only as labels
    inside raster figures. Text alone is not sufficient; use get_page_image for results figures.
    """
    d = _doc(cf_id)
    if page is None:
        txt = "".join(f"\n===== PAGE {i + 1} =====\n{d.load_page(i).get_text()}"
                      for i in range(d.page_count))
        return {"cf_paper_id": cf_id, "pages": d.page_count, "text": txt}
    if not 1 <= page <= d.page_count:
        raise ValueError(f"page {page} out of range 1..{d.page_count}")
    return {"cf_paper_id": cf_id, "page": page, "pages": d.page_count,
            "text": d.load_page(page - 1).get_text()}


@mcp.tool()
def get_page_image(cf_id: str, page: int, dpi: int = 150) -> Image:
    """PNG of one page, 1-indexed, at native resolution by default.

    Deliberately NOT pre-downsampled: how much detail survives downsampling is the effect this
    benchmark measures, so that choice belongs to the client.
    """
    d = _doc(cf_id)
    if not 1 <= page <= d.page_count:
        raise ValueError(f"page {page} out of range 1..{d.page_count}")
    pix = d.load_page(page - 1).get_pixmap(dpi=max(72, min(dpi, 400)))
    return Image(data=pix.tobytes("png"), format="png")


@mcp.tool()
def get_scope_note(cf_id: str) -> dict:
    """Per-paper scope note, if the curator narrowed what counts for this paper. Usually empty."""
    f = CAMPAIGN / "paper_scope.json"
    note = (json.loads(f.read_text()).get("scopes") or {}).get(cf_id) if f.exists() else None
    return {"cf_paper_id": cf_id, "scope_note": note}


@mcp.tool()
def get_answerability(cf_id: str) -> dict:
    """Per-paper answerability ceiling: what fraction of GT parameter cells appear in the document.

    Lets a score of 0.75 be read as "at ceiling" rather than "the model failed". Returns the
    fraction only — never which cells.
    """
    f = CAMPAIGN / "findability.json"
    m = (json.loads(f.read_text()).get(cf_id) or {}) if f.exists() else {}
    return {"cf_paper_id": cf_id, "ceiling": m.get("ceiling"),
            "param_cells": m.get("param_cells"), "findable": m.get("findable")}


@mcp.tool()
def submit_extraction(cf_id: str, rows: list[dict]) -> dict:
    """Score an extraction against ground truth and return METRICS ONLY.

    Ground truth never leaves the server: no GT values, no per-cell verdicts, no indication of which
    rows matched. That is what allows a held-out split to be evaluated without being consumed.

    `rows`: one object per printed-and-tested condition, using the schema field names.
    """
    gt_rows = _gt_rows(cf_id)
    if not gt_rows:
        raise ValueError(f"no ground truth for {cf_id!r}")
    summary, _, _, _ = S10.score_one(rows, gt_rows, f"{cf_id}__mcp", cf_id)

    payload = json.dumps(rows, sort_keys=True, default=str)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "cf_paper_id": cf_id,
           "n_rows": len(rows), "rows_sha256": hashlib.sha256(payload.encode()).hexdigest()[:16],
           "row_f1": summary.get("row_f1"), "cell_acc": summary.get("cell_acc")}
    with SUBMIT_LOG.open("a") as fh:
        fh.write(json.dumps(rec) + "\n")

    keep = ("pred_rows", "gt_rows", "matched", "row_precision", "row_recall", "row_f1",
            "cell_acc", "cells_scored", "param_acc", "UTS_acc", "UTS_MAPE_pct",
            "UTS_sorted_MAPE_pct", "UTS_metric_to_use", "false_fill_rate",
            "answerability_ceiling", "alignment_degenerate", "ambiguous_row_frac",
            "gt_conditions", "out_of_scope_excluded")
    metrics = {k: summary.get(k) for k in keep if k in summary}
    metrics["_note"] = ("Metrics only — ground-truth values are never returned. "
                        "Submissions are logged; repeated scored submissions on a held-out "
                        "split turn it into a training signal.")
    return metrics


if __name__ == "__main__":
    mcp.run()
