# Dental organoid metadata qualification

The AI assistant retrieved two exact GEO SOFT metadata families, through
`regen.http_bytes` and `regen.record`. [Retrieval receipts](geo_metadata_receipt.json)
retain URLs, timestamps and response hashes; [the qualification report](geo_qualification.json)
retains sample accessions and declared characteristics. Raw metadata stay in
ignored literature storage. No RNA count matrix or FASTQ was acquired or analyzed.

| Dataset | Retrieved scope | Comparison limitation |
|---|---|---|
| [GSE307437](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE307437) | Six RNA sample records; WTC-11 declared throughout; two source-labeled replicates per condition | WT untreated, WT treated and DLX3-KO treated; untreated KO is absent from this source sample set |
| [GSE184749](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE184749) | Nineteen records mixing fetal tissue and iPSC samples, and single-cell and bulk sequencing | Pooled fetal material and shared cell-line provenance do not establish donor-independent validation |

For GSE307437, WT treated versus WT untreated is a candidate within-background
molecular contrast. KO treated versus WT treated is a candidate genotype contrast
under that condition, with clone effects unresolved. A complete genotype-by-
treatment interaction cannot be estimated from these three conditions alone.
Replicate labels do not qualify culture-batch or donor independence. The source
advertises a raw-count CSV, but column mapping, count integrity and reuse rights
remain unqualified here. Transcript changes are not enamel mechanical function.

For GSE184749, GSM5596824 has an incisor sample title and a molar tissue
characteristic. The report preserves both and flags the conflict; it assigns no
corrected label. The series describes pooled fetal preparations. Cells and
libraries cannot be counted as independent donors. WTC-11 labels in both series
also require lineage/clone review before either series is called an independent
external test. No independent-donor count or held-out eligibility is supplied.

The next useful inputs are sample-to-library/count-column mappings, independent
culture and clone records, pooling/donor mappings, a source clarification for the
tissue label and documented reuse terms. Their absence in this intake means
unknown, rather than proof they were never recorded by the investigators.

Reproduce metadata retrieval or recheck its cached snapshot:

```sh
python studies/dental-regeneration-2026-10-09/fetch_geo_metadata.py
python studies/dental-regeneration-2026-10-09/fetch_geo_metadata.py --summarize-cached
```

The cache path checks both response and parsed-metadata hashes and reparses the
SOFT family. The new organoid campaign starter retains these comparison limits;
it is an editable research hypothesis, not a performed expression analysis.

Docker `dev` completed 375 unit tests with four optional skips. The metadata
tests check series/sample identity, duplicate refusal, exclusion of table values,
unresolved source conflicts and preserved independence limits. New intake code
and tests passed Ruff. The live API exposes three organoid starters, including
this comparison, and its Experiments endpoint remains healthy. All saved
workspace content and five notes were unchanged after reload. The separate
long-lived `workbench` service was not running, so its `regen doctor` command
could not execute; no doctor-pass or biological-validation claim is made.
