# The capacity curve — and what re-running the same sweep three times revealed

Gemma 3 spends a **fixed visual budget at every model size**: 258 tokens per page, 896×896 tiling,
independent of parameter count. That was measured separately on 4B, 12B and 27B with a token-delta
probe (identical prompt with and without the image, compare `prompt_tokens`), not assumed from
documentation. It makes Gemma 3 the only family in the roster where **parameters can be varied with
perception held constant** — the complement to a DPI ladder, which varies perception at fixed
parameters.

All three arms: engineered prompt, ctx 40,960, temperature 0.1, 13 dev papers × 3 repeats = 39 runs,
one Mac Mini M4 Pro, `lmstudio-community` GGUF at Q4_K_M.

| model | sweeps | row F1 | recall | precision | cell | UTS MAPE | rows/run | pages viewed | wall |
|---|---|---|---|---|---|---|---|---|---|
| **4B** | **3** | 0.371 | 0.336 | 0.655 | 0.746 | **31.6 ± 12.4** | 2.6 | 4.6 | 34 m |
| **12B** | 1 | 0.288 | 0.285 | 0.346 | 0.785 | 10.40 | 4.8 | 9.5 | 2 h 48 m |
| **27B** | 1 | 0.573 | 0.677 | 0.577 | 0.798 | 5.20 | 8.6 | 6.3 | 3 h 24 m |

## What is monotone, and what is not

**Monotone in parameters:** UTS MAPE (31.6 → 10.4 → 5.2) and rows emitted (2.6 → 4.8 → 8.6). The
metrics that require actually reading a value off a figure order cleanly with capacity.

**Not monotone:** row F1 and recall. The **4B beats the 12B on both**, and this survives all three
independent 4B sweeps — even the weakest (F1 0.336, recall 0.314) clears the 12B's 0.288 / 0.285.

Two mechanisms, and they are different:

- **Precision from under-extraction.** The 4B emits 2.6 rows against a mean ground truth of ~8.7 and
  posts precision **0.655** against the 12B's **0.346**. It returns a small, self-selected set of
  easy conditions and gets a good fraction of them right. This is the selection artifact catalogued
  in [failure-modes.md](failure-modes.md#3-severe-under-extraction) — the reason that document says
  to compare recall rather than F1.
- **The 12B's own collapse.** Recall was supposed to break the tie and it does not, because the 12B
  returns **zero rows on CF-P14, CF-P10 and CF-P15** — three total failures that a model a third its
  size survives. That is not under-extraction; it is a different failure, and it is what drags the
  12B below the 4B on a metric that should have been immune.

So "bigger is better" holds on value-reading and fails on row identification, for reasons that are
separable and neither of which is a scoring artifact alone.

## The methodological result: UTS MAPE is not a stable estimator

The 4B arm was run **three times with nothing changed** — same machine, same GGUF, same backend,
same context, same prompt, same harness. Only sampling at temperature 0.1 differs.

| metric | run 1 | run 2 | run 3 | mean | SD | **CV** |
|---|---|---|---|---|---|---|
| row F1 | 0.336 | 0.354 | 0.423 | 0.371 | 0.046 | 12.4 % |
| recall | 0.321 | 0.314 | 0.373 | 0.336 | 0.032 | 9.6 % |
| precision | 0.619 | 0.611 | 0.735 | 0.655 | 0.069 | 10.6 % |
| cell accuracy | 0.745 | 0.754 | 0.738 | 0.746 | 0.008 | **1.1 %** |
| **UTS MAPE** | **40.85** | **17.47** | **36.36** | **31.56** | **12.41** | **39.3 %** |

`docs/metrics.md` calls MAPE "the stable metric." **At this sample size, with a weak model, it is
the least stable quantity measured** — a 39 % coefficient of variation where cell accuracy moves
1.1 %.

The cause is a scorer property, not a model property. MAPE is **unbounded above** and averaged
per-paper before averaging across papers, so a 2-row paper carries the same weight as a 20-row paper
while having roughly ten times the variance. Per-paper, between two identical sweeps:

| paper | GT rows | run 1 | run 2 | Δ |
|---|---|---|---|---|
| **CF-P18** | **2** | **218.65** | **37.91** | **−180.75** |
| CF-P02 | 3 | 32.81 | 0.19 | −32.62 |
| CF-P05 | 18 | 43.34 | 11.54 | −31.80 |
| CF-P13 | 11 | 20.43 | 0.00 | −20.43 |
| CF-P24 | 20 | 10.59 | 10.59 | 0.00 |

Mean |Δ| per paper is **27.12**. One wrong value on CF-P18's two rows produces a 218 % error, and
whether that happens is close to a coin flip.

### A retraction this caused

An earlier reading of the data compared the 4B on the Mac (MAPE 40.85, `lmstudio-community`, Metal)
against the 4B on an RTX A2000 (15.03, `google` GGUF, CUDA) and treated the 2.7× gap as evidence of
**backend numerics or GGUF build** differences — with the implication that extraction results might
not be portable across compute backends. **That claim is withdrawn.** The A2000's 15.03 sits inside
the Mac's own run-to-run range of 17.47–40.85. Nothing about Metal-vs-CUDA was demonstrated, and the
follow-up experiment designed to separate the two causes would have been chasing sampling noise.

### What to change

1. **Report `UTS_medAPE_pct`** — the scorer already computes it and nothing uses it. Median APE is
   not destroyed by one 218 % paper.
2. **Bootstrap CIs over papers** on every reported mean, and state the unit of analysis as the paper
   (*n* = 13), not the run (*n* = 39) — `manifest.json` sets temperature 0.1, so three repeats on one
   paper are near-duplicates.
3. **Weight or stratify by GT row count**, or report MAPE only for papers above some row threshold.
4. **Repeat whole sweeps, not just runs within a sweep.** The 12B and 27B arms have *no* sweep-level
   variance estimate, so their MAPE values carry unknown error bars and the monotone ordering above
   is stated on one sample each.

## Cost of the arms

| arm | hardware | wall clock | API cost |
|---|---|---|---|
| 4B × 3 sweeps | M4 Pro | 34 m + 45 m + 29 m | $0 |
| 12B | M4 Pro | 2 h 48 m | $0 |
| 27B | M4 Pro | 3 h 24 m | $0 |

The 4B is **~6× faster than the 27B per sweep**, which is what made three repeats affordable — and
is the reason the instability above was discoverable at all. No arm of this campaign had a
sweep-level repeat before.
