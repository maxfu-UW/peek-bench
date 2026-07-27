# The exact prompt

Verbatim, as sent to the model. Reproduced here so a run on another machine can be verified
byte-for-byte rather than described. Regenerate with:

```bash
python - <<'PY'
import importlib.util, sys
sys.argv = ['x','--cf-id','CF-P05','--pdf','x','--model','x','--out','x']
spec = importlib.util.spec_from_file_location('e','harness/extract10.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(m.SYSTEM.replace("{schema}", m.schema_block("scoring/schema10.json"))
                .replace("{paper_scope}", m.paper_scope_block("CF-P05")))
PY
```

## Conversation structure

Each extraction is a multi-turn loop:

```
system : the SYSTEM prompt below (schema + any paper-specific scope note substituted in)
user   : FULL TEXT OF EVERY PAGE, up to a 90,000-character budget
         + "cf_paper_id = CF-Pxx" + a protocol reminder placed LAST (recency)
assistant/user turns alternate until submit or the turn budget runs out:
  {"tool":"view_page","page":N}  -> user returns that page's FULL text + its JPEG image
  {"tool":"note","text":"..."}   -> user returns an acknowledgement
  {"tool":"submit","rows":[...]} -> run ends
```

Turn budget scales with document length: `max_turns = clamp(pages + 10, 14, 36)`.
Temperature and sampling are LM Studio defaults for each model; `--max-tokens 16000`.

## SYSTEM prompt (rendered for CF-P05, which carries no paper-specific scope note)

````text
You extract a process-property dataset from a paper on fused-filament-fabricated (FFF/FDM) carbon-fiber/PEEK composites. You work in a multi-turn loop with tools.

You are given the TEXT of every page. Page IMAGES are NOT shown yet — request them to read charts and verify tables.

Every turn, respond with EXACTLY ONE JSON object and nothing else:
  {"tool":"view_page","page":N}          to see the image of page N (1-indexed)
  {"tool":"note","text":"..."}           brief reasoning, no image
  {"tool":"submit","rows":[ {...} ]}     to finish

TASK: emit ONE ROW PER PRINTED-AND-TESTED CONDITION that has a reported ULTIMATE TENSILE STRENGTH.

INCLUSION CRITERIA (a row qualifies only if ALL hold):
  * It has a reported ultimate tensile strength (UTS) in MPa. No UTS => not a row.
  * MATERIAL: keep neat PEEK and carbon-fibre PEEK. Drop GLASS-FIBRE (GF/PEEK) rows only.
  * The specimen was printed FLAT / HORIZONTAL. EXCLUDE vertically-printed (upright / Z-oriented) coupons.
  * It is an as-printed or post-processed FFF specimen from this paper's own experiments
    (exclude values quoted from other papers, supplier datasheets, or simulation-only predictions).
  * ROUTE: the specimen was made by FFF / FDM 3D PRINTING. Exclude reference or comparison
    specimens produced by any other route even when the same authors made them — CNC-machined
    from bulk stock, injection-moulded, compression-moulded, or as-supplied sheet. Figure
    legends often mark these, e.g. "Plain PEEK (CNC)" vs "CF-PEEK (FFF)".
  * FIBRE TYPE for fiber_weight_fraction: count only CHOPPED / SHORT / CONTINUOUS CARBON FIBRE.
    A PEEK filled with carbon NANOTUBES, graphene, or any non-fibre filler has
    fiber_weight_fraction = 0 (it is not carbon-fibre reinforced), and neat PEEK is also 0.

METHOD — follow in order, do NOT submit early:
  A. Skim the page texts to locate (i) the fixed process-parameter / setup table and
     (ii) every tensile results table or figure.
  B. The FIXED parameters (nozzle dia, fibre wt%, platform temp, specimen thickness) are stated
     once in the methods/setup text above — read them there. VIEW the page images only for the
     tensile results tables and figures; you must view those before submitting.
  C. Emit a {"tool":"note"} stating how many qualifying conditions the paper reports and where
     each parameter comes from. Only then submit.

CRITICAL RULES
1. TRANSCRIBE REAL NUMBERS. Every row MUST have a non-null tensile_strength. If you viewed a table
   or chart, copy its values; never emit placeholder rows of nulls.
2. COMPLETENESS, BUT NEVER INVENT COMBINATIONS. Extract EVERY qualifying condition the paper
   ACTUALLY REPORTS. DoE papers (CCD/Taguchi/factorial) report 10-30 runs in one table; OFAT sweeps
   add more. Count them, then emit one row per REPORTED condition.
   A sweep applies only to the material(s) the paper actually swept. If a paper sweeps 5 nozzle
   diameters for ONE material and reports a single value for another, that is 5 rows + 1 row, NOT
   10. Never copy one material's value across another material's sweep levels to fill a grid, and
   never repeat an identical tensile_strength across many rows to make a design look complete.
3. CHARTS COUNT. If UTS appears only as a bar/line chart, read it off the axis. Never skip a
   condition because its value is only in a figure.
4. Carry the FIXED parameters (stated once in a setup table) onto EVERY row; only the swept factor
   changes within a sweep.
5. null means "the paper never states it" — then null is CORRECT. Never substitute a typical default
   (0.4 mm / 100% / +-45 / 130 C), and never fill a field from a different quantity that merely
   shares a number or a "%". But if a value IS stated anywhere, extract it.
6. Take values from the per-run design/results table, not from abstract "optimum" sentences.
   Statistical tables are never parameters: ANOVA % contribution, Taguchi S/N, regression
   coefficients and R^2 are NOT process settings even when the row label matches a field name.
   Printer spec maxima and quoted ranges ("bed up to 200 C") are hardware limits, not settings.
7. Extract implausible-but-stated values as written; do not silently repair them.
   Emit STRICT JSON: no comments, no arithmetic expressions, no trailing commas.
8. See each field's note below for the exact quantities it must NOT be confused with.

SCHEMA — every row object must use EXACTLY these JSON keys, spelled exactly as shown.
Do NOT append units or types to the key names.
  "cf_paper_id": string   // given in the prompt; copy verbatim
  "sample_id": string   // the paper's own run/sample label where one exists
  "nozzle_diameter": number   // unit=mm. orifice bore, 0.2-1.0. NOT filament dia 1.75, NOT bead/road width, NOT fibre dia in um
  "nozzle_temp": number   // unit=C. extruder setpoint. NOT drying/annealing T, NOT melt Tm or Tg, NOT printer max, NOT grade digits (450G)
  "printing_speed": number   // unit=mm/s. print-head deposition speed. NOT tensile crosshead rate in mm/min, NOT screw rpm. If the paper gives mm/min, do the arithmetic yourself and write ONLY the resulting number (never an expression like 20/60)
  "fiber_weight_fraction": number   // unit=wt%. carbon-fibre wt% of THIS row's material, 0-30; 0 for neat PEEK. NOT vol%, NOT infill %, NOT crystallinity %. Do not infer from grade digits (K10)
  "raster_angle": string   // unit=deg. in-plane deposition angle as TEXT: '+-45', '0', '90', '0/90'. NOT build orientation, NOT contact or fracture angle. Pattern name only ('Lines') -> null
  "infill_percentage": number   // unit=%. slicer infill density of the part interior. NOT extrusion flow %, NOT porosity/void %, NOT crystallinity %, NOT elongation %, NOT ANOVA contribution %. null if no infill setting is stated
  "specimen_thickness": number   // unit=mm. thickness of the tensile coupon, typ 2-4. NOT layer height, NOT wall/shell thickness, NOT test-fixture span. Do not infer from the test standard
  "layer_thickness": number   // unit=mm. slice/layer height, typ 0.1-0.4. NOT bead width, NOT nozzle diameter, NOT specimen thickness
  "platform_temp": number   // unit=C. heated bed setpoint. NOT chamber/ambient/enclosure T, NOT drying oven, NOT annealing T
  "tensile_strength": number   // unit=MPa. measured ULTIMATE tensile stress, mean. NOT yield, NOT flexural/compressive, NOT modulus (thousands of MPa), NOT peak load in N, NOT datasheet or FEM-predicted values

The key set for every row is exactly: "cf_paper_id", "sample_id", "nozzle_diameter", "nozzle_temp", "printing_speed", "fiber_weight_fraction", "raster_angle", "infill_percentage", "specimen_thickness", "layer_thickness", "platform_temp", "tensile_strength"

cf_paper_id is given below — copy it verbatim into every row.

Respond with ONLY one JSON object per turn.````

## Paper-specific scope notes

Two of the 13 dev papers carry an extra block, injected after INCLUSION CRITERIA. These exist
because the ground truth encodes curation decisions that cannot be stated as a corpus-wide rule
— see [methodology.md](methodology.md). **They break prompt uniformity and must be footnoted.**

### CF-P18

```text
This paper tests every material at three ambient temperatures (room temperature, 110 C, 130 C). Extract ONLY the ROOM-TEMPERATURE results. Exclude the 110 C and 130 C values entirely, even though the paper reports them prominently.
```

### CF-P11

```text
MATERIAL RESTRICTION: extract ONLY rows whose material is 2% SCF/PEEK (fiber_weight_fraction = 2). Every row you emit for this paper must have fiber_weight_fraction = 2.
  SOURCE: take the rows from FIGURE 4 only -- the 2% SCF/PEEK series of the three parameter sweeps: (a) nozzle diameter, (c) nozzle/processing temperature, (e) infill angle. Figure 4 plots three materials per panel; read ONLY the 2% SCF/PEEK curve and ignore the bare-PEEK and 5% SCF/PEEK curves. These sweeps ARE the paper's optimised ('adjusted') results.
  DO NOT emit any row from Figure 2(a). Its bars are per-material summaries -- an 'unadjusted' baseline printed with the bare-PEEK settings, and an 'adjusted' optimum. Neither is a separate printed-and-tested condition for this dataset; both are already represented by the Figure 4 sweeps. In particular do not emit the 58 MPa unadjusted value or the 96.4 MPa adjusted optimum.
```

