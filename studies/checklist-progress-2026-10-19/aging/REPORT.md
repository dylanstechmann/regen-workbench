# Donor confounding and fibroblast-mixture challenge

Date: 2026-10-19. Persistent goal: [durable youthful function throughout the
body](../../restoration-run-plan-2026-10-11/GOALS_AND_CONTINUITY.md), including
the oral tissues needed for full tooth restoration.

The earlier cell-resolved gingival result survives several new challenges:
the positive healthy-age structural-matrix association persists after sex and
processing-version adjustment and after fixing the two fibroblast subgroups'
RNA contributions. Disease-associated fibroblast degradation, inhibitor and
inflammatory scores also keep their positive directions. However, this cohort
has poor age/sex overlap, and small near-zero matrix/barrier contrasts are
unstable. None of these expression results establishes younger tissue or
functional repair.

## What was actually run

This is a new sensitivity analysis of existing public donor pseudobulk tables,
not a new experiment or independent validation. The [plan](analysis_plan.json)
was specified after reading the earlier reports and before running these new
outcomes. It was not independently preregistered. Four input text hashes pin
the tables to source commit `439c3306709777b80e604690e232a7b89e6b3ee7`.

The original human oral single-cell experiment is [Williams et al.,
2021](https://doi.org/10.1016/j.cell.2021.05.013), deposited as
[GSE164241](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE164241).
The earlier workbench analysis used the curated [CELLxGENE periodontal
atlas](https://cellxgene.cziscience.com/collections/71f4bccf-53d4-4c12-9e80-e73bfb89e398),
verified integer raw counts, and summed repeated biopsies within inferred
donors. Its [qualification and limitations](../../aging-state-2026-10-11/GINGIVAL_CELL_RESOLVED_CHALLENGE_REPORT.md)
remain applicable. No raw H5AD was reread or new network download made here.

This challenge retains 13 healthy and five inferred periodontitis donors.
Cells and repeated biopsies do not increase the number of independent people.
Only nine non-overlapping cell compartments enter the comparison;
their donors overlap, and their scores are correlated. Fibroblast/epithelial
and lymphoid subgroups are not counted again as replications.

The unchanged gene panels are scored in mean `log1p(CPM)`. The script fits
**98 disease-model rows**, **56 healthy-age-model rows**, **488 individual
donor omissions**, and **80 observed/fixed-mixture model rows**. It retains
rank or sample-size failures if they occur; none occurred in these specified
fits. All coefficients are descriptive. No p-values, age-in-years conversion,
intervention prediction or rejuvenation threshold is supplied.

## Sparse shared age and sex support

The disease donors span ages 34–45. Healthy donors span 21–61, but only **three
healthy donors**, ages 35, 37 and 39, fall inside that interval. All three are
female. Healthy men are 21, 28 and 32; the two disease men are 44 and 45, so
the male groups have **no overlapping age ranges**. For the Cell Ranger 3.0.1
subset, just two healthy donors fall inside the disease age range.

Consequently, a full-cohort age/sex/version-adjusted coefficient still relies
on a linear/additive model across unevenly supported groups. Adjustment does
not manufacture the missing age-matched people. The female overlap
sensitivity leaves only three healthy and three disease donors in the
well-covered compartments, and two healthy donors for three other
compartments. It is useful for exposing extrapolation, but cannot settle it.
See [all demographic strata](derived/donor_common_support.tsv).

## Disease contrasts: strong directions and fragile ones

The table shows disease minus healthy expression-score differences. The
overlap models retain the full panel/group's age-range intersection, fixed
before restricting by sex. They include age adjustment but cannot support the
full covariate set with this sampling. Restricted and full-cohort estimates
also refer to different donor subsets; the changes are not a pure estimate
of bias removal.

| Cell compartment and panel | Age adjusted | Age, sex, version adjusted | Age overlap | Female age overlap |
| --- | ---: | ---: | ---: | ---: |
| Fibroblasts, degradation | +1.056 | +1.039 | +1.456 | +1.421 |
| Fibroblasts, inhibitors | +0.391 | +0.378 | +0.493 | +0.477 |
| Fibroblasts, inflammation | +0.949 | +0.907 | +1.128 | +1.095 |
| Fibroblasts, structural ECM | −0.004 | −0.029 | +0.140 | +0.138 |
| Fibroblasts, stromal identity | +0.109 | +0.060 | +0.231 | +0.229 |
| Epithelium, barrier/identity | −0.097 | −0.108 | +0.294 | +0.376 |
| Epithelium, inflammation | +1.102 | +1.043 | +1.557 | +1.580 |
| Endothelium, inflammation | +0.806 | +0.752 | +0.876 | +0.845 |
| Perivascular support, inflammation | +1.001 | +0.957 | +1.050 | +1.080 |
| Dendritic cells, inflammation | +1.009 | +0.991 | +1.681 | +1.698 |
| Lymphoid cells, inflammation | +0.113 | +0.127 | +0.291 | +0.292 |
| Macrophages/monocytes, inflammation | +1.041 | +0.875 | +1.507 | +1.668 |
| Mast cells, inflammation | +1.121 | +1.114 | +1.546 | +1.581 |
| Neutrophils, inflammation | +1.353 | +1.340 | +1.367 | +1.336 |

The seven specified models also retain the unadjusted, age-plus-sex and
age-plus-version outcomes in the [complete table](derived/disease_adjustment_challenge.tsv).
Positive degradation, inhibitor and inflammatory transcript scores should
not be interpreted as higher measured enzyme activity or repaired matrix.

Omitting each donor once preserved positive fibroblast degradation,
inhibitor and inflammation differences in both the age-only and fully
adjusted models. In the fully adjusted model, the 18 donor-omission ranges
were +0.946 to +1.165, +0.311 to +0.454 and +0.666 to +1.042, respectively.
These are sensitivity ranges, not confidence intervals.

The fibroblast structural-ECM contrast was different: its age-only coefficient
changed sign in **10 of 18** omissions, spanning −0.040 to +0.023. Even the
fully adjusted coefficient crossed zero once, ranging −0.064 to +0.013.
The epithelial barrier/identity difference changed sign after one case was
omitted in each adjustment set. Lymphoid inflammation changed sign in one
age-only omission and two fully adjusted omissions. The small direction
labels for these readouts are therefore unreliable. All donor-level failures,
sign changes and case-only omission summaries are retained in
[individual omissions](derived/donor_omission_effects.tsv) and their
[summary](derived/donor_omission_summary.tsv).

## Fixing fibroblast subtype composition

For every panel and all 18 donors, the script first verifies that Fibroblast 1
and Fibroblast 2 cells, total raw UMIs and per-gene counts sum exactly to the
combined fibroblast values. Reconstructed observed-mixture scores reproduce
the original scores within **1.78 × 10⁻¹⁵**. Each subtype passes the original
20-cell gate. It then gives each subtype half the RNA contribution for every
gene, before applying `log1p` and averaging the unchanged panel genes.
Equal RNA fractions are neither equal cell fractions nor an intervention.

Among healthy donors, the structural-ECM slope is:

| Mixture and adjustment | Mean log1p(CPM) per decade |
| --- | ---: |
| Observed mixture, age only | +0.1724 |
| Fixed 50:50 RNA mixture, age only | +0.1676 |
| Observed mixture, sex/version adjusted | +0.1861 |
| Fixed 50:50 RNA mixture, sex/version adjusted | +0.1818 |

This two-subtype mixture sensitivity does not remove the positive
cell-resolved association. It therefore fails to explain the opposite
direction in the earlier small, mixed-cell
[bulk GSE83382 reference](../../aging-state-2026-10-11/GINGIVAL_AGE_REFERENCE_REPORT.md). It does
not exclude other composition, cohort, technical or within-subtype state
effects. The complete healthy-age adjustment results are in the
[age table](derived/healthy_age_adjustment_challenge.tsv), and donor-specific
RNA/cell fractions and reconstruction checks are in the
[mixture audit](derived/fibroblast_mixture_audit.tsv).

In the fully adjusted disease model, fixed mixing changes fibroblast
degradation from +1.039 to +1.009, inhibitors from +0.378 to +0.362 and
inflammation from +0.907 to +0.914. These directions survive this particular
composition challenge. Structural ECM remains small (−0.029 observed versus
−0.016 fixed). In the age-only model that near-zero contrast switches from
−0.004 to +0.010; this is another reason not to overread its sign. All 80
[mixture-model outcomes](derived/fibroblast_mixture_effects.tsv) remain visible.

## Consequence for youthful-function and restoration work

Keep age and inflammatory-disease challenges separate. In this cohort the
stronger degradation/inhibitor/inflammation contrasts are useful candidate
challenge readouts, while a signed structural-matrix or barrier score is
insufficient to declare damage or repair. Before transporting an age score
between tissues or studies, obtain donor-resolved, overlapping age/sex
coverage and test whether that direction transfers without relearning its
features on the evaluation cohort.

The next concrete evidence step is an independent, donor-resolved healthy
oral-tissue reference with overlapping age and sex strata, kept separate from
disease and processing comparisons. For a future cellular/tissue model, pair
the molecular axes with the program's independently required attachment,
barrier, matrix organization, mechanics, integration and durability
measurements. A favorable transcript change cannot substitute for those
endpoints. This analysis does not measure enamel formation, PDL insertion,
restored tooth position, organ function, genomic repair, lifespan or sustained
youthful human function.

Donor identities remain inferred from source sample codes and matched
demographics. There is only one observational cohort, annotations and
normalization remain inherited, panels share genes, and covariate adjustment
cannot remove unmeasured confounding. Fixed mixing deliberately removes
between-subtype RNA differences and may remove relevant biology as well.

## Reproduce and verify

From the repository root, with NumPy available:

```powershell
python studies/checklist-progress-2026-10-19/aging/challenge_donor_confounding.py
python -m unittest discover -s tests -p test_checklist_aging_confounding.py -v
```

The new 12 tests pass in the bundled NumPy runtime. They challenge duplicate
donor rows, rank failures, insufficient residual degrees of freedom, missing
age overlap, the decade unit, exact subtype count nesting, mixing before log
transformation, original-score reconstruction and receipt hashes. The
integrated full suite ran 573 tests with 86 skips and no failures;
the optional NumPy tests are run separately. Docker doctor could not run
because service `workbench` is stopped.

The [machine-readable summary](derived/analysis_summary.json) records the
script, plan, input and output hashes, software versions and retained limits.
UTF-8/LF text hashing tolerates checkout newline conversion. No source-fetch
provenance record is manufactured for this local-table reanalysis.
