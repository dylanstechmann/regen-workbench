"""Constructed count fixtures test qualification and arithmetic, not biology."""

import copy
import gzip
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import regen_desk as desk

SPEC = importlib.util.spec_from_file_location("dental_counts", ROOT / "studies/dental-regeneration-2026-10-09/analyze_ameloblast_counts.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class DentalCountTests(unittest.TestCase):
    def setUp(self):
        self.header = "," + ",".join(row[0] for row in analysis.LABELS) + "\n"
        self.metadata = {"series": {"accession": "GSE307437"}, "samples": [
            {"accession": label[1], "fields": {"Sample_title": [label[3]]}} for label in analysis.LABELS]}

    def test_cpm_uses_all_deposited_counts_and_preserves_unknown_units(self):
        rows, qc = analysis.qualify_counts(gzip.compress((self.header + "ENAM,1,1,1,1,1,1\nOTHER,3,3,3,3,3,3\n").encode()), self.metadata)
        self.assertEqual(rows[0], ("ENAM", [250000.0] * 6))
        self.assertEqual(rows[1], ("OTHER", [750000.0] * 6))
        self.assertEqual(qc[0]["assigned_count_total"], 4)
        self.assertEqual(qc[0]["nonzero_gene_rows"], 2)
        self.assertTrue(all(row["independent_donor_id"] is None for row in qc))

    def test_wrong_columns_duplicate_genes_invalid_counts_and_zero_total_fail(self):
        for text in (self.header.replace("WT_isAM_1", "unknown") + "ENAM,1,1,1,1,1,1\n",
                     self.header + "ENAM,1,1,1,1,1,1\nENAM,2,2,2,2,2,2\n",
                     self.header + "ENAM,1.5,1,1,1,1,1\n",
                     self.header + "ENAM,-1,1,1,1,1,1\n",
                     self.header + "ENAM,0,1,1,1,1,1\n",
                     self.header + "ENAM,1,1\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                analysis.qualify_counts(gzip.compress(text.encode()), self.metadata)

    def test_conflicting_metadata_cannot_silently_assign_a_column(self):
        metadata = copy.deepcopy(self.metadata)
        metadata["samples"][0]["fields"]["Sample_title"] = ["Unrelated sample"]
        with self.assertRaisesRegex(ValueError, "correspondence"):
            analysis.qualify_counts(gzip.compress((self.header + "ENAM,1,1,1,1,1,1\n").encode()), metadata)

    def test_descriptive_source_record_roundtrips_without_claiming_tissue_identity(self):
        seeds = json.loads((ROOT / "config/research-blueprints.json").read_text(encoding="utf-8"))
        starter = next(s for s in seeds["campaign_starters"]["organoids"] if s["id"] == "ameloblast-rna-contrast")
        with tempfile.TemporaryDirectory() as directory:
            instance = desk.Desk(Path(directory))
            self.addCleanup(lambda: instance.executor.shutdown(wait=True))
            saved = instance.campaign({**starter, "starter_id": starter["id"], "blueprint_id": "organoids", "id": ""})
            record = saved["evidence_records"][0]
            self.assertEqual(record["source_type"], "dataset")
            self.assertEqual(record["status"], "not assessed")
            self.assertIn("Computational descriptive", record["stage_track"])
            self.assertEqual(record["dataset_sha256"], json.loads((analysis.STUDY / "count_receipt.json").read_text())["response_sha256"])


if __name__ == "__main__":
    unittest.main()
