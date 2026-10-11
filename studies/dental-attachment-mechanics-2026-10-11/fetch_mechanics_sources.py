"""Fetch exact public dental attachment mechanics articles through regen."""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen

HERE = Path(__file__).resolve().parent
SOURCES = {
    "PMC8881622": "10.1038/s41598-022-06865-6",
    "PMC3029000": "10.1089/ten.TEA.2010.0264",
}
SUPPLEMENTS = {
    "PMC8881622": {
        "url": "https://static-content.springer.com/esm/art%3A10.1038%2Fs41598-022-06865-6/MediaObjects/41598_2022_6865_MOESM1_ESM.pdf",
        "filename": "41598_2022_6865_MOESM1_ESM.pdf",
        "md5": "1c3c2d21a96406cdef8fe243d5fa1924",
        "table": "Supplementary Table S3",
        "page": 6,
    }
}


def text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join(" ".join(element.itertext()).split())


def parse_article(pmcid: str, root: ET.Element, raw: bytes) -> dict:
    ids = {
        node.get("pub-id-type", ""): text(node)
        for node in root.findall(".//article-meta/article-id")
    }
    actual_pmcid = ids.get("pmcid", "")
    if actual_pmcid != pmcid:
        raise ValueError(f"Article identity mismatch: expected {pmcid}, got {actual_pmcid}")
    doi = ids.get("doi", "")
    if doi != SOURCES[pmcid]:
        raise ValueError(f"DOI mismatch for {pmcid}: {doi!r}")
    license_text = " ".join(text(node) for node in root.findall(".//permissions/license"))
    tables = []
    for table_wrap in root.findall(".//table-wrap"):
        table = table_wrap.find(".//table")
        rows = []
        if table is not None:
            for row in table.findall(".//tr"):
                cells = [text(cell) for cell in list(row) if cell.tag.rsplit("}", 1)[-1] in {"th", "td"}]
                if cells:
                    rows.append(cells)
        tables.append({
            "label": text(table_wrap.find("label")),
            "caption": text(table_wrap.find("caption")),
            "rows": rows,
        })
    figures = []
    for figure in root.findall(".//fig"):
        figures.append({"label": text(figure.find("label")), "caption": text(figure.find("caption"))})
    return {
        "pmcid": pmcid,
        "doi": doi,
        "title": text(root.find(".//article-title")),
        "license_text": license_text,
        "source_url": f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML",
        "retrieved_utc": regen.now(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "local_fulltext_path": f"data/literature/dental-attachment-mechanics/{pmcid}-fulltext.xml",
        "table_count": len(tables),
        "tables": tables,
        "figures": figures,
    }


def main() -> None:
    regen.ensure_dirs()
    records = []
    failures = []
    output_dir = regen.DATA / "literature" / "dental-attachment-mechanics"
    output_dir.mkdir(parents=True, exist_ok=True)
    for pmcid in SOURCES:
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
        try:
            raw = regen.http_bytes(url)
        except urllib.error.URLError as exc:
            status = getattr(exc, "code", None)
            failures.append({"pmcid": pmcid, "doi": SOURCES[pmcid], "url": url,
                             "status": status, "error_type": type(exc).__name__,
                             "retrieved_utc": regen.now()})
            continue
        root = ET.fromstring(raw)
        target = output_dir / f"{pmcid}-fulltext.xml"
        target.write_bytes(raw)
        provenance = regen.record("dental-mechanics-primary-fulltext", {"pmcid": pmcid, "doi": SOURCES[pmcid], "url": url}, [target])
        record = parse_article(pmcid, root, raw)
        record["local_provenance_receipt"] = provenance.name if provenance else None
        records.append(record)
    supplements = []
    for pmcid, source in SUPPLEMENTS.items():
        try:
            raw = regen.http_bytes(source["url"])
        except urllib.error.URLError as exc:
            failures.append({"pmcid": pmcid, "doi": SOURCES[pmcid], "url": source["url"],
                             "status": getattr(exc, "code", None),
                             "error_type": type(exc).__name__, "retrieved_utc": regen.now(),
                             "kind": "supplementary_file"})
            continue
        md5 = hashlib.md5(raw).hexdigest()
        if md5 != source["md5"]:
            raise ValueError(f"Supplement checksum mismatch for {pmcid}: {md5}")
        target = output_dir / source["filename"]
        target.write_bytes(raw)
        provenance = regen.record("dental-mechanics-primary-supplement",
                                  {"pmcid": pmcid, "doi": SOURCES[pmcid],
                                   "url": source["url"], "md5": md5}, [target])
        supplements.append({"pmcid": pmcid, "doi": SOURCES[pmcid],
                            "source_url": source["url"], "retrieved_utc": regen.now(),
                            "bytes": len(raw), "md5": md5,
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "local_path": f"data/literature/dental-attachment-mechanics/{source['filename']}",
                            "table": source["table"], "page": source["page"],
                            "local_provenance_receipt": provenance.name if provenance else None})
    receipt = {
        "schema_version": 1,
        "scope": "Two primary studies selected for a periodontal-attachment mechanics comparison, plus the official supplementary PDF for the PDGF-BB study. Full text and supplement are retained for successfully retrieved records only; endpoint failures are listed separately.",
        "records": records,
        "supplementary_files": supplements,
        "retrieval_failures": failures,
        "limitations": [
            "Primary article data may be reported only in plots or group summaries; this receipt does not turn graphical values into specimen-level observations.",
            "The two studies use different species, injuries and mechanical loading protocols and are not pooled.",
            "Supplementary Table S3 reports group mean maximum loads with surface areas from one representative CT-measured tooth per group; public per-tooth mechanics records were not located.",
            "A failed full-text endpoint request records a retrieval limitation, not evidence that the article or its findings are invalid.",
        ],
    }
    path = HERE / "source_extraction_receipt.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"sources": [{"pmcid": row["pmcid"], "title": row["title"], "tables": row["table_count"], "bytes": row["bytes"], "sha256": row["sha256"], "provenance": row["local_provenance_receipt"]} for row in records], "supplements": supplements}))


if __name__ == "__main__":
    main()
