"""Bounded retrieval of two source-declared GEO metadata families; no count matrices."""

import gzip
import hashlib
import io
import json
import sys
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen

ACCESSIONS = ("GSE307437", "GSE184749")
LIMIT = 8 * 1024 * 1024


def parse_metadata(text, accession):
    """Retain series/sample metadata fields; never parse expression or platform tables."""
    entities = []
    current = None
    for line in text.splitlines():
        if line.startswith("^") and " = " in line:
            kind, identifier = line[1:].split(" = ", 1)
            current = {"kind": kind.upper(), "accession": identifier, "fields": {}}
            entities.append(current)
        elif current is not None and line.startswith("!") and " = " in line:
            key, value = line[1:].split(" = ", 1)
            current["fields"].setdefault(key, []).append(value)
    series = [entry for entry in entities if entry["kind"] == "SERIES" and entry["accession"] == accession]
    if len(series) != 1:
        raise ValueError("Retrieved SOFT metadata does not identify the requested series")
    samples = [entry for entry in entities if entry["kind"] == "SAMPLE"]
    identifiers = [entry["accession"] for entry in samples]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate GEO sample accession")
    if set(series[0]["fields"].get("Series_sample_id", [])) != set(identifiers):
        raise ValueError("Series sample list does not match metadata sample entities")
    return {"series": series[0], "samples": samples,
            "limits": "GSM accessions are source sample records, not certified independent donors. No expression values parsed, license inferred or biological function validated."}


def summarize_metadata(metadata):
    rows, conflicts = [], []
    for sample in metadata["samples"]:
        fields = sample["fields"]
        traits = {}
        for characteristic in fields.get("Sample_characteristics_ch1", []):
            key, separator, value = characteristic.partition(": ")
            if separator:
                traits.setdefault(key, []).append(value)
        titles = fields.get("Sample_title", [])
        # Preserve a source conflict without assigning a corrected tissue label.
        if any(t.startswith("Incisors_") and "Molars" not in t for t in titles) and any("molar" in t.lower() for t in traits.get("tissue", [])):
            conflicts.append({"sample_accession": sample["accession"], "issue": "Incisor title versus molar tissue characteristic", "resolution": "unresolved; neither field overrides the other"})
        rows.append({"sample_accession": sample["accession"], "source_titles": titles,
                     "declared_characteristics": traits, "independent_donor_id": None,
                     "clone_id": None, "culture_batch_id": None})
    return {"accession": metadata["series"]["accession"], "n_source_sample_records": len(rows), "samples": rows,
            "source_annotation_conflicts": conflicts,
            "declared_cell_line_labels": sorted({value for row in rows for value in row["declared_characteristics"].get("cell line", [])}),
            "declared_experiment_types": sorted({value for row in rows for value in row["declared_characteristics"].get("experiment type", [])}),
            "expression_values_parsed": False, "matrix_columns_qualified": False,
            "independent_donors_qualified": False, "reuse_license_qualified": False,
            "eligible_for_donor_heldout_claim": False,
            "limits": "Unknown identity fields are gaps in this intake, not proof the source never recorded them. Replicate labels and cell counts do not establish independent donors. Metadata conflicts require source review."}


def summarize_cached():
    receipt = json.loads((Path(__file__).parent / "geo_metadata_receipt.json").read_text(encoding="utf-8"))
    rows = []
    for record in receipt["records"]:
        if record["status"] != "metadata_retrieved":
            continue
        accession = record["accession"]
        raw_path = regen.DATA / "literature" / f"{accession}-metadata-2026-10-09.soft.gz"
        path = raw_path.with_suffix(".metadata.json")
        if regen.sha256_file(raw_path) != record["response_sha256"] or regen.sha256_file(path) != record["parsed_metadata_sha256"]:
            raise ValueError("Cached GEO metadata does not match retrieval receipt")
        metadata = parse_metadata(gzip.decompress(raw_path.read_bytes()).decode("utf-8"), accession)
        if metadata != json.loads(path.read_text(encoding="utf-8")):
            raise ValueError("Cached parsed metadata differs from the source metadata family")
        rows.append({**summarize_metadata(metadata),
                     "source_url": record["url"], "metadata_response_sha256": record["response_sha256"]})
    target = Path(__file__).parent / "geo_qualification.json"
    target.write_text(json.dumps({"schema_version": 1, "origin": "retrieved_source_metadata", "assisted_by": "AI", "datasets": rows}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"dataset_metadata_reports": len(rows)}))


def main():
    regen.ensure_dirs()
    public = []
    for accession in ACCESSIONS:
        prefix = accession[:-3] + "nnn"
        url = f"https://ftp.ncbi.nlm.nih.gov/geo/series/{prefix}/{accession}/soft/{accession}_family.soft.gz"
        try:
            raw = regen.http_bytes(url, timeout=30)
        except HTTPError as error:
            public.append({"accession": accession, "url": url, "retrieved_utc": regen.now(),
                           "status": "retrieval_failed", "http_status": error.code})
            continue
        if len(raw) > LIMIT:
            raise ValueError("GEO metadata response exceeds bounded intake size")
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as handle:
            expanded = handle.read(LIMIT + 1)
        if len(expanded) > LIMIT:
            raise ValueError("Expanded GEO metadata exceeds bounded intake size")
        metadata = parse_metadata(expanded.decode("utf-8"), accession)
        path = regen.DATA / "literature" / f"{accession}-metadata-2026-10-09.soft.gz"
        path.write_bytes(raw)
        parsed = path.with_suffix(".metadata.json")
        parsed.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        receipt = regen.record("dental-geo-metadata", {"accession": accession, "url": url}, [path, parsed])
        public.append({"accession": accession, "url": url, "retrieved_utc": regen.now(),
                       "status": "metadata_retrieved", "response_sha256": hashlib.sha256(raw).hexdigest(),
                       "parsed_metadata_sha256": regen.sha256_file(parsed),
                       "sample_accessions": [s["accession"] for s in metadata["samples"]],
                       "series_fields": {key: metadata["series"]["fields"].get(key, []) for key in
                                         ("Series_geo_accession", "Series_status", "Series_type", "Series_pubmed_id", "Series_sample_id")},
                       "local_provenance_receipt": receipt.name,
                       "expression_values_parsed": False, "independent_donors_qualified": False,
                       "reuse_license_qualified": False})
    target = Path(__file__).parent / "geo_metadata_receipt.json"
    target.write_text(json.dumps({"scope": "Exact-accession metadata intake, not RNA analysis or dataset eligibility", "records": public}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": [{"accession": r["accession"], "status": r["status"], "sample_records": len(r.get("sample_accessions", []))} for r in public]}))
    summarize_cached()


if __name__ == "__main__":
    if sys.argv[1:] == ["--summarize-cached"]:
        summarize_cached()
    elif not sys.argv[1:]:
        main()
    else:
        raise SystemExit("Usage: fetch_geo_metadata.py [--summarize-cached]")
