"""Fetch hash-pinned GENCODE v50 references for the exploratory RNA-seq run."""

from __future__ import annotations

import hashlib
import gzip
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen


BASE = "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_50"
DEST = regen.DATA / "literature" / "gencode-v50"
REVIEW_DIR = Path(__file__).parent
FILES = {
    "gencode.v50.transcripts.fa.gz": f"{BASE}/gencode.v50.transcripts.fa.gz",
    "gencode.v50.annotation.gtf.gz": f"{BASE}/gencode.v50.annotation.gtf.gz",
}


def inspect_gzip(path: Path) -> int:
    total = 0
    with gzip.open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            total += len(chunk)
    return total


def fetch(name: str, url: str) -> tuple[Path, dict[str, object]]:
    target = DEST / name
    temporary = target.with_suffix(target.suffix + ".part")
    if target.is_file():
        uncompressed = inspect_gzip(target)
        return target, {"filename": name, "url": url, "bytes": target.stat().st_size,
                        "sha256": regen.sha256_file(target), "uncompressed_bytes": uncompressed,
                        "reused_existing_file": True}
    request = Request(url, headers={"User-Agent": regen.UA, "Range": "bytes=0-"})
    value = hashlib.sha256()
    total = 0
    print(f"Downloading {name}", flush=True)
    with urlopen(request, timeout=180) as response, temporary.open("wb") as handle:
        expected = response.headers.get("Content-Length")
        while chunk := response.read(1 << 20):
            handle.write(chunk)
            value.update(chunk)
            total += len(chunk)
            handle.flush()
            if total % (64 << 20) < (1 << 20):
                print(f"{name}: {total} bytes", flush=True)
    temporary.replace(target)
    if expected is not None and total != int(expected):
        raise IOError(f"{name}: expected {expected} bytes, received {total}")
    print(f"Verified {name}: {total} bytes", flush=True)
    uncompressed = inspect_gzip(target)
    return target, {"filename": name, "url": url, "bytes": total,
                    "sha256": value.hexdigest(), "uncompressed_bytes": uncompressed,
                    "last_modified": response.headers.get("Last-Modified", ""),
                    "reused_existing_file": False}


def main() -> None:
    regen.ensure_dirs()
    DEST.mkdir(parents=True, exist_ok=True)
    results = [fetch(name, url) for name, url in FILES.items()]
    outputs = [path for path, _record in results]
    provenance = regen.record(
        "dental-ipspdl-rnaseq-gencode-v50-reference",
        {"release": "GENCODE human 50", "assembly": "GRCh38.p14",
         "source": "Official GENCODE/EBI release archive",
         "index_scope": "Transcriptome-only; no genomic decoy sequence included"},
        outputs,
    )
    receipt = {
        "release": "GENCODE human 50",
        "assembly": "GRCh38.p14",
        "index_scope": "Transcriptome-only; no genomic decoy sequence included",
        "retrieved_utc": regen.now(),
        "local_provenance_receipt": provenance.name,
        "files": [record for _path, record in results],
    }
    path = REVIEW_DIR / "ipspdl_rnaseq_reference_receipt.json"
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"release": receipt["release"], "files": len(outputs),
                      "receipt": path.name}, indent=2))


if __name__ == "__main__":
    main()
