"""Fetch the curated human periodontal meta-atlas H5AD with a size/hash receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / "data" / "literature" / "oral-atlas-GSE164241"
DATASET_ID = "9fcb0b73-c734-40a5-be9c-ace7eea401c9"
VERSION_ID = "171607d7-dcc2-4993-9deb-bbc62cf13273"
COLLECTION_ID = "71f4bccf-53d4-4c12-9e80-e73bfb89e398"
URL = f"https://datasets.cellxgene.cziscience.com/{VERSION_ID}.h5ad"
EXPECTED_BYTES = 705_007_195
MAX_BYTES = 1_500_000_000
CHUNK = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / "human-periodontal-meta-atlas-v1.h5ad"
    receipt_path = CACHE / "human-periodontal-meta-atlas-v1.receipt.json"
    if target.is_file() and target.stat().st_size == EXPECTED_BYTES:
        digest = sha256_file(target)
        source = "verified_existing_cache"
    else:
        temporary = target.with_suffix(target.suffix + ".partial")
        request = urllib.request.Request(URL, headers={"User-Agent": "regen-workbench/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response:
            declared = int(response.headers.get("Content-Length", "0"))
            if response.status != 200 or declared != EXPECTED_BYTES or declared > MAX_BYTES:
                raise ValueError(f"Unexpected H5AD response: status={response.status}, bytes={declared}")
            digest_builder = hashlib.sha256()
            received = 0
            last_report = 0
            with temporary.open("wb") as output:
                while block := response.read(CHUNK):
                    received += len(block)
                    if received > MAX_BYTES or received > declared:
                        raise ValueError("H5AD download exceeded the declared size bound")
                    output.write(block)
                    digest_builder.update(block)
                    if received - last_report >= 64 * CHUNK:
                        print(f"downloaded_bytes={received}", flush=True)
                        last_report = received
            if received != declared:
                raise ValueError(f"Incomplete H5AD download: {received} of {declared} bytes")
        temporary.replace(target)
        digest = digest_builder.hexdigest()
        source = "downloaded"

    receipt = {
        "source": "CZ CELLxGENE Discover curated H5AD",
        "collection_id": COLLECTION_ID,
        "dataset_id": DATASET_ID,
        "dataset_version_id": VERSION_ID,
        "source_url": URL,
        "retrieved_utc_epoch": int(time.time()),
        "sha256": digest,
        "bytes": target.stat().st_size,
        "cache_action": source,
        "note": "Curated integrated atlas; subset by original study and sample metadata before any GSE164241-specific inference.",
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"data": str(target), "receipt": str(receipt_path), "sha256": digest,
                      "bytes": target.stat().st_size, "cache_action": source}, indent=2))


if __name__ == "__main__":
    main()
