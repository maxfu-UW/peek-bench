# Running PEEK-Bench on another machine

Everything in this repo is the harness, scorer and results. **The corpus PDFs and the ground-truth
spreadsheet are not published** — they are the curated research dataset. You need both from Max to
reproduce a run.

## 1. What you need that is not in this repo

| | what | where it goes |
|---|---|---|
| **Ground truth** | `PEEK2-CF-main-*-peekbench-v*.xlsx` | any directory; point `PEEKBENCH_GT_DIR` at it |
| **Source PDFs** | 23 paper PDFs + `SUPPLEMENTARY-INDEX.json` | a `P2-data-source-papers/` directory |
| **Splits** | `splits_v3_dev_test.json` | referenced by the sweep runner |

The scorer resolves the **highest-versioned** GT file automatically and prints the filename and MD5
on every run. Check that hash matches Max's — a stale ground truth fails as *plausible numbers*
rather than as an error, which is the worst failure mode for a benchmark.

## 2. Hardware and serving

Reference runs are on an **Apple M4 Pro, 64 GB unified memory**, models served by **LM Studio** on
its OpenAI-compatible endpoint at `127.0.0.1:1234`. Any OpenAI-compatible server works; the harness
only needs `/v1/chat/completions` with image support.

```bash
lms server start
lms load gemma-3-27b-it                        --context-length 40960 --gpu max -y
lms load mistral-small-3.1-24b-instruct-2503   --context-length 65536 --gpu max -y   # see note
lms load qwen3-vl-32b-instruct                 --context-length 65536 --gpu max -y
```

> **Context note.** The published sweep ran Mistral at **32,768**, and three runs failed on the
> longest papers because a 23-page document plus two page images consumes ~72 % of that budget
> before generation. Use **65,536** for Mistral. Its published numbers are a floor, not its
> capability.

64 GB is comfortable for one model at a time. The runners load one model, sweep all papers, then
unload — 3 loads instead of 39.

## 3. Python environment

```bash
pip install requests pymupdf pandas numpy scipy openpyxl matplotlib python-docx
```

## 4. A single extraction

```bash
export PEEKBENCH_GT_DIR=/path/to/ground_truth
python harness/extract10.py \
  --cf-id CF-P05 \
  --pdf "/path/to/P2-data-source-papers/Bashir-2025-....pdf" \
  --model gemma-3-27b-it \
  --max-tokens 16000 \
  --out results/CF-P05__gemma-r1.json
```

`--max-turns` defaults to `0` = auto, computing `clamp(pages + 10, 14, 36)`. Do not pin it; a fixed
budget starved long documents and produced zero-row runs.

## 5. The full dev-13 sweep

```bash
export PEEKBENCH_ROOT=/path/to/peek_bench_2026     # holds group_truth_excel_file/ and splits/
export PEEKBENCH_GT_DIR=$PEEKBENCH_ROOT/group_truth_excel_file
nohup caffeinate -i ./runners/dev13_sweep.sh &     # 117 runs, ~11 h on an M4 Pro
python runners/progress.py                          # live progress + metrics, safe to run any time
```

`progress.py` scores completed runs on the fly (no GPU) and prints per-model and per-paper metrics,
so you can compare against the published tables while it runs.

## 6. Scoring and figures

```bash
python scoring/score10.py --pred results_dev13/*.json --out DEV13-sweep.xlsx
python make_figures.py                              # regenerates docs/figures/ from the workbooks
```

Every workbook records `gt_file` and `gt_md5`, so results are traceable to the exact ground truth.

## 7. Verifying you match

Two checks before trusting a comparison:

1. **Regression fixture** — feed ground truth back as a prediction; it must score
   `row_f1 = cell_acc = UTS_acc = 1.000`. Run it after any scorer change.
2. **The prompt** — regenerate it (see [docs/prompt.md](docs/prompt.md)) and diff against the
   published text. Prompt drift is the most likely reason two machines disagree.

Expect **run-to-run variance**: the same model on the same paper varies across repeats, which is
why everything here is 3 repeats. Do not compare single runs. And do not silently drop failed runs
— an earlier result reported `0.895 ± 0.002` that was actually two surviving runs out of three;
with all three it was `0.681 ± 0.237`.

## Reproducing the Claude rows

The two Claude configurations are not run by these shell scripts — they are Claude Code subagents.
To reproduce:

1. Use the prompt in [docs/prompt.md](docs/prompt.md), with the `view_page`/`note`/`submit` protocol
   replaced by "read this PDF". Keep the inclusion criteria, field definitions and any per-paper
   scope note **verbatim** — they are what the local harness sends.
2. Run **one extraction per subagent**, with no shared conversation history, given only the PDF path.
   If the agent can see the ground truth — or a session that discussed it — the result is
   contaminated and worthless.
3. For the **Read-only** row, forbid Bash/Write/Edit and verify from the transcripts that no code
   ran. Do not rely on the agent's self-report.
4. Write each run to `results_claude/<CF-Pxx>__claude-r<N>.json` in the same shape as the local
   runs (`{cf_paper_id, model, rows, submitted_full}`), then score with the same `score10.py`.

Cost for 39 runs was **$10.47** (Read-only) and **$13.50** (with tools) at $5/MTok input +
$25/MTok output, ~90 % input share. Token counts are in the README so the figures recompute at any
rate.
