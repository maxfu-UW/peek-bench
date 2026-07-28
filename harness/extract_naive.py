#!/usr/bin/env python3
"""
PEEK-Bench extraction — 9 FFF process parameters + UTS, keyed on cf_paper_id.

Agentic multi-turn harness: the model gets every page's text up front and pulls
page IMAGES on demand, so context stays bounded and chart reading is iterative.

The GT inclusion criteria are stated in the prompt so the task is well-posed
(otherwise a correct extractor is penalised for rows the curator excluded).

Usage:
  python extract10.py --cf-id CF-P05 --pdf ".../Bashir-2025-....pdf" \
      --model gemma-3-27b-it --out results10/CF-P05__gemma.json
"""
import argparse, json, os, re, sys, time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "calibration"))
from calib import render_pages, stream_chat                       # noqa: E402
from agentic import extract_action, page_text_index, _top_json_values               # noqa: E402


def full_text_index(pages, budget_chars=90000):
    """Serve the COMPLETE text of every page up front.

    Text is ~1 token per 4 chars; a page IMAGE costs 256 (Gemma) to ~2900 (Qwen3-VL) tokens.
    So full text is cheap and images are what must stay on-demand. The previous 1500-char
    per-page cap was silently hiding the methods/setup section, where the FIXED process
    parameters (nozzle diameter, fibre wt%, platform temp, specimen thickness) are stated
    once — both models scored 0/18 on exactly those columns because they never navigated
    there. Fixing this in the harness applies uniformly to every system, unlike a prompt
    instruction, which we measured to be model-dependent.
    """
    total = sum(len(p["text"]) for p in pages)
    per = None if total <= budget_chars else max(1500, budget_chars // max(len(pages), 1))
    out = ["FULL TEXT OF EVERY PAGE (page images available on request via view_page):"]
    for p in pages:
        t = p["text"].strip()
        if per and len(t) > per:
            t = t[:per] + " ...[truncated]"
        out.append(f"\n===== PAGE {p['idx']} =====\n{t}")
    return "\n".join(out)


def view_message(page):
    """Return FULL page text + the page image.

    Critical: the up-front index truncates each page to ~1500 chars, which cuts off large
    results tables. And Gemma-3 encodes any image as a fixed 256 tokens (896x896), so a
    journal page is unreadable as an image. Serving the untruncated text layer with the
    image is what makes table transcription possible at all; the image still carries the
    charts, which is where models with dynamic image tokenisation (e.g. Qwen3-VL) win.
    """
    return {"role": "user", "content": [
        {"type": "text", "text": f"--- FULL TEXT OF PAGE {page['idx']} ---\n{page['text']}\n"
                                 f"--- IMAGE OF PAGE {page['idx']} (read charts/axes here) ---"},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{page['b64']}"}},
    ]}

SYSTEM = """I'm building a dataset of 3D printing process parameters and mechanical properties from research papers.

Please read this paper and extract the printing conditions and their measured tensile strength. Give me one row per condition tested, as a table with these columns:

  nozzle_diameter (mm)
  nozzle_temp (C)
  printing_speed (mm/s)
  fiber_weight_fraction (wt%)
  raster_angle (deg)
  infill_percentage (%)
  specimen_thickness (mm)
  layer_thickness (mm)
  platform_temp (C)
  tensile_strength (MPa)

Use null if a value isn't given. Return the rows as JSON.

You are given the TEXT of every page. To see a page IMAGE, respond with {"tool":"view_page","page":N}.
Respond with EXACTLY ONE JSON object per turn:
  {"tool":"view_page","page":N}
  {"tool":"note","text":"..."}
  {"tool":"submit","rows":[ {...} ]}

cf_paper_id is given below - copy it into every row."""


def paper_scope_block(cf_id):
    """Paper-specific scope note, or empty string. See paper_scope.json for why this exists and
    what it costs: a paper carrying a note does not see the same prompt as the rest of the corpus."""
    f = Path(__file__).parent / "paper_scope.json"
    if not f.exists():
        return ""
    note = (json.loads(f.read_text()).get("scopes") or {}).get(cf_id)
    if not note:
        return ""
    return "\nPAPER-SPECIFIC SCOPE (overrides nothing above; narrows what counts for THIS paper):\n  * " + note + "\n"


def schema_block(path):
    """Render the schema so the JSON KEY is unambiguous.

    Units must never appear inside the key: writing `tensile_strength [MPa]` makes models
    emit that whole string as the key, which silently breaks every downstream lookup.
    """
    s = json.loads(Path(path).read_text())
    lines = []
    for c in s["columns"]:
        t = {"str": "string", "float": "number", "int": "number"}.get(c["type"], c["type"])
        u = f"unit={c['unit']}. " if c.get("unit") else ""
        n = c.get("note", "")
        lines.append(f'  "{c["name"]}": {t}   // {u}{n}')
    keys = ", ".join(f'"{c["name"]}"' for c in s["columns"])
    return ("SCHEMA — every row object must use EXACTLY these JSON keys, spelled exactly as shown.\n"
            "Do NOT append units or types to the key names.\n" + "\n".join(lines) +
            f"\n\nThe key set for every row is exactly: {keys}")


COMMENT_RE = re.compile(r'//[^\n"]*')
EXPR_RE = re.compile(r'(?<=:)\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)')


def sanitize_json_text(t):
    """Repair the malformations models actually emit before JSON parsing.

    Observed: `"printing_speed": 20/60,  // mm/s` — a JS comment plus an unevaluated expression,
    both invalid JSON, which discarded an otherwise perfect extraction. The prompt is fixed too,
    but tolerate it here so no other model loses data the same way.
    """
    if not t:
        return t
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    t = COMMENT_RE.sub("", t)
    def _ev(m):
        try:
            return " " + f"{float(m.group(1)) / float(m.group(2)):.6g}"
        except Exception:
            return m.group(0)
    t = EXPR_RE.sub(_ev, t)
    t = re.sub(r",(\s*[}\]])", r"\1", t)
    return t


UNIT_SUFFIX = re.compile(r"\s*[\[(].*?[\])]\s*$")


def normalise_keys(rows, schema_path):
    """Strip any '[unit]' suffix a model appends to keys and map onto canonical names."""
    valid = [c["name"] for c in json.loads(Path(schema_path).read_text())["columns"]]
    lut = {v.lower(): v for v in valid}
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        fixed = {}
        for k, v in r.items():
            base = UNIT_SUFFIX.sub("", str(k)).strip().lower()
            fixed[lut.get(base, k)] = v
        out.append({v: fixed.get(v) for v in valid})
    return out



SCHEMA_KEYS = None


def parse_action(text, schema_path):
    """extract_action + tolerance for models that stream ONE BARE ROW per turn.

    Nemotron (and Gemma under long context) sometimes emit a naked row object with no
    {"tool":"submit","rows":[...]} wrapper. That is correct data in the wrong envelope;
    discarding it as UNPARSEABLE loses real extractions. Recognise it and accumulate.
    """
    global SCHEMA_KEYS
    if SCHEMA_KEYS is None:
        SCHEMA_KEYS = {c["name"] for c in json.loads(Path(schema_path).read_text())["columns"]}
    act = extract_action(text)
    if act is not None:
        return act
    cleaned = sanitize_json_text(re.sub(r"<think>.*?</think>", "", text or "", flags=re.S))
    for cand in _top_json_values(cleaned):
        try:
            obj = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            hit = SCHEMA_KEYS & {UNIT_SUFFIX.sub("", str(k)).strip() for k in obj}
            if len(hit) >= 4:                    # looks like a data row, not an action
                return {"tool": "row", "row": obj}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cf-id", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--schema", default=str(Path(__file__).parent / "schema10.json"))
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--max-turns", type=int, default=0, help="0 = auto, scales with pages")
    ap.add_argument("--max-tokens", type=int, default=16000)
    ap.add_argument("--temp", type=float, default=0.1)
    ap.add_argument("--port", type=int, default=1234)
    args = ap.parse_args()

    base = f"http://localhost:{args.port}"
    img_dir = Path("/tmp") / f"pb10_{args.cf_id}"
    img_dir.mkdir(parents=True, exist_ok=True)
    pages, _mb, _tot = render_pages(args.pdf, args.dpi, 0, img_dir)
    by_idx = {p["idx"]: p for p in pages}
    if not args.max_turns:
        # Sequential browsers spend ~2 turns/page (view + note). A fixed 14 starved the 21-page
        # WITH-SI document into zero-row runs; scale the budget with document length instead.
        args.max_turns = max(14, min(36, len(pages) + 10))
    print(f"[render] {args.cf_id} {len(pages)} pages | max_turns={args.max_turns}", flush=True)

    try:
        ids = [m["id"] for m in requests.get(f"{base}/v1/models", timeout=15).json().get("data", [])]
        model = next((m for m in ids if args.model.lower() in m.lower()), args.model)
    except Exception:
        model = args.model

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": full_text_index(pages) +
         f"\n\n===== END OF PAPER TEXT =====\n"
         f"cf_paper_id = \"{args.cf_id}\"   ({len(pages)} pages)\n"
         f"Fixed parameters are in the methods text above. View page IMAGES only for the tensile\n"
         f"results tables/figures, reading chart values off the axes.\n"
         f"PROTOCOL REMINDER: reply with EXACTLY ONE JSON object per turn -\n"
         '  {"tool":"view_page","page":N} | {"tool":"note","text":"..."} | {"tool":"submit","rows":[...]}\n'
         f"Never emit a bare row object. When finished, put ALL conditions in ONE submit call."},
    ]

    turns, viewed, bad, total_bad, submitted = [], [], 0, 0, None
    streamed = []
    raw_bad = []
    t0 = time.perf_counter()
    for turn in range(1, args.max_turns + 1):
        r = stream_chat(base, model, messages, args.max_tokens, args.temp)
        u = r["usage"] or {}
        # Some reasoning models emit <think>...</think> inline in `content` rather than on
        # the reasoning channel; strip it so the JSON action can be found.
        clean = re.sub(r"<think>.*?</think>", "", r["text"], flags=re.S)
        clean = re.sub(r"^.*?</think>", "", clean, flags=re.S) if "</think>" in clean else clean
        act = parse_action(sanitize_json_text(clean), args.schema)
        kind = act.get("tool") if act else "UNPARSEABLE"
        turns.append({"turn": turn, "sec": round(r["total_s"], 1), "action": kind,
                      "page": (act or {}).get("page"), "ctok": u.get("completion_tokens"),
                      "reasoning_chars": len(r.get("reasoning") or "")})
        print(f"[turn {turn:2d}] {r['total_s']:6.1f}s {kind}"
              f"{' p'+str(act.get('page')) if kind=='view_page' else ''} ctok={u.get('completion_tokens')}",
              flush=True)
        messages.append({"role": "assistant", "content": r["text"]})
        if kind == "row":
            streamed.append(act["row"])
            messages.append({"role": "user", "content":
                             "Row recorded. Continue with the next condition, or call submit "
                             "with ALL remaining rows."})
            bad = 0
            continue
        if kind == "submit":
            submitted = normalise_keys(act.get("rows"), args.schema)
            if streamed:      # merge any rows streamed individually before the submit
                submitted = normalise_keys(streamed, args.schema) + (submitted or [])
            break
        if kind == "UNPARSEABLE":
            bad += 1; total_bad += 1; raw_bad.append(r["text"][:600])
        else:
            bad = 0
        if kind == "view_page":
            pg = act.get("page")
            if pg in by_idx:
                viewed.append(pg); messages.append(view_message(by_idx[pg]))
            else:
                messages.append({"role": "user", "content": f"Page {pg} out of range (1-{len(pages)})."})
        elif kind == "note":
            messages.append({"role": "user", "content": "Noted. Continue: view another page or submit."})
        else:
            if bad >= 2 or total_bad >= 4:
                print(f"[abort] unparseable: {bad} consecutive / {total_bad} total", flush=True); break
            messages.append({"role": "user", "content":
                'Reply with EXACTLY ONE JSON object: {"tool":"view_page","page":N}, '
                '{"tool":"note","text":"..."} or {"tool":"submit","rows":[...]}. No prose.'})

    if submitted is None and streamed:
        submitted = normalise_keys(streamed, args.schema)
        print(f"[recovered] {len(submitted)} streamed rows without a submit", flush=True)
    wall = time.perf_counter() - t0
    out = {"cf_paper_id": args.cf_id, "model": model, "pages": len(pages),
           "pages_viewed": sorted(set(viewed)), "turns": turns, "turns_used": len(turns),
           "wall_clock_min": round(wall / 60, 2),
           "n_rows": len(submitted) if isinstance(submitted, list) else 0,
           "submitted_ok": isinstance(submitted, list), "unparseable_turns": total_bad,
           "reasoning_chars_total": sum(t.get("reasoning_chars", 0) for t in turns),
           "raw_unparseable": raw_bad, "rows": submitted or []}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\n[done] {args.cf_id} {model}: rows={out['n_rows']} viewed={out['pages_viewed']} "
          f"{out['wall_clock_min']} min -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
