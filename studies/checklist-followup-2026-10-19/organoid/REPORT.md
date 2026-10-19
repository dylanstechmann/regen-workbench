# Functional response in a perfused pancreatic spheroid model

AI-assisted reanalysis, 2026-10-19. This follows the checklist's organoid and
engineered-tissue goal with actual published functional measurements. It
replaces no earlier result and does not establish rejuvenation or organ
replacement.

## What was acquired and checked

We retrieved the primary XML and the unmodified **29,553-byte Source Data
workbook** for [Quintard et al., 2024](https://doi.org/10.1038/s41467-024-45710-4).
The workbook SHA-256 is pinned in the [analysis plan](analysis_plan.json).
Read-only extraction from `Figure 7` retains 48 paired low/high insulin
observations and their exact source-cell coordinates. Every recomputed
high/low ratio matches the workbook's Figure 7d stimulation index exactly.
The source workbook remained byte-identical after analysis.

The source construct uses EndoC-βH5 cells with fibroblasts and endothelial
cells. It is a pancreatic islet spheroid model, not a patient-islet graft or
the blood-vessel organoid experiment elsewhere in the paper. Each Figure 7
point is described as a spheroid observation. Donor, manufacturing-lot and
chip/circuit mappings are unavailable in this workbook. The methods mention
duplicate assay measurements; duplicates do not add biological units.

## Results from measured source observations

Stimulation index (SI) is high-glucose insulin concentration divided by the
paired low-glucose concentration. Both concentrations use pg/mL.

| Source condition | Reported observations | Mean SI | Median SI | Sample SD | Mean low insulin | Mean high insulin |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Conventional well | 22 | 1.442 | 1.254 | 0.359 | 27,523 | 38,346 |
| Static, no surrounding vascular bed | 5 | 1.311 | 1.366 | 0.185 | 29,332 | 38,399 |
| Static, with vascular bed | 5 | 1.470 | 1.572 | 0.347 | 41,553 | 59,364 |
| Flow, no surrounding vascular bed | 5 | 1.398 | 1.243 | 0.356 | 21,354 | 29,278 |
| Flow, with vascular bed | 11 | 2.631 | 2.725 | 0.903 | 16,169 | 43,668 |

The combined flow/vascular-bed condition has the highest mean and median SI.
Its mean SI exceeds the well condition by **1.189**, a **1.825-fold ratio of
group means**. It exceeds the static/no-bed condition by **1.320**. The
descriptive four-chip-condition contrast is +1.075 SI units, calculated as
combined − flow-only − bed-only + neither. This is not a donor-independent or
causal interaction estimate.

Higher SI does **not** mean that absolute stimulated insulin is highest:
the static/vascular-bed mean high-glucose concentration is larger than the
combined condition's. The baseline concentrations also differ substantially.
The combined condition's mean of individual SIs is 2.631, whereas the ratio
of its group mean concentrations is 2.701. Those are different quantities;
the former reproduces Figure 7d. Do not substitute one for the other.

Across **81 single-observation omissions**, the combined-versus-well mean
difference ranges +1.022 to +1.304 SI units. Every corresponding chip-control
contrast also remains positive. These are influence checks on the reported
assay observations, not leave-one-donor validation or confidence intervals.
All rows, condition summaries and contrasts are retained in [derived outputs](derived/analysis_receipt.json).

## Source statistics and inference limits

The Figure 7 caption describes unpaired two-sided t tests. The workbook's
SI analysis includes ANOVA with Dunnett comparisons, and reports a
Brown–Forsythe variance-test P value of 0.004. We preserve that discrepancy
and the source outputs in [a separate context record](derived/source_statistics_context.json).
We do not resolve it by silently selecting one test or by treating source
P values as new confirmatory results.

No donor/batch-adjusted inference is possible without the missing mapping.
The numerical direction survives individual-row omissions, but unobserved
manufacturing or cell-source differences could still explain some of it.
This is exploratory source-data reanalysis selected after reading the paper,
not an untouched validation cohort or a calibrated treatment prediction.

## What this advances for regeneration

The data make **coupled transport and niche architecture** a concrete
functional comparator. Comparing flow and surrounding endothelium separately
and together can discriminate an interaction that a viability marker or
vessel image alone would miss. SI, absolute secretion, viability and lineage
identity must remain separate outcomes.

The next evidence intake should obtain traceable donor/lot, spheroid and
circuit identifiers plus paired perfusion, viability, identity and functional
measurements. An independently replicated construct comparison can then
test whether the functional difference persists at the correct biological
unit. Do not infer those joint outcomes from the marginal SI result.

For the dental programme, this supports evaluating perfused niches as one
component of pulp/attachment constructs. It supplies no inserted PDL fibers,
enamel/dentin recovery, tooth positioning, sensory integration or durability
after support withdrawal. Those remain required in the
[restoration contract](../../periodontal-attachment-restoration-2026-10-11/restoration_contract.json).
Genome correction would add its own product/identity/function requirements;
no genetic editing was evaluated in this source experiment.

## Reproduce and credit

With the source workbook in the recorded local data directory and `openpyxl`
available, run from the repository root:

```text
python studies/checklist-followup-2026-10-19/organoid/analyze_islet_function.py
python -m unittest discover -s tests -p test_islet_source_function.py -v
```

Eight tests check ratio reconstruction, units, incomplete pairs, measured
zero versus missing values, observation counts and influence calculations.
The [receipt](derived/analysis_receipt.json) pins source bytes, script, plan
and outputs in canonical UTF-8/LF form. Raw workbook editing was not performed.

Credit: **Quintard C. et al. (2024), A microfluidic platform integrating
functional vascularized organoids-on-chip, Nature Communications 15:1452**,
[DOI 10.1038/s41467-024-45710-4](https://doi.org/10.1038/s41467-024-45710-4).
The article is [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Source-derived numerical tables retain that attribution/license. Changes:
extracted source-cell-linked pairs, recomputed SI, generated descriptive
summaries and single-row influence analyses. No source images, diagrams,
full text or complete workbook are redistributed in GitHub. Generic study
code is separate from this source-data license.
