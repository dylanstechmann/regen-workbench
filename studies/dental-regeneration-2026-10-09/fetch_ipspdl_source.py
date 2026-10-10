"""Fetch the exact open-access iPS-PDL article and record private provenance."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen


def main():
    regen.ensure_dirs()
    doi = "10.4012/dmj.2025-235"
    url = "https://www.jstage.jst.go.jp/article/dmj/advpub/0/advpub_2025-235/_pdf"
    raw = regen.http_bytes(url)
    if not raw.startswith(b"%PDF-") or len(raw) < 10_000:
        raise ValueError("Response is not the expected article PDF")
    target = regen.DATA / "literature" / "dmj-2025-235-2026-10-09.pdf"
    target.write_bytes(raw)
    provenance = regen.record("dental-ipspdl-fulltext", {"doi": doi, "url": url}, [target])
    receipt = {
        "title": "Functional evaluation of iPS cell-derived periodontal ligament-like cells",
        "doi": doi,
        "url": url,
        "retrieved_utc": regen.now(),
        "response_sha256": regen.sha256_file(target),
        "local_provenance_receipt": provenance.name,
        "license": "CC BY 4.0; source-stated open license",
        "scope": "Exact article PDF fetched through Regen Workbench. Hash identifies retrieved bytes, not independent validation of the article's claims.",
    }
    out = Path(__file__).with_name("ipspdl_receipt.json")
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"doi": doi, "bytes": len(raw)}))


if __name__ == "__main__":
    main()
