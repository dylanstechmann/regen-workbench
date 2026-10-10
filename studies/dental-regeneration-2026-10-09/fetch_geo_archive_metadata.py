"""Inspect the two DLX3-KO GEO samples' linked public archive metadata.

The intake is limited to the two KO BioSamples and their two linked SRA
experiments. Raw XML and Regen provenance receipts stay under ignored data/.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen

SAMPLES = {
    "SAMN51222981": "GSM9224212",
    "SAMN51222980": "GSM9224213",
}
EXPERIMENTS = {
    "SRX30400800": "GSM9224212",
    "SRX30400801": "GSM9224213",
}
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def one_text(element, path):
    value = element.findtext(path)
    return value.strip() if value and value.strip() else None


def fetch_record(database, accession, sample_accession):
    url = EUTILS + "?" + urlencode(
        {"db": database, "id": accession, "retmode": "xml"}
    )
    raw = regen.http_bytes(url)
    root = ET.fromstring(raw)
    match = next(
        (node for node in root.iter() if node.get("accession") == accession), None
    )
    if match is None:
        raise ValueError(f"Response does not contain requested accession {accession}")

    if database == "biosample":
        attrs = []
        for attribute in match.findall(".//Attribute"):
            attrs.append(
                {
                    "name": attribute.get("attribute_name"),
                    "harmonized_name": attribute.get("harmonized_name"),
                    "value": (attribute.text or "").strip(),
                }
            )
        record = {
            "database": database,
            "accession": accession,
            "geo_sample": sample_accession,
            "title": one_text(match, "Description/Title"),
            "organism": one_text(match, "Description/Organism/OrganismName"),
            "attributes": attrs,
            "identifiers": [
                {"db": identifier.get("db"), "id": (identifier.text or "").strip()}
                for identifier in match.findall("./Ids/Id")
            ],
            "links": [
                {
                    "target": link.get("target"),
                    "label": link.get("label"),
                    "url_or_id": (link.text or "").strip(),
                }
                for link in match.findall("./Links/Link")
            ],
        }
    elif database == "sra":
        descriptor = match.find("./DESIGN/LIBRARY_DESCRIPTOR")
        sample = match.find("./DESIGN/SAMPLE_DESCRIPTOR")
        platform = match.find("./PLATFORM")
        record = {
            "database": database,
            "accession": accession,
            "geo_sample": sample_accession,
            "title": one_text(match, "TITLE"),
            "description": one_text(match, "DESCRIPTION"),
            "sra_sample_accession": sample.get("accession") if sample is not None else None,
            "geo_sample_identifier": (
                next(
                    (
                        item.text.strip()
                        for item in sample.findall(".//EXTERNAL_ID")
                        if item.get("namespace") == "GEO" and item.text
                    ),
                    None,
                )
                if sample is not None
                else None
            ),
            "library_descriptor": (
                {
                    child.tag: (child.text or "").strip()
                    for child in descriptor.iter()
                    if child is not descriptor and (child.text or "").strip()
                }
                if descriptor is not None
                else {}
            ),
            "instrument_model": (
                (platform.findtext(".//INSTRUMENT_MODEL") or "").strip() or None
                if platform is not None
                else None
            ),
        }
    else:
        raise ValueError(f"Unsupported database: {database}")

    out = regen.DATA / "literature" / f"{accession}-archive-metadata.xml"
    out.write_bytes(raw)
    provenance = regen.record(
        "dental-geo-archive-metadata",
        {"database": database, "accession": accession, "url": url},
        [out],
    )
    return {
        "record": record,
        "url": url,
        "response_sha256": regen.sha256_file(out),
        "local_provenance_receipt": provenance.name,
    }


def main():
    regen.ensure_dirs()
    results = []
    for database, accessions in (("biosample", SAMPLES), ("sra", EXPERIMENTS)):
        for accession, gsm in accessions.items():
            results.append(fetch_record(database, accession, gsm))

    normalized = {item["record"]["accession"]: item["record"] for item in results}
    for gsm, biosample, experiment in (
        ("GSM9224212", "SAMN51222981", "SRX30400800"),
        ("GSM9224213", "SAMN51222980", "SRX30400801"),
    ):
        if normalized[biosample]["geo_sample"] != gsm:
            raise ValueError(f"BioSample mapping mismatch for {gsm}")
        if normalized[experiment]["geo_sample"] != gsm:
            raise ValueError(f"SRA mapping mismatch for {gsm}")
        sra_sample = normalized[experiment]["sra_sample_accession"]
        biosample_sra_id = next(
            (
                item["id"]
                for item in normalized[biosample]["identifiers"]
                if item["db"] == "SRA"
            ),
            None,
        )
        if sra_sample and biosample_sra_id and sra_sample != biosample_sra_id:
            raise ValueError(f"SRA sample mismatch for {gsm}")
        if normalized[experiment]["geo_sample_identifier"] != gsm:
            raise ValueError(f"SRA-to-GEO mapping mismatch for {gsm}")

    report = {
        "scope": "Two DLX3-KO sample records only; archive metadata check, not FASTQ analysis",
        "retrieved_utc": regen.now(),
        "records": results,
        "qualification": {
            "geo_samples": ["GSM9224212", "GSM9224213"],
            "clone_to_sample_mapping_found": False,
            "differentiation_batch_mapping_found": False,
            "interpretation": (
                "The linked public BioSample and SRA XML records were checked for "
                "a KO-10/KO-13-to-library mapping and named independent differentiation "
                "batches. No such mapping was present. This is an archive-field result, "
                "not proof the investigators lack these records elsewhere."
            ),
        },
        "raw_xml": "Ignored under data/literature; each retrieval has a Regen SHA-256 receipt.",
    }
    target = Path(__file__).with_name("geo_archive_metadata_audit.json")
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"records_retrieved": len(results), "report": str(target)}))


if __name__ == "__main__":
    main()
