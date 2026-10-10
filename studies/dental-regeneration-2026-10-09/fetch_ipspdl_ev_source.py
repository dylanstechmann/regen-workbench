"""Fetch the open iPS-PDL extracellular-vesicle article and record provenance."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen


def main() -> None:
    regen.ensure_dirs()
    doi = "10.3389/fcell.2026.1821829"
    url = (
        "https://www.frontiersin.org/journals/cell-and-developmental-biology/"
        "articles/10.3389/fcell.2026.1821829/pdf"
    )
    raw = regen.http_bytes(url)
    if not raw.startswith(b"%PDF-") or len(raw) < 10_000:
        raise ValueError("Response is not the expected article PDF")
    target = regen.DATA / "literature" / "frontiers-fcell-2026-1821829.pdf"
    target.write_bytes(raw)
    provenance = regen.record(
        "dental-ipspdl-ev-fulltext", {"doi": doi, "url": url}, [target]
    )
    receipt = {
        "title": (
            "Extracellular vesicles from induced pluripotent stem cell-derived "
            "periodontal ligament cells enhance proliferation and migration "
            "of periodontal ligament cells for periodontal regeneration"
        ),
        "doi": doi,
        "url": url,
        "retrieved_utc": regen.now(),
        "response_sha256": regen.sha256_file(target),
        "local_provenance_receipt": provenance.name,
        "license": "CC BY 4.0; source-stated open license",
        "scope": (
            "Exact article PDF fetched through Regen Workbench. The hash "
            "identifies retrieved bytes, not independent validation of claims."
        ),
    }
    out = Path(__file__).with_name("ipspdl_ev_receipt.json")
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"doi": doi, "bytes": len(raw)}))


if __name__ == "__main__":
    main()
