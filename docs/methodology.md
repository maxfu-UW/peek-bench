# Methodology

## Extraction harness (`harness/extract10.py`)

An agentic multi-turn loop. The model receives the **complete text of every page up front** and
requests page **images on demand**:

```json
{"tool":"view_page","page":6}
{"tool":"note","text":"Table 1 gives the fixed parameters; Fig 4 has the sweeps"}
{"tool":"submit","rows":[{...}]}
```

**Why text up front, images on request.** Text costs ~1 token per 4 characters; one page image
costs 256–2,900 tokens depending on the model. An earlier version capped page text at 1,500
characters and silently truncated the methods section — both models then scored 0/18 on exactly the
parameters stated there. Fixing it in the harness applies uniformly to every model, unlike a prompt
instruction, which is model-dependent.

**Prefix caching makes the loop cheaper than single-pass** (0.73× / 0.77× wall clock measured),
because the conversation prefix is reused across turns.

**Turn budget scales with document length**: `max_turns = clamp(pages + 10, 14, 36)`. A fixed
budget of 14 starved a 21-page document and produced zero-row runs.

**Output tolerance.** Models emit invalid JSON in predictable ways — `//` comments, unevaluated
arithmetic (`20/60`), trailing commas. The parser repairs these before parsing. The arithmetic case
was *induced by our own prompt*, which said "divide mm/min by 60"; the rule now says to write only
the final number, and the sanitiser catches it anyway.

## Scoring (`scoring/score10.py`)

Ground truth is loaded with four filters reproducing the source analysis exactly (232 datapoints /
23 papers): UTS present, paper id present, non-vertical coupons, source in a 23-paper whitelist.

**Row alignment.** Hungarian assignment on a record-linkage distance over **input parameters
only** — never the output. Including UTS in the distance pairs rows that already agree on UTS and
then scores UTS as correct, which manufactures near-perfect accuracy from a wrong extraction.

`identity_cols()` returns columns varying in ground truth **or** in the prediction. Constant
columns are still fully scored for cell accuracy, they just cannot veto a match. A predicted row
with **null `tensile_strength` can never match** — the task's first criterion is "no UTS ⇒ not a
row".

**Metrics.** Row precision / recall / F1; tolerance-aware cell accuracy (1 % on parameters, 5 % on
UTS since it is often a chart read); UTS MAPE; and `false_fill_rate` — of the cells the paper
leaves unreported, how often did the model invent a value? The curator's imputation defaults
(0.4 mm, ±45, 100 %, 130 °C) are exactly what a model would guess, so this separates reading from
convention-guessing.

**Alignment diagnostics.** `alignment_degenerate` marks papers where *no* scored column
distinguishes the rows — these vary factors outside the schema (chamber temperature, annealing
temperature), so pairing is arbitrary and per-row UTS is withheld in favour of an order-free sorted
MAPE. `ambiguous_row_frac` reports partial collisions elsewhere.

**Provenance.** Every workbook is stamped with the ground-truth filename and MD5. The scorer
resolves the highest-versioned `PEEK2-CF-main-*-peekbench-v*.xlsx` rather than pinning a name,
because a stale ground truth fails as *plausible numbers* rather than as an error.

## Answerability (`scoring/audit_findability.py`)

Some ground-truth values appear in **no source document** — curator inference from datasheets.
Scoring those cells punishes faithful extraction, so they are excluded and counted, and a per-paper
**answerability ceiling** is reported alongside results. A 0.75 then reads as "at ceiling" rather
than "model failed".

Two deliberate limits: the audit covers input parameters only (tensile strength is frequently
figure-sourced, so absence from the text layer says nothing), and string matching is optimistic, so
the ceiling is an upper bound. Zero-valued cells are a known weak spot — `"0"` matches almost any
document.

## The Claude configurations

Two rows in the results table are `claude-opus-5` driven through Claude Code rather than a local
serving endpoint. They use the same inclusion criteria, field definitions and per-paper scope notes
as the local harness — see [prompt.md](prompt.md) — with the `view_page`/`note`/`submit` tool
protocol replaced by direct document reading.

**Orchestration.** Each extraction is an independent subagent; 39 run in parallel. Wall clock for
the 39-run sweep was 12.9 min against 2.0 h of serial-equivalent model time. That parallelism is an
infrastructure property, not a model property, and is reported separately from per-run cost.

**Contamination control.** The ground truth was built and audited in the same session that launched
these runs, so an agent with that context would be recalling answers rather than reading papers.
Every extraction therefore runs in a fresh subagent with no conversation history, given only the PDF
path and the prompt, and explicitly barred from opening any spreadsheet or searching for ground
truth.

**The Read-only ablation.** Because the first run's agents wrote and executed code to digitise
charts, the set was re-run with code execution forbidden. Compliance is checked by counting actual
`tool_use` records in the agent transcripts — self-reporting on a compliance question is verified,
not trusted. Any run that executed code would be discarded; none did.

**What cannot be equalised.** Local models receive page JPEGs at a fixed image-token budget
(256 / 1,030 / ~2,900). Claude reads the PDF through a document-reading tool at native resolution.
The two are not a controlled swap of one variable, and the Claude rows carry no image-token figure.

## Scope mechanisms

Ground truth encodes curation decisions the prompt never stated, and charging those to the model
inverts rankings (see [scoring-defects.md](scoring-defects.md) §5).

- **`out_of_scope.json`** — scoring-side. Conditions a paper genuinely reports but the curator
  excluded, keyed by tensile strength. Matching predictions leave the precision denominator instead
  of counting as hallucinations. Only safe where excluded and in-scope values are well separated;
  one paper is deliberately absent because they collide inside tolerance.
- **`paper_scope.json`** — prompt-side. A per-paper note injected into the system prompt where the
  scope cannot be stated as a corpus-wide rule. Two papers currently carry one.

**Why not a global rule?** One paper keeps only room-temperature rows while another keeps a full
cryogenic sweep (25 down to −175 °C) — and both papers explicitly study temperature. No instruction
derivable from the papers separates them; it is a curation choice. A global "room temperature only"
rule would have deleted 4 of 5 ground-truth rows from a **frozen test** paper.

**The cost, stated plainly:** a paper carrying a scope note does not see the same prompt as the
rest of the corpus, so its scores are not strictly comparable and must be footnoted. Keep the file
as small as possible. A measured side-effect: after adding scope notes, 2 of 18 runs collapsed to a
single row.

## Reproducibility

Regression fixtures feed ground truth back as a prediction; they must score
`row_f1 = cell_acc = UTS_acc = 1.000`. Checked after every scorer change — it caught several of the
defects.

Charts are regenerated from the shipped workbooks with `python make_figures.py`, which reads only
the `summary` sheets and needs no ground truth.
