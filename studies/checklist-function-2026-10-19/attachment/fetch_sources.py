"""Fetch only declared primary public sources, retaining actual byte receipts."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = ROOT / "data/literature/checklist-function-2026-10-19/attachment"
SOURCES = {
    "magnetic2024.xml": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11465412/fullTextXML",
    "viscoelastic2024.xml": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11095218/fullTextXML",
    "native_tension2018.xml": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6251174/fullTextXML",
    "magnetic2024.html": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11465412/",
    "magnetic2024_supp.docx": "https://pmc.ncbi.nlm.nih.gov/articles/instance/11465412/bin/sj-docx-1-jdr-10.1177_00220345241264792.docx",
    "magnetic2024_publisher_supp.docx": "https://journals.sagepub.com/doi/suppl/10.1177/00220345241264792/suppl_file/sj-docx-1-jdr-10.1177_00220345241264792.docx",
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="+", choices=list(SOURCES), help="Explicit sources only; no automatic acquisition")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "tools"))
    import regen
    CACHE.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE / "source_receipts.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"actual_fetches": []}
    for name in args.names:
        path = CACHE / name
        prior = [r for r in manifest["actual_fetches"] if r["cache_path"] == path.relative_to(ROOT).as_posix()]
        if path.exists() and prior:
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != prior[-1]["sha256"]:
                raise ValueError("Cached source differs from its actual-fetch receipt")
            print(name, "verified; no fetch")
            continue
        req = Request(SOURCES[name], headers={"User-Agent": "regen-workbench-public-research/1"})
        try:
            with urlopen(req, timeout=60) as response:
                raw = response.read(8_000_001)
                final_url, content_type = response.url, response.headers.get_content_type()
        except HTTPError as exc:
            manifest.setdefault("failed_attempts", []).append({"source_url": SOURCES[name], "http_status": exc.code,
                "retained_source_payload": False, "observed_at_utc": regen.now(), "fetch_receipt_created": False})
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
            print(name, "HTTP", exc.code, "no retained source document")
            continue
        if len(raw) > 8_000_000:
            raise ValueError("Source exceeds declared eight-megabyte cap")
        path.write_bytes(raw)
        receipt = regen.record("checklist-attachment-function-source-fetch", {"url": SOURCES[name], "final_url": final_url}, [path])
        row = {"source_url": SOURCES[name], "final_url": final_url,
               "cache_path": path.relative_to(ROOT).as_posix(), "content_type": content_type,
               "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
               "receipt_path": receipt.relative_to(ROOT).as_posix(), "fetched_at_utc": regen.now()}
        row["expected_document_received"] = not name.endswith(".docx") or raw.startswith(b"PK\x03\x04")
        if not row["expected_document_received"]:
            row["classification"] = "HTML_download_challenge_not_a_DOCX"
        manifest["actual_fetches"].append(row)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(name, len(raw), "actual fetch retained")

if __name__ == "__main__":
    main()
