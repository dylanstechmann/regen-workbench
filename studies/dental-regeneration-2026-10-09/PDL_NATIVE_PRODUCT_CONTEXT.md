# Native PDL reference and cultured iPS-PDL product context

Context date: 2026-10-10. This connects the source-scoped native-tissue marker screen with the existing cultured-cell RNA-seq analysis. The assays and biological units remain distinct.

The existing analyses support a matrix-associated expression profile in cultured iPS-PDL and a heterogeneous expression mixture in native PDL deposits. They do not establish a complete product identity, a developmental-stage effect, rejuvenation or a mechanically functioning periodontal ligament. In particular, SCX or TNMD alone cannot supply a universal pass/fail threshold: both are sparsely detected in the native deposits, while bulk assays average a different population using different measurement units.

## The reference and product answer different questions

| Dataset | Observation unit | Sample construction and unresolved issues | Useful descriptive question |
| --- | --- | --- | --- |
| Native PDL [GSE306722](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE306722) | Barcode within one deposited GEO record per developmental source label | The 12,769 and 12,993 barcode records have no cell-to-donor crosswalk. Numeric values are positive integer entries, but their exact preprocessing stage and raw UMI lineage remain unverified. | Which fixed-marker expression contexts are detectable within each deposited tissue mixture? |
| Cultured iPS-PDL / iPS / primary PDL [PRJDB39888](https://ddbj.nig.ac.jp/search/entry/bioproject/PRJDB39888) | Bulk RNA library, summarized descriptively within three archive labels per group | The iPS-PDL products share one HPS0381 parental iPSC background; three conditioned-medium sources/differentiation products do not substitute for unrelated parental donors. Primary PDL has three commercial donor sources. A run-to-conditioned-medium crosswalk is unresolved and one primary comparator has single/layout-unspecified reads. | What expression pattern accompanies differentiation and how sensitive is it to reference and comparator choices? |

The native study's immature/mature labels describe developmental-root sources. Their difference cannot be treated as an aging contrast, and the two archive records do not qualify independent-donor stage inference. The [source-linkage audit](PDLSC_SOURCE_LINKAGE_AUDIT.md) also distinguishes a matching conference abstract's 20+20 reported teeth from a verified deposited-library or unique-donor count.

## Native deposits: detection and deposited-entry normalization

These are all-barcode summaries from the fixed panel. Detection is positive deposited entry divided by all barcodes in that record. Abundance is the mean across barcodes of `ln(1 + 10,000 × feature entry / barcode total Gene Expression entries)`. It is called **mean ln(1 + deposited-entry cp10k)** because raw UMI lineage is unresolved. No bulk TPM value is used in this table. [Complete native results](PDLSC_NATIVE_MARKER_SCREEN.md), [public computational receipt](pdls_native_marker_receipt.json).

| Marker | GSM9206804 detected / 12,769 | Mean ln cp10k | GSM9206805 detected / 12,993 | Mean ln cp10k |
| --- | ---: | ---: | ---: | ---: |
| POSTN | 3,115 (24.40%) | 0.6120 | 6,406 (49.30%) | 1.7343 |
| COL1A1 | 5,174 (40.52%) | 1.3596 | 8,747 (67.32%) | 2.7244 |
| DCN | 4,128 (32.33%) | 0.9590 | 6,798 (52.32%) | 1.6974 |
| SCX | 421 (3.30%) | 0.0352 | 287 (2.21%) | 0.0239 |
| TNMD | 37 (0.29%) | 0.0029 | 151 (1.16%) | 0.0110 |
| MKX | 410 (3.21%) | 0.0327 | 718 (5.53%) | 0.0579 |

The separately implemented source-rule sensitivity screen retains 11,852/12,769 and 11,819/12,993 barcodes after requiring at least 200 detected Gene Expression features and mitochondrial entry fraction no greater than 10%. It leaves SCX detection at 3.48% and 2.34%, and TNMD at 0.31% and 1.24%, within the respective retained subsets. Screening does not certify cells, reproduce the source's full processing or remove doublets. The full report preserves both denominators rather than reporting only a favorable subset.

All 45 frozen symbols match unique Gene Expression feature rows in both files. Thus a reported zero for a marker is distinct from an absent or ambiguous feature. That does not mean a zero proves lack of biological expression: a barcode records a finite captured transcript sample, and low expression or inefficient capture can cause single-cell nondetection. The primary integrated dental atlas discusses this capture limitation and uses broader marker combinations for annotation. Here no imputation or cell labels are supplied. [Hermans et al., 2022](https://www.frontiersin.org/journals/cell-and-developmental-biology/articles/10.3389/fcell.2022.1021459/full).

## Cultured-cell baseline: gene-summed transcript TPM

The following summarize the published **transcript-only-reference baseline**, with values formatted from its retained numerical group-summary table, across three archive labels per group. Units are Salmon transcript TPM summed by GENCODE gene ID; they are neither positive-barcode percentages nor single-cell cp10k. The rows describe library-level patterns without donor-level significance tests. [Baseline analysis](IPSPDL_RNASEQ_EXPLORATORY_RESULTS.md), [sample provenance audit](IPSPDL_RNASEQ_METADATA_AUDIT.md).

| Gene | iPS-PDL TPM, median (range) | Parental iPS TPM, median (range) | Primary PDL TPM, median (range) |
| --- | ---: | ---: | ---: |
| POSTN | 4,086.65 (2,581.86–4,541.36) | 0.65 (0.25–0.77) | 527.60 (91.10–1,452.93) |
| COL1A1 | 15,961.17 (13,078.31–16,661.34) | 65.44 (50.54–82.30) | 19,259.55 (17,797.99–19,932.55) |
| DCN | 90.78 (39.80–100.61) | 0.00 (0.00–1.99) | 4,752.21 (1,711.17–5,755.75) |
| SCX | 1.57 (1.10–3.13) | 1.74 (1.61–1.82) | 0.76 (0.36–1.66) |
| TNMD | 0.00 (0.00–1.05) | 2.83 (2.11–3.16) | 0.00 (0.00–0.00) |
| MKX | 1.70 (0.72–2.43) | 0.31 (0.29–0.64) | 28.81 (11.58–73.67) |
| POU5F1 | 0.91 (0.59–1.53) | 6.28 (4.70–7.84) | 0.79 (0.72–1.19) |
| SOX2 | 0.00 (0.00–0.06) | 136.01 (111.56–190.84) | 0.00 (0.00–0.00) |

Within this bulk assay, the iPS-PDL pattern includes high POSTN/COL1A1 and reduced pluripotency-marker expression relative to parental iPS. The primary PDL labels also have high COL1A1 and more DCN/MKX than iPS-PDL. These are inspectable product/comparator differences; they do not resolve lineage identity or quantify residual tumorigenic cells. SCX and TNMD are low in the cultured primary comparators as well, so their low iPS-PDL levels cannot define an independently validated rejection threshold.

## Composition, specificity and assay sensitivity

The tissue screen includes detectable endothelial-associated PECAM1/CDH5, T-cell-associated CD3D/CD3E, myeloid-associated LYZ/CSF1R and perivascular-associated RGS5/KCNJ8 contexts. Their marginal detection does not establish cell identities, the fraction of each lineage, coexpression within one cell or whether multiplets/ambient RNA contribute. A bulk culture value likewise cannot distinguish uniform expression from a minority of strongly expressing cells. Capture, dissociation, culture selection and different transcript measurement/normalization schemes provide several competing explanations for apparent differences between these assays; none was isolated experimentally here.

Matrix genes are useful but incompletely specific. The integrated human-tooth atlas places POSTN and COL12A1 in both PDL and dental-follicle annotation panels. Collagens and proteoglycans describe extracellular-matrix expression without identifying an organized cementum–ligament–bone interface. The appropriate current output is an expression-context inventory with missing evidence, rather than a validated cell label or combined identity score. [Human-tooth atlas Table 6](https://pmc.ncbi.nlm.nih.gov/articles/PMC9590651/).

SCX/TNMD nondetection can reflect sparse sampling, the small fraction of a relevant cell state, processing or assay sensitivity; low bulk abundance can also reflect population composition. Conversely, detecting them does not demonstrate properly oriented fibers or load transfer. These alternatives are reasons to investigate joint marker patterns and orthogonal protein/spatial/functional measurements, not reasons to silently infer either success or failure from one marker. No effect size, fold change or numerical rank is calculated across the native cp10k and bulk TPM tables.

## The functional ligament gap

Li et al.'s cell-characterization study reports selected matrix/osteogenic and compression-responsive behaviors with batch variation. Such in-vitro responses do not directly measure a continuous ligament attached to both root cementum and alveolar bone, physiological tooth mobility or mechanical load transfer. A compression-associated transcriptional response and a mechanically functioning tooth–ligament interface are different observations. [Primary study](https://doi.org/10.4012/dmj.2025-235), [source-scoped functional review](IPS_PDL_FUNCTION_REVIEW.md).

For a bioidentical periodontal product, separate evidence questions remain: Does the resulting tissue maintain a ligament space? Do organized fibers insert at both interfaces? Does it support appropriate movement and sustained load transfer? Does it avoid ankylosis/root resorption and retain function over time? The native RNA deposits measure none of these whole-interface outcomes. The [existing model comparison](PDL_MODEL_COMPARISON.md) keeps bone, histology, attachment, mobility and durability distinct; proposed evidence requirements are not a laboratory protocol.

## Full-genome-decoy comparison: completed nine-run sensitivity

All nine final decoy-aware quantifications completed with exit code 0 and converged estimates. The comparison validates the same 670,670 transcript target names and lengths in both references, adds 706 full-genome decoy records, and finds no other normalized quantification-setting or detected library-type change. The final estimates are separate from earlier interrupted attempts; those attempts remain recorded rather than entering the comparison. [Final execution receipt](ipspdl_decoy_run_receipt.json), [decoy reference receipt](ipspdl_rnaseq_decoy_reference_receipt.json), [interrupted-attempt receipt](ipspdl_decoy_interrupted_attempt_receipt.json).

The following **decoy-aware bulk gene-summed TPM medians** use all three archive libraries per group. They share units with the cultured baseline table above; they are not native-barcode detection percentages or native cp10k. Exact medians, ranges and both inclusion scopes are retained in `data/structures/ipspdl-rnaseq/sensitivity/marker_group_summary.tsv`.

| Gene | iPS-PDL median TPM | Parental iPS median TPM | Primary PDL median TPM |
| --- | ---: | ---: | ---: |
| POSTN | 4,278.17 | 0.72 | 542.02 |
| COL1A1 | 17,351.67 | 72.69 | 21,124.68 |
| DCN | 101.99 | 0.00 | 4,890.54 |
| SCX | 1.53 | 1.63 | 0.66 |
| TNMD | 0.00 | 3.17 | 0.00 |
| MKX | 1.92 | 0.34 | 29.64 |
| POU5F1 | 0.00 | 1.91 | 0.00 |
| SOX2 | 0.00 | 148.98 | 0.00 |

The broad cultured-cell pattern persists under this reference change: iPS-PDL has high POSTN/COL1A1 relative to parental iPS, while primary PDL has higher DCN/MKX than iPS-PDL. SCX/TNMD remain low. POU5F1 is reference-sensitive: its medians change from 0.91/6.28/0.79 to 0.00/1.91/0.00 for iPS-PDL/parental iPS/primary PDL. A zero median is not absence in every library: the decoy-aware maxima are 0.067159 TPM in iPS-PDL and 0.299593 TPM in primary PDL. Neither these low estimates nor the parental-iPS contrast measures the absence of residual unsafe cells.

Per-run expression Pearson correlations are 0.9641–0.9879 on `log2(TPM + 1)` for genes with at least 1 TPM in either estimate; common low/zero genes are excluded from that calculation. Individual genes can still change substantially, so global agreement is not a blanket gene-level robustness claim. Ten of 198 marker/group-pair/inclusion-scope comparisons change median order, including small ALPL/BGLAP differences and some low pluripotency-marker comparisons that become ties. These are technical sensitivity observations rather than biological reversals. Exact evidence is retained in `data/structures/ipspdl-rnaseq/sensitivity/expression_agreement.tsv`, `largest_gene_tpm_changes.tsv` and `marker_group_order_sensitivity.tsv`.

With the same baseline-selected 2,000 PCA features, between-library distance Pearson correlations are 0.999887 for all nine libraries and 0.999917 for the paired-only subset. Independently selecting variable genes retains 1,861/2,000 and 1,852/2,000 feature overlaps, respectively. This supports stability of the broad descriptive geometry under the tested reference change, without establishing donor-independent group separation. The retained PCA summary and method are in `data/structures/ipspdl-rnaseq/sensitivity/summary.json`; the paired-only analysis excludes DRR913336 and therefore one primary PDL donor together with its single/layout-unspecified library. It leaves primary PDL n=2 while the other groups remain n=3, so it cannot isolate a library-layout effect. Pairing in the reference comparison means the same library quantified twice, not donor pairing between product and comparator.

The exact run-level mapping/library diagnostics remain in `data/structures/ipspdl-rnaseq/sensitivity/mapping_sensitivity.tsv`. The directory also retains full baseline/candidate gene-TPM tables and PCA coordinates/figure. These generated files remain ignored local artifacts. TPM is compositional: read reassignment can change a gene's normalized estimate without a biological change. Decoy-aware technical persistence therefore qualifies selected bulk expression patterns; it does not close the native-assay, donor, cell-identity, safety or functional-ligament gaps above, and it does not turn the native cp10k and bulk TPM tables into one score.

## Native receipt integrity check

The published native receipt was independently checked against exact Git blob bytes in commit `908bc8fa280e5d54b7cc6c3bc19d255d70815118`; the public remote main matched that commit at the check. The receipt matches the physical ignored run summary from 2026-10-10T19:55:59.780611+00:00 byte-for-byte. Its script, panel, source-audit and matrix-audit SHA-256 bindings match both the committed blobs and physical source files. The generated native report matches its committed blob and recorded output digest; the local marker TSV, barcode TSV, panel copy and inspected PNG match their recorded output hashes/sizes. All six matrix/feature/barcode input hashes also match the physical files and upstream audit. This verifies provenance integrity, not biological identity or function. [Published native receipt](pdls_native_marker_receipt.json).
