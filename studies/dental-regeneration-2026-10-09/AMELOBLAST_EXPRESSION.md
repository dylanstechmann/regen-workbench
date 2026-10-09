# Deposited ameloblast-organoid counts: descriptive comparison

The exact advertised [GSE307437 count table](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE307437)
was acquired through Regen Workbench. The [receipt](count_receipt.json) records
the actual response hash. It contains **41,129 unique gene identifiers and six
libraries**, all with nonnegative integer values and matching row widths.
Total assigned counts range from 77,348,174 to 96,403,727; nonzero gene rows
range from 25,343 to 26,678. These are table totals, not sequencing read depth,
independent cells or donor counts.

The count-column labels correspond to the six source sample titles in the
[metadata intake](GEO_QUALIFICATION.md). That mapping is an explicit source-label
interpretation, not molecular authentication. Independent donor, clone and
culture-batch identities remain unknown. Two source-labeled biological
replicates per group do not supply a donor-held-out validation cohort.

## Operation performed

For each library, CPM = deposited gene count / sum of all deposited gene counts
in that library × 1,000,000. The study script supplies these **linear CPM**
values to the existing `regen expression-contrast` method. Raw counts are never
passed directly to that method. This simple total-count normalization is
composition-sensitive; it is not DESeq2, batch correction, per-cell abundance
or adjustment for differing RNA content/cell mixtures.

Two comparisons use two libraries per group:

- WT treated relative to WT untreated: a within-background treatment contrast.
- Knockout treated relative to WT treated: a genotype-under-treatment contrast,
  with clone and batch effects unresolved.

Untreated knockout libraries are absent. There is no full genotype×treatment
interaction estimate. No p values, confidence intervals or differential-
expression significance calls are computed. The method's leave-one-library-out
range is a sensitivity diagnostic, not a confidence interval; its
`direction_stable` flag refers only to the four supplied libraries.

Before running, the script declared an eleven-gene inspection panel: AMELX,
AMBN, ENAM, MMP20, KLK4, DLX3, SP6, ALPL, KRT14, KRT19 and SOX2. This spans
enamel-associated, regulatory and epithelial/context markers. It is not an
exhaustive gene set, a maturity score or a panel selected by the largest effect.
The [summary](ameloblast_expression_summary.json) retains every panel entry,
library QC, missing-identifier checks and two pseudocount settings.

## What the deposited table shows

Rounded means and log2 ratios below describe CPM library means. WT treatment
uses treated/untreated; genotype uses knockout-treated/WT-treated. The added
pseudocount is in CPM units.

| Gene | WT untreated mean CPM | WT treated mean CPM | Knockout treated mean CPM | WT treatment log2 ratio, pc=1 | Genotype log2 ratio, pc=1 |
|---|---:|---:|---:|---:|---:|
| DLX3 | 8.266 | 18.772 | 1.768 | 1.093 | −2.837 |
| SP6 | 14.090 | 44.534 | 1.712 | 1.593 | −4.070 |
| SOX2 | 357.625 | 2.528 | 489.670 | −6.668 | 7.120 |
| MMP20 | 0.012 | 0.749 | 0.036 | 0.789 | −0.756 |
| ENAM | 0.000 | 0.000 | 0.023 | 0.000 | 0.032 |

DLX3/SP6 and the epithelial/context pattern are compatible with a molecular
state shift in these particular libraries. They do not certify functional
enamel production. Several enamel-associated rows are sparse: ENAM has zero
deposited counts in both WT groups, while AMELX/AMBN are near zero. A zero in
this table is not proof the biological gene is absent or that another assay
in the paper failed.

Low-count effect magnitude depends strongly on the pseudocount. For example,
WT MMP20's log2 ratio is 2.920 at 0.1 CPM versus 0.789 at 1 CPM, and KLK4's is
0.920 versus 0.148. AMBN and KRT14 do not retain treatment direction under every
single-library omission. The panel contains mixed responses, rather than
uniform upregulation of enamel markers.

The next interpretable step needs culture/clone/batch qualification and an
appropriate raw-count statistical model, together with the source's actual
assay and differentiation-stage context. Tooth-site architecture, bonding,
mechanics, pulp and periodontal integration remain separate evidence domains.
Dataset reuse licensing is not qualified by this analysis.

## Reproduce

Run from the workbench root in the existing scientific environment:

```sh
python studies/dental-regeneration-2026-10-09/fetch_geo_metadata.py
python studies/dental-regeneration-2026-10-09/analyze_ameloblast_counts.py --fetch --out data/expression-dental-cpm-rerun
```

Without `--fetch`, the script verifies the cached count and metadata hashes.
The output directory must be new. Raw counts, all-gene contrasts and detailed
method manifests remain private under ignored `data/`; only the selected
derived panel summary and retrieval receipts are tracked. Each of the four
method runs retains input hashes, method implementation hash, parameters and
Python version. The public summary links their actual manifest hashes and the
study-script hash. Dates and response hashes can change on a new retrieval.

This AI-assisted analysis is computational exploration of a source-deposited
table, not an experiment or owner-reviewed biological result.
