# Somatic Mutation Repair Pilot

This is the first target-centered campaign created in the research desk. It
starts with age-expanded clones in normal esophageal epithelium and asks what
would need to be true before sequence correction is a plausible repair target.
The campaign deliberately keeps DNA sequence, epigenetic state, clone fitness,
cell phenotype and tissue function as separate observations.

## Live Research Runs

All three runs completed on 2026-10-01 through the local research desk. PubMed,
Europe PMC and OpenAlex / Semantic Scholar ran with the configured accounts;
all selected providers succeeded. The provider totals below include duplicate
records and are not counts of independent papers.

| Run | Search | Provider records | Result |
| --- | --- | --- | --- |
| `9c1308ecef5b4efda366c1ad2ea4124d` | Age-associated somatic mutations, human tissues, clonal expansion and function | PubMed 1, Europe PMC 5, OpenAlex 5 | 11 records; broad query mixed relevant papers with unrelated OpenAlex hits |
| `4d6548fdd6d2407c93dbe091a37e45e2` | Base editing, somatic mutation correction, aging and functional rescue | PubMed 0, Europe PMC 5, Semantic Scholar 5 | 10 records; included one directly relevant monogenic progeria correction study |
| `4685bbf87e1243999b5d057a115734d1` | NOTCH1 / TP53 somatic clones in normal aged esophagus | PubMed 1, Europe PMC 5, Semantic Scholar 5 | 11 records; surfaced a genotype-to-phenotype study in aged normal human esophagus |

The immutable provider snapshots, full abstracts where available, manifests,
parameters and run receipts are retained locally under
`data/research-desk/runs/<run-id>/`. The campaign record is
`794c6e76ced24309b6d0889a2c5e819f` under the `reprogramming` blueprint. These
runtime data directories are git-ignored; this summary preserves the main
findings but is not a replacement for the raw snapshots.

## Reproducing the Supplementary-Table Summaries

The local script `studies/mutation_repair_pilot/reproduce.py` rebuilds compact
aggregate CSV/JSON tables from six public workbooks under the ignored
`data/research-desk/source_snapshots/` directory. It checks each workbook's
byte count and SHA-256 against `source_manifest.json` before analysis, then
writes `derived/manifest.json` with input and output hashes. Run from the
workbench repository root with Python 3.11 plus NumPy and openpyxl:

```bash
docker compose exec workbench python /lab/workbench/studies/mutation_repair_pilot/reproduce.py
```

The outputs reconstruct selected descriptive counts, liver-table BH
adjustment, skin-model R-squared/relative-importance summaries, and NanoSeq
mutation-row distributions. They do not reproduce every analysis in the
papers and do not test mutation correction or rejuvenation.

## What the Searches Found

1. **Normal aging is a mosaic, not a single mutation target.** A single-cell
   genotype-to-phenotype study profiled aged, histologically normal esophagus
   from six donors. It associated NOTCH1-mutant clones with stunted epithelial
   differentiation and TP53-mutant clones with differentiation bias and
   increased cycling. This maps candidate effects; it did not correct either
   mutation or show that editing would improve tissue function. The small,
   tissue-specific sample and targeted transcript panel limit generalization.
   [Primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12874418/)

2. **There is a strong monogenic proof-of-principle, but it is a different
   problem.** A 2026 study corrected the causal `LMNA` variant in Hutchinson-
   Gilford progeria models and reported partial bone-structure and mechanical
   rescue in treated mice. Correction depended on treatment timing. This is a
   high-effect, known disease mutation in a defined model, not the diverse,
   low-frequency and competing mutations of ordinary aging.
   [Primary paper](https://pubmed.ncbi.nlm.nih.gov/42689491/)

3. **Some age-associated clones may influence repair, but clone removal is not
   automatically restorative.** A 2026 preprint combined human lung cohorts,
   mouse models and human lung analyses to link mutation identity and clone
   size in clonal hematopoiesis with fibrotic repair phenotypes. It motivates
   testing systemic and tissue interactions; it does not test mutation
   correction as an anti-aging treatment. Its preprint status should remain
   visible.
   [Preprint and full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC13041955/)

4. **Mitochondrial heteroplasmy is a separate research axis.** The broad search
   also found a review describing tissue-specific mitochondrial mutation
   mosaicism and the unresolved balance between drift and cellular selection.
   It is a synthesis, not an intervention result; nuclear DNA editing results
   should not be assumed to apply to mitochondrial genomes.
   [Review record](https://pubmed.ncbi.nlm.nih.gov/42728666/)

## Structured Mutation Evidence Matrix

This pass went beyond search-result abstracts. On 2026-10-01 I queried the
Europe PMC full-text API for the open SMART-PTA preprint, retrieved the
publisher's public scG2P supplement workbook from Figshare, and checked both
studies' EGA records. The workbook is retained locally under the ignored
`data/research-desk/source_snapshots/` directory; its SHA-256 and accessions are
recorded in `data/ACCESSIONS.tsv`. The individual-level sequencing files remain
controlled-access and were not downloaded.

| Evidence | Reported observation | Intervention and endpoint | Boundary |
| --- | --- | --- | --- |
| **NOTCH1 mutation and LOH, normal human esophagus** | The six-donor scG2P study reports NOTCH1-mutant clones as common and associated with stunted differentiation; TP53-mutant clones show differentiation bias and increased cycling. In its additional ESO-6 sample, NOTCH1 LOH was called in 1,697 of 4,976 cells genotyped at the locus (34%); 811/1,697 LOH cells (48%) and 732/3,279 cells without LOH (22%) carried a driver SNV. LOH alone, a NOTCH1 SNV alone, and combined/double NOTCH1 hits were analyzed as distinct states. | No sequence correction was performed. The measured outcomes were genotype, clone structure, cycling and differentiation scores, not restored barrier or organ function. | Observational, tissue-specific, and vulnerable to targeted-panel dropout. The authors note incomplete NOTCH1 amplicon capture and that LOH without a detected SNV does not always establish NOTCH1 biallelic loss. Raw data: EGA study `EGAS50000001429`, request-controlled. Primary paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC12874418/ |
| **Table-level scG2P supplement extraction** | The public S1-S14 workbook includes per-cell variant calls, clone-fraction fields, clone IDs, cell types, and cycling/differentiation scores. Its ESO-6 genotype/RNA tables contain 2,492 matched rows: 1,725 WT, 475 single-NOTCH1, 146 TP53, 57 FAT1, 50 PPM1D, and 39 double-NOTCH1 rows. | This enables a reproducible lead-triage layer; it does not add an intervention experiment. I retained the workbook's reported `clone_fraction` without reinterpreting its denominator as whole-tissue mutant burden. | The per-cell ESO-6 tables do not encode the LOH state alongside every phenotype row, so the article's LOH-specific aggregate results cannot be reconstructed from those two sheets alone. Publisher supplement, CC BY: https://aacr.figshare.com/articles/dataset/Supplementary_Tables_S1-S14_from_Genotype-to-Phenotype_Mapping_of_Somatic_Clonal_Mosaicism_via_Single-Cell_Co-Capture_of_DNA_Mutations_and_mRNA_Transcripts/31911152 |
| **TP53/FAT1 and clonal evolution, normal human esophagus** | A separate SMART-PTA preprint profiled four donors aged 76-79 and 2,783 single cells. TP53 and FAT1 mutant cells were enriched in earlier basal states; some biallelic TP53-loss clones showed higher cell-cycle expression. CNLOH spanning the NOTCH1 locus was frequent, but NOTCH1 itself had low mean coverage (2.2x) in this assay. | No mutation correction or functional tissue rescue was tested. Clone phylogenies and RNA-state scores were the endpoints. | This remains a preprint. Its supplemental scG2P comparison reanalyzed an earlier scG2P dataset, so that comparison is not an independent cohort replication. The paper reports four donors, while the later EGA deposit and public iTOL project expose five sample/tree labels including `eso05`; keep that later material outside the paper's stated N=4 until reconciled. Paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC12632828/; EGA record: https://www.ega-archive.org/datasets/EGAD50000002573; public trees: https://itol.embl.de/shared/2CNE84KS0anV4 |
| **LMNA correction in a human tissue-engineered vascular model** | In HGPS iPSC-derived cells, ABE restored about 97.5% wild-type allele at the target in two cell lines. Differentiated edited endothelial and smooth-muscle cells lacked detectable progerin; edited cells improved shear response, and edited-cell TEBVs restored vasodilation and smooth-muscle density. Mixtures required at least 50% edited smooth-muscle cells for significant improvement in proliferation and myosin-heavy-chain levels. | This is the closest inspected bridge from editing to tissue-level function: human engineered vessels were tested for flow response, vasoactivity, cell density and contractile markers. | It is an engineered model of a single, known pathogenic LMNA mutation, not an implanted vessel or a test of heterogeneous ordinary aging. Paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC11871533/ |
| **LMNA correction in HGPS animal models** | Earlier ABE work corrected the known HGPS variant in mice and reported vascular rescue and longer survival. In the 2026 bone study, correction measured at six months was about 14%, 22%, 10% and under 1% after treatment at P3, P14, one month and four months, respectively; P14 treatment partially rescued bone structural and physical parameters. | These are intervention results with disease-specific tissue and functional readouts, unlike the esophageal clone-association studies. | Strong positive-control class for monogenic correction; not evidence that diverse age-acquired variants can be corrected safely or that normal human aging is reversed. Papers: https://pubmed.ncbi.nlm.nih.gov/33408413/ and https://pubmed.ncbi.nlm.nih.gov/42689491/ |

## Cross-Tissue Mutation Landscape

I extended the pilot beyond esophagus using targeted `regen europepmc` searches,
primary papers, controlled-archive metadata and public supplementary data. The
search receipts are under `data/provenance/`; downloaded workbooks and their
hashes are recorded in `data/ACCESSIONS.tsv`.

| Tissue and assay | Findings from the study | What this means for repair triage |
| --- | --- | --- |
| **Oral epithelium, targeted NanoSeq** | A 2025 study profiled buccal swabs from 1,042 people aged 21-91 (median 68) with a 239-gene panel, plus matched blood from 371. Oral mutations accumulated at about 18 SNVs/cell/year within the targeted panel; a separate 16-sample assay supported a genome-wide extrapolation of about 23 SNVs/cell/year. The study reported 46 genes under positive selection and estimated about 10% of cells carried NOTCH1 driver mutations and 3% TP53 mutations in donors aged 65-85. In its site-level selection supplement, recurrent oral NOTCH1 replacements included C440R, F357S and I471T (all q<0.01). | These are normal-epithelium fitness signals, not evidence that the clones damage oral function. NOTCH1 was present in roughly 10% of older normal oral cells versus 16% of head-and-neck squamous cancers; TP53 was about 3% versus 69%, respectively. The authors interpret TP53 and most other drivers as more tumor-enriched than NOTCH1. A selected clone is not automatically a good editing target. Paper: https://www.nature.com/articles/s41586-025-09584-w |
| **Blood, targeted NanoSeq** | In the matched 371 blood samples, the same study identified 14 genes under positive selection and 4,406 nonsynonymous mutations in those genes. Most calls were very low fraction: 95% were supported by one duplex molecule and 90% had unbiased VAF below 0.1%. A q<0.01 slice of the published site-level table includes DNMT3A Y735C, TET2 I1873T and SRSF2 P95H. | Hematopoietic stem/progenitor clone fitness is a different biological system from epithelial clone fitness. The low-VAF results also show why standard bulk-sequencing prevalence estimates miss most small clones. Raw sequencing is controlled-access; anonymized mutation data are public in Supplementary Table 9. |
| **Sun-exposed skin, targeted cancer-gene sequencing** | A cross-sectional study analyzed 123 cancer-free donors aged 11-92 using a 46-gene skin-cancer panel. It detected 5,214 variants (mean 42.39 per sample, within the 0.32-Mb target); burden increased with age, with skin phototype also an important modifier. About 80% of samples carried at least one protein-altering variant in positively selected TP53, NOTCH1 or FAT1. | These are selected coding loci, not a whole-genome per-cell mutation count. The cohort and exposure measures are valuable for age/exposure analysis, but variants and selection cannot be generalized to unexposed skin or other organs. Supplementary mutation and clinical datasets are public; raw sequencing is deposited at EGA study `EGAS00001004279`. Paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC7614988/ |
| **Liver hepatocytes versus liver stem cells, single-cell WGS** | In 48 single hepatocytes from 12 donors aged five months to 77 years, median mutation counts were 1,222 SNVs/cell in the group aged 36 or younger and 4,054 in the group aged 46 or older. Adult liver stem cells had substantially lower mutation frequencies than differentiated hepatocytes. Four extreme high-mutation hepatocytes were excluded from the age-model fit. | This separates per-cell passenger burden from expanding clone burden and shows that cell identity matters even within one organ. The cross-sectional study did not show that these mutations caused liver functional decline or that correcting them restores function. Raw data are controlled through dbGaP `phs001956.v1.p1`. Paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC6994209/ |
| **Nine-organ body map, WES and WGS** | The study analyzed 1,737 morphologically normal tissue biopsies from nine organs in five donors. Macroscopic clones were common in esophagus and cardia, whereas colon, rectum and duodenum mostly showed microscopic, spatially independent clones. S3's sensitivity-corrected donor medians span 11.3-103.0 in colon and 35.0-105.1 in liver for the VAF-qualified biopsy subset; the full nine-organ comparison appears below. | The spatial and donor-level variation argues against one pooled mutation-burden ranking. The small donor count limits population inference; EGA lists 1,792 archive samples for the raw dataset, so that archive sample count should not be substituted for the paper's 1,737 analyzed biopsies. Supplementary mutation tables are public; raw reads require DAC approval. Paper: https://www.nature.com/articles/s41586-021-03836-1 |

### Donor-Aware Body-Map Summary

From S3 Sheet2, I took each organ's reported sensitivity-corrected median
coding mutation burden per biopsy for each donor, then summarized those donor
medians without pooling biopsies. The interval is the range across the
contributing donors. These values are for the paper's VAF-qualified subset
(median sample VAF 0.08-0.14), not all biopsies or a population-level estimate.

| Tissue | Donors | Median of donor medians | Range across donor medians |
| --- | ---: | ---: | ---: |
| Bronchus | 3 | 29.3 | 21.4-37.3 |
| Cardia | 3 | 46.7 | 34.5-56.7 |
| Colon | 5 | 21.4 | 11.3-103.0 |
| Duodenum | 4 | 39.4 | 18.2-65.1 |
| Esophagus | 5 | 33.5 | 26.1-50.2 |
| Liver | 5 | 83.2 | 35.0-105.1 |
| Pancreas | 5 | 11.9 | 7.7-19.2 |
| Rectum | 4 | 50.5 | 8.4-79.2 |
| Stomach | 4 | 36.0 | 27.3-40.0 |

The donor-median spread is about 9.1-fold in colon and 9.4-fold in rectum,
versus 3-fold in liver. This is a descriptive signal of substantial
between-donor variation; five donors cannot separate age, exposure, biology
and sampling effects or establish an organ-wide ranking. The body's mutation
burden is not one scalar target, and the published spatial clone maps further
show that burden and clone size are separate properties.

### Liver Body-Map Supplement Audit

The pan-organ study's Supplementary Table 3 gives liver-specific summaries for
each donor. The sample counts and both figure summaries below are copied from
its Sheet2. Extended Data Fig. 2c is explicitly the sensitivity-corrected
subset with median VAF 0.08-0.14; these are not counts of mutations per cell.

| Donor | Source sample n | Median (Fig. 1c), range | Median (Extended Data Fig. 2c), range |
| --- | ---: | ---: | ---: |
| PN1 | 20 | 27 (13-84) | 35.0 (20.2-91.0) |
| PN2 | 15 | 86 (20-200) | 91.8 (28.7-202.3) |
| PN7 | 31 | 60 (29-95) | 61.2 (31.2-96.9) |
| PN8 | 39 | 78 (43-125) | 83.2 (50.3-127.6) |
| PN9 | 23 | 103 (30-159) | 105.1 (30.5-163.3) |

Within liver alone, sensitivity-corrected donor medians span 3.0-fold before
any between-organ comparison. These are five donor summaries, not 128
independent people; the source table's sample n values total 128. This
reinforces the warning against reading the pooled liver median as a population
ranking.

I also audited the row-level coding-call sheet. It contains 66,188 mutation
rows for 1,731 distinct sampleIDs, whereas the paper reports 1,737 biopsies.
The reason for the six-ID difference is not exposed by this sheet alone.
Liver-coded IDs (`PN[donor]L-...`) account for 18,246 rows across 248 sampleIDs
from the five donors. Liver-row impact labels are 12,218 `Missense`, 4,587
`Synonymous`, 905 `Nonsense`, 313 `Essential_Splice`, 23 `Stop_loss` and 200
`no-SNV`.
These are annotated coding-call rows, not per-cell burdens or independent
donors. The `gene` column also loads as a date for 67 rows across the workbook,
including 21 liver rows. I queried all 60 unique affected loci against
Ensembl's GRCh37 gene-overlap endpoint. The source worksheet does not identify
its reference assembly, so these are provisional coordinate checks rather
than a complete annotation repair. The same date value, `2021-03-01`, maps to
both `MARC1` and `MARCH1` at different loci; some other affected positions
overlap multiple protein-coding genes. A date-to-symbol lookup is therefore
unsafe. I left the workbook unchanged and withheld gene-frequency ranking
until the original transcript annotations and assembly are reconciled. The
six-ID difference and date-coerced values are data-quality questions, not
biological findings. Ensembl endpoint:
https://grch37.rest.ensembl.org/documentation/info/overlap_region. Primary source:
https://www.nature.com/articles/s41586-021-03836-1.

### Liver Hotspot and Driver-Enrichment Check

Publisher Supplementary Table 9 lists one cancer-hotspot call in normal liver:
`TP53 H179R` in `PN9L-1-3`. I matched it to the same `chr17:7578394 T>C`
missense call in Table 3 Sheet1, confirming the two supplement tables agree
for this variant. A hotspot in one sampled donor is not evidence that the
mutation damaged liver function or that correcting it would improve function.

Supplementary Table 10 reports one-sided hypergeometric p-values for 32 genes
across nine organs. Seven liver entries have nominal p<0.05. I applied
Benjamini-Hochberg correction across the full 288 gene-by-organ tests; among
those seven liver entries, only `KMT2D` remains below q=0.05. These are
exploratory enrichment signals, not variant-level causal evidence or repair
targets.

| Liver gene | Published p | Local BH q (288 tests) |
| --- | ---: | ---: |
| KMT2D | 3.21e-4 | 0.0120 |
| APOB | 7.24e-3 | 0.1390 |
| AMER1 | 1.29e-2 | 0.2188 |
| NOTCH2 | 1.92e-2 | 0.2909 |
| PTCH1 | 2.84e-2 | 0.3638 |
| ARHGAP35 | 2.84e-2 | 0.3638 |
| ZNF750 | 4.13e-2 | 0.4572 |

This ranks `KMT2D` as the strongest corrected liver-enrichment lead for
mechanistic follow-up; the TP53 hotspot is an internal cross-table consistency
check, not independent replication. Neither result establishes that the
signal causes age-related liver decline.

### Skin Supplement Audit

I joined the public skin Supplementary Dataset S1 mutation calls to S2 donor
metadata by `sampleID`. The join is one-to-one across all 123 donors. The 5,214
calls give a mean of 42.39 per sample (median 27; range 2-169), matching the
paper's reported summary. These are calls in a targeted 46-gene, 0.32-Mb panel,
not a whole-genome or per-cell mutation burden. In the joined tables, 98/123
donors (79.7%) have at least one protein-altering call annotated as missense,
nonsense, frameshift, splice-site or in-frame in TP53, NOTCH1 or FAT1. These
are cancer-associated selected clones, not validated anti-aging edit targets.

The raw donor-level count median is 48 in chronically photoexposed sites (44
donors) and 19 in intermittently exposed sites (79 donors), but the chronic
site donors are older on average (69.9 versus 52.2 years). That imbalance makes
the unadjusted contrast unsuitable as an exposure effect. A complete-case OLS
fit of log call count with age, phototype, sex, site exposure class, sun damage,
sun history and MC1R genotype (n=104) gives adjusted R-squared 49.34%, close to
the paper's reported 49.88%. The estimated age multiplier is 1.33 per decade
(classical normal-theory 95% interval 1.22-1.44); the intermittent-versus-
chronic site ratio is 0.84 (0.59-1.20), an interval that includes no difference.
Type II ANOVA on this fit gives p=1.8e-9 for age and p=7.8e-4 for phototype;
all other predictor terms have p>=0.23. These are local classical OLS tests,
not claimed as the paper's exact ANOVA implementation.
The authors likewise identify age and phototype as the strongest contributors
and report that other tested risk factors do not remain significant. This is a
near-reconstruction of the overall model fit, and it does not turn the crude
site contrast into a causal exposure effect.

I also calculated an all-subsets Shapley/LMG decomposition: for each predictor,
average its incremental R-squared over all possible predictor orderings, then
express that contribution as a share of the full model's explained variance.
The results sum to 100%; the three percentages explicitly quoted in the paper
match within 0.06 percentage points. This is strong evidence that the predictor
grouping and decomposition have been reconstructed, though the paper's exact
model-selection code was not available for direct comparison.

| Predictor | Local share of explained variance | Published textual benchmark |
| --- | ---: | ---: |
| Age | 55.10% | 55.16% |
| Skin phototype | 17.95% | 17.92% |
| Site exposure pattern | 7.79% | 7.82% |
| Sun-damage rating | 7.92% | Not stated in article text |
| Sun-exposure history | 5.41% | Not stated in article text |
| Sex | 3.84% | Not stated in article text |
| MC1R genotype | 1.99% | Not stated in article text |

The 30-page publisher supplement specifies the predictor set, names R's
`relaimpo` package for relative importance, and reports AIC comparison of
linear, log-linear, quadratic, cubic and non-linear age models. Using all 123
donor-level counts, I reproduced the first four Figure S3 model comparisons.
The local AIC values below use R's parameter-count convention (two points
above `statsmodels`' default OLS AIC); model p-values are overall F tests.

| Age model | Published AIC (p) | Local AIC (p) |
| --- | ---: | ---: |
| Linear | 1203.23 (1.64e-11) | 1203.23 (1.64e-11) |
| Log-linear | 291.00 (2.54e-14) | 291.00 (2.53e-14) |
| Quadratic | 1203.79 (7.74e-11) | 1203.79 (7.74e-11) |
| Cubic | 1203.13 (1.34e-10) | 1203.13 (1.34e-10) |
| Non-linear | 1204.16 (9.25e-06) | Not reproduced |

The supplement does not define the non-linear candidate's formula, so that
curve remains unreproduced. The log-linear fit models `ln(count)`, while the
polynomial candidates model counts directly; AIC values across response
transformations require a common likelihood scale. Applying the lognormal
Jacobian correction to the local R-style log-linear AIC gives 1107.35 on the
count scale, still below the best raw-count polynomial AIC (1203.13). Thus the
model preference remains under this correction, though the displayed AIC gap
of 291 versus 1203 is not itself a like-for-like comparison.

As a separate check, I fit `ln(call count) ~ age` within each phototype and
ran 1,000 nonparametric paired-bootstrap resamples, resampling donors with
replacement within each phototype (seed 12345). Predictions are expected S1
panel calls at age 65 from the full-sample fits; intervals are percentile
bootstrap intervals. The supplement also states 1,000 runs but does not provide
a seed or more detailed resampling implementation, so this is not a bitwise
replication.

| Phototype | Donors | Calls per decade multiplier | Predicted calls at 65 (95% bootstrap interval) |
| --- | ---: | ---: | ---: |
| I | 14 | 1.51 | 50.4 (28.2-92.0) |
| II | 47 | 1.38 | 35.6 (28.9-44.3) |
| III | 46 | 1.30 | 38.9 (30.5-48.0) |
| IV | 15 | 1.23 | 14.7 (9.4-21.7) |

The paper reports 68.63 calls at age 65 for phototype I (40.65-122.73) and
14.22 for phototype IV (8.16-20.54); both point estimates fall within the local
intervals, but the local phototype-I point estimate is about 27% lower.
Averaging the 1,000 bootstrap predictions yields 53.0 calls for type I and
15.0 for type IV, so bootstrap point-summary choice does not remove the type-I
gap. Small donor groups make these slopes and predictions uncertain. These are
targeted-panel mutation-count analyses, not evidence that editing the variants
would reverse skin aging. Primary study:
https://pmc.ncbi.nlm.nih.gov/articles/PMC7614988/.

### Public NanoSeq Supplement Audit

I streamed the public S8/S9 workbooks and the S4 selection table. S8 contains
341,620 oral mutation-record rows (296,128 SNVs, 30,662 deletions, 13,181
insertions, 1,622 DNVs and 27 MNVs); S9 contains 75,377 blood rows (68,488
SNVs, 4,031 deletions, 2,395 insertions, 441 DNVs and 22 MNVs). The median
per-record duplex VAF was 0.147% in oral (5th-95th percentiles: 0.052-0.930%)
and 0.173% in blood (0.066-1.020%). These summaries count workbook rows;
percentiles use the stored `duplex_vaf` values without person-level weighting.
They are not mutation counts per person or estimates of donor prevalence. The
published S4 site-level selection output contains 1,308
oral replacements across 58 genes and 21 blood replacements across 11 genes;
the 58 site-level genes are distinct from the paper's 46-gene gene-level
positive-selection result. The site-level sheet includes oral NOTCH1
C440R/F357S/I471T and blood DNMT3A Y735C examples. Selection is a fitness
signal, not evidence that editing those variants is beneficial.

Neither S8 nor S9 exposes a participant/sample identifier. The supplementary
analysis code uses sample IDs for donor-specific models and uses
`times_called` as mutation-call multiplicity; this column is not a participant
key. We therefore cannot reproduce donor-level age/exposure effects, twin
comparisons, or matched buccal-blood contamination checks from the public
workbooks alone. S8/S9 VAF distributions are descriptive over mutation rows,
and should not be compared with the paper's selected-driver or per-person
summaries as if the denominators matched.

### Cross-Tissue Readout

This comparison strengthens mutation mapping as a target-prioritization layer,
not as a correction result. The same gene can have different clone fitness and
organ consequences by cell type; mutation burden, mutant-cell fraction and
spatial clone size are distinct quantities. A credible repair hypothesis must
name the exact allele and cell type, measure corrected-cell coverage, and test
tissue function, competition with unedited clones and tumor-selection risk.
None of the skin, blood, oral, liver or multi-organ mapping studies tested
mutation correction as a treatment for ordinary aging.

### Data Retrieval Notes

I downloaded and inspected the public body-map S3 workbook, the 2025 NanoSeq
site-level selection workbook (S4), and blood mutation table (S9). The 44.7-MB
oral mutation table (S8) was retrieved through Europe PMC's official
`supplementaryFiles` REST endpoint after the publisher media host returned a
client challenge. The S8 workbook is 46,876,574 bytes (SHA-256
`8B79B04D2951F45F70A90A6AD040EB433502A92DB201E161DE6EEE8ACBE15389`). The
Europe PMC ZIP was 68,429,726 bytes (SHA-256
`466CFF062FF284CA543D2758017119FEA5B023E3DFBF05B118487D036D12DD2A`); its
Supplementary Code file was inspected to verify the table-field limitation.
The raw oral and blood sequencing datasets and linked participant metadata
remain under TwinsUK-controlled EGA access.

The S3 mutation-call sheet has 66,188 coding-variant rows across 1,731
`sampleID`s with at least one listed call. The paper reports 1,737 analyzed
biopsies. S3 does not explain the six-ID difference, so absent IDs should not
be interpreted as zero-mutation biopsies or used to reconstruct the study
denominator.

The skin Supplementary Datasets S1-S2 workbook was retrieved from the
publisher's supplementary-file host; it is 488,802 bytes (SHA-256
`17F6A04FB38486D62E66A1D5EC0112E5B72C8046302697E8CF73ED95F87D0F14`). S1
contains 5,214 mutation calls and S2 contains metadata for 123 donors, joined
by `sampleID`. The publisher's 2,470,248-byte Supplementary Material PDF was
also inspected (SHA-256
`FEDB841F0C7C1D68315BEE0955B3C9BE050C76E94C73573F673AA30AEF79F6AB`). Raw
sequencing remains controlled through EGA study `EGAS00001004279`.

### Readout

The most testable near-term mutation-repair hypothesis is not "edit all
age-associated mutations." It is to distinguish mutation-only from compound
allele states (especially NOTCH1 SNV plus LOH, double NOTCH1 hits, and mono- vs
biallelic TP53 loss), then ask whether correction changes a functional,
tissue-relevant endpoint without harming clone competition or tumor
surveillance. The HGPS vessel study shows that partial correction can shift a
causal model's tissue phenotype, but the required edited fraction and response
cannot be carried over to normal-aging clones.

For ordinary aging, the matrix still contains no mutation-repair intervention.
The strongest current signals are cell-state and clone-selection associations,
not restored tissue function or rejuvenation.

## Working Readout

The near-term opportunity is mutation-and-cell-state triage, not indiscriminate
correction. A useful candidate needs evidence that the specific variant is
causal in a defined cell type, that its clone is harmful rather than neutral or
advantageous in context, that the intended cells can be reached at useful
coverage, and that correction changes a functional tissue endpoint without
creating a worse clonal or off-target state. Epigenetic reprogramming can be
measured alongside those variables but cannot stand in for sequence correction.

This pilot review did **not** identify evidence that heterogeneous,
age-acquired mutations can currently be broadly corrected to rejuvenate an
older human. This is a bounded finding from exploratory searches and selected
primary studies, not a systematic-review conclusion. Search ranking also
produced irrelevant hits, so the returned set needs human screening before any
synthesis is treated as complete.

## Next Research Increment

- Request controlled EGA access before attempting raw scG2P or SMART-PTA
  sequencing analyses; do not mirror the multi-hundred-gigabyte files locally.
- Reconcile the four-donor SMART-PTA manuscript with the later five-sample
  EGA/iTOL project update before treating `eso05` as a published result.
- Use the public scG2P workbook for genotype/RNA summaries, preserving donor as
  the replication unit. Its per-cell phenotype tables do not carry LOH calls;
  obtain an authorized LOH-call table through EGA before attempting an
  allele-state comparison of NOTCH1 SNV-only, LOH-only and SNV-plus-LOH cells.
- Continue variant-level analysis of public NanoSeq S4/S8/S9 while keeping
  each sheet's denominator explicit. Donor-aware age/exposure, twin and
  matched-blood analyses require authorized EGA data plus linked participant
  metadata; the public S8/S9 mutation tables do not include sample IDs.
- Reconcile the remaining phototype-I point-estimate difference and identify
  the unpublished non-linear comparison formula and exact bootstrap details;
  the other Figure S3 models, overall fit and three quoted relative-importance
  shares now reproduce closely from S1-S2.
- Extend the liver comparison with its public mutation tables, preserving
  tissue, cell class, assay sensitivity and donor as separate axes.
- Add an evidence matrix for each proposed edit: causal evidence, cell/tissue
  scope, clone fitness, functional endpoint, delivery coverage, durability,
  off-target and tumor-selection risks, and explicit falsifiers.
- Keep the `LMNA` progeria correction study as a positive-control class for
  known monogenic repair, not as a proxy for normal aging.
- Do not launch docking for this campaign unless a specific protein-ligand
  mechanism is justified and a prepared, experimentally grounded receptor is
  available. No anti-aging target docking run has been made in this pilot.
