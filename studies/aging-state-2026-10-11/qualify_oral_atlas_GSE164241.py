"""Audit GEO donor, tissue and condition metadata for oral atlas GSE164241."""

from __future__ import annotations

import csv
import gzip
import json
from collections import Counter
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import regen

ACCESSION = "GSE164241"
PREFIX = "GSE164nnn"
MAX_COMPRESSED = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
URL = f"https://ftp.ncbi.nlm.nih.gov/geo/series/{PREFIX}/{ACCESSION}/soft/{ACCESSION}_family.soft.gz"
SUPPLEMENT_URL = "https://ars.els-cdn.com/content/image/1-s2.0-S0092867421006309-mmc1.xlsx"
SUPPLEMENT_NAME = "GSE164241_Table_S1_demographics.xlsx"


def norm(value: str) -> str:
    return re.sub(r"[\s_-]+", " ", value).strip().casefold()


def parse_soft(path: Path) -> dict:
    samples, series_fields, current_kind, current = [], {}, None, None
    expanded = 0
    with gzip.open(path, "rt", encoding="utf-8", errors="strict") as handle:
        for raw in handle:
            expanded += len(raw.encode("utf-8"))
            if expanded > MAX_EXPANDED:
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
    declared = set(series_fields.get("Series_sample_id", []))
    observed = {sample["accession"] for sample in samples}
    if not samples or declared != observed or len(observed) != len(samples):
        raise ValueError("GEO series sample list differs from unique SAMPLE metadata records")
    if not any("oral mucosa" in title.casefold() for title in series_fields.get("Series_title", [])):
        raise ValueError("GSE164241 series title differs from expected oral mucosa atlas")
    return {"samples": samples, "series_fields": series_fields, "expanded_bytes": expanded}


def characteristics(sample: dict) -> dict[str, str]:
    result = {}
    for item in sample["fields"].get("Sample_characteristics_ch1", []):
        if ":" in item:
            key, value = item.split(":", 1)
            result[norm(key)] = value.strip()
    return result


def classify(sample: dict, char: dict[str, str]) -> str:
    text = " ".join([
        *sample["fields"].get("Sample_title", []),
        *sample["fields"].get("Sample_source_name_ch1", []),
        *sample["fields"].get("Sample_characteristics_ch1", []),
    ]).casefold()
    disease_value = norm(char.get("disease state", char.get("disease status", char.get("disease", ""))))
    is_diseased = "periodontitis" in disease_value or "periodontitis" in text or "diseased" in text
    is_gingiva = "gingiva" in text or "gingival" in text
    is_buccal = "buccal" in text
    if is_gingiva and "lad1" in disease_value:
        return "periodontitis_gingiva_added_2023"
    if is_gingiva and is_diseased:
        return "periodontitis_gingiva"
    if is_gingiva and not is_diseased:
        return "healthy_gingiva_candidate"
    if is_buccal and not is_diseased:
        return "healthy_buccal"
    return "unclassified"


def excel_column_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref)
    if not letters:
        raise ValueError(f"Malformed XLSX cell reference: {cell_ref!r}")
    number = 0
    for char in letters.group(0):
        number = number * 26 + ord(char) - ord("A") + 1
    return number - 1


def parse_demographics_xlsx(path: Path) -> list[dict]:
    """Read the simple, single-sheet Table S1 without adding an XLSX dependency."""
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        if "xl/worksheets/sheet1.xml" not in archive.namelist():
            raise ValueError("Expected Table S1 as the first worksheet")
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = ["".join(node.text or "" for node in item.findall(".//x:t", ns))
                              for item in root.findall("x:si", ns)]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    rows = []
    for row in sheet.findall(".//x:sheetData/x:row", ns):
        values = {}
        for cell in row.findall("x:c", ns):
            index = excel_column_index(cell.attrib["r"])
            cell_type = cell.attrib.get("t", "")
            value_node = cell.find("x:v", ns)
            if cell_type == "inlineStr":
                value = "".join(node.text or "" for node in cell.findall(".//x:t", ns))
            elif value_node is None:
                value = ""
            elif cell_type == "s":
                value = shared_strings[int(value_node.text)]
            else:
                value = value_node.text or ""
            values[index] = value.strip() if isinstance(value, str) else value
        if values:
            rows.append([values.get(index, "") for index in range(max(values) + 1)])
    if not rows or rows[0][:7] != ["Sample ID", "Tissue location", "Disease status", "Assay", "Sex", "Race", "Age"]:
        raise ValueError("Table S1 headings or order differ from the expected donor metadata table")
    header = rows[0][:7]
    records = []
    for values in rows[1:]:
        if len(values) < 7 or norm(str(values[3])) != "scrna seq":
            continue
        records.append(dict(zip(header, values[:7], strict=True)))
    ids = [str(row["Sample ID"]) for row in records]
    if len(records) != 29 or len(set(ids)) != len(ids):
        raise ValueError(f"Expected 29 unique scRNA-seq sample rows in Table S1; found {len(records)}")
    return records


def sample_code_root(code: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"([A-Z]+)(\d+)[a-z]*", code.strip())
    if not match:
        return None
    return match.group(1), match.group(2)


def cellranger_version(sample: dict) -> str:
    title = sample["fields"].get("Sample_title", [""])[0]
    processing = " ".join(sample["fields"].get("Sample_data_processing", []))
    versions = []
    for version, names in re.findall(r"v([0-9]+\.[0-9]+\.[0-9]+)\s*\(([^)]*)\)", processing):
        if title in {name.strip() for name in names.split(",")}:
            versions.append(version)
    if len(versions) > 1:
        raise ValueError(f"Sample appears in multiple CellRanger version lists: {title}")
    return versions[0] if versions else "not specified"


def main() -> None:
    cache = regen.DATA / "literature" / "oral-atlas-GSE164241"
    cache.mkdir(parents=True, exist_ok=True)
    soft_path = cache / f"{ACCESSION}_family.soft.gz"
    fetch_receipt = None
    if not soft_path.is_file():
        content = regen.http_bytes(URL, timeout=120)
        if len(content) > MAX_COMPRESSED:
            raise ValueError("Compressed GEO family file exceeds intake bound")
        soft_path.write_bytes(content)
        fetch_receipt = regen.record("oral-atlas-gse164241-source-fetch", {
            "accession": ACCESSION, "source_url": URL, "compressed_sha256": regen.sha256_file(soft_path),
            "compressed_bytes": len(content), "expanded_limit_bytes": MAX_EXPANDED,
        }, [soft_path])
    if soft_path.stat().st_size > MAX_COMPRESSED:
        raise ValueError("Cached GEO family file exceeds intake bound")
    parsed = parse_soft(soft_path)

    supplement_path = cache / SUPPLEMENT_NAME
    supplement_fetch_receipt = None
    if not supplement_path.is_file():
        content = regen.http_bytes(SUPPLEMENT_URL, timeout=120)
        if not content.startswith(b"PK\x03\x04") or len(content) > 10 * 1024 * 1024:
            raise ValueError("Table S1 download is not a valid, size-bounded XLSX file")
        supplement_path.write_bytes(content)
        supplement_fetch_receipt = regen.record("oral-atlas-table-s1-source-fetch", {
            "source_url": SUPPLEMENT_URL, "sha256": regen.sha256_file(supplement_path),
            "bytes": len(content), "format_check": "ZIP/XLSX signature verified",
        }, [supplement_path])
    if not zipfile.is_zipfile(supplement_path):
        raise ValueError("Cached Table S1 supplement is not a valid XLSX archive")
    table_records = parse_demographics_xlsx(supplement_path)
    table_by_id = {str(row["Sample ID"]): row for row in table_records}

    records, group_to_samples = [], {}
    for sample in parsed["samples"]:
        fields = sample["fields"]
        char = characteristics(sample)
        title = fields.get("Sample_title", [""])[0]
        category = classify(sample, char)
        root = sample_code_root(title)
        table_match = table_by_id.get(title)
        match_method = "exact_sample_id" if table_match else "unmatched"
        if table_match is None and root:
            candidates = [row for sample_id, row in table_by_id.items()
                          if sample_code_root(sample_id) == root]
            if len(candidates) == 1:
                table_match = candidates[0]
                match_method = "unique_shared_sample_code_root"
            elif len(candidates) > 1:
                raise ValueError(f"Ambiguous Table S1 match for GEO sample title {title!r}")
        if table_match:
            table_disease = norm(str(table_match["Disease status"]))
            table_tissue = norm(str(table_match["Tissue location"]))
            if (("periodontitis" in table_disease) != ("periodontitis" in category)):
                raise ValueError(f"GEO and Table S1 disease labels disagree for {title}")
            if table_tissue not in norm(char.get("tissue", "")) and norm(char.get("tissue", "")) not in table_tissue:
                raise ValueError(f"GEO and Table S1 tissue labels disagree for {title}")
            donor_code = root
            donor_group = f"{table_disease}:{root[1]}" if root else ""
            age = int(float(table_match["Age"]))
            sex = str(table_match["Sex"])
            race = str(table_match["Race"])
        else:
            donor_code, donor_group, age, sex, race = root, "", "", "", ""
        group_to_samples.setdefault(category, []).append(sample["accession"])
        records.append({
            "GSM": sample["accession"], "sample_title": title, "category": category,
            "source_name": fields.get("Sample_source_name_ch1", [""])[0],
            "characteristics": char,
            "donor_code_root": donor_code,
            "inferred_donor_group": donor_group,
            "donor_grouping_basis": "shared numeric sample-code root; Table S1 age/sex/race agree" if donor_group else "not linked",
            "Table_S1_sample_ID": str(table_match["Sample ID"]) if table_match else "",
            "Table_S1_match_method": match_method,
            "age": age, "sex": sex, "race": race,
            "cellranger_version": cellranger_version(sample),
            "platform_ID": fields.get("Sample_platform_id", [""])[0],
            "submission_date": fields.get("Sample_submission_date", [""])[0],
            "supplementary_files": fields.get("Sample_supplementary_file", []),
            "relations": fields.get("Sample_relation", []),
            "SRA_accessions": [value for value in fields.get("Sample_relation", []) if "SRA" in value],
            "library_strategy": fields.get("Sample_library_strategy", []),
        })

    matched_titles = {row["Table_S1_sample_ID"] for row in records if row["Table_S1_sample_ID"]}
    if matched_titles != set(table_by_id) or len(matched_titles) != 29:
        raise ValueError("GEO/Table S1 crosswalk does not cover all 29 original scRNA samples uniquely")
    if sum(bool(row["Table_S1_sample_ID"]) for row in records) != 29:
        raise ValueError("Unexpected number of GEO samples linked to Table S1")
    demographics_by_group = {}
    donor_groups = {}
    for row in records:
        if row["inferred_donor_group"]:
            donor_groups.setdefault(row["inferred_donor_group"], []).append(row)
    for donor, group_rows in donor_groups.items():
        signatures = {(row["age"], row["sex"], row["race"]) for row in group_rows}
        if len(signatures) != 1:
            raise ValueError(f"Demographics disagree within inferred donor code {donor}")
    for condition in ("health", "periodontitis"):
        members = [row for row in records if row["inferred_donor_group"].startswith(condition + ":")]
        unique_donors = {row["inferred_donor_group"] for row in members}
        demographics_by_group[condition] = {
            "sample_libraries": len(members), "inferred_donors": len(unique_donors),
            "donor_ages": sorted(next(row["age"] for row in members if row["inferred_donor_group"] == donor)
                                 for donor in unique_donors),
        }
    repeated_donor_groups = {key: [row["GSM"] for row in rows] for key, rows in donor_groups.items()
                             if len(rows) > 1}

    sample_path = HERE / "oral_atlas_GSE164241_sample_crosswalk.tsv"
    fieldnames = ["GSM", "sample_title", "category", "source_name", "tissue", "disease_status",
                  "Table_S1_sample_ID", "Table_S1_match_method", "age", "sex", "race",
                  "inferred_donor_group", "donor_grouping_basis", "cellranger_version",
                  "platform_ID", "submission_date", "supplementary_files", "SRA_accessions"]
    with sample_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in records:
            char = row["characteristics"]
            writer.writerow({
                "GSM": row["GSM"], "sample_title": row["sample_title"], "category": row["category"],
                "source_name": row["source_name"], "tissue": char.get("tissue", ""),
                "disease_status": char.get("disease state", char.get("disease status", char.get("disease", ""))),
                "Table_S1_sample_ID": row["Table_S1_sample_ID"],
                "Table_S1_match_method": row["Table_S1_match_method"],
                "age": row["age"], "sex": row["sex"], "race": row["race"],
                "inferred_donor_group": row["inferred_donor_group"],
                "donor_grouping_basis": row["donor_grouping_basis"],
                "cellranger_version": row["cellranger_version"], "platform_ID": row["platform_ID"],
                "submission_date": row["submission_date"],
                "supplementary_files": " | ".join(row["supplementary_files"]),
                "SRA_accessions": " | ".join(row["SRA_accessions"]),
            })

    receipt = {
        "schema_version": 1,
        "accession": ACCESSION,
        "source": "NCBI GEO official FTP series family SOFT",
        "source_url": URL,
        "source_sha256": regen.sha256_file(soft_path),
        "table_s1_source_url": SUPPLEMENT_URL,
        "table_s1_sha256": regen.sha256_file(supplement_path),
        "table_s1_record_count": len(table_records),
        "retrieved_or_cache_checked_utc": regen.now(),
        "series_title": parsed["series_fields"].get("Series_title", []),
        "pubmed_ids": parsed["series_fields"].get("Series_pubmed_id", []),
        "sample_count": len(records),
        "category_counts": {category: len(gsms) for category, gsms in sorted(group_to_samples.items())},
        "Table_S1_linkage": {"GEO_samples_linked": sum(bool(row["Table_S1_sample_ID"]) for row in records),
                              "Table_S1_sample_IDs": len(table_by_id),
                              "unmatched_GEO_samples": [row["GSM"] for row in records if not row["Table_S1_sample_ID"]],
                              "match_methods": dict(Counter(row["Table_S1_match_method"] for row in records))},
        "sample_counts_by_category": {category: len(gsms) for category, gsms in sorted(group_to_samples.items())},
        "inferred_donor_summary": demographics_by_group,
        "repeated_sample_codes_within_inferred_donor": repeated_donor_groups,
        "processing_versions": dict(Counter(row["cellranger_version"] for row in records)),
        "sample_records": records,
        "limits": {
            "donor_groups_are_inferred_from_shared_numeric_sample_code_and_matching_age_sex_race_not_an_explicit_GEO_donor_ID": True,
            "ID080UST_added_in_2023_is_absent_from_original_Table_S1_and_kept_separate": True,
            "healthy_buccal_and_gingival_samples_are_separate_tissues_not_exchangeable_age_controls": True,
            "CellRanger_versions_must_be_considered_in_any_count_level_comparison": True,
            "cell_level_counts_or_pseudobulk_not_performed": True,
            "multiple_samples_from_a_donor_must_not_be_counted_as_independent_donors": True,
        },
        "local_provenance_receipts": {"geo_fetch": fetch_receipt.name if fetch_receipt else "reused_verified_cache",
                                       "table_s1_fetch": supplement_fetch_receipt.name if supplement_fetch_receipt else "reused_verified_cache"},
    }
    receipt_path = HERE / "oral_atlas_GSE164241_intake_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    regen.record("oral-atlas-gse164241-intake", {"accession": ACCESSION}, [sample_path, receipt_path])
    print(json.dumps({"accession": ACCESSION, "samples": len(records),
                      "category_counts": receipt["sample_counts_by_category"],
                      "table_s1_linkage": receipt["Table_S1_linkage"],
                      "inferred_donor_summary": demographics_by_group,
                      "repeated_sample_codes": repeated_donor_groups,
                      "processing_versions": receipt["processing_versions"],
                      "crosswalk": str(sample_path), "receipt": str(receipt_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
