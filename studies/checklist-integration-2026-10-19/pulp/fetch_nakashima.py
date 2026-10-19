"""Explicit bounded primary-source fetch; writes provenance only after retrieval."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5345141/fullTextXML"
CACHE = ROOT / "data/literature/checklist-integration-2026-10-19/pulp/nakashima2017.xml"

def main():
    manifest = HERE / "source_receipts.json"
    if CACHE.exists() and manifest.exists():
        row = json.loads(manifest.read_text(encoding="utf-8"))["actual_fetches"][0]
        if hashlib.sha256(CACHE.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Cached primary source differs from actual-fetch receipt")
        print("Primary source hash matches; no fetch")
        return
    with urlopen(Request(URL, headers={"User-Agent": "regen-workbench-public-research/1"}), timeout=60) as response:
        raw = response.read(10_000_001)
        content_type, final_url = response.headers.get_content_type(), response.url
    if len(raw) > 10_000_000:
        raise ValueError("Source exceeds bounded ten-megabyte intake")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(raw)
    sys.path.insert(0, str(ROOT / "tools"))
    import regen
    receipt = regen.record("checklist-pulp-source-fetch", {"url": URL, "final_url": final_url}, [CACHE])
    manifest.write_text(json.dumps({"source_set": "Nakashima2017 human five-patient primary pilot; no second source yet required", "actual_fetches": [{
        "source_url": URL, "final_url": final_url, "content_type": content_type,
        "cache_path": CACHE.relative_to(ROOT).as_posix(), "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(), "actual_fetch_receipt": receipt.relative_to(ROOT).as_posix(),
        "fetched_at_utc": regen.now()}]}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Actual primary source retained:", len(raw), "bytes")

if __name__ == "__main__":
    main()
