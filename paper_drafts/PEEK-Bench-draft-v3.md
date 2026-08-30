# Three Instruments and an Unstable Estimator: A Validity Audit of PEEK-Bench

*Draft v3 (2026-08-19, postscript updated 2026-08-29): adds §8.8 — the v2 fleet-campaign
readout, including repeat-sweep replication of the §6 instability result, the Qwen3.8-27B vs
frontier comparison (now three sweeps on both sides), and the engineered-vs-naive inversion
measured on Claude Fable 5 / Opus 4.8 (readout (d)). Earlier copies of this draft numbered the
postscript §8.6, colliding with "Reading beats tooling"; cross-references to §8.6 elsewhere in
the draft refer to that original section.*

**Keywords:** benchmark validity; structured information extraction; evaluation metric design; scientific document understanding; vision–language models; materials informatics

## Abstract

Structured-extraction benchmarks publish leaderboards. They rarely publish evidence that the leaderboard measures what it claims. Three instruments stand between a model's output and a benchmark number: the scorer, the corpus, and the reference tables. We audit all three on PEEK-Bench — extraction of process–property records from figure-heavy carbon-fibre/PEEK additive-manufacturing papers, 23 papers and 232 datapoints — using only its 13-paper development split. We report eight scorer defects, each with a reproduction: row alignment through the target variable; an all-null extraction scoring at the top of its paper's table; a basis change that raised cell accuracy while dropping roughly a third of ground-truth cells from scoring; correct transcription penalised as fabrication. Two defects remain live in our own reported numbers. Four of thirteen papers carry 93.7% of the between-configuration signal; removing three collapses that spread from 4.81 to 1.14 percentage points, and removing a fourth inverts the model ordering. Three sweeps differing only in temperature-0.1 sampling return UTS MAPE of 40.8488, 17.4723 and 36.3624 — a coefficient of variation of 39.3%. Model results appear last, as an instrument readout with sensitivity attached. The frozen test split has never been run, and we argue it should not be until its reference tables are audited.

---

## 1. Introduction

Structured-extraction benchmarks publish leaderboards. Almost none publish evidence that the leaderboard is measuring what it claims. Three instruments stand between a model's output and the number printed in the table — the **scorer** that turns predicted rows into a metric, the **corpus** that supplies the documents the metric is averaged over, and the **reference tables** that define what a correct answer is. A benchmark paper typically validates none of them. It reports that model A beat model B, and the reader is left to assume that the alignment rule, the paper selection, and the annotation are all faithful enough that the gap is about the models.

On PEEK-Bench they were not. This paper is a validity audit of our own benchmark. Each of the first two instruments was independently large enough to invert or erase the model ranking; the third was never audited at all. A fourth strand joins them: even after the scorer was fixed, the estimator it produces is unstable. Three sweeps that differed in nothing but temperature-0.1 sampling — same machine, same GGUF, same backend, same context length, same prompt, same harness — returned UTS MAPE of 40.8488, 17.4723 and 36.3624, a coefficient of variation of 39.3%.

PEEK-Bench is a small, deliberately hard corpus: extraction of process-property records from figure-heavy carbon-fibre/PEEK fused-filament-fabrication papers, nine process parameters plus ultimate tensile strength, one row per printed-and-tested condition with a reported UTS. 23 papers, 232 UTS datapoints. A large share of the tensile values exist only inside raster figures — printed bar labels, swept line curves, axis ticks. A paper can contain the string "MPa" exactly once and still report nine tensile values. Everything below is the DEV split: 13 papers, 113 rows. The TEST split — 10 papers, 119 rows — is frozen and has never been run. No claim in this paper depends on it, and we say so here rather than in a limitations paragraph.

### 1.1 The objection, stated first

The strongest objection to this work is short, and we would rather print it than let a reviewer discover it:

> These are bugs in one person's code, on 13 papers, single annotator, signal concentrated in four documents, no held-out results.

Every clause is true. The scorer defects were found in our own `score10.py`. The dev split is 13 papers. The ground truth has one annotator. Per-paper between-configuration spread in UTS MAPE sums to 60.93 across the dev papers, and four papers carry 93.7% of it. Nothing is held out that has been run.

The answer is that the objection assumes the paper is making a population claim. It is not. A ranking inversion is an existence proof, and an existence proof needs one instance, not a sample. When a scorer places a run that emitted 21 rows with every tensile value null at the top of its paper's table (§5.2), that is a defect in the scorer, demonstrated by construction, and it does not become less of a defect at n = 100 papers. When adding one column to the alignment basis moves mean row F1 from 0.792 to 0.478 while cell accuracy *rises* from 0.656 to 0.705 (§5.3), the metric pair is shown to be incoherent, and no amount of additional data repairs it. The same holds for the corpus: dropping three papers collapses between-configuration spread from 4.81 pp to 1.14 pp and makes the gemma-to-mistral step vanish; dropping a fourth inverts the ordering outright. Those are properties of this corpus, established on this corpus, and they are exactly the properties a leaderboard built on it would have silently inherited.

Small n weakens population claims. It does not weaken proofs by construction. So the rhetorical order of this paper is: concede the objection here, then answer it for eight sections with results that hold at n = 1.

### 1.2 Contributions

1. **A scorer audit with reproductions (§4, §5).** Nine design decisions with no settled standard, and eight defects in our scoring code, each with a construction that exhibits it. Two of the eight are proofs by construction in the strict sense. Three were introduced by the repair of an earlier one. Two are still live in every number this paper reports. We also show that the shipped regression fixtures — two identity fixtures — are structurally incapable of catching four of the eight, and we specify the mutation suite that would.
2. **A corpus-sensitivity analysis that erases the result (§7).** Four of thirteen papers carry 93.7% of the discriminative signal, and three of those four are exactly the papers whose ground truth encodes curation the document never states. CF-P13 is the sole exception, and it is the model of what a benchmark item should be.
3. **An instability demonstration (§6).** Three sweeps differing only in sampling give row F1 CV 12.4% and UTS MAPE CV 39.3%, with per-paper MAPE deltas up to 180.75. A single-sweep benchmark number is not a measurement of the model. One previously reported cross-hardware finding is withdrawn on this basis.
4. **A model comparison reported as an instrument readout (§8).** Five configurations across roughly an 11x image-token range, with sensitivity attached to every claim, plus a prompt-engineering result — every local model fabricates more when prompted harder; the frontier model does not — and the confound in that ablation stated in the same breath.

The remainder follows that order: the benchmark (§2), the scorer's decision surface (§4) and its defects (§5), the estimator (§6), the corpus (§7), and only then the models (§8). §9 states limitations, §10 argues that the frozen split must not be run before its reference tables are audited, and §11 concludes.

---

## 2. PEEK-Bench

### 2.1 Task

PEEK-Bench asks a model to read a materials-science paper and return a table of process–property records. The domain is fused-filament fabrication (FFF) of carbon-fibre-reinforced PEEK. The unit of extraction is one printed-and-tested condition that has a reported ultimate tensile strength (UTS); the schema is nine FFF process parameters — `nozzle_diameter`, `nozzle_temp`, `printing_speed`, `fiber_weight_fraction`, `raster_angle`, `infill_percentage`, `specimen_thickness`, `layer_thickness`, `platform_temp` — plus UTS as the single property column.

The task is figure-heavy by construction: a large share of tensile values exist only inside raster figures, as printed bar labels or as swept line curves read against axis ticks. Text alone does not suffice, and text alone is not small either — the heaviest paper, CF-P15, runs 23 pages and measures 26,909 real prompt tokens of body text before a single image is attached.

### 2.2 Corpus and splits

**Table 1. Splits.**

| | papers | UTS rows |
|---|---|---|
| DEV | 13 | 113 |
| TEST | 10 | 119 |
| total | 23 | 232 |

Every result in this paper is DEV (Table 1). TEST is frozen and has never been run; six of its ten papers have not been audited for scope filters (§2.5, §10). We report the split sizes so the reader can see how little is being held back, and how little a held-out set would buy at n = 10.

All inference ran on a single Mac Mini M4 Pro, 64 GB unified memory, 273 GB/s. No cloud, no rented GPU. The whole campaign is 205+ runs and roughly 25 h of inference at $0 compute; the two Claude arms carry an imputed ~$24 at Opus list rates, marked IMPUTED because those runs used a subscription rather than a metered API.

### 2.3 Harness

The harness is agentic, not a single-shot prompt. Each run receives the paper's full page text up front and exposes three tools:

- `view_page(n)` — return the rendered image of page *n*. Images are pulled on demand, so the number of pages a model chooses to look at is itself a measured quantity.
- `note(...)` — scratch memory for partial rows.
- `submit(rows)` — emit the final table and end the run.

This design separates two failure modes that a flat prompt conflates: not finding the figure, and not reading it. It also makes image cost a per-configuration property rather than a constant, because the vision front-ends differ by more than an order of magnitude in what one page costs.

Two prompts are used: a naive 869-character instruction and an engineered 4,513-character template. Unless stated otherwise, all results use the engineered prompt. Sampling is temperature 0.1 throughout, with three repeats per paper, giving 39 runs per configuration on dev-13. Because the three repeats within a sweep are near-duplicates, the unit of analysis is the paper (n = 13), not the run (n = 39).

### 2.4 Model configurations

**Table 2. Configurations.**

| configuration | image tokens/page | wall/run |
|---|---|---|
| gemma-3-27b | 258 | 5.24 min |
| mistral-3.1-24b | 1030 | 4.21 min |
| qwen3-vl-32b | ~2900 | 9.55 min |
| claude-opus-5, read-only | native | — |
| claude-opus-5, + Bash/Write/Edit | native | — |

The three local models in Table 2 run under the same backend, context window (40,960 for the Gemma capacity sweeps), prompt and harness. The two Claude arms differ from each other only in tool access: the read-only arm has `view_page` / `note` / `submit`; the tooled arm additionally has Bash, Write and Edit and may compute, cache and re-read intermediate files.

### 2.5 Why scoring is the hard part

Extraction is hard. Scoring is harder, for a reason specific to how the reference tables were built.

Ground truth was curated by a human reading charts. Producing a row means deciding where a bar's top edge sits against an axis, which of several overlapping curves belongs to which condition, and — critically — which conditions belong in the table at all. That last decision is not recoverable from the document. Three of the thirteen dev papers carry a scope filter the source text never states: one admits room-temperature rows only, one narrows to a single material arm, one restricts to the FFF route where the paper also reports other routes. A model that transcribes the page perfectly and completely will emit rows the reference table deliberately excludes, and a scorer that does not know this will read correct transcription as fabrication.

The harness therefore ships a per-paper scope note for two of the three affected papers, CF-P11 and CF-P18; the remaining eleven dev papers receive none. This is a concession, not a feature. It means part of the reference standard lives in the prompt rather than in the document, and any comparison that varies the prompt also silently varies the scope note. §8.7 shows that the prompt-engineering ablation was confounded exactly this way. It also means the third curated paper is scored against a filter it was never told about; §8.6 returns to that paper.

The consequence for measurement is structural. The scorer must align predicted rows to reference rows before it can score any cell, and the alignment basis is a free parameter that the ground truth — not the prediction — has to fix. §4 and §5 show that reasonable choices of that parameter move mean row F1 by more than the entire spread between models.

### 2.6 Pre-imputation ground truth

One design decision deserves to be stated as a decision rather than a detail: **the reference tables are pre-imputation**. A blank cell means the paper does not report that value. It is not filled with a machine default, a column median, or a value inferred from a sibling condition.

This costs coverage — many reference rows are sparse — and buys one thing that most materials-extraction benchmarks cannot have. Because `null` is a correct answer, filling a blank cell is unambiguously wrong, and *false-fill* becomes directly measurable: the rate at which a model invents a value the source never reported. Benchmarks that impute their ground truth cannot distinguish a fabricated number from a recovered one, and so cannot measure the failure mode that matters most for scientific extraction. False-fill is reported alongside row F1 throughout, and §8.7 shows the two moving in opposite directions under prompt engineering for every local model.

---

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

## 4. The scorer, part I: nine decisions with no standard

A model reads a paper and emits a table. The benchmark holds a reference table. Someone must now turn the pair into a number. This step is usually treated as bookkeeping — a detail of the harness, described in two sentences of an appendix if at all. It is not bookkeeping. It is a modelling problem with at least nine independent design decisions, each of which admits a defensible-sounding answer that silently changes which system wins.

The difficulty is structural. Classification has a canonical scorer because the prediction and the reference are both a label drawn from the same finite set. Extraction of *records* has no such luxury. The prediction is a set of tuples of unknown cardinality, in arbitrary order, over fields that may be blank on either side, describing entities that the reference identifies only implicitly. Before any cell can be compared to any other cell, the scorer must decide which predicted row is *about the same thing* as which reference row — and that decision is a model of the domain, not an arithmetic operation.

### 4.1 The decisions

**(a) What is the unit of comparison?** A table can be scored as a rendered structure (does the predicted grid have the same cells in the same places?), as a bag of records (does the predicted set of tuples cover the reference set?), or as a set of field-value assertions about named entities. These give different answers on the same output. Structure-first metrics such as TEDS and its successors (Zhong et al., 2020; Smock et al., 2023) treat the table as a tree and reward getting the layout right; a model that reproduces a paper's *layout* but reads every number off the wrong axis scores well. For scientific extraction the layout is irrelevant — the same nine conditions may be reported as one table, three figures, and a sentence — so a bag-of-records view is the right one. But choosing it immediately creates decision (b), which structure-first metrics never have to face.

**(b) How are predicted rows put in correspondence with reference rows?** Greedy nearest-neighbour matching is the obvious answer and is order-dependent: it can consume the reference row that a later prediction needed. Optimal assignment (Hungarian; Kuhn, 1955; Munkres, 1957) removes the order dependence and is the standard choice in permutation-invariant set prediction. It does not remove the problem; it relocates it into the cost function, decision (c). A second sub-decision hides here: whether a match requires the distance to fall below a threshold, or whether the assignment is forced. A forced assignment will pair a fabricated row with a real one at any distance and then score its cells.

**(c) Which columns establish row identity?** This is the load-bearing choice and the least discussed. A row in our schema is identified by its *process condition* — the combination of inputs the experimenter set. The measured property is the thing under test. If the measured value participates in the matching cost, the scorer pairs rows partly on the basis of the answer being right, and accuracy becomes partly self-fulfilling: the same output scored with and without the target column in the basis gets two different numbers, and the more flattering one is the invalid one. The reasonable-looking wrong answer is *use all available columns, they carry information*. It is wrong for the same reason using the outcome as a blocking key is wrong in record linkage (Fellegi & Sunter, 1969).

A subtler failure lives in the same decision: which *input* columns. Adding a column that the reference reports sparsely does not add signal — it adds a dimension in which most reference rows are blank, and blank-versus-value comparisons dominate the cost.

**(d) Who chooses the basis, and when?** The basis must be selected from properties of the reference table, and it must be selected once, before any prediction is seen. Choosing it by inspecting the prediction — "use whichever column varies in the output" — is the circularity of (c) with an extra step, and it hands the choice of scoring rule to the system being scored.

**(e) What does a blank mean?** Three distinct things get written as an empty cell: *the paper does not report this*, *this does not apply to this condition*, and *the annotator did not get to it*. Most materials-extraction references impute, which collapses all three into a plausible value and makes fabrication unmeasurable. A pre-imputation reference (§2.6) keeps them distinct and makes null a *correct answer* — which in turn means the scorer must decide whether agreeing on a null earns credit. If it does, an output consisting of the correct row skeleton with every measured value omitted is rewarded for the omission, and can outrank an output that attempted the measurement and got it approximately right. The reasonable-looking wrong answer is *treat null as a value like any other and check equality*.

**(f) What happens when reference rows are indistinguishable?** If two reference rows carry identical values on the alignment basis — because the paper varied something the schema does not encode, or reports replicates — the assignment between them is not identifiable. Any permutation is equally optimal, and the score becomes a coin flip that the scorer reports as a measurement. The scorer must detect this condition and either abstain, collapse the rows, or report the metric as undefined. Crucially, degeneracy is a property of the *reference*, and must be diagnosed from the reference alone. Diagnosing it from the prediction — declaring a paper degenerate because the output was flat — lets a system exempt itself from scoring by failing in the right shape.

**(g) What is in scope?** The reference table for a paper is not "everything in the paper"; it is everything after the curation rules the annotator applied (§2.5). A prediction that faithfully transcribes an excluded condition is *correct about the document and absent from the reference*. Counting it as a false positive penalises reading accuracy. The reasonable-looking wrong answer is *anything not in the reference is a false positive*, which is exactly right when the reference is a complete enumeration and exactly wrong when it is a filtered one. §7.4 argues that the filters are themselves an unaudited instrument; here the point is narrower — the scorer cannot be written without knowing which regime it is in, and nothing in a reference file states which.

**(h) Over what population does each metric aggregate?** A record-level error statistic — mean absolute percentage error (Makridakis, 1993; Hyndman & Koehler, 2006) on the measured value — can only be computed on rows that matched. That makes it *conditional on the matching succeeding*, so it silently excludes exactly the runs that failed hardest, and the conditioning is invisible in the reported number. The same trap catches any rate whose denominator is derived from the matched set: a fabrication rate whose denominator counts blank cells *among matched rows* is endogenous to the matching, and moves when row-level performance moves even if fabrication behaviour is unchanged. The reasonable-looking wrong answer is *average the per-run values*, which is a mean over a non-random, performance-selected subsample. The fix is either a coverage penalty inside the statistic or an explicit, reported denominator.

**(i) Row, run, or paper as the unit of analysis?** Repeats within a sweep are not independent samples of the quantity of interest, and papers differ enormously in how many reference rows they carry. Micro-averaging over rows lets one 20-row paper outvote nine small ones; macro-averaging over runs treats near-duplicate repeats as evidence. This decision does not corrupt the score, but it determines every significance test computed on top of it.

### 4.2 The decision surface

**Table 3. Nine scoring decisions and their plausible wrong answers.**

| Decision | Plausible wrong answer | What it produces |
|---|---|---|
| (a) Unit of comparison | Score the rendered table structure | Rewards layout fidelity, not reading |
| (b) Row correspondence | Greedy nearest neighbour; forced assignment | Order-dependent scores; fabrications matched at any distance |
| (c) Alignment basis | Use every column, including the target | Circular accuracy; the answer helps find the answer |
| (d) Basis selection | Pick the column that varies in the prediction | The scored system chooses its own scoring rule |
| (e) Meaning of blank | Null is a value; agreement on null earns credit | Empty extractions outrank attempted ones |
| (f) Degenerate references | Diagnose degeneracy from the output | Failure in the right shape buys an exemption |
| (g) Scope of the reference | Everything not in the reference is a false positive | Correct transcription of filtered-out conditions is penalised |
| (h) Metric conditioning | Average the per-run value | Statistic conditioned on the matching having worked |
| (i) Unit of analysis | Average over runs | Near-duplicate repeats counted as independent evidence |

Every row of Table 3 was taken in its wrong form at some point in this campaign. §5 gives the reproductions.

### 4.3 What is known prior art, and what is not

Honesty requires conceding that most of these are not new problems; they are new *instances*. The circularity in (c) is the outcome-in-the-blocking-key error familiar from record linkage since Fellegi–Sunter, and is a close cousin of target leakage. Optimal-assignment matching for unordered predictions is standard in set prediction and in n-ary and document-level relation extraction, where the corresponding question — when do two extracted tuples refer to the same fact — has been debated for years without a settled answer. Table-structure metrics (TEDS, GriTS, cell-adjacency measures) have their own long-running argument about whether to score structure, content, or both, and about how to handle empty cells. Key-information-extraction benchmarks such as SROIE, CORD and the Kleister tasks have repeatedly discovered that annotation scope, not model capability, drives leaderboard movement. The reward for empty output in (e) is the extraction analogue of the well-known precision-only degenerate solution.

Two things do appear to us to be under-discussed rather than merely re-encountered. The first is (h) as a *composition* problem: individually reasonable per-run statistics become invalid when averaged across runs whose inclusion depends on performance, and the resulting bias is largest exactly where the benchmark is most informative. The second is that nothing in the surrounding literature supplies a *validation procedure* for a scorer. Benchmarks ship reference data and a script; they do not ship adversarial fixtures that would fail if the script were wrong. An identity fixture — a reference table fed back as its own prediction — passes under every wrong answer in Table 3, because all of them agree on the perfect case. A scorer tested only against itself is untested.

The claim is not that any single decision is novel. It is that there are at least nine of them, that no standard exists to settle them, that each benchmark therefore re-derives the whole surface privately, and that on our benchmark the wrong branches were taken often enough to reorder the models.

---

## 5. The scorer, part II: eight defects, with reproductions

Every claim in this paper — every ranking, every ablation, every significance test — is a statement about the scorer as much as about the models. This section reports eight defects found in it. Each is presented as a design question that has a plausible answer, the answer we in fact chose, a reproduction on real runs from this campaign, and the fix.

![Figure 1. The same runs, scored twice. (a) Three real runs under the pre-audit scorer (left) and the audited scorer (right); nothing about the models changed between the columns. The 21-row run whose every tensile value is null falls from the top of its paper's table to zero, and the run that transcribed all nine printed bar labels correctly overtakes a three-row run wrong by 8-13 MPa. (b) The raster_angle over-correction: mean row F1 falls while cell accuracy rises on the same runs, because roughly a third of ground-truth cells silently left scoring.](figures/fig1_scored_twice.png)


Two of the eight are proofs by construction in the strict sense: a single input on which the scorer's ordering is provably wrong, independent of sample size. Three were **introduced by the repair of defect 1**; that is not incidental, and §5.9 returns to it. Two are **not fixed** and are live in every number this paper reports.

**Table 4. The eight defects.**

| # | Defect | Reproduction | Status |
|---|---|---|---|
| 1 | UTS included in Hungarian row-matching distance | circular: alignment manufactures accuracy | fixed |
| 2 | All-null tensile column scores near the top of a paper's table | 21 rows, every UTS null → row F1 **0.895** → **0.000** | fixed |
| 3 | `raster_angle` added to the alignment basis | mean row F1 0.792 → 0.478 while cell accuracy *rose* 0.656 → 0.705 | fixed (introduced by fix 1) |
| 4 | Alignment basis chosen from the prediction | correct extraction, zero matches | fixed (introduced by fix 1) |
| 5 | Degeneracy diagnosed from predictions | hallucination masks a degenerate paper | fixed (introduced by fix 1) |
| 6 | Out-of-scope predictions in the precision denominator | CF-P18: correct run **0.364**, wrong run **0.800** → correct run **1.000** | fixed |
| 7 | UTS MAPE computed only over matched pairs, no coverage penalty | gemma-3-27b MAPE over 31/39 runs; the 8 excluded runs have mean row F1 **0.000** | diagnosed, **not fixed** |
| 8 | False-fill denominator inside the same matched-pairs loop | `blank_gt_cells` is endogenous to row F1 | diagnosed, **not fixed** |

### 5.1 Defect 1 — circular alignment

**Question.** Predictions and ground truth are unordered sets of rows. Before any cell can be compared, rows must be matched. On which columns should the Hungarian matching distance be computed?

**Wrong answer.** All of them, including UTS. It is the most informative column; using it produces the "best" pairing.

**Reproduction.** Including the target in the matching distance makes the matcher pair each predicted row with whichever ground-truth row its tensile value is closest to. Accuracy is then not measured but constructed: the scorer searches over pairings for the one that minimises the error it is about to report. A model that emits plausible UTS values attached to arbitrary process conditions is rewarded exactly as much as a model that reads the right row.

**Fix.** Alignment must use INPUT columns only — the nine FFF process parameters. The target may never appear in the distance that decides which rows are compared.

### 5.2 Defect 2 — the 21-row all-null run (proof by construction)

**Question.** How should a row that identifies the right printed condition but reports no tensile value score?

**Wrong answer.** As a matched row. It matched, after all; the null is one missing cell.

**Reproduction.** A run emitted 21 rows for one paper with **every tensile value null**. It scored **row F1 0.895** — the top of that paper's table. It beat a 52-row run that got 47% of its tensile values right.

This is the cleanest possible statement of the failure. The benchmark exists to measure extraction of tensile values from figures. Under this scorer the winning strategy was to extract no tensile values at all, transcribe the process-parameter grid (which is usually in a table, in text, and cheap), and let the alignment do the rest. The scorer was measuring table-reading and calling it figure-reading.

**Fix.** A predicted row with a null target is not a scoreable row. After the fix the same run scores **0.000**. One run, one input, no statistics: the ordering was wrong.

### 5.3 Defect 3 — a wider alignment basis that silently drops ground truth

**Question.** Fix 1 removed UTS from the basis. Which input columns should replace it? More columns should mean a tighter, less ambiguous match.

**Wrong answer.** Add `raster_angle`, a column that genuinely varies across conditions in many papers.

**Reproduction.** Mean row F1 fell **0.792 → 0.478** while cell accuracy **rose 0.656 → 0.705**, and roughly **a third of GT cells silently left scoring**. The two metrics moving in opposite directions is the tell. Rows that could not be matched on the wider basis were not penalised — they were dropped, and cell accuracy was then computed over the surviving, easier remainder. The scorer got more confident by measuring less.

**Fix.** The alignment basis must be validated for coverage: the count of ground-truth cells entering scoring is an invariant and must be asserted, not assumed. Any basis change that reduces it is a scorer regression regardless of what happens to the headline number.

### 5.4 Defect 4 — an alignment basis read off the prediction

**Question.** Different papers vary along different axes. Can the basis be chosen per paper, automatically?

**Wrong answer.** Use the column that varies in the PREDICTION.

**Reproduction.** On one paper this picked a column that is **all-blank in the ground truth**, and gave **zero matches to a CORRECT extraction**. The prediction varied along an axis the reference table does not populate; every ground-truth row was equidistant from every predicted row; the matcher returned nothing; the run scored zero for being right.

**Fix.** The basis is a function of the ground truth alone. For fixed ground truth, mutating the prediction must not change which columns align.

### 5.5 Defect 5 — degeneracy diagnosed from the wrong side

**Question.** Some papers are structurally degenerate: no input column distinguishes their rows, so no alignment is possible and the paper must be flagged rather than scored. How is degeneracy detected?

**Wrong answer.** From the predictions — if the model's rows are distinguishable, the paper must be.

**Reproduction.** This inverts the intended safeguard. A model that hallucinates variation into a column the paper never reports makes a degenerate paper look scoreable, and is then scored against a reference table that cannot support the comparison. Fabrication buys immunity from the degeneracy flag.

**Fix.** Degeneracy is a property of the reference table and must be diagnosed from ground truth only.

### 5.6 Defect 6 — out-of-scope predictions in the precision denominator (proof by construction)

**Question.** Several dev papers carry scope filters that the ground truth encodes but the document never states (§2.5). A model that also transcribes the out-of-scope conditions has produced correct rows that are not in the reference table. What are they?

**Wrong answer.** False positives.

**Reproduction.** CF-P18 prints its tensile values as bar labels. A run **transcribed all nine printed bar labels correctly** and scored **row F1 0.364**. A three-row run **wrong by 8–13 MPa** on every value scored **0.800**. The scorer preferred a run that read the figure incorrectly to one that read it perfectly, because the perfect run read too much of it.

**Fix.** Predictions falling outside the reference table's scope filter are excluded from the precision denominator rather than counted against it. After the fix the correct run scores **1.000**. Again: one paper, one pair of runs, an inversion that no increase in n would have resolved and no decrease in n could weaken.

### 5.7 Defect 7 — MAPE with no coverage penalty (open)

**Question.** Over which rows is UTS MAPE computed?

**Wrong answer.** Over the matched pairs — the only rows where both a prediction and a reference value exist.

**Reproduction.** In `score10.py`, line 319 opens `for i, j, d in pairs:` and the error append at line 342 is inside that loop. A run therefore contributes to MAPE only through rows it managed to match, and a run that matches nothing contributes nothing.

**Table 5. MAPE coverage by configuration, dev-13 (39 runs each).**

| configuration | runs entering MAPE | mean row F1 of the excluded runs |
|---|---|---|
| gemma-3-27b | 31 / 39 | **0.000** |
| mistral-3.1-24b | 33 / 39 | 0.447 |
| qwen3-vl-32b | 36 / 39 | 0.965–1.000 (CF-P14, structurally degenerate) |
| claude-opus-5 read-only | 36 / 39 | 0.965–1.000 (CF-P14) |
| claude-opus-5 + tools | 36 / 39 | 0.965–1.000 (CF-P14) |

Table 5 is the measured consequence. The weakest configuration has its eight worst runs — runs that extracted nothing — removed from its error metric, while the strongest configurations lose only three runs each, and those three are excluded for a structural reason unrelated to quality. The MAPE column of the main table is thus computed on systematically different subsets per configuration, and the difference favours the weaker models. Every MAPE reported in this paper is computed under this defect.

**Fix (proposed, not yet applied).** MAPE must carry a coverage penalty: unmatched ground-truth rows enter the error at a defined ceiling, or the metric is reported as a pair (MAPE, coverage) and never as a scalar. A run with zero matched rows must not be silently absent from its own error statistic.

### 5.8 Defect 8 — an endogenous false-fill denominator (open)

**Question.** False-fill is the rate at which a model invents values for cells the paper leaves blank. What is its denominator?

**Wrong answer.** Blank ground-truth cells among the matched rows.

**Reproduction.** That count sits inside the same matched-pairs loop as defect 7, so `blank_gt_cells` is endogenous to row F1: a run that matches fewer rows has fewer blank cells available to fabricate into, and its false-fill rate is computed over a smaller, differently-composed base. False-fill and row F1 are therefore not independent axes, and the prompt-engineering result in §8.7 — every local model fabricating more when prompted harder, with false-fill rising 3.6–5.2x — is reported on a denominator that moves with the accuracy it is being contrasted against. The direction of the effect is large enough that we do not expect it to reverse, but the magnitudes are not clean.

**Fix (proposed, not yet applied).** The denominator is all blank ground-truth cells in the paper, matched or not, fixed before any alignment runs.

### 5.9 Three of the eight came from fixing the first

Defects 3, 4 and 5 did not exist in the original scorer. They were created by the repair of defect 1. Removing UTS from the alignment distance was correct and necessary; it also left a hole where the matching basis used to be, and each of the next three defects is a different plausible way of filling that hole — a wider basis, a per-paper basis read off the prediction, and a degeneracy test read off the prediction. Each was validated by checking whether the headline number looked reasonable. Each passed that test. Defect 3 in particular *improved* cell accuracy while destroying a third of the measurement.

The lesson is not that we were careless. It is that a scorer fix has no local proof of correctness: the only visible output of a scoring change is a change in scores, and there is no independent oracle telling you which direction is right. Every fix in this section was validated by a reproduction constructed specifically for it, after the fact. Nothing in the harness would have caught any of them prospectively.

### 5.10 The regression-fixture problem, and a mutation suite

What ships as regression protection is two fixtures: `CF-P05__perfect.json` and `CF-P13__perfect.json`. Both are **identity fixtures** — the prediction is the ground truth, and the expected score is the maximum.

An identity fixture tests exactly one point in the score space, and it is the one point every defect in this section leaves untouched. Defects 1, 3, 4 and 6 are all mis-orderings of *imperfect* predictions; a perfect prediction scores 1.000 under each of them and under their fixes. The two shipped fixtures are structurally incapable of catching any of the four. The same argument extends to 2, 7 and 8: an all-null prediction, an incomplete prediction and a fabricating prediction are all, by construction, not the identity.

The replacement is a **mutation suite**, built by applying labelled operators to the two known-good tables and asserting an ordering property rather than a value. Two operator classes:

**Corrupting mutations — the score must be non-increasing.** Perturb one UTS value by ε, then 2ε, then 10ε. Null one UTS cell; null the whole UTS column. Delete one row; delete half the rows. Shuffle UTS values across rows while holding the process columns fixed. Blank one process column. Each operator is parameterised by a corruption magnitude, and the required property is monotonicity: for corruption magnitudes m₁ < m₂, score(m₂) ≤ score(m₁). This is checkable without knowing what the score *should* be, which is precisely what makes it usable on a metric nobody can calibrate a priori.

**Equivalence mutations — the score must be invariant.** Permute row order. Reformat units without changing values. Add a correct row for a condition the paper reports but the reference table filters out.

**Table 6. Mutation operators and the defects they catch.**

| Mutation | Property asserted | Catches |
|---|---|---|
| shuffle UTS across rows, process columns fixed | score must fall | 1 |
| null the entire UTS column | score → 0 | 2 |
| any basis change | count of GT cells entering scoring is invariant | 3 |
| perturb the prediction only | alignment basis unchanged | 4, 5 |
| add a correct out-of-scope row | score invariant | 6 |
| delete rows from the prediction | MAPE must not improve | 7 |
| delete rows from the prediction | false-fill denominator invariant | 8 |

The monotonicity property in Table 6 is the important part. It converts scorer validation from "does this number look right" — the test that let all eight defects through — into an assertion that fails loudly on inputs no one thought to construct. Defect 7's fix is not complete until "deleting the rows you got wrong must not improve your error" is a test that runs on every commit.

---

## 6. The estimator: a validated scorer can still be unstable

§4 and §5 addressed the scorer's *correctness*: after the repairs, a score means what it claims to mean. Correctness is not the same as stability. A metric can be well-defined, defect-free, and still be an estimator so noisy that the number you report is mostly a draw from its own sampling distribution. We measured this directly, by running the same configuration three times and changing nothing.

![Figure 2. Estimator instability across three identical sweeps of gemma-3-4b (same machine, GGUF, backend, context, prompt and harness; only temperature-0.1 sampling differs). (a) Coefficient of variation by metric: UTS MAPE moves 39.3% where cell accuracy moves 1.1%. (b) The three sweep means for UTS MAPE (red, left axis) against cell accuracy (blue, right axis) over the same runs.](figures/fig3_estimator_instability.png)


### 6.1 Three identical sweeps

Same Mac Mini, same GGUF, same backend, same context length (40,960), same engineered prompt, same harness, same 13 dev papers, same scorer. The only difference between the three sweeps is temperature-0.1 sampling.

**Table 7. Three identical gemma-3-4B sweeps.**

| metric | run1 | run2 | run3 | mean | SD | CV |
|---|---|---|---|---|---|---|
| row F1 | 0.3359 | 0.3540 | 0.4233 | 0.3711 | 0.0461 | 12.4% |
| recall | 0.3207 | 0.3137 | 0.3726 | 0.3357 | 0.0322 | 9.6% |
| precision | 0.6188 | 0.6111 | 0.7351 | 0.6550 | 0.0695 | 10.6% |
| cell accuracy | 0.7453 | 0.7537 | 0.7376 | 0.7455 | 0.0081 | 1.1% |
| UTS MAPE | 40.8488 | 17.4723 | 36.3624 | 31.5612 | 12.4058 | 39.3% |

The headline of Table 7 is the last column. UTS MAPE has a coefficient of variation of 39.3%; cell accuracy, computed on the same runs by the same scorer, has 1.1%. A thirty-five-fold difference in stability between two metrics reading the same outputs is a property of the metrics, not of the model.

The practical consequence: on this arm, any reported UTS MAPE improvement smaller than the observed SD of 12.4058 is indistinguishable from rerunning the same command. Row F1 is better but not safe — an SD of 0.0461 covers most of the gaps people would call a result.

### 6.2 Mechanism

Three scorer design choices compound.

**MAPE is unbounded above.** Cell accuracy lives in [0, 1] and cannot be dragged by a single bad cell. A percentage error has no ceiling: one row read off a curve at three times its true value contributes 200 percentage points on its own. The metric's upper tail is set by its worst single pairing.

**Papers are averaged before models.** We average absolute percentage error within a paper, then average papers. That is the right unit of analysis (§6.4), but it means a paper with 2 ground-truth rows enters the corpus mean with exactly the same weight as a paper with 20 — while carrying roughly ten times the variance, because its paper-level mean is an average over ten times fewer terms.

**The set of scored pairs is itself random.** Defect 7 (§5.7) established that UTS MAPE is computed only over Hungarian-matched pairs, with no coverage penalty. So between two identical sweeps the *estimand* moves: a run that matches fewer rows is scored on a different, smaller sample. Stability was never going to survive that.

**Table 8. Per-paper UTS MAPE between two identical sweeps (mean |delta| = 27.12).**

| paper | GT rows | sweep A | sweep B | delta |
|---|---|---|---|---|
| CF-P18 | 2 | 218.65 | 37.91 | −180.75 |
| CF-P05 | 18 | 43.34 | 11.54 | −31.80 |
| CF-P02 | 3 | 32.81 | 0.19 | −32.62 |
| CF-P13 | 11 | 20.43 | 0.00 | −20.43 |
| CF-P24 | 20 | 10.59 | 10.59 | 0 |

Table 8 shows all three mechanisms at once. CF-P18 has two ground-truth rows and swings 180.75 points. CF-P24 has twenty and does not move at all. The corpus mean is, to a first approximation, a readout of what happened on the smallest papers.

### 6.3 A retraction

We previously reported an apparent [TK]x discrepancy in UTS MAPE for the same model between two machines, and read it as evidence of compute-backend divergence — Metal versus CUDA — or of a difference in GGUF build. **That finding is withdrawn.** The second machine's value ([TK]) sits inside the first machine's own run-to-run range, 17.4723 to 40.8488, established in Table 7 from three sweeps that shared a machine, a backend and a build. There is no cross-hardware effect in the data. There is one estimator with a wide sampling distribution, sampled twice.

The near-miss is worth stating plainly because the setup is common. Anyone comparing quantised local inference across backends, GPUs, or llama.cpp builds is comparing two draws from distributions whose width they have usually not measured. A single run per machine cannot distinguish a backend effect from sampling. The minimum defensible protocol is to characterise within-machine variance *first*, and only then ask whether the cross-machine gap exceeds it. We did the second step before the first, and we were wrong.

The same standard applies inward. The reading-beats-tooling gap in §8.6 is reported as a noise floor, not a finding, for exactly this reason.

### 6.4 Fixes

1. **Report median APE alongside the mean.** The mean is a tail readout; the median is not. Where they disagree, the disagreement is the finding.
2. **Bootstrap confidence intervals over papers**, and print them next to every headline number. A point estimate with no interval is not reportable on a corpus this size.
3. **Treat the paper as the unit of analysis, n = 13, not the run, n = 39.** At temperature 0.1 the three repeats inside a sweep are near-duplicates; treating them as independent inflates the effective sample threefold and manufactures significance.
4. **Weight or stratify by ground-truth row count.** Either weight paper means by row count, or report small-n and large-n papers separately. Do not let a 2-row paper and a 20-row paper enter unweighted and pretend they carry equal information.
5. **Repeat whole sweeps, not runs within a sweep.** Within-sweep repeats measure sampling jitter on one paper; sweep-level repeats measure the thing you actually report.

The honest limitation: we have applied step 5 only to the 4B arm. The 12B and 27B arms are single sweeps (2h48m and 3h24m of wall clock respectively) and therefore have **no sweep-level variance estimate at all**. Every 12B and 27B number in this paper, including the 27B UTS MAPE of 5.20 that anchors both the capacity curve and the main table, should be read as one draw from a distribution of unknown width — and the only arm where we have measured that width had a CV of 39.3%.

---

## 7. The corpus: does it discriminate?

A benchmark separates systems only if its items do. §5 showed that the scorer could invert the ranking; this section shows that the corpus can erase it. The demonstration needs no population argument: it is a leave-out computation on the 13 dev papers, and its conclusion is a property of this corpus, not an estimate about corpora in general.

![Figure 3. Where the discriminative signal lives. (a) Per-paper between-configuration UTS MAPE spread, sorted; four of thirteen papers carry 93.7% of it, and three of those four carry an undisclosed scope filter (red). (b) Removing them collapses the benchmark: configuration spread falls from 4.81 to 0.33 percentage points and the count of significant paired comparisons falls from 4 of 9 to 0 of 9.](figures/fig2_signal_concentration.png)


### 7.1 Almost all of the signal lives in four papers

Take the between-configuration spread in UTS MAPE within each paper — the range across the configurations run on it — and sum over the dev set. The total is 60.93 MAPE points. It is not spread evenly.

**Table 9. Per-paper spread decomposition, dev-13.**

| Paper | Spread (MAPE pts) | Share | Cumulative |
|---|---:|---:|---:|
| CF-P11 | 28.26 | 46.4% | 46.4% |
| CF-P18 | 13.11 | 21.5% | 67.9% |
| CF-P13 | 10.02 | 16.4% | 84.3% |
| CF-P24 | 5.71 | 9.4% | 93.7% |
| other nine papers combined | 3.83 | 6.3% | 100.0% |

Four of thirteen papers carry 93.7% of the discriminative signal. The remaining nine contribute 3.83 points between them — less than the fourth-ranked paper alone. Whatever PEEK-Bench measures about a model, it measures it on four documents; the other nine are ballast that stabilises the mean and contributes nothing to the ordering.

### 7.2 The cascade: Dev-13, Dev-10, Dev-9

Remove the three highest-spread papers (CF-P11, CF-P18, CF-P24) and the corpus becomes Dev-10. Remove CF-P13 as well and it becomes Dev-9.

**Table 10. The leave-out cascade.**

| | Dev-13 | Dev-10 | Dev-9 |
|---|---:|---:|---:|
| papers (unit of analysis) | 13 | 10 | 9 |
| between-configuration spread | 4.81 pp | 1.14 pp | 0.33 pp |
| significant paired-Wilcoxon comparisons | 4 of 9 | 1 of 9 | 0 of 9 |
| image-token gradient (gemma / mistral / qwen) | 5.20 / 4.44 / 1.06 | 1.37 / 1.33 / 0.55 | ordering inverts |
| paper × config cells at UTS-accuracy ceiling | [TK] | [TK] | 87.2% |

Three things happen on the way down Table 10.

**The gemma→mistral step vanishes at Dev-10.** On the full dev set the two configurations differ by 0.76 MAPE points (5.20 vs 4.44), a gap this paper elsewhere associates with a roughly fourfold difference in image tokens per page. On Dev-10 the same gap is 0.04 points (1.37 vs 1.33). The image-token gradient does not disappear — qwen still separates at 0.55 — but its lower half was an artefact of three papers.

**The ordering inverts at Dev-9.** With CF-P13 also removed, gemma-3-27b (0.24) beats mistral-3.1-24b (0.38). The corpus now reports the opposite of what it reported at Dev-13, from the same runs, the same scorer, and the same prompts. One instance is enough: a four-paper edit to the corpus flips a ranking. Only 6.3% of the original separation survives.

**The benchmark saturates.** At Dev-9, 87.2% of paper × configuration cells sit at the UTS-accuracy ceiling. A measurement in which seven of eight observations are at the top of the scale has no resolution left to spend; the residual 0.33 pp of spread is the shape of the remaining 12.8%.

A fourth consequence reaches outside this section. On Dev-9 the naive prompt beats the engineered prompt for 2 of 5 configurations. This matters more than it looks, because the prompt ablation on the full dev set is confounded on exactly the papers Dev-10 and Dev-9 exclude (§8.7). The deconfounded comparison is therefore precisely the one in which the engineered prompt stops winning.

### 7.3 What the significance cascade does and does not show

The 4 → 1 → 0 cascade is partly an artefact of n. The unit of analysis is the paper, so a paired Wilcoxon runs on n = 13, then 10, then 9; dropping four papers removes 30.8% of the pairs, and the exact signed-rank test loses power accordingly (at n = 9 the two-sided floor is 2/2⁹ ≈ 0.004, so significance remains attainable, but only for a near-perfect sign pattern). A reviewer is entitled to say that some of the collapse is arithmetic, and they are right.

Three pieces of evidence are not vulnerable to that objection.

1. **Spread is an effect size, not a test statistic.** 4.81 pp → 1.14 pp → 0.33 pp is a 14.6x contraction that does not depend on n at all. Removing four papers removed the effect, not merely the power to detect it.
2. **Inversion is not a power phenomenon.** Losing power moves a result toward "no difference"; it does not move it to the other side of zero. Gemma beating mistral at Dev-9 is a sign flip in the point estimates.
3. **Ceiling saturation is distributional.** 87.2% of cells at ceiling is a property of the score distribution and would be unchanged by adding a hundred more papers of the same kind.

What we did not run, and what a stronger version of this analysis would run, is the counterfactual: resample 9-paper subsets that *retain* the four discriminative papers and confirm that significance survives at n = 9. Until that is done, the honest claim is the one the effect sizes already support — the signal is concentrated, not merely under-sampled.

### 7.4 The coupling: discriminative papers are curated papers

The finding is not that four papers dominate. It is *which* four.

Three of the four — CF-P11, CF-P18, CF-P24, together 77.3% of the spread — are exactly the papers whose ground truth encodes curation the document never states (§2.5). Nothing in the PDF tells an extractor to apply any of those filters. A model that reads the paper correctly and returns everything the paper reports is scored wrong; a model that guesses the curator's intent is scored right.

That is a mechanism, and it explains the concentration rather than merely co-occurring with it. Undisclosed curation makes a paper hard in a way that is uncorrelated with reading ability, so configurations scatter on it, so it acquires spread. The papers that separate models best separate them partly on compliance with an unstated convention. This is a **reference-table** defect — the third instrument, the one never audited — surfacing as a corpus property, and it is why the two cannot be audited independently.

**CF-P13 is the existence proof that the coupling is not necessary.** It is figure-locked — the tensile values exist only inside raster figures — it carries 10.02 points of spread (16.4% of the total, third-highest in Table 9), it separates all four capability tiers (per-tier UTS MAPE 9.28 / 11.70 / 3.56 / 1.78), and it needs no scope note: its ground truth is derivable from the document alone. Difficulty can come from the *rendering* of the data rather than from the curator's private filters, and when it does, the resulting discrimination measures extraction rather than convention-guessing.

### 7.5 A selection criterion, and a reporting standard

CF-P13 suggests the criterion directly. A benchmark item earns inclusion when it satisfies both conditions:

- **Discriminative.** It produces measurable between-configuration spread — otherwise it is ballast, and nine of our thirteen papers are ballast.
- **Self-contained.** Its ground truth is reconstructible from the document by a reader given only the schema. No room-temperature filter, no material arm, no route restriction that the paper does not state.

Items that are discriminative but not self-contained are the dangerous class: they look like the benchmark's strongest items and they measure the wrong thing. Items that are self-contained but not discriminative are merely expensive.

We therefore recommend that **discriminative power be reported as a standard benchmark property**, alongside size and score. Concretely, a benchmark release should publish (i) the per-item spread decomposition and its concentration, (ii) the share of item × system cells at ceiling, (iii) leave-out ranking stability for the top-spread items, and (iv) for each discriminative item, whether its reference table is self-contained. None of these require extra inference runs; all four fall out of results already computed. PEEK-Bench reports them here because the alternative — "23 papers, 232 datapoints" as the only statement of corpus strength — would have concealed that the benchmark is, for ranking purposes, four papers wide.

One consequence for the frozen split follows immediately, and §10 develops it: if the coupling observed on DEV holds on TEST, the test papers that discriminate are disproportionately likely to be the six that have never been audited.

---

## 8. Model results as an instrument readout

Everything before this section was about instruments. This section reads them. The numbers below are the output of a scorer with eight known defects (six repaired, two — #7 and #8 — still live in the reported figures), on a corpus whose separating power sits in four papers, against reference tables that have never been audited. They are reported as an instrument readout with sensitivity attached, not as a ranking. TEST was never run.

![Figure 4. The gemma-3 capacity curve at fixed perception. Gemma 3 spends 258 image tokens per page at every model size, so parameters vary with perception held constant. (a) Row F1 and recall are not monotone in parameters - the 4B beats the 12B on both, across all three of its sweeps. (b) UTS MAPE is monotone. Error bars on the 4B are the standard deviation over three independent sweeps; the 12B and 27B arms have one sweep each and therefore no error estimate.](figures/fig4_capacity_curve.png)


The unit of analysis is the paper (n = 13), not the run (n = 39): at temperature 0.1 the three repeats within a sweep are near-duplicates.

### 8.1 Main dev-13 table

**Table 11. Main dev-13 results. Engineered prompt, 39 runs per configuration (13 papers × 3 repeats).**

| config | img tok/page | row F1 | recall | cell | UTS MAPE | false-fill | wall/run |
|---|---|---|---|---|---|---|---|
| gemma-3-27b | 258 | 0.5734 | 0.6773 | 0.7982 | 5.20 | 0.2166 | 5.24 min |
| mistral-3.1-24b | 1030 | 0.8558 | 0.8616 | 0.9058 | 4.44 | 0.7500 | 4.21 min |
| qwen3-vl-32b | ~2900 | 0.9333 | 0.9858 | 0.9274 | 1.06 | 0.4012 | 9.55 min |
| claude-opus-5 read-only | native | 0.9504 | 1.0000 | 0.9633 | 0.39 | 0.1111 | — |
| claude-opus-5 + tools | native | 0.9331 | 0.9758 | 0.9623 | 0.49 | 0.0740 | — |

The UTS MAPE column of Table 11 carries defect 7 directly: it is measured on systematically different subsets per configuration, and the subsets are worst-biased exactly where the model is worst (Table 5). The false-fill column inherits the same conditioning through defect 8.

Read with that caveat, Table 11 says one thing loudly: **false-fill does not track accuracy.** Mistral, the second-weakest configuration by row F1, fabricates at 0.7500 — the highest rate in the campaign, above qwen's 0.4012 and an order of magnitude above claude+tools at 0.0740. A model that fills cells the paper never reports can look competent on row F1 and cell accuracy while corrupting exactly the property (pre-imputation blanks, §2.6) that makes this ground truth worth having.

### 8.2 The gemma-3 capacity curve: parameters with perception held constant

Gemma-3 fixes its vision budget at 258 image tokens per page at every model size; the token delta was measured independently on 4B, 12B and 27B. Same Mac, same engineered prompt, same ctx 40,960. This is the one comparison in the campaign where parameter count varies with perception genuinely held constant.

**Table 12. Gemma-3 capacity curve, image tokens fixed at 258/page.**

| model | sweeps | row F1 | recall | precision | cell | UTS MAPE | rows/run | pages viewed | wall |
|---|---|---|---|---|---|---|---|---|---|
| 4B | 3 | 0.3711 | 0.3357 | 0.6550 | 0.7455 | 31.56 ± 12.41 | 2.54 | 4.63 | ~34 min |
| 12B | 1 | 0.2879 | 0.2852 | 0.3464 | 0.7852 | 10.40 | 4.82 | 9.46 | 2h48m |
| 27B | 1 | 0.5734 | 0.6773 | 0.5766 | 0.7982 | 5.20 | 8.64 | 6.28 | 3h24m |

Two quantities in Table 12 are monotone in parameters: UTS MAPE (31.56 → 10.40 → 5.20) and rows emitted (2.54 → 4.82 → 8.64). Cell accuracy is weakly monotone (0.7455 → 0.7852 → 0.7982).

Row F1, recall and precision are **not** monotone. The 4B beats the 12B on row F1 and recall, and it does so in all three of its sweeps individually, not merely on the mean: row F1 0.3359 / 0.3540 / 0.4233 against the 12B's 0.2879, and recall 0.3207 / 0.3137 / 0.3726 against 0.2852 (Table 7). The inversion survives the full observed spread of the smaller model. Precision is non-monotone in the other direction: the 4B's 0.6550 is the highest of the three, above even the 27B's 0.5766.

The mechanism is visible in the same table and is not a capability claim. **Under-extraction buys precision.** The 4B emits 2.54 rows per run against the 12B's 4.82 and views 4.63 pages against 9.46 — it looks at half as much, answers half as much, and its precision is nearly twice as high (0.6550 vs 0.3464). A model that answers less is wrong less often per answer, and row F1 rewards that. What Table 12 shows is a metric responding to a truncation policy, not a capability ordering.

Both the 12B and 27B rows rest on one sweep each and carry no measured variance. §6.1 puts row F1 CV at 12.4% and UTS MAPE CV at 39.3% at 4B, which is the only direct estimate of how much of a single-sweep gap is sampling noise.

### 8.3 The image-token gradient is a three-point correlation

Across the three local families the engineered-prompt UTS MAPE falls 5.20 (258 tok/page) → 4.44 (1030) → 1.06 (~2900) (Table 11). This is a three-point correlation across three model families in which encoder architecture, tiling policy, pretraining mixture and release date are all collinear with image budget. Nothing in this design separates them.

The corpus sensitivity is not a footnote to that gradient; it is most of it. On Dev-10 the gradient flattens and the gemma→mistral step vanishes entirely, overall configuration spread falls from 4.81 pp to 1.14 pp, and significant paired-Wilcoxon comparisons drop from 4 of 9 to 1 of 9 (Table 10). The claim that survives is at most "the highest-image-budget model is better on this corpus"; the claim that image tokens order the low and middle tiers does not survive removing three papers.

The one clean carrier is CF-P13: figure-locked, spread 10.02, no scope note needed, and it orders all four tiers on its own at 9.28 / 11.70 / 3.56 / 1.78 (§7.4).

### 8.4 Interpolation versus transcription

The qwen-to-Claude gap is not uniform across visual task types. On CF-P18, where the tensile values are **printed bar labels**, qwen ties Claude at 0.00 MAPE. On CF-P11, where the values are **swept curves requiring axis interpolation**, qwen is at 6.45 against Claude's 1.96. Transcription from a raster figure is solved at the open-weight tier; reading a value off an axis is not.

Sensitivity: this is a two-paper contrast, and CF-P11 and CF-P18 are two of the three dev papers whose ground truth encodes curation the document never states. The perception finding and the scope-note dependence sit on the same papers.

### 8.5 Supplementary information supplies parameters, not tensile values

The supplementary-information A/B on CF-P13 dissociates cleanly: process-parameter extraction improves strongly (p = 0.0006) while UTS does not move (p = 0.93). Supplementary material fills in the process columns and leaves the measured property where it was — inside the figures. Sensitivity: single paper, single ablation.

### 8.6 Reading beats tooling — not separable

Claude read-only scores 0.39 MAPE / 0.9504 row F1; Claude with Bash/Write/Edit scores 0.49 / 0.9331. The direction is stable but the effect is not separable from noise. The two arms differ on only **3 of 12 papers, with opposite signs**, and the aggregate gap is driven by CF-P24 alone. Against the 4B's measured run-to-run CV (§6.1), a gap of this size on this few papers is the noise floor of the campaign, and should be reported as such rather than as a finding about tool use.

There is a second reason not to read it as a tooling result. CF-P24 — the single paper carrying the gap — is one of the three dev papers whose ground truth encodes undisclosed curation, and it is the one for which the harness ships **no** scope note (§2.5). The one paper that separates the two Claude arms is a paper on which both arms are scored against a filter neither was told about.

### 8.7 Prompt engineering: real, confounded, and it buys fabrication

**Table 13. Naive (869 characters) versus engineered (4,513-character template).**

| config | row F1 naive → eng | false-fill naive → eng |
|---|---|---|
| gemma-3-27b | 0.547 → 0.573 | 0.042 → 0.217 (5.2x) |
| mistral-3.1-24b | 0.777 → 0.856 | 0.204 → 0.750 (3.7x) |
| qwen3-vl-32b | 0.770 → 0.933 | 0.111 → 0.401 (3.6x) |
| claude-opus-5 read-only | 0.885 → 0.950 | 0.111 → 0.111 (unchanged) |
| claude-opus-5 + tools | 0.898 → 0.933 | 0.074 → 0.074 (unchanged) |

Every local model in Table 13 fabricates more when prompted harder — between 3.6x and 5.2x more. The frontier model does not move at all on false-fill while gaining on row F1. Prompt engineering, measured against pre-imputation ground truth, is partly a purchase of confident nulls-turned-values.

**This ablation is confounded and must not be reported without the disclosure.** `extract_naive.py` defines `paper_scope_block()` and never calls it. The naive arm therefore saw no scope note on CF-P11 or CF-P18 — the two papers holding 67.9% of the between-configuration spread (Table 9). The naive arm was run on a materially different task on exactly the papers that carry the signal. The comparison must be restricted to the eleven no-note papers or re-run before any number in Table 13 is used.

The corpus sensitivity adds a second warning: on Dev-9, which excludes both confounded papers, the naive prompt **beats** the engineered prompt for 2 of 5 configurations (Table 10). Whatever prompt engineering is worth here, it is worth it on four papers.

---

![Figure 5. The image-token gradient and its sensitivity. (a) UTS MAPE against measured image tokens per page, on the full development split and after removing three papers; the first step vanishes. Encoder, tiling policy, pretraining mixture and release date are all collinear with image budget across these three model families, so this is a three-point correlation, not a manipulation. (b) The surviving frontier gap is specific: on printed bar labels the local model ties the frontier model, and separates only where values must be interpolated against an axis.](figures/fig5_image_tokens.png)

![Figure 6. Coverage bought with fabrication. Each arrow runs from a configuration's naive-prompt operating point (hollow) to its engineered-prompt point (solid). Every local model moves upward - buying row F1 with invented values in cells the source paper leaves blank - while both frontier arms move horizontally. This is measurable only because the reference tables are pre-imputation, so null is a correct answer. The prompt ablation is confounded on two papers (Section 8.7).](figures/fig6_coverage_fabrication.png)

### 8.8 Postscript readout — the v2 fleet campaign (added 2026-08-19, updated 2026-08-29)

Between the analysis above and this draft's revision, the benchmark was re-run as a managed
fleet campaign: 35+ sweep arms over 23 local vision-language models on two machines plus
a frontier-API tier (~3,800 scored runs, ~330 local machine-hours, 156 token-metered agentic
runs), with the instrument disciplines this paper argues for applied throughout — per-arm
configuration logs, per-run watchdogs, repeat sweeps for eighteen arms, and negative results
retained rather than deleted. Four readouts matter for this paper's theses; the full table
follows them.

**(a) The estimator-instability finding (§6) replicates across the fleet.** With the repaired
scorer, row F1 between-sweep SD runs 0.000–0.055 — below 0.017 for every top-tier arm, though
the noisiest small arms (GLM-4.6V-Flash 0.055, Qwen3.5-4B 0.042) remain at the §6.1
instability scale. UTS MAPE remains the volatile metric: absolute between-sweep SDs of
0.01–1.57 percentage points, roughly eight-fold smaller than the early harness's 12.41 pp,
though *relative* volatility on low-MAPE arms can still exceed the early harness's CV of 39.3%
(the Opus 4.8 naive arm's 1.13±1.25 is a CV of ~110%). No single-sweep MAPE ranking should be
read as settled. The instability was an estimator property, not a bug artefact: fixing the
scorer shrank it; repeat sweeps remain mandatory.

**(b) The frontier-gap subplot inverted in fourteen days — and repeat sweeps confirmed it.**
The v1 readout had the frontier API arm (claude-opus-5, same harness and prompt) at 2.7x the
numeric fidelity of the best local model. In the v2 campaign, **Qwen3.8-27B** — released
2026-08-14, Apache-2.0, 19 GB Q4_K_M on a consumer Mac — returned **row F1 0.961±0.006,
recall 1.000±0.000, UTS MAPE 0.53±0.06%** across three full sweeps, winning row-finding
outright against every Claude arm in the campaign (best frontier F1: 0.908±0.000) with numeric
fidelity inside the noise band established by (a). The repeat-sweep discipline this paper
demands was applied to both sides of the comparison; the conclusion survived it. The frontier
gap on this task closed to within instrument noise in under a year, at zero marginal cost per
paper — what the frontier arms retain is blank-discipline (false-fill 0.000–0.037) and the
best absolute MAPE (0.33±0.06%, Claude Opus 4.8 engineered).

**(c) Protocol compatibility is a hidden axis a leaderboard hides.** Four models produced
essentially zero rows under every configuration tried in a systematic ladder (EXAONE-4.5-33B,
Fara1.5-9B, NuExtract3, DeepSeek-OCR-2) — reasoning-channel, GUI-agent, template-extractor,
and short-context page-parser failure classes respectively. Two more (Nemotron-Omni,
InternVL3.5) carry engine-level caveats (a fixed-256-token projector bug; context-exhaustion
view-loops). A leaderboard that silently omits such models overstates the generality of the
task; we report them as first-class results.

**(d) The prompt-engineering result of §8.7 acquires a second branch: the advantage inverts
at the frontier.** A full engineered-vs-naive matrix on two frontier models (Claude Fable 5
and Claude Opus 4.8, three sweeps per cell through the agentic harness) has both models
scoring *higher* row F1 under the naive prompt (Fable 5: 0.908±0.000 naive vs 0.885±0.002
engineered; Opus 4.8: 0.901±0.005 vs 0.883±0.003) — small absolute gaps, but many combined
between-sweep SDs, and in the direction *opposite* to every local pair measured (+0.07 to
+0.18 across the v2 repeat-sweep pairs; the v1-era single-sweep local pairs were also
positive, +0.03 to +0.16). This reverses the v1-era frontier pairs of §8.7's Table 13, where
claude-opus-5 gained +0.035 to +0.065 row F1 from engineering (its two harness modes) under
the same scope-note handicap — the inversion is a property of the current frontier models
under the agentic harness, not of the frontier as such, and the v1 pairs remain single-sweep
measurements. Note the direction of
§8.7's scope-note confound: the naive arms run *without* the two scope notes, i.e.
handicapped, and still win F1 at the frontier. The capability-dependence claim of §8.7
therefore has edges on both ends: models too weak to execute the rules gain nothing, mid-range
models gain coverage, and frontier models pay a precision tax for scaffolding they no longer
need. Villain-only repeat sweeps (eight paired comparisons, seven with between-sweep SD on
both sides; the qwen3.8-27B naive-villain side is a single sweep) sharpen the same picture:
mid-range pairs roughly double
their engineered advantage on the six hardest papers (+0.13 to +0.35), the frontier pairs stay
inverted, and one small model (Ministral-3-8B) inverts from below — its engineered arm's
false-fill (0.490±0.117 on villains) costs more F1 than the scaffolding's coverage buys.

**Full v2.2 readout (dev-13; local arms 3 repeats per sweep, Claude agentic arms 1 run per
paper per sweep; ± = between-sweep SD where n sweeps > 1; min/run is host-specific and never
pooled across machines; NAIVE marks naive-prompt arms):**

| arm | row F1 | recall | cell acc | UTS MAPE % | false-fill | min/run |
|---|---|---|---|---|---|---|
| Claude Opus 4.8 agentic (eng) | 0.883±0.003 | 1.000±0.000 | 0.973±0.004 | 0.33±0.06 | 0.012±0.021 | - |
| Claude Fable 5 agentic (naive) | 0.908±0.000 | 1.000±0.000 | 0.980±0.002 | 0.40±0.01 | 0.037±0.000 | - |
| Claude Opus 5 API (v1 era) | 0.933 | 0.976 | 0.962 | 0.49 | 0.074 | - |
| Claude Fable 5 agentic (eng) | 0.885±0.002 | 1.000±0.000 | 0.974±0.006 | 0.49±0.10 | 0.037±0.000 | - |
| Qwen3.8-27B | 0.961±0.006 | 1.000±0.000 | 0.958±0.001 | 0.53±0.06 | 0.152±0.033 | 14.9 |
| Qwen3.6-35B Q8_0 | 0.939 | 0.995 | 0.956 | 0.77 | 0.148 | 4.8 |
| Qwen3.6-35B-A3B | 0.917±0.007 | 0.960±0.014 | 0.953±0.005 | 0.83±0.20 | 0.140±0.026 | 4.4 |
| Qwen3.5-9B | 0.871±0.030 | 0.890±0.022 | 0.921±0.004 | 1.02±0.32 | 0.385±0.045 | 9.2 |
| Qwen3.8-27B NAIVE | 0.869 | 0.942 | 0.939 | 1.02 | 0.160 | 11.5 |
| Claude Opus 4.8 agentic (naive) | 0.901±0.005 | 0.961±0.041 | 0.962±0.006 | 1.13±1.25 | 0.000±0.000 | - |
| Agents-A1-35B | 0.739 | 0.797 | 0.917 | 1.64 | 0.136 | 7.2 |
| Gemma4-31B dense | 0.936 | 0.994 | 0.951 | 1.77 | 0.197 | 15.2 |
| Qwen3.5-4B | 0.772±0.042 | 0.800±0.053 | 0.903±0.003 | 1.99±0.17 | 0.303±0.013 | 11.7 |
| Gemma4-26B-A4B MoE | 0.926±0.004 | 0.991±0.007 | 0.937±0.002 | 2.20±0.21 | 0.259±0.064 | 3.6 |
| Muse Glimmer 30B | 0.843 | 0.941 | 0.915 | 2.23 | 0.210 | 8.5 |
| Gemma4-12BQAT CUDA | 0.909±0.011 | 0.951±0.010 | 0.925±0.010 | 2.28±0.36 | 0.359±0.017 | 14.8 |
| Qwen3.6-35B NAIVE | 0.846±0.017 | 0.869±0.027 | 0.921±0.011 | 2.86±1.17 | 0.099±0.021 | 2.2 |
| Qwen3VL-32B | 0.938±0.007 | 0.961±0.014 | 0.924±0.005 | 2.92±0.30 | 0.549±0.010 | 8.3 |
| InternVL3.5-30B(35) | 0.639 | 0.661 | 0.834 | 3.08 | 0.756 | 2.3 |
| Qwen3VL-30B-A3B | 0.944±0.017 | 0.946±0.023 | 0.895±0.005 | 3.17±0.52 | 0.895±0.033 | 5.1 |
| GLM-4.6V-Flash | 0.839±0.055 | 0.831±0.048 | 0.903±0.007 | 3.50±0.46 | 0.283±0.019 | 3.5 |
| Gemma4-12B Metal | 0.879 | 0.889 | 0.913 | 3.50 | 0.360 | 12.5 |
| Qwen3VL-8B (38) | 0.866±0.010 | 0.900±0.024 | 0.886±0.007 | 3.51±0.68 | 0.730±0.033 | 3.5 |
| Gemma4-12B CUDA | 0.926 | 0.958 | 0.902 | 4.09 | 0.338 | 23.4 |
| Nemotron-30B-A3B | 0.722 | 0.757 | 0.896 | 4.23 | 0.410 | 6.7 |
| Ministral-3-8B | 0.858±0.025 | 0.840±0.031 | 0.924±0.003 | 4.48±0.72 | 0.620±0.011 | 1.6 |
| Qianfan-OCR (32) | 0.561 | 0.589 | 0.761 | 5.27 | 0.873 | 3.4 |
| Gemma4-E4B naive x3 | 0.645±0.005 | 0.628±0.005 | 0.849±0.010 | 5.54±1.10 | 0.099±0.020 | 1.0 |
| Gemma4-E4B eng x3 | 0.820±0.007 | 0.817±0.020 | 0.866±0.014 | 6.37±1.57 | 0.123±0.016 | 1.9 |
| MiniCPM-V4.6 (36) | 0.346 | 0.332 | 0.660 | 25.53 | 0.863 | 1.3 |

*Configuration provenance for every arm — engine build, KV precision, image-token budget,
flash-attention setting, sampling, and every rescue deviation — is recorded in the campaign
arm logs; deviations are annotated per arm rather than silently normalized.*

## 9. Limitations

**One annotator, no inter-annotator agreement.** The reference tables — the third instrument — were produced by a single person reading charts, and no second annotator has ever re-derived a single paper. There is therefore no measurement of how much of any score is annotation rather than extraction, and no measurement of how reproducible the three undisclosed scope filters are. Those filters were found by inspection, one paper at a time; nothing in the annotation protocol required them to be declared, and nothing in a reference file marks a filtered table as filtered. The instrument this paper is most confident is broken is the one it never measured. A second annotator on even three papers — CF-P13, CF-P11 and CF-P24 — would be the highest-value experiment remaining.

**n = 13 papers, 113 rows.** Every significance test in this paper runs at n = 13 or fewer, and §7.3 concedes that part of the 4 → 1 → 0 Wilcoxon cascade is arithmetic. The paper's load-bearing claims are existence claims that survive at n = 1; its aggregate claims do not have the sample to be population claims, and are not offered as such.

**One materials system, one property.** All 23 papers are carbon-fibre/PEEK FFF, and the schema has exactly one property column. Nothing here shows that the scorer defects, the concentration of signal, or the estimator instability behave the same way for a benchmark with several correlated properties, for a domain whose values live mostly in text, or for a corpus where reference tables are complete enumerations rather than filtered ones.

**Imputed API costs.** The ~$24 attributed to the two Claude arms is IMPUTED at Opus list rates; those runs used a subscription, not a metered API. It is not a measured cost and must not be used for a cost-per-point comparison against the $0-compute local arms.

**Two arms have no sweep-level variance.** The 12B and 27B rows of Table 12 are single sweeps. The 27B UTS MAPE of 5.20 anchors both the capacity curve and the main results table, and its uncertainty is unknown; the one arm where width was measured had a UTS MAPE CV of 39.3%.

**Two scorer defects are live in every number reported.** Defects 7 and 8 are diagnosed, reproduced, and unfixed. Every MAPE and every false-fill figure in §8 is computed under them.

**The prompt ablation is confounded** on the two highest-spread papers (§8.7), and has not been re-run or restricted.

**Six of ten test papers are unaudited for scope filters**, which is the subject of §9.

**One analysis was specified and not run.** §7.3 identifies the counterfactual — resampling 9-paper subsets that retain the discriminative papers — that would separate effect from power in the leave-out cascade.

---

## 10. What the frozen split will and will not settle

TEST is 10 papers and 119 rows. It has never been run. The obvious next step is to run it, and this section argues against doing so yet.

### 10.1 What it cannot settle

A held-out split answers one question: does a result measured on DEV generalise to documents the analyst did not look at. That question is orthogonal to most of this paper.

- **Scorer validity.** Defects 2 and 6 are proofs by construction. A run that emits 21 all-null rows and lands at the top of its paper's table is a defective ordering whether or not the same thing happens on TEST. Running TEST cannot confirm or refute it, and cannot repair the two defects still live.
- **Estimator stability.** Instability is measured by repeating a sweep, not by adding papers. Ten new papers scored once give ten more single draws from distributions of unmeasured width.
- **Corpus discrimination.** Concentration is a property of a specific item set. The Dev-13 decomposition (Table 9) does not transfer to TEST; it would have to be recomputed there, which requires running TEST and then reporting that its discriminative power is also concentrated — a result that arrives too late to change the split.

What TEST could settle is narrow and real: whether the ordering at the top of Table 11 survives on unseen documents, and whether the selection criterion of §7.5 is satisfiable at scale.

### 10.2 The unaudited half

Six of the ten test papers have never been checked for scope filters, and those six hold 56 of the 119 test rows — 47% of the split. Neither their reference tables nor their per-paper scope notes have been reviewed against the source documents.

The DEV evidence on how often that check matters is not reassuring. Three of thirteen dev papers carry a filter the source text never states. Both dev papers whose scope was examined closely enough to change the harness turned out to need a scope note, and a third paper with undisclosed curation was identified without ever receiving one (§2.5, §8.6). Applied to six unaudited papers, the DEV base rate predicts at least one filtered reference table, and the audit that would find it has not been run.

§7.4 makes the prediction sharper than a base rate. On DEV, undisclosed curation and discriminative power are **coupled**: three of the four papers carrying 93.7% of the signal are exactly the curated ones. If that coupling holds on TEST, the test papers that separate models are disproportionately likely to be drawn from the six that were never checked. The split's strongest items and its least-verified items are predicted to be the same items.

### 10.3 Running it now produces a number this paper's own method invalidates

Suppose one of the six carries an undisclosed filter, and TEST is run today. Two outcomes, both bad.

If the filter is present and the harness ships no note, defect 6 describes exactly what happens: a model that transcribes the figure correctly and completely emits rows the reference table excludes, and is scored down for reading accuracy. On CF-P18 that mechanism moved a perfect transcription from 0.364 to 1.000 — a swing larger than the entire between-configuration spread of Table 11. If instead a note is written to cover the filter, part of the reference standard moves into the prompt, and any comparison that varies the prompt varies the standard along with it — which is how the prompt ablation was confounded in the first place (§8.7).

Either way the resulting number is uninterpretable by this paper's own criteria, and a benchmark paper that publishes a number its own methods section invalidates is worse off than one that publishes none.

The failure is also irreversible. A frozen split stops being frozen the moment it is used. Reporting a test number, discovering a filter, auditing, and reporting again does not yield a held-out result; it yields a revision, on a split that has now been seen. There is exactly one first run of TEST, and its value is destroyed by spending it before the audit.

### 10.4 Auditing precedes spending

The asymmetry in cost settles the ordering.

One pass of the three local configurations over TEST at three repeats each is 30 runs per configuration; at the wall times of Table 2 that is about 9.5 hours of inference, and it produces exactly the single-draw numbers §6 showed to be unreportable. Doing it properly — three sweep-level repeats, per §6.4 — is roughly 28.5 hours, more than the entire campaign to date (~25 h) and on the same single Mac Mini.

Auditing six reference tables against six PDFs is human hours, not machine hours. It requires no inference, produces a permanent artefact, and is a prerequisite for interpreting anything the 28.5 hours would buy. The order is not close.

The audit should also produce the four properties §7.5 recommends publishing, in the following order: (i) confirm or write down the scope filter for each of the six papers, in the reference file rather than the prompt; (ii) mark each test paper self-contained or not; (iii) fix defects 7 and 8 so that MAPE and false-fill are not conditioned on matching; (iv) only then run TEST, as whole repeated sweeps, and report intervals rather than point estimates.

**Until (i)–(iii) are done, the correct number of test runs is zero.** That is the recommendation this paper makes about its own remaining work, and it is the same recommendation it would make to anyone else holding an unaudited split.

---

## 11. Conclusion

A benchmark number is the output of three instruments. On PEEK-Bench, two of them were independently capable of changing the answer and the third was never examined.

The scorer had eight defects. Six are fixed, two are still live in every figure this paper prints, and three of the eight were created by the repair of the first — because a scorer fix has no local proof of correctness, and the only visible consequence of changing a scoring rule is that the scores change. Two of the defects are proofs by construction: a run that reported no tensile values at all sat at the top of its paper's table, and a run that transcribed nine printed bar labels perfectly scored below a run that misread every one of them. Neither result depends on how many papers the benchmark has. The shipped regression fixtures could not have caught either, because both fixtures are identity fixtures and every defect agrees on the perfect case. A mutation suite that asserts monotonicity under corruption and invariance under relabelling would have caught all eight (Table 6), and costs no inference.

The corpus concentrates its discriminative power in four of thirteen papers. Removing three collapses between-configuration spread by a factor of 4.2; removing a fourth inverts the model ordering and leaves 87.2% of the measurement at ceiling. Worse, three of those four papers are separating models partly on compliance with curation the documents never state. The benchmark's best items were measuring the wrong thing, and CF-P13 — figure-locked, self-contained, ordering all four capability tiers on its own — is the proof that they did not have to.

Even with the scorer repaired, the estimator is unstable. Three sweeps differing only in sampling produced UTS MAPE ranging from 17.4723 to 40.8488, a CV of 39.3%, while cell accuracy computed on the same outputs varied by 1.1%. One cross-hardware finding is withdrawn on that basis. Two of the five configurations in this paper have no variance estimate at all.

The model results are reported last and are compatible with all of it: a clean image-token gradient that mostly disappears on ten of thirteen papers; a capacity curve in which a 4B model beats a 12B on row F1 by answering less; a tooling comparison that is a noise floor; and a prompt-engineering result — every local model fabricates 3.6x to 5.2x more when prompted harder, while the frontier model does not move — that is real in direction, confounded in construction, and reversed for two of five configurations once the confounded papers are removed.

None of these findings required a large corpus. All of them required looking at the instruments. The practical recommendation is therefore procedural rather than empirical: ship a mutation suite instead of identity fixtures; publish per-item spread, ceiling share, and leave-out ranking stability alongside corpus size; report intervals from repeated whole sweeps rather than point estimates from single ones; and audit reference tables for undisclosed curation before spending a frozen split on them. We have done the first three here and are doing the fourth before running TEST.

---

## References

*APA 7th edition. Every entry verified against a live source; all 39 DOIs independently re-resolved through Crossref.*

Alzahrani, N., Alyahya, H., Alnumay, Y., AlRashed, S., Alsubaie, S., Almushayqih, Y., Mirza, F., Alotaibi, N., Al-Twairesh, N., Alowisheq, A., Bari, M. S., & Khan, H. (2024). When benchmarks are targets: Revealing the sensitivity of large language model leaderboards. In Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers) (pp. 13787-13805). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.acl-long.744

Anthropic. (n.d.). Models overview. Retrieved July 29, 2026, from https://platform.claude.com/docs/en/about-claude/models/overview

Bai, S., Cai, Y., Chen, R., Chen, K., Chen, X., Cheng, Z., Deng, L., Ding, W., Gao, C., Ge, C., Ge, W., Guo, Z., Huang, Q., Huang, J., Huang, F., Hui, B., Jiang, S., Li, Z., Li, M., ... Zhu, K. (2025). Qwen3-VL technical report. arXiv. https://arxiv.org/abs/2511.21631

Bai, S., Chen, K., Liu, X., Wang, J., Ge, W., Song, S., Dang, K., Wang, P., Wang, S., Tang, J., Zhong, H., Zhu, Y., Yang, M., Li, Z., Wan, J., Wang, P., Ding, W., Fu, Z., Xu, Y., ... Lin, J. (2025). Qwen2.5-VL technical report. arXiv. https://arxiv.org/abs/2502.13923

Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate: A practical and powerful approach to multiple testing. Journal of the Royal Statistical Society: Series B (Methodological), 57(1), 289-300. https://doi.org/10.1111/j.2517-6161.1995.tb02031.x

Biderman, S., Schoelkopf, H., Sutawika, L., Gao, L., Tow, J., Abbasi, B., Aji, A. F., Ammanamanchi, P. S., Black, S., Clive, J., DiPofi, A., Etxaniz, J., Fattori, B., Forde, J. Z., Foster, C., Hsu, J., Jaiswal, M., Lee, W. Y., Li, H., ... Zou, A. (2024). Lessons from the trenches on reproducible evaluation of language models. arXiv. https://arxiv.org/abs/2405.14782

Bowman, S. R., & Dahl, G. (2021). What will it take to fix benchmarking in natural language understanding? In Proceedings of the 2021 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (pp. 4843-4855). Association for Computational Linguistics. https://doi.org/10.18653/v1/2021.naacl-main.385

Card, D., Henderson, P., Khandelwal, U., Jia, R., Mahowald, K., & Jurafsky, D. (2020). With little power comes great responsibility. In Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (pp. 9263-9274). Association for Computational Linguistics. https://doi.org/10.18653/v1/2020.emnlp-main.745

Chi, Z., Huang, H., Xu, H.-D., Yu, H., Yin, W., & Mao, X.-L. (2019). Complicated table structure recognition. arXiv. https://arxiv.org/abs/1908.04729

Dagdelen, J., Dunn, A., Lee, S., Walker, N., Rosen, A. S., Ceder, G., Persson, K. A., & Jain, A. (2024). Structured information extraction from scientific text with large language models. Nature Communications, 15, Article 1418. https://doi.org/10.1038/s41467-024-45563-x

Dehghani, M., Mustafa, B., Djolonga, J., Heek, J., Minderer, M., Caron, M., Steiner, A., Puigcerver, J., Geirhos, R., Alabdulmohsin, I., Oliver, A., Padlewski, P., Gritsenko, A., Lucic, M., & Houlsby, N. (2023). Patch n' Pack: NaViT, a vision transformer for any aspect ratio and resolution. In Advances in neural information processing systems 36 (pp. 2252-2274). Neural Information Processing Systems Foundation. https://doi.org/10.52202/075280-0106

Efron, B. (1987). Better bootstrap confidence intervals. Journal of the American Statistical Association, 82(397), 171-185. https://doi.org/10.1080/01621459.1987.10478410

Efron, B. (1979). Bootstrap methods: Another look at the jackknife. The Annals of Statistics, 7(1), 1-26. https://doi.org/10.1214/aos/1176344552

Fellegi, I. P., & Sunter, A. B. (1969). A theory for record linkage. Journal of the American Statistical Association, 64(328), 1183-1210. https://doi.org/10.1080/01621459.1969.10501049

Gemma Team. (2025). Gemma 3 technical report. arXiv. https://arxiv.org/abs/2503.19786

Guo, Z., Xu, R., Yao, Y., Cui, J., Ni, Z., Ge, C., Chua, T.-S., Liu, Z., & Huang, G. (2024). LLaVA-UHD: An LMM perceiving any aspect ratio and high-resolution images. In Computer vision – ECCV 2024 (pp. 390-406). Springer. https://doi.org/10.1007/978-3-031-73010-8_23

Holm, S. (1979). A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics, 6(2), 65-70. https://www.jstor.org/stable/4615733

Huang, Q., Hao, S., Ye, Y., Zhu, S., Feng, Y., & Zhao, D. (2022). Does recommend-revise produce reliable annotations? An analysis on missing instances in DocRED. In Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers) (pp. 6241-6252). Association for Computational Linguistics. https://doi.org/10.18653/v1/2022.acl-long.432

Huang, Z., Chen, K., He, J., Bai, X., Karatzas, D., Lu, S., & Jawahar, C. V. (2019). ICDAR2019 competition on scanned receipt OCR and information extraction. In Proceedings of the 2019 International Conference on Document Analysis and Recognition (ICDAR) (pp. 1516–1520). IEEE. https://doi.org/10.1109/ICDAR.2019.00244

Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast accuracy. International Journal of Forecasting, 22(4), 679-688. https://doi.org/10.1016/j.ijforecast.2006.03.001

Šimsa, Š., Šulc, M., Uřičář, M., Patel, Y., Hamdi, A., Kocián, M., Skalický, M., Matas, J., Doucet, A., Coustaty, M., & Karatzas, D. (2023). DocILE benchmark for document information localization and extraction. In Document analysis and recognition – ICDAR 2023 (pp. 147–166). Springer. https://doi.org/10.1007/978-3-031-41679-8_9

Jaume, G., Ekenel, H. K., & Thiran, J.-P. (2019). FUNSD: A dataset for form understanding in noisy scanned documents. In Proceedings of the 2019 International Conference on Document Analysis and Recognition Workshops (ICDARW) (pp. 1–6). IEEE. https://doi.org/10.1109/ICDARW.2019.10029

Kim, E., Huang, K., Tomala, A., Matthews, S., Strubell, E., Saunders, A., McCallum, A., & Olivetti, E. (2017). Machine-learned and codified synthesis parameters of oxide materials. Scientific Data, 4, Article 170127. https://doi.org/10.1038/sdata.2017.127

Kim, S., & Kim, H. (2016). A new metric of absolute percentage error for intermittent demand forecasts. International Journal of Forecasting, 32(3), 669-679. https://doi.org/10.1016/j.ijforecast.2015.12.003

Kononova, O., Huo, H., He, T., Rong, Z., Botari, T., Sun, W., Tshitoyan, V., & Ceder, G. (2019). Text-mined dataset of inorganic materials synthesis recipes. Scientific Data, 6, Article 203. https://doi.org/10.1038/s41597-019-0224-1

Kuhn, H. W. (1955). The Hungarian method for the assignment problem. Naval Research Logistics Quarterly, 2(1-2), 83-97. https://doi.org/10.1002/nav.3800020109

Makridakis, S. (1993). Accuracy measures: Theoretical and practical concerns. International Journal of Forecasting, 9(4), 527-529. https://doi.org/10.1016/0169-2070(93)90079-3

Masry, A., Long, D. X., Tan, J. Q., Joty, S., & Hoque, E. (2022). ChartQA: A benchmark for question answering about charts with visual and logical reasoning. In Findings of the Association for Computational Linguistics: ACL 2022 (pp. 2263-2279). Association for Computational Linguistics. https://doi.org/10.18653/v1/2022.findings-acl.177

Methani, N., Ganguly, P., Khapra, M. M., & Kumar, P. (2020). PlotQA: Reasoning over scientific plots. In Proceedings of the IEEE/CVF Winter Conference on Applications of Computer Vision (WACV) (pp. 1516-1525). IEEE. https://doi.org/10.1109/WACV45572.2020.9093523

Mistral AI. (2025, March 17). Mistral Small 3.1. https://mistral.ai/news/mistral-small-3-1

Munkres, J. (1957). Algorithms for the assignment and transportation problems. Journal of the Society for Industrial and Applied Mathematics, 5(1), 32-38. https://doi.org/10.1137/0105003

Newcombe, H. B., Kennedy, J. M., Axford, S. J., & James, A. P. (1959). Automatic linkage of vital records. Science, 130(3381), 954-959. https://doi.org/10.1126/science.130.3381.954

Northcutt, C. G., Athalye, A., & Mueller, J. (2021). Pervasive label errors in test sets destabilize machine learning benchmarks. arXiv. https://arxiv.org/abs/2103.14749

Olivetti, E. A., Cole, J. M., Kim, E., Kononova, O., Ceder, G., Han, T. Y.-J., & Hiszpanski, A. M. (2020). Data-driven materials research enabled by natural language processing and information extraction. Applied Physics Reviews, 7(4), Article 041317. https://doi.org/10.1063/5.0021106

Park, S., Shin, S., Lee, B., Lee, J., Surh, J., Seo, M., & Lee, H. (2019). CORD: A consolidated receipt dataset for post-OCR parsing. In Workshop on Document Intelligence at NeurIPS 2019. https://openreview.net/forum?id=SJl3z659UH

Pavlick, E., & Kwiatkowski, T. (2019). Inherent disagreements in human textual inferences. Transactions of the Association for Computational Linguistics, 7, 677-694. https://doi.org/10.1162/tacl_a_00293

Peng, N., Poon, H., Quirk, C., Toutanova, K., & Yih, W.-T. (2017). Cross-sentence n-ary relation extraction with graph LSTMs. Transactions of the Association for Computational Linguistics, 5, 101-115. https://doi.org/10.1162/tacl_a_00049

Polak, M. P., & Morgan, D. (2024). Extracting accurate materials data from research papers with conversational language models and prompt engineering. Nature Communications, 15, Article 1569. https://doi.org/10.1038/s41467-024-45914-8

Raji, I. D., Bender, E. M., Paullada, A., Denton, E., & Hanna, A. (2021). AI and the everything in the whole wide world benchmark. arXiv. https://arxiv.org/abs/2111.15366

Sainz, O., Campos, J., García-Ferrero, I., Etxaniz, J., Lopez de Lacalle, O., & Agirre, E. (2023). NLP evaluation in trouble: On the need to measure LLM data contamination for each benchmark. In Findings of the Association for Computational Linguistics: EMNLP 2023 (pp. 10776-10787). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.findings-emnlp.722

Sclar, M., Choi, Y., Tsvetkov, Y., & Suhr, A. (2023). Quantifying language models' sensitivity to spurious features in prompt design or: How I learned to start worrying about prompt formatting. arXiv. https://arxiv.org/abs/2310.11324

Smock, B., Pesala, R., & Abraham, R. (2023). GriTS: Grid table similarity metric for table structure recognition. In Document analysis and recognition – ICDAR 2023 (pp. 535–549). Springer. https://doi.org/10.1007/978-3-031-41734-4_33

Smock, B., Pesala, R., & Abraham, R. (2022). PubTables-1M: Towards comprehensive table extraction from unstructured documents. In Proceedings of the 2022 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) (pp. 4624–4632). IEEE. https://doi.org/10.1109/CVPR52688.2022.00459

Song, Y., Miret, S., & Liu, B. (2023). MatSci-NLP: Evaluating scientific language models on materials science language tasks using text-to-schema modeling. In Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers) (pp. 3621-3639). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.acl-long.201

Swain, M. C., & Cole, J. M. (2016). ChemDataExtractor: A toolkit for automated extraction of chemical information from the scientific literature. Journal of Chemical Information and Modeling, 56(10), 1894-1904. https://doi.org/10.1021/acs.jcim.6b00207

Tan, Q., Xu, L., Bing, L., Ng, H. T., & Aljunied, S. M. (2022). Revisiting DocRED - Addressing the false negative problem in relation extraction. In Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing (pp. 8472-8487). Association for Computational Linguistics. https://doi.org/10.18653/v1/2022.emnlp-main.580

Wang, P., Bai, S., Tan, S., Wang, S., Fan, Z., Bai, J., Chen, K., Liu, X., Wang, J., Ge, W., Fan, Y., Dang, K., Du, M., Ren, X., Men, R., Liu, D., Zhou, C., Zhou, J., & Lin, J. (2024). Qwen2-VL: Enhancing vision-language model's perception of the world at any resolution. arXiv. https://arxiv.org/abs/2409.12191

Wang, Z., Xia, M., He, L., Chen, H., Liu, Y., Zhu, R., Liang, K., Wu, X., Liu, H., Malladi, S., Chevalier, A., Arora, S., & Chen, D. (2024). CharXiv: Charting gaps in realistic chart understanding in multimodal LLMs. arXiv. https://arxiv.org/abs/2406.18521

Wilcoxon, F. (1945). Individual comparisons by ranking methods. Biometrics Bulletin, 1(6), 80-83. https://doi.org/10.2307/3001968

Xu, Z., Du, S., Qi, Y., Xu, C., Yuan, C., & Guo, J. (2023). ChartBench: A benchmark for complex visual reasoning in charts. arXiv. https://arxiv.org/abs/2312.15915

Yao, Y., Ye, D., Li, P., Han, X., Lin, Y., Liu, Z., Liu, Z., Huang, L., Zhou, J., & Sun, M. (2019). DocRED: A large-scale document-level relation extraction dataset. In Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics (pp. 764-777). Association for Computational Linguistics. https://doi.org/10.18653/v1/P19-1074

Zheng, X., Burdick, D., Popa, L., Zhong, X., & Wang, N. X. R. (2021). Global Table Extractor (GTE): A framework for joint table identification and cell structure recognition using visual context. In Proceedings of the 2021 IEEE Winter Conference on Applications of Computer Vision (WACV) (pp. 697–706). IEEE. https://doi.org/10.1109/WACV48630.2021.00074

Zheng, Z., Zhang, O., Borgs, C., Chayes, J. T., & Yaghi, O. M. (2023). ChatGPT chemistry assistant for text mining and the prediction of MOF synthesis. Journal of the American Chemical Society, 145(32), 18048-18062. https://doi.org/10.1021/jacs.3c05819

Zhong, X., ShafieiBavani, E., & Jimeno Yepes, A. (2020). Image-based table recognition: Data, model, and evaluation. In Computer vision – ECCV 2020 (pp. 564–580). Springer. https://doi.org/10.1007/978-3-030-58589-1_34

## Editor's notes (delete before submission)

**Numbers corrected or deleted (audited against the locked-facts table)**

1. §1: "40.85, 17.47, and 36.36" replaced with the verbatim locked values 40.8488 / 17.4723 / 36.3624. Same correction applied in the abstract and §10.
2. §8 opening: "a scorer with seven known defects" → **eight** (six repaired, two live). The draft's arithmetic was internally inconsistent with its own table.
3. §6.2: the illustrative "reads 12 MPa off a curve whose true value is 4 MPa" was invented; replaced with a unit-free equivalent ("three times its true value → 200 percentage points"), which is arithmetic, not data.
4. §6.3 (retraction): the "2.7x" cross-machine discrepancy is **not in the locked-facts table** and is now **[TK]**, alongside the draft's existing [TK] for the second machine's value. **Flag for the first author:** (a) the locked facts state a single Mac Mini M4 Pro for the whole campaign, so the second machine needs sourcing; (b) as written the two claims are in tension — if the second machine's value lies inside 17.4723–40.8488, the cross-machine ratio is bounded by 2.34x, so a 2.7x figure cannot also be inside the range. Restore the real numbers or cut §6.3.
5. §8.2: deleted "The 12B returns zero rows on three papers — CF-P14, CF-P10 and CF-P15." Not in the locked facts. The recall-collapse mechanism is now argued from locked figures only (rows/run 4.82 vs 2.54, pages 9.46 vs 4.63, precision 0.3464 vs 0.6550).
6. §8.4: deleted the parenthetical assigning specific filters to specific papers ("CF-P11 a narrowed material arm, CF-P18 an FFF-only route filter"). The locked facts list the three filter types but never assign them to papers.
7. §7.1: "the range across the five configurations run on it" → "across the configurations run on it". The configuration count entering the spread computation is not locked.
8. §7.2: "a 4x difference in image tokens per page" → "a roughly fourfold difference" (258 → 1030 is 3.99x).
9. §4: "at least seven independent design decisions" → **nine**, and decision (c) was split into (c) alignment basis and (d) basis selection so the lettering matches the nine-row Table 3 and §4.3's "at least nine". Subsequent letters renumbered (e)–(i).
10. §5.9 heading: "Three of eight came from fixing the other five" → "Three of the eight came from fixing the first". Defects 3, 4 and 5 all descend from the repair of defect 1, not from five separate fixes.
11. §11: "a factor of 4.2" is derived from locked values (4.81 / 1.14 = 4.22).
12. Derived arithmetic used and labelled as such elsewhere: 77.3% (46.4+21.5+9.4); 14.6x (4.81/0.33); 30.8% (4/13); 2/2⁹ ≈ 0.004; ~11x image-token range (258→~2900); 35-fold stability ratio (39.3/1.1); 47% of test rows (56/119); the §10.4 estimates of ~9.5 h (30 runs × 5.24/4.21/9.55 min) and ~28.5 h (three sweep-level repeats).

**Numbers used that are NOT in the locked-facts table — verify before submission**

13. **§10.2: "56 of the 119 test rows".** This figure comes from the section brief, not the locked-facts table, which states only that 6 of 10 test papers are unaudited. Verify or replace with a row count derived from the split file.
14. **§2.3 harness tool names** (`view_page`, `note`, `submit`) are drafted method description, not locked facts. Verify against the harness.
15. **Table 10** retains [TK] for the ceiling share at Dev-13 and Dev-10; only the Dev-9 value (87.2%) is locked.

**An internal tension in the locked facts, resolved one way — please confirm**

16. The locked facts state that **three** dev papers (CF-P11, CF-P18, CF-P24) have ground truth encoding undisclosed curation, but also that the prompt ablation must be restricted to "the eleven no-note papers" and that the naive arm saw no scope note "on CF-P11 or CF-P18". Those are consistent only if the harness ships scope notes for **two** papers, not three. The paper now says exactly that (§2.5), and draws one consequence in §8.6: CF-P24 carries undisclosed curation, receives no scope note, and is the single paper driving the read-only-vs-tooled gap. If in fact three notes ship, §2.5, §8.6 and §8.7's "eleven no-note papers" all need revision.

**Redundancy removed (each now appears once in full)**

17. **21-row all-null run:** full treatment in §5.2 only. §1.1 reduced to a one-clause pointer with no numbers; Table 4 keeps the summary line.
18. **CF-P18 precision-denominator inversion (0.364 / 0.800 / 1.000):** full treatment in §5.6 only. Removed from §1.2; §10.3 cites it by cross-reference with a single number.
19. **Image-token gradient:** the Dev-13/Dev-10/Dev-9 values now live once, in Table 10. §8.3 states the Dev-13 gradient (already in Table 11) and cross-references Table 10 for the flattening instead of restating 1.37 / 1.33 / 0.55.
20. **`extract_naive.py` / `paper_scope_block()` confound:** full disclosure in §8.7 only; §2.5 and §7.2 cross-reference it.
21. **Campaign totals (205+ runs, ~25 h, $0, ~$24 IMPUTED):** stated once in §2.2; removed from §8.1, cited again only in §10.4 for the cost comparison.
22. **"MPa exactly once"** hook: §1 only; §2.1 now carries the CF-P15 page/token figures instead.
23. **Pre-imputation ground truth:** defined once in §2.6; §4.1(e), §5.8 and §8.1 reference it.
24. **Three scope-filter types:** enumerated once in §2.5; §4.1(g), §5.6 and §7.4 refer back.

**Structural and cross-reference repairs**

25. Section titles now name the instrument each section audits (scorer part I / scorer part II / estimator / corpus), and §1's roadmap paragraph was rewritten to match the actual ten-section order — the draft promised "scorer, corpus, reference tables, estimator stability" in that order, which no section followed.
26. There is **no standalone reference-tables section**. That instrument is treated in §2.5, §2.6, §7.4, §9 and §10, and the draft's dangling pointer in §7.4 ("This is a reference-table defect (Section 9)") now points to the audit argument rather than to Limitations. If a reviewer expects a fourth audit section, §10 is the closest thing and could be promoted.
27. Repaired cross-references: §6 "Sections 2–4" → §4–§5; §6.2 "Defect 7 (Section 4)" → §5.7; §6.3 "Section 10" → §8.6; §7 opening "Section 6 showed the scorer could invert" → §5; §7.2 "Section 8's prompt-engineering result" → §8.7; §5.8 "§9" → §8.7; §8.2 the broken "§on the three identical 4B sweeps" → §6.1; §2.5 "Section 8" → §8.7; §4.1 "Section 7" → §7.4.
28. Tables numbered 1–13 and every one is now referenced in the body text.

**Judgement calls worth a second look**

29. §5.10 extends the identity-fixture argument from defects 1, 3, 4 and 6 (the four named in the locked facts) to 2, 7 and 8. That extension is an argument from the definition of an identity fixture, not a locked fact, and is phrased as such.
30. §5.9's claim that defects 3, 4 and 5 were *created by* the repair of defect 1 is narrative, not a locked fact. It is load-bearing for §5.9 and §11; confirm it against the commit history.
31. §8.2's precision-non-monotonicity observation (4B 0.6550 > 27B 0.5766) is new to this merge and comes straight from the locked capacity-curve table.