#!/usr/bin/env python3
"""
PEEK-Bench single-pass timing calibration.

Renders one paper PDF to page images (dpi configurable), builds a realistic
single-pass extraction prompt (55-col schema + page text + page images), sends
it to a locally served vision LLM via the LM Studio OpenAI-compatible API with
streaming, and measures:

  - model + input sizing (pages, prompt tokens, image bytes)
  - TTFT (prefill wall-clock, ~= time to first token)
  - decode throughput (tokens/s) and completion length
  - total per-paper wall-clock

then projects the full benchmark loop (1 repeat, 10 test papers, single-pass +
agentic) so the synthetic per-paper estimates in the draft can be replaced with
a measured anchor.

Usage:
  python calib.py --pdf "/path/to/paper.pdf" --model gemma-3-27b-it
  python calib.py --pdf ... --model qwen3-vl-30b-a3b-thinking --max-pages 14

Requires: PyMuPDF (fitz), Pillow, requests, and an LM Studio server running with
the target model loaded (lms server start; lms load <model> --context-length N).
"""
import argparse, base64, io, json, os, sys, time, statistics
from pathlib import Path

import requests
import fitz  # PyMuPDF
from PIL import Image


def render_pages(pdf_path, dpi, max_pages, img_dir, jpeg_quality=85):
    """Render pages to JPEG (smaller payload than PNG for photos/charts) + extract text."""
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    n = total_pages if max_pages in (0, None) else min(max_pages, total_pages)
    pages = []
    total_img_bytes = 0
    for i in range(n):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=jpeg_quality)
        data = buf.getvalue()
        total_img_bytes += len(data)
        b64 = base64.b64encode(data).decode()
        text = page.get_text("text")
        (img_dir / f"page_{i+1:02d}.jpg").write_bytes(data)
        pages.append({"idx": i + 1, "w": pix.width, "h": pix.height,
                      "b64": b64, "text": text})
    doc.close()
    return pages, total_img_bytes, total_pages


def schema_text(schema_path):
    cols = json.loads(Path(schema_path).read_text())["columns"]
    lines = [f"{c['name']} [{c.get('unit','')}] ({c.get('type','')}) - {c.get('note', c.get('type_note',''))}".rstrip(" -")
             for c in cols]
    return f"SCHEMA ({len(cols)} columns), one row per printed-and-tested condition:\n" + "\n".join(lines)


SYSTEM_PROMPT = """You are extracting a structured process-property dataset from a PDF of a paper on fused-filament-fabricated (FFF/FDM) PEEK and its composites.

Output: JSON array of row objects under the schema below. One row per printed-and-tested condition per sweep occurrence. Fill every applicable parameter and property column; use null for values the paper does not report.

Conventions (part of the task):
- Repeated baseline conditions that appear in different sweeps are DISTINCT rows.
- Printed table values take precedence over chart readings of the same quantity.
- Canonicalize units: MPa (strength), GPa (modulus), % (elongation/crystallinity), kJ/m^2 (impact), um (roughness), C (temperature).
- For each value set value_source to 'table', 'figure', or 'text' and source_ref to the figure/table label.
- Keep data series apart; read values off chart axes carefully.

{schema}

Respond with ONLY the JSON array."""


def build_messages(pages, schema_txt, k_example_note=True):
    sys_msg = {"role": "system", "content": SYSTEM_PROMPT.format(schema=schema_txt)}
    content = []
    intro = ("Extract all datapoints from this paper. Page images follow, each "
             "preceded by its extracted text layer. Use the images to read charts "
             "and verify table values.\n")
    if k_example_note:
        intro += ("(A curated few-shot example pool is used in production; this "
                  "calibration run omits it, so real prompts are somewhat larger.)\n")
    content.append({"type": "text", "text": intro})
    for p in pages:
        txt = p["text"].strip()
        if len(txt) > 3500:
            txt = txt[:3500] + " ...[truncated]"
        content.append({"type": "text", "text": f"\n--- PAGE {p['idx']} TEXT ---\n{txt}\n--- PAGE {p['idx']} IMAGE ---"})
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{p['b64']}"}})
    return [sys_msg, {"role": "user", "content": content}]


def resolve_model(base_url, requested):
    try:
        r = requests.get(f"{base_url}/v1/models", timeout=15)
        ids = [m["id"] for m in r.json().get("data", [])]
    except Exception as e:
        print(f"[warn] could not list models: {e}", file=sys.stderr)
        return requested, []
    if not ids:
        return requested, ids
    for mid in ids:
        if requested.lower() in mid.lower() or mid.lower() in requested.lower():
            return mid, ids
    return ids[0], ids  # fall back to whatever is loaded


def stream_chat(base_url, model, messages, max_tokens, temperature):
    payload = {"model": model, "messages": messages, "temperature": temperature,
               "max_tokens": max_tokens, "stream": True,
               "stream_options": {"include_usage": True}}
    t0 = time.perf_counter()
    ttft = None
    ntok_seen = 0
    text_parts = []
    reason_parts = []
    usage = None
    with requests.post(f"{base_url}/v1/chat/completions", json=payload,
                       stream=True, timeout=(30, 3600)) as resp:
        resp.raise_for_status()
        for raw in resp.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8", "ignore")
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            if chunk.get("usage"):
                usage = chunk["usage"]
            for ch in chunk.get("choices", []):
                delta = ch.get("delta", {}) or {}
                # Reasoning models (e.g. Nemotron-*-Reasoning) stream thinking tokens on a
                # SEPARATE channel. Capturing only `content` makes them look like they
                # produced nothing, when in fact they exhausted max_tokens thinking.
                think = delta.get("reasoning_content") or delta.get("reasoning")
                if think:
                    reason_parts.append(think)
                piece = delta.get("content")
                if piece:
                    if ttft is None:
                        ttft = time.perf_counter() - t0
                    ntok_seen += 1
                    text_parts.append(piece)
    t_end = time.perf_counter() - t0
    return {"ttft_s": ttft, "total_s": t_end, "text": "".join(text_parts),
            "reasoning": "".join(reason_parts),
            "stream_chunks": ntok_seen, "usage": usage}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--model", default="gemma-3-27b-it")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--max-pages", type=int, default=0, help="0 = all pages")
    ap.add_argument("--max-tokens", type=int, default=4000)
    ap.add_argument("--temp", type=float, default=0.1)
    ap.add_argument("--port", type=int, default=1234)
    ap.add_argument("--schema", default=str(Path(__file__).parent / "schema.json"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "results" / "calib_result.json"))
    ap.add_argument("--agentic-mult", type=float, default=4.0,
                    help="assumed agentic/single-pass wall-clock ratio (until agentic harness exists)")
    ap.add_argument("--n-test-papers", type=int, default=10)
    ap.add_argument("--repeats", type=int, default=1)
    args = ap.parse_args()

    base_url = f"http://localhost:{args.port}"
    img_dir = Path(os.environ.get("CALIB_IMG_DIR", "/tmp/calib_pages"))
    img_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] rendering {args.pdf} @ {args.dpi} dpi ...", flush=True)
    t = time.perf_counter()
    pages, img_bytes, pdf_pages = render_pages(args.pdf, args.dpi, args.max_pages, img_dir)
    print(f"      {len(pages)} pages rendered ({img_bytes/1e6:.1f} MB jpeg) in {time.perf_counter()-t:.1f}s", flush=True)

    schema_txt = schema_text(args.schema)
    messages = build_messages(pages, schema_txt)

    model, all_ids = resolve_model(base_url, args.model)
    print(f"[2/4] server models: {all_ids}", flush=True)
    print(f"      using model id: {model}", flush=True)

    print(f"[3/4] sending single-pass request (max_tokens={args.max_tokens}, temp={args.temp}) ...", flush=True)
    r = stream_chat(base_url, model, messages, args.max_tokens, args.temp)

    usage = r["usage"] or {}
    ptok = usage.get("prompt_tokens")
    ctok = usage.get("completion_tokens") or r["stream_chunks"]
    ttft = r["ttft_s"] or float("nan")
    total = r["total_s"]
    decode_s = max(total - ttft, 1e-6)
    prefill_tps = (ptok / ttft) if (ptok and ttft) else None
    decode_tps = (ctok / decode_s) if ctok else None

    # projection: (single_pass + agentic) * n_papers * repeats, this model only
    sp = total
    ag = total * args.agentic_mult
    per_model_loop_min = (sp + ag) * args.n_test_papers * args.repeats / 60.0

    out = {
        "model": model, "pdf": os.path.basename(args.pdf), "pdf_pages_total": pdf_pages,
        "pages_used": len(pages), "dpi": args.dpi, "image_mb": round(img_bytes/1e6, 2),
        "prompt_tokens": ptok, "completion_tokens": ctok,
        "ttft_s": round(ttft, 2), "total_s": round(total, 2),
        "prefill_tok_per_s": round(prefill_tps, 1) if prefill_tps else None,
        "decode_tok_per_s": round(decode_tps, 2) if decode_tps else None,
        "sec_per_page_prefill": round(ttft/len(pages), 2),
        "single_pass_min": round(sp/60, 2),
        "assumed_agentic_min": round(ag/60, 2),
        "assumed_agentic_mult": args.agentic_mult,
        "projected_loop_min_this_model": round(per_model_loop_min, 1),
        "n_test_papers": args.n_test_papers, "repeats": args.repeats,
        "output_preview": r["text"][:800],
        "output_full": r["text"],  # REQUIRED for scoring — never truncate the prediction
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))

    print("\n===================== CALIBRATION RESULT =====================")
    for k in ["model", "pages_used", "pdf_pages_total", "dpi", "image_mb",
              "prompt_tokens", "completion_tokens", "ttft_s",
              "prefill_tok_per_s", "decode_tok_per_s", "sec_per_page_prefill",
              "total_s", "single_pass_min", "assumed_agentic_min",
              "projected_loop_min_this_model"]:
        print(f"  {k:32s}: {out[k]}")
    print("==============================================================")
    print(f"[4/4] wrote {args.out}")
    print("\n--- output preview (first 800 chars) ---")
    print(out["output_preview"])


if __name__ == "__main__":
    main()
