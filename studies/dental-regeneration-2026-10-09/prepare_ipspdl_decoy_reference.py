"""Fetch a matching full genome and prepare a hash-bound Salmon decoy reference."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen

HERE = Path(__file__).parent
BASE = "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_50"
GENOME = "GRCh38.p14.genome.fa.gz"
MAX_DOWNLOAD = 2 * 1024**3


def publisher_md5(text: str, filename: str) -> str:
    matches = [row.split()[0].lower() for row in text.splitlines()
               if len(row.split()) == 2 and row.split()[1].lstrip("*") == filename]
    if len(matches) != 1 or len(matches[0]) != 32 or any(c not in "0123456789abcdef" for c in matches[0]):
        raise ValueError(f"No unique publisher MD5 for {filename}")
    return matches[0]


def digest_file(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def download_ranges(url: str, partial: Path) -> dict:
    """Resume a prefix through four bounded ranges; final publisher MD5 is mandatory."""
    headers = {"User-Agent": regen.UA, "Accept-Encoding": "identity", "Range": "bytes=0-0"}
    with regen._http_with_retry(Request(url, headers=headers), 180) as response:
        match = re.fullmatch(r"bytes 0-0/(\d+)", response.headers.get("Content-Range", ""))
        if response.status != 206 or not match or len(response.read(2)) != 1:
            raise ValueError("Server did not honor the reference size-probe range")
        total = int(match[1])
    if total <= 0 or total > MAX_DOWNLOAD:
        raise ValueError("Genome download exceeds bound")
    prefix = partial.stat().st_size if partial.exists() else 0
    if prefix > total:
        raise ValueError("Cached genome prefix exceeds source size")
    ranges = [(start, min(start + (64 << 20), total) - 1) for start in range(prefix, total, 64 << 20)]

    def fetch(bounds: tuple[int, int]) -> tuple[int, Path]:
        start, end = bounds
        piece = partial.with_name(f"{partial.name}.{start}-{end}")
        expected = end - start + 1
        # Pieces are never trusted until the assembled publisher checksum passes.
        if piece.is_file() and piece.stat().st_size == expected:
            return start, piece
        request = Request(url, headers={**headers, "Range": f"bytes={start}-{end}"})
        with regen._http_with_retry(request, 180) as response, piece.open("wb") as out:
            if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{total}":
                raise ValueError("Genome server returned a different range")
            received = 0
            while chunk := response.read(min(1 << 20, expected - received + 1)):
                received += len(chunk)
                if received > expected:
                    raise ValueError("Genome range exceeds requested size")
                out.write(chunk)
        if received != expected:
            raise ValueError("Genome range was truncated")
        print(f"Completed genome range {start}-{end}", flush=True)
        return start, piece

    pieces = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch, bounds) for bounds in ranges]
        for future in as_completed(futures):
            pieces.append(future.result())
    assembled = partial.with_name(partial.name + ".assembled")
    with assembled.open("wb") as out:
        if prefix:
            with partial.open("rb") as inp:
                shutil.copyfileobj(inp, out, length=1 << 20)
        for _, piece in sorted(pieces):
            with piece.open("rb") as inp:
                shutil.copyfileobj(inp, out, length=1 << 20)
    if assembled.stat().st_size != total:
        raise ValueError("Assembled genome size differs from source")
    assembled.replace(partial)
    return {"mode": "four bounded HTTP ranges; resumed prefix; assembled publisher MD5 required",
            "source_bytes": total, "resumed_prefix_bytes": prefix, "range_count": len(ranges)}


def fasta_names(path: Path) -> list[str]:
    names, seen, last_line = [], set(), ""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            last_line = line
            if line.startswith(">"):
                fields = line[1:].split()
                name = fields[0] if fields else ""
                if not name or name in seen:
                    raise ValueError(f"Empty or duplicate FASTA identifier in {path.name}")
                seen.add(name)
                names.append(name)
    if not names:
        raise ValueError(f"No FASTA records in {path.name}")
    if not last_line.endswith("\n"):
        raise ValueError(f"FASTA needs a final newline before concatenation: {path.name}")
    return names


def assemble(transcripts: Path, genome: Path, destination: Path) -> dict:
    transcript_names, genome_names = fasta_names(transcripts), fasta_names(genome)
    if set(transcript_names).intersection(genome_names):
        raise ValueError("Target and decoy identifiers collide")
    destination.mkdir(parents=True, exist_ok=True)
    decoys = destination / "decoys.txt"
    decoys.write_text("\n".join(genome_names) + "\n", encoding="utf-8")
    gentrome = destination / "gentrome.fa.gz"
    partial = destination / "gentrome.fa.gz.part"
    # Concatenated gzip members are the publisher tutorial's supported recipe;
    # transcript records precede every genomic decoy record.
    with partial.open("wb") as out:
        for source in (transcripts, genome):
            with source.open("rb") as inp:
                shutil.copyfileobj(inp, out, length=1 << 20)
    partial.replace(gentrome)
    return {"transcript_records": len(transcript_names), "decoy_records": len(genome_names),
            "decoy_names": genome_names, "gentrome": str(gentrome),
            "gentrome_sha256": regen.sha256_file(gentrome), "gentrome_bytes": gentrome.stat().st_size,
            "decoys_sha256": regen.sha256_file(decoys), "ordering": "transcripts then full GRCh38.p14 genome"}


def main() -> None:
    regen.ensure_dirs()
    directory = regen.DATA / "literature" / "gencode-v50"
    directory.mkdir(parents=True, exist_ok=True)
    transcript = directory / "gencode.v50.transcripts.fa.gz"
    baseline = json.loads((HERE / "ipspdl_rnaseq_reference_receipt.json").read_text(encoding="utf-8"))
    expected = next(row["sha256"] for row in baseline["files"] if row["filename"] == transcript.name)
    if regen.sha256_file(transcript) != expected:
        raise ValueError("Existing transcript source differs from the baseline receipt")
    checksums = regen.http_bytes(f"{BASE}/MD5SUMS")
    checksum_path = directory / "MD5SUMS-decoy-reference"
    checksum_path.write_bytes(checksums)
    checksum = publisher_md5(checksums.decode("utf-8"), GENOME)
    target = directory / GENOME
    reused = target.is_file()
    download = {"mode": "hash-verified cached genome"}
    if not reused:
        temporary = target.with_suffix(target.suffix + ".part")
        print(f"Downloading {GENOME}", flush=True)
        download = download_ranges(f"{BASE}/{GENOME}", temporary)
        if digest_file(temporary, "md5") != checksum:
            raise ValueError("Genome fails publisher MD5")
        temporary.replace(target)
    if digest_file(target, "md5") != checksum:
        raise ValueError("Cached genome fails publisher MD5")
    genome_sha = regen.sha256_file(target)
    assembly = assemble(transcript, target, regen.DATA / "structures" / "ipspdl-rnaseq" / "decoy-reference")
    provenance = regen.record("dental-ipspdl-decoy-reference", {"url": f"{BASE}/{GENOME}",
                              "publisher_md5_url": f"{BASE}/MD5SUMS", "reused_genome": reused},
                              [checksum_path, target, Path(assembly["gentrome"])])
    report = {"schema_version": 1, "release": "GENCODE human 50", "assembly": "GRCh38.p14",
              "index_scope": "Full-genome decoys appended to the unchanged baseline transcript reference",
              "prepared_utc": regen.now(), "local_provenance_receipt": provenance.name,
              "transcript_sha256": expected, "genome": {"filename": GENOME, "url": f"{BASE}/{GENOME}",
              "sha256": genome_sha, "publisher_md5": checksum, "bytes": target.stat().st_size,
              "reused_existing_file": reused, "download": download}, "reference": assembly,
              "note": "Same Salmon 2.7.0 implementation and retained duplicate transcript targets as baseline; no --gencode header truncation."}
    (HERE / "ipspdl_rnaseq_decoy_reference_receipt.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"genome_bytes": target.stat().st_size, "transcripts": assembly["transcript_records"],
                      "decoys": assembly["decoy_records"], "genome_sha256": genome_sha}), flush=True)


if __name__ == "__main__":
    main()
