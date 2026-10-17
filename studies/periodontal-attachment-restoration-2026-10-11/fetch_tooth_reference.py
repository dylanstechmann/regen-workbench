"""Fetch one public pre-instrumentation micro-CT reference, with checksums.

Pereira et al., ds-uct-002, doi:10.5281/zenodo.3877625, CC BY 4.0.
Pre-instrumentation does not mean pristine or clinically healthy.
"""

from __future__ import annotations

import hashlib
import argparse
import io
import json
import struct
import sys
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen

DEST = ROOT / "data" / "literature" / "dental-reference-ds-uct-002"
API = "https://zenodo.org/api/records/3877625"
KEY = "ds-uct-002_root_canal_strain_tomo1b_20um_8bits.zip"
EXPECTED_MD5 = "977bc12d30f0ebb725bb04f37fa090f2"
EXPECTED_BYTES = 252940963


def file_md5(path: Path) -> str:
    h = hashlib.md5()  # Publisher integrity check, not a security primitive.
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main_full() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    with urlopen(Request(API, headers={"User-Agent": regen.UA}), timeout=45) as r:
        raw = r.read()
    obj = json.loads(raw)
    if obj["metadata"].get("license", {}).get("id") != "cc-by-4.0":
        raise ValueError("Review changed dataset license before fetching")
    item = next(f for f in obj["files"] if f["key"] == KEY)
    if item["checksum"] != "md5:" + EXPECTED_MD5 or item["size"] != EXPECTED_BYTES:
        raise ValueError("Published reference changed; review before fetching")
    metadata = DEST / "zenodo_record.json"
    metadata.write_bytes(raw)
    target = DEST / KEY
    if not (target.is_file() and target.stat().st_size == EXPECTED_BYTES
            and file_md5(target) == EXPECTED_MD5):
        partial = target.with_suffix(".zip.part")
        with urlopen(Request(item["links"]["self"], headers={"User-Agent": regen.UA}),
                     timeout=60) as response, partial.open("wb") as output:
            total = 0
            while chunk := response.read(1 << 20):
                total += len(chunk)
                if total > EXPECTED_BYTES:
                    raise ValueError("Reference exceeds declared size")
                output.write(chunk)
        if partial.stat().st_size != EXPECTED_BYTES or file_md5(partial) != EXPECTED_MD5:
            raise ValueError("Reference failed publisher size/checksum verification")
        partial.replace(target)
    info = next(f for f in obj["files"] if f["key"] == "_info_ds-uct-002.txt")
    info_path = DEST / info["key"]
    with urlopen(Request(info["links"]["self"], headers={"User-Agent": regen.UA}), timeout=45) as r:
        info_path.write_bytes(r.read())
    if file_md5(info_path) != info["checksum"].split(":", 1)[1]:
        raise ValueError("Dataset description checksum mismatch")
    receipt = regen.record("dental-reference-microct-fetch", {
        "doi": "10.5281/zenodo.3877625", "license": "CC-BY-4.0",
        "metadata_url": API, "file_url": item["links"]["self"],
        "publisher_md5_verified": EXPECTED_MD5, "declared_voxel_size_um": 20.0,
        "baseline_status": "before instrumentation; intactness not established",
    }, [metadata, info_path, target])
    print(json.dumps({"file": str(target), "sha256": regen.sha256_file(target),
                      "provenance": receipt.name}, indent=2))


URL = "https://zenodo.org/records/3877625/files/" + KEY + "?download=1"


def fetch_range(start: int, end: int) -> bytes:
    if not 0 <= start <= end < EXPECTED_BYTES:
        raise ValueError("Invalid archive range")
    request = Request(URL, headers={"User-Agent": regen.UA,
                                   "Range": f"bytes={start}-{end}"})
    with urlopen(request, timeout=45) as response:
        expected = f"bytes {start}-{end}/{EXPECTED_BYTES}"
        if response.status != 206 or response.headers.get("Content-Range") != expected:
            raise ValueError("Server did not honor exact partial-content request")
        data = response.read(end - start + 2)
    if len(data) != end - start + 1:
        raise ValueError("Partial-content size mismatch")
    return data


class RangeReader(io.RawIOBase):
    """Read only the central directory with Python's ZIP parser."""
    def __init__(self) -> None:
        self.pos = 0

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = (offset if whence == 0 else self.pos + offset
                    if whence == 1 else EXPECTED_BYTES + offset)
        return self.pos

    def read(self, size: int = -1) -> bytes:
        size = min(size if size >= 0 else EXPECTED_BYTES - self.pos,
                   EXPECTED_BYTES - self.pos)
        if size <= 0:
            return b""
        data = fetch_range(self.pos, self.pos + size - 1)
        self.pos += len(data)
        return data


def fetch_member(info: zipfile.ZipInfo) -> dict:
    # One request includes the fixed header, variable header and compressed data.
    end = min(EXPECTED_BYTES - 1, info.header_offset + info.compress_size + 4095)
    raw = fetch_range(info.header_offset, end)
    header = struct.unpack("<4s5H3I2H", raw[:30])
    if header[0] != b"PK\x03\x04" or header[3] != info.compress_type:
        raise ValueError("Unexpected local ZIP header")
    name_size, extra_size = header[-2:]
    if raw[30:30 + name_size].decode("utf-8") != info.filename:
        raise ValueError("ZIP member name mismatch")
    start = 30 + name_size + extra_size
    compressed = raw[start:start + info.compress_size]
    if info.compress_type == zipfile.ZIP_DEFLATED:
        data = zlib.decompress(compressed, -15)
    elif info.compress_type == zipfile.ZIP_STORED:
        data = compressed
    else:
        raise ValueError("Unsupported ZIP compression")
    if len(data) != info.file_size or zlib.crc32(data) != info.CRC:
        raise ValueError("ZIP member failed length/CRC verification")
    path = DEST / "sampled_slices" / Path(info.filename).name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"member": info.filename, "file": path.name,
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "zip_crc32": f"{info.CRC:08x}", "range_start": info.header_offset,
            "range_end": end}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Fetch the full 253 MB archive")
    args = parser.parse_args()
    if args.full:
        main_full()
        return
    DEST.mkdir(parents=True, exist_ok=True)
    with urlopen(Request(API, headers={"User-Agent": regen.UA}), timeout=45) as r:
        raw = r.read()
    obj = json.loads(raw)
    item = next(f for f in obj["files"] if f["key"] == KEY)
    if (obj["metadata"].get("license", {}).get("id") != "cc-by-4.0"
            or item["checksum"] != "md5:" + EXPECTED_MD5
            or item["size"] != EXPECTED_BYTES):
        raise ValueError("Review changed source metadata before fetching")
    metadata = DEST / "zenodo_record.json"
    metadata.write_bytes(raw)
    with zipfile.ZipFile(RangeReader()) as archive:
        infos = archive.infolist()
    entries = DEST / "zip_index.json"
    entries.write_text(json.dumps([{"name": v.filename, "bytes": v.file_size,
                                    "crc32": f"{v.CRC:08x}", "offset": v.header_offset}
                                   for v in infos], indent=2) + "\n", encoding="utf-8")
    slices = sorted((v for v in infos if v.filename.lower().endswith(".tiff")),
                    key=lambda v: v.filename)
    # Fixed, uniformly spaced subsample; no outcome-dependent slice selection.
    selected = slices[::16]
    header = next(v for v in infos if v.filename.endswith("/Header.txt"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(fetch_member, [header, *selected]))
    receipt = regen.record("dental-reference-microct-range-fetch", {
        "doi": "10.5281/zenodo.3877625", "license": "CC-BY-4.0", "url": URL,
        "archive_declared_md5": EXPECTED_MD5, "archive_md5_verified": False,
        "integrity": "each selected member ZIP CRC32 verified; local SHA256 recorded",
        "selection": "all TIFF entries sorted by filename; every sixteenth from first",
        "baseline_status": "before instrumentation; intactness not established",
    }, [metadata, entries, *(DEST / "sampled_slices" / v["file"] for v in results)])
    manifest = {
        "doi": "10.5281/zenodo.3877625", "license": "CC-BY-4.0",
        "retrieved_utc": regen.now(), "archive_url": URL,
        "archive_bytes": EXPECTED_BYTES, "archive_declared_md5": EXPECTED_MD5,
        "archive_md5_verified": False, "original_slice_count": len(slices),
        "sample_stride_z": 16, "declared_native_voxel_um": 20.0,
        "scale_caveat": "record/ZIP name say 20 um; inner folder says 10um; header must be inspected",
        "provenance_receipt": receipt.name, "files": results,
    }
    path = DEST / "sampled_reference_manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Fetched {len(selected)} sampled slices and source header; manifest: {path}")


if __name__ == "__main__":
    main()
