"""Fetch and qualify the independent GSE113957 fibroblast age reference."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import regen

ACCESSION = "GSE113957"
PREFIX = "GSE113nnn"
COMPRESSED_LIMIT = 64 * 1024 * 1024
EXPANDED_LIMIT = 512 * 1024 * 1024
FILES = {
    "series_metadata": (
        f"https://ftp.ncbi.nlm.nih.gov/geo/series/{PREFIX}/{ACCESSION}/soft/{ACCESSION}_family.soft.gz",
        f"{ACCESSION}_family.soft.gz",
    ),
    "fpkm_matrix": (
        f"https://ftp.ncbi.nlm.nih.gov/geo/series/{PREFIX}/{ACCESSION}/suppl/{ACCESSION}_fpkm.txt.gz",
        f"{ACCESSION}_fpkm.txt.gz",
    ),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm(value: str) -> str:
    return re.sub(r"[\s_]+", " ", value).strip().casefold()


def parse_soft(path: Path) -> dict:
    samples, series_fields, current_kind, current = [], {}, None, None
    expanded = 0
    with gzip.open(path, "rt", encoding="utf-8", errors="strict") as handle:
        for raw in handle:
            expanded += len(raw.encode("utf-8"))
            if expanded > EXPANDED_LIMIT:
                raise ValueError("Expanded GEO family file exceeds intake bound")
            line = raw.rstrip("\r\n")
            if line.startswith("^") and " = " in line:
                current_kind, accession = line[1:].split(" = ", 1)
                current = {"accession": accession, "fields": {}}
                if current_kind == "SERIES" and accession == ACCESSION:
                    series_fields = current["fields"]
                elif current_kind == "SAMPLE":
                    samples.append(current)
            elif current is not None and line.startswith("!") and " = " in line:
                key, value = line[1:].split(" = ", 1)
                current["fields"].setdefault(key, []).append(value)
    if len(samples) != 143:
        raise ValueError(f"Expected the 143 GEO sample records; found {len(samples)}")
    declared = set(series_fields.get("Series_sample_id", []))
    observed = {sample["accession"] for sample in samples}
    if declared != observed or len(observed) != len(samples):
        raise ValueError("GEO series sample list differs from unique SAMPLE metadata records")
    return {"accession": ACCESSION, "samples": samples,
            "series_fields": series_fields, "expanded_bytes": expanded}


def inspect_matrix(path: Path) -> dict:
    expanded, line_count, header, first_row = 0, 0, None, None
    with gzip.open(path, "rt", encoding="utf-8", errors="strict", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            line_count += 1
            expanded += len(("\t".join(row) + "\n").encode("utf-8"))
            if expanded > EXPANDED_LIMIT:
                raise ValueError("Expanded FPKM matrix exceeds intake bound")
            if header is None:
                header = row
            elif first_row is None:
                first_row = row
    if not header or len(header) < 2 or len(set(header)) != len(header):
        raise ValueError("Missing, short, or duplicated FPKM matrix header")
    return {"header": header, "line_count_including_header": line_count,
            "data_row_count": line_count - 1, "column_count": len(header),
            "expanded_bytes": expanded, "first_feature_row": first_row}


def main() -> None:
    cache = regen.DATA / "literature" / "aging-reference-GSE113957"
    cache.mkdir(parents=True, exist_ok=True)
    fetched = {}
    parsed = None
    for key, (url, filename) in FILES.items():
        path = cache / filename
        if not path.is_file():
            content = regen.http_bytes(url, timeout=120)
            if len(content) > COMPRESSED_LIMIT:
                raise ValueError(f"Compressed source exceeds bound: {filename}")
            path.write_bytes(content)
            fetch_receipt = regen.record("aging-gse113957-source-fetch", {
                "accession": ACCESSION, "source_url": url, "compressed_sha256": sha256_bytes(content),
                "compressed_bytes": len(content), "compressed_limit_bytes": COMPRESSED_LIMIT,
                "expanded_limit_bytes": EXPANDED_LIMIT,
            }, [path])
        else:
            fetch_receipt = None
        if path.stat().st_size > COMPRESSED_LIMIT:
            raise ValueError(f"Cached GEO source exceeds compressed bound: {filename}")
        if key == "series_metadata":
            parsed = parse_soft(path)
            metadata_path = cache / f"{ACCESSION}_sample_metadata.json"
            metadata_path.write_text(json.dumps({
                "accession": ACCESSION, "sample_count": len(parsed["samples"]),
                "samples": parsed["samples"],
                "series_fields": {name: parsed["series_fields"].get(name, []) for name in (
                    "Series_title", "Series_status", "Series_pubmed_id", "Series_sample_id")},
                "expanded_bytes": parsed["expanded_bytes"],
            }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            regen.record("aging-gse113957-parsed-metadata", {
                "accession": ACCESSION, "source_sha256": regen.sha256_file(path)
            }, [metadata_path])
            fetched[key] = {"filename": filename, "sha256": regen.sha256_file(path),
                            "compressed_bytes": path.stat().st_size, "sample_count": len(parsed["samples"]),
                            "metadata_json_sha256": regen.sha256_file(metadata_path),
                            "expanded_bytes": parsed["expanded_bytes"],
                            "local_provenance_receipt": fetch_receipt.name if fetch_receipt else "reused_verified_cache"}
        else:
            matrix = inspect_matrix(path)
            fetched[key] = {"filename": filename, "sha256": regen.sha256_file(path),
                            "compressed_bytes": path.stat().st_size, **matrix,
                            "local_provenance_receipt": fetch_receipt.name if fetch_receipt else "reused_verified_cache"}

    metadata_path = cache / f"{ACCESSION}_sample_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    gsm_lookup, title_lookup = {}, {}
    for sample in metadata["samples"]:
        gsm_lookup[sample["accession"]] = sample
        title = sample["fields"].get("Sample_title", [""])[0]
        key = norm(title)
        if title:
            if key in title_lookup:
                raise ValueError("GEO sample titles collide after separator normalization")
            title_lookup[key] = sample
    # The table begins with eight transcript-annotation fields, followed by sample titles.
    columns = fetched["fpkm_matrix"]["header"][8:]
    mapped, unmatched = [], []
    for column in columns:
        sample = gsm_lookup.get(column) or title_lookup.get(norm(column))
        if sample is None:
            unmatched.append(column)
        else:
            mapped.append({"expression_header": column, "GSM": sample["accession"],
                           "GEO_sample_title": sample["fields"].get("Sample_title", [""])[0]})
    accession_ids = {entry["GSM"] for entry in mapped}
    metadata_ids = set(gsm_lookup)
    check = {"metadata_sample_count": len(metadata_ids), "matrix_sample_columns": len(columns),
             "unique_GSMs_mapped": len(accession_ids),
             "all_samples_mapped_one_to_one": not unmatched and len(columns) == len(accession_ids) and accession_ids == metadata_ids,
             "unmatched_expression_headers": unmatched,
             "metadata_samples_missing_from_matrix": sorted(metadata_ids - accession_ids),
             "expression_header_to_GSM": mapped}
    receipt = {"schema_version": 1, "accession": ACCESSION,
               "source": "NCBI GEO official FTP", "retrieved_or_cache_checked_utc": regen.now(),
               "files": fetched, "sample_mapping_check": check,
               "limits": {"FPKM_is_processed_expression_not_raw_counts": True,
                          "GEO_sample_records_are_not_assumed_to_be_independent_donors": True,
                          "age_associations_are_not_causal_or_healthspan_effects": True}}
    if not check["all_samples_mapped_one_to_one"]:
        raise ValueError("FPKM matrix columns do not map one-to-one onto GEO sample records")
    output = HERE / "aging_reference_intake_receipt.json"
    output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    regen.record("aging-gse113957-intake-summary", {"accession": ACCESSION}, [output])
    print(json.dumps({"accession": ACCESSION, "samples": len(metadata_ids),
                      "matrix_feature_rows": fetched["fpkm_matrix"]["data_row_count"],
                      "matrix_columns": len(columns), "mapping_matches": check["all_samples_mapped_one_to_one"],
                      "receipt": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
