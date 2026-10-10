"""Independent checks on decoy-driver layout, completion and safe resume."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


STUDY = Path(__file__).resolve().parents[1] / "studies/dental-regeneration-2026-10-09"
SPEC = importlib.util.spec_from_file_location("ipspdl_decoy_driver", STUDY / "run_ipspdl_decoy_rnaseq.py")
driver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(driver)


class LayoutAndCompletion(unittest.TestCase):
    def test_paired_and_single_commands_preserve_same_quantification_options(self):
        with patch.object(driver, "DATA", Path("fixture/reads")), patch.object(driver, "INDEX", Path("fixture/index")), patch.object(driver, "OUT", Path("fixture/quant")):
            paired, mates = driver.run_command({"run": "DRR913328", "layout": "paired"}, 4)
            single, unmated = driver.run_command({"run": "DRR913336", "layout": "single/unspecified"}, 4)
        self.assertEqual([path.name for path in mates], ["DRR913328_1.fastq.gz", "DRR913328_2.fastq.gz"])
        self.assertEqual([path.name for path in unmated], ["DRR913336.fastq.gz"])
        for command in (paired, single):
            self.assertEqual(command[:2], ["salmon", "quant"])
            self.assertEqual(command[command.index("--libType")+1], "A")
            self.assertEqual(command[command.index("--threads")+1], "4")
            self.assertIn("--seqBias", command)
            self.assertIn("--gcBias", command)
            self.assertEqual(command[command.index("--index")+1], str(Path("fixture/index")))
        self.assertEqual(paired[paired.index("--mates1")+1], str(mates[0]))
        self.assertEqual(paired[paired.index("--mates2")+1], str(mates[1]))
        self.assertNotIn("--unmatedReads", paired)
        self.assertEqual(single[single.index("--unmatedReads")+1], str(unmated[0]))
        self.assertNotIn("--mates1", single)
        self.assertNotIn("--mates2", single)
        self.assertEqual(single[single.index("--output")+1], str(Path("fixture/quant/DRR913336")))

    def test_unsupported_library_layout_is_rejected(self):
        for layout in ("", "single", "unknown", "paired-end"):
            with self.subTest(layout=layout), self.assertRaisesRegex(ValueError, "Unsupported layout"):
                driver.run_command({"run": "DRR913336", "layout": layout}, 4)

    def test_completed_estimate_requires_explicit_booleans_and_empty_errors(self):
        good = {"meta_info_complete": True, "em_converged": True, "quant_errors": []}
        self.assertTrue(driver.complete_metadata(good))
        bad = [{}, {**good, "meta_info_complete": False}, {**good, "em_converged": False},
               {**good, "meta_info_complete": 1}, {**good, "em_converged": "true"},
               {**good, "quant_errors": ["error"]}, {**good, "quant_errors": None}]
        for metadata in bad:
            with self.subTest(metadata=metadata):
                self.assertFalse(driver.complete_metadata(metadata))


class HashBoundResume(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)/"DRR913328"
        self.output.mkdir()
        (self.output/"aux_info").mkdir()
        self.quant = self.output/"quant.sf"
        self.meta = self.output/"aux_info/meta_info.json"
        self.quant.write_text("Name\tLength\tEffectiveLength\tTPM\tNumReads\nENST1|ENSG1\t100\t90\t1000000\t900\n", encoding="utf-8")
        metadata = {"meta_info_complete": True, "em_converged": True, "quant_errors": [], "percent_mapped": 90.}
        self.meta.write_text(json.dumps(metadata), encoding="utf-8")
        self.binding = {"salmon_version": "salmon 2.7.0", "driver_sha256": "driver-hash",
                        "manifest_sha256": "manifest-hash", "reference_receipt_sha256": "reference-hash",
                        "command": ["salmon", "quant", "--libType", "A"],
                        "inputs": [{"filename": "R1.fastq.gz", "sha256": "read-hash", "bytes": 123}]}
        self.record = {"run": "DRR913328", "binding": self.binding, "status": "completed", "exit_code": 0,
                       "quant_sha256": driver.sha(self.quant), "metadata_sha256": driver.sha(self.meta), "metadata": metadata}
        self.receipt = self.output/"runner_receipt.json"
        self.write_receipt(self.record)

    def write_receipt(self, record: dict) -> None:
        self.receipt.write_text(json.dumps(record), encoding="utf-8")

    def test_unchanged_completed_output_can_be_reused(self):
        result = driver.reuse_completed(self.output, copy.deepcopy(self.binding))
        self.assertEqual(result["run"], "DRR913328")
        self.assertEqual(result["quant_sha256"], driver.sha(self.quant))
        self.assertEqual(result["metadata_sha256"], driver.sha(self.meta))

    def test_any_input_reference_command_or_driver_binding_change_blocks_resume(self):
        for key in ("salmon_version", "driver_sha256", "manifest_sha256", "reference_receipt_sha256", "command", "inputs"):
            changed = copy.deepcopy(self.binding)
            changed[key] = "changed"
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "different binding"):
                driver.reuse_completed(self.output, changed)

    def test_missing_invalid_or_incomplete_receipt_blocks_resume(self):
        self.receipt.unlink()
        with self.assertRaisesRegex(ValueError, "no completed receipt"):
            driver.reuse_completed(self.output, self.binding)
        self.receipt.write_text("{invalid", encoding="utf-8")
        with self.assertRaises(ValueError):
            driver.reuse_completed(self.output, self.binding)
        for status in ("running", "failed", None):
            self.write_receipt({**self.record, "status": status})
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, "did not complete"):
                driver.reuse_completed(self.output, self.binding)

    def test_corrupted_quantification_and_quant_hash_are_rejected(self):
        self.quant.write_text("corrupted", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "quantification bytes differ"):
            driver.reuse_completed(self.output, self.binding)
        self.record["quant_sha256"] = driver.sha(self.quant)
        self.write_receipt({**self.record, "quant_sha256": "corrupted-receipt-digest"})
        with self.assertRaisesRegex(ValueError, "quantification bytes differ"):
            driver.reuse_completed(self.output, self.binding)

    def test_changed_metadata_and_metadata_hash_are_rejected(self):
        self.meta.write_text(json.dumps({**self.record["metadata"], "percent_mapped": 12.}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            driver.reuse_completed(self.output, self.binding)
        self.write_receipt({**self.record, "metadata_sha256": "corrupted-receipt-digest"})
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            driver.reuse_completed(self.output, self.binding)

    def test_embedded_receipt_metadata_cannot_disagree_with_verified_output(self):
        corrupted = copy.deepcopy(self.record)
        corrupted["metadata"]["percent_mapped"] = 12.
        self.write_receipt(corrupted)
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            driver.reuse_completed(self.output, self.binding)

    def test_nonconvergence_is_rejected_even_if_receipt_hash_matches(self):
        metadata = {**self.record["metadata"], "em_converged": False}
        self.meta.write_text(json.dumps(metadata), encoding="utf-8")
        self.write_receipt({**self.record, "metadata_sha256": driver.sha(self.meta), "metadata": metadata})
        with self.assertRaisesRegex(ValueError, "did not converge"):
            driver.reuse_completed(self.output, self.binding)


if __name__ == "__main__":
    unittest.main()
