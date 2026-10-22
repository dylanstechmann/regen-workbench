"""Bounded actual retrieval. No study analysis or figure acquisition occurs here."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "data/literature/checklist-delivery-engineering-2026-10-22"
SOURCES = {
    "original_xml": ("https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7735425/fullTextXML", "Cheng2020_primary.xml", 5_000_000),
    "main_xml": ("https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12873177/fullTextXML", "Moore2026_primary.xml", 5_000_000),
    "figure2": ("https://media.springernature.com/lw685/springer-static/image/art%3A10.1038%2Fs41467-025-68103-7/MediaObjects/41467_2025_68103_Fig2_HTML.png", "Moore2026_Fig2.png", 5_000_000),
}

def fetch(key: str) -> dict:
    url, filename, cap = SOURCES[key]
    CACHE.mkdir(parents=True, exist_ok=True)
    destination = CACHE / filename
    if destination.exists():
        raise FileExistsError(destination)
    receipt = {"source_id": key, "requested_url": url, "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "max_bytes": cap, "timeout_seconds": 60, "output_relative_path": str(destination.relative_to(ROOT)).replace("\\", "/")}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "regen-workbench-source-audit/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read(cap + 1)
            receipt.update(status=response.status, final_url=response.url, content_type=response.headers.get("Content-Type"))
        receipt["response_bytes"] = len(raw)
        if len(raw) > cap:
            receipt["outcome"] = "cap_exceeded_response_discarded"
        else:
            destination.write_bytes(raw)
            receipt.update(outcome="response_retained_not_yet_qualified", bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    except (urllib.error.URLError, TimeoutError) as error:
        receipt.update(outcome="request_failed", error=str(error))
    receipt_path = ROOT / "data/provenance" / f"{time.time_ns()}_checklist-delivery-source-fetch.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**receipt, "receipt": str(receipt_path.relative_to(ROOT)).replace("\\", "/")}))
    return receipt

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", choices=SOURCES)
    fetch(parser.parse_args().source)
