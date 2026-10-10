# Human PDL maturity single-cell dataset: qualification

## Why this dataset is relevant

GEO [GSE306722](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE306722) is a human periodontal-ligament single-cell RNA-seq study of immature and mature teeth. A matching [conference abstract by Shao et al., *International Dental Journal* (2025), DOI 10.1016/j.identj.2025.104622](https://doi.org/10.1016/j.identj.2025.104622) reports 20 teeth in each developmental group; its exact relationship to the deposited libraries is unverified. The GEO summary describes an osteogenic PDLSC subpopulation with RELB expression. Reported osteogenic endpoints do not establish restored periodontal attachment.

**2026-10-10 amendment:** The earlier qualification called the 2025 item an associated article and carried its tooth counts into the dataset description. The [source linkage audit](PDLSC_SOURCE_LINKAGE_AUDIT.md) corrects that attribution and identifies [PMID 42785307 / DOI 10.1016/j.stemcr.2026.103088](https://pubmed.ncbi.nlm.nih.gov/42785307/) as a strongly matching 2026 journal article. The retrieved abstract and six ordered authors match the archive, but an explicit accession statement and full methods were not retrieved. The original metadata receipt is preserved as a dated retrieval; its publication-count sentence is superseded by this amendment.

This is a useful follow-up to the PRJDB39888 iPS-PDL comparison because it profiles native PDL tissue and its cell-state mixture. It can help frame which native cell states a proposed periodontal construct should be compared with. Its immature-versus-mature contrast is a developmental-root-maturity comparison, not an aging or rejuvenation experiment.

## Archive-level eligibility

The source GEO family metadata was retrieved through `regen.http_bytes` on 2026-10-10 and is inventoried in [pdls_maturity_metadata_receipt.json](pdls_maturity_metadata_receipt.json). The receipt records the exact source URL, response hash, sample accessions, source labels and metadata fields. Raw SOFT bytes and the `regen.record` provenance file remain under ignored `data/literature/` and `data/provenance/` directories.

GEO exposes two sample records, labeled immature and mature. The conference abstract's 20 teeth per group are not 40 individually mapped GEO sample records or necessarily 40 unique donors. The retrieved archive metadata does not identify individual tooth donors or map cells back to donors. Its processing field says a custom script combined expression data and metadata from libraries corresponding to one batch, then filtered cells and generated scaled/log-transformed values for downstream clustering. The cells are not independent biological replicates, and the archive alone does not support donor-level variance estimates, donor-held-out validation or inferential testing of the maturity contrast.

The subsequent [matrix audit](PDLSC_MATURITY_MATRIX_AUDIT.md) downloaded and hash-checked all six supplementary files. Each record has 36,601 features; immature and mature records contain 12,769 and 12,993 barcodes. Positive integer entries pass sparse-structure checks, qualifying a descriptive count-like analysis. Their precise preprocessing stage and raw-UMI provenance remain unresolved. There are 127 and 75 barcodes below 200 detected features, despite the source's described downstream filter. Sample-prefixed barcode identifiers are required because 59 strings overlap between records.

## Decision for the next comparison

Keep this accession as a **candidate native-PDL cell-state reference**, not a qualified validation cohort. The structural audit permits a fixed-panel descriptive marker screen with explicit inclusion sensitivity. Donor/library construction and raw-UMI provenance remain open source questions. Any cell-level result should be labeled descriptive unless independent sample units and their mapping become available.

For construct assessment, marker similarity would remain a screening result. Functional periodontal regeneration still requires evidence for oriented fiber insertion at cementum and bone, a maintained ligament space, appropriate mechanical load transfer, and durable integration without ankylosis or root resorption. The current dataset does not measure those whole-interface outcomes.

## Sources

- [GEO GSE306722](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE306722): deposited series and sample-level archive metadata.
- [NCBI BioProject PRJNA1311975](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA1311975): linked project record; archive listing reports two SRA experiments and two BioSamples.
- [GEO sample GSM9206804](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM9206804) and [GSM9206805](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM9206805): immature and mature sample records and supplementary matrices.
- [Shao et al. conference abstract (2025), DOI 10.1016/j.identj.2025.104622](https://doi.org/10.1016/j.identj.2025.104622): reports 20 teeth per stage; explicit library linkage unverified.
- [Shao et al. (2026), PMID 42785307](https://pubmed.ncbi.nlm.nih.gov/42785307/): strongly matching associated-study candidate; full methods and accession statement not retrieved.
