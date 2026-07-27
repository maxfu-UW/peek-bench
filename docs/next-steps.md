# Next steps

Ranked. Costs are measured from observed throughput (min/page per model), not estimated.

## 1. Audit the six unaudited test papers — before spending GPU time

**CF-P22, P07, P17, P08, P09, P23 = 56 of the 119 test rows** have never been checked for
undisclosed scope filters. Four such filters are already known — room-temperature-only,
material-arm narrowing, sweep subsetting, and CNT-filled-PEEK classified as neat — and every one
was found by examining a *handful* of papers. Both papers examined closely (CF-P18, CF-P11) turned
out to have them, and in both cases they inverted the model ranking until fixed.

Cost: no GPU. Strictly blocking — discovering this after the test run means repeating the test run.

## 2. Resolve CF-P06

Fully degenerate under the current schema: all five rows share one identity tuple because what
distinguishes them is **test temperature**, stored in a column that is not scored. Its row F1 will
be meaningless.

Options: accept sorted-UTS-only for it (free, already implemented) and footnote; or add
`test_temperature` to the schema, which also repairs part of the wider collision problem but needs
ground-truth work.

## 3. Freeze and record the configuration

Development results came from **mixed prompt versions** — pre-ROUTE, post-ROUTE, and two per-paper
scope notes added mid-campaign. Fine for development, not for the headline table. The test run
needs one frozen configuration with prompt, scorer, GT filename and MD5, `paper_scope.json` and
`out_of_scope.json` all pinned and recorded.

The scorer already stamps `gt_file` and `gt_md5` into every workbook.

## 4. Run the frozen test

Measured throughput from the COMPLETED dev-13 sweep: gemma 0.398 min/page, mistral 0.333, qwen 0.713. (Earlier priors of 0.355/0.275/0.565 came from two short papers and underestimated the corpus.)

| configuration | runs | wall clock |
|---|---|---|
| 10 papers × 3 models × 3 repeats | 90 | **9.2 h** + ~9 min model-load overhead |
| 2 models instead of 3 | 60 | 5.8 h |
| 1 repeat instead of 3 | 30 | 3.1 h |

Largest items: CF-P25 (15 pp, 30 pts, 54 min), CF-P22 (21 pp, 24 pts, 75 min).

**Keep all three models and all three repeats.** Dropping a model loses the image-token result
entirely. Dropping repeats loses variance — and variance is what exposed both the 1-in-3
catastrophic failure rate and the survivorship bias that made an unstable configuration look
consistent to three decimal places.

## 5. Cheap control (~12 min)

Three `gemma-3-12b-it` runs on CF-P18. All Gemma 3 vision models share the fixed 256-token image
encoder, so if the 12B checkpoint also returns correct conditions with null values, the
image-token effect is demonstrably **architectural rather than a size artefact** — closing the most
obvious objection, since the current evidence rests on the 27B checkpoint alone.

## 6. Serve the benchmark over MCP

Today the harness is bespoke Python driving a local LM Studio endpoint. That makes the benchmark
hard to run against anything else, and it means the ground truth has to sit on the same machine as
the model.

An MCP server fixes both. A `peek-paper-md` server already exists and serves the corpus
(`list_papers`, `get_paper` returning frontmatter + markdown body). The benchmark needs three more
tools on top of it:

| tool | purpose |
|---|---|
| `get_page_image(paper_id, page)` | the load-bearing one — this benchmark is about **reading figures**, and a markdown body cannot carry a bar chart |
| `submit_extraction(paper_id, rows)` | score server-side and return metrics only |
| `get_answerability(paper_id)` | per-paper ceiling, so a score can be read as "at ceiling" vs "model failed" |

**Why this matters more than convenience: it protects the frozen test split.** If scoring happens
server-side and only metrics come back, ground truth never reaches the client. The test papers can
then be evaluated by any MCP-capable agent without the answers leaking into a context window, a
log, or a training corpus. That is the difference between a benchmark that can be published and one
that is single-use.

It also makes the comparison **model-agnostic**. Every number in this repo comes from three local
vision models driven by one harness; the image-token finding predicts how *any* model should
behave, and an MCP surface is how that prediction gets tested against hosted models on identical
tooling.

Design notes worth keeping: return page images at native resolution and let the client downsample
(the whole finding is about what survives downsampling); expose the per-paper scope notes through
the same tool that serves the paper, so scope travels with the task rather than living in a
separate prompt; and rate-limit or log `submit_extraction` per paper, since unlimited scored
submissions turn a held-out split into a training signal.

## 7. Package the workflows as Skills

Three procedures in this project are reusable, non-obvious, and were each arrived at by getting
them wrong first:

- **`peek-extract`** — the extraction protocol: inclusion criteria, the 12-field schema with its
  per-field "NOT x, NOT y" disambiguations (derived from a 549-term scan of the corpus), and the
  A→B→C method that forces a model to locate the setup table before viewing figures.
- **`peek-score`** — running the scorer and, more importantly, *reading* it: when `row_f1` is an
  alignment artefact, when `UTS_acc` is withheld and sorted MAPE should be quoted instead, what
  `answerability_ceiling` and `ambiguous_row_frac` mean, and why row F1 and UTS accuracy must never
  be reported alone.
- **`peek-curate`** — the ground-truth audit loop that found four undisclosed scope filters and 25
  wrongly-blank cells: read the paper, map each GT row to a reported condition, and check whether a
  blank is genuinely unreported or a curation miss. This one changed published numbers twice.

The scoring skill is the one with value beyond this project. Nothing in it is PEEK-specific: *a
metric that rewards narrow extraction over correct extraction* is a general failure mode, and the
six defects in [scoring-defects.md](scoring-defects.md) are a checklist any extraction benchmark
could run against itself.

## Deferred

- **Per-paper scope notes break prompt uniformity.** Two papers currently carry them, so their
  scores are not strictly comparable to the rest of the corpus. Footnote required.
- **Ground-truth curation.** One paper appears under-curated (30 rows where the design supports
  more). Not blocking the test run.
- **`audit_findability` is optimistic for zero-valued cells** — a substring test where the value is
  `0` matches almost any document, so 40 such cells are marked findable automatically. The corpus
  ceiling moved only 96.3 % → 96.4 %, so nothing material rests on it, but per-paper 100 % figures
  should not be read as evidence a paper states a neat-PEEK fibre content.
