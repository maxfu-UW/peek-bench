# The capacity curve, and what repeating whole sweeps revealed

Gemma 3 spends a **fixed visual budget at every model size**: 258 tokens per page, independent of
parameter count. Measured separately on 4B, 12B and 27B with a token-delta probe (identical prompt
with and without the image, compare `prompt_tokens`), not taken from documentation. That makes
Gemma 3 the only family in the roster where **parameters vary with perception held constant**.

All arms: engineered prompt, ctx 40,960, temperature 0.1, 13 dev papers × 3 repeats = 39 runs per
sweep, one Mac Mini M4 Pro, `lmstudio-community` GGUF at Q4_K_M.

**Every arm has now been swept at least twice.** Values below are means across whole sweeps, ± the
standard deviation *between* sweeps.

| model | sweeps | row F1 | recall | precision | cell acc | UTS MAPE |
|---|---|---|---|---|---|---|
| **4B** | 3 | 0.371 ± 0.046 | 0.336 ± 0.032 | 0.655 ± 0.069 | 0.746 ± 0.008 | **31.56 ± 12.41** |
| **12B** | 2 | 0.362 ± 0.105 | 0.371 ± 0.122 | 0.404 ± 0.082 | 0.805 ± 0.028 | **9.54 ± 1.23** |
| **27B** | 2 | 0.572 ± 0.001 | 0.645 ± 0.045 | 0.609 ± 0.046 | 0.798 ± 0.000 | **5.51 ± 0.44** |

## What is monotone

**UTS MAPE: 31.56 → 9.54 → 5.51.** **Recall: 0.336 → 0.371 → 0.645.** Both order with parameters,
and both survive repetition.

**Row F1 does not: 0.371 → 0.362 → 0.572.** The 4B and 12B are tied within their error bars.

## Retraction: the "4B beats the 12B" inversion

An earlier version of this document, of the repository README, and of the paper draft reported that
the **4B outscored the 12B on row F1 and recall**, and offered two mechanisms for it — the 4B's
precision advantage from under-extraction, and the 12B returning zero rows on three papers.

**That inversion was substantially a single-sample artifact and is withdrawn.** It rested on one
12B sweep. A second identical sweep moved the 12B's row F1 from **0.288 to 0.437** (+52% relative)
and its recall from **0.285 to 0.458** (+61%). Averaged over both sweeps the 12B ties the 4B on F1
and **exceeds** it on recall, which is the ordering capacity would predict.

The under-extraction mechanism is still real and still visible in the precision column (4B 0.655
against 12B 0.404). What is withdrawn is the claim that it produced a *rank inversion*.

## The finding that replaced it: reproducibility scales with model size

Repeating whole sweeps was intended to put error bars on the curve. It measured something the
campaign had not looked for.

| model | worst relative swing between identical sweeps | on |
|---|---|---|
| **4B** | **74.1 %** | UTS MAPE |
| **12B** | **46.4 %** | recall |
| **27B** | **11.4 %** | UTS MAPE |

**Small models are not merely less accurate — they are less reproducible.** A single sweep of the
27B is a usable estimate of that arm; a single sweep of the 4B is close to a draw from a wide
distribution. Nothing changed between sweeps but temperature-0.1 sampling.

Two consequences:

1. **A fixed repeat protocol is wrong.** Evaluating every system with the same *n* repeats is
   under-powered at the small end and wasteful at the large end. The number of repeats a benchmark
   needs is a property of the system under test, and should be chosen from a measured variance, not
   assumed.
2. **F1 can hide the instability that produced it.** Between the 27B's two sweeps, recall fell 9.5 %
   and precision rose 11.4 % while row F1 moved **0.573 → 0.571**. Reporting F1 alone would have
   shown a perfectly stable arm and concealed that it had traded coverage for correctness.

## Metric stability, measured

From three identical 4B sweeps:

| metric | run 1 | run 2 | run 3 | CV |
|---|---|---|---|---|
| cell accuracy | 0.745 | 0.754 | 0.738 | **1.1 %** |
| recall | 0.321 | 0.314 | 0.373 | 9.6 % |
| precision | 0.619 | 0.611 | 0.735 | 10.6 % |
| row F1 | 0.336 | 0.354 | 0.423 | 12.4 % |
| **UTS MAPE** | **40.85** | **17.47** | **36.36** | **39.3 %** |

`docs/metrics.md` originally called MAPE "the stable metric". On the 4B it is the least stable thing
measured. MAPE is unbounded above and averaged per-paper before averaging across papers, so a 2-row
paper carries the same weight as a 20-row paper with roughly ten times the variance — between two
identical sweeps CF-P18 (2 GT rows) swung **218.65 → 37.91**.

**But metric stability is itself model-dependent**, which the 4B data alone would not have shown: on
the 12B the least stable metric was **recall**, not MAPE, and on the 27B row F1 and cell accuracy
were reproducible to three decimal places. There is no metric that is stable in general.

### A retraction this line of work caused

An apparent 2.7× gap between the 4B on this Mac (MAPE 40.85) and the same model on an RTX A2000
(15.03) was initially read as evidence of **compute-backend (Metal vs CUDA) or GGUF-build
divergence**, with the implication that results might not be portable across hardware. **Withdrawn.**
The A2000's 15.03 sits inside the Mac's own run-to-run range of 17.47–40.85. Nothing about backend
numerics was demonstrated.

## What to change

1. Report `UTS_medAPE_pct` alongside the mean — the scorer computes it and nothing uses it.
2. Bootstrap CIs over papers; the unit of analysis is the **paper** (*n* = 13), not the run
   (*n* = 39), because temperature 0.1 makes within-sweep repeats near-duplicates.
3. Weight or stratify by ground-truth row count.
4. **Repeat whole sweeps, and choose the repeat count from measured variance per system.** Every
   arm in this table needed it; the two that were not repeated produced a published claim that did
   not survive.

## Cost

| arm | sweeps | wall clock |
|---|---|---|
| 4B | 3 | 29 m + 45 m + 29 m |
| 12B | 2 | 2 h 48 m + 2 h 36 m |
| 27B | 2 | 3 h 24 m + 3 h 05 m |

All on one M4 Pro, $0 compute. The 4B is ~6× faster per sweep than the 27B, which is why three
repeats were affordable there first — and why the instability was discoverable at all.
