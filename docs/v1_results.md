# PEEK-Bench v1 — archived results & accounting

Moved from the README when v2 superseded them as the campaign summary. Kept verbatim for provenance.

---

## Headline finding — generation A (early per-paper runs, mixed prompts)

*(historical, v1)*

**Chart-reading accuracy is monotonic in image-token budget, and it is not explained by model size.**

Pooled UTS error across the two papers whose values are figure-locked (CF-P11, CF-P18):

| model | image tokens | UTS MAPE | runtime | runs |
|---|---|---|---|---|
| gemma-3-27b | 256 | **40.78 %** | 4.4 min/run | 3 |
| mistral-small-3.1 | 1,030 | **18.78 %** | **3.2 min/run** | 6 |
| qwen3-vl-32b | ~2,900 | **3.48 %** | 7.4 min/run | 12 |

![headline](docs/figures/fig1_uts_error_by_paper.png)

An 11× spread across the local models, correctly ordered. Gemma-3-27B is the **largest** of the
three yet the **least accurate**, so this is an architectural property rather than a capability
ranking. *(Generation-A figures, from the early per-paper runs — the completed sweep gives
5.20 / 4.44 / 1.06.)*

*("Least accurate", not slowest — on wall-clock time the ordering is nearly reversed. See
[speed](#accuracy-costs-time) below.)*

The mechanism is unusually legible on CF-P18, whose values are printed as data labels on a
2008×716 raster bar chart. Gemma emitted the **correct experimental conditions** — `CF-PEEK 450 °C
/ 10 wt%`, `ESD-PEEK 430 °C / 0 wt%` — with `tensile_strength = null` on *every* row. It located
the experiment and could not resolve the digits. Qwen transcribed all nine bar labels exactly
(UTS MAPE **0.00 %**).

The contrast paper matters as much: **CF-P19** reports its results in a *table*, and all three
models matched 12/12 rows at 0.01–2.24 % MAPE. Same harness, same schema, same models — the only
difference is where the numbers live.

See [docs/findings.md](docs/findings.md) for the full result set, including the supplementary-
information experiment (parameter accuracy 0.393 → 0.916, *p* = 0.0006, *d* = 2.70, with UTS
deliberately unmoved at *p* = 0.93).


---

## Accuracy costs time

Reading a chart properly is not free. Mean wall-clock per run, same M4 Pro, three papers:

| model | CF-P19 | CF-P11 | CF-P18 | **mean** | UTS MAPE (figure-locked) |
|---|---|---|---|---|---|
| mistral-small-3.1-24b | 3.6 | 3.7 | 2.3 | **3.2 min** | 18.78 % |
| gemma-3-27b-it | 5.3 | 3.9 | 4.1 | **4.4 min** | 40.78 % |
| qwen3-vl-32b-instruct | 9.9 | 7.8 | 4.5 | **7.4 min** | **3.48 %** |

**The most accurate model is the slowest — 2.3× Mistral and 1.7× Gemma.** *(v1 table, LM Studio
era.)* **v2 update:** the effect generalized and then inverted its meaning — mixture-of-experts
models broke the accuracy-costs-time trade-off. The full-campaign `min/run` column (leaderboard
above) shows MoE arms (26B-A4B 3.6 min, Qwen3.6-35B 4.4 min) matching or beating dense models
one-third their total size while scoring within 0.02 F1 of the dense leaders: decode cost tracks
*active* parameters, and on bandwidth-bound consumer hardware that is a 3–5× wall-clock dividend. Gemma is neither fastest
nor most accurate, which is the least useful position to occupy: its fixed 256-token image encoder
means the extra time buys nothing on figure-locked papers.

The tradeoff is worth stating explicitly because it drives campaign cost. A full 10-paper × 3-model
× 3-repeat test run is ≈ 9 h; dropping to Qwen alone would be slower per run but is the only
configuration that reads charts reliably.

![runtime vs accuracy](docs/figures/fig5_runtime_vs_accuracy.png)


---

## Dev-13 sweep — generation B (primary result, complete)

*(historical, v1 — superseded as campaign summary by the v2 leaderboard above)*

All 13 development papers, 3 models × 3 repeats = 117 runs, one frozen prompt version. **This is the
result to cite**; generation A above came from mixed prompt versions and is not poolable with it.

**COMPLETE: 117/117 runs, 12 h 24 min wall clock, 3 zero-row failures (all Mistral, all traced to a
context-exhaustion bug on the longest papers).**

| configuration | model | tools | image path | runs | row F1 | cell | UTS acc | **UTS MAPE** | API cost |
|---|---|---|---|---|---|---|---|---|---|
| gemma | `gemma-3-27b-it` | agentic view/note/submit | JPEG, **256** tok | 39 | 0.573 | 0.798 | 0.761 | 5.20 | $0 · local |
| mistral | `mistral-small-3.1-24b-instruct-2503` | agentic view/note/submit | JPEG, **1,030** tok | 39 | 0.856 | 0.906 | 0.808 | 4.44 | $0 · local |
| qwen | `qwen3-vl-32b-instruct` | agentic view/note/submit | JPEG, **~2,900** dyn | 39 | 0.933 | 0.927 | 0.947 | 1.06 | $0 · local |
| **claude** | `claude-opus-5` | **Read only** | PDF native | 39 | **0.950** | **0.963** | **0.982** | **0.39** | **$10.47** |
| **claude code** | `claude-opus-5` | Read + Bash + Write + Edit | PDF native + code | 39 | 0.933 | 0.962 | 0.968 | 0.49 | $13.50 |

Local models: LM Studio on one Apple M4 Pro (64 GB), contexts 40,960 / 32,768 / 65,536. Claude rows:
Anthropic API through Claude Code, orchestrated as parallel subagents (12.9 min wall clock, 2.0 h
serial-equivalent for 39 runs). **Both Claude rows are the same model** — the only variable is tool
access.

API cost at **$5/MTok input + $25/MTok output** ([Opus 5 / Opus 4.8 standard rates](https://platform.claude.com/docs/en/about-claude/pricing)),
assuming a 90 % input share since PDF page images dominate. Token counts are exact; dollars scale
with your rate. The Batch API would halve these to **$5.24 / $6.75**. Local models cost nothing in
API terms but consumed ~11 h of GPU for the equivalent 117 runs.

![five configurations](docs/figures/fig7_five_configs.png)

**Claude is 2.7× more accurate than the best local model** (0.39 vs qwen's 1.06) and **13× more
accurate than the worst** (gemma 5.20), for about a dollar a paper. Note this gap narrowed sharply
once qwen completed: against the two models finished first it looked like ~11×.

| paper | gemma | mistral | qwen | claude |
|---|---|---|---|---|
| CF-P11 (figure sweeps) | 29.84 | 25.96 | 6.45 | **1.96** |
| CF-P18 (printed bar labels) | 13.11 | 10.17 | **0.00** | **0.00** |
| CF-P13 (SI + figures) | 9.28 | 11.70 | 3.56 | **1.78** |

On CF-P18 — printed bar labels on a raster chart — **qwen matches Claude exactly at 0.00 %**. A
local 32B model with a large enough image budget reads that chart perfectly. The remaining gap is on
CF-P11's swept curves, where values must be estimated against an axis rather than transcribed.

### The result is reading, not tooling — verified by ablation

The first Claude run made **220 Bash calls against 138 Reads**: agents were rendering pages at
1100 dpi and detecting axis ticks programmatically. That would make the headline a
chart-*digitisation* result rather than a chart-*reading* one, so it was re-run on five papers with
**code execution forbidden** — Read tool only, verified against the transcripts (44 Read calls,
**zero** Bash/Write/Edit across 15/15 agents).

Across all 13 papers, **Read-only beat the tool-enabled run on every metric** — row F1 0.950 vs
0.933, UTS MAPE **0.39 vs 0.49** — and cost 22 % less. On the five papers examined first, including
CF-P24 where the tool-enabled agents had digitised the axes at 1100 dpi:

UTS MAPE %, all five configurations:

| paper | gemma | mistral | qwen | claude READ-ONLY | claude + code |
|---|---|---|---|---|---|
| CF-P11 | 29.84 | 25.96 | 6.45 | 1.96 | **1.59** |
| CF-P13 | 9.28 | 11.70 | 3.56 | 1.78 | **1.68** |
| CF-P18 | 13.11 | 10.17 | **0.00** | **0.00** | **0.00** |
| CF-P19 *(table control)* | 0.64 | 1.00 | 1.41 | **0.40** | **0.40** |
| CF-P24 | 6.25 | 2.11 | 1.31 | **0.54** | 2.16 |

Eyeballing beat computing. The agents' own provenance says so: *"EVERY tensile_strength below is an
EYEBALL ESTIMATE against the y-axis"* — landing within 2 % on a paper where Gemma is 30 % out.

Note qwen: it **ties Claude at 0.00 on CF-P18** and is within ~1 point on CF-P19 and CF-P24. The
frontier advantage is real but narrow, and it is concentrated on **CF-P11's swept curves**
(1.96 vs 6.45), where values must be interpolated against an axis rather than transcribed from a
printed label.

**Caveats that stay attached to this row.** Claude reads the PDF through a document-reading tool
rather than fixed-budget JPEGs, so it does not have a comparable "image tokens" figure — the
comparison is *agentic system* vs *local VLM at a fixed image budget*, not a controlled swap of one
variable. Contamination was controlled by running every extraction in a fresh subagent with no
access to the session that built the ground truth, barred from opening any spreadsheet; the
provenance strings cite page numbers and figure panels. All four systems may have seen these
published papers in training — a shared confound, not a Claude-specific one.

**Cost**: the 39-run Claude sweep used **1.93 M tokens** and **12.9 min wall clock** (2.0 h serial,
run in parallel), versus ~11 h of local GPU for the equivalent 117 local runs.

**Paired Wilcoxon across all 13 papers, every pair:**

| comparison | row F1 | cell accuracy | UTS MAPE |
|---|---|---|---|
| mistral vs gemma | 8/13, ***p* = 0.043** | 6/11, ***p* = 0.031** | 4/11, *p* = 0.38 |
| qwen vs mistral | 5/13, *p* = 0.078 | 8/13, *p* = 0.055 | 7/12, ***p* = 0.023** |
| **qwen vs gemma** | 9/13, ***p* = 0.007** | 7/11, ***p* = 0.016** | 5/11, *p* = 0.063 |

The pattern is not a clean ladder. **Mistral beats Gemma on structure but not on values**
(UTS *p* = 0.38 — on figure-locked CF-P11 they are effectively tied at 25.96 % vs 29.84 %, both
catastrophic). **Qwen beats Mistral on values but not on structure** (UTS *p* = 0.023, row F1
*p* = 0.078).

So the image-token budget buys **chart reading specifically**, and it only starts paying above
~1,000 tokens: 256 → 1,030 changes nothing measurable for value accuracy, 1,030 → ~2,900 changes it
significantly. Structure — finding which conditions exist — improves earlier and for different
reasons.

![dev-13 sweep](docs/figures/fig6_dev13_sweep.png)

Much of Mistral's F1 advantage is not superior alignment but simply *writing numbers down*:
`CF-P14 0.000 → 0.894`, `CF-P20 0.000 → 1.000`, `CF-P18 0.457 → 1.000`. Those are papers where
Gemma returned rows with every `tensile_strength` null.

### Two failure modes found during the sweep

**Context exhaustion (harness bug, not model weakness).** Three runs returned zero rows — all
Mistral, all on the three longest papers. CF-P15 is 23 pages ≈ 20,700 text tokens; add two page
images at 1,030 each and the 32,768-token context is ~72 % consumed before generation. The evidence
is decisive: the CF-P15 run that viewed **one** page succeeded, and both runs that viewed **two**
pages returned empty completions at the same turn. Mistral's numbers here are therefore a **floor** —
it should be re-run at 65,536 context before any Gemma-vs-Mistral claim is published.

**Reported-but-unread rows.** Gemma scored `row F1 = 0.000` on CF-P14 and CF-P20 not by finding
nothing, but by finding every condition and reporting no values. See [docs/metrics.md](docs/metrics.md).


---

## Total development time estimate

**v2 update (2026-08-13):** the fleet campaign has since grown the totals to **2,383 runs on
disk** and **~200 machine-hours** across both machines (live master progress bar in the campaign
tooling). The v1 accounting below is kept as the record of what the *initial* benchmark cost —
the marginal cost per additional model has fallen with every layer of orchestration.

Measured from run artefacts on disk, **final as of 2026-07-27 01:22**. The dev-13 sweep is complete
(117/117), so these are the numbers, not a floor.

### Local GPU (Apple M4 Pro, 64 GB)

| | |
|---|---|
| **Runs on disk** | **205** |
| **Total inference** | **24.8 h** |
| **Calendar span** | **2.07 days**, 2026-07-24 23:43 → 2026-07-27 01:22 |
| Hardware | one M4 Pro — no cloud, no GPU rental |
| Code written | ~1,100 lines Python + 7 runner scripts |

| model | runs | inference |
|---|---|---|
| qwen3-vl-32b | 68 | **13.4 h** |
| gemma-3-27b | 68 | 6.0 h |
| mistral-small-3.1-24b | 68 | 4.9 h |

**Qwen consumed 54 % of all GPU time for the same number of runs** — 2.7× Mistral. It is also the
only local model that reads charts (UTS MAPE 1.06 % vs 4.44 / 5.20). That is the accuracy/cost
tradeoff as a budget line rather than a per-run average.

The full dev-13 sweep alone was **117 runs in 12 h 24 min**, with **3 zero-row failures** — all
Mistral, all traced to context exhaustion on the three longest papers.

### Claude API

| | |
|---|---|
| **Extractions** | **78** (39 with tools + 39 Read-only) |
| **Tokens** | **3,425,083** |
| **Wall clock** | **~20 min** total (parallel subagents) |
| **Cost** | **$23.98** at $5/MTok in + $25/MTok out, 90 % input share |

Two complete 13-paper configurations for **under $24 and twenty minutes**, against 24.8 h of local
GPU for the local sweeps.

### What the 24.8 h actually bought

| | |
|---|---|
| Survived into the published results | **16.8 h** |
| **Superseded by re-runs** | **8.1 h (33 %)** |

A third of all compute was thrown away and redone: the supplementary A/B ran twice (a harness that
failed 1-in-3, then again after fixes); CF-P18 and CF-P11 were each re-run after scope corrections;
the whole dev-13 sweep redid all 13 papers because earlier results came from mixed prompt versions.
Plus model triage, including **three verdicts that were wrong and had to be retracted** — each from
a qualitative probe rather than a measurement, which is why image-token budgets are now measured by
token delta.

### Honest read

The **inference time is the small part**. The dominant costs were curation and metric design: four
undisclosed scope filters, six scoring defects, 25 wrongly-blank ground-truth cells, and a ground
truth that contradicted a paper's own Table 1. All changed published results; none is visible in a
runtime total.

A team reproducing this — correct ground truth in hand, scorer already right — would need roughly
**13 h of local compute plus ~$24 of API**, and a day of setup. Building it from scratch, including
discovering that the *metric* was the dominant error source, took substantially longer than the
compute suggests.

### Cost of a full sweep, by split

The dev-13 figures below are **measured** from the completed 117-run sweep, not projected. The
test-10 row is projected from the same measured throughput.

| split | papers | pages | runs | inference | wall clock | status |
|---|---|---|---|---|---|---|
| **dev-13** | 13 | 186 | 117 | **12.3 h** | **12 h 24 min** | **complete** |
| test-10 (frozen) | 10 | 127 | 90 | *9.2 h projected* | — | not started |
| both | 23 | 313 | 207 | ~21.5 h | — | — |

**Measured throughput superseded the earlier priors** — every model was slower in the full sweep
than in the short per-paper runs used to build the first estimate:

| model | measured min/page | earlier prior |
|---|---|---|
| gemma-3-27b | **0.398** | 0.355 |
| mistral-small-3.1 | **0.333** | 0.275 |
| qwen3-vl-32b | **0.713** | 0.565 |

That is why the test-10 projection rose from 7.6 h to **9.2 h**. The original priors came from
CF-P18 and CF-P11 — both small, and both papers where models terminate early — so they
underestimated the corpus.

**Per-paper cost tracks page count far less cleanly than expected.** Measured, 9 runs each:

| dev paper | pages | UTS pts | 9 runs |
|---|---|---|---|
| CF-P13 | 21 | 11 | **134 min** |
| CF-P14 | 21 | 9 | 100 min |
| CF-P05 | 11 | 18 | 90 min |
| CF-P24 | 11 | 20 | 71 min |
| CF-P19 | 6 | 12 | 56 min |
| CF-P15 | 23 | 2 | 50 min |
| CF-P11 | 10 | 17 | 48 min |
| CF-P01 | 19 | 10 | 47 min |
| CF-P20 | 17 | 5 | 37 min |
| CF-P18 | 13 | 2 | 33 min |
| CF-P10 | 17 | 2 | 30 min |
| CF-P04 | 8 | 2 | 25 min |
| CF-P02 | 9 | 3 | 18 min |

The page-count model I used for planning does not hold: **CF-P15 is the longest paper (23 pp) but
only the 6th most expensive**, while CF-P05 at 11 pages cost 90 min. Runtime tracks **rows emitted**
— generation volume — more than pages read. CF-P13 is expensive on both counts (21 pp, and models
over-extract it), CF-P02 cheap on both.

The cost/yield asymmetry survives though: **CF-P02 gives 3 datapoints for 18 min; CF-P05 gives 18
for 90 min** — a 5× spread in minutes per datapoint.

### Remaining to a complete benchmark

| item | cost |
|---|---|
| Audit the 6 unaudited test papers | no GPU — **blocking** |
| Frozen test run: 10 papers × 3 models × 3 repeats = 90 runs | **9.2 h** + ~9 min model-load overhead |
| `gemma-3-12b-it` control on CF-P18 | ~12 min |
| **Total to publishable** | **≈ 9–10 h**, one overnight run |

*(dev-13 is complete — 117/117. The test-run estimate rose from 7.6 h to 9.2 h once the completed
sweep gave measured throughput rather than priors.)*

### Honest read on the estimate

The **12.5 h of inference is the small part**. The dominant costs were curation and metric design:
tracing four undisclosed scope filters, finding six scoring defects, and reconciling ground-truth
cells against the source papers — all of which changed results and none of which is visible in a
runtime total.

A team reproducing this with the ground truth in hand and the scorer already correct would need
roughly **10 h of compute and a day of setup**. Building it from scratch — including discovering
that the metric, not the model, was the dominant error source — took substantially longer than the
compute suggests.
