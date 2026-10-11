# Periodontal-ligament age reference qualification

## Decision

The literature contains a direct human PDL age association, but the public
datasets found in this review do not qualify as a donor-resolved adult PDL
aging reference. Keep PDL, gingiva, pulp, and developmental tooth-maturity
signals as separate evidence streams. Do not transfer the gingival score to the
ligament or train a PDL age clock from a maturity contrast.

The most direct human report is Takatsu et al. (1999): healthy PDL from people
aged 9–76 years showed decreasing COL1A1 mRNA and increasing methylation at
two promoter positions. The paper used Northern/dot blot and
methylation-sensitive Southern blot methods. Its abstract does not give the
sample count, age-by-sample values, covariates, or an accession for individual
data. It supports COL1A1 and promoter methylation as hypotheses for a modern
PDL study, not a multigene age reference or a quantified restoration target.

## Candidate dataset disposition

| Candidate | Source design | Decision for aging work |
|---|---|---|
| [Takatsu et al. 1999](https://doi.org/10.1016/S0047-6374(99)00041-X) | Healthy human PDL, ages 9–76; one collagen gene transcript plus selected promoter methylation sites; abstract-only sample count and no public sample-level matrix located. | Direct age-associated signal, but insufficiently reported and too narrow for a clock. Retrieve full methods/data or replicate with donor-level measurements. |
| [GSE50639](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE50639) | Human permanent-tooth PDL versus pulp; source paper reports donors aged 11–14 and three deposited tissue-group arrays. | Tissue identity contrast from young donors, not age variation; do not use to infer adult PDL aging. |
| [GSE50640](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE50640) | Deciduous versus permanent PDL from children/adolescents; primary and permanent tooth classes, root resorption and development differ, and expression samples are pooled. | Developmental/dentition comparator only. Tooth class and root maturity cannot stand in for chronological aging. |
| [GSE227731](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE227731) | Single-cell DPSC/PDLSC atlas from three healthy donors aged 21–27; GEO has one sample record per tissue, without a donor-to-cell matrix for age comparisons. | Useful young-adult PDL cell-identity reference; age range is too narrow and not donor-resolved for an age trend. |
| [GSE306722](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE306722) | Two human PDL single-cell libraries labelled immature/mature; root developmental stage is part of the grouping, age values and independent donor mapping are not supplied. | Already qualified for maturity and osteogenic-capacity work. Exclude from chronological-age training or inference. |
| [GSE27993](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE27993) | Five GEO records labelled healthy PDL and five periodontitis PDL records; age is not stated in the series-level design. | Disease-state comparison, not an age reference. Any later use must first recover donor age and periodontal-health covariates. |
| [GSE180588](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE180588) | Rhesus-macaque gingiva sampled across four age groups and multiple ligature-disease time points. | Possible cross-species gingival age-by-inflammation challenge, not PDL or human-age ground truth. Keep tissue and disease contrasts separate. |

The machine-readable screen is in
[`pdl_age_reference_candidates.tsv`](pdl_age_reference_candidates.tsv).
Candidate inclusion means that a source is relevant to the qualification
question; it does not mean it passed as an age reference.

## What a qualifying PDL age reference needs

The next useful reference is a healthy-human PDL cohort with individual ages,
sex, donor IDs, tooth class, root maturity, extraction indication, periodontal
health, sampling region, and assay batch linked to each biological sample. The
analysis must retain donor as the unit, distinguish repeated teeth from
independent people, and account for cell composition. Adult aging should not
be estimated by comparing deciduous to permanent teeth or immature to mature
roots.

Freeze a small tissue-specific panel before examining any new cohort: collagen
synthesis/assembly and turnover, PDL fibroblast identity, vascular and immune
context, cell-cycle/senescence alternatives, and the COL1A1-promoter signal
from the 1999 report if assay details can be recovered. Report expression and
methylation separately. A candidate panel must be checked against periodontitis
and cell-mixture shifts before it is called intrinsic age.

The functional link remains a separate endpoint: fiber insertion into both
cementum and alveolar bone, ligament-space architecture, physiologic
force–displacement and energy dissipation, and stable tooth position after
temporary support is removed. Transcript age or collagen abundance alone does
not establish periodontal-ligament restoration.

## Reproduction and limits

This is a source-qualification review, not a reanalysis of expression matrices.
GEO records and the cited primary papers should be rechecked before a new
quantitative analysis. No adult PDL age clock, rejuvenating intervention, or
human recovery effect is established by these sources.
