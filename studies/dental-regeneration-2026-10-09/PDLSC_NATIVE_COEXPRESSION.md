# Native PDL within-record marker co-detection

Analysis run (UTC): 2026-10-11T06:26:01.850344+00:00.

## Question and fixed rules

Do PDL-associated low-abundance markers occur in the same deposited barcodes as a multi-marker extracellular-matrix pattern, and how often do competing vascular/perivascular or immune marker contexts co-occur? This is a descriptive follow-up to the fixed 45-symbol native screen, not a cell annotation.

A matrix-anchor barcode has positive entries for at least two of POSTN, COL1A1, DCN and COL12A1; a stricter three-of-four rule is also reported. Ligament-associated targets are SCX, TNMD, MKX, CILP and ITGA11. A positive entry is evaluated at thresholds of at least 1 and at least 2 deposited units. Vascular, perivascular and immune contexts are positive when any listed fixed-panel marker reaches that same threshold. The two archive records and the all-barcode/source-rule screens remain separate.

The deposited matrices have integer numeric form, but their raw-UMI lineage and exact preprocessing stage remain unresolved. Barcode-level co-detection can reflect capture depth, ambient signal, multiplets, processing and true biological co-expression. The two GEO records lack a cell-to-library/tooth/donor map; barcodes are descriptive observations, not independent donor replicates. The source labels are developmental root-maturity labels, not chronological aging or rejuvenation.

## Key results

The following table uses the all-barcode screen and entry threshold ≥1. Fractions use only barcodes meeting the stated matrix-anchor rule.

| Record / source label | Anchor rule | Anchor barcodes | Gene | Joint barcodes | Gene positive within anchor |
| --- | --- | ---: | --- | ---: | ---: |
| GSM9206804 (immature) | at_least_2_of_4 | 4099 | SCX | 252 | 6.15% |
| GSM9206804 (immature) | at_least_2_of_4 | 4099 | TNMD | 36 | 0.88% |
| GSM9206804 (immature) | at_least_2_of_4 | 4099 | MKX | 394 | 9.61% |
| GSM9206804 (immature) | at_least_2_of_4 | 4099 | CILP | 22 | 0.54% |
| GSM9206804 (immature) | at_least_2_of_4 | 4099 | ITGA11 | 692 | 16.88% |
| GSM9206804 (immature) | at_least_3_of_4 | 3029 | SCX | 232 | 7.66% |
| GSM9206804 (immature) | at_least_3_of_4 | 3029 | TNMD | 33 | 1.09% |
| GSM9206804 (immature) | at_least_3_of_4 | 3029 | MKX | 357 | 11.79% |
| GSM9206804 (immature) | at_least_3_of_4 | 3029 | CILP | 19 | 0.63% |
| GSM9206804 (immature) | at_least_3_of_4 | 3029 | ITGA11 | 680 | 22.45% |
| GSM9206805 (mature) | at_least_2_of_4 | 7228 | SCX | 232 | 3.21% |
| GSM9206805 (mature) | at_least_2_of_4 | 7228 | TNMD | 148 | 2.05% |
| GSM9206805 (mature) | at_least_2_of_4 | 7228 | MKX | 710 | 9.82% |
| GSM9206805 (mature) | at_least_2_of_4 | 7228 | CILP | 97 | 1.34% |
| GSM9206805 (mature) | at_least_2_of_4 | 7228 | ITGA11 | 351 | 4.86% |
| GSM9206805 (mature) | at_least_3_of_4 | 5603 | SCX | 217 | 3.87% |
| GSM9206805 (mature) | at_least_3_of_4 | 5603 | TNMD | 143 | 2.55% |
| GSM9206805 (mature) | at_least_3_of_4 | 5603 | MKX | 704 | 12.56% |
| GSM9206805 (mature) | at_least_3_of_4 | 5603 | CILP | 97 | 1.73% |
| GSM9206805 (mature) | at_least_3_of_4 | 5603 | ITGA11 | 335 | 5.98% |

A compact combination check asks how often the same matrix-anchor barcode contains multiple ligament-associated signals. These are raw co-detection counts at threshold ≥1; the second threshold and cell-inclusion screen are retained in the machine-readable table.

| Record / source label | Screen | Entry threshold | Anchor barcodes | ≥1 of 5 genes | ≥2 of 5 | ≥3 of 5 | SCX+TNMD+MKX |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GSM9206804 (immature) | all_barcodes | ≥1 | 4099 | 1125 | 247 | 24 | 0 |
| GSM9206804 (immature) | all_barcodes | ≥2 | 3390 | 396 | 40 | 1 | 0 |
| GSM9206804 (immature) | source_rule_sensitivity | ≥1 | 4007 | 1113 | 247 | 24 | 0 |
| GSM9206804 (immature) | source_rule_sensitivity | ≥2 | 3339 | 394 | 40 | 1 | 0 |
| GSM9206805 (mature) | all_barcodes | ≥1 | 7228 | 1326 | 195 | 17 | 3 |
| GSM9206805 (mature) | all_barcodes | ≥2 | 6155 | 234 | 5 | 0 | 0 |
| GSM9206805 (mature) | source_rule_sensitivity | ≥1 | 6833 | 1281 | 189 | 16 | 3 |
| GSM9206805 (mature) | source_rule_sensitivity | ≥2 | 5896 | 227 | 5 | 0 | 0 |

## Competing marker contexts

Context co-detection tables are retained in `pdls_native_coexpression_contexts.tsv`. A context marker in the same barcode as a matrix anchor is not by itself proof of a distinct cell type or contamination; the deposited processing and cell labels do not support that conclusion.

## Interpretation and limits

This calculation answers whether fixed-panel signals are observed together at the barcode level. It cannot establish organized PDL tissue, oriented fibers inserting at cementum and alveolar bone, physiological tooth mobility, load transfer, avoidance of ankylosis, or durable function. It also cannot assign a maturity effect because the archive has one group-level record per source label and no donor-level map. Native deposited-entry cp10k remains distinct from bulk TPM.

The [co-detection figure](derived/pdls-native-coexpression/pdls_native_coexpression.png), all pairwise matrix/ligament-marker counts, conditional fractions, context summaries and output hashes are committed beside this report. The raw matrix inputs remain local; their SHA-256 bindings are checked against the committed source receipt before analysis.

Reproduce from the repository root with the running workbench container:

```powershell
$analysisRevision = git rev-parse HEAD
docker compose exec -T workbench python /lab/workbench/studies/dental-regeneration-2026-10-09/analyze_pdls_native_coexpression.py --code-revision $analysisRevision
```

Source script SHA-256: `26b8c6ab7bb667634511869f705c30dc9ebb930b89ac325d2e827e549ca45493`.
Frozen panel SHA-256: `9994a0e3d401eac99ed3a1a6f743e1a62f8242d8bb594dfb6517dd659b66a2f2`.
Matrix-audit receipt SHA-256: `1bf91fc46d885afb678f5b8590b15ef7dec487cadfc3605198164d943966040f`.
