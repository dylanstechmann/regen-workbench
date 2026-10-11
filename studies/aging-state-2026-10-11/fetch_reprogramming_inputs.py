"""Fetch and qualify bounded, processed GSE165177 inputs for descriptive analysis."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import regen

ACCESSION = "GSE165177"
PREFIX = "GSE165nnn"
COMPRESSED_LIMIT = 64 * 1024 * 1024
EXPANDED_LIMIT = 512 * 1024 * 1024
FILES = {
    "series_metadata": (
        f"https://ftp.ncbi.nlm.nih.gov/geo/series/{PREFIX}/{ACCESSION}/soft/{ACCESSION}_family.soft.gz",
        f"{ACCESSION}_family.soft.gz",
    ),
    "expression_part_1": (
        f"https://ftp.ncbi.nlm.nih.gov/geo/series/{PREFIX}/{ACCESSION}/suppl/{ACCESSION}_Log2_RPM_Transient_reprogramming.txt.gz",
        f"{ACCESSION}_Log2_RPM_Transient_reprogramming.txt.gz",
    ),
    "expression_part_2": (
        f"https://ftp.ncbi.nlm.nih.gov/geo/series/{PREFIX}/{ACCESSION}/suppl/{ACCESSION}_Log2_RPM_Transient_reprogramming_part2_170621.txt.gz",
        f"{ACCESSION}_Log2_RPM_Transient_reprogramming_part2_170621.txt.gz",
    ),
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def normalize_sample_label(label: str) -> str:
    """Normalize GEO title separators only; preserve a strict one-to-one join."""
    return re.sub(r"[\s_]+", " ", label).strip().casefold()


def parse_soft(path: Path) -> dict:
    samples, series_fields, current_kind, current = [], {}, None, None
    expanded = 0
    with gzip.open(path, "rt", encoding="utf-8", errors="strict") as handle:
        for line in handle:
            expanded += len(line.encode("utf-8"))
            if expanded > EXPANDED_LIMIT:
                raise ValueError("Expanded SOFT family exceeds the intake bound")
            line = line.rstrip("\r\n")
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
    if len(samples) != 95:
        raise ValueError(f"Expected 95 source sample records per the series card; got {len(samples)}")
    declared = set(series_fields.get("Series_sample_id", []))
    observed = {sample["accession"] for sample in samples}
    if declared != observed or len(observed) != len(samples):
        raise ValueError("GEO series sample list and unique SAMPLE metadata records differ")
    return {"accession": ACCESSION, "series_fields": series_fields, "samples": samples,
            "sample_record_count": len(samples), "expanded_bytes": expanded,
            "limits": "GEO sample records and barcodes are not assumed to be independent donors or cultures."}


def inspect_expression(path: Path) -> dict:
    expanded, lines, header = 0, 0, None
    first_rows = []
    with gzip.open(path, "rt", encoding="utf-8", errors="strict", newline="") as handle:
        for line in handle:
            lines += 1
            expanded += len(line.encode("utf-8"))
            if expanded > EXPANDED_LIMIT:
                raise ValueError(f"Expanded expression file exceeds intake bound: {path.name}")
            stripped = line.rstrip("\r\n")
            if header is None:
                header = stripped.split("\t")
            elif len(first_rows) < 2:
                first_rows.append(stripped.split("\t", 1)[0])
    if not header or len(header) < 2 or len(set(header)) != len(header):
        raise ValueError(f"Missing, short, or duplicated table header in {path.name}")
    return {"filename": path.name, "expanded_bytes": expanded, "line_count_including_header": lines,
            "data_row_count": lines - 1, "column_count": len(header), "header": header,
            "first_feature_labels": first_rows}


def main() -> None:
    cache = regen.DATA / "literature" / "aging-reprogramming-GSE165177"
    cache.mkdir(parents=True, exist_ok=True)
    fetched = {}
    for key, (url, filename) in FILES.items():
        path = cache / filename
        if not path.is_file():
            content = regen.http_bytes(url, timeout=120)
            if len(content) > COMPRESSED_LIMIT:
                raise ValueError(f"Compressed source exceeds bound: {filename}")
            path.write_bytes(content)
            receipt = regen.record("aging-gse165177-source-fetch", {
                "accession": ACCESSION, "source_url": url, "content_encoding": "gzip",
                "compressed_sha256": sha256_bytes(content), "compressed_bytes": len(content),
                "compressed_limit_bytes": COMPRESSED_LIMIT, "expanded_limit_bytes": EXPANDED_LIMIT,
            }, [path])
        else:
            receipt = None
        if path.stat().st_size > COMPRESSED_LIMIT:
            raise ValueError(f"Cached source exceeds compressed bound: {filename}")
        if key == "series_metadata":
            parsed = parse_soft(path)
            summary = {"sample_record_count": parsed["sample_record_count"],
                       "series_fields": {name: parsed["series_fields"].get(name, []) for name in (
                           "Series_title", "Series_status", "Series_pubmed_id", "Series_sample_id")},
                       "sample_metadata": parsed["samples"], "expanded_bytes": parsed["expanded_bytes"]}
            parsed_path = cache / f"{ACCESSION}_series_metadata.json"
            parsed_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            regen.record("aging-gse165177-parsed-metadata", {"accession": ACCESSION, "source_sha256": regen.sha256_file(path)}, [parsed_path])
            fetched[key] = {"filename": filename, "sha256": regen.sha256_file(path),
                            "compressed_bytes": path.stat().st_size, "metadata_json_sha256": regen.sha256_file(parsed_path),
                            "sample_record_count": parsed["sample_record_count"],
                            "expanded_bytes": parsed["expanded_bytes"],
                            "local_provenance_receipt": receipt.name if receipt else "reused_verified_cache"}
        else:
            table = inspect_expression(path)
            fetched[key] = {"filename": filename, "sha256": regen.sha256_file(path),
                            "compressed_bytes": path.stat().st_size, **table,
                            "local_provenance_receipt": receipt.name if receipt else "reused_verified_cache"}
    metadata = json.loads((cache / f"{ACCESSION}_series_metadata.json").read_text(encoding="utf-8"))
    metadata_ids = {sample["accession"] for sample in metadata["sample_metadata"]}
    title_to_sample = {}
    for sample in metadata["sample_metadata"]:
        title = sample["fields"].get("Sample_title", [""])[0]
        key = normalize_sample_label(title)
        if not title or key in title_to_sample:
            raise ValueError("GEO sample titles are missing or ambiguous after separator normalization")
        title_to_sample[key] = sample
    crosswalks = {}
    accession_headers = []
    for table_key in ("expression_part_1", "expression_part_2"):
        # The first 12 columns are genomic annotation; remaining columns are sample titles.
        sample_titles = fetched[table_key]["header"][12:]
        mapped = []
        for title in sample_titles:
            sample = title_to_sample.get(normalize_sample_label(title))
            if sample is None:
                raise ValueError(f"Expression sample title has no exact GEO metadata match: {title!r}")
            mapped.append({"expression_header": title, "GSM": sample["accession"],
                           "GEO_sample_title": sample["fields"]["Sample_title"][0]})
        crosswalks[fetched[table_key]["filename"]] = mapped
        accession_headers.extend(item["GSM"] for item in mapped)
    accession_header_ids = set(accession_headers)
    receipt = {
        "schema_version": 1, "accession": ACCESSION, "source": "NCBI GEO official FTP",
        "retrieved_or_cache_checked_utc": regen.now(), "files": fetched,
        "sample_mapping_check": {"metadata_sample_count": len(metadata_ids),
                                 "expression_sample_columns": len(accession_headers),
                                 "unique_GSMs_after_exact_title_join": len(accession_header_ids),
                                 "all_headers_match_metadata_samples": (
                                     len(accession_headers) == len(accession_header_ids)
                                     and accession_header_ids == metadata_ids),
                                 "headers_missing_from_metadata": sorted(accession_header_ids - metadata_ids),
                                 "metadata_samples_missing_from_headers": sorted(metadata_ids - accession_header_ids),
                                 "expression_header_to_GSM": crosswalks,
                                 "normalization": "case-fold and collapse spaces/underscores; all titles must join uniquely"},
        "limits": {"processed_log2_RPM_is_not_raw_count_data": True,
                   "biosample_records_do_not_prove_independent_donors": True,
                   "functional_assays_not_yet_joined_to_expression_samples": True},
    }
    if not receipt["sample_mapping_check"]["all_headers_match_metadata_samples"]:
        raise ValueError("Expression sample titles do not map one-to-one onto GEO sample records")
    output = HERE / "geo_intake_receipt.json"
    output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    regen.record("aging-gse165177-intake-summary", {"accession": ACCESSION}, [output])
    print(json.dumps({"accession": ACCESSION,
                      "sample_records": len(metadata_ids),
                      "matrix_sample_columns": len(accession_headers),
                      "files": {key: {"compressed_bytes": value["compressed_bytes"],
                                     "rows": value.get("data_row_count"),
                                     "columns": value.get("column_count")}
                                for key, value in fetched.items()},
                      "headers_match_metadata": True,
                      "receipt": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
