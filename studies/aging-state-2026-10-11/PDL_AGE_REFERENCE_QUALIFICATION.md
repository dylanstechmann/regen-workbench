# Periodontal-ligament age reference qualification

## Decision

The literature contains a direct human PDL age-associated molecular signal
and several donor-derived functional studies of PDL stem cells. The public
datasets found in this review still do not qualify as a donor-resolved adult
PDL tissue-aging reference. Keep PDL, gingiva, pulp, and developmental
tooth-maturity signals as separate evidence streams. Do not transfer the
gingival score to the ligament or train a PDL age clock from a maturity
contrast.

The only age-spanning report located on native human PDL tissue molecular
abundance is Takatsu et al. (1999): healthy PDL from people aged 9–76 years
showed decreasing COL1A1 mRNA and increasing methylation at two promoter
positions. The paper used Northern/dot blot and methylation-sensitive Southern
blot methods. Its abstract does not give the sample count, age-by-sample
values, covariates, or an accession for individual data. It supports COL1A1
and promoter methylation as hypotheses for a modern PDL study, not a multigene
age reference or a quantified restoration target. The focused source check
found the PubMed record and ScienceDirect abstract, but no accessible full
methods or sample-level data. This leaves donor count, tooth/root maturity,
periodontal-health ascertainment, and age-specific effect sizes unresolved; do
not infer them from the reported age span.

## Functional donor evidence: distinct from a tissue age reference

Multiple primary studies report age-associated changes in cultured human
PDLSCs, including proliferation, migration, differentiation, cell-sheet matrix
content and senescence-associated readouts. Their donor counts are not their
tooth counts, wells or technical repeats. Most use clinically selected
third-molar sources and expanded cells, which do not represent every mature,
load-bearing PDL. These studies strengthen the case for measuring donor age and
cell-source quality in regeneration work, but they cannot be pooled into a
multigene PDL age score.

The highest-value niche hypothesis is [Zheng et al. (2009)](https://doi.org/10.1089/ten.tea.2008.0562): young PDL-cell
conditioned medium improved several assays of aged-donor PDLSCs, and the
authors reported cementum/PDL-like tissue in their in-vivo differentiation
model after exposure. This is a mechanistic benchmark, not proof of durable
repair in an alveolar socket. The conditioned medium is an undefined mixture,
and the abstract does not report donor counts or age bands. The counterweight
is [Zhang et al. (2012)](https://doi.org/10.1016/j.biomaterials.2012.06.032): among 90 third molars from 54 donors aged 16–75,
proliferative, migratory and differentiation capacity declined across age
groups, and no identified cementum or PDL-like tissue was reported in the two
age groups included in the in-vivo transplantation comparison. Thus an
improved cell assay cannot stand in for regenerated attachment.

[Wu et al. (2015)](https://doi.org/10.1016/j.actbio.2015.04.024) found age-associated declines in fibronectin, integrin-beta1,
COL-I and osteogenic properties in PDLSC sheets; the 62 teeth came from 42
donors, and one randomly selected tooth per donor was used where multiple
teeth were available. [Ng et al. (2020)](https://doi.org/10.1007/s00441-020-03176-y) compared 18 independent donors in three
age bands and reported lower proliferation, migration and mesodermal
differentiation with age, plus shorter telomere length and lower SSEA4 in the
over-40 group; IL6 and CXCL8 were higher in adult groups. [Li et al. (2020)](https://doi.org/10.1186/s13287-020-01846-w)
compared donors aged 19–20 with donors aged 35–50, but each experiment used
three independent donors per group, despite a larger donor source pool. Their
supplement contains a group-level differential-expression workbook, not the
donor-by-gene matrix needed for reanalysis. The reported microarray screen
used `p < 0.05` or fold change `> 2`; no multiple-testing correction is
described in the methods. Three selected qRT-PCR directions (RC3H1, TNFSF4,
and TNFSF14) disagreed with the microarray result. Treat its candidate genes as
hypotheses for independent validation, not a prespecified rejuvenation panel.
Machine-readable detail and study limits are in
[`pdl_age_functional_evidence.tsv`](pdl_age_functional_evidence.tsv).

Two mechanistic studies sharpen the assay cautions but do not qualify as
natural-aging references. [A 2025 study](https://doi.org/10.1016/j.jare.2024.12.037)
found that TGF-beta1 induced ROS accumulation and
senescence-associated changes in cultured human PDLSCs obtained from healthy
15–25-year-old orthodontic patients; NAC or decitabine mitigated that induced
phenotype in vitro. [A 2023 BDNF study](https://doi.org/10.1016/j.cellsig.2023.110724)
reported reduced senescence readouts and increased osteogenic
markers in a mouse orthodontic-force study that also promoted tooth movement.
Neither result establishes restoration to a registered original tooth
position. These are reasons to pair cell-state panels with attachment and
position outcomes, not to recommend systemic pathway manipulation.

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

The GSE screen should therefore be read alongside the functional-study table
above: a useful cell-source or niche-rescue comparison may exist even when no
public age-series transcriptome passes the donor-level qualification gate.

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

For cell-based restoration, the next discriminating test is a donor-crossed
**cell-source age × niche age** comparison, with periodontal health and root
maturity recorded before culture. Zheng's young-conditioned-medium result is
the historical positive benchmark; young and aged niche preparations must be
tracked as independent donors, and the medium or matrix should be deconstructed
only after a reproducible effect. Measure cell identity, survival, senescence
alternatives and lineage balance before and after washout, then carry the
strongest condition into the two-interface assay. The primary readouts remain
root- and bone-facing fiber insertion, ligament-space preservation and
recoverable mechanics. Report a transient cell-state change separately from
durable attachment function. The donor-level contrasts, crossed-effects model,
confounding limits, and advancement rules are specified in the
[`age-by-niche analysis contract`](../organoid/periodontal-ligament-interface/age_by_niche_analysis_plan.md).

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
