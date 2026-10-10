"""Audit DDBJ sample metadata for the iPS-PDL RNA-seq cited by Taniguchi et al."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen


BASE = "https://ddbj.nig.ac.jp/search/api/entries"
RUNS = [f"DRR913{i:03d}" for i in range(328, 337)]
OUT_DIR = regen.DATA / "literature" / "ddbj-ipspdl-rnaseq-PRJDB39888"
REVIEW_DIR = Path(__file__).parent


def fetch_record(record_type: str, accession: str) -> tuple[str, bytes, dict]:
    url = f"{BASE}/{quote(record_type)}/{quote(accession)}"
    raw = regen.http_bytes(url)
    parsed = json.loads(raw)
    return url, raw, parsed


def attr_map(sample: dict) -> dict[str, str]:
    attrs = sample.get("BioSample", {}).get("Attributes", {}).get("Attribute", [])
    if isinstance(attrs, dict):
        attrs = [attrs]
    return {str(a.get("attribute_name", "")): str(a.get("content", "")) for a in attrs}


def inventory_fastq(run_id: str, directory_url: str) -> list[dict[str, str]]:
    page = regen.http_bytes(directory_url).decode("latin-1")
    filenames = sorted(set(re.findall(r'href="([^"]+\.fastq\.bz2)"', page)))
    if not filenames:
        raise ValueError(f"No compressed FASTQ files listed for {run_id}")
    inventory = []
    for filename in filenames:
        url = urljoin(directory_url, filename)
        request = Request(url, method="HEAD", headers={"User-Agent": regen.UA})
        with urlopen(request, timeout=60) as response:
            length = response.headers.get("Content-Length")
            if length is None:
                raise ValueError(f"No Content-Length for {url}")
            inventory.append({
                "run": run_id,
                "filename": filename,
                "url": url,
                "bytes": str(int(length)),
                "last_modified": response.headers.get("Last-Modified", ""),
            })
    return inventory


def main() -> None:
    regen.ensure_dirs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    project_record = fetch_record("bioproject", "PRJDB39888")
    project_xrefs = project_record[2].get("dbXrefs", [])
    run_ids = sorted(item["identifier"] for item in project_xrefs if item["type"] == "sra-run")
    experiment_ids = sorted(item["identifier"] for item in project_xrefs if item["type"] == "sra-experiment")
    sample_ids = sorted(item["identifier"] for item in project_xrefs if item["type"] == "biosample")
    if run_ids != RUNS:
        raise ValueError(f"BioProject run links differ from the nine cited runs: {run_ids}")
    if len(experiment_ids) != 9 or len(sample_ids) != 18:
        raise ValueError(f"Expected 9 experiments and 18 BioSamples; found {len(experiment_ids)} and {len(sample_ids)}")
    requests = [("sra-run", run) for run in run_ids]
    requests += [("sra-experiment", exp) for exp in experiment_ids]
    requests += [("biosample", sample) for sample in sample_ids]

    fetched: dict[tuple[str, str], tuple[str, bytes, dict]] = {
        ("bioproject", "PRJDB39888"): project_record
    }
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(fetch_record, kind, accession): (kind, accession)
            for kind, accession in requests
        }
        for future, key in futures.items():
            fetched[key] = future.result()

    raw_paths: list[Path] = []
    hashes: list[dict[str, object]] = []
    for (kind, accession), (_url, raw, _parsed) in sorted(fetched.items()):
        path = OUT_DIR / f"{kind}_{accession}.json"
        path.write_bytes(raw)
        raw_paths.append(path)
        hashes.append({"record_type": kind, "accession": accession,
                       "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})

    project = fetched[("bioproject", "PRJDB39888")][2]
    project_data = project["properties"]["Project"]["Project"]
    project_title = project_data["ProjectDescr"]["Title"]
    project_description = project_data["ProjectDescr"]["Description"]
    rows: list[dict[str, str]] = []
    run_sample_ids: dict[str, str] = {}
    for run_id in RUNS:
        run = fetched[("sra-run", run_id)][2]["properties"]["RUN_SET"]["RUN"]
        experiment_id = run["EXPERIMENT_REF"]["accession"]
        experiment = fetched[("sra-experiment", experiment_id)][2]["properties"]
        experiment = experiment["EXPERIMENT_SET"]["EXPERIMENT"]
        sample_id = experiment["DESIGN"]["SAMPLE_DESCRIPTOR"]["IDENTIFIERS"]["PRIMARY_ID"]["content"]
        run_sample_ids[sample_id] = run_id
        sample = fetched[("biosample", sample_id)][2]["properties"]
        sample = sample["BioSample"]
        attributes = attr_map({"BioSample": sample})
        library = experiment["DESIGN"].get("LIBRARY_DESCRIPTOR", {})
        platform = experiment.get("PLATFORM", {})
        illumina = platform.get("ILLUMINA", {})
        cell_type = attributes.get("cell_type", "")
        if cell_type == "periodontal ligament-like cell":
            group = "iPS-PDL"
        elif cell_type == "induced pluripotent stem cell":
            group = "iPS"
        elif cell_type == "periodontal ligament fibroblast":
            group = "primary PDL"
        else:
            group = "unclassified"
        rows.append({
            "group": group,
            "sample_name": attributes.get("sample_name", sample.get("Description", {}).get("SampleName", "")),
            "biosample": sample_id,
            "experiment": experiment_id,
            "run": run_id,
            "library_name": library.get("LIBRARY_NAME", ""),
            "cell_type": cell_type,
            "cell_line": attributes.get("cell_line", ""),
            "provider": attributes.get("biomaterial_provider", ""),
            "age_years": attributes.get("age", ""),
            "sex": attributes.get("sex", ""),
            "collection_date": attributes.get("collection_date", ""),
            "treatment": attributes.get("treatment", ""),
            "library_strategy": library.get("LIBRARY_STRATEGY", ""),
            "library_source": library.get("LIBRARY_SOURCE", ""),
            "library_selection": library.get("LIBRARY_SELECTION", ""),
            "layout": "paired" if "PAIRED" in library.get("LIBRARY_LAYOUT", {}) else "single/unspecified",
            "instrument": illumina.get("INSTRUMENT_MODEL", ""),
        })

    sample_index_rows: list[dict[str, str]] = []
    sample_ids_by_name: dict[str, list[str]] = {}
    for sample_id in sample_ids:
        sample = fetched[("biosample", sample_id)][2]["properties"]["BioSample"]
        attributes = attr_map({"BioSample": sample})
        name = attributes.get("sample_name", sample.get("Description", {}).get("SampleName", ""))
        sample_ids_by_name.setdefault(name, []).append(sample_id)
        sample_index_rows.append({
            "biosample": sample_id,
            "sample_name": name,
            "title": sample.get("Description", {}).get("Title", ""),
            "run": run_sample_ids.get(sample_id, ""),
            "run_link_status": "linked to cited run" if sample_id in run_sample_ids else "project BioSample link; no cited run",
            "last_update": sample.get("last_update", ""),
            "provider": attributes.get("biomaterial_provider", ""),
            "cell_type": attributes.get("cell_type", ""),
            "cell_line": attributes.get("cell_line", ""),
            "age_years": attributes.get("age", ""),
            "sex": attributes.get("sex", ""),
            "collection_date": attributes.get("collection_date", ""),
            "treatment": attributes.get("treatment", ""),
            "karyotype": attributes.get("karyotype", ""),
        })

    sample_index = REVIEW_DIR / "ipspdl_rnaseq_biosample_index.tsv"
    with sample_index.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(sample_index_rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(sample_index_rows)

    fastq_jobs = []
    for run_id in RUNS:
        run_obj = fetched[("sra-run", run_id)][2]
        distribution = next(x for x in run_obj.get("distribution", []) if x.get("encodingFormat") == "FASTQ")
        fastq_jobs.append((run_id, distribution["contentUrl"]))
    fastq_files: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(inventory_fastq, run_id, url) for run_id, url in fastq_jobs]
        for future in futures:
            fastq_files.extend(future.result())
    fastq_manifest = REVIEW_DIR / "ipspdl_rnaseq_fastq_inventory.tsv"
    with fastq_manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fastq_files[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(fastq_files)
    compressed_bytes = sum(int(item["bytes"]) for item in fastq_files)

    duplicate_pairs = []
    for name, ids in sorted(sample_ids_by_name.items()):
        if len(ids) != 2:
            continue
        old_id, new_id = sorted(ids)
        old = fetched[("biosample", old_id)][2]["properties"]["BioSample"]
        new = fetched[("biosample", new_id)][2]["properties"]["BioSample"]
        duplicate_pairs.append({
            "sample_name": name,
            "biosamples": ids,
            "same_owner_model_attributes": all(old.get(k) == new.get(k) for k in ("Owner", "Models", "Attributes")),
            "same_description": old.get("Description") == new.get("Description"),
            "only_one_has_a_cited_run": (old_id in run_sample_ids) != (new_id in run_sample_ids),
        })
    if len(duplicate_pairs) != 9 or not all(
        pair["same_owner_model_attributes"] and pair["only_one_has_a_cited_run"]
        for pair in duplicate_pairs
    ):
        raise ValueError("Expected nine pairs of matching BioSample profiles, each with only one run-linked record")

    manifest = REVIEW_DIR / "ipspdl_rnaseq_manifest.tsv"
    if rows:
        with manifest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    provenance = regen.record(
        "dental-ipspdl-rnaseq-metadata-audit",
        {"project": "PRJDB39888", "base_url": BASE, "record_count": len(fetched),
         "runs": RUNS, "statement": "Metadata only; no FASTQ or SRA read files downloaded."},
        raw_paths + [manifest, sample_index, fastq_manifest],
    )
    receipt = {
        "project": "PRJDB39888",
        "project_title": project_title,
        "project_description": project_description,
        "source_api": BASE,
        "retrieved_utc": regen.now(),
        "record_count": len(fetched),
        "run_count": len(RUNS),
        "manifest": manifest.name,
        "biosample_index": sample_index.name,
        "fastq_inventory": fastq_manifest.name,
        "fastq_file_count": len(fastq_files),
        "compressed_fastq_bytes": compressed_bytes,
        "fastq_files": fastq_files,
        "project_biosample_count": len(sample_ids),
        "duplicate_sample_profile_pairs": duplicate_pairs,
        "local_provenance_receipt": provenance.name,
        "raw_read_files_downloaded": False,
        "record_hashes": hashes,
    }
    receipt_path = REVIEW_DIR / "ipspdl_rnaseq_metadata_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"project": "PRJDB39888", "records": len(fetched),
                      "runs": len(rows), "manifest": str(manifest),
                      "fastq_files": len(fastq_files), "compressed_fastq_bytes": compressed_bytes,
                      "provenance": provenance.name}, indent=2))


if __name__ == "__main__":
    main()
