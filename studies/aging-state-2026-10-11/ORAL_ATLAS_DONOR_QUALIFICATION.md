# Oral atlas donor and library qualification: GSE164241

## Decision

GSE164241 is suitable as a cell-resolved **disease-state challenge** for oral
repair hypotheses, with major limits on donor-level inference. The GEO records
alone hide donor age and sex. The original study's Table S1 supplies sample IDs
and demographics for 29 single-cell libraries and matches 28 GEO titles exactly
plus one title by a unique shared sample-code root (`GM184a` to `GM184`). A
thirtieth GEO record, `ID080UST`, was added in 2023 and does not appear in the
original Table S1.

The first 29 records comprise 13 healthy gingival biopsies, 8 healthy buccal
biopsies, and 8 periodontitis gingival biopsies. The paper reports 20 healthy
volunteers for 21 tissue samples; Table S1 and GEO titles identify the paired
healthy `GM169` gingival and `BM169` buccal samples. The eight disease biopsies
fall into five apparent donor-code groups when samples sharing a numeric code
and matching age, sex, and race are grouped: `PD134`, `PD153`, `PD161`, `PD164`,
and `PD170`. `PD161b` repeats the `PD161` code; `PD164b` and `PD164c` repeat
`PD164`. GEO does not have a formal donor-ID field, so these are explicit
sample-code-based donor groupings, not a separately supplied donor key.

Sources: [Williams et al., *Cell* (2021)](https://doi.org/10.1016/j.cell.2021.05.013),
[GSE164241](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE164241),
[the Table S1 source file](https://ars.els-cdn.com/content/image/1-s2.0-S0092867421006309-mmc1.xlsx),
and [the later `ID080UST` GEO record](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM7780241).

## Sample structure and covariates

| Sample set | GEO libraries | Apparent donor codes | Ages from Table S1 | Qualification |
|---|---:|---:|---|---|
| Healthy gingiva | 13 | 13 | 21–61 years | Tissue-matched healthy comparison; sex and age vary. |
| Healthy buccal mucosa | 8 | 8, one paired with healthy gingiva | 22–33 years | Keep separate from gingiva because anatomic site differs. |
| Periodontitis gingiva | 8 | 5 | 34–45 years | Aggregate repeated sample codes within donor before inference. |
| 2023 periodontitis-LAD1 extension | 1 | Not linked | Not supplied in the original Table S1 | Hold outside the original comparison; it uses a separate platform and submission. |

The age distributions are not balanced: the five apparent disease donors are
34–45, while healthy gingival donors span 21–61. Sex and race also vary. A raw
disease-versus-health mean would mix disease, age, donor, site, and batch
effects. It should not be described as an aging effect.

GEO states that Cell Ranger v2.0.0 generated five libraries and v3.0.1 generated
the other 25, including the 2023 extension. Four of the five v2.0.0 libraries
are healthy gingiva and one is periodontitis gingiva. This imbalance needs a
pipeline-version sensitivity check in any count-level comparison. The small
five-donor disease set will not support a rich covariate model.

## Analysis gate

No cell counts or expression tests were run in this qualification step. Before
testing the GSE83382 aging panels against disease:

1. Restrict to gingiva, retain the 13 healthy gingival sample records, and keep
   the buccal samples as a separate tissue reference.
2. Sum or otherwise model repeated `PD161` and `PD164` biopsies within their
   donor-code groups so cells and libraries do not inflate the disease sample
   size. Run a sensitivity result with the 2023 `ID080UST` extension excluded.
3. Use the original count matrices and cell identities, if the published
   annotations can be reproduced. Compare fixed inflammation and matrix panels
   within fibroblast and epithelial compartments, alongside cell proportions.
4. Show the pipeline-version effect and age overlap explicitly. If those checks
   do not support a stable within-cell result, report the dataset as an
   inflammation confounder rather than using it to adjust a gum-age score.

The [machine-readable crosswalk](oral_atlas_GSE164241_sample_crosswalk.tsv)
records every GSM, the Table S1 match method, sample-code group, age, sex, race,
condition, instrument platform, Cell Ranger version, and submission date. The
[intake receipt](oral_atlas_GSE164241_intake_receipt.json) includes SHA-256
hashes for GEO metadata and Table S1.

## Reproduction

```powershell
python studies/aging-state-2026-10-11/qualify_oral_atlas_GSE164241.py
```

The source workbooks and family SOFT file are kept in ignored local literature
storage. The qualification script parses the simple Table S1 worksheet with
the Python standard library, verifies its table shape and donor/sample joins,
and writes only the compact crosswalk and receipt to the repository.
