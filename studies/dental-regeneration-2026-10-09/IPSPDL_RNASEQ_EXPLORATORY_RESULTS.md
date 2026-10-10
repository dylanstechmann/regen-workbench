# iPS-PDL RNA-seq: exploratory reanalysis

This is a descriptive reanalysis of DDBJ BioProject [PRJDB39888](https://ddbj.nig.ac.jp/search/entry/bioproject/PRJDB39888), cited by Taniguchi et al. (2026). It screens expression patterns across iPS-PDL, parental iPS and primary PDL samples. It does not fit inferential differential-expression tests or establish a functional PDL phenotype.

## Biological-unit scope

The archive provides three run-linked samples in each labeled group: iPS-PDL1–3, iPS1–3 and primary PDL1–3. The associated [Li et al. methods](https://www.jstage.jst.go.jp/article/dmj/advpub/0/advpub_2025-235/_pdf) identify one HPS0381 parental iPSC line differentiated using conditioned media from three distinct PDL sources to produce iPS-PDL#1–3. [Taniguchi et al.](https://www.frontiersin.org/journals/cell-and-developmental-biology/articles/10.3389/fcell.2026.1821829/full) likewise describe three independently differentiated iPS-PDL lines. The DDBJ run labels align numerically, but DDBJ does not map each run to its PDL donor or conditioned-medium source; that crosswalk remains an inference across publications. These are not three independent parental iPSC donors. The primary PDL comparators come from three commercial donors (ages 18, 24 and 44 in archive metadata), and DRR913336 is single/layout-unspecified.

## Processing and quantification

All 17 archive FASTQ files (15,976,782,817 compressed bytes) were downloaded and SHA-256 checked against the recorded receipts. BZip2 inputs were streamed once to local seekable gzip files; raw reads and derived outputs remain in ignored local `data/` storage. FastQC 0.12.1 and MultiQC 1.35 generated per-file reports and a local aggregate report.

Salmon 2.7.0 quantified the nine runs with automatic library-type detection, selective alignment, sequence-bias correction and GC-bias correction. The index contains 670,670 [GENCODE human release 50](https://www.gencodegenes.org/human/release_50.html) transcript references on GRCh38.p14. It is transcript-only and has no genomic decoy; the [Salmon documentation](https://salmon.readthedocs.io/en/stable/salmon.html) recommends decoy-aware references to reduce spurious transcript matches. The run command and environment are recorded in [the pipeline](run_ipspdl_rnaseq.sh), [container recipe](rnaseq.Dockerfile) and [environment file](ipspdl_rnaseq_environment.yml).

For a compact marker screen and visualization, transcript TPMs are summed by the GENCODE gene ID embedded in each transcript header. This is a descriptive sum, not a gene-level model with transcript-length offsets. PCA uses centered `log2(gene TPM + 1)` values for the 2,000 most variable expressed genes. The scripts preserve per-run mapping metadata and write complete gene, marker, mapping and PCA tables to ignored local analysis storage.

## FastQC module flags

All 17 reports were generated (187 module checks). The per-base sequence-content and sequence-duplication modules were flagged FAIL in every file. Per-tile sequence quality was WARN in six read files: DRR913329_1, DRR913330_1, DRR913331_1, DRR913332_1, DRR913334_1 and DRR913335_1. The remaining eight module categories passed in every file. These flags describe sequence composition, duplication and tile-level quality; they do not by themselves determine whether the libraries are unusable. RNA-seq expression skew can elevate duplication, but the flags remain relevant technical caveats and are retained rather than filtered away.

## Quantification and expression summaries

All nine runs produced nonempty `quant.sf` files. Salmon's metadata records a completed estimate with EM convergence for all nine. The matrix contains 86,411 gene IDs after descriptive transcript-TPM summation. Per-run mapping was:

| Sample | Run | Group | Layout | Mapped / processed fragments | Mapping rate | Detected type |
|---|---|---|---|---:|---:|---|
| iPS_PDL1 | DRR913328 | iPS-PDL | Paired | 16,405,898 / 17,638,797 | 93.01% | IU |
| iPS_PDL2 | DRR913329 | iPS-PDL | Paired | 16,755,863 / 17,585,315 | 95.28% | IU |
| iPS_PDL3 | DRR913330 | iPS-PDL | Paired | 16,078,092 / 17,985,621 | 89.39% | IU |
| iPS1 | DRR913331 | iPS | Paired | 14,513,906 / 15,656,256 | 92.70% | IU |
| iPS2 | DRR913332 | iPS | Paired | 13,253,697 / 14,383,864 | 92.14% | IU |
| iPS3 | DRR913333 | iPS | Paired | 13,569,537 / 14,844,585 | 91.41% | IU |
| PDL1 | DRR913334 | primary PDL | Paired | 12,668,266 / 13,462,016 | 94.10% | IU |
| PDL2 | DRR913335 | primary PDL | Paired | 15,615,786 / 16,474,981 | 94.78% | IU |
| PDL3 | DRR913336 | primary PDL | Single/layout-unspecified | 15,218,436 / 16,359,273 | 93.03% | U |

Median mapping was 93.01% (range 89.39–95.28%) for iPS-PDL, 92.14% (91.41–92.70%) for parental iPS and 94.10% (93.03–94.78%) for primary PDL. Salmon reported a small `strand_bias_unstranded` diagnostic in eight of nine runs; `strand_mapping_bias` ranged from 0.50992 to 0.51290. The inferred types were compatible with all assigned fragments, but the small directional imbalance is retained as a technical caveat, not a biological signal.

### Exploratory marker panel and PCA

The following are medians and ranges across the three sample labels per group, in transcript TPM summed by gene. They are descriptive values, not fitted differential-expression estimates.

| Gene | iPS-PDL | Parental iPS | Primary PDL |
|---|---:|---:|---:|
| POSTN | 4,086.65 (2,581.86–4,541.36) | 0.65 (0.25–0.77) | 527.60 (91.10–1,452.93) |
| COL1A1 | 15,961.17 (13,078.31–16,661.34) | 65.44 (50.54–82.30) | 19,259.55 (17,797.99–19,932.55) |
| DCN | 90.78 (39.80–100.61) | 0.00 (0.00–1.99) | 4,752.21 (1,711.17–5,755.75) |
| SCX | 1.57 (1.10–3.13) | 1.74 (1.61–1.82) | 0.76 (0.36–1.66) |
| TNMD | 0.00 (0.00–1.05) | 2.83 (2.11–3.16) | 0.00 (0.00–0.00) |
| MKX | 1.70 (0.72–2.43) | 0.31 (0.29–0.64) | 28.81 (11.58–73.67) |
| POU5F1 | 0.91 (0.59–1.53) | 6.28 (4.70–7.84) | 0.79 (0.72–1.19) |
| SOX2 | 0.00 (0.00–0.06) | 136.01 (111.56–190.84) | 0.00 (0.00–0.00) |

The iPS-PDL label group had high POSTN and COL1A1 relative to parental iPS, while primary PDL also had high COL1A1 and much higher DCN and MKX. SCX and TNMD were low across all three group medians. POU5F1 and SOX2 were highest in parental iPS. This is consistent with a changed matrix-associated expression profile and reduced pluripotency-marker expression in the iPS-PDL samples, but it does not establish a complete native PDL identity or mature ligament function. Several primary-PDL marker ranges are broad, including POSTN and COL3A1, so donor-level variation remains visible.

In the descriptive PCA of the 2,000 most variable expressed genes, the three sample-label groups occupy distinct regions: PC1 explains 74.6% and PC2 14.5% of selected-gene variance. With three samples per group, one parental iPSC background for the iPS-PDL products and unresolved differentiation-source mapping, this separation is a visualization of this dataset, not a statistical group test or independent-donor validation. The local PCA image and complete marker, gene-TPM, mapping and coordinate tables are in ignored `data/structures/ipspdl-rnaseq/summary/` and are not committed.

## Interpretation limits

The expression results are hypothesis-generating. The design has three iPS-PDL differentiation products from one parental iPSC background, three primary PDL donors with different age/sex metadata, and no run-to-conditioned-medium source map. Cell type is therefore confounded with source and differentiation context. One primary PDL sample is single/layout-unspecified, so its comparison has a library-layout caveat. PCA is a descriptive display, not a test of group separation. The targeted panel is not a validated PDL identity signature; marker expression cannot establish oriented insertion at cementum and bone, ligament-space preservation, load transfer, clinical benefit or safety.

## Full-genome-decoy reference sensitivity

The same nine libraries were re-quantified with the 670,670 unchanged GENCODE 50 transcript targets plus the GRCh38.p14 genomic decoys described in the [decoy pipeline](IPSPDL_DECOY_PIPELINE.md). All nine estimates completed and converged; each baseline and decoy quantification had identical transcript target names and lengths, and no other quantification-setting or detected-library-type changes were recorded. The [decoy run receipt](ipspdl_decoy_run_receipt.json) binds each result to its inputs, reference, driver, and output hashes. Candidate mapping rates are lower because Salmon can assign fragments to genomic decoys rather than transcript targets; the decoy runs recorded 934,596–2,130,572 decoy fragments per library. This is a reference-sensitivity result, not a library-quality verdict.

| Scope and group | n | Baseline median mapped | Decoy median mapped | Change (percentage points) |
|---|---:|---:|---:|---:|
| All: iPS-PDL | 3 | 93.01% | 91.32% | -1.69 |
| All: parental iPS | 3 | 92.14% | 89.69% | -2.45 |
| All: primary PDL | 3 | 94.10% | 92.33% | -1.77 |
| Paired-only: primary PDL | 2 | 94.44% | 92.67% | -1.78 |

Per-run Pearson correlations for log2(TPM+1), among genes with TPM ≥1 in either reference, ranged from 0.964 to 0.988; median absolute log2(TPM+1) changes ranged from 0.036 to 0.140. Large changes for individual genes remain visible in the local `data/structures/ipspdl-rnaseq/sensitivity/largest_gene_tpm_changes.tsv` output. PCA geometry was highly stable: correlations across all pairwise sample distances on 2,000 fixed baseline-selected genes were 0.999887 for all nine libraries and 0.999917 for the eight paired libraries. Independently reselected gene sets overlapped by 1,861/2,000 genes (all nine) and 1,852/2,000 (paired-only). PC1/PC2 explained 74.6%/14.5% of variance in the all-nine baseline and 74.8%/14.9% in its decoy estimate; for paired-only they explained 78.7%/13.5% and 79.2%/13.9%, respectively.

The broad matrix-associated pattern remained: decoy-reference medians for POSTN were 4,278.17 TPM in iPS-PDL, 0.72 in parental iPS and 542.02 in primary PDL; for COL1A1 they were 17,351.67, 72.69 and 21,124.68 TPM, respectively. DCN remained much higher in primary PDL than in the other groups, while SCX, TNMD and MKX remained low in the cultured products. POU5F1 was reference-sensitive: its group medians changed from 0.91 to 0 TPM for iPS-PDL, 6.28 to 1.91 for parental iPS, and 0.79 to 0 for primary PDL. The zero decoy medians are not zero in every library: the per-library maxima were 0.067 TPM for iPS-PDL and 0.300 TPM for primary PDL. Ten of 198 marker/group-pair/scope median-order comparisons changed, mostly among low-expression markers. These shifts qualify the transcript-level estimates and do not establish a change in cell state or product identity.

The paired-only scope excludes DRR913336 because it is single/layout-unspecified. This also reduces primary PDL from three donor sources to two, so it cannot isolate a layout effect. Full comparison tables and the PCA figure are generated locally under ignored `data/structures/ipspdl-rnaseq/sensitivity/`; the analysis script and tracked summary above preserve the reproducible method and principal findings.

The transcript-only reference omits genomic decoys, transcript TPMs are summed directly to genes, and no differential-expression significance or multiple-testing analysis is performed. The FastQC flags above and any Salmon library-format warnings must be considered when reading the exploratory patterns. The [metadata audit](IPSPDL_RNASEQ_METADATA_AUDIT.md) and [manifest](ipspdl_rnaseq_manifest.tsv) preserve the archive joins and sample fields; the downloaded reads and generated matrices are intentionally not committed.
