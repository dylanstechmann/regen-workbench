# Human native-PDL maturity matrices: input audit

## Result

The six official supplementary files for [GEO GSE306722](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE306722) were downloaded on 2026-10-10 and passed gzip integrity and sparse-structure checks. Both matrices contain nonnegative integer values and can be loaded for a source-scoped descriptive native-PDL reference. Their numeric form is compatible with counts; their exact raw-UMI and preprocessing lineage remains unqualified. Independent donor inference remains unsupported by the deposited cell labels and metadata.

| Property | Immature, GSM9206804 | Mature, GSM9206805 |
|---|---:|---:|
| Feature rows | 36,601 | 36,601 |
| Barcode columns | 12,769 | 12,993 |
| Declared and actual stored entries | 25,909,721 | 22,945,968 |
| Unique stored coordinates | 25,909,721 | 22,945,968 |
| Stored-coordinate density | 5.544% | 4.825% |
| Minimum / maximum stored value | 1 / 25,225 | 1 / 22,544 |
| Barcode entry-sum median (range) | 4,172 (500–63,030) | 3,379 (500–51,360) |
| Positive features per barcode, median (range) | 1,781 (27–8,315) | 1,578 (15–6,402) |
| Barcodes with fewer than 200 positive features | 127 | 75 |
| Features with no positive entries | 8,942 | 9,046 |

The MatrixMarket headers declare `matrix coordinate integer general`, and the parsed values have `int64` dtype. Dimensions match feature rows and barcode columns. Declared entry counts match all parsed stored entries; all sparse indices are within bounds. Both matrices have **zero** duplicate-coordinate groups, repeated-coordinate entries, explicit zeros, negative values, fractional values and nonfinite values. Neither has a zero-total barcode.

Both feature files contain three fields per row, with 36,601 unique feature identifiers and the feature type `Gene Expression` throughout. Their feature identifiers appear in the same order. Gene names are less unique: there are 36,591 distinct names, with 10 repeated name rows. Analyses should preserve feature identifiers and use an explicit rule when combining repeated gene names. Barcodes are unique within each sample. There are 59 barcode strings shared across sample files; analyses must prefix barcodes with the GEO sample accession so these independent archive records are never merged by barcode text alone.

## Preprocessing interpretation

The retrieved GEO processing statements describe Cell Ranger 6.1.2 with `GRCh38-2020-A`, filtered expression matrices, a custom script combining libraries from a batch, cell filtering, scaling to 10,000 transcripts per cell, log transformation, and regression of mitochondrial fraction before dimension reduction. The metadata does not assign an explicit processing stage to the six deposited files. These statements are preserved verbatim in [pdls_maturity_matrix_receipt.json](pdls_maturity_matrix_receipt.json).

The integer values establish a numerical property of the deposited files. They do not prove that the matrices are untouched raw UMI measurements, show how library merging was performed, or identify which cells came from each library, tooth or donor. The deposited matrices also include 127 immature and 75 mature barcodes below the metadata's stated 200-feature downstream threshold. That discrepancy means the deposited inputs should not be described as reproducing the final downstream cell cohort without an explicit inclusion rule and additional processing provenance. This audit applies no cell exclusions.

The sample labels refer to developmental root maturity. They are not an aging or rejuvenation contrast. Cells cannot replace independent donor units for stage-level uncertainty estimates. There is no cell-to-tooth, cell-to-donor or library-to-cell crosswalk in these three-file inputs or the previously retrieved GEO metadata. See [the archive qualification](PDLSC_MATURITY_DATASET_QUALIFICATION.md) for the publication's reported study design and its limits.

## Retrieval and reproducibility

Raw files occupy **186,658,140 compressed bytes** in ignored `data/literature/GSE306722-matrices/`. Each real fetch has a `regen.record` receipt in ignored `data/provenance/`. Compressed SHA-256 hashes, expanded SHA-256 hashes, byte counts, original FTP URLs, actual HTTPS URLs, fetch times and provenance filenames are retained in [pdls_maturity_matrix_receipt.json](pdls_maturity_matrix_receipt.json). The downloads were followed by a complete second audit using a hash-verified local cache; fetch dates and provenance records remain those of the real first retrieval.

| Official deposited file | Compressed SHA-256 |
|---|---|
| [Immature barcodes](https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM9206nnn/GSM9206804/suppl/GSM9206804_Immature_barcodes.tsv.gz) | `12defd4c508a6156d61bd86f24c9919316474b3796372d91730cec2cf5f6270b` |
| [Immature features](https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM9206nnn/GSM9206804/suppl/GSM9206804_Immature_features.tsv.gz) | `bb3b92f1e134e6943cb764c24867a0940790694ad0bd866b8c4324c851ac8db7` |
| [Immature matrix](https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM9206nnn/GSM9206804/suppl/GSM9206804_Immature_matrix.mtx.gz) | `4600bf429b9737c6f252f08f19e2dbddc6bc4a26ebfe36f5e3a875c4a19b2e9c` |
| [Mature barcodes](https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM9206nnn/GSM9206805/suppl/GSM9206805_Mature_barcodes.tsv.gz) | `4e5a7dff2d412391e63d678b6de38089b25ac188ede0a17312bd0c36394a26be` |
| [Mature features](https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM9206nnn/GSM9206805/suppl/GSM9206805_Mature_features.tsv.gz) | `8303f9573a056d7970ff21a815fed0ef2280ab458801a98db52d62f269ed964f` |
| [Mature matrix](https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM9206nnn/GSM9206805/suppl/GSM9206805_Mature_matrix.mtx.gz) | `dbcf209988cf6d7255b4986b8ab948515f8fbc9d51912ce6f41208dbc25c40f1` |

From the host repository, reproduce the audit in the existing workbench:

```powershell
docker compose exec -T workbench python /lab/workbench/studies/dental-regeneration-2026-10-09/audit_pdls_maturity_matrices.py
```

The script uses the qualified metadata receipt as its six-file manifest. It streams HTTP responses through the existing `regen` retry and user-agent path, caps each compressed file at 256 MiB, reads gzip members through their CRC trailers with a 2 GiB expansion cap, and verifies cached bytes against their download receipts. SciPy parses COO entries before any duplicate summation. Packed coordinate sorting counts both repeated entries and distinct duplicated coordinate groups, so duplicates cannot disappear during sparse canonicalization. No matrix is densified. The audit records Python, NumPy and SciPy versions and hashes of its source script and metadata receipt.

Nine focused tests passed in Docker, including corrupt gzip CRCs, expansion limits, bounded HTTP intake, duplicate feature/barcode identities, repeated sparse coordinates, transposed matrices, fractional/negative/nonfinite values, invalid indices, incorrect declared entry counts, and empty matrices. Scientific-library tests skip on a host lacking NumPy/SciPy; the Docker run executes all nine.

## Next analysis gate

Freeze the marker panel and cell-inclusion rule before source-scoped cell-state summaries. Report sensitivity to the stated feature threshold and preserve sample-prefixed barcodes. Compare native-PDL cell states with the iPS-PDL bulk results using transparent descriptive summaries that respect the different assays and unresolved preprocessing; do not present stage-level cell counts as donor replication. Expression similarity can screen candidates, but whole-periodontal regeneration still requires the architectural and functional endpoints listed in the archive qualification.
