---
name: peek-extract
description: Extract a process-property dataset (9 FFF process parameters + ultimate tensile strength) from a carbon-fibre/PEEK additive-manufacturing paper. Use when asked to pull printed-and-tested conditions, process parameters, or tensile data out of an FFF/FDM PEEK study, or to add a paper to PEEK-Bench.
---

# Extracting a PEEK process-property dataset

Emit **one row per printed-and-tested condition that has a reported ultimate tensile strength**.

The hard part is not the prose. In this corpus a large share of tensile values exist **only inside
raster figures** — printed bar labels, swept curves, axis ticks. A paper can contain the string
`MPa` exactly once and still report nine tensile values. **Look at the page images.** Answering from
the text layer alone silently loses most of the data.

## Inclusion criteria — a row qualifies only if ALL hold

- It has a reported **ultimate tensile strength in MPa**. No UTS ⇒ not a row.
- **Material**: keep neat PEEK and carbon-fibre PEEK. Drop glass-fibre (GF/PEEK) rows.
- Printed **flat / horizontal**. Exclude vertical / upright / Z-oriented coupons.
- An **as-printed or post-processed FFF specimen from this paper's own experiments** — exclude values
  quoted from other papers, supplier datasheets, or simulation-only predictions.
- **Route**: made by FFF/FDM printing. Exclude reference specimens made another way *even by the same
  authors* — CNC-machined, injection-moulded, compression-moulded, as-supplied sheet. Figure legends
  often mark these, e.g. `Plain PEEK (CNC)` vs `CF-PEEK (FFF)`.

## Method

1. Locate the fixed process-parameter/setup table, and every tensile results table or figure.
2. Fixed parameters (nozzle diameter, fibre wt%, platform temp, specimen thickness) are usually
   stated **once** in the methods. Read them there.
3. **Open the page images** for the results tables and figures before answering.
4. State how many qualifying conditions the paper reports and where each value came from, then emit
   the rows.

## Fields

| field | unit | must NOT be confused with |
|---|---|---|
| `nozzle_diameter` | mm | filament dia 1.75, bead/road width, fibre dia in µm |
| `nozzle_temp` | °C | drying/annealing T, melt Tm or Tg, printer max, grade digits (450G) |
| `printing_speed` | mm/s | tensile crosshead rate in mm/min, screw rpm |
| `fiber_weight_fraction` | wt% | vol%, infill %, crystallinity %. Grade digits (K10) are not a loading |
| `raster_angle` | deg, **text** | build orientation, contact/fracture angle. Pattern name only ("Lines") → null |
| `infill_percentage` | % | **extrusion flow %**, porosity/void %, crystallinity %, elongation %, ANOVA contribution % |
| `specimen_thickness` | mm | layer height, wall/shell thickness, test-fixture span |
| `layer_thickness` | mm | bead width, nozzle diameter, specimen thickness |
| `platform_temp` | °C | chamber/ambient/enclosure T, drying oven, annealing T |
| `tensile_strength` | MPa | yield, flexural/compressive, modulus (thousands of MPa), peak load in N, datasheet or FEM values |

Carbon **nanotube**-filled PEEK has `fiber_weight_fraction = 0` — it is not carbon-fibre reinforced.
Neat PEEK is also 0.

## Rules learned the hard way

1. **Transcribe real numbers.** Every row must have a non-null `tensile_strength`. A row with no
   measurement is not a row — this was the single most common failure in benchmarking, and such runs
   score zero by design.
2. **Completeness, but never invent combinations.** A sweep applies only to the materials the paper
   actually swept. Five nozzle diameters for one material plus a single value for another is
   5 + 1 rows, not 10. Never copy one material's value across another's sweep levels, and never
   repeat an identical UTS across many rows to make a design look complete.
3. **Charts count.** If UTS appears only as a bar or line chart, read it off the label or axis.
4. **Carry the fixed parameters onto every row**; only the swept factor changes within a sweep.
5. **`null` means "the paper never states it"** — and then null is *correct*. Never substitute a
   typical default (0.4 mm, 100 %, ±45, 130 °C). Never fill a field from a different quantity that
   merely shares a number or a `%`.
6. **Per-run tables, not abstract "optimum" sentences.** ANOVA % contribution, Taguchi S/N,
   regression coefficients and R² are not process settings. Printer spec maxima ("bed up to 200 °C")
   are hardware limits, not settings.
7. **Extract implausible-but-stated values as written.** Do not silently repair them.
8. **Units**: `printing_speed` in mm/s. If the paper gives mm/min, do the arithmetic and write only
   the resulting number — never an expression like `20/60`. Strict JSON: no comments, no arithmetic,
   no trailing commas.

## Traps actually observed in this corpus

- `infill_percentage` taken from *"extrusion flow of 100 %"* — a different quantity entirely.
- Reading the **wrong temperature group** off a 3×3 figure and reporting it as room temperature.
- Collapsing a raster-angle sweep (0–90°) to a single `raster_angle = 0`, because the methods table
  states a default and the sweep appears only in a figure.
- Treating a paper's summary bars ("unadjusted" vs "adjusted") as separate printed conditions when
  they aggregate sweeps already extracted.
- Inferring a fibre loading from a commercial grade name (`CF10`, `K10`) when the paper never states
  the number in words.

## Scope beyond the paper

Ground truth for a benchmark may encode curation decisions the paper cannot tell you — e.g. keeping
only room-temperature rows from a study that also reports 110 °C. If a per-paper scope note is
supplied, it **narrows** these criteria and takes precedence. Without one, extract everything that
meets the criteria above.

## Output

One object per condition using the field names verbatim, with `cf_paper_id` copied unchanged onto
every row. Report the count of qualifying conditions and the provenance of each value alongside the
rows.
