"""Bounded primary-source metadata intake through the workbench's HTTP/provenance tools."""

import json
import sys
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen

QUERY = "EXT_ID:19666587 OR EXT_ID:33579703 OR EXT_ID:28620633 OR EXT_ID:41624073 OR DOI:10.1186/s13287-016-0288-1 OR DOI:10.1038/s41368-026-00429-4 OR DOI:10.1038/s41392-025-02320-w OR EXT_ID:40373211 OR EXT_ID:27096365 OR EXT_ID:29160308 OR DOI:10.1038/s41586-019-1161-z OR DOI:10.1038/s41586-019-1711-4"


def main():
    regen.ensure_dirs()
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urlencode({"query": QUERY, "format": "json", "resultType": "core", "pageSize": 20})
    document = regen.http_json(url)
    target = regen.DATA / "literature" / "dental-genome-core-2026-10-09.json"
    target.write_text(json.dumps(document, indent=2), encoding="utf-8")
    receipt = regen.record("dental-genome-metadata", {"query": QUERY, "url": url}, [target])
    rows = document.get("resultList", {}).get("result", [])
    public = {"retrieved_utc": regen.now(), "scope": "Exact-ID/DOI metadata retrieval, not a systematic search or independent validation", "url": url,
              "response_sha256": regen.sha256_file(target), "local_provenance_receipt": receipt.name,
              "records": [{k: row.get(k) for k in ("id", "source", "pmid", "pmcid", "doi", "title", "firstPublicationDate", "isOpenAccess")} for row in rows]}
    (Path(__file__).parent / "metadata_receipt.json").write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(rows), "response_sha256": public["response_sha256"]}))


if __name__ == "__main__":
    main()
