# Dental organoid metadata qualification

The AI assistant retrieved two exact GEO SOFT metadata families through
`regen.http_bytes` and `regen.record`. [Retrieval receipts](geo_metadata_receipt.json)
retain URLs, timestamps and response hashes; [the qualification report](geo_qualification.json)
retains sample accessions, declared characteristics and source-linked BioSample/SRA
records. Raw metadata stay in ignored literature storage. This metadata-only
intake did not analyze FASTQ data. The later count-table analysis is documented
separately in [AMELOBLAST_EXPRESSION.md](AMELOBLAST_EXPRESSION.md).

| Dataset | Retrieved scope | Comparison limitation |
|---|---|---|
| [GSE307437](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE307437) | Six RNA sample records; WTC-11 declared throughout; two source-labeled replicates per condition | WT untreated, WT treated and DLX3-KO treated; untreated KO is absent from this source sample set |
| [GSE184749](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE184749) | Nineteen records mixing fetal tissue and iPSC samples, and single-cell and bulk sequencing | Pooled fetal material and shared cell-line provenance do not establish donor-independent validation |

GSE307437's source records provide the following sample and SRA links:

| GEO sample | Source condition label | BioSample | SRA experiment |
|---|---|---|---|
| [GSM9224208](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM9224208) | WT isAM, untreated, replicate 1 | [SAMN51222985](https://www.ncbi.nlm.nih.gov/biosample/SAMN51222985) | [SRX30400796](https://www.ncbi.nlm.nih.gov/sra?term=SRX30400796) |
| [GSM9224209](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM9224209) | WT isAM, untreated, replicate 2 | [SAMN51222984](https://www.ncbi.nlm.nih.gov/biosample/SAMN51222984) | [SRX30400797](https://www.ncbi.nlm.nih.gov/sra?term=SRX30400797) |
| [GSM9224210](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM9224210) | WT isAM, C3-DLL4, replicate 1 | [SAMN51222983](https://www.ncbi.nlm.nih.gov/biosample/SAMN51222983) | [SRX30400798](https://www.ncbi.nlm.nih.gov/sra?term=SRX30400798) |
| [GSM9224211](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM9224211) | WT isAM, C3-DLL4, replicate 2 | [SAMN51222982](https://www.ncbi.nlm.nih.gov/biosample/SAMN51222982) | [SRX30400799](https://www.ncbi.nlm.nih.gov/sra?term=SRX30400799) |
| [GSM9224212](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM9224212) | DLX3-KO isAM, C3-DLL4, replicate 1 | [SAMN51222981](https://www.ncbi.nlm.nih.gov/biosample/SAMN51222981) | [SRX30400800](https://www.ncbi.nlm.nih.gov/sra?term=SRX30400800) |
| [GSM9224213](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM9224213) | DLX3-KO isAM, C3-DLL4, replicate 2 | [SAMN51222980](https://www.ncbi.nlm.nih.gov/biosample/SAMN51222980) | [SRX30400801](https://www.ncbi.nlm.nih.gov/sra?term=SRX30400801) |

The GEO record labels the cell background WTC-11 throughout and describes
replicates 1/2 within each condition as biological replicates. The article
separately reports two edited clones (KO-10 and KO-13), but the GEO sample
records do not map either clone to GSM9224212 or GSM9224213, nor name separate
differentiation batches. Thus the sample/SRA chain is traceable, while clone and
culture independence remain unresolved.

For GSE307437, WT treated versus WT untreated is a candidate within-background
molecular contrast. KO treated versus WT treated is a candidate genotype contrast
under that condition, with clone effects unresolved. A complete genotype-by-
treatment interaction cannot be estimated from these three conditions alone.
Replicate labels do not qualify culture-batch or donor independence. This
metadata-only report does not validate the raw-count CSV's columns or integrity;
the later count-table note documents the column-to-sample source-label mapping.
Reuse rights remain unqualified here. Transcript changes are not enamel
mechanical function.

For GSE184749, GSM5596824 has an incisor sample title and a molar tissue
characteristic. The report preserves both and flags the conflict; it assigns no
corrected label. The series describes pooled fetal preparations. Cells and
libraries cannot be counted as independent donors. WTC-11 labels in both series
also require lineage/clone review before either series is called an independent
external test. No independent-donor count or held-out eligibility is supplied.

The next useful inputs are independent culture and clone records,
pooling/donor mappings, a source clarification for the tissue label and
documented reuse terms. Their absence in this intake means unknown, rather than
proof they were never recorded by the investigators.

Reproduce metadata retrieval or recheck its cached snapshot:

```sh
python studies/dental-regeneration-2026-10-09/fetch_geo_metadata.py
python studies/dental-regeneration-2026-10-09/fetch_geo_metadata.py --summarize-cached
```

The cache path checks both response and parsed-metadata hashes and reparses the
SOFT family. The new organoid campaign starter retains these comparison limits;
it is an editable research hypothesis, not a performed expression analysis.

The metadata tests check series/sample identity, duplicate refusal, preservation
of BioSample/SRA relations, exclusion of table values, unresolved source
conflicts and independence limits. The latest full local suite passed 388 tests;
29 platform/optional tests were skipped on Windows. The live API exposes three
organoid starters, including this comparison, and its Experiments endpoint
remains healthy. All saved workspace content and five notes were unchanged after
reload. The separate long-lived `workbench` service was not running, so its
`regen doctor` command could not execute; no doctor-pass or biological-validation
claim is made.
