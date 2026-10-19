"""Bounded primary-source intake for independent oral age-reference screening."""
from __future__ import annotations

import hashlib
import argparse
import json
from pathlib import Path
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = ROOT / "data/literature/checklist-aging-followup-2026-10-19"
MAX_BYTES = 32 * 1024 * 1024
SOURCES = [
    {"id": accession, "filename": accession + "_family.soft.gz",
     "url": f"https://ftp.ncbi.nlm.nih.gov/geo/series/{accession[:-3]}nnn/{accession}/soft/{accession}_family.soft.gz",
     "purpose": "Official donor, age, sex, tissue, phenotype and library metadata"}
    for accession in ["GSE173078", "GSE111523", "GSE133603", "GSE224044", "GSE312885"]
] + [
    {"id": "cilia_aging_primary", "filename": "PMC13354758.xml",
     "url": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13354758/fullTextXML",
     "purpose": "Independent 2026 human healthy-gingiva single-cell aging source, methods and data availability"}
] + [{"id": "GSE173078_counts", "filename": "GSE173078_rnaseq_raw_counts.txt.gz",
      "url": "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE173nnn/GSE173078/suppl/GSE173078_rnaseq_raw_counts.txt.gz",
      "purpose": "Small official integer gene-count matrix; download only after metadata qualification"},
     {"id": "HGNC_CXCL8", "filename": "HGNC_CXCL8.json",
      "url": "https://rest.genenames.org/fetch/symbol/CXCL8",
      "purpose": "Official previous-symbol mapping for a separately labelled post-outcome annotation sensitivity"}]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=[source["id"] for source in SOURCES], nargs="+")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "tools"))
    import regen
    CACHE.mkdir(parents=True, exist_ok=True)
    receipt_path = HERE / "source_receipts.json"
    existing = json.loads(receipt_path.read_text(encoding="utf-8"))["sources"] if receipt_path.exists() else []
    receipts = {row["id"]: row for row in existing}
    for source in SOURCES:
        if args.only and source["id"] not in args.only:
            continue
        path = CACHE / source["filename"]
        if path.exists():
            expected = receipts.get(source["id"], {}).get("sha256")
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError(f"Existing cache is not pinned by receipt: {path.name}")
            print(json.dumps({"source": source["id"], "cache": "verified_no_fetch"}), flush=True)
            continue
        headers = {"User-Agent": "regen-workbench/1.0"}
        if source["filename"].endswith(".json"):
            headers["Accept"] = "application/json"
        request = urllib.request.Request(source["url"], headers=headers)
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read(MAX_BYTES + 1)
            final_url = response.url
        if not raw or len(raw) > MAX_BYTES:
            raise ValueError(f"Empty/over-bound source: {source['id']}")
        if source["filename"].endswith(".gz") and not raw.startswith(b"\x1f\x8b"):
            raise ValueError("Official GEO source did not return gzip data")
        if source["filename"].endswith(".xml") and b"<article" not in raw[:1000]:
            raise ValueError("Primary full text did not return article XML")
        path.write_bytes(raw)
        provenance = regen.record("checklist-independent-oral-reference-fetch", source, [path])
        expected = receipts.get(source["id"], {}).get("sha256")
        if expected and hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("New official source differs from the pinned receipt; qualify the update separately")
        row = {**source, "final_url": final_url, "local_path": str(path.relative_to(ROOT)).replace("\\", "/"),
               "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
               "provenance_path": str(provenance.relative_to(ROOT)).replace("\\", "/")}
        receipts[source["id"]] = row
        print(json.dumps({"source": source["id"], "bytes": len(raw)}), flush=True)
        # Preserve each actual fetch even if a later independent source fails.
        receipt_path.write_text(json.dumps({"schema_version": 1, "review_date": "2026-10-19",
            "scope": "Focused primary-source qualification, not an exhaustive review", "sources": list(receipts.values())}, indent=2)
            + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
