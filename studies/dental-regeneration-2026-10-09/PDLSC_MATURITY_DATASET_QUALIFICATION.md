# Human PDL maturity single-cell dataset: qualification

## Why this dataset is relevant

GEO [GSE306722](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE306722) is a human periodontal-ligament single-cell RNA-seq study of immature and mature teeth. The associated article reports 20 teeth in each developmental group and describes an osteogenic PDLSC subpopulation with RELB expression; its reported perturbation results are evidence about the study's chosen osteogenic endpoints, not proof of restored periodontal attachment. The publication is [Shao et al., *International Dental Journal* (2025), DOI 10.1016/j.identj.2025.104622](https://doi.org/10.1016/j.identj.2025.104622).

This is a useful follow-up to the PRJDB39888 iPS-PDL comparison because it profiles native PDL tissue and its cell-state mixture. It can help frame which native cell states a proposed periodontal construct should be compared with. Its immature-versus-mature contrast is a developmental-root-maturity comparison, not an aging or rejuvenation experiment.

## Archive-level eligibility

The source GEO family metadata was retrieved through `regen.http_bytes` on 2026-10-10 and is inventoried in [pdls_maturity_metadata_receipt.json](pdls_maturity_metadata_receipt.json). The receipt records the exact source URL, response hash, sample accessions, source labels and metadata fields. Raw SOFT bytes and the `regen.record` provenance file remain under ignored `data/literature/` and `data/provenance/` directories.

GEO exposes two sample records, labeled immature and mature. The publication's stated 20 teeth per group do not appear as 40 individually mapped GEO sample records. The retrieved archive metadata does not identify individual tooth donors or map cells back to donors. Its processing field says a custom script combined expression data and metadata from libraries corresponding to one batch, then filtered cells and generated scaled/log-transformed values for downstream clustering. The listed matrix files therefore need a content-level check before anyone treats them as raw counts. The cells are not independent biological replicates, and the archive alone does not support donor-level variance estimates, donor-held-out validation or inferential testing of the maturity contrast.

## Decision for the next comparison

Keep this accession as a **candidate native-PDL cell-state reference**, not a qualified validation cohort. A future expression comparison should first establish whether raw counts or only transformed values are supplied, recover any pooled-sample and donor mapping from the article or source authors, and freeze cell inclusion and marker definitions before comparing with iPS-PDL. Any cell-level result should be labeled descriptive unless independent sample units and their mapping become available.

For construct assessment, marker similarity would remain a screening result. Functional periodontal regeneration still requires evidence for oriented fiber insertion at cementum and bone, a maintained ligament space, appropriate mechanical load transfer, and durable integration without ankylosis or root resorption. The current dataset does not measure those whole-interface outcomes.

## Sources

- [GEO GSE306722](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE306722): deposited series and sample-level archive metadata.
- [NCBI BioProject PRJNA1311975](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA1311975): linked project record; archive listing reports two SRA experiments and two BioSamples.
- [GEO sample GSM9206804](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM9206804) and [GSM9206805](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM9206805): immature and mature sample records and supplementary matrices.
- [Shao et al. (2025), DOI 10.1016/j.identj.2025.104622](https://doi.org/10.1016/j.identj.2025.104622): publication describing the 20-teeth-per-stage study and its RELB-associated osteogenic analyses.
