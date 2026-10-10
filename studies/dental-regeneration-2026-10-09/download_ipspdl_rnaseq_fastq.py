"""Download and size-verify the public FASTQ files listed in the DDBJ audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen


REVIEW_DIR = Path(__file__).parent
INVENTORY = REVIEW_DIR / "ipspdl_rnaseq_fastq_inventory.tsv"
DEST = regen.DATA / "literature" / "ddbj-ipspdl-rnaseq-PRJDB39888" / "fastq"
RECEIPT = REVIEW_DIR / "ipspdl_rnaseq_download_receipt.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def download(item: dict[str, str]) -> dict[str, str]:
    filename = Path(item["filename"]).name
    expected_size = int(item["bytes"])
    destination = DEST / filename
    partial = DEST / f"{filename}.part"
    if destination.is_file() and destination.stat().st_size == expected_size:
        return {**item, "local_path": str(destination), "sha256": digest(destination), "status": "already complete"}

    for attempt in range(3):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset >= expected_size:
            partial.unlink(missing_ok=True)
            offset = 0
        headers = {"User-Agent": regen.UA}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            request = Request(item["url"], headers=headers)
            with urlopen(request, timeout=180) as response:
                append = offset > 0 and response.status == 206
                if offset and not append:
                    offset = 0
                mode = "ab" if append else "wb"
                with partial.open(mode) as handle:
                    while chunk := response.read(1 << 20):
                        handle.write(chunk)
            if partial.stat().st_size != expected_size:
                raise IOError(f"expected {expected_size} bytes, received {partial.stat().st_size}")
            partial.replace(destination)
            print(f"verified size {filename}: {expected_size} bytes", flush=True)
            return {**item, "local_path": str(destination), "sha256": digest(destination), "status": "downloaded"}
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            if attempt == 2:
                raise RuntimeError(f"download failed for {filename}: {exc}") from exc

    raise RuntimeError(f"download failed for {filename}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.workers <= 6:
        parser.error("--workers must be between 1 and 6")
    if not INVENTORY.is_file():
        raise FileNotFoundError(f"Run fetch_ipspdl_rnaseq_metadata.py first: {INVENTORY}")
    with INVENTORY.open(encoding="utf-8", newline="") as handle:
        items = list(csv.DictReader(handle, delimiter="\t"))
    if not items:
        raise ValueError("FASTQ inventory is empty")
    expected_total = sum(int(item["bytes"]) for item in items)
    free_bytes = shutil.disk_usage(DEST.parent).free
    if free_bytes < expected_total + (2 << 30):
        raise OSError(f"Need {expected_total + (2 << 30)} free bytes; found {free_bytes}")
    DEST.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {len(items)} public compressed FASTQ files ({expected_total} bytes)", flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(download, item) for item in items]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda x: (x["run"], x["filename"]))
    if sum(int(row["bytes"]) for row in results) != expected_total:
        raise ValueError("Downloaded size total differs from the archived directory inventory")
    provenance = regen.record(
        "dental-ipspdl-rnaseq-fastq-download",
        {"project": "PRJDB39888", "files": len(results), "bytes": expected_total,
         "source": "DDBJ public FASTQ directory; Content-Length verified; SHA-256 calculated locally"},
        [Path(row["local_path"]) for row in results],
    )
    receipt = {
        "project": "PRJDB39888",
        "retrieved_utc": regen.now(),
        "file_count": len(results),
        "compressed_bytes": expected_total,
        "local_provenance_receipt": provenance.name,
        "files": [{key: value for key, value in row.items() if key != "local_path"}
                  for row in results],
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(results), "compressed_bytes": expected_total,
                      "receipt": RECEIPT.name}, indent=2), flush=True)


if __name__ == "__main__":
    main()
