#!/usr/bin/env python3
"""
PEEK-Bench agentic (multi-turn) extraction harness + timing.

Contrast with calib.py (single-pass, all page images in one prompt). Here the
model starts with only the page TEXT index and pulls page IMAGES on demand via a
tool loop, then self-verifies and submits. This (a) keeps context bounded on
32k-context local models and (b) exercises the iterative chart-reading the draft
credits for the figure-sourced accuracy gain.

Tool protocol (text, not native function-calling, for local-model robustness):
each turn the model must emit exactly ONE JSON object:
  {"tool":"view_page","page":N}              -> harness returns that page image
  {"tool":"submit","rows":[ {...}, ... ]}    -> ends the run
Optionally {"tool":"note","text":"..."} to think without spending a view.

Measures per-turn and total wall-clock, token usage, and the agentic/single-pass
ratio (the "agentic multiplier" the campaign estimate needs).

Usage:
  python agentic.py --pdf "/path/paper.pdf" --model gemma-3-27b-it \
      --max-pages 12 --max-turns 14 --single-pass-sec 486.7
"""
import argparse, json, os, re, time
from pathlib import Path

import requests
from calib import render_pages, schema_text, stream_chat  # reuse single-pass helpers

SYSTEM_AGENTIC = """You are extracting a structured process-property dataset from a paper on fused-filament-fabricated (FFF/FDM) PEEK and its composites. You work in a multi-turn loop with tools.

You are first given the TEXT of every page. Page IMAGES are NOT shown yet — request them to read charts and verify table values.

Every turn, respond with EXACTLY ONE JSON object and nothing else:
  {"tool":"view_page","page":N}            to see the image of page N (1-indexed)
  {"tool":"note","text":"..."}             to record brief reasoning (no image)
  {"tool":"submit","rows":[ {...} ]}       to finish; rows follow the schema below

Method: first locate the MAIN results table (DoE/Box-Behnken/Taguchi matrix or the
mechanical-property summary, often mid-paper) and view that page; then view every
other page with a data table or figure; read chart values off the axes carefully;
keep data series apart; RE-VIEW at least one figure you read values from to self-check.

COMPLETENESS IS CRITICAL. Extract EVERY printed-and-tested condition, not a sample.
DoE papers report many runs — often 10-30 rows in a single results table; single-factor
sweeps add more. Before submitting: (1) view the main results table(s); (2) count the
conditions reported there; (3) emit ONE row per condition. A 2-3 row submission for a
multi-condition study is a FAILURE — do not submit a partial answer.

Row rules: one row per printed-and-tested condition per sweep occurrence; repeated
baseline conditions across different sweeps are DISTINCT rows; printed table values
take precedence over chart readings; canonicalize units (MPa, GPa, %, kJ/m^2, um, C);
set value_source to table|figure|text and source_ref to the figure/table label; use
null for unreported values.

{schema}

Respond with ONLY one JSON object per turn."""


def _top_json_values(text):
    """Return substrings of top-level balanced JSON values ({...} or [...]),
    skipping brackets inside string literals."""
    vals = []
    i, n = 0, len(text)
    while i < n:
        if text[i] in "{[":
            depth = 0; instr = False; esc = False; j = i
            while j < n:
                c = text[j]
                if instr:
                    if esc: esc = False
                    elif c == "\\": esc = True
                    elif c == '"': instr = False
                else:
                    if c == '"': instr = True
                    elif c in "{[": depth += 1
                    elif c in "}]":
                        depth -= 1
                        if depth == 0:
                            vals.append(text[i:j + 1]); i = j; break
                j += 1
        i += 1
    return vals


def extract_action(text):
    """Parse a tool action from model text. Accepts the {"tool":...} protocol AND
    tolerates a bare rows array or a {"rows":[...]} object (some models emit the
    final answer directly when pushed for completeness) -> treated as submit."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text)
    for cand in reversed(_top_json_values(text)):  # prefer the last complete value
        try:
            obj = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, list):
            return {"tool": "submit", "rows": obj}
        if isinstance(obj, dict):
            if "tool" in obj:
                return obj
            if "rows" in obj:
                return {"tool": "submit", "rows": obj["rows"]}
    return None


def image_message(page):
    return {"role": "user", "content": [
        {"type": "text", "text": f"Image of page {page['idx']} (300 dpi). Read any charts/tables carefully."},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{page['b64']}"}},
    ]}


def page_text_index(pages, per_page_chars=1500):
    parts = ["PAGE TEXT INDEX (images available on request):"]
    for p in pages:
        t = p["text"].strip().replace("\n", " ")
        if len(t) > per_page_chars:
            t = t[:per_page_chars] + " ..."
        parts.append(f"\n[Page {p['idx']}] {t}")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--model", default="gemma-3-27b-it")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--max-pages", type=int, default=12)
    ap.add_argument("--max-turns", type=int, default=16)
    ap.add_argument("--max-tokens", type=int, default=8000)
    ap.add_argument("--temp", type=float, default=0.1)
    ap.add_argument("--port", type=int, default=1234)
    ap.add_argument("--schema", default=str(Path(__file__).parent / "schema.json"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "results" / "agentic_result.json"))
    ap.add_argument("--single-pass-sec", type=float, default=486.7,
                    help="measured single-pass wall-clock (s) for this model, to compute the multiplier")
    args = ap.parse_args()

    base_url = f"http://localhost:{args.port}"
    img_dir = Path(os.environ.get("CALIB_IMG_DIR", "/tmp/calib_pages"))
    img_dir.mkdir(parents=True, exist_ok=True)

    print(f"[render] {args.pdf} @ {args.dpi} dpi (max {args.max_pages} pages)", flush=True)
    pages, img_bytes, total_pages = render_pages(args.pdf, args.dpi, args.max_pages, img_dir)
    page_by_idx = {p["idx"]: p for p in pages}
    schema_txt = schema_text(args.schema)

    # resolve served model id
    try:
        ids = [m["id"] for m in requests.get(f"{base_url}/v1/models", timeout=15).json().get("data", [])]
        model = next((m for m in ids if args.model.lower() in m.lower()), args.model)
    except Exception:
        model = args.model

    messages = [
        {"role": "system", "content": SYSTEM_AGENTIC.replace("{schema}", schema_txt)},
        {"role": "user", "content": page_text_index(pages) +
         f"\n\nThe paper has {len(pages)} pages available. Begin: view the pages with data, verify, then submit."},
    ]

    turns = []
    total_s = 0.0
    total_ptok = 0
    total_ctok = 0
    submitted = None
    viewed = []
    consecutive_bad = 0
    t_run = time.perf_counter()

    for turn in range(1, args.max_turns + 1):
        r = stream_chat(base_url, model, messages, args.max_tokens, args.temp)
        dt = r["total_s"]
        total_s += dt
        u = r["usage"] or {}
        total_ptok += (u.get("prompt_tokens") or 0)
        total_ctok += (u.get("completion_tokens") or 0)
        text = r["text"]
        action = extract_action(text)
        act_kind = action.get("tool") if action else "UNPARSEABLE"
        turns.append({"turn": turn, "sec": round(dt, 1), "action": act_kind,
                      "page": (action or {}).get("page"),
                      "prompt_tok": u.get("prompt_tokens"), "completion_tok": u.get("completion_tokens")})
        print(f"[turn {turn:2d}] {dt:6.1f}s  action={act_kind}"
              f"{' page='+str(action.get('page')) if act_kind=='view_page' else ''}"
              f"  ptok={u.get('prompt_tokens')} ctok={u.get('completion_tokens')}", flush=True)

        # record assistant turn in history
        messages.append({"role": "assistant", "content": text})

        if act_kind == "submit":
            submitted = action.get("rows")
            break
        consecutive_bad = consecutive_bad + 1 if act_kind == "UNPARSEABLE" else 0
        if act_kind == "view_page":
            pg = action.get("page")
            if pg in page_by_idx:
                viewed.append(pg)
                messages.append(image_message(page_by_idx[pg]))
            else:
                messages.append({"role": "user", "content": f"Page {pg} is out of range (1-{len(pages)}). Choose a valid page or submit."})
        elif act_kind == "note":
            messages.append({"role": "user", "content": "Noted. Continue: view another page or submit."})
        else:
            if consecutive_bad >= 2:
                print(f"[abort] {consecutive_bad} consecutive unparseable responses; stopping loop", flush=True)
                break
            messages.append({"role": "user", "content": "Reply with EXACTLY ONE JSON value: {\"tool\":\"view_page\",\"page\":N}, {\"tool\":\"note\",\"text\":\"...\"}, or {\"tool\":\"submit\",\"rows\":[...]} (a bare rows array is also accepted). No prose."})
    else:
        print(f"[warn] hit max_turns={args.max_turns} without submit", flush=True)

    wall = time.perf_counter() - t_run
    n_rows = len(submitted) if isinstance(submitted, list) else None
    mult = wall / args.single_pass_sec if args.single_pass_sec else None

    out = {
        "model": model, "pdf": os.path.basename(args.pdf), "pages_used": len(pages),
        "max_turns": args.max_turns, "turns_used": len(turns),
        "pages_viewed": viewed, "distinct_pages_viewed": sorted(set(viewed)),
        "submitted_rows": n_rows, "submitted_ok": submitted is not None,
        "total_model_s": round(total_s, 1), "wall_clock_s": round(wall, 1),
        "wall_clock_min": round(wall / 60, 2),
        "total_prompt_tokens": total_ptok, "total_completion_tokens": total_ctok,
        "single_pass_sec": args.single_pass_sec,
        "agentic_multiplier": round(mult, 2) if mult else None,
        "per_turn": turns,
        "submitted_preview": (json.dumps(submitted)[:1500] if submitted is not None else None),
        "submitted_full": submitted,  # REQUIRED for scoring — never truncate the prediction
        "raw_last_text": (messages[-1]["content"] if isinstance(messages[-1].get("content"), str) else None),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))

    print("\n===================== AGENTIC RESULT =====================")
    for k in ["model", "turns_used", "distinct_pages_viewed", "submitted_rows",
              "submitted_ok", "total_model_s", "wall_clock_min",
              "total_prompt_tokens", "total_completion_tokens",
              "single_pass_sec", "agentic_multiplier"]:
        print(f"  {k:26s}: {out[k]}")
    print("==========================================================")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
