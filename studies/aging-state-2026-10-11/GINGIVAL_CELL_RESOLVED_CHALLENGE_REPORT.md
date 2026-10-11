# Cell-resolved gingival age and disease challenge: GSE164241

## Decision

The curated GSE164241 gingival data support a bounded, donor-aware challenge of
the fixed oral-tissue panels. The result argues against treating “younger
gingiva” as one transcript score. Within healthy annotated fibroblasts, the
structural-ECM panel trends upward across the available adult ages. In
periodontitis, inflammatory and matrix-turnover panels rise across several
compartments, while the structural-ECM panel is approximately unchanged. Those
are distinct cross-sectional patterns, and neither measures restored
attachment or youthful function.

This analysis uses the original human oral single-cell study by Williams et
al. and the curated CELLxGENE version of the periodontal meta-atlas. It includes
only GSE164241 gingiva and excludes healthy buccal samples and the later
`ID080UST` GEO addition. Sources: [Williams et al. (2021)](https://doi.org/10.1016/j.cell.2021.05.013),
[GSE164241](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE164241),
[CELLxGENE collection](https://cellxgene.cziscience.com/collections/71f4bccf-53d4-4c12-9e80-e73bfb89e398).

## Input and unit of analysis

The curated H5AD contains 86,138 GSE164241 gingival cells from 21 original
libraries: 13 healthy and 8 periodontitis. GEO titles were joined to the
original paper's Table S1; exact titles were preferred, with a unique shared
sample-code root used only where needed. Because GEO provides no formal donor
key, repeated `PD161` and `PD164` sample codes were combined into five
**inferred** periodontitis donor groups. The comparison therefore has 13
healthy and 5 periodontitis donor groups, not 13 and 8 independent people. See
the [sample qualification](ORAL_ATLAS_DONOR_QUALIFICATION.md) and generated
[sample crosswalk](derived/gingival-cell-atlas-GSE164241/oral_atlas_sample_crosswalk.tsv).

The H5AD's `.raw/X` integer-valued matrix was used; the curated `.X` log-normalized
matrix was not. Raw counts were summed across each inferred donor and its
repeated gingival biopsies within each published cell-set grouping. For each
donor-cell-group, gene counts were converted to counts per million using total
raw UMIs, transformed as `log1p(CPM)`, and averaged across the already frozen
genes in each panel. Age slopes use healthy donors only. Disease contrasts use
an age-adjusted linear model and bootstrap resampling within condition. The
intervals are exploratory donor-bootstrap ranges, not confirmatory confidence
intervals or p-values. Scores remain on this analysis's transformed expression
scale; they are not fold changes, clinical effect sizes, or years of age.

Cell groups include both combined populations and selected subpopulation
sensitivities. All observed annotated cell sets were either mapped to a group
or assigned an explicit exclusion reason. The report's repeated combined and
subgroup results are not independent replications.

## Results

Among the 13 healthy inferred donors, fibroblast structural-ECM score rose by
about **0.17 mean-log1p(CPM) units per decade** in the combined fibroblast group
(donor-bootstrap range 0.045 to 0.302; leave-one-donor-out range 0.125 to
0.207). The two annotated fibroblast subgroups showed similar directions. In
contrast, the combined fibroblast matrix-degradation slope was −0.033 per
decade (range −0.229 to 0.157), and the matrix-inhibitor slope was −0.024
(−0.169 to 0.094). These small, cross-sectional age trends are exploratory;
they do not establish a mechanism or a target for rejuvenation.

The age-associated structural-ECM direction differs from the small bulk
GSE83382 young-versus-old comparison, where the same frozen panel was lower in
the older group. Those studies have different age ranges, cell resolution,
sample structures and expression scales, so their numerical scores cannot be
combined. The discordance is a reason to resolve cell mixture, cohort and
measurement effects before treating either result as a gingival aging axis.
See the [GSE83382 qualification and results](GINGIVAL_AGE_REFERENCE_REPORT.md).

For the age-adjusted periodontitis challenge:

| Cell group and panel | Donors, healthy / disease | Difference | Exploratory bootstrap range |
|---|---:|---:|---:|
| Fibroblasts, matrix degradation | 13 / 5 | +1.06 | +0.71 to +1.39 |
| Fibroblasts, matrix inhibitors | 13 / 5 | +0.39 | +0.17 to +0.64 |
| Fibroblasts, structural ECM | 13 / 5 | −0.004 | −0.15 to +0.17 |
| Fibroblasts, inflammation | 13 / 5 | +0.95 | +0.61 to +1.30 |
| Epithelium, inflammation | 13 / 5 | +1.10 | +0.43 to +1.78 |
| Endothelium, inflammation | 13 / 5 | +0.81 | +0.43 to +1.22 |
| Dendritic cells, inflammation | 12 / 5 | +1.01 | +0.56 to +1.58 |
| Perivascular support, inflammation | 13 / 5 | +1.00 | +0.60 to +1.44 |

The v3.0.1-only sensitivity retained the same broad directions in these
well-covered groups (for example, combined-fibroblast matrix degradation
+1.04, inhibitors +0.32, structural ECM −0.009, and inflammation +0.70).
That subset contains only 9 healthy and 4 disease donors. The five v2.0.0
libraries are too imbalanced by condition for a comparably supported
version-specific contrast. Pipeline version therefore remains a limitation,
even though the primary directions were not explained by the v3.0.1-only
subset.

The key biological separation is that periodontitis raises both the
matrix-degradation and matrix-inhibitor panels, rather than showing a simple
“more MMP equals less ECM” transcript pattern. This is consistent with active
matrix turnover and a compensating inhibitor response as candidate
interpretations; the expression data cannot establish enzyme activity,
deposition, fiber insertion, barrier integrity or mechanical recovery.

## Limits and consequence for the restoration program

The donor groups are inferred from sample-code roots and matching Table S1
demographics, not supplied donor IDs. The disease group has five inferred
donors, its age range is narrower than the healthy group, and sex, age and
processing version are not balanced by design. Some cell-group estimates have
fewer donors after a 20-cell-per-donor screening gate. Many panels and cell
groups were examined without multiplicity correction; the intervals should be
read as exploratory sensitivity summaries. The CELLxGENE annotations were
used as published, and minor or mixed groups were either kept separate or
excluded as recorded in the machine-readable summary.

This dataset is useful as an inflammatory challenge reference, not as a
cell-resolved healthy aging series. For dental restoration work, it supports
keeping an inflammatory disease challenge separate from an age challenge and
measuring matrix turnover together with inhibitor response, epithelial seal,
vascular/immune state, cementum-facing and bone-facing fiber insertion, and
attachment mechanics. It does not support interpreting transcript panel
normalization as gum regeneration or as recovery of a tooth's position.

## Reproduction and outputs

The download script pins the CELLxGENE dataset version, expected byte count and
SHA-256 receipt. It stores the H5AD in the repository's ignored local literature
cache. The analysis script verifies that receipt, joins the donor crosswalk,
checks count integrality, audits cell-set coverage and writes the tracked
tables under `derived/gingival-cell-atlas-GSE164241/`.

From the repository root, with Python packages `h5py`, `scipy` and `numpy`
available:

```powershell
python studies/aging-state-2026-10-11/fetch_periodontal_meta_atlas.py
python studies/aging-state-2026-10-11/analyze_gingival_cell_atlas.py
```

Key files are the analysis summary JSON, cell-set donor counts, fixed-panel
coverage, donor pseudobulk gene counts and donor scores, healthy-age slopes,
periodontitis challenge, and age-versus-disease direction table. The source
receipt and full input H5AD remain in ignored local cache storage; the tracked
summary records the H5AD hash and collection/version IDs.
