# ECM direction disagreement is broad across genes and sensitive to age support

Computed 2026-10-19. This advances the youthful-function workstream by testing
whether the opposing gingival structural-matrix directions are concentrated
in a few genes or depend on the sampled age distribution. No new cohort,
panel, age clock or intervention was introduced.

**Result:** the full-cohort fibroblast/bulk disagreement spans seven of eight
fixed ECM genes in age-only fits and all eight after source-specific
adjustment. Removing any one gene preserves each panel direction. However,
restricting the nominal common age span removes all older bulk donors and
reverses that cohort's direction for all eight genes. A different, coarse
shared-decade restriction retains older adults and the original opposition.
This is evidence of population-dependent descriptive associations, not a
resolution into a causal aging program or matched-age validation.

## Fixed inputs, genes and demographic rules

The [plan](analysis_plan.json) was specified after earlier panel results and
metadata review, before this batch's gene/support outcomes. It was not
preregistered. The eight equally weighted genes are unchanged:
`COL1A1, COL1A2, COL3A1, COL5A1, COL6A1, FN1, DCN, LUM`.
All eight occur for every eligible donor in both cohorts; no annotation
substitution, missing-gene imputation or outcome-based selection is used.

Existing public tables supply four separate measurements:

- GSE164241 fibroblast-only raw-count `log1p(CPM)`.
- GSE164241 observed and common-RNA-weight **partial captured-cell** mixtures
  from the [previous disjoint-compartment challenge](../../checklist-mechanisms-2026-10-19/aging/REPORT.md).
- GSE173078 bulk-gingiva gene values from the
  [separate-cohort challenge](../../checklist-followup-2026-10-19/aging/REPORT.md).

These are different estimands and assay contexts. The partial mixtures omit
386 captured cells with unknown RNA and cannot be called intact-tissue bulk.
The original 13 healthy inferred GSE164241 donors and 12 source-labelled
healthy GSE173078 participants remain the units; cells, genes and repeated
biopsies do not become extra people. Original experiment and public sources:
[Williams et al., 2021](https://doi.org/10.1016/j.cell.2021.05.013),
[GSE164241](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE164241),
[GSE173078](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE173078).
No new source data were acquired.

A [metadata-only script](freeze_populations.py) freezes the following
populations before gene outcomes. Exact retained **donor IDs, ages, sex and
processing labels** are preserved in [frozen populations](frozen_populations.json).

| Population | GSE164241 donors / retained ages | GSE173078 donors / retained ages |
| --- | --- | --- |
| Original healthy cohorts | 13: 21,21,22,24,28,31,32,35,37,39,51,57,61 | 12: 28,32,37,39,40,42,42,45,63,66,68,75 |
| Intersection of original observed age spans, 28–61 | 9: 28,31,32,35,37,39,51,57,61 | 8: 28,32,37,39,40,42,42,45 |
| Decade bins occupied by both original cohorts: 20s/30s/60s | 11: 21,21,22,24,28,31,32,35,37,39,61 | 7: 28,32,37,39,63,66,68 |

The common-span rule does **not** produce matched distributions: the retained
bulk sample has nobody aged 46–61. The decade rule is also coarse support,
not matching: its older cell-source bin contains one 61-year donor versus
bulk donors aged 63, 66 and 68; its twenties bin contains five versus one.
Neither restriction establishes improved clinical validation, overlap of
unmeasured covariates, or adequate older-male representation.

Separate within-source models use age only, or age plus sex and processing.
Processing means Cell Ranger version for GSE164241 and batch A/B for
GSE173078, with no pooled batch correction. All genes in each fit use exactly
the same donors/design. Failed rank or residual-degrees-of-freedom checks
would remain explicit; none occurred in these specified full fits or donor
omissions.

## All eight full-cohort gene effects

Slopes below are relative gene `log1p(CPM)` per decade; numerical scales are
not pooled across assays. Signs are descriptive and do not establish
individual-gene significance or functional effects.

| Gene | Fibroblast, age only | Bulk, age only | Fibroblast, adjusted | Bulk, adjusted |
| --- | ---: | ---: | ---: | ---: |
| COL1A1 | +0.248 | −0.265 | +0.311 | −0.318 |
| COL1A2 | +0.212 | −0.048 | +0.245 | −0.234 |
| COL3A1 | +0.251 | −0.271 | +0.281 | −0.306 |
| COL5A1 | +0.165 | −0.039 | +0.201 | −0.208 |
| COL6A1 | +0.183 | −0.066 | +0.238 | −0.195 |
| FN1 | +0.085 | +0.006 | +0.077 | −0.126 |
| DCN | +0.124 | −0.288 | +0.132 | −0.339 |
| LUM | +0.111 | −0.191 | +0.002 | −0.164 |

The exception in age-only fits is near-zero bulk FN1; adjusted fibroblast
LUM is also near zero. These small signs should not be overread. Nevertheless,
the full-panel disagreement is not solely one gene carrying the average.
The largest full age-only absolute coefficient shares are 18.2% for fibroblast
COL3A1 and 24.6% for bulk DCN. These are algebraic contribution shares, not
causal fractions or variance explained.

Under a shared design, the slope of the mean eight-gene score equals the mean
of the eight gene slopes. The script verifies that identity within 10⁻¹².
[All 192 gene effects and contributions](derived/gene_contributions.tsv)
and [cross-cohort gene directions](derived/cross_cohort_gene_directions.tsv)
are retained, including both partial-mixture modes and every population.

## Age-support restrictions change the answer

Each cell in this table shows **age-only / adjusted** panel slopes per decade.

| Population | Fibroblast only | Observed partial capture | Common-RNA partial capture | Bulk gingiva |
| --- | ---: | ---: | ---: | ---: |
| Original healthy cohorts | +0.172 / +0.186 | +0.213 / +0.187 | +0.183 / +0.192 | −0.145 / −0.236 |
| Common observed span, 28–61 | +0.121 / +0.155 | +0.120 / +0.089 | +0.140 / +0.172 | +0.562 / +0.481 |
| Shared nonempty decade bins | +0.188 / +0.189 | +0.163 / +0.136 | +0.182 / +0.180 | −0.144 / −0.237 |

In the common-span bulk subset, **all eight gene slopes become positive**
in both models, and the panel remains positive in every donor omission.
Its adjusted maximum leverage is **0.862**, for the 28-year participant
AC018. The positive narrow-range association and the negative full-range
association are different sampled contrasts; they do not demonstrate a
nonlinear biological trajectory or identify the reason for reversal.

The shared-decade full fits retain negative bulk and positive cell-derived
directions. Yet its cell-source adjusted maximum leverage is **0.724** for
the single 61-year donor; bulk adjusted leverage is **0.800** for AC018.
The unadjusted bulk panel changes sign when AC016, age 68, is omitted
(−0.144 full versus +0.033 after omission). The adjusted bulk omission
range stays negative (−0.275 to −0.131).

One other fragile result stays visible: in the common-span observed partial
mixture, the adjusted +0.089 slope becomes −0.082 after omitting `health:241`
or −0.016 after omitting `health:148`. All the
[24 panel fits](derived/fixed_panel_age_effects.tsv) retain rank, residual
degrees of freedom, exact maximum-leverage identity and
[252 individual donor omissions](derived/donor_omissions.tsv).

Every one of the **192 single-gene omission diagnostics** retains its own
full-panel sign. No seven-gene subset is selected as a replacement panel.
The complete [gene-omission table](derived/all_gene_omissions.tsv) shows every
omission, rather than only favorable subsets. Gene omissions are diagnostics,
not eight independent biological replications.

## Research decision and limits

The first question now has a bounded answer: the original full-cohort
opposition is broad across this fixed ECM panel, rather than an isolated
feature. The second question exposes a larger problem: changing age support
can reverse the entire bulk panel, while a different coarse restriction
retains the conflict. An age-signature interpretation therefore depends
strongly on whom and what range was sampled.

This cannot distinguish biological age dependence from cell mixture,
clinical ascertainment, tissue site, sequencing/processing or other donor
differences. The restrictions were frozen from metadata, but they still alter
the population and do not recover absent older men or matched donor/assay
pairs. The earlier common-RNA weights remain frozen from all 13 healthy
cell-source donors, including donors omitted by these restrictions; this
work is not held-out validation.

The next discriminant remains matched-donor bulk and cell-resolved tissue
with overlapping age/sex coverage, site/health qualification and independent
functional measurements. Until that exists, neither increasing nor decreasing
an ECM transcript mean should be treated as a rejuvenation endpoint. Dental
matrix architecture, barrier, bilateral attachment, mechanical recovery and
durability after finite support remain separate required outcomes.

## Reproduce and inspect

```powershell
python studies/checklist-translation-2026-10-19/aging/freeze_populations.py
python studies/checklist-translation-2026-10-19/aging/analyze_gene_support.py
python -m unittest discover -s tests -p test_checklist_translation_aging_support.py -v
```

The analysis/tests need NumPy; demographic freezing uses the standard library.
Twelve new checks pass, including fixed-gene OLS additivity, all eight
omissions, exact donor sets, rank failure, coarse versus common-span support,
donor influence counts and receipt hashes. The analyzer independently
recomputes the healthy-only metadata populations to reject changed membership.
No source acquisition, new fetch provenance, model/gene optimization or new
method package was added. Docker workbench remains unavailable.

[The summary](derived/analysis_summary.json) pins plan/population/script/output
hashes and software; [the healthy gene table](derived/healthy_gene_values.tsv)
retains the actual input values used. All previous source qualifications,
unknowns and rights remain applicable. Original source data and observations
belong to their authors; these are computational reanalyses and explicitly
bounded diagnostics, not new wet-lab findings.
