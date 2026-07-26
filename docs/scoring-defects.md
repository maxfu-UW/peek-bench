# Scoring defects found and fixed

Six defects in the scorer, several of which **inverted the model ranking** — the benchmark
rewarded worse extraction. Each was found by adversarially re-deriving numbers from primary
sources, and each is recorded with the observation that exposed it.

The transferable lesson: on this project **the metric was a larger error source than any model**.
Three of the six were introduced by fixes to earlier ones.

---

### 1. Circular alignment — UTS weighted inside the matching distance

Rows were matched using a distance that included `tensile_strength`. The matcher paired rows that
already agreed on UTS, then scored UTS as correct — manufacturing near-perfect accuracy from a
wrong extraction.

**Fix:** align on **input parameters only**. Row alignment answers "which condition is this row
about"; the output is then scored independently.

### 2. Non-discriminative columns vetoing matches

Columns constant across a paper still contributed to the distance, so a wrong value in a column
that never varies could veto an otherwise perfect match.

**Fix:** `identity_cols()` = columns varying in GT **or** in the predictions. The prediction clause
matters: a model may extract neat-PEEK rows a single-material GT does not contain, and without it
those rows are indistinguishable and get mis-assigned.

### 3. Single-factor papers scoring F1 = 0

`row_distance` required 2 co-present fields. Papers sweeping exactly one factor could never reach
that, so a correct extraction scored 0.

**Fix:** `need = min(2, len(cols))`.

### 4. `raster_angle` excluded from alignment — and the over-correction that followed

`identity_cols` looped over numeric columns only, so papers whose rows are labelled *only* by
raster angle looked unalignable. Adding the text column fixed those but introduced two worse bugs,
both caught before shipping:

- **Total blackout.** Where `raster_angle` was the sole varying column, a model that got every
  numeric parameter and UTS right but worded the angle differently (`"Lines"`, a list, `null`)
  scored `f1 = 0.0, cell_acc = None`. `None` does not penalise — it **silently drops out of a
  mean**, so a broken paper looked identical to a perfect one.
- **Errors made invisible.** Rows carrying a raster error became unmatchable, so the error left the
  denominator. On real runs, mean `row_f1` fell 0.792 → 0.478 while `cell_acc` *rose*
  0.656 → 0.705 and a third of GT cells vanished from scoring.

**Fix:** a categorical column can never be the sole identity basis (numerics stay in), and
categorical distance carries weight 0.5 — a categorical mismatch is all-or-nothing (1.0) whereas a
numeric mismatch is a bounded ratio (nozzle temp 400 vs 440 scores 0.09), so at equal weight one
categorical error outvoted several correct numeric fields.

### 5. Out-of-scope conditions counted as hallucinations

Ground truth reflects curation decisions the extractor prompt never states — e.g. keeping only
room-temperature rows from a paper that also reports 110 °C and 130 °C.

On CF-P18 a model that transcribed **all nine** of a chart's printed bar labels correctly (2 in
scope, 7 curator-excluded) scored `row_f1 = 0.364`, while one returning 3 rows with values wrong by
8–13 MPa scored **0.800**. The metric rewarded narrowness over accuracy.

**Fix:** `out_of_scope.json` lists conditions a paper genuinely reports but the curator excluded,
keyed by `tensile_strength`. Matching predictions leave the precision denominator instead of
counting as hallucinations. After the fix the perfect run scores 1.000.

**Caveat, and why one paper is deliberately absent.** A value-keyed exclusion is only safe when
excluded and in-scope values are well separated. For CF-P11 they collide inside tolerance (58 MPa
is both an excluded summary bar *and* a real GT row), so an entry there would forgive genuine
misses. That paper's scope is handled with a prompt-side note instead.

### 6. Rows with no measurement scoring best

Because alignment uses inputs only (defect 1's fix), a run that emitted **21 rows with every
`tensile_strength` null** scored the paper's **top row-F1 (0.895)** — beating a run with 52 rows at
47 % UTS accuracy. It identified conditions perfectly while reporting no measurements at all.

**Fix:** a predicted row with null `tensile_strength` can never match. The task's first inclusion
criterion is *"has a reported UTS; no UTS ⇒ not a row"*. Such rows stay in the precision
denominator — they were claimed — but earn nothing. The offending run went 0.895 → **0.000**, and
every other run was unchanged.

This fix proved itself immediately on fresh data: in the CF-P18 re-run, gemma emitted 5–6 rows with
correct process parameters and null values throughout. Under the old scorer it would have matched
on alignment and looked competitive.

---

## Reporting consequences

- **Row F1 and UTS accuracy dissociate and must be reported together.** On CF-P18, Mistral scores
  `row F1 = 1.000` with `UTS acc = 0.167` — perfect row identification, wrong numbers. F1 alone
  ranks it above the model that got every value exactly right.
- **Alignment degeneracy must be flagged, not averaged away.** Four papers have GT rows that no
  scored column distinguishes (they vary chamber temperature, annealing temperature — factors
  outside the schema). Their pairing is arbitrary, so per-row UTS is withheld and an order-free
  sorted MAPE is reported instead. A further 11 papers have *some* colliding rows, reported as
  `ambiguous_row_frac`.
- **Regression fixtures.** Ground truth fed back as a prediction must score
  `row_f1 = cell_acc = UTS_acc = 1.000`. This is checked after every scorer change and caught
  several of the above.
