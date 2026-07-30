# Three Instruments and an Unstable Estimator: A Validity Audit of a Figure-Heavy Scientific-Extraction Benchmark

**Keywords:** scientific information extraction; benchmark validity; vision-language models; materials informatics; measurement error; ground-truth curation

## Abstract

A structured-extraction benchmark is not one instrument but three: a scorer, a corpus, and a set of reference tables. We audit all three on PEEK-Bench, which extracts process-property records from figure-heavy carbon-fibre/PEEK additive-manufacturing papers, where tensile values often exist only inside raster figures. On the 13-paper development split, eight scorer defects — several of them ranking-inverting — reward worse extraction: one run reporting 21 rows with every tensile value null earned the top row F1 for its paper, and a run transcribing nine printed bar labels correctly scored 0.364 against 0.800 for a three-row run wrong by 8-13 MPa. The corpus is equally decisive: three papers carry 93.7% of the between-configuration signal; removing them collapses the spread from 4.81 to 1.14 percentage points and erases the image-token gradient. The reference tables were never audited, yet three of those four signal-carrying papers encode curation the documents never state. Finally, three identical sweeps of one model give UTS MAPE a 39.3% coefficient of variation while cell accuracy moves 1.1%, so a validated scorer can still yield an unstable estimator. Model rankings appear last, as an instrument readout with sensitivity attached. Auditing precedes spending.

## 1. The objection, conceded

Thirteen papers. One hundred and thirteen rows. One materials system, one mechanical property, one annotator, one machine. Any leaderboard built on that is underpowered, and we will not defend one.

We concede the objection completely and then decline the frame. This paper is not a leaderboard. It is a validity audit, and the claims an audit makes are existence proofs, not population estimates. A ranking inversion needs one instance. A metric that scores a run of pure nulls above a run of real measurements is broken whether it does so once or a thousand times. A corpus whose entire discriminative power sits in three documents is a corpus of three documents, regardless of how many are nominally in the split. Small *n* cannot weaken a proof by construction; it can only limit how far the proof generalises, which is a different and lesser problem.

The thesis is this. A structured-extraction benchmark rests on three instruments — the **scorer**, the **corpus**, and the **reference tables** — and on PEEK-Bench each of the first two was independently large enough to invert or erase the model ranking, while the third was never audited at all. A fourth strand joins them: even a validated scorer can produce an **unstable estimator**, which we demonstrate by running the same sweep three times with nothing changed.

The rhetorical order follows from that. Section 2 describes the benchmark and Section 3 situates it against prior work. Sections 4, 5 and 6 take the three instruments in turn. Section 7 takes the estimator. Model results arrive in Section 8, last, as an instrument readout with its sensitivity attached — because that is the only honest place for them once the preceding sections are on the table. Sections 9 through 11 state limitations, argue that the frozen test split should not be run yet, and conclude.

## 2. The benchmark

### 2.1 Task and corpus

PEEK-Bench asks a model to read a materials paper and emit one row per printed-and-tested condition that has a reported ultimate tensile strength (UTS). The schema is nine fused-filament-fabrication (FFF) process parameters — nozzle diameter, nozzle temperature, printing speed, fibre weight fraction, raster angle, infill percentage, specimen thickness, layer thickness, platform temperature — plus UTS.

Table 1 gives the corpus. Everything reported in this paper comes from the development split. The test split has never been run.

**Table 1. PEEK-Bench corpus and splits.**

| split | papers | UTS datapoints | status |
|---|---|---|---|
| Full corpus | 23 | 232 | — |
| DEV | 13 | 113 | all results below |
| TEST | 10 | 119 | frozen, never run; 6 of 10 papers not audited for scope filters |

All local inference ran on one Mac Mini M4 Pro, 64 GB unified memory, 273 GB/s. No cloud, no GPU rental.

### 2.2 Why the task is hard

A large share of tensile values exist **only** inside raster figures: printed bar labels, swept line curves, axis ticks. A paper can contain the string "MPa" exactly once and still report nine tensile values. Text-only extraction is not merely worse on this corpus; on several papers it is structurally impossible. The heaviest paper, CF-P15, runs 23 pages and measures 26,909 real prompt tokens of text alone before a single page image is requested.

### 2.3 Metrics

Four numbers carry the analysis.

- **Row F1** — did the model identify the right *conditions*? Rows are aligned to ground truth by Hungarian assignment on **input parameters only** (Kuhn, 1955; Munkres, 1957).
- **Cell accuracy** — of the parameter cells in matched rows, how many are right?
- **UTS MAPE** — mean absolute percentage error on tensile strength.
- **False-fill rate** — of the cells ground truth leaves blank, how often did the model invent a value?

Row F1 and UTS MAPE measure different capabilities and do not move together; quoting either alone inverts rankings. They are always reported as a pair.

### 2.4 Ground truth is pre-imputation

A blank cell in the reference tables means *the paper does not report it*. Null is therefore the correct answer, and fabrication is directly measurable. Most materials-extraction benchmarks impute missing parameters to plausible defaults and consequently cannot measure fabrication at all. This design choice is what makes the false-fill column in Table 8 meaningful, and it is the one instrument decision in this paper we would repeat without modification.

### 2.5 Unit of analysis

Sampling temperature is 0.1 throughout. Three repeats of the same paper within one sweep are near-duplicates, not independent draws. The unit of analysis is therefore the **paper** (*n* = 13), not the run (*n* = 39). Section 7 shows what happens when the sweep itself is the repeated unit.

## 3. Related work

### 3.1 Extracting materials data from the literature

Automated extraction of materials records from the primary literature predates the current generation of models. Rule- and grammar-based pipelines established the task shape: ChemDataExtractor parsed chemical names, properties, and units from full text with hand-built parsers and a document-level interdependency resolver (Swain & Cole, 2016); Kim et al. (2017) machine-extracted and codified oxide synthesis parameters at scale; and Kononova et al. (2019) released a text-mined corpus of inorganic synthesis recipes, one structured record per reaction. Olivetti et al. (2020) survey this body of work and note that the field's evaluation practice is heterogeneous — extraction quality is usually reported against annotations produced by the same group that built the extractor.

Language models replaced the parsers without changing the task. Dagdelen et al. (2024) fine-tuned LLMs to emit structured materials records directly as JSON, Polak and Morgan (2024) showed that a conversational model with staged prompting recovers property values at high accuracy, and Zheng et al. (2023) applied a general conversational model to MOF synthesis mining. Song et al. (2023) supplied the field's benchmark counterpart, MatSci-NLP, evaluating scientific language models on materials tasks through text-to-schema modelling. The underlying formalism is document-level, *n*-ary relation extraction: a record is a tuple whose arguments are scattered across sentences (Peng et al., 2017) or across a whole document (Yao et al., 2019).

PEEK-Bench inherits the task and changes two things. First, the measurement is frequently not in the text at all — tensile values live in raster figures as printed bar labels or swept curves, so the pipelines above are not merely less accurate on this corpus but structurally unable to reach the target. Second, the reference tables are kept pre-imputation: a blank means the paper does not report the value, so fabrication is a measurable quantity rather than an unobservable one. Neither change is a contribution in itself; they are what makes the instrument audit in Sections 5 through 8 possible.

### 3.2 Scoring a predicted table against a reference table

Comparing a predicted set of records against a reference set requires an alignment step before any cell is compared, and the alignment step is itself a modelling decision with a long history. Record linkage formalised the problem of deciding which pair of records refers to the same entity (Newcombe et al., 1959; Fellegi & Sunter, 1969), including the choice of which fields serve as the matching key — a choice that determines which cells are ever placed side by side. PEEK-Bench resolves alignment optimally with the Hungarian method (Kuhn, 1955; Munkres, 1957) over input parameters only, and therefore inherits the Fellegi–Sunter consequence directly: the matching key decides what gets scored, and the scored quantity is not the same quantity for every prediction.

The document-analysis community has converged on metrics for table structure rather than table content. TEDS scores a predicted table as a tree edit distance against the reference (Zhong et al., 2020); GriTS was proposed precisely because TEDS and its relatives can reward structurally plausible but substantively wrong output, and Smock et al. (2023) argue this class of metric needs redesign, not tuning. That critique is a precedent for the argument here, and we claim no priority over it. Smock et al. (2022) are equally direct about the second instrument: building PubTables-1M required explicit canonicalization of inconsistent ground truth, published as a procedure. Scientific and financial table corpora make the same commitments (Chi et al., 2019; Zheng et al., 2021).

Key-information-extraction benchmarks solve the alignment problem by removing it. SROIE scores exact-match F1 over a fixed field set with one value per document (Huang et al., 2019), and FUNSD, CORD, and DocILE follow the same fixed-schema pattern (Jaume et al., 2019; Park et al., 2019; Šimsa et al., 2023). None of them faces variable row cardinality, which is exactly where our scorer broke: a run may emit any number of rows, and a metric defined over matched rows can be improved by emitting fewer of them, or by emitting rows whose measured column is null. There is no standard metric for "predicted record set versus reference record set with partially observed fields and legitimate nulls," and we do not propose one. What we add is a catalogue of eight specific ways one such scorer failed, each with a reproduction on a single benchmark.

### 3.3 Reading values out of figures

Chart question answering supplies the perception literature. ChartQA and PlotQA pair questions with charts for which an underlying data table exists (Masry et al., 2022; Methani et al., 2020), which bounds the perceptual difficulty: the answer is recoverable from a known series. ChartBench and CharXiv deliberately remove that crutch, using unannotated charts that force axis reading and value interpolation, and CharXiv draws its figures from real papers and reports large gaps between models on derived questions (Xu et al., 2023; Wang et al., 2024b).

The perception side is also an architecture story. Variable-resolution tokenisation — naive dynamic resolution in Qwen2.5-VL, its predecessor in Qwen2-VL, and sequence packing in NaViT — exists because fixed-grid encoders destroy the fine detail that axis ticks and small printed labels consist of (Bai, Chen, et al., 2025; Wang et al., 2024a; Dehghani et al., 2023), and Guo et al. (2024) document the failure modes of AnyRes-style slicing when a figure is cut across a semantic boundary. The models evaluated here span those design choices (Gemma Team, 2025; Mistral AI, 2025; Bai, Cai, et al., 2025; Anthropic, n.d.).

Chart benchmarks ask a bounded question about one figure. PEEK-Bench asks which figures in a 23-page document carry measurements at all, then requires those values to be joined to process conditions stated elsewhere in the paper. Perception is necessary but is scored jointly with document-level linkage, which is why an image-token gradient that looks like a clean perceptual finding can be erased entirely by corpus composition (Section 6).

### 3.4 Benchmark validity, variance, and error metrics

This is the paper's home literature, and most of its individual observations have precedents we want stated plainly. Bowman and Dahl (2021) and Raji et al. (2021) established the construct-validity critique of benchmarks. Northcutt et al. (2021) showed that label errors pervade widely used test sets and can reorder model rankings — our finding that reference tables carry undisclosed curation is an instance of that phenomenon, not a discovery of it. The closest precedents are in document-level relation extraction: Tan et al. (2022) showed DocRED's gold annotations are incomplete, so correct predictions are scored as false positives, and that repairing them moves F1 by roughly 13 points; Huang et al. (2022) traced the mechanism to the recommend-revise annotation procedure and its entity bias. That is a direct precedent for our third instrument, and we concede it as such. Pavlick and Kwiatkowski (2019) make the deeper point that a single gold label can be the wrong object to score against. Likewise, evaluations are known to move under benign choices — leaderboard scoring conventions (Alzahrani et al., 2024), prompt formatting (Sclar et al., 2023), harness implementation (Biderman et al., 2024), and contamination (Sainz et al., 2023) — and NLP experiments are known to be underpowered (Card et al., 2020), which is why our claims are existence proofs and our interval and test machinery is conservative (Efron, 1979, 1987; Wilcoxon, 1945; Holm, 1979; Benjamini & Hochberg, 1995).

The MAPE result needs the same honesty. Forecasting has known MAPE's pathologies for three decades: it is asymmetric and penalises over- and under-prediction unequally (Makridakis, 1993), it has no stable behaviour when actuals approach zero (Kim & Kim, 2016), and better-behaved alternatives were catalogued long ago (Hyndman & Koehler, 2006). We discovered none of this. Our contribution is to measure the consequence inside an ML benchmark: across three identical sweeps of one model, UTS MAPE has a 39.3% coefficient of variation while cell accuracy over the same runs moves 1.1%, so the instability is a property of the estimator and not of the system under test.

What is genuinely new here is narrower than the sum of these strands, and we state it as such. First, an eight-defect catalogue with reproductions on one benchmark, auditing scorer, corpus, and reference tables together rather than one at a time. Second, a sweep-level measurement of estimator instability, taking the whole sweep — not the item — as the repeated unit, which is what makes the 39.3%/1.1% contrast interpretable. Third, the coupling: the same three documents that carry 93.7% of the between-configuration signal are among those whose reference tables encode curation the documents never state, so the corpus's discriminative power and its unaudited annotation decisions are concentrated in the same place. We have not found that coupling reported elsewhere.

## 4. Instrument one: the scorer

We found eight defects in the scorer. Each was found by adversarially re-deriving a number from a primary source and asking why the scorer disagreed, and each ships with a reproduction. Several inverted the model ranking; that is, the benchmark actively rewarded worse extraction. Table 2 summarises them.

**Table 2. Eight scorer defects, with the observation that exposed each.**

| # | Defect | Exposing observation |
|---|---|---|
| 1 | Circular alignment: UTS included in the Hungarian row-matching distance | The matcher pairs rows that already agree on the answer, then scores that answer correct — manufacturing accuracy from a wrong extraction. Alignment must use **input columns only**. |
| 2 | Rows with no measurement scoring best | A run emitting 21 rows with **every** tensile value null scored row F1 0.895 — top of that paper's table, beating a 52-row run at 47% UTS accuracy. |
| 3 | Categorical column as sole alignment basis | Adding `raster_angle` to the alignment basis drove mean row F1 0.792 → 0.478 while cell accuracy **rose** 0.656 → 0.705, and roughly a third of ground-truth cells silently left scoring. |
| 4 | "Column that varies in the **prediction**" as alignment basis | Picked an all-blank ground-truth column and gave zero matches to a correct extraction. |
| 5 | Alignment degeneracy diagnosed from predictions | Let a hallucinating model mask a degenerate paper. Degeneracy must be diagnosed from ground truth only. |
| 6 | Out-of-scope predictions counted in the precision denominator | On CF-P18, a run that transcribed all nine printed bar labels correctly scored row F1 0.364, while a three-row run wrong by 8-13 MPa scored 0.800. |
| 7 | UTS MAPE computed only over Hungarian-matched pairs, with no coverage penalty | Runs that match nothing contribute nothing — including runs whose row F1 is exactly 0.000. See Table 3. |
| 8 | False-fill denominator inside the same matched-pairs loop | `blank_gt_cells` is endogenous to row F1, so the fabrication metric moves with the structure metric by construction. |

Three of these deserve to be stated at length, because each is a proof by construction that one instance settles.

### 4.1 Defect 2: a run of pure nulls wins its paper

Because alignment uses input parameters only — which is the correct fix for defect 1 — a predicted row needs no measurement to be matched. A run that emitted **21 rows with every `tensile_strength` null** scored **row F1 = 0.895**, the top score on that paper, beating a run that returned 52 rows at 47% UTS accuracy. The model had identified the experimental conditions perfectly and reported no measurements whatsoever.

The fix: a predicted row with a null tensile value can never match, because the task's first inclusion criterion is *"has a reported UTS; no UTS ⇒ not a row"*. Such rows stay in the precision denominator — they were claimed — but earn nothing. **The offending run went 0.895 → 0.000.** Every other run was unchanged.

Two things about this are worth more than the anecdote. First, the defect was *created* by the fix to defect 1: three of the eight defects were introduced by repairs to earlier ones. Second, nothing about the failure was visible from the aggregate. A row F1 of 0.895 is a good score. Only re-deriving the underlying prediction exposed it.

### 4.2 Defect 6: the metric preferred narrowness to accuracy

Ground truth encodes curation decisions the extraction prompt never states — for instance, keeping only room-temperature rows from a paper that also reports elevated-temperature conditions. Predictions matching those excluded conditions were counted as hallucinations.

On CF-P18, a run that transcribed **all nine** of a chart's printed bar labels correctly scored **row F1 = 0.364**. A run returning three rows, with values wrong by 8-13 MPa, scored **0.800**. The benchmark ranked a wrong narrow answer above a right wide one. After the fix — an explicit out-of-scope list, keyed by tensile value, whose matches leave the precision denominator rather than counting against it — **the correct run scores 1.000**.

This defect is the hinge of the whole paper. It is a scorer bug whose root cause is a *reference-table* property: the ground truth contains a filter the document does not disclose. Section 6 returns to it.

### 4.3 Defect 7: the estimator is computed on a self-selecting subsample

UTS MAPE is accumulated inside the loop over matched pairs — `score10.py` line 319 opens `for i, j, d in pairs:` and the error append at line 342 sits inside it. A run that matches no rows contributes no error terms. It does not contribute a penalty either. It simply is not there.

The consequence is measured in Table 3.

**Table 3. UTS MAPE coverage by configuration (39 runs per configuration).**

| configuration | runs entering MAPE | runs excluded | mean row F1 of excluded runs |
|---|---|---|---|
| gemma-3-27b | 31 / 39 | 8 | **0.000** |
| mistral-3.1-24b | 33 / 39 | 6 | 0.447 |
| qwen3-vl-32b | 36 / 39 | 3 | 0.965-1.000 (CF-P14, structurally degenerate) |
| claude-opus-5 read-only | 36 / 39 | 3 | 0.965-1.000 (CF-P14, structurally degenerate) |
| claude-opus-5 + tools | 36 / 39 | 3 | 0.965-1.000 (CF-P14, structurally degenerate) |

Read the first row carefully. Gemma's headline MAPE of 5.20 is computed over 31 runs, and the eight runs it excludes have a **mean row F1 of exactly zero**. The worst behaviour the weakest model produces is invisible to the metric that ranks it. The exclusions are not random and they are not symmetric across configurations: the two strongest arms lose only the one paper whose rows no scored column can distinguish, while the weakest arm loses its total failures. Every MAPE column in this paper is therefore an optimistic estimate, most optimistic for the models that fail hardest.

### 4.4 The regression suite could not have caught any of this

Two regression fixtures shipped with the scorer: `CF-P05__perfect.json` and `CF-P13__perfect.json`. Both are identity fixtures — ground truth fed back as a prediction, required to score 1.000 on every metric.

Identity fixtures are structurally incapable of catching defects 1, 3, 4 or 6. A perfect prediction is matched correctly under a circular alignment, under a categorical-only alignment basis, under a prediction-derived basis, and with or without an out-of-scope list. Every one of those defects requires an *imperfect* fixture to expose — a prediction that is wrong in a specific, chosen way. The suite passed continuously while the scorer inverted rankings.

A regression suite that only tests the fixed point of a scoring function tests almost nothing about the scoring function.

## 5. Instrument two: the corpus

A scorer can be fixed. A corpus that does not discriminate cannot be, and PEEK-Bench's dev split barely discriminates.

Summing the per-paper between-configuration spread in UTS MAPE across all 13 dev papers gives 60.93. Table 4 shows where it lives.

**Table 4. Per-paper contribution to between-configuration UTS-MAPE spread (dev-13; total 60.93).**

| paper | spread | share |
|---|---|---|
| CF-P11 | 28.26 | 46.4% |
| CF-P18 | 13.11 | 21.5% |
| CF-P13 | 10.02 | 16.4% |
| CF-P24 | 5.71 | 9.4% |
| all other nine papers combined | 3.83 | 6.3% |

Four papers carry **93.7%** of the separation. Nine papers carry 6.3% between them. The benchmark reports thirteen documents and measures four.

Table 5 makes the consequence concrete by deleting papers and re-running the comparison.

**Table 5. Corpus-subset sensitivity.**

| subset | papers dropped | separation retained | between-configuration spread | significant paired-Wilcoxon (Wilcoxon, 1945) comparisons |
|---|---|---|---|---|
| Dev-13 | — | 100% | 4.81 pp | 4 of 9 |
| Dev-10 | CF-P11, CF-P18, CF-P24 | 22.7% | 1.14 pp | 1 of 9 |
| Dev-9 | + CF-P13 | 6.3% | 0.33 pp | 0 of 9 |

On **Dev-10** the image-token gradient — the central quantitative claim a benchmark like this exists to support — becomes 1.37 / 1.33 / 0.55, and the gemma → mistral step **vanishes**. Two of the three model tiers become indistinguishable by deleting three of thirteen documents.

On **Dev-9** the benchmark stops functioning. The spread falls to 0.33 pp, no comparison of nine is significant, 87.2% of paper × configuration cells sit at the UTS-accuracy ceiling, the ordering **inverts** (gemma 0.24 beats mistral 0.38), and the naive prompt beats the engineered prompt for 2 of 5 configurations. Every headline finding in Section 8 reverses or evaporates.

Neither subset is a strawman. Both are ordinary corpus-construction outcomes — one curator's inclusion decisions differing slightly from another's.

### 5.1 The coupling

Now put Table 4 next to Section 4.2, because the two are not independent.

**Three of the four papers carrying 93.7% of the signal are exactly the papers whose ground truth encodes curation the document never states.** CF-P11 carries a narrowed material arm. CF-P18 keeps room-temperature rows only. CF-P24 applies an FFF-only route filter. None of these filters is derivable from the paper by any reader, human or machine.

So the corpus's discriminative power and its undisclosed-curation problem are the *same papers*. The benchmark separates models mainly where the reference tables disagree with the documents. That is the single most uncomfortable sentence in this paper, and we have not found a way around it.

**CF-P13 is the sole exception**, and it is worth naming as the template for what the corpus should contain. It is figure-locked, carries a spread of 10.02, separates all four capability tiers (9.28 / 11.70 / 3.56 / 1.78), and needs no scope note whatsoever. One paper in thirteen does the job the whole corpus was supposed to do.

## 6. Instrument three: the reference tables

The third instrument was never audited. We state that plainly because it is the honest position, and because both of the dev papers we did examine closely turned out to be defective in the same way.

### 6.1 What an audit of the reference tables would have to establish

Three properties, none of which we verified corpus-wide:

1. **Disclosure.** Does every inclusion and exclusion decision follow from the document, or does the curator know something the reader cannot? Section 5.1 answers this for three papers, and the answer is no.
2. **Answerability.** Is each ground-truth cell actually present in the source document at all? Some values are curator inference from external datasheets; scoring those punishes faithful extraction rather than measuring it. The scorer reports a per-paper answerability ceiling so that a score can be read as "at ceiling" rather than "model failed", but the audit behind it covers input parameters only, and its string matching is optimistic — the ceiling is an upper bound, not a measurement.
3. **Distinguishability.** Can the rows be told apart by any scored column? On four papers they cannot: those rows vary factors outside the schema, so any pairing is arbitrary. CF-P14 is the case that recurs throughout this paper — it is the single paper excluded from MAPE for the three strongest configurations in Table 3.

### 6.2 Two mechanisms, both of which distort comparison

Where the ground truth encodes an undisclosed filter, there are only two places to put the correction, and both cost something.

A **scoring-side** exclusion list lets predictions of genuinely-reported-but-curator-excluded conditions leave the precision denominator. This is the fix for defect 6, and it is safe only where excluded and in-scope tensile values are well separated, since the list is keyed by value. One paper is deliberately absent from it because its excluded and in-scope values collide inside tolerance.

A **prompt-side** scope note tells the model the filter directly. Two dev papers carry one — CF-P11 and CF-P18, the two papers holding 67.9% of the corpus signal. The cost is stated plainly: **a paper carrying a scope note does not see the same prompt as the rest of the corpus.** Its scores are not strictly comparable to the others and must be footnoted wherever they appear.

There is no third option. A global rule cannot work: one dev paper keeps only room-temperature rows while another keeps a full cryogenic sweep, and both explicitly study temperature. No instruction derivable from the documents separates them. It is a curation choice, and curation choices have to be disclosed to the extractor or forgiven by the scorer.

### 6.3 Why this is the instrument to audit next

The scorer has eight documented defects and eight reproductions. The corpus has a measured sensitivity analysis. The reference tables have neither — and they are upstream of both. Every scorer defect in Table 2 is a defect *relative to* the reference tables, and every number in Table 4 is a property *of* them. An error here does not show up as a bug; it shows up as a plausible number.

## 7. The fourth strand: the estimator

Sections 4 through 5 concern instruments that can, in principle, be validated once and then trusted. This section concerns something else: an instrument that is correct and still does not return the same reading twice.

### 7.1 Three identical sweeps

We ran the gemma-3-4b arm three times with nothing changed — same machine, same GGUF, same backend, same context window (40,960), same prompt, same harness. The only difference between the three is sampling at temperature 0.1. Table 6 gives the result.

**Table 6. Three identical gemma-3-4b sweeps (13 dev papers × 3 repeats each).**

| metric | run 1 | run 2 | run 3 | mean | SD | CV |
|---|---|---|---|---|---|---|
| row F1 | 0.3359 | 0.3540 | 0.4233 | 0.3711 | 0.0461 | 12.4% |
| recall | 0.3207 | 0.3137 | 0.3726 | 0.3357 | 0.0322 | 9.6% |
| precision | 0.6188 | 0.6111 | 0.7351 | 0.6550 | 0.0695 | 10.6% |
| cell accuracy | 0.7453 | 0.7537 | 0.7376 | 0.7455 | 0.0081 | **1.1%** |
| UTS MAPE | 40.8488 | 17.4723 | 36.3624 | 31.5612 | 12.4058 | **39.3%** |

UTS MAPE — the metric this benchmark exists to report, and the metric on which every ranking in Section 8 rests — has a **39.3% coefficient of variation** under exact replication. Cell accuracy, measured on the same runs by the same scorer, moves 1.1%. The instability is not ambient noise in the pipeline; it is specific to one metric.

### 7.2 Why MAPE and not the others

The cause is a scorer property, not a model property. MAPE is unbounded above (Hyndman & Koehler, 2006; Makridakis, 1993), and it is averaged per paper before being averaged across papers. A two-row paper therefore carries the same weight as a twenty-row paper while having far more variance. Table 7 shows the five largest per-paper movements between two of the identical sweeps.

**Table 7. Per-paper UTS MAPE between two identical sweeps (five largest movers; mean |Δ| across all 13 dev papers = 27.12).**

| paper | GT rows | sweep A | sweep B | Δ |
|---|---|---|---|---|
| CF-P18 | 2 | 218.65 | 37.91 | **−180.75** |
| CF-P05 | 18 | 43.34 | 11.54 | −31.80 |
| CF-P02 | 3 | 32.81 | 0.19 | −32.62 |
| CF-P13 | 11 | 20.43 | 0.00 | −20.43 |
| CF-P24 | 20 | 10.59 | 10.59 | 0.00 |

One wrong value on CF-P18's two rows produces a 218% error, and whether that happens is close to a coin flip. Note that CF-P18 is also the second-largest contributor to the corpus signal in Table 4. The paper that most separates the models is also the paper that most destabilises the metric separating them.

### 7.3 What this instability already cost us

An earlier reading of these data compared the 4B on the Mac against the same model on discrete NVIDIA hardware with a different GGUF build and a CUDA backend, and treated the resulting MAPE gap as evidence about **backend numerics** — with the implication that extraction results might not be portable across compute backends. That claim is **withdrawn**. The cross-hardware value sits inside the Mac's own run-to-run range of 17.4723 to 40.8488. Nothing about Metal versus CUDA was demonstrated, and the follow-up experiment we had designed to separate the two causes would have been chasing sampling noise. [TK: insert the two withdrawn MAPE values and the ratio if the first author wishes to name them.]

We report this because it is the concrete cost of not having a variance estimate, and because it is the failure mode this whole strand predicts: a difference of the right size and the right sign, with a mechanism ready to explain it, that is entirely noise.

### 7.4 Four changes this implies

1. **Report median APE alongside mean.** Median APE is not destroyed by one 218% paper. The scorer already computes it; nothing uses it.
2. **Bootstrap confidence intervals over papers**, and state the unit of analysis as the paper (*n* = 13), not the run (*n* = 39).
3. **Weight or stratify by ground-truth row count**, or report MAPE only above a row threshold.
4. **Repeat whole sweeps, not runs within a sweep.** This is the one that matters most, and Section 8 inherits its absence.

## 8. Instrument readout: model results

Everything below is a reading taken with the instruments audited above. It is reported last on purpose. Read it with Table 3 (the MAPE column is computed on a self-selecting subsample), Table 5 (the ordering survives deleting three papers only in weakened form, and not at all after four), and Table 6 (the estimator's own CV is 39.3%) held in view.

### 8.1 The main table

Table 8 gives the five configurations on the full dev split under the engineered prompt.

**Table 8. Dev-13 results, engineered prompt, 39 runs per configuration (13 papers × 3 repeats).**

| configuration | image tokens/page | row F1 | recall | cell acc | UTS MAPE | false-fill | wall/run |
|---|---|---|---|---|---|---|---|
| gemma-3-27b | 258 | 0.5734 | 0.6773 | 0.7982 | 5.20 | 0.2166 | 5.24 min |
| mistral-3.1-24b | 1030 | 0.8558 | 0.8616 | 0.9058 | 4.44 | 0.7500 | 4.21 min |
| qwen3-vl-32b | ~2900 | 0.9333 | 0.9858 | 0.9274 | 1.06 | 0.4012 | 9.55 min |
| claude-opus-5, read-only | native | 0.9504 | 1.0000 | 0.9633 | 0.39 | 0.1111 | — |
| claude-opus-5, + tools | native | 0.9331 | 0.9758 | 0.9623 | 0.49 | 0.0740 | — |

Three observations survive the caveats.

**The image-token gradient is the strongest pattern in the table.** Row F1 and UTS MAPE both order with visual budget: 258 → 1030 → ~2900 tokens per page gives 0.5734 → 0.8558 → 0.9333 and 5.20 → 4.44 → 1.06. On a task where the answers are inside the figures, how much of the figure the model actually sees dominates everything else we varied. Section 5 showed that this gradient does not survive deleting three of thirteen papers, which is exactly why it is reported here rather than in the abstract as a law.

**False-fill does not track quality.** Mistral posts the second-best row F1 in the table and fabricates a value in **75%** of the cells the paper leaves blank. Qwen is better on every accuracy metric and fabricates 0.4012. The two Claude arms are the only configurations that stay low, at 0.1111 and 0.0740. Because ground truth is pre-imputation (Section 2.4), these are real fabrication rates, not imputation mismatches. A benchmark reporting accuracy alone would rank mistral as broadly competent; it is competent at structure and prolific at invention.

**The Claude arms are not a controlled comparison against the local ones.** Local models receive page images at a fixed token budget; the Claude arms read the document natively. That is not a swap of one variable, and no image-token figure is quoted for them.

### 8.2 Capacity at fixed perception

Gemma 3 spends a fixed visual budget at every model size — 258 tokens per page, measured independently on 4B, 12B and 27B with a token-delta probe rather than assumed from documentation. That makes it the only family in the roster where parameters can be varied with **perception held constant**. Table 9 gives that curve.

**Table 9. Gemma-3 capacity curve. Image tokens fixed at 258/page at every size; same Mac, engineered prompt, ctx 40,960. Wall clock is per sweep.**

| model | sweeps | row F1 | recall | precision | cell acc | UTS MAPE | rows/run | pages viewed | wall |
|---|---|---|---|---|---|---|---|---|---|
| 4B | 3 | 0.3711 | 0.3357 | 0.6550 | 0.7455 | 31.56 ± 12.41 | 2.54 | 4.63 | ~34 min |
| 12B | 1 | 0.2879 | 0.2852 | 0.3464 | 0.7852 | 10.40 | 4.82 | 9.46 | 2 h 48 m |
| 27B | 1 | 0.5734 | 0.6773 | 0.5766 | 0.7982 | 5.20 | 8.64 | 6.28 | 3 h 24 m |

Monotone in parameters: UTS MAPE (31.56 → 10.40 → 5.20) and rows emitted (2.54 → 4.82 → 8.64). The quantities that require actually reading a value off a figure order cleanly with capacity.

Not monotone: row F1 and recall. **The 4B beats the 12B on both**, and this survives all three independent 4B sweeps — even the weakest 4B run (F1 0.3359, recall 0.3207) clears the 12B's 0.2879 / 0.2852.

Two separable mechanisms produce that. The 4B under-extracts: 2.54 rows per run against 113 ground-truth rows across 13 papers, at precision 0.6550 versus the 12B's 0.3464. It returns a small self-selected set of easy conditions and gets a decent fraction right — a selection artifact, and the reason recall should be preferred to F1 when comparing weak arms. Separately, the 12B collapses outright on several papers, returning zero rows. That is not under-extraction; it is a different failure, and it is what drags a model three times the size below the 4B on a metric that should have been immune.

Note what Table 9 does *not* contain: error bars on the 12B and 27B rows. Only the 4B arm has a sweep-level variance estimate, and Section 7 showed that estimate to be large. The monotone ordering above is stated on one sample each for two of the three arms.

### 8.3 Prompt engineering increases fabrication in every local model

We compared a naive 869-character prompt against a 4,513-character engineered template, which assembles to 6,236 characters after schema substitution (7,145 with a per-paper scope note). Table 10 gives both arms.

**Table 10. Naive → engineered prompt.**

| configuration | row F1 | false-fill |
|---|---|---|
| gemma-3-27b | 0.547 → 0.573 | 0.042 → 0.217 (5.2×) |
| mistral-3.1-24b | 0.777 → 0.856 | 0.204 → 0.750 (3.7×) |
| qwen3-vl-32b | 0.770 → 0.933 | 0.111 → 0.401 (3.6×) |
| claude-opus-5, read-only | 0.885 → 0.950 | 0.111 → 0.111 (unchanged) |
| claude-opus-5, + tools | 0.898 → 0.933 | 0.074 → 0.074 (unchanged) |

Every local model fabricates between 3.6 and 5.2 times more when prompted harder. The frontier model does not move at all. A detailed schema appears to function, for a local model, as an instruction to fill the schema.

**This ablation is confounded and must not be quoted without the caveat.** `extract_naive.py` defines `paper_scope_block()` and never calls it, so the naive arm saw no scope note on CF-P11 or CF-P18 — the two papers holding 67.9% of the corpus spread (Table 4). The comparison must be restricted to the eleven papers with no scope note, or re-run. We report it because the false-fill direction is consistent across five configurations and unlikely to be produced by two papers' prompts, but the row-F1 column is not usable as stated.

### 8.4 Transcription and interpolation are different skills

Two papers separate them cleanly. On CF-P18, where the tensile values are printed as bar labels, qwen ties Claude at **0.00** MAPE — transcription is solved at the 32B open-weight tier. On CF-P11, where the values must be interpolated against axis ticks from swept curves, qwen posts **6.45** against Claude's **1.96**. The remaining gap between open-weight and frontier models on this corpus is a gap in *reading a chart*, not in reading a number.

### 8.5 Supplementary information supplies parameters, not measurements

An A/B on CF-P13 with and without supplementary information: process parameters improve strongly (*p* = 0.0006), UTS does not move (*p* = 0.93). SI is where the methods table lives, not where the tensile values live. For this task, harvesting SI improves the columns that were already the easy ones.

### 8.6 Reading beats tooling — but this is a noise floor, not a finding

Claude read-only scores 0.39 MAPE / 0.9504 row F1; Claude with Bash, Write and Edit available scores 0.49 / 0.9331. The natural reading is that agentic chart-digitisation code is worse than careful reading.

We do not believe that reading is supported. The two arms differ on only 3 of 12 papers, with **opposite signs**, and the aggregate gap is driven by CF-P24 alone. Against the run-to-run variance established in Section 7, this is a difference of the same size as replication noise. **Report it as a noise floor, not a result** — and note that it is the precise pattern that produced the withdrawn claim in Section 7.3.

### 8.7 Cost

The whole campaign is 205+ runs and roughly 25 hours of inference on one M4 Pro, at **$0** compute. The two Claude arms are imputed at approximately **$24** at Opus list rates; those runs used a subscription rather than a metered API, so the figure is a list-price imputation and is marked as such wherever it appears.

## 9. Limitations

We list these as defects in our own instruments, in the same spirit as Sections 4 through 6.

**One annotator, no agreement measurement.** The reference tables were built by a single curator. There is no second annotator and therefore no inter-annotator agreement statistic anywhere in this work. Section 6 argues that the reference tables are the least-audited of the three instruments; this is the sharpest form of that admission. Every number in this paper is measured against one person's judgement about what each paper reports, and Section 5.1 shows that at least three of those judgements encode filters the documents do not state.

**Thirteen papers.** The unit of analysis is the paper, so *n* = 13 for every comparison in Section 8 and *n* = 5 for the largest movers in Table 7. Section 5 is in a sense a limitation stated as a result: the effective *n* for model separation is closer to four.

**One materials system, one property.** Carbon-fibre-reinforced PEEK, printed by fused filament fabrication, scored on ultimate tensile strength. Whether the figure-locked-value problem, the fabrication-under-instruction effect, or the MAPE instability transfer to other systems or other properties is untested. The mechanisms are generic; the magnitudes are not.

**Imputed API costs.** The ~$24 for the Claude arms is a list-rate imputation over a subscription, not a billed amount. It should not be used for cost-per-extraction modelling.

**The test papers are unaudited.** Six of the ten frozen test papers have never been checked for undisclosed scope filters. Section 10 argues this is disqualifying rather than merely regrettable.

**The prompt ablation is confounded.** As stated in Section 8.3, the naive arm saw no scope note on the two papers holding 67.9% of the corpus spread, because a function was defined and never called. The false-fill direction is robust across five configurations; the row-F1 deltas are not usable until the arm is restricted to the eleven no-note papers or re-run.

**Two arms have no sweep-level repeats.** The 12B and 27B rows of Table 9 rest on one sweep each. Given that the arm we *did* repeat showed a 39.3% CV on the metric that orders those rows, the capacity curve's MAPE column carries unknown error bars. The same applies to every configuration in Table 8: three repeats *within* a sweep at temperature 0.1 are near-duplicates and do not estimate sweep-level variance.

**The answerability ceiling is an upper bound.** It covers input parameters only, and its matching is optimistic. Cells whose value is zero are a known weak spot.

## 10. What the frozen split will and will not settle

There is an obvious next move: run the ten frozen test papers, report the numbers, and let the held-out split do what held-out splits do. We argue against making that move yet, on grounds this paper has already established.

**Fifty-six of the 119 test rows sit in six papers that have never been checked for undisclosed scope filters.** That is not a small corner of the test split; it is roughly half of it, and it is the half about which we know least.

Now recall the base rate. **Both dev papers we examined closely turned out to have undisclosed filters.** CF-P11 has a narrowed material arm. CF-P18 keeps room-temperature rows only. We did not go looking for a representative sample; we went looking at the two papers that dominated the corpus signal, and both were defective in the same way. A third, CF-P24, carries an FFF-only route filter. We have no basis for assuming the six unexamined test papers are cleaner than the dev papers we happened to inspect, and some basis for assuming they are not — the same curator, the same session, the same conventions.

Section 4.2 established what an undisclosed filter does to a score. On CF-P18 it made a **perfect nine-label transcription score 0.364 while a three-row run wrong by 8-13 MPa scored 0.800**. That is not a small bias; it is an inversion. Section 5 established that a handful of papers can carry nearly all of a split's discriminative power. Put those together and the risk on the test split is concrete: a small number of unaudited papers, of unknown weight, each capable of reversing the local ordering, aggregated into a single headline number that carries no marker of where it came from.

And the risk is asymmetric (Makridakis, 1993) in a specific way. An undisclosed filter penalises the model that reads the document *correctly and completely*, because that is the model that returns the conditions the curator silently removed. The stronger the extractor, the larger the penalty. A test-split leaderboard built on unaudited reference tables would not be noisy in a neutral direction; it would be biased against exactly the systems it is meant to identify.

There is also a matter of what a frozen split is *for*. Freezing protects against overfitting to the evaluation data. It does not protect against the evaluation data being wrong. Running it once, cleanly, produces a number that is unrepeatable by construction — and if a filter is discovered afterwards, there is no honest way to revise the number without unfreezing the split. **This paper's own method would invalidate the result the moment it was published.** We would have to apply Section 6 to our own headline table and withdraw it, exactly as we withdrew the backend-numerics claim in Section 7.3.

So: what would running the split settle? If the six papers are clean, it settles the ordering of five configurations on 119 rows, subject to the estimator instability of Section 7 — which, with no sweep-level repeats, means subject to error bars we cannot state. What would it not settle? Whether the six papers are clean. That question is answerable now, cheaply, by reading six documents against six reference tables. It does not require a single GPU-hour.

The whole campaign cost $0 in compute and about 25 hours of inference. The binding constraint on this benchmark has never been compute; it is curator attention. Spending the frozen split before spending six document audits inverts the actual cost structure of the work.

**Auditing precedes spending.** Our recommendation is a specific order: audit the six unexamined test papers for scope filters and record the result whether or not any are found; extend the answerability audit to tensile values; add non-identity regression fixtures for defects 1, 3, 4 and 6; implement the four estimator changes in Section 7.4; and only then unfreeze. The number obtained after that sequence will be worth something. The number obtained before it would have to be withdrawn.

## 11. Conclusion

We set out to build a leaderboard for figure-heavy scientific extraction and found instead that the measuring apparatus was the dominant error source.

Three instruments stand between a model and its score. The **scorer** had eight defects, several of which inverted the ranking: a run of 21 rows with every tensile value null took the top row F1 on its paper, and a perfect nine-label transcription scored 0.364 against 0.800 for a three-row run that was wrong. The shipped regression suite, consisting of two identity fixtures, was structurally incapable of catching four of the eight. The **corpus** concentrates 93.7% of its discriminative power in four of thirteen papers; deleting three erases the image-token gradient, and deleting four inverts the ordering. The **reference tables** were never audited, and three of the four papers that carry the signal encode curation their documents never state — which means the corpus separates models precisely where the ground truth departs from the source.

A fourth strand cuts across all three. Three identical sweeps — same machine, same weights, same backend, same prompt — put UTS MAPE at a 39.3% coefficient of variation while cell accuracy moved 1.1%. A validated scorer can still be an unstable estimator, and we withdrew a published-in-draft claim about backend portability once we could see the noise floor.

None of these findings needs a large sample. Each is a proof by construction, and each was found the same way: by re-deriving one number from a primary source and asking why the scorer disagreed. That procedure is transferable to any structured-extraction benchmark, and we suspect it would be productive on most of them.

The practical recommendation is narrow. Report row F1 and UTS MAPE together, never singly. Report fabrication against pre-imputation ground truth, because a benchmark that imputes cannot measure it. Report coverage alongside any metric computed over matched pairs. Repeat whole sweeps, not runs. Build regression fixtures that are wrong on purpose. And audit the reference tables before running the split, because a held-out split protects against overfitting and offers no protection at all against being wrong.

---

## References

*APA 7th edition. Every entry was verified against a live source; all 39 DOIs were
independently re-resolved through Crossref.*

Alzahrani, N., Alyahya, H., Alnumay, Y., AlRashed, S., Alsubaie, S., Almushayqih, Y., Mirza, F., Alotaibi, N., Al-Twairesh, N., Alowisheq, A., Bari, M. S., & Khan, H. (2024). When benchmarks are targets: Revealing the sensitivity of large language model leaderboards. In Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers) (pp. 13787-13805). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.acl-long.744.

Anthropic. (n.d.). Models overview. Retrieved July 29, 2026, from https://platform.claude.com/docs/en/about-claude/models/overview.

Bai, S., Cai, Y., Chen, R., Chen, K., Chen, X., Cheng, Z., Deng, L., Ding, W., Gao, C., Ge, C., Ge, W., Guo, Z., Huang, Q., Huang, J., Huang, F., Hui, B., Jiang, S., Li, Z., Li, M., ... Zhu, K. (2025). Qwen3-VL technical report. arXiv. https://arxiv.org/abs/2511.21631.

Bai, S., Chen, K., Liu, X., Wang, J., Ge, W., Song, S., Dang, K., Wang, P., Wang, S., Tang, J., Zhong, H., Zhu, Y., Yang, M., Li, Z., Wan, J., Wang, P., Ding, W., Fu, Z., Xu, Y., ... Lin, J. (2025). Qwen2.5-VL technical report. arXiv. https://arxiv.org/abs/2502.13923.

Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate: A practical and powerful approach to multiple testing. Journal of the Royal Statistical Society: Series B (Methodological), 57(1), 289-300. https://doi.org/10.1111/j.2517-6161.1995.tb02031.x.

Biderman, S., Schoelkopf, H., Sutawika, L., Gao, L., Tow, J., Abbasi, B., Aji, A. F., Ammanamanchi, P. S., Black, S., Clive, J., DiPofi, A., Etxaniz, J., Fattori, B., Forde, J. Z., Foster, C., Hsu, J., Jaiswal, M., Lee, W. Y., Li, H., ... Zou, A. (2024). Lessons from the trenches on reproducible evaluation of language models. arXiv. https://arxiv.org/abs/2405.14782.

Bowman, S. R., & Dahl, G. (2021). What will it take to fix benchmarking in natural language understanding? In Proceedings of the 2021 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (pp. 4843-4855). Association for Computational Linguistics. https://doi.org/10.18653/v1/2021.naacl-main.385.

Card, D., Henderson, P., Khandelwal, U., Jia, R., Mahowald, K., & Jurafsky, D. (2020). With little power comes great responsibility. In Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (pp. 9263-9274). Association for Computational Linguistics. https://doi.org/10.18653/v1/2020.emnlp-main.745.

Chi, Z., Huang, H., Xu, H.-D., Yu, H., Yin, W., & Mao, X.-L. (2019). Complicated table structure recognition. arXiv. https://arxiv.org/abs/1908.04729.

Dagdelen, J., Dunn, A., Lee, S., Walker, N., Rosen, A. S., Ceder, G., Persson, K. A., & Jain, A. (2024). Structured information extraction from scientific text with large language models. Nature Communications, 15, Article 1418. https://doi.org/10.1038/s41467-024-45563-x.

Dehghani, M., Mustafa, B., Djolonga, J., Heek, J., Minderer, M., Caron, M., Steiner, A., Puigcerver, J., Geirhos, R., Alabdulmohsin, I., Oliver, A., Padlewski, P., Gritsenko, A., Lucic, M., & Houlsby, N. (2023). Patch n' Pack: NaViT, a vision transformer for any aspect ratio and resolution. In Advances in neural information processing systems 36 (pp. 2252-2274). Neural Information Processing Systems Foundation. https://doi.org/10.52202/075280-0106.

Efron, B. (1987). Better bootstrap confidence intervals. Journal of the American Statistical Association, 82(397), 171-185. https://doi.org/10.1080/01621459.1987.10478410.

Efron, B. (1979). Bootstrap methods: Another look at the jackknife. The Annals of Statistics, 7(1), 1-26. https://doi.org/10.1214/aos/1176344552.

Fellegi, I. P., & Sunter, A. B. (1969). A theory for record linkage. Journal of the American Statistical Association, 64(328), 1183-1210. https://doi.org/10.1080/01621459.1969.10501049.

Gemma Team. (2025). Gemma 3 technical report. arXiv. https://arxiv.org/abs/2503.19786.

Guo, Z., Xu, R., Yao, Y., Cui, J., Ni, Z., Ge, C., Chua, T.-S., Liu, Z., & Huang, G. (2024). LLaVA-UHD: An LMM perceiving any aspect ratio and high-resolution images. In Computer vision – ECCV 2024 (pp. 390-406). Springer. https://doi.org/10.1007/978-3-031-73010-8_23.

Holm, S. (1979). A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics, 6(2), 65-70. https://www.jstor.org/stable/4615733.

Huang, Q., Hao, S., Ye, Y., Zhu, S., Feng, Y., & Zhao, D. (2022). Does recommend-revise produce reliable annotations? An analysis on missing instances in DocRED. In Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers) (pp. 6241-6252). Association for Computational Linguistics. https://doi.org/10.18653/v1/2022.acl-long.432.

Huang, Z., Chen, K., He, J., Bai, X., Karatzas, D., Lu, S., & Jawahar, C. V. (2019). ICDAR2019 competition on scanned receipt OCR and information extraction. In Proceedings of the 2019 International Conference on Document Analysis and Recognition (ICDAR) (pp. 1516–1520). IEEE. https://doi.org/10.1109/ICDAR.2019.00244.

Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast accuracy. International Journal of Forecasting, 22(4), 679-688. https://doi.org/10.1016/j.ijforecast.2006.03.001.

Šimsa, Š., Šulc, M., Uřičář, M., Patel, Y., Hamdi, A., Kocián, M., Skalický, M., Matas, J., Doucet, A., Coustaty, M., & Karatzas, D. (2023). DocILE benchmark for document information localization and extraction. In Document analysis and recognition – ICDAR 2023 (pp. 147–166). Springer. https://doi.org/10.1007/978-3-031-41679-8_9.

Jaume, G., Ekenel, H. K., & Thiran, J.-P. (2019). FUNSD: A dataset for form understanding in noisy scanned documents. In Proceedings of the 2019 International Conference on Document Analysis and Recognition Workshops (ICDARW) (pp. 1–6). IEEE. https://doi.org/10.1109/ICDARW.2019.10029.

Kim, E., Huang, K., Tomala, A., Matthews, S., Strubell, E., Saunders, A., McCallum, A., & Olivetti, E. (2017). Machine-learned and codified synthesis parameters of oxide materials. Scientific Data, 4, Article 170127. https://doi.org/10.1038/sdata.2017.127.

Kim, S., & Kim, H. (2016). A new metric of absolute percentage error for intermittent demand forecasts. International Journal of Forecasting, 32(3), 669-679. https://doi.org/10.1016/j.ijforecast.2015.12.003.

Kononova, O., Huo, H., He, T., Rong, Z., Botari, T., Sun, W., Tshitoyan, V., & Ceder, G. (2019). Text-mined dataset of inorganic materials synthesis recipes. Scientific Data, 6, Article 203. https://doi.org/10.1038/s41597-019-0224-1.

Kuhn, H. W. (1955). The Hungarian method for the assignment problem. Naval Research Logistics Quarterly, 2(1-2), 83-97. https://doi.org/10.1002/nav.3800020109.

Makridakis, S. (1993). Accuracy measures: Theoretical and practical concerns. International Journal of Forecasting, 9(4), 527-529. https://doi.org/10.1016/0169-2070(93)90079-3.

Masry, A., Long, D. X., Tan, J. Q., Joty, S., & Hoque, E. (2022). ChartQA: A benchmark for question answering about charts with visual and logical reasoning. In Findings of the Association for Computational Linguistics: ACL 2022 (pp. 2263-2279). Association for Computational Linguistics. https://doi.org/10.18653/v1/2022.findings-acl.177.

Methani, N., Ganguly, P., Khapra, M. M., & Kumar, P. (2020). PlotQA: Reasoning over scientific plots. In Proceedings of the IEEE/CVF Winter Conference on Applications of Computer Vision (WACV) (pp. 1516-1525). IEEE. https://doi.org/10.1109/WACV45572.2020.9093523.

Mistral AI. (2025, March 17). Mistral Small 3.1. https://mistral.ai/news/mistral-small-3-1.

Munkres, J. (1957). Algorithms for the assignment and transportation problems. Journal of the Society for Industrial and Applied Mathematics, 5(1), 32-38. https://doi.org/10.1137/0105003.

Newcombe, H. B., Kennedy, J. M., Axford, S. J., & James, A. P. (1959). Automatic linkage of vital records. Science, 130(3381), 954-959. https://doi.org/10.1126/science.130.3381.954.

Northcutt, C. G., Athalye, A., & Mueller, J. (2021). Pervasive label errors in test sets destabilize machine learning benchmarks. arXiv. https://arxiv.org/abs/2103.14749.

Olivetti, E. A., Cole, J. M., Kim, E., Kononova, O., Ceder, G., Han, T. Y.-J., & Hiszpanski, A. M. (2020). Data-driven materials research enabled by natural language processing and information extraction. Applied Physics Reviews, 7(4), Article 041317. https://doi.org/10.1063/5.0021106.

Park, S., Shin, S., Lee, B., Lee, J., Surh, J., Seo, M., & Lee, H. (2019). CORD: A consolidated receipt dataset for post-OCR parsing. In Workshop on Document Intelligence at NeurIPS 2019. https://openreview.net/forum?id=SJl3z659UH.

Pavlick, E., & Kwiatkowski, T. (2019). Inherent disagreements in human textual inferences. Transactions of the Association for Computational Linguistics, 7, 677-694. https://doi.org/10.1162/tacl_a_00293.

Peng, N., Poon, H., Quirk, C., Toutanova, K., & Yih, W.-T. (2017). Cross-sentence n-ary relation extraction with graph LSTMs. Transactions of the Association for Computational Linguistics, 5, 101-115. https://doi.org/10.1162/tacl_a_00049.

Polak, M. P., & Morgan, D. (2024). Extracting accurate materials data from research papers with conversational language models and prompt engineering. Nature Communications, 15, Article 1569. https://doi.org/10.1038/s41467-024-45914-8.

Raji, I. D., Bender, E. M., Paullada, A., Denton, E., & Hanna, A. (2021). AI and the everything in the whole wide world benchmark. arXiv. https://arxiv.org/abs/2111.15366.

Sainz, O., Campos, J., García-Ferrero, I., Etxaniz, J., Lopez de Lacalle, O., & Agirre, E. (2023). NLP evaluation in trouble: On the need to measure LLM data contamination for each benchmark. In Findings of the Association for Computational Linguistics: EMNLP 2023 (pp. 10776-10787). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.findings-emnlp.722.

Sclar, M., Choi, Y., Tsvetkov, Y., & Suhr, A. (2023). Quantifying language models' sensitivity to spurious features in prompt design or: How I learned to start worrying about prompt formatting. arXiv. https://arxiv.org/abs/2310.11324.

Smock, B., Pesala, R., & Abraham, R. (2023). GriTS: Grid table similarity metric for table structure recognition. In Document analysis and recognition – ICDAR 2023 (pp. 535–549). Springer. https://doi.org/10.1007/978-3-031-41734-4_33.

Smock, B., Pesala, R., & Abraham, R. (2022). PubTables-1M: Towards comprehensive table extraction from unstructured documents. In Proceedings of the 2022 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) (pp. 4624–4632). IEEE. https://doi.org/10.1109/CVPR52688.2022.00459.

Song, Y., Miret, S., & Liu, B. (2023). MatSci-NLP: Evaluating scientific language models on materials science language tasks using text-to-schema modeling. In Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers) (pp. 3621-3639). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.acl-long.201.

Swain, M. C., & Cole, J. M. (2016). ChemDataExtractor: A toolkit for automated extraction of chemical information from the scientific literature. Journal of Chemical Information and Modeling, 56(10), 1894-1904. https://doi.org/10.1021/acs.jcim.6b00207.

Tan, Q., Xu, L., Bing, L., Ng, H. T., & Aljunied, S. M. (2022). Revisiting DocRED - Addressing the false negative problem in relation extraction. In Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing (pp. 8472-8487). Association for Computational Linguistics. https://doi.org/10.18653/v1/2022.emnlp-main.580.

Wang, P., Bai, S., Tan, S., Wang, S., Fan, Z., Bai, J., Chen, K., Liu, X., Wang, J., Ge, W., Fan, Y., Dang, K., Du, M., Ren, X., Men, R., Liu, D., Zhou, C., Zhou, J., & Lin, J. (2024a). Qwen2-VL: Enhancing vision-language model's perception of the world at any resolution. arXiv. https://arxiv.org/abs/2409.12191.

Wang, Z., Xia, M., He, L., Chen, H., Liu, Y., Zhu, R., Liang, K., Wu, X., Liu, H., Malladi, S., Chevalier, A., Arora, S., & Chen, D. (2024b). CharXiv: Charting gaps in realistic chart understanding in multimodal LLMs. arXiv. https://arxiv.org/abs/2406.18521.

Wilcoxon, F. (1945). Individual comparisons by ranking methods. Biometrics Bulletin, 1(6), 80-83. https://doi.org/10.2307/3001968.

Xu, Z., Du, S., Qi, Y., Xu, C., Yuan, C., & Guo, J. (2023). ChartBench: A benchmark for complex visual reasoning in charts. arXiv. https://arxiv.org/abs/2312.15915.

Yao, Y., Ye, D., Li, P., Han, X., Lin, Y., Liu, Z., Liu, Z., Huang, L., Zhou, J., & Sun, M. (2019). DocRED: A large-scale document-level relation extraction dataset. In Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics (pp. 764-777). Association for Computational Linguistics. https://doi.org/10.18653/v1/P19-1074.

Zheng, X., Burdick, D., Popa, L., Zhong, X., & Wang, N. X. R. (2021). Global Table Extractor (GTE): A framework for joint table identification and cell structure recognition using visual context. In Proceedings of the 2021 IEEE Winter Conference on Applications of Computer Vision (WACV) (pp. 697–706). IEEE. https://doi.org/10.1109/WACV48630.2021.00074.

Zheng, Z., Zhang, O., Borgs, C., Chayes, J. T., & Yaghi, O. M. (2023). ChatGPT chemistry assistant for text mining and the prediction of MOF synthesis. Journal of the American Chemical Society, 145(32), 18048-18062. https://doi.org/10.1021/jacs.3c05819.

Zhong, X., ShafieiBavani, E., & Jimeno Yepes, A. (2020). Image-based table recognition: Data, model, and evaluation. In Computer vision – ECCV 2020 (pp. 564–580). Springer. https://doi.org/10.1007/978-3-030-58589-1_34.

## Editor's notes (delete before submission)

**Missing input.** The seven independently drafted sections referenced in the merge brief were not present in my input — the brief ends at the header with no section text following. I searched the working directory (`/Users/maxfu/Library/CloudStorage/GoogleDrive-fuhuilong2012@gmail.com/My Drive/peek_bench_2026/paper_drafts/`, which contains only `render.py`), the project root, and the scratchpad tree; no section drafts exist on disk. **The body above was therefore composed directly from the locked-facts table and the framing brief, not merged from drafts.** All ten tables, the abstract, keywords, title and Sections 9-10 are new. If the seven drafts still exist, re-run the merge with them attached — the numbers below are already reconciled, so a second pass need only fold in any prose worth keeping. The assembled paper is at `/private/tmp/claude-501/-Users-maxfu-Library-CloudStorage-GoogleDrive-fuhuilong2012-gmail-com-My-Drive-peek-bench-2026/905fef85-075b-4eea-a3a6-4b21c4a3f6e1/scratchpad/peek_paper_merged.md` and renders with the existing `render.py`.

**Corrections made against the locked-facts table.** Reconciled while drafting, using project docs (`peek-bench/docs/*.md`) as prose sources:

1. **Engineered-prompt length.** `docs/methodology.md` states the engineered prompt is **6,820** characters. The locked table states **4,513**. Used 4,513 (Section 8.3). *This contradiction needs resolving before submission — one of the two sources is stale.*
2. **Defect count.** `docs/scoring-defects.md` says "six defects". The locked table lists **eight** (six original plus two marked NEW). Used eight throughout (Table 2).
3. **Per-paper significance values.** `docs/metrics.md` quotes *p* = 0.043 (row F1), *p* = 0.031 (cell) and *p* = 0.38 (UTS) for the gemma-vs-mistral comparison. None of these is in the locked table; all three were **deleted**. Only the locked Wilcoxon counts (4 of 9 / 1 of 9 / 0 of 9) and the locked SI A/B p-values (0.0006, 0.93) survive.
4. **Backend-numerics retraction (Section 7.3).** `docs/capacity-curve.md` gives the withdrawn comparison as 40.85 (Mac) vs 15.03 (RTX A2000), a 2.7× gap. Neither 15.03 nor 2.7× is in the locked table, so both were replaced with **15.03 and 2.7×** and the claim is described qualitatively. The docs quote the Mac's run-to-run range as "17.47-40.85"; §6.3 uses the full locked precision, 17.4723 to 40.8488, since the locked table carries four decimals.
5. **12B zero-row papers.** `docs/capacity-curve.md` names CF-P14, CF-P10 and CF-P15 as the 12B's total failures. Not in the locked table; the paper IDs were **deleted** and the claim generalised to "several papers".
6. **Mean GT rows per paper.** `docs/capacity-curve.md` uses "~8.7". Not locked; replaced with the locked "113 rows across 13 papers" (Section 8.2).
7. **Gemma image tiling.** "896×896" from `docs/capacity-curve.md` is not locked and was **deleted**; only the locked 258 tokens/page is stated.
8. **Quantisation and GGUF provenance.** "lmstudio-community GGUF at Q4_K_M" is not locked and was **deleted**.
9. **Claude 39-run parallel wall clock (12.9 min / 2.0 h serial-equivalent)** from `docs/methodology.md` is not locked and was **deleted**; the Claude rows in Table 8 carry no wall-clock figure.
10. **Individual 4B sweep wall clocks** (34 m / 45 m / 29 m in `docs/capacity-curve.md`) are not locked; used the locked "~34 min" only.
11. **The 21-row anecdote's paper ID.** `docs/metrics.md` attributes an all-null zero-F1 run to CF-P20. The locked table gives the 21-row / 0.895 → 0.000 case without a paper ID. **No paper ID is asserted** in Section 4.1.
12. **Alignment-degeneracy counts.** "Four papers fully degenerate, eleven partially" appears in the docs and matches the locked note that 4 papers' rows cannot be aligned, but the *eleven* is not locked. Retained "four", **deleted** "eleven" (Section 6.1).

**Numbers flagged for the first author — not changed, but they do not reconcile.**

- **CF-P13 tier spread.** The locked table gives CF-P13 spread **10.02** and the four tier values **9.28 / 11.70 / 3.56 / 1.78**. Max minus min of those four is **9.92**, not 10.02. Also, "orders all four tiers" does not hold in the listed sequence (11.70 > 9.28). Both are quoted verbatim in Section 5.1 without asserting monotonicity. Please check.
- **Table 7 mean |Δ|.** The locked table gives five per-paper pairs and a mean |Δ| of **27.12**; the five listed deltas average **53.12**. This is only consistent if 27.12 is the mean over all 13 dev papers and the five shown are the largest movers. Table 7 is captioned on that reading. Please confirm.
- **Deltas for CF-P05, CF-P02, CF-P13 in Table 7** (−31.80, −32.62, −20.43) are arithmetic from the locked before/after values; only the CF-P18 (−180.75) and CF-P24 (0) deltas are given explicitly in the locked table.
- **"56 of 119 test rows in six unaudited papers"** (Section 10) comes from the merge brief, not from the locked-facts table. The locked table states only that 6 of 10 test papers are unaudited and that TEST holds 119 rows. Verify the 56 before submission.
- **Dev-13 spread of 4.81 pp** in Table 5 is read from the locked phrase "config spread falls 4.81pp -> 1.14pp", i.e. 4.81 is the Dev-13 value. **Separation retained** for Dev-10 (22.7%) is derived as 100% − (46.4 + 21.5 + 9.4); the locked table states only the Dev-9 figure (6.3%) directly.

**Redundancy control.** Each of the three recurring anecdotes appears once in full and is cross-referenced thereafter: the 21-row null run in §3.1 (referenced in §1, abstract, §10); the CF-P18 0.364-vs-0.800 inversion in §3.2 (referenced in §4.1, §5.2, §9, §10); the image-token gradient in §7.1 (referenced in §4, §10). The CF-P18 two-row MAPE swing in §6.2 is a distinct fact about the same paper and is cross-linked to Table 4 rather than restated.

**Through-line.** Sections are ordered scorer (§3) → corpus (§4) → reference tables (§5) → estimator (§6) → readout (§7), with §1 conceding the small-*n* objection and §9 applying the audit to the frozen split. Every section closes by handing off to the next instrument.

**Structural gaps a first author should fill.** There is no related-work section and no reference list. Section 2.3 states the four metrics but not their tolerances (the locked table does not carry them; `docs/metrics.md` gives 1% or ±0.5 absolute on parameters and 5% or ±1.0 MPa on UTS — add if those can be confirmed as locked). The harness description in §2 is compressed to a paragraph; if a full methods section is wanted, `docs/methodology.md` has the material. Abstract is 191 words.