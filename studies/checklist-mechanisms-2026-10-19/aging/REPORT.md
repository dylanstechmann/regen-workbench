# Between-compartment composition does not resolve this age-direction conflict

Computed 2026-10-19. This advances the persistent youthful-function goal by
testing a specific possible explanation for the opposing gingival age
directions. It extends the earlier two-fibroblast-subtype sensitivity to nine
mutually exclusive captured-cell compartments, without changing genes.

**Result:** the structural-ECM age slope remains positive in both the observed
partial RNA mixture (**+0.213 per decade**) and a common-composition partial
mixture (**+0.183**). These retain the positive same-donor fibroblast direction
and oppose the negative earlier bulk-gingiva results. This particular mixture
sensitivity changes numerical estimates but does not reproduce the bulk
direction. It cannot exclude other mixture, cohort or assay explanations.

## Coverage: partial captured-cell mixture, never whole tissue

The inputs are the already public raw fixed-gene pseudobulk counts, total raw
UMIs, cell counts, donor/sample crosswalk and annotation-coverage receipt from
the [earlier GSE164241 analysis](../../aging-state-2026-10-11/GINGIVAL_CELL_RESOLVED_CHALLENGE_REPORT.md).
Original experiment: [Williams et al., Cell 2021](https://doi.org/10.1016/j.cell.2021.05.013),
[GSE164241](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE164241), using
the pinned [curated periodontal atlas](https://cellxgene.cziscience.com/collections/71f4bccf-53d4-4c12-9e80-e73bfb89e398).
No new source download or H5AD read was needed.

The [coverage audit](derived/capture_coverage_audit.json) maps every source
cell-set label to at most one chosen compartment. Combined fibroblast,
epithelial and lymphoid parents are used; their child groups are never added
again. The nine disjoint compartments cover **85,752 of 86,138 captured cells
(99.5519%)**. Four excluded labels lack retained raw pseudobulk:

| Omitted source label | Captured cells |
| --- | ---: |
| Cells in the cell cycle, mixed lineages | 222 |
| Melanocytes | 119 |
| Schwann cells | 26 |
| Merkel cells | 19 |

Those **386 omitted cells' total UMIs and selected-gene contributions are
unknown**. A high captured-cell fraction therefore cannot establish high
captured-RNA coverage or negligible marker effects. Each inferred donor's
included cells are also checked against the original libraries; the counts
never exceed that donor's capture. Single-cell capture frequencies are affected
by dissociation, sampling and annotation and need not equal intact-tissue
cell or RNA fractions. These outputs must remain labelled **partial
captured-cell mixtures**, not reconstructed full gingiva or observed bulk RNA.

All 18 inferred donors have all nine compartments with positive UMIs. Five of
the 13 healthy donors have at least one minor compartment containing 9–19
cells. The primary analysis retains the same 13 healthy donors; a separately
specified strict sensitivity requires at least 20 cells in every compartment.
The latter leaves eight healthy donors aged **21, 21, 24, 28, 31, 32, 35 and
57**, with only one older donor. That changes the sampled population and makes
the age contrast particularly sensitive to the 57-year donor. Repeated
biopsies remain summed within the original inferred donor groups; none becomes
an extra person.

The exact healthy reference/fit set is `health:136, 143, 144, 147, 148, 169,
183, 184, 238, 241, 242, 283, 289`, ages 21–61 (ten women/three men). The five
`periodontitis:134, 153, 161, 164, 170` groups are scored for transparency but
enter neither reference-weight estimation nor healthy-age fitting. The source
has 21 original libraries nested in these 18 groups. The
[metadata table](derived/donor_compartment_metadata.tsv) preserves original
sample-code membership and exact per-donor counts.

## Frozen common RNA composition

The [plan](analysis_plan.json) was specified after reviewing earlier results
and metadata, before this mixture analysis. It was not independently
preregistered. A separate [metadata-only script](freeze_composition_reference.py)
does not open selected-gene counts. It calculates each healthy donor's
compartment RNA fractions, then takes their **unweighted mean across the 13
donors**. It uses neither disease donors nor age associations to optimize
weights. Pooling all donors' UMI counts would overweight larger libraries;
that is not this reference rule.

The [frozen common weights](frozen_RNA_weights.json) are:

| Captured compartment | Common RNA weight |
| --- | ---: |
| Fibroblasts | 26.2292% |
| Epithelium | 12.5730% |
| Endothelium | 38.3291% |
| Perivascular support | 5.1410% |
| Dendritic cells | 2.7521% |
| Lymphoid cells | 11.2460% |
| Neutrophils | 0.8170% |
| Macrophages/monocytes | 1.3656% |
| Mast cells | 1.5469% |

These are RNA weights, **not equal cell weights**, biological target fractions
or a tissue-engineering recipe. Within-compartment subpopulation composition
still varies; fixing nine parent weights does not fix every underlying cell
state. The strict 20-cell sensitivity uses these same weights.

For each gene, observed weights mix compartment CPM before `log1p`; this must
equal the direct sum of included counts divided by the sum of included UMIs.
The maximum reconstruction error is **1.82 × 10⁻¹² CPM**. Common weights are
then applied to each donor's unchanged compartment gene CPM, followed by
`log1p` and averaging the six existing fixed panels. Logs or panel scores are
never mixed directly. The comparison also reconstructs the relevant lineage
panel in the same donor set: fibroblasts for five panels and epithelium for the
barrier/identity panel. The unadjusted lineage slopes reproduce the earlier
source analysis within 10⁻¹⁰.

All **40 unique prespecified panel genes** are present at every donor ×
compartment key: 8 degradation, 3 inhibitor, 8 structural-ECM, 9 inflammation,
9 barrier/identity and 9 stromal-identity memberships, with shared genes
counted once in the raw matrix. No missing-gene imputation, alias substitution
or outcome-based feature selection is used. Coverage here differs from the
historical bulk cohorts; numerical cross-study magnitudes are not pooled.

## Age-direction results and retained sensitivities

The following slopes use all 13 healthy donors, with age as a linear predictor.
Units are mean `log1p(CPM)` per ten chronological years. This is relative
expression, not absolute RNA production, biological age or function.

| Fixed panel | Observed partial RNA mixture | Common-RNA partial mixture | Same-donor lineage reference |
| --- | ---: | ---: | ---: |
| Matrix degradation | +0.151 | +0.163 | −0.033 |
| Matrix inhibitors | +0.056 | +0.020 | −0.024 |
| Structural ECM | +0.213 | +0.183 | +0.172 |
| Inflammation | +0.013 | +0.028 | +0.088 |
| Epithelial barrier/identity | −0.122 | −0.054 | −0.050 |
| Fibroblast/stromal identity | +0.151 | +0.125 | +0.118 |

Composition and measurement context affect panels differently. Inhibitor and
degradation directions differ between lineage-only and aggregate partial
mixtures; that is a change of estimand, not independent replication or proof
of causality. The near-zero inflammatory estimates are fragile: the observed
unadjusted direction changes sign in 3/13 donor omissions, and the common-RNA
direction changes sign in 2/13. No inflammatory rejuvenation claim follows.

The structural-ECM comparison remains positive in every specified model:

| Healthy age model | Donors | Observed mixture | Common-RNA mixture | Lineage reference |
| --- | ---: | ---: | ---: | ---: |
| Age only | 13 | +0.213 | +0.183 | +0.172 |
| Age, sex, processing version | 13 | +0.187 | +0.192 | +0.186 |
| Women, age and processing version | 10 | +0.183 | +0.197 | +0.191 |
| Every compartment ≥20 cells, age only | 8 | +0.279 | +0.106 | +0.075 |
| Every compartment ≥20 cells, age/sex/version | 8 | +0.227 | +0.101 | +0.075 |

The common-composition value is slightly **higher**, rather than lower, in the
sex/version-adjusted models. A difference between these slopes must not be
labelled a causal fraction attributable to composition. The strict subset's
maximum design leverage reaches **0.943** in the fully adjusted fit; it is a
small, strongly uneven age sample.

Across the 13 unadjusted donor omissions, observed-mixture ECM slopes range
from +0.150 to +0.272; common-RNA slopes range from +0.136 to +0.220. Both stay
positive. The fully adjusted omission ranges also remain positive
(+0.116 to +0.282 observed; +0.135 to +0.269 common). These are influence
ranges, not confidence intervals. The frozen reference still contains each
omitted donor's composition: omissions remove that donor only from the age
fit. They therefore **are not donor-held-out validation**.

All **90 model rows** and **468 individual donor omissions** are retained in
the [model table](derived/healthy_age_effects.tsv) and
[omission table](derived/healthy_age_donor_omissions.tsv). No fitting failures
occurred in these specified models; the script retains rank/sample-size
failures if they arise. Panels and score types share donors and genes and are
not independent studies.

## Consequence for the bulk-versus-lineage conflict

The earlier [GSE173078 bulk challenge](../../checklist-followup-2026-10-19/aging/REPORT.md)
had a female/batch-adjusted structural-ECM slope of −0.246. The earlier
[GSE83382 bulk group contrast](../../aging-state-2026-10-11/GINGIVAL_AGE_REFERENCE_REPORT.md)
also declined with older group age. The current observed partial mixture and
its common-RNA counterpart retain a positive direction. Thus this particular
captured between-compartment mixture does not reproduce the negative bulk
pattern. The [full direction table](derived/direction_challenge.tsv) preserves
all six panel comparisons without pooling numerical scales or people.

This is a failed explanation under the stated retained data and weights,
not proof that composition is irrelevant. Omitted-label RNA, subpopulation
mixtures, capture/site effects, sex/age distributions, clinical status and
UMI-versus-bulk processing remain unresolved. No computational reweighting can
establish that the different cohorts represent the same intact-tissue state.

The next discriminating evidence is a matched-donor bulk and cell-resolved
gingival dataset with spatial/site and health qualification, full donor-linked
RNA/cell coverage, and external functional outcomes. It would distinguish
assay/mixture differences from actual donor/tissue differences more directly
than selecting a preferred age signature. For the restoration program, keep
matrix organization, barrier, attachment mechanics and post-support durability
as separate required measurements. This analysis supplies no intervention,
clinical age change, restored tooth attachment or whole-body rejuvenation.

## Reproduction and checks

```powershell
python studies/checklist-mechanisms-2026-10-19/aging/freeze_composition_reference.py
python studies/checklist-mechanisms-2026-10-19/aging/analyze_compartment_mixture.py
python -m unittest discover -s tests -p test_checklist_mechanisms_aging_mixture.py -v
```

The analysis/tests use NumPy; freezing uses only the standard library. Twelve
new checks pass: parent/child overlap rejection, explicit omitted-RNA status,
equal-donor versus pooled-count weights, disease exclusion from the reference,
mixing before logs, raw-count reconstruction, donor units, rank failure,
identical donor sets, omission units and receipt hashes. No new method package
was added. Docker workbench remains stopped, and no successful doctor run is
claimed.

The [summary](derived/analysis_summary.json) pins the input/plan/reference and
output hashes and software. Public outputs include the
[donor-compartment metadata](derived/donor_compartment_metadata.tsv),
[per-gene partial mixtures](derived/partial_mixture_gene_values.tsv) and
[donor-panel scores](derived/partial_mixture_donor_scores.tsv). Text hashes use
canonical UTF-8/LF. No new fetch/provenance record is manufactured for this
local-table calculation; original source rights and attribution remain with
the original study and curated data.
