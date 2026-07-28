# Failure modes

Catalogued from the naive-prompt ablation (39 local runs, 78 Claude runs) against the
prompt-engineered sweep. They are **model-specific, not uniform** — each configuration fails a
different way, which is why a single accuracy number hides most of what is going on.

---

## 1. Grid-filling over-extraction

The model treats a paper's factors as a cross-product and emits every combination, including ones
never run.

| paper | GT rows | mistral naive | qwen naive |
|---|---|---|---|
| **CF-P24** | 20 | **41** | **60** |
| **CF-P11** | 17 | **33** | 5 |
| **CF-P18** | 2 | **10** | **6** |

Qwen emitted **3× the ground truth** on CF-P24. Both models attempt the full material × sweep-level
grid where the paper reports several materials swept across several factors.

**It is concentrated, not general.** On the seven papers with unambiguous scope — CF-P05, P20, P02,
P04, P15, P10, P01 — all three local models matched the row count **exactly**, with no guidance.
Over-extraction appears only where the ground truth silently keeps a subset of what the paper
reports.

*Mitigation:* the engineered rule *"a sweep applies only to the material(s) the paper actually
swept … never copy one material's value across another material's sweep levels."* This rule was
itself written after observing the failure — an earlier version said *"two materials across a
5-level sweep = 10 rows"*, which invited it.

## 2. Rows with no measurement

```
gemma     25/79  rows (31.6 %) had tensile_strength = null
mistral    2/156 (1.3 %)
qwen       0/155 (0.0 %)
```

**Almost a third of Gemma's naive rows carry no value.** It identifies the experimental conditions
and reports nothing measured. This produces `row_f1 = 0.000` on CF-P01 and CF-P18 despite emitting
9 and 3 rows, because a null-UTS row cannot match by design — the task's first criterion is
*"has a reported UTS; no UTS ⇒ not a row."*

Before that scorer rule existed, such runs scored **near the top of the table**: they align
perfectly on process parameters while contributing no data. See
[scoring-defects.md](scoring-defects.md) §6.

## 3. Severe under-extraction

The mirror image of §1, and also Gemma:

| paper | GT | gemma naive | row F1 |
|---|---|---|---|
| CF-P24 | 20 | **5** | 0.080 |
| CF-P11 | 17 | **4** | 0.190 |

It stops after the first table or figure rather than enumerating the sweep. Note this *inflates*
its cell and UTS accuracy, because those are computed only over matched rows — a smaller,
self-selected, easier subset. Compare recall, not cell accuracy.

## 4. Chart-reading collapse on swept curves

CF-P11 UTS MAPE, naive: **gemma 35.0, qwen 35.5, mistral 47.0** — against 29.8 / 6.5 / 26.0
engineered. Qwen degrades **5.5×**, its single worst regression anywhere.

CF-P11 is the paper whose values sit on swept line curves rather than printed labels, so they must
be **interpolated against an axis** rather than transcribed. That distinction — interpolation vs
transcription — is where the frontier/local gap survives: on CF-P18's printed bar labels qwen ties
Claude at 0.00, but on CF-P11's curves it is 6.45 against Claude's 1.96.

## 5. Intermittent non-termination

**4 of 39** local naive runs exceeded 5× their engineered-prompt time and were killed:
CF-P11 × mistral (3 h 38 m), CF-P24 × qwen (2 h), CF-P11 × qwen (36 min), CF-P13 × qwen (75 min).

**All four completed on retry under a 3× cap.** CF-P11 × mistral went from a 3 h 38 m stall to
**5.9 min** on an identical configuration; CF-P24 × qwen needed four attempts and finished in
21.0 min. Non-termination is therefore **intermittent, not a deterministic property of the prompt**
— an earlier claim to the contrary is withdrawn.

The mechanism is §1: runtime scales with rows emitted, so the 60-row CF-P24 run and the stall are
the same event, not two.

*Mitigation:* a **3× timeout with retry**, not a longer prompt. It recovered 3 of 4 on the first
retry and costs at most 3× a normal run.

Two distinct stall signatures were observed, worth distinguishing when diagnosing:

| status | meaning |
|---|---|
| `GENERATING` | runaway output — unbounded row grid (mistral) |
| `PROCESSINGPROMPT` | prefill blowup — too many page images in context (qwen, ~2,900 tok/image) |

## 6. Fabrication under coverage pressure

The engineered prompt makes every **local** model invent more, not less:

| model | naive false-fill | engineered | |
|---|---|---|---|
| gemma | 0.042 | 0.217 | **5.2×** |
| mistral | 0.204 | 0.750 | 3.7× |
| qwen | 0.111 | 0.401 | 3.6× |
| claude | 0.111 | 0.111 | unchanged |

Mistral fabricates a value in **75 %** of the cells its paper leaves blank. The
*"extract EVERY qualifying condition"* rule buys coverage and pays for it in invention. Claude does
not respond to that pressure at all.

This is visible only because ground truth is **pre-imputation** — a blank means the paper does not
report it, so filling it is a scored error rather than a lucky guess.

---

## What ties them together

Failures are **not randomly distributed across papers**. Modes 1, 4 and 5 cluster on CF-P24,
CF-P11, CF-P13 and CF-P18 — precisely the papers where the ground truth keeps a subset of what the
paper reports, or where values must be interpolated from curves.

Part of what the engineered prompt buys is therefore not extraction skill but **transmission of
curation decisions the source document does not contain**. That is a property of the benchmark, not
of the models, and it is the same conclusion the scope-filter audit reached from the opposite
direction — see [methodology.md](methodology.md#scope-mechanisms).
