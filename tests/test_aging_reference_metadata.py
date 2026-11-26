"""Check the metadata pin with synthetic files and no source retrieval."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

STUDY = Path(__file__).resolve().parents[1] / "studies" / "aging-state-2026-10-11"
sys.path.insert(0, str(STUDY))
import analyze_fibroblast_age_reference as analysis
import analyze_reprogramming_endpoints as endpoint_analysis
import fetch_aging_reference as intake
import fetch_reprogramming_inputs as endpoint_intake


class AgingReferenceMetadataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.cache = Path(temporary.name)
        self.sample_metadata = {
            "samples": [{"accession": "fixture", "fields": {"Sample_characteristics_ch1": ["age: 40"]}}]
        }
        self.metadata_path = self.cache / intake.METADATA_FILENAME
        raw = json.dumps(self.sample_metadata).encode("utf-8")
        self.metadata_path.write_bytes(raw)
        self.receipt = {
            "files": {"series_metadata": {"metadata_json_sha256": hashlib.sha256(raw).hexdigest()}}
        }

    def test_verified_metadata_is_available_to_analysis(self):
        self.assertEqual(intake.load_verified_metadata(self.cache, self.receipt), self.sample_metadata)

    def test_analysis_refuses_changed_age_metadata_before_reading_matrix(self):
        receipt_path = self.cache / "receipt.json"
        receipt_path.write_text(json.dumps(self.receipt), encoding="utf-8")
        original = self.metadata_path.read_bytes()
        self.metadata_path.write_bytes(original.replace(b"age: 40", b"age: 60"))

        with patch.object(analysis, "CACHE", self.cache), patch.object(analysis, "INTAKE_RECEIPT", receipt_path):
            with self.assertRaisesRegex(ValueError, "GSE113957 sample metadata hash does not match"):
                analysis.main()


class AgingReferenceIntakeTests(unittest.TestCase):
    def test_existing_metadata_pin_survives_a_changed_parser(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "literature" / "aging-reference-GSE113957"
            cache.mkdir(parents=True)
            pins = {}
            for key, (_, filename) in intake.FILES.items():
                raw = key.encode()
                (cache / filename).write_bytes(raw)
                pins[key] = {"filename": filename, "sha256": hashlib.sha256(raw).hexdigest()}
            previous_metadata = b'{"samples": []}\n'
            (cache / intake.METADATA_FILENAME).write_bytes(previous_metadata)
            pins["series_metadata"]["metadata_json_sha256"] = hashlib.sha256(previous_metadata).hexdigest()
            receipt = root / "receipt.json"
            original_receipt = json.dumps({"accession": intake.ACCESSION, "files": pins}).encode()
            receipt.write_bytes(original_receipt)
            with (
                patch.object(intake, "INTAKE_RECEIPT", receipt),
                patch.object(intake.regen, "DATA", root),
                patch.object(intake, "parse_soft", return_value={"samples": [], "series_fields": {}, "expanded_bytes": 1}),
                patch.object(intake, "inspect_matrix", return_value={}),
                patch.object(intake.regen, "record") as record,
            ):
                with self.assertRaisesRegex(ValueError, "parsed metadata hash does not match"):
                    intake.main()
            self.assertEqual((cache / intake.METADATA_FILENAME).read_bytes(), previous_metadata)
            self.assertEqual(receipt.read_bytes(), original_receipt)
            record.assert_not_called()

    def test_existing_source_pin_rejects_changed_cache_or_download(self):
        for cached in (True, False):
            with self.subTest(cached=cached), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                cache = root / "literature" / "aging-reference-GSE113957"
                cache.mkdir(parents=True)
                expected = b"pinned source fixture"
                changed = b"different source fixture"
                _, filename = intake.FILES["series_metadata"]
                source = cache / filename
                if cached:
                    source.write_bytes(changed)
                receipt_path = root / "receipt.json"
                receipt_bytes = json.dumps({
                    "accession": intake.ACCESSION,
                    "files": {"series_metadata": {"filename": filename,
                                                   "sha256": hashlib.sha256(expected).hexdigest()}},
                }).encode("utf-8")
                receipt_path.write_bytes(receipt_bytes)

                with (
                    patch.object(intake, "INTAKE_RECEIPT", receipt_path),
                    patch.object(intake.regen, "DATA", root),
                    patch.object(intake.regen, "http_bytes", return_value=changed) as download,
                    patch.object(intake.regen, "record") as record,
                    patch.object(intake, "parse_soft") as parse_soft,
                ):
                    with self.assertRaisesRegex(ValueError, "source hash does not match"):
                        intake.main()

                self.assertEqual(download.call_count, 0 if cached else 1)
                self.assertEqual(receipt_path.read_bytes(), receipt_bytes)
                self.assertFalse((cache / intake.METADATA_FILENAME).exists())
                if cached:
                    self.assertEqual(source.read_bytes(), changed)
                else:
                    self.assertFalse(source.exists())
                parse_soft.assert_not_called()
                record.assert_not_called()


class ReprogrammingMetadataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.cache = Path(temporary.name)
        self.metadata = {"sample_metadata": [{"accession": "fixture"}]}
        self.metadata_path = self.cache / endpoint_intake.METADATA_FILENAME
        raw = json.dumps(self.metadata).encode("utf-8")
        self.metadata_path.write_bytes(raw)
        self.receipt = {
            "files": {"series_metadata": {"metadata_json_sha256": hashlib.sha256(raw).hexdigest()}}
        }

    def test_reads_verified_target_metadata(self):
        self.assertEqual(endpoint_intake.load_verified_metadata(self.cache, self.receipt), self.metadata)

    def test_endpoint_analysis_rejects_changed_target_metadata_before_reading_expression(self):
        self.metadata_path.write_text('{"sample_metadata": []}', encoding="utf-8")
        with patch.object(endpoint_analysis, "CACHE", self.cache):
            with self.assertRaisesRegex(ValueError, "GSE165177 sample metadata hash does not match"):
                endpoint_analysis.load_input_manifest(self.receipt)

    @unittest.skipUnless(all(importlib.util.find_spec(name) for name in ("numpy", "scipy")),
                         "broad age-state analysis requires NumPy and SciPy")
    def test_broad_age_state_rejects_changed_target_metadata_before_reading_expression(self):
        import analyze_broad_age_state as broad_age_state

        self.metadata_path.write_text('{"sample_metadata": []}', encoding="utf-8")
        with patch.object(broad_age_state, "TARGET_CACHE", self.cache):
            with self.assertRaisesRegex(ValueError, "GSE165177 sample metadata hash does not match"):
                broad_age_state.load_target_expression(self.receipt)


if __name__ == "__main__":
    unittest.main()
