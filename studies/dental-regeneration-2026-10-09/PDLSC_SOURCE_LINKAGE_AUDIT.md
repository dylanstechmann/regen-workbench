# PDL maturity source linkage and descriptive marker plan

Audit date: 2026-10-10. This audit reviews source identity and analysis eligibility; no expression values were analyzed here. The associated fetch script is [fetch_pdls_source_linkage.py](fetch_pdls_source_linkage.py), with successful response hashes and failed access attempts in [pdls_source_linkage_receipt.json](pdls_source_linkage_receipt.json). Raw responses and `regen.record` receipts are retained under ignored local `data/`.

## What the sources establish

| Source | Established information | Linkage limit |
| --- | --- | --- |
| [GEO GSE306722](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE306722) and its [existing SOFT receipt](pdls_maturity_metadata_receipt.json) | PDL maturity study deposited by Xin Shao at Xi'an Jiaotong University; two GEO records, GSM9206804 and GSM9206805, with immature and mature labels. | The retrieved SOFT series has no PubMed ID and no individual tooth/donor map. |
| [Conference DOI 10.1016/j.identj.2025.104622](https://www.sciencedirect.com/science/article/pii/S002065392503905X) | CA2845, *Single-Cell Atlas Of Human Periodontal Ligament Stem Cells*, by Xin Shao, Liying Wang and Kun Qi, in *International Dental Journal* 75 Supplement 1, October 2025. The brief methods report 20 immature and 20 mature human teeth. | No accession or library-to-tooth crosswalk was recovered from the indexed publisher abstract. |
| [New journal article PMID 42785307](https://pubmed.ncbi.nlm.nih.gov/42785307/), [DOI 10.1016/j.stemcr.2026.103088](https://doi.org/10.1016/j.stemcr.2026.103088) | *Diminished RELB impairs osteogenesis in mature periodontal ligament stem cells*, *Stem Cell Reports*, first publication 2026-09-24; all six authors match the six GEO contributors in the retrieved raw SOFT, in order. | Its retrieved bibliographic metadata and abstract provide no explicit GSE306722 linkage or donor/pooling crosswalk. Full methods were not retrieved. |

**Classification:** The 2025 item is a conference abstract, inferred from its CA2845 identifier, brief structured abstract and placement in the supplement containing [2025 FDI World Dental Congress abstracts](https://www.sciencedirect.com/journal/international-dental-journal/vol/75/suppl/S1). Crossref calls it `journal-article`, but that generic registry type does not make it a full methods article; its publisher assertion is `simple-article`, compared with `article` for the 2026 record. [Publisher-deposited Crossref record](https://api.crossref.org/works/10.1016/j.identj.2025.104622).

The 2026 article is a strongly matching associated-study candidate: its abstract and the archive summary share the specific RELB, PDLSC-5 and SOD2 mechanism and immature/mature comparison, in addition to the exact ordered contributor match (Shao, Wu, Song, Gao, Qi, Wang). This is an inference from matching content, **not an explicit accession verification**. Neither the conference abstract nor the new article should be counted as an independent replication of the GEO study on this evidence. [PubMed record](https://pubmed.ncbi.nlm.nih.gov/42785307/), [BioProject record](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA1311975).

## Tooth counts, donors and pooling

The defensible wording is: **a matching conference abstract reports 20 teeth per developmental group; their exact relationship to the deposited libraries is unverified.** Teeth are not automatically unique donors, and 40 reported teeth are not 40 separately represented GEO samples.

The archive describes indexed libraries being combined for sequencing and expression/metadata merging within a batch. These operations do not establish whether tissue or cells from multiple donors were pooled before capture, how many capture libraries existed, or whether donor information survives in the matrices. GEO/BioSample and SRA experiment identifiers are archive identifiers rather than proof of independent biological replicates. A barcode suffix or a change in sequencing batch cannot recover a donor identity without an explicit crosswalk. [GEO sample GSM9206804](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM9206804), [GEO sample GSM9206805](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM9206805).

Eligibility remains descriptive within each deposited record. No donor-level variance, donor-held-out evaluation, stage-effect significance test or rejuvenation score is qualified. Root developmental maturity is a different comparison from age-acquired damage repair. An eventual publisher methods/supplement audit may clarify sample construction; it must not be replaced by an assumed pooling design.

## Retrieval boundaries

Actual `regen.http_bytes` fetches recovered Crossref metadata for both DOIs, EuropePMC core metadata for PMID 42785307, publisher API coredata for both papers, and a primary control-marker article's full-text XML. Each successful file has a SHA-256 and a `regen.record` provenance receipt. Publisher HTML and the normal Cell PDF route returned 403; the full-view publisher API attempt exhausted the helper's rate-limit retries with 429. The successful publisher API responses contain coredata only, not article bodies, and contain no GSE306722 literal.

Publisher coredata identifies the 2026 paper as open access under CC BY-NC-ND 4.0. EuropePMC currently lists no PMC copy and labels its DOI link subscription-required. Those metadata disagree; absence from EuropePMC is not evidence that the paper is paywalled. We did not bypass access controls or obtain the full methods. [Publisher API](https://api.elsevier.com/content/article/PII:S2213671126002997?httpAccept=text/xml), [EuropePMC core record](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:42785307%20AND%20SRC:MED&format=json&resultType=core).

## Frozen descriptive panel before native expression inspection

Retain all **33** symbols already used in the bulk exploratory [summarizer](summarize_ipspdl_rnaseq.py), in their existing order:

```text
POSTN COL1A1 COL1A2 COL3A1 COL12A1 COL14A1 ASPN
SCX TNMD MKX CILP DCN LUM BGN THY1 PDGFRA
ITGA11 VCAM1 FAP ALPL RUNX2 SP7 IBSP BGLAP
POU5F1 SOX2 NANOG LIN28A AMELX ENAM AMBN DSPP MMP20
```

Add these **12** control-context symbols in the order below, producing a 45-symbol panel. Table 6 of the primary integrated human-tooth atlas supplies the published annotation context. [Hermans et al. (2022), DOI 10.3389/fcell.2022.1021459](https://pmc.ncbi.nlm.nih.gov/articles/PMC9590651/).

| Descriptive control context | Fixed symbols |
| --- | --- |
| T-cell-associated expression | CD3D, CD3E |
| Myeloid-associated expression | LYZ, CSF1R |
| Endothelial-associated expression | PECAM1, CDH5 |
| Epithelial-associated expression | KRT14, ODAM |
| Glial/Schwann-associated expression | PLP1, SOX10 |
| Perivascular-associated expression | RGS5, KCNJ8 |

That source lists POSTN and COL12A1 in both PDL and dental-follicle panels, illustrating that matrix expression is not uniquely diagnostic of PDL. The added symbols provide competing expression contexts; they are not verified identities for these deposited cells. The source itself uses broader combinations than several of the pairs shown here. [Human-tooth atlas Table 6](https://pmc.ncbi.nlm.nih.gov/articles/PMC9590651/).

Before plotting: record this symbol order, the doc hash and code revision; preserve missing-feature entries; resolve symbols against exact feature IDs without silently combining ambiguous matches; and keep absent features distinct from zero expression. Describe feature prevalence and abundance within each archive record using a declared normalization. RNA-seq TPM and single-cell UMI/log-normalized abundance have different denominators and cannot be compared as equivalent absolute units. Any optional pattern comparison must state its transformation and assay limitations.

Do not select replacement markers after viewing favorable patterns, assign validated cell-type labels from a pair, infer functional ligament regeneration, or turn these panels into a biological-age score. Inspection can generate explicitly dated follow-up hypotheses without rewriting this frozen starting panel.

## Corrections to the earlier qualification

1. Replace the unqualified description of DOI 10.1016/j.identj.2025.104622 as an associated article with **matching conference abstract; explicit accession linkage unverified**.
2. Attribute the 20+20 count to that abstract as **teeth reported**, with library inclusion and unique-donor counts unresolved.
3. Add the 2026 *Stem Cell Reports* DOI/PMID as a newly identified, strongly matching source candidate, without claiming its full methods or data availability statement were read.
4. Keep the archive-level absence of donor mappings and descriptive eligibility intact. The source audit does not upgrade replication or validation status.
5. Preserve this audit and the prior metadata receipt as dated records. Correct current display/qualification wording through an explicit amendment rather than silently changing what the original retrieval returned.
