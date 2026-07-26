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

Measured throughput: gemma 0.355 min/page, mistral 0.275, qwen 0.565.

| configuration | runs | wall clock |
|---|---|---|
| 10 papers × 3 models × 3 repeats | 90 | **7.6 h** + ~1.5 h model-load overhead |
| 2 models instead of 3 | 60 | 5.1 h |
| 1 repeat instead of 3 | 30 | 2.5 h |

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

## Deferred

- **Per-paper scope notes break prompt uniformity.** Two papers currently carry them, so their
  scores are not strictly comparable to the rest of the corpus. Footnote required.
- **Ground-truth curation.** One paper appears under-curated (30 rows where the design supports
  more). Not blocking the test run.
- **`audit_findability` is optimistic for zero-valued cells** — a substring test where the value is
  `0` matches almost any document, so 40 such cells are marked findable automatically. The corpus
  ceiling moved only 96.3 % → 96.4 %, so nothing material rests on it, but per-paper 100 % figures
  should not be read as evidence a paper states a neat-PEEK fibre content.
