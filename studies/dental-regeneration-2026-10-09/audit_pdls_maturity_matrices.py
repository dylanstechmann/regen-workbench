"""Fetch and audit the six deposited GSE306722 sparse-matrix inputs.

Numerical count compatibility is measured independently of preprocessing lineage.
Downloads and uncompressed gzip reads are bounded; matrices stay sparse.
"""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import platform
import sys
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen

ACCESSION = "GSE306722"
COMPRESSED_LIMIT = 256 * 1024 * 1024
EXPANDED_LIMIT = 2 * 1024 * 1024 * 1024
CHUNK = 1024 * 1024


def official_https_url(source: str) -> str:
    parts = urlsplit(source)
    if (parts.scheme not in {"ftp", "https"} or parts.hostname != "ftp.ncbi.nlm.nih.gov"
            or parts.username or parts.password or parts.port or parts.query or parts.fragment
            or not parts.path.startswith("/geo/samples/GSM9206nnn/")
            or not parts.path.endswith(("_barcodes.tsv.gz", "_features.tsv.gz", "_matrix.mtx.gz"))):
        raise ValueError("Input URL is not an expected official GEO supplementary file")
    return urlunsplit(("https", parts.netloc, parts.path, "", ""))


def download_file(source: str, directory: Path, refresh: bool = False) -> dict:
    """Use regen HTTP retry/UA and record each completed real fetch."""
    url = official_https_url(source)
    destination = directory / Path(urlsplit(url).path).name
    sidecar = destination.with_suffix(destination.suffix + ".download.json")
    if destination.is_file() and sidecar.is_file() and not refresh:
        cached = json.loads(sidecar.read_text(encoding="utf-8"))
        if (cached["download_url"] != url or destination.stat().st_size != cached["compressed_bytes"]
                or regen.sha256_file(destination) != cached["sha256"]):
            raise ValueError(f"Cached bytes do not match their download receipt: {destination.name}")
        return {**cached, "cache_reused_this_run": True}
    if destination.exists() and not refresh:
        raise ValueError(f"Unreceipted cache file requires --refresh: {destination.name}")
    directory.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = Request(url, headers={"User-Agent": regen.UA, "Accept": "application/octet-stream"})
    digest = hashlib.sha256()
    size = 0
    try:
        with regen._http_with_retry(request, timeout=120) as response, temporary.open("wb") as output:
            declared_length = response.headers.get("Content-Length")
            if declared_length is not None and int(declared_length) > COMPRESSED_LIMIT:
                raise ValueError("Content-Length exceeds compressed intake limit")
            final_url = response.geturl()
            if official_https_url(final_url) != url:
                raise ValueError("Unexpected supplementary-file redirect")
            while block := response.read(CHUNK):
                size += len(block)
                if size > COMPRESSED_LIMIT:
                    raise ValueError("Download exceeds compressed intake limit")
                digest.update(block)
                output.write(block)
        if declared_length is not None and size != int(declared_length):
            raise ValueError("Downloaded bytes do not match Content-Length")
        if not size:
            raise ValueError("Downloaded file is empty")
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    provenance = regen.record("dental-pdls-maturity-matrix-fetch", {
        "accession": ACCESSION, "source_url": source, "download_url": url,
        "compressed_intake_limit_bytes": COMPRESSED_LIMIT,
    }, [destination])
    result = {
        "source_url": source, "download_url": url, "final_url": final_url,
        "local_path_relative_to_data": str(destination.relative_to(regen.DATA)),
        "retrieved_utc": regen.now(), "compressed_bytes": size, "sha256": digest.hexdigest(),
        "content_length_header_bytes": int(declared_length) if declared_length is not None else None,
        "local_provenance_receipt": provenance.name,
    }
    sidecar.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {**result, "cache_reused_this_run": False}


def verify_gzip(path: Path, expanded_limit: int = EXPANDED_LIMIT) -> dict:
    """Read through all gzip members/trailers, validating CRC and bounding expansion."""
    digest = hashlib.sha256()
    size = 0
    with gzip.open(path, "rb") as handle:
        while block := handle.read(CHUNK):
            size += len(block)
            if size > expanded_limit:
                raise ValueError(f"Expanded gzip exceeds intake limit: {path.name}")
            digest.update(block)
    return {"gzip_integrity_passed": True, "expanded_bytes": size,
            "expanded_sha256": digest.hexdigest()}


def audit_labels(path: Path, kind: str) -> tuple[dict, list[str]]:
    if kind not in {"features", "barcodes"}:
        raise ValueError("Unknown label-file kind")
    identities, symbols, widths, feature_types = [], [], Counter(), Counter()
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            fields = line.rstrip("\r\n").split("\t")
            if any(not field or field != field.strip() for field in fields):
                raise ValueError(f"Blank or padded label in {path.name}")
            if (kind == "barcodes" and len(fields) != 1
                    or kind == "features" and len(fields) not in {2, 3}):
                raise ValueError(f"Unexpected label columns in {path.name}")
            widths[len(fields)] += 1
            identities.append(fields[0])
            if kind == "features":
                symbols.append(fields[1])
                if len(fields) == 3:
                    feature_types[fields[2]] += 1
    if not identities:
        raise ValueError(f"No labels in {path.name}")
    repeated_identities = len(identities) - len(set(identities))
    result = {
        "rows": len(identities), "column_count_distribution": dict(widths),
        "unique_identifiers": len(set(identities)), "repeated_identifier_rows": repeated_identities,
        "identifiers_in_order_sha256": hashlib.sha256("\n".join(identities).encode()).hexdigest(),
    }
    if repeated_identities:
        raise ValueError(f"Duplicate {kind} identifiers in {path.name}: {repeated_identities}")
    if kind == "features":
        result.update({"unique_gene_names": len(set(symbols)),
                       "repeated_gene_name_rows": len(symbols) - len(set(symbols)),
                       "feature_type_distribution": dict(feature_types)})
    return result, identities


def read_matrix_header(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="ascii") as handle:
        header = handle.readline().strip()
        tokens = header.lower().split()
        if (len(tokens) != 5 or tokens[:3] != ["%%matrixmarket", "matrix", "coordinate"]
                or tokens[3] not in {"integer", "real"} or tokens[4] != "general"):
            raise ValueError("Expected general integer/real coordinate MatrixMarket input")
        for line in handle:
            if line.strip() and not line.startswith("%"):
                dimensions = line.split()
                break
        else:
            raise ValueError("Missing MatrixMarket dimensions")
        if len(dimensions) != 3:
            raise ValueError("Invalid MatrixMarket dimensions")
        rows, columns, nnz = map(int, dimensions)
        if min(rows, columns) <= 0 or nnz < 0:
            raise ValueError("Invalid MatrixMarket dimension or entry count")
    return {"header": header, "declared_field": tokens[3], "declared_symmetry": tokens[4],
            "declared_rows": rows, "declared_columns": columns, "declared_entries": nnz}


def summary_quantiles(values) -> dict:
    import numpy as np
    quantiles = np.quantile(values, [0, 0.25, 0.5, 0.75, 1])
    return dict(zip(["min", "q25", "median", "q75", "max"], map(float, quantiles)))


def audit_matrix(path: Path, feature_count: int, barcode_count: int) -> dict:
    import numpy as np
    from scipy.io import mmread

    header = read_matrix_header(path)
    shape = (header["declared_rows"], header["declared_columns"])
    if shape == (feature_count, barcode_count):
        orientation = "features_by_barcodes"
    elif shape == (barcode_count, feature_count):
        orientation = "barcodes_by_features"
    else:
        raise ValueError("Matrix dimensions do not match feature/barcode files")
    # mmread preserves COO entries, including repeated coordinates; do not sum
    # duplicates into CSR before this audit. It also rejects incorrect nnz and
    # out-of-range coordinates instead of silently clipping them.
    with gzip.open(path, "rb") as handle:
        matrix = mmread(handle).tocoo(copy=False)
    if matrix.shape != shape or matrix.nnz != header["declared_entries"]:
        raise ValueError("Parsed MatrixMarket dimensions/entry count disagree with the header")
    if (np.any(matrix.row < 0) or np.any(matrix.row >= shape[0])
            or np.any(matrix.col < 0) or np.any(matrix.col >= shape[1])):
        raise ValueError("Sparse coordinates outside declared dimensions")
    data = matrix.data
    finite = np.isfinite(data)
    finite_values = data[finite]
    negative = int(np.count_nonzero(finite_values < 0))
    fractional = int(np.count_nonzero(finite_values != np.floor(finite_values)))
    zero = int(np.count_nonzero(finite_values == 0))
    nonfinite = int(data.size - np.count_nonzero(finite))
    packed = matrix.row.astype(np.int64) * shape[1] + matrix.col
    packed.sort()
    repeated = packed[1:] == packed[:-1]
    repeated_entries = int(np.count_nonzero(repeated))
    # Number of coordinate groups with 2+ entries, distinct from excess entries.
    duplicate_groups = (int(np.count_nonzero(repeated & np.concatenate(([True], ~repeated[:-1]))))
                        if repeated.size else 0)
    unique_coordinates = int(data.size - repeated_entries)
    feature_axis = matrix.row if orientation == "features_by_barcodes" else matrix.col
    barcode_axis = matrix.col if orientation == "features_by_barcodes" else matrix.row
    cell_totals = np.bincount(barcode_axis, weights=data, minlength=barcode_count)
    cell_detected = np.bincount(barcode_axis[data > 0], minlength=barcode_count)
    feature_detected = np.bincount(feature_axis[data > 0], minlength=feature_count)
    result = {**header, "orientation_from_label_dimensions": orientation,
              "parsed_dtype": str(data.dtype), "actual_stored_entries": int(matrix.nnz),
              "declared_entry_count_matches_actual": True, "sparse_indices_valid": True,
              "unique_coordinates": unique_coordinates,
              "duplicate_coordinate_groups": duplicate_groups, "repeated_coordinate_entries": repeated_entries,
              "explicit_zero_entries": zero, "negative_entries": negative,
              "nonfinite_entries": nonfinite, "fractional_finite_entries": fractional,
              "minimum_finite_value": float(finite_values.min()) if finite_values.size else None,
              "maximum_finite_value": float(finite_values.max()) if finite_values.size else None,
              "all_finite_values_are_integers": fractional == 0,
              "nonnegative_integer_numeric_form": nonfinite == negative == fractional == 0,
              "stored_coordinate_density": unique_coordinates / (feature_count * barcode_count),
              "zero_total_barcodes": int(np.count_nonzero(cell_totals == 0)),
              "features_with_no_positive_entries": int(np.count_nonzero(feature_detected == 0))}
    if not nonfinite:
        result["per_barcode_entry_sum"] = summary_quantiles(cell_totals)
    # Counting stored entries gives distinct detected features only if there
    # are no repeated coordinates. Never report an inflated detection count.
    if not repeated_entries:
        result["per_barcode_positive_feature_count"] = summary_quantiles(cell_detected)
        result["barcodes_with_fewer_than_200_positive_features"] = int(np.count_nonzero(cell_detected < 200))
    result["structural_quality_passed"] = nonfinite == negative == repeated_entries == 0
    if header["declared_field"] == "integer" and fractional:
        raise ValueError("Integer MatrixMarket header contains fractional values")
    return result


def summarize_sample(sample: dict, directory: Path, refresh: bool = False) -> tuple[dict, dict]:
    file_records, file_paths = {}, {}
    for source in sample["supplementary_files"]:
        name = Path(urlsplit(source).path).name
        kind = next((item for item in ("barcodes", "features", "matrix") if f"_{item}." in name), None)
        if kind is None or kind in file_records:
            raise ValueError("Expected exactly one barcode, feature and matrix file per sample")
        print(f"# intake {sample['geo_sample']} {kind}", flush=True)
        record = download_file(source, directory, refresh)
        path = regen.DATA / record["local_path_relative_to_data"]
        file_records[kind] = {**record, **verify_gzip(path)}
        file_paths[kind] = path
    if set(file_records) != {"barcodes", "features", "matrix"}:
        raise ValueError("Missing supplementary-file role")
    feature_info, features = audit_labels(file_paths["features"], "features")
    barcode_info, barcodes = audit_labels(file_paths["barcodes"], "barcodes")
    result = {
        "geo_sample": sample["geo_sample"],
        "stage_label_from_source_fields": sample["stage_label_from_source_fields"],
        "files": file_records, "features": feature_info, "barcodes": barcode_info,
        "matrix": audit_matrix(file_paths["matrix"], len(features), len(barcodes)),
        "source_data_processing_statements": sample["data_processing"],
        "preprocessing_lineage": {
            "deposited_values_are_verified_raw_umi_counts": False,
            "exact_deposited_matrix_processing_stage": "unknown",
            "library_to_cell_mapping_available": False,
            "cell_to_tooth_or_donor_mapping_available": False,
            "reason": "Metadata describes Cell Ranger filtered matrices, library merging, cell filtering, normalization/log transformation and regression. It does not identify which stage generated these deposited files. Integer-valued entries do not establish raw UMI lineage.",
        },
    }
    return result, {"features": features, "barcodes": barcodes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Refetch files instead of using a hash-verified cache")
    args = parser.parse_args()
    import numpy as np
    import scipy

    regen.ensure_dirs()
    metadata_path = Path(__file__).with_name("pdls_maturity_metadata_receipt.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata["accession"] != ACCESSION or len(metadata["samples"]) != 2:
        raise ValueError("Expected qualified GSE306722 metadata with two sample records")
    directory = regen.DATA / "literature" / f"{ACCESSION}-matrices"
    samples, labels = [], []
    for sample in metadata["samples"]:
        result, identifiers = summarize_sample(sample, directory, args.refresh)
        samples.append(result)
        labels.append(identifiers)
        print(json.dumps({"geo_sample": result["geo_sample"], "matrix": result["matrix"]}), flush=True)
    receipt = {
        "schema_version": 1, "accession": ACCESSION, "audited_utc": regen.now(),
        "metadata_receipt_sha256": regen.sha256_file(metadata_path),
        "script_sha256": regen.sha256_file(Path(__file__)),
        "software": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "compressed_file_limit_bytes": COMPRESSED_LIMIT, "expanded_file_limit_bytes": EXPANDED_LIMIT,
        "samples": samples,
        "cross_sample_labels": {
            "feature_id_order_identical": labels[0]["features"] == labels[1]["features"],
            "shared_feature_identifiers": len(set(labels[0]["features"]) & set(labels[1]["features"])),
            "shared_barcode_strings": len(set(labels[0]["barcodes"]) & set(labels[1]["barcodes"])),
            "barcode_strings_are_not_cross_sample_cell_identifiers": True,
        },
        "qualification": {
            "descriptive_sparse_matrix_loading_eligible": all(item["matrix"]["structural_quality_passed"] for item in samples),
            "raw_umi_provenance_qualified": False, "independent_donor_inference_eligible": False,
            "recommended_next_step": "Freeze native-PDL marker panels and a cell-inclusion rule; perform source-scoped descriptive cell-state analysis with sample-prefixed barcodes, retaining unresolved preprocessing and donor lineage.",
        },
    }
    destination = Path(__file__).with_name("pdls_maturity_matrix_receipt.json")
    destination.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": str(destination), "qualification": receipt["qualification"]}), flush=True)


if __name__ == "__main__":
    main()
