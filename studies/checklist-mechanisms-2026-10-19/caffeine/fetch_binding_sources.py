"""Bounded official primary-source intake for a buffer binding feasibility model."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = ROOT / "data/literature/checklist-binding-2026-10-19"
SOURCES = [
    {"id": "WP6_sensor", "pmcid": "PMC8725816", "filename": "WP6_primary.xml",
     "purpose": "Measured caffeine and methylxanthine binding in a buffer sensor study"},
    {"id": "P6AS_sequestration", "pmcid": "PMC10281757", "filename": "P6AS_primary.xml",
     "purpose": "Different host/guest preclinical sequestration comparator; no transfer of constants"},
]

def main():
    sys.path.insert(0, str(ROOT / "tools"))
    import regen
    CACHE.mkdir(parents=True, exist_ok=True)
    receipt_path = HERE / "source_receipts.json"
    rows = json.loads(receipt_path.read_text(encoding="utf-8"))["sources"] if receipt_path.exists() else []
    receipts = {row["id"]: row for row in rows}
    for source in SOURCES:
        path = CACHE / source["filename"]
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != receipts.get(source["id"], {}).get("sha256"):
                raise ValueError("Cache is not pinned by a receipt")
            continue
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{source['pmcid']}/fullTextXML"
        request = urllib.request.Request(url, headers={"User-Agent": "regen-workbench/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read(2_000_001)
                final_url = response.url
        except urllib.error.HTTPError as exc:
            print(json.dumps({"id": source["id"], "url": url, "status": exc.code, "result": "no_file_or_fetch_provenance"}))
            continue
        if not raw or len(raw) > 2_000_000 or ET.fromstring(raw).tag != "article":
            raise ValueError("Expected bounded article XML")
        path.write_bytes(raw)
        provenance = regen.record("checklist-buffer-binding-source-fetch", {**source, "url": url}, [path])
        receipts[source["id"]] = {**source, "url": url, "final_url": final_url,
            "local_path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(), "provenance_path": provenance.relative_to(ROOT).as_posix()}
        receipt_path.write_text(json.dumps({"schema_version": 1, "review_date": "2026-10-19",
            "sources": list(receipts.values())}, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"id": source["id"], "bytes": len(raw)}))

if __name__ == "__main__":
    main()
