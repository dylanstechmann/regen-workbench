import gzip
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import patch

SCRIPT = Path(os.environ.get("IPSPDL_DECOY_REFERENCE_SCRIPT", str(
    Path(__file__).resolve().parents[1] / "studies" / "dental-regeneration-2026-10-09" / "prepare_ipspdl_decoy_reference.py")))
SPEC = importlib.util.spec_from_file_location("prepare_ipspdl_decoy_reference", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

PATTERN = bytes(range(251))


def source_slice(start, length):
    """Deterministic fixture bytes without allocating a whole genome-sized source."""
    offset = start % len(PATTERN)
    return (PATTERN * ((offset + length + len(PATTERN) - 1) // len(PATTERN)))[offset:offset + length]


class RangeResponse(io.RawIOBase):
    def __init__(self, start, end, total, fault=None):
        super().__init__()
        self.start = start
        self.position = 0
        self.length = end - start + 1
        self.status = 200 if fault == "ignored200" else 206
        header_total = total + 1 if fault == "mismatched_range" else total
        header_start = start + 1 if fault == "mismatched_range" and start == end == 0 else start
        header_end = end + 1 if fault == "mismatched_range" and start == end == 0 else end
        self.headers = {"Content-Range": f"bytes {header_start}-{header_end}/{header_total}"}
        if fault == "truncated":
            self.length -= 1
        elif fault == "oversized":
            self.length += 1

    def read(self, amount=-1):
        available = self.length - self.position
        count = available if amount < 0 else min(amount, available)
        result = source_slice(self.start + self.position, count)
        self.position += count
        return result


class DecoyReferenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def fasta(self, name, text):
        destination = self.root / name
        destination.write_bytes(gzip.compress(text.encode("ascii"), mtime=0))
        return destination

    def test_publisher_md5_matches_exact_filename_and_normalizes_hex(self):
        expected = "ABCDEF0123456789ABCDEF0123456789"
        manifest = f"{'0' * 32} other.GRCh38.p14.genome.fa.gz\n{expected}  *GRCh38.p14.genome.fa.gz\n"
        self.assertEqual(MODULE.publisher_md5(manifest, "GRCh38.p14.genome.fa.gz"), expected.lower())

    def test_publisher_md5_rejects_missing_ambiguous_and_malformed_entries(self):
        name = "GRCh38.p14.genome.fa.gz"
        valid = f"{'a' * 32} {name}\n"
        cases = ["", valid * 2, f"{'a' * 31} {name}\n", f"{'a' * 33} {name}\n",
                 f"{'g' * 32} {name}\n", f"{'a' * 32} {name} extra\n",
                 f"{'a' * 32} prefixed.{name}\n"]
        for manifest in cases:
            with self.subTest(manifest=manifest):
                with self.assertRaisesRegex(ValueError, "unique publisher MD5"):
                    MODULE.publisher_md5(manifest, name)

    def test_gzip_fasta_names_keep_full_pipe_identifiers_and_record_order(self):
        path = self.fasta("transcripts.fa.gz", ">ENST2.1|ENSG2.1|description transcript two\nACGT\n>ENST1.2|ENSG1.1|description transcript one\nTTAA\n")
        self.assertEqual(MODULE.fasta_names(path), ["ENST2.1|ENSG2.1|description", "ENST1.2|ENSG1.1|description"])

    def test_fasta_rejects_missing_empty_and_duplicate_identifiers(self):
        for text in ["", "ACGT\n", ">\nACGT\n", ">   \nACGT\n",
                     ">chr1 first description\nACGT\n>chr1 changed description\nTTAA\n"]:
            with self.subTest(text=text):
                path = self.fasta("invalid.fa.gz", text)
                with self.assertRaises(ValueError):
                    MODULE.fasta_names(path)

    def test_fasta_read_checks_gzip_crc_and_truncated_trailers(self):
        source = self.fasta("broken.fa.gz", ">chr1\nACGT\n")
        original = source.read_bytes()
        corrupted = bytearray(original)
        corrupted[-8] ^= 1
        for blob in [bytes(corrupted), original[:-5]]:
            with self.subTest(blob=blob):
                source.write_bytes(blob)
                with self.assertRaises((OSError, EOFError)):
                    MODULE.fasta_names(source)

    def test_assembly_rejects_target_decoy_identifier_collisions(self):
        transcript = self.fasta("transcripts.fa.gz", ">chr1 transcript description\nAAAA\n")
        genome = self.fasta("genome.fa.gz", ">chr1 genomic description\nTTTT\n")
        destination = self.root / "reference"
        with self.assertRaisesRegex(ValueError, "collide"):
            MODULE.assemble(transcript, genome, destination)
        self.assertFalse(destination.exists())

    def test_assembly_rejects_missing_final_newline_without_changing_source_bytes(self):
        transcript = self.fasta("transcripts.fa.gz", ">ENST1.1|ENSG1.1\nAAAA")
        genome = self.fasta("genome.fa.gz", ">chr1\nTTTT\n")
        original = transcript.read_bytes()
        destination = self.root / "reference"
        with self.assertRaisesRegex(ValueError, "newline"):
            MODULE.assemble(transcript, genome, destination)
        self.assertEqual(transcript.read_bytes(), original)
        self.assertFalse(destination.exists())

    def test_assembly_preserves_publisher_bytes_headers_order_and_hashes(self):
        transcript_text = ">ENST2.1|ENSG2.1|other full transcript header\nACGT\n>ENST1.1|ENSG1.1|other another header\nGGAA\n"
        genome_text = ">chr2 chromosome 2 full description\nTTCC\n>chr1 chromosome 1 full description\nAAAA\n"
        transcript = self.fasta("transcripts.fa.gz", transcript_text)
        genome = self.fasta("genome.fa.gz", genome_text)
        original_transcript, original_genome = transcript.read_bytes(), genome.read_bytes()
        result = MODULE.assemble(transcript, genome, self.root / "reference")
        gentrome = Path(result["gentrome"])
        expected = original_transcript + original_genome
        self.assertEqual(gentrome.read_bytes(), expected)
        self.assertEqual(gzip.decompress(expected).decode("ascii"), transcript_text + genome_text)
        self.assertEqual(MODULE.fasta_names(gentrome), ["ENST2.1|ENSG2.1|other", "ENST1.1|ENSG1.1|other", "chr2", "chr1"])
        self.assertEqual((gentrome.parent / "decoys.txt").read_text(), "chr2\nchr1\n")
        self.assertEqual(result["transcript_records"], 2)
        self.assertEqual(result["decoy_records"], 2)
        self.assertEqual(result["decoy_names"], ["chr2", "chr1"])
        self.assertEqual(result["gentrome_bytes"], len(expected))
        self.assertEqual(result["gentrome_sha256"], hashlib.sha256(expected).hexdigest())
        # Hash the actual text-file bytes: Windows may serialize CRLF while
        # Docker serializes LF; both must retain the same ordered identifiers.
        decoys_bytes = (gentrome.parent / "decoys.txt").read_bytes()
        self.assertEqual(decoys_bytes.replace(b"\r\n", b"\n"), b"chr2\nchr1\n")
        self.assertEqual(result["decoys_sha256"], hashlib.sha256(decoys_bytes).hexdigest())
        self.assertEqual(transcript.read_bytes(), original_transcript)
        self.assertEqual(genome.read_bytes(), original_genome)
        self.assertFalse((gentrome.parent / "gentrome.fa.gz.part").exists())

    def test_digest_file_covers_full_compressed_bytes(self):
        path = self.fasta("source.fa.gz", ">chr1\nACGT\n")
        for algorithm in ["md5", "sha256"]:
            self.assertEqual(MODULE.digest_file(path, algorithm), hashlib.new(algorithm, path.read_bytes()).hexdigest())

    def mock_range_server(self, total, fault=None, fault_on_probe=False, reverse_completion=False):
        requests = []
        later_range_started = threading.Event()

        def respond(request, timeout):
            value = request.get_header("Range")
            match = re.fullmatch(r"bytes=(\d+)-(\d+)", value)
            self.assertIsNotNone(match)
            self.assertEqual(request.get_header("Accept-encoding"), "identity")
            start, end = map(int, match.groups())
            requests.append((start, end))
            probe = start == end == 0
            if reverse_completion and not probe:
                if start < (64 << 20):
                    if not later_range_started.wait(5):
                        raise AssertionError("Second range was not scheduled concurrently")
                else:
                    later_range_started.set()
            applicable_fault = fault if probe == fault_on_probe else None
            return RangeResponse(start, end, total, applicable_fault)

        return respond, requests

    def test_range_assembly_resumes_prefix_and_orders_concurrent_pieces(self):
        # Cross the real 64 MiB chunk boundary. The fixture generates each read
        # on demand, and schedules the tail before releasing the first range.
        total, prefix = (64 << 20) + 23, 7
        partial = self.root / "genome.fa.gz.part"
        partial.write_bytes(source_slice(0, prefix))
        server, requests = self.mock_range_server(total, reverse_completion=True)
        with patch.object(MODULE.regen, "_http_with_retry", side_effect=server):
            result = MODULE.download_ranges("https://example.invalid/genome.fa.gz", partial)
        self.assertEqual(set(requests), {(0, 0), (prefix, prefix + (64 << 20) - 1), (prefix + (64 << 20), total - 1)})
        self.assertEqual(result["source_bytes"], total)
        self.assertEqual(result["resumed_prefix_bytes"], prefix)
        self.assertEqual(result["range_count"], 2)
        self.assertEqual(partial.stat().st_size, total)
        actual, expected = hashlib.sha256(), hashlib.sha256()
        position = 0
        with partial.open("rb") as handle:
            while block := handle.read(1 << 20):
                actual.update(block)
                expected.update(source_slice(position, len(block)))
                position += len(block)
        self.assertEqual(actual.hexdigest(), expected.hexdigest())
        self.assertFalse(partial.with_name(partial.name + ".assembled").exists())

    def test_range_download_without_prefix_and_complete_prefix_are_supported(self):
        partial = self.root / "genome.fa.gz.part"
        server, requests = self.mock_range_server(23)
        with patch.object(MODULE.regen, "_http_with_retry", side_effect=server):
            result = MODULE.download_ranges("https://example.invalid/genome.fa.gz", partial)
        self.assertEqual(result["resumed_prefix_bytes"], 0)
        self.assertEqual(requests, [(0, 0), (0, 22)])
        self.assertEqual(partial.read_bytes(), source_slice(0, 23))
        server, requests = self.mock_range_server(23)
        with patch.object(MODULE.regen, "_http_with_retry", side_effect=server):
            result = MODULE.download_ranges("https://example.invalid/genome.fa.gz", partial)
        self.assertEqual(result["resumed_prefix_bytes"], 23)
        self.assertEqual(result["range_count"], 0)
        self.assertEqual(requests, [(0, 0)])
        self.assertEqual(partial.read_bytes(), source_slice(0, 23))

    def test_range_workers_reject_ignored_and_mismatched_ranges(self):
        for fault in ["ignored200", "mismatched_range"]:
            with self.subTest(fault=fault):
                partial = self.root / f"{fault}.part"
                partial.write_bytes(source_slice(0, 3))
                server, _ = self.mock_range_server(23, fault=fault)
                with patch.object(MODULE.regen, "_http_with_retry", side_effect=server):
                    with self.assertRaisesRegex(ValueError, "different range"):
                        MODULE.download_ranges("https://example.invalid/genome.fa.gz", partial)
                self.assertEqual(partial.read_bytes(), source_slice(0, 3))

    def test_range_workers_reject_truncated_and_oversized_bodies(self):
        for fault, message in [("truncated", "truncated"), ("oversized", "exceeds requested size")]:
            with self.subTest(fault=fault):
                partial = self.root / f"{fault}.part"
                partial.write_bytes(source_slice(0, 3))
                server, _ = self.mock_range_server(23, fault=fault)
                with patch.object(MODULE.regen, "_http_with_retry", side_effect=server):
                    with self.assertRaisesRegex(ValueError, message):
                        MODULE.download_ranges("https://example.invalid/genome.fa.gz", partial)
                self.assertEqual(partial.read_bytes(), source_slice(0, 3))

    def test_range_probe_rejects_ignored_mismatched_and_wrong_size_bodies(self):
        for fault in ["ignored200", "mismatched_range", "truncated", "oversized"]:
            with self.subTest(fault=fault):
                partial = self.root / f"probe-{fault}.part"
                server, requests = self.mock_range_server(23, fault=fault, fault_on_probe=True)
                with patch.object(MODULE.regen, "_http_with_retry", side_effect=server):
                    with self.assertRaisesRegex(ValueError, "size-probe range"):
                        MODULE.download_ranges("https://example.invalid/genome.fa.gz", partial)
                self.assertEqual(requests, [(0, 0)])
                self.assertFalse(partial.exists())

    def test_range_probe_rejects_zero_oversized_total_and_oversized_prefix(self):
        for total in [0, MODULE.MAX_DOWNLOAD + 1]:
            with self.subTest(total=total):
                partial = self.root / f"total-{total}.part"
                server, requests = self.mock_range_server(total)
                with patch.object(MODULE.regen, "_http_with_retry", side_effect=server):
                    with self.assertRaisesRegex(ValueError, "exceeds bound"):
                        MODULE.download_ranges("https://example.invalid/genome.fa.gz", partial)
                self.assertEqual(requests, [(0, 0)])
                self.assertFalse(partial.exists())
        partial = self.root / "oversized-prefix.part"
        original = source_slice(0, 24)
        partial.write_bytes(original)
        server, requests = self.mock_range_server(23)
        with patch.object(MODULE.regen, "_http_with_retry", side_effect=server):
            with self.assertRaisesRegex(ValueError, "prefix exceeds source size"):
                MODULE.download_ranges("https://example.invalid/genome.fa.gz", partial)
        self.assertEqual(requests, [(0, 0)])
        self.assertEqual(partial.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
