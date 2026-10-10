"""Qualify public GEO metadata for the human PDL maturity single-cell study."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen


ACCESSION = "GSE306722"
URL = (
    "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE306nnn/"
    f"{ACCESSION}/soft/{ACCESSION}_family.soft.gz"
)
LIMIT = 8 * 1024 * 1024
EXPANDED_LIMIT = 32 * 1024 * 1024


def parse_soft(text: str, accession: str = ACCESSION) -> dict:
    """Parse only SOFT metadata fields; expression matrices are never read."""
    entities: list[dict] = []
    current = None
    for line in text.splitlines():
        if line.startswith("^") and " = " in line:
            kind, identifier = line[1:].split(" = ", 1)
            current = {"kind": kind.upper(), "accession": identifier, "fields": {}}
            entities.append(current)
        elif current is not None and line.startswith("!") and " = " in line:
            key, value = line[1:].split(" = ", 1)
            current["fields"].setdefault(key, []).append(value)

    series = [item for item in entities if item["kind"] == "SERIES" and item["accession"] == accession]
    samples = [item for item in entities if item["kind"] == "SAMPLE"]
    if len(series) != 1 or not samples:
        raise ValueError("SOFT response does not contain the requested series and samples")
    sample_ids = [item["accession"] for item in samples]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("Duplicate GEO sample accession")
    declared = set(series[0]["fields"].get("Series_sample_id", []))
    if declared != set(sample_ids):
        raise ValueError("Series sample list does not match the sample records")
    return {"series": series[0], "samples": samples}


def values(fields: dict, *keys: str) -> list[str]:
    return [value for key in keys for value in fields.get(key, [])]


def stage_for(sample: dict) -> str:
    fields = sample["fields"]
    text = " ".join(values(fields, "Sample_title", "Sample_source_name_ch1", "Sample_characteristics_ch1"))
    if re.search(r"\bimmature\b", text, flags=re.IGNORECASE):
        return "immature"
    if re.search(r"\bmature\b", text, flags=re.IGNORECASE):
        return "mature"
    return "unclassified"


def summarize(metadata: dict, raw: bytes, provenance_name: str, retrieved: str) -> dict:
    series_fields = metadata["series"]["fields"]
    samples = []
    for sample in metadata["samples"]:
        fields = sample["fields"]
        supplementary = [
            value
            for key, entries in fields.items()
            if key.startswith("Sample_supplementary_file")
            for value in entries
        ]
        samples.append({
            "geo_sample": sample["accession"],
            "stage_label_from_source_fields": stage_for(sample),
            "title": values(fields, "Sample_title"),
            "source_name": values(fields, "Sample_source_name_ch1"),
            "organism": values(fields, "Sample_organism_ch1"),
            "characteristics": values(fields, "Sample_characteristics_ch1"),
            "relations": values(fields, "Sample_relation"),
            "supplementary_files": supplementary,
            "data_processing": values(fields, "Sample_data_processing"),
            "donor_id": None,
            "individual_tooth_id": None,
        })

    stage_counts = {stage: sum(item["stage_label_from_source_fields"] == stage for item in samples)
                    for stage in ("immature", "mature", "unclassified")}
    return {
        "schema_version": 1,
        "accession": ACCESSION,
        "source_url": URL,
        "retrieved_utc": retrieved,
        "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_response_bytes": len(raw),
        "local_provenance_receipt": provenance_name,
        "series": {
            key: series_fields.get(key, [])
            for key in ("Series_title", "Series_status", "Series_type", "Series_summary",
                        "Series_overall_design", "Series_pubmed_id", "Series_sample_id")
        },
        "n_geo_sample_records": len(samples),
        "sample_records_by_stage_label": stage_counts,
        "samples": samples,
        "qualification": {
            "expression_values_parsed": False,
            "individual_donor_ids_found_in_geo_metadata": False,
            "individual_tooth_ids_found_in_geo_metadata": False,
            "biological_replicates_qualified": False,
            "donor_held_out_comparison_eligible": False,
            "recommended_use": "Source-scoped cell-state and marker-pattern description only, after expression-matrix provenance review.",
            "limits": (
                "GEO sample records are archive records, not proof of independent donors. "
                "The publication reports 20 immature and 20 mature teeth, but the retrieved "
                "GEO family metadata exposes group-level sample records without tooth-to-donor "
                "or cell-to-donor mapping. Cells must not be treated as biological replicates. "
                "Developmental root maturity is not an aging comparison."
            ),
        },
    }


def main() -> None:
    regen.ensure_dirs()
    raw = regen.http_bytes(URL, timeout=60)
    if len(raw) > LIMIT:
        raise ValueError("Compressed GEO family metadata exceeds the bounded intake limit")
    expanded = gzip.decompress(raw)
    if len(expanded) > EXPANDED_LIMIT:
        raise ValueError("Expanded GEO family metadata exceeds the bounded intake limit")
    metadata = parse_soft(expanded.decode("utf-8"))

    raw_path = regen.DATA / "literature" / f"{ACCESSION}-family-metadata.soft.gz"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw)
    provenance = regen.record(
        "dental-pdls-maturity-metadata",
        {"accession": ACCESSION, "url": URL, "scope": "GEO SOFT metadata only"},
        [raw_path],
    )
    report = summarize(metadata, raw, provenance.name, regen.now())
    target = Path(__file__).with_name("pdls_maturity_metadata_receipt.json")
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"accession": ACCESSION, "sample_records": report["n_geo_sample_records"],
                      "stage_counts": report["sample_records_by_stage_label"],
                      "raw_sha256": report["raw_response_sha256"]}))


if __name__ == "__main__":
    main()
