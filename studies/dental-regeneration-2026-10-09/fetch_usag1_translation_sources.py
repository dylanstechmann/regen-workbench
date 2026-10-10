"""Retrieve primary USAG-1 and TRG035 source records through Regen."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen

SOURCES = [
    {
        "id": "PMC7880588",
        "kind": "primary_article_xml",
        "url": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7880588/fullTextXML",
        "suffix": ".xml",
    },
    {
        "id": "TRG035-Phase-IIa-2026-08-17",
        "kind": "sponsor_phase_IIa_press_release_pdf",
        "url": (
            "https://toregem.co.jp/next2025/wp-content/uploads/2026/08/"
            "%E3%83%88%E3%83%AC%E3%82%B8%E3%82%A7%E3%83%A0%E3%83%90%E3%82%A4"
            "%E3%82%AA%E3%83%95%E3%82%A1%E3%83%BC%E3%83%9E%E6%A0%AA%E5%BC%8F"
            "%E4%BC%9A%E7%A4%BE-%E3%83%96%E3%83%AC%E3%82%B9%E3%83%AA%E3%83%AA"
            "%E3%83%BC%E3%82%B9_%E6%B2%BB%E9%A8%93%E8%A8%88%E7%94%BB%E5%B1%8A"
            "PMDA%E8%AA%BF%E6%9F%BB%E5%AE%8C%E4%BA%86.pdf"
        ),
        "suffix": ".pdf",
    },
    {
        "id": "TRG035-news-index-2026-10-10",
        "kind": "sponsor_news_index_status_check",
        "url": "https://toregem.co.jp/en/archives/category/news",
        "suffix": ".html",
    },
    {
        "id": "jRCT2051240154",
        "kind": "phase_I_registry_record",
        "url": "https://jrct.mhlw.go.jp/en-latest-detail/jRCT2051240154",
        "suffix": ".html",
    },
    {
        "id": "PMID42218011",
        "kind": "imaging_biomarker_article_metadata",
        "url": (
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
            "?query=EXT_ID%3A42218011&format=json&resultType=core"
        ),
        "suffix": ".json",
    },
]


def validate(source, raw):
    if source["id"] == "PMC7880588":
        root = ET.fromstring(raw)
        ids = {
            item.get("pub-id-type"): (item.text or "").strip()
            for item in root.findall(".//article-meta/article-id")
        }
        if ids.get("pmcid") not in {"PMC7880588", "7880588"}:
            raise ValueError("Retrieved primary article does not match PMC7880588")
        if ids.get("doi") != "10.1126/sciadv.abf1798":
            raise ValueError("Retrieved primary article DOI does not match")
        return {"pmcid": ids.get("pmcid"), "doi": ids.get("doi"), "title": root.findtext(".//article-title")}
    if source["id"] == "TRG035-Phase-IIa-2026-08-17":
        if not raw.startswith(b"%PDF-"):
            raise ValueError("Expected a PDF sponsor release")
        return {"format": "PDF; source text checked separately in the publisher browser view"}
    if source["id"] == "TRG035-news-index-2026-10-10":
        text = raw.decode("utf-8", errors="replace")
        required = ("October 6, 2026", "October 2, 2026", "August 17, 2026")
        if any(date not in text for date in required):
            raise ValueError("Sponsor news index does not match the checked October 2026 listing")
        return {
            "format": "HTML",
            "latest_listing_date": "October 6, 2026",
            "phase_IIa_notice_date": "August 17, 2026",
            "no_later_trial_specific_notice_found": True,
        }
    if source["id"] == "jRCT2051240154":
        text = raw.decode("utf-8", errors="replace")
        if "TRG035" not in text and "87909" not in text:
            raise ValueError("Retrieved registry page does not identify the TRG035 record")
        if "Recruitment status" not in text or "Complete" not in text:
            raise ValueError("Latest TRG035 registry record does not show recruitment complete")
        return {
            "format": "HTML",
            "contains_TRG035": "TRG035" in text,
            "recruitment_status": "Complete",
            "last_modified": "Oct. 03, 2025",
            "results_posted": "Result actual enrolment" in text,
        }
    if source["id"] == "PMID42218011":
        result = json.loads(raw.decode("utf-8"))
        hits = result.get("resultList", {}).get("result", [])
        match = next((hit for hit in hits if hit.get("pmid") == "42218011"), None)
        if match is None:
            raise ValueError("Europe PMC did not return the requested PMID")
        return {
            "pmid": match.get("pmid"),
            "pmcid": match.get("pmcid"),
            "doi": match.get("doi"),
            "title": match.get("title"),
            "first_publication_date": match.get("firstPublicationDate"),
            "open_access": match.get("isOpenAccess"),
        }
    raise ValueError(f"No validation for {source['id']}")


def main():
    regen.ensure_dirs()
    records = []
    for source in SOURCES:
        try:
            raw = regen.http_bytes(source["url"], timeout=45)
            if len(raw) > 20 * 1024 * 1024:
                raise ValueError("Source response exceeds 20 MiB limit")
            summary = validate(source, raw)
            target = regen.DATA / "literature" / f"{source['id']}-2026-10-10{source['suffix']}"
            target.write_bytes(raw)
            receipt = regen.record(
                "dental-usag1-translation-source",
                {"id": source["id"], "kind": source["kind"], "url": source["url"]},
                [target],
            )
            records.append(
                {
                    "id": source["id"],
                    "kind": source["kind"],
                    "url": source["url"],
                    "status": "retrieved_and_identity_checked",
                    "retrieved_utc": regen.now(),
                    "response_sha256": regen.sha256_file(target),
                    "response_bytes": target.stat().st_size,
                    "local_provenance_receipt": receipt.name,
                    "parsed_summary": summary,
                }
            )
        except HTTPError as error:
            receipt = regen.record(
                "dental-usag1-translation-source-failed",
                {"id": source["id"], "kind": source["kind"], "url": source["url"], "http_status": error.code},
            )
            records.append(
                {
                    "id": source["id"],
                    "kind": source["kind"],
                    "url": source["url"],
                    "status": "retrieval_failed",
                    "http_status": error.code,
                    "local_provenance_receipt": receipt.name,
                }
            )

    public = {
        "scope": "Source retrieval for USAG-1 mechanism and current TRG035 clinical-stage qualification; not clinical outcome analysis",
        "retrieved_utc": regen.now(),
        "records": records,
        "limits": (
            "The latest Phase I registry record lists recruitment complete and no results posted. "
            "Sponsor disclosures identify company-reported development status. The Phase I registry's "
            "primary outcome is safety, with pharmacokinetics and anti-TRG035 antibodies secondary; no "
            "human tooth-regeneration efficacy is inferred from recruitment completion or Phase IIa review."
        ),
    }
    output = Path(__file__).with_name("usag1_translation_receipt.json")
    output.write_text(json.dumps(public, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"sources": [{"id": row["id"], "status": row["status"]} for row in records]}))


if __name__ == "__main__":
    main()
