# What the metrics mean

They follow the extraction pipeline in order: **find the rows → align them to ground truth →
score the parameters → score the answer.**

## The four headline metrics

| metric | question it answers | tolerance |
|---|---|---|
| **row F1** | did the model find the right *conditions*? | match distance `< 0.5` |
| **cell acc** | of the parameter cells in matched rows, how many are right? | 1 % or ±0.5 absolute |
| **UTS acc** | fraction of tensile values correct | 5 % or ±1.0 MPa |
| **UTS MAPE** | mean absolute % error on tensile strength | — |

**Row alignment uses input parameters only — never the output.** Including UTS in the matching
distance lets the matcher pair rows that already agree on the answer and then score that answer as
correct. That bug existed, and it manufactured near-perfect UTS accuracy from wrong extractions.

**UTS gets a looser tolerance than parameters** because it is frequently read off a chart, while
parameters are usually tabulated.

**MAPE is the stable metric.** Accuracy is a step function that cannot distinguish missing by 6 %
from missing by 60 %.

## Row F1 and UTS accuracy measure different capabilities

They do not move together, and quoting one alone inverts rankings. Real examples from the dev-13
sweep:

| run | row F1 | UTS acc | what happened |
|---|---|---|---|
| CF-P11 mistral | **0.938** | **0.134** | found 94 % of conditions, read 13 % of values |
| CF-P01 mistral | 1.000 | 1.000 | tabulated paper — both agree |
| CF-P20 gemma | **0.000** | — | found every condition, reported `tensile_strength = null` on all |

The last row is the important one. `0.000` does not mean "found nothing" — it means the model
identified the experiment and reported **no measurements**. A null-UTS row cannot match by design,
because the task's first inclusion criterion is *"has a reported UTS; no UTS ⇒ not a row"*. Before
that rule was enforced, such runs scored near the top of the table.

Report **row F1 and UTS MAPE together**, always.

## Three diagnostics that qualify the headline numbers

**`false_fill_rate`** — of the cells ground truth leaves blank (the paper does not report them),
how often did the model invent a value? The curator's imputation defaults (0.4 mm, ±45, 100 %,
130 °C) are exactly what a model would guess, so this separates *reading* from
*convention-guessing*.

**`answerability_ceiling`** — fraction of ground-truth cells actually present in the source
document. Some GT values appear in no document at all (curator inference from datasheets); scoring
those punishes faithful extraction. The ceiling lets a 0.75 be read as "at ceiling" rather than
"model failed".

**`alignment_degenerate` / `ambiguous_row_frac`** — whether GT rows can be told apart at all. Four
papers vary only factors outside the schema (chamber temperature, annealing temperature), so every
pairing is arbitrary; for those, per-row UTS is withheld and an order-free **sorted MAPE** is
reported instead. Eleven more papers have *some* colliding rows, reported as a fraction.

## Reading a model row

```
gemma    F1 0.573   cell 0.798   MAPE 5.20
mistral  F1 0.856   cell 0.906   MAPE 4.44
```

Mistral is significantly better at **structure** (row F1 *p* = 0.043, cell *p* = 0.031) and
statistically **tied on values** (*p* = 0.38). Those are different capabilities. A single blended
"accuracy" score would report Mistral as broadly better, when what it actually does better is find
rows and write numbers down at all — it reads charts no better than Gemma does.

## Provenance

Every workbook carries `gt_file` and `gt_md5`, so any number can be traced to the exact ground
truth it was scored against. The scorer resolves the highest-versioned GT file rather than pinning
a name, because a stale ground truth fails as *plausible numbers* rather than as an error.
