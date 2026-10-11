"""Fetch and qualify the public human gingiva age-reference series GSE83382."""

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

ACCESSION = "GSE83382"
PREFIX = "GSE83nnn"
COMPRESSED_LIMIT = 32 * 1024 * 1024
EXPANDED_LIMIT = 256 * 1024 * 1024
FILES = {
    "series_metadata": (
        f"https://ftp.ncbi.nlm.nih.gov/geo/series/{PREFIX}/{ACCESSION}/soft/{ACCESSION}_family.soft.gz",
        f"{ACCESSION}_family.soft.gz",
    ),
    "processed_expression": (
        f"https://ftp.ncbi.nlm.nih.gov/geo/series/{PREFIX}/{ACCESSION}/suppl/"
        f"{ACCESSION}_Processed_data_file_FPKM.txt.gz",
        f"{ACCESSION}_Processed_data_file_FPKM.txt.gz",
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
    if len(samples) != 6:
        raise ValueError(f"Expected the six GEO sample records; found {len(samples)}")
    declared = set(series_fields.get("Series_sample_id", []))
    observed = {sample["accession"] for sample in samples}
    if declared != observed or len(observed) != len(samples):
        raise ValueError("GEO series sample list differs from unique SAMPLE metadata records")
    expected_title = "Differential Matrix metalloprotease (MMP) Expression Profiles Found in Aged Gingiva"
    if series_fields.get("Series_title") != [expected_title]:
        raise ValueError("GSE83382 series title differs from the expected gingiva age study")
    return {"accession": ACCESSION, "samples": samples,
            "series_fields": series_fields, "expanded_bytes": expanded}


def inspect_expression(path: Path) -> dict:
    expanded, line_count, header, first_row = 0, 0, None, None
    with gzip.open(path, "rt", encoding="utf-8", errors="strict", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            line_count += 1
            expanded += len(("\t".join(row) + "\n").encode("utf-8"))
            if expanded > EXPANDED_LIMIT:
                raise ValueError("Expanded expression matrix exceeds intake bound")
            if header is None:
                header = row
            elif first_row is None:
                first_row = row
    if not header or len(header) < 7 or len(set(header)) != len(header):
        raise ValueError("Missing, short, or duplicated expression matrix header")
    return {"header": header, "line_count_including_header": line_count,
            "data_row_count": line_count - 1, "column_count": len(header),
            "expanded_bytes": expanded, "first_feature_row": first_row}


def characteristics(sample: dict) -> dict[str, str]:
    result = {}
    for item in sample["fields"].get("Sample_characteristics_ch1", []):
        if ":" in item:
            key, value = item.split(":", 1)
            result[norm(key)] = value.strip()
    return result


def main() -> None:
    cache = regen.DATA / "literature" / "gingival-age-reference-GSE83382"
    cache.mkdir(parents=True, exist_ok=True)
    fetched, parsed = {}, None
    for key, (url, filename) in FILES.items():
        path = cache / filename
        fetch_receipt = None
        if not path.is_file():
            content = regen.http_bytes(url, timeout=120)
            if len(content) > COMPRESSED_LIMIT:
                raise ValueError(f"Compressed source exceeds bound: {filename}")
            path.write_bytes(content)
            fetch_receipt = regen.record("gingival-gse83382-source-fetch", {
                "accession": ACCESSION, "source_url": url,
                "compressed_sha256": sha256_bytes(content),
                "compressed_bytes": len(content), "compressed_limit_bytes": COMPRESSED_LIMIT,
                "expanded_limit_bytes": EXPANDED_LIMIT,
            }, [path])
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
            regen.record("gingival-gse83382-parsed-metadata", {
                "accession": ACCESSION, "source_sha256": regen.sha256_file(path)
            }, [metadata_path])
            fetched[key] = {"filename": filename, "sha256": regen.sha256_file(path),
                            "compressed_bytes": path.stat().st_size,
                            "sample_count": len(parsed["samples"]),
                            "metadata_json_sha256": regen.sha256_file(metadata_path),
                            "expanded_bytes": parsed["expanded_bytes"],
                            "local_provenance_receipt": fetch_receipt.name if fetch_receipt else "reused_verified_cache"}
        else:
            matrix = inspect_expression(path)
            fetched[key] = {"filename": filename, "sha256": regen.sha256_file(path),
                            "compressed_bytes": path.stat().st_size, **matrix,
                            "local_provenance_receipt": fetch_receipt.name if fetch_receipt else "reused_verified_cache"}

    metadata = json.loads((cache / f"{ACCESSION}_sample_metadata.json").read_text(encoding="utf-8"))
    samples = metadata["samples"]
    expression_columns = fetched["processed_expression"]["header"][-6:]
    if len(expression_columns) != 6:
        raise ValueError("Expected six processed-expression sample columns")
    geo_samples = []
    for sample in samples:
        char = characteristics(sample)
        title = sample["fields"].get("Sample_title", [""])[0]
        age_raw = char.get("age", "")
        sex = char.get("gender", char.get("sex", ""))
        group = "young" if norm(title).startswith("young") else "old" if norm(title).startswith("old") else "unknown"
        if group == "unknown" or not age_raw or not sex:
            raise ValueError(f"Incomplete age/group/sex metadata for {sample['accession']}")
        age = float(re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", age_raw).group(1))
        if (group == "young" and not 17 <= age <= 20) or (group == "old" and age < 60):
            raise ValueError(f"Age is inconsistent with paper's group label for {sample['accession']}")
        geo_samples.append({"GSM": sample["accession"], "sample_title": title,
                       "synthetic_donor_label": f"{group[0].upper()}{len([m for m in geo_samples if m['group'] == group]) + 1}",
                       "group": group, "age_years": age, "sex": sex,
                       "source_name": sample["fields"].get("Sample_source_name_ch1", [""])[0],
                       "characteristics": char,
                       "treatment_protocol": sample["fields"].get("Sample_treatment_protocol_ch1", []),
                       "growth_protocol": sample["fields"].get("Sample_growth_protocol_ch1", []),
                       "extract_protocol": sample["fields"].get("Sample_extract_protocol_ch1", []),
                       "data_processing": sample["fields"].get("Sample_data_processing", [])})
    metadata_groups = {group: sum(row["group"] == group for row in geo_samples) for group in ("young", "old")}
    if metadata_groups != {"young": 3, "old": 3}:
        raise ValueError(f"Unexpected GEO age-group balance: {metadata_groups}")
    expression_map = []
    for column in expression_columns:
        match = re.fullmatch(r"(Young|Old)\d+", column, flags=re.IGNORECASE)
        if not match:
            raise ValueError(f"Unrecognized processed-expression header: {column!r}")
        group = match.group(1).casefold()
        expression_map.append({"expression_header": column, "group": group,
                               "candidate_GSMs": [row["GSM"] for row in geo_samples if row["group"] == group],
                               "individual_linkage_resolved": False})
    expression_groups = {group: sum(row["group"] == group for row in expression_map) for group in ("young", "old")}
    if expression_groups != metadata_groups:
        raise ValueError(f"Expression headers do not match GEO age-group balance: {expression_groups}")

    mapping_path = HERE / "gingival_age_geo_samples.tsv"
    columns = ["GSM", "synthetic_donor_label", "sample_title", "group", "age_years", "sex",
               "source_name", "tissue", "other_characteristics"]
    with mapping_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in geo_samples:
            char = row["characteristics"]
            writer.writerow({
                "GSM": row["GSM"], "synthetic_donor_label": row["synthetic_donor_label"],
                "sample_title": row["sample_title"], "group": row["group"],
                "age_years": row["age_years"], "sex": row["sex"],
                "source_name": row["source_name"], "tissue": char.get("tissue", ""),
                "other_characteristics": json.dumps({k: v for k, v in char.items()
                                                      if k not in ("age", "gender", "sex", "tissue")}, sort_keys=True),
            })
    expression_map_path = HERE / "gingival_age_expression_group_map.tsv"
    with expression_map_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["expression_header", "group", "candidate_GSMs",
                                                    "individual_linkage_resolved"],
                                delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in expression_map:
            writer.writerow({**row, "candidate_GSMs": ",".join(row["candidate_GSMs"])})
    receipt = {
        "schema_version": 1, "accession": ACCESSION,
        "primary_publication": {"pmid": "27391467", "doi": "10.1371/journal.pone.0158777",
                                "pmcid": "PMC4938517"},
        "source": "NCBI GEO official FTP",
        "retrieved_or_cache_checked_utc": regen.now(),
        "files": fetched,
        "geo_sample_records": geo_samples,
        "expression_header_group_map": expression_map,
        "sample_mapping_check": {"metadata_sample_count": len(geo_samples),
                                  "matrix_sample_columns": len(expression_columns),
                                  "unique_GSMs_mapped": len(geo_samples),
                                  "individual_samples_mapped_one_to_one": False,
                                  "group_counts_match": True,
                                  "samples_per_group": metadata_groups,
                                  "expression_headers_per_group": expression_groups,
                                  "expression_scale": "Processed FPKM matrix; GEO metadata states quantile-normalized, log2-transformed, and median-centered across genes and samples.",
                                  "biological_unit": "The source study describes three distinct people per group. GEO sample records provide individual ages, but processed matrix aliases (Young1/Young3/Young4, Old1/Old2/Old3) cannot be joined one-to-one to GEO's Young rep1-3/Old rep1-3 titles from available metadata. Analyses therefore use group-level replicate values without individual ages."},
        "eligibility_and_limits": {
            "eligible_for": "Descriptive group-level young-versus-old gingival tissue comparison and fixed exploratory panels.",
            "not_eligible_for": "Robust age-clock training, causal age effects, precise differential-expression inference, cell-intrinsic fibroblast or epithelial aging claims.",
            "limitations": ["Only three RNA-seq donors per age group.",
                            "Young ages are 17-20 and old ages are 60 or older; age is confounded with a widely separated group comparison.",
                            "Bulk gingiva mixes epithelial, stromal, vascular and immune cells.",
                            "Processed FPKM values are already quantile-normalized, log2-transformed, and median-centered; raw count-scale reconstruction is not used.",
                            "The source paper's qPCR validation used a separate five-per-group cohort and cannot increase the RNA-seq sample size."]},
    }
    receipt_path = HERE / "gingival_age_intake_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    regen.record("gingival-gse83382-intake-summary", {"accession": ACCESSION},
                 [mapping_path, expression_map_path, receipt_path])
    print(json.dumps({"accession": ACCESSION, "samples": len(geo_samples),
                      "matrix_rows": fetched["processed_expression"]["data_row_count"],
                      "matrix_columns": len(expression_columns), "samples_per_group": metadata_groups,
                      "geo_sample_table": str(mapping_path), "expression_map": str(expression_map_path),
                      "receipt": str(receipt_path),
                      "matrix_header": fetched["processed_expression"]["header"],
                      "first_row": fetched["processed_expression"]["first_feature_row"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
