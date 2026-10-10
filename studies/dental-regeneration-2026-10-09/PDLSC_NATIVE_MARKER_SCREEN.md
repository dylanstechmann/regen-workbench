# Native PDL fixed-marker descriptive screen

Run date/time (UTC): 2026-10-10T19:55:59.780611+00:00.

The two deposited GSE306722 records contain matrix-associated expression and several competing control contexts. SCX and TNMD are detectable in a small fraction of archived barcodes. These summaries describe the deposited mixtures; they do not establish cell identities, maturation, rejuvenation or functional periodontal regeneration.

## Frozen inputs and eligibility

The analysis uses the exact 45 symbols in [native_marker_panel.json](native_marker_panel.json), frozen before expression inspection: the existing 33 bulk markers plus 12 source-backed control-context markers. The source selection and publication-linkage limits are in [PDLSC_SOURCE_LINKAGE_AUDIT.md](PDLSC_SOURCE_LINKAGE_AUDIT.md). All 45 symbols map uniquely to Gene Expression features in each deposited record. Ten duplicated symbols elsewhere in the feature file are not silently summed. All 36,601 features in each record have the Gene Expression type.

[pdls_maturity_matrix_receipt.json](pdls_maturity_matrix_receipt.json) qualifies file integrity and positive integer numeric form. It does not establish raw UMI lineage or the exact processing stage. There is one GEO record per developmental source label, with no cell-to-donor map; barcodes are not independent biological replicates. The 59 barcode strings shared between records are kept distinct by prefixing each with its GEO sample accession.

## Measures and implemented sensitivity screen

Detection is the fraction of selected barcodes with a positive deposited entry for the uniquely mapped feature. The abundance measure is the average, over selected barcodes, of the natural logarithm ln(1 + 10,000 × feature entry / total Gene Expression entries in that barcode). Each barcode is normalized before logging and averaging. These are deposited-entry cp10k units, not verified raw UMI units and not bulk RNA-seq TPM.

The all-barcode analysis includes every deposited barcode. The implemented sensitivity screen retains barcodes with at least 200 positive Gene Expression features and a mitochondrial entry fraction no greater than 10%, based on the source-described cutoffs. Mitochondrial features are the 13 Gene Expression rows whose symbols begin MT-. This screen does not reproduce source regression, clustering, tissue pooling or doublet removal.

Missing features, ambiguous symbols and non-Gene Expression matches have undefined marker metrics. A uniquely mapped feature with zero entries remains measured zero. Zero-total barcodes have undefined normalized abundance and are excluded from the sensitivity screen; none occur in this run. An empty selected subset stays undefined rather than becoming zero.

| GEO record / source label | All barcodes | Retained sensitivity | Excluded union | <200 features | >10% MT | Both exclusions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GSM9206804 / immature | 12,769 | 11,852 | 917 | 127 | 907 | 117 |
| GSM9206805 / mature | 12,993 | 11,819 | 1,174 | 75 | 1,148 | 49 |

The low-feature and high-mitochondrial counts overlap; adding them would overstate exclusions. The source labels identify archive records. No stage-effect significance test, donor contrast or cell-type proportion estimate is performed.

## Complete fixed-panel results

Each table describes one archive record. Detection cells are detected barcode counts followed by their percentage of that table's screen denominator. Abundance columns are mean ln(1 + deposited-entry cp10k). The screen results are a sensitivity check on these supplied values, not proof that retained barcodes are validated cells. Table order follows the frozen panel.

### GSM9206804 — source label immature

Denominators: all 12,769; sensitivity 11,852.

| Symbol | Detected all | Detected sensitivity | Mean ln all | Mean ln sensitivity |
| --- | ---: | ---: | ---: | ---: |
| POSTN | 3,115 (24.40%) | 3,027 (25.54%) | 0.6120 | 0.6401 |
| COL1A1 | 5,174 (40.52%) | 4,974 (41.97%) | 1.3596 | 1.4140 |
| COL1A2 | 5,280 (41.35%) | 5,074 (42.81%) | 1.3358 | 1.3907 |
| COL3A1 | 5,259 (41.19%) | 5,085 (42.90%) | 1.3153 | 1.3769 |
| COL12A1 | 3,066 (24.01%) | 2,980 (25.14%) | 0.4948 | 0.5161 |
| COL14A1 | 2,848 (22.30%) | 2,807 (23.68%) | 0.4305 | 0.4567 |
| ASPN | 1,949 (15.26%) | 1,917 (16.17%) | 0.3197 | 0.3381 |
| SCX | 421 (3.30%) | 413 (3.48%) | 0.0352 | 0.0369 |
| TNMD | 37 (0.29%) | 37 (0.31%) | 0.0029 | 0.0032 |
| MKX | 410 (3.21%) | 408 (3.44%) | 0.0327 | 0.0348 |
| CILP | 25 (0.20%) | 25 (0.21%) | 0.0017 | 0.0019 |
| DCN | 4,128 (32.33%) | 4,029 (33.99%) | 0.9590 | 1.0120 |
| LUM | 3,799 (29.75%) | 3,703 (31.24%) | 0.8857 | 0.9346 |
| BGN | 4,023 (31.51%) | 3,940 (33.24%) | 0.5489 | 0.5775 |
| THY1 | 3,713 (29.08%) | 3,634 (30.66%) | 0.5722 | 0.6034 |
| PDGFRA | 2,060 (16.13%) | 2,020 (17.04%) | 0.2461 | 0.2583 |
| ITGA11 | 707 (5.54%) | 695 (5.86%) | 0.0478 | 0.0493 |
| VCAM1 | 2,105 (16.49%) | 2,046 (17.26%) | 0.2229 | 0.2304 |
| FAP | 1,815 (14.21%) | 1,757 (14.82%) | 0.1756 | 0.1811 |
| ALPL | 1,646 (12.89%) | 1,622 (13.69%) | 0.1906 | 0.2014 |
| RUNX2 | 2,280 (17.86%) | 2,246 (18.95%) | 0.2226 | 0.2339 |
| SP7 | 604 (4.73%) | 599 (5.05%) | 0.0540 | 0.0573 |
| IBSP | 611 (4.79%) | 590 (4.98%) | 0.1161 | 0.1204 |
| BGLAP | 379 (2.97%) | 374 (3.16%) | 0.0382 | 0.0404 |
| POU5F1 | 15 (0.12%) | 15 (0.13%) | 0.0013 | 0.0014 |
| SOX2 | 109 (0.85%) | 107 (0.90%) | 0.0144 | 0.0152 |
| NANOG | 25 (0.20%) | 23 (0.19%) | 0.0020 | 0.0018 |
| LIN28A | 4 (0.03%) | 4 (0.03%) | 0.0002 | 0.0002 |
| AMELX | 0 (0.00%) | 0 (0.00%) | 0.0000 | 0.0000 |
| ENAM | 0 (0.00%) | 0 (0.00%) | 0.0000 | 0.0000 |
| AMBN | 7 (0.05%) | 7 (0.06%) | 0.0007 | 0.0008 |
| DSPP | 2 (0.02%) | 2 (0.02%) | 0.0001 | 0.0001 |
| MMP20 | 1 (0.01%) | 1 (0.01%) | 0.0001 | 0.0001 |
| CD3D | 1,526 (11.95%) | 1,506 (12.71%) | 0.2577 | 0.2737 |
| CD3E | 1,430 (11.20%) | 1,406 (11.86%) | 0.2081 | 0.2198 |
| LYZ | 1,828 (14.32%) | 1,722 (14.53%) | 0.3964 | 0.4044 |
| CSF1R | 1,030 (8.07%) | 969 (8.18%) | 0.1171 | 0.1162 |
| PECAM1 | 3,219 (25.21%) | 3,007 (25.37%) | 0.4901 | 0.4856 |
| CDH5 | 1,688 (13.22%) | 1,571 (13.26%) | 0.2080 | 0.2038 |
| KRT14 | 147 (1.15%) | 132 (1.11%) | 0.0251 | 0.0237 |
| ODAM | 9 (0.07%) | 9 (0.08%) | 0.0008 | 0.0008 |
| PLP1 | 338 (2.65%) | 325 (2.74%) | 0.0586 | 0.0607 |
| SOX10 | 161 (1.26%) | 155 (1.31%) | 0.0202 | 0.0209 |
| RGS5 | 1,780 (13.94%) | 1,739 (14.67%) | 0.3918 | 0.4120 |
| KCNJ8 | 706 (5.53%) | 698 (5.89%) | 0.0790 | 0.0839 |

### GSM9206805 — source label mature

Denominators: all 12,993; sensitivity 11,819.

| Symbol | Detected all | Detected sensitivity | Mean ln all | Mean ln sensitivity |
| --- | ---: | ---: | ---: | ---: |
| POSTN | 6,406 (49.30%) | 6,045 (51.15%) | 1.7343 | 1.8069 |
| COL1A1 | 8,747 (67.32%) | 8,118 (68.69%) | 2.7244 | 2.8018 |
| COL1A2 | 8,422 (64.82%) | 7,837 (66.31%) | 2.5377 | 2.6192 |
| COL3A1 | 8,405 (64.69%) | 7,849 (66.41%) | 2.5315 | 2.6155 |
| COL12A1 | 4,844 (37.28%) | 4,633 (39.20%) | 0.7979 | 0.8320 |
| COL14A1 | 3,657 (28.15%) | 3,429 (29.01%) | 0.5868 | 0.5997 |
| ASPN | 5,025 (38.67%) | 4,820 (40.78%) | 1.1435 | 1.2095 |
| SCX | 287 (2.21%) | 276 (2.34%) | 0.0239 | 0.0248 |
| TNMD | 151 (1.16%) | 146 (1.24%) | 0.0110 | 0.0116 |
| MKX | 718 (5.53%) | 692 (5.85%) | 0.0579 | 0.0606 |
| CILP | 100 (0.77%) | 98 (0.83%) | 0.0075 | 0.0080 |
| DCN | 6,798 (52.32%) | 6,472 (54.76%) | 1.6974 | 1.7866 |
| LUM | 6,039 (46.48%) | 5,756 (48.70%) | 1.5477 | 1.6296 |
| BGN | 5,769 (44.40%) | 5,480 (46.37%) | 0.8088 | 0.8379 |
| THY1 | 6,160 (47.41%) | 5,921 (50.10%) | 0.9484 | 0.9959 |
| PDGFRA | 2,446 (18.83%) | 2,360 (19.97%) | 0.2447 | 0.2560 |
| ITGA11 | 362 (2.79%) | 344 (2.91%) | 0.0281 | 0.0285 |
| VCAM1 | 1,736 (13.36%) | 1,658 (14.03%) | 0.1899 | 0.1954 |
| FAP | 1,469 (11.31%) | 1,407 (11.90%) | 0.1267 | 0.1311 |
| ALPL | 4,115 (31.67%) | 3,960 (33.51%) | 0.6103 | 0.6409 |
| RUNX2 | 3,806 (29.29%) | 3,639 (30.79%) | 0.4323 | 0.4483 |
| SP7 | 1,965 (15.12%) | 1,896 (16.04%) | 0.1797 | 0.1883 |
| IBSP | 250 (1.92%) | 227 (1.92%) | 0.0512 | 0.0499 |
| BGLAP | 609 (4.69%) | 581 (4.92%) | 0.0709 | 0.0725 |
| POU5F1 | 9 (0.07%) | 7 (0.06%) | 0.0009 | 0.0007 |
| SOX2 | 32 (0.25%) | 29 (0.25%) | 0.0036 | 0.0037 |
| NANOG | 48 (0.37%) | 42 (0.36%) | 0.0042 | 0.0037 |
| LIN28A | 3 (0.02%) | 3 (0.03%) | 0.0003 | 0.0003 |
| AMELX | 0 (0.00%) | 0 (0.00%) | 0.0000 | 0.0000 |
| ENAM | 0 (0.00%) | 0 (0.00%) | 0.0000 | 0.0000 |
| AMBN | 0 (0.00%) | 0 (0.00%) | 0.0000 | 0.0000 |
| DSPP | 1 (0.01%) | 1 (0.01%) | 0.0001 | 0.0001 |
| MMP20 | 0 (0.00%) | 0 (0.00%) | 0.0000 | 0.0000 |
| CD3D | 1,438 (11.07%) | 1,386 (11.73%) | 0.2477 | 0.2621 |
| CD3E | 1,154 (8.88%) | 1,118 (9.46%) | 0.1784 | 0.1887 |
| LYZ | 413 (3.18%) | 340 (2.88%) | 0.0886 | 0.0824 |
| CSF1R | 212 (1.63%) | 154 (1.30%) | 0.0246 | 0.0188 |
| PECAM1 | 2,742 (21.10%) | 2,521 (21.33%) | 0.4485 | 0.4479 |
| CDH5 | 2,006 (15.44%) | 1,880 (15.91%) | 0.2714 | 0.2747 |
| KRT14 | 135 (1.04%) | 105 (0.89%) | 0.0299 | 0.0250 |
| ODAM | 36 (0.28%) | 33 (0.28%) | 0.0047 | 0.0048 |
| PLP1 | 211 (1.62%) | 207 (1.75%) | 0.0215 | 0.0230 |
| SOX10 | 16 (0.12%) | 16 (0.14%) | 0.0025 | 0.0027 |
| RGS5 | 2,617 (20.14%) | 2,356 (19.93%) | 0.5905 | 0.5798 |
| KCNJ8 | 1,132 (8.71%) | 1,072 (9.07%) | 0.1476 | 0.1524 |

## Interpretation and reproducibility

POSTN, collagen and proteoglycan expression supports inspecting matrix-associated patterns in the native tissue mixtures. The endothelial-, immune- and perivascular-associated control genes also have detectable expression. Detection of a control gene does not identify a cell type or establish whether different markers occur in the same cells. The full tables preserve the low and zero markers.

Sparse SCX/TNMD detection in these tissue mixtures means that a universal identity or maturity cutoff cannot be inferred from their low bulk expression alone. Cell-state mixture, capture sensitivity, assay differences and unresolved preprocessing must be considered before comparison with cultured iPS-PDL. No single-cell cp10k value is treated as equivalent to bulk gene-summed TPM, and this analysis generates no cross-assay identity score.

The next useful test is a separately frozen within-record coexpression exploration that checks which matrix-associated markers occur together and which control contexts accompany them, retaining ambiguous/dropout cases. It would remain descriptive until sample construction and donor mapping are resolved.

Run from the repository root with Docker:

```powershell
$nativeAnalysisRevision = git rev-parse HEAD
docker compose exec workbench python /lab/workbench/studies/dental-regeneration-2026-10-09/summarize_native_pdls_markers.py --code-revision $nativeAnalysisRevision
```

Local generated artifacts remain ignored under `data/structures/pdls-maturity/summary/`: `native_marker_summary.tsv` (180 rows), `native_barcode_screen.tsv` (25,762 rows), `native_marker_contexts.png`, the exact panel copy and `summary.json`. The figure uses separate color scales for detection and abundance, with missing/ambiguous values shown as gray. The computational receipt binds the script, frozen panel, source audit, upstream matrix audit, six input hashes and output hashes; its `regen.record` provenance receipt remains in ignored `data/provenance/`.

- Panel SHA-256: `9994a0e3d401eac99ed3a1a6f743e1a62f8242d8bb594dfb6517dd659b66a2f2`.
- Analysis script SHA-256: `30095440d3dd66da810a16297342f2b57c79bfc51d040647f574289d97e3854a`.
- Matrix audit SHA-256: `1bf91fc46d885afb678f5b8590b15ef7dec487cadfc3605198164d943966040f`.
- Source linkage audit SHA-256: `ff39eec989005ad92a977a6177718fd02b6d38c2ae5f1af222a9c238f5e54b66`.
- Checkout revision at run: `1f66902db01a6579945803671170373849329b8f`; the script hash binds the analysis code pending commit.

Focused numerical and input-integrity tests cover threshold boundaries, overlapping exclusions, protein-count denominators, missing/ambiguous/zero distinctions, empty subsets and changed input/panel rejection. These are software checks rather than biological validation.
