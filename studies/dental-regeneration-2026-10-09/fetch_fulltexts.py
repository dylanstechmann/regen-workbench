"""Retrieve three exact primary full texts privately and record response hashes."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen


def main():
    regen.ensure_dirs()
    rows = []
    for pmcid in ("PMC4761216", "PMC12311062", "PMC12855574"):
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
        raw = regen.http_bytes(url)
        root = ET.fromstring(raw)
        ids = {e.get("pub-id-type"): e.text for e in root.findall(".//article-meta/article-id")}
        if ids.get("pmcid", ids.get("pmc")) not in {pmcid, pmcid[3:]}:
            raise ValueError(f"Retrieved article identity does not match {pmcid}")
        target = regen.DATA / "literature" / f"{pmcid}-fulltext-2026-10-09.xml"
        target.write_bytes(raw)
        receipt = regen.record("dental-primary-fulltext", {"pmcid": pmcid, "url": url}, [target])
        rows.append({"pmcid": pmcid, "doi": ids.get("doi"), "url": url,
                     "retrieved_utc": regen.now(), "response_sha256": regen.sha256_file(target),
                     "local_provenance_receipt": receipt.name})
    public = {"scope": "Three exact primary articles; private full texts, public retrieval receipts. Not a systematic review.", "records": rows}
    (Path(__file__).parent / "fulltext_receipt.json").write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"retrieved_articles": len(rows)}))


if __name__ == "__main__":
    main()
