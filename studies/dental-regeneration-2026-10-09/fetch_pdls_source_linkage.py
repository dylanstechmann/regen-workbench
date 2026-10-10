"""Fetch primary metadata for the PDL maturity study's publication linkage.

Raw responses are kept in ignored data/literature and hashed by regen.record.
This script does not infer donor independence or analyze expression values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen

SOURCES = [
    ("conference-crossref", "https://api.crossref.org/works/10.1016/j.identj.2025.104622", "json"),
    ("full-article-crossref", "https://api.crossref.org/works/10.1016/j.stemcr.2026.103088", "json"),
    ("full-article-europepmc", "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:42785307%20AND%20SRC:MED&format=json&resultType=core", "json"),
    ("conference-publisher", "https://www.sciencedirect.com/science/article/pii/S002065392503905X", "html"),
    ("full-article-publisher", "https://www.sciencedirect.com/science/article/pii/S2213671126002997", "html"),
    ("full-article-cell", "https://www.cell.com/stem-cell-reports/fulltext/S2213-6711(26)00299-7", "html"),
    ("full-article-cell-pdf", "https://www.cell.com/stem-cell-reports/pdf/S2213-6711(26)00299-7.pdf", "pdf"),
    ("conference-publisher-api", "https://api.elsevier.com/content/article/PII:S002065392503905X?httpAccept=text/xml", "xml"),
    ("full-article-publisher-api", "https://api.elsevier.com/content/article/PII:S2213671126002997?httpAccept=text/xml", "xml"),
    ("full-article-publisher-fullview", "https://api.elsevier.com/content/article/PII:S2213671126002997?httpAccept=text/xml&view=FULL", "xml"),
    ("control-markers-human-teeth", "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9590651/fullTextXML", "xml"),
    ("control-markers-human-oral-mucosa", "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8359928/fullTextXML", "xml"),
]
MAX_BYTES = 8 * 1024 * 1024


def summary(name: str, raw: bytes) -> dict:
    if name.endswith("pdf"):
        if not raw.startswith(b"%PDF-"):
            raise ValueError("Publisher PDF route did not return PDF bytes")
        return {"pdf_signature_verified": True, "manual_content_review_required": True}
    if name.endswith("crossref"):
        item = json.loads(raw)["message"]
        return {key: item.get(key) for key in (
            "DOI", "title", "container-title", "volume", "issue", "article-number",
            "type", "published", "author", "link", "relation", "special_numbering", "assertion", "license",
        )}
    if name.endswith("europepmc"):
        items = json.loads(raw)["resultList"]["result"]
        return {"result_count": len(items), "records": [
            {key: item.get(key) for key in (
                "id", "source", "pmid", "pmcid", "doi", "title", "authorString",
                "firstPublicationDate", "pubTypeList", "fullTextUrlList", "inPMC", "isOpenAccess",
            )} for item in items
        ]}
    if "publisher-api" in name or "publisher-fullview" in name:
        root = ET.fromstring(raw)
        namespaces = {"article": "http://www.elsevier.com/xml/svapi/article/dtd",
                      "prism": "http://prismstandard.org/namespaces/basic/2.0/",
                      "dc": "http://purl.org/dc/elements/1.1/"}
        core = root.find("article:coredata", namespaces)
        if core is None:
            raise ValueError("Elsevier response has no expected article coredata")
        return {"doi": core.findtext("prism:doi", namespaces=namespaces),
                "title": core.findtext("dc:title", namespaces=namespaces),
                "cover_date": core.findtext("prism:coverDate", namespaces=namespaces),
                "open_access": core.findtext("article:openaccessArticle", namespaces=namespaces),
                "license_url": core.findtext("article:openaccessUserLicense", namespaces=namespaces),
                "full_text_body_retrieved": any(item.tag.split("}")[-1] == "body" for item in root.iter()),
                "contains_accession_literal": b"GSE306722" in raw}
    return {"structured_metadata_extracted": False,
            "contains_accession_literal": b"GSE306722" in raw,
            "manual_inspection_required": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", action="append", choices=[item[0] for item in SOURCES],
                        help="Fetch only these source IDs and retain previous receipt entries for other sources")
    args = parser.parse_args()
    regen.ensure_dirs()
    receipt_path = Path(__file__).with_name("pdls_source_linkage_receipt.json")
    entries = (json.loads(receipt_path.read_text(encoding="utf-8"))["sources"]
               if args.source_id and receipt_path.is_file() else [])
    raw_dir = regen.DATA / "literature" / "pdls-source-linkage"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, url, suffix in SOURCES:
        if args.source_id and name not in args.source_id:
            continue
        entry = {"source_id": name, "url": url, "attempted_utc": regen.now()}
        try:
            raw = regen.http_bytes(url, timeout=30)
            if len(raw) > MAX_BYTES:
                raise ValueError("Source response exceeds bounded metadata intake")
            metadata = summary(name, raw)
            target = raw_dir / f"{name}.{suffix}"
            target.write_bytes(raw)
            provenance = regen.record("dental-pdls-source-linkage", {"source_id": name, "url": url}, [target])
            entry.update({"retrieved": True, "response_bytes": len(raw),
                          "response_sha256": hashlib.sha256(raw).hexdigest(),
                          "local_provenance_receipt": provenance.name, "metadata": metadata})
        except HTTPError as exc:
            entry.update({"retrieved": False, "failure_class": "HTTPError", "http_status": exc.code})
        except (URLError, OSError, ValueError) as exc:
            entry.update({"retrieved": False, "failure_class": type(exc).__name__})
        entries = [previous for previous in entries if previous["source_id"] != name] + [entry]
        print(json.dumps({"source_id": name, "retrieved": entry["retrieved"],
                          "bytes": entry.get("response_bytes"), "http_status": entry.get("http_status")}))
    receipt = {"schema_version": 1, "accession_under_review": "GSE306722",
               "retrieved_utc": regen.now(), "sources": entries,
               "scope": "Primary metadata/source linkage; no expression analysis and no donor crosswalk inference."}
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
