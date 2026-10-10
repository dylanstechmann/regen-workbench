"""Constructed metadata fixtures and source-report boundaries, not RNA analysis."""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location("dental_geo_intake", ROOT / "studies/dental-regeneration-2026-10-09/fetch_geo_metadata.py")
intake = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(intake)


class GeoMetadataTests(unittest.TestCase):
    def setUp(self):
        self.fixture = (
            "^SERIES = GSE0\n!Series_sample_id = GSM0\n^SAMPLE = GSM0\n"
            "!Sample_title = Incisors_20_22w\n!Sample_characteristics_ch1 = tissue: Fetal molar tooth germ\n"
            "!Sample_relation = BioSample: https://www.ncbi.nlm.nih.gov/biosample/SAMN000\n"
            "!Sample_relation = SRA: https://www.ncbi.nlm.nih.gov/sra?term=SRX000\n"
            "!sample_table_begin\ngene\tvalue\nENAM\t100\n!sample_table_end"
        )

    def test_table_values_are_not_parsed_and_conflicting_tissue_is_not_corrected(self):
        parsed = intake.parse_metadata(self.fixture, "GSE0")
        report = intake.summarize_metadata(parsed)
        self.assertEqual(report["n_source_sample_records"], 1)
        self.assertFalse(report["expression_values_parsed"])
        self.assertEqual(len(report["source_annotation_conflicts"]), 1)
        self.assertIsNone(report["samples"][0]["independent_donor_id"])
        self.assertEqual(report["samples"][0]["source_relations"], [
            "BioSample: https://www.ncbi.nlm.nih.gov/biosample/SAMN000",
            "SRA: https://www.ncbi.nlm.nih.gov/sra?term=SRX000",
        ])
        self.assertNotIn("ENAM", json.dumps(report))

    def test_wrong_accession_duplicate_samples_and_incomplete_family_fail(self):
        with self.assertRaises(ValueError):
            intake.parse_metadata(self.fixture, "GSE9")
        with self.assertRaises(ValueError):
            intake.parse_metadata(self.fixture + "\n^SAMPLE = GSM0", "GSE0")
        with self.assertRaises(ValueError):
            intake.parse_metadata(self.fixture.replace("!Series_sample_id = GSM0", "!Series_sample_id = GSM1"), "GSE0")

    def test_public_reports_preserve_source_counts_and_unqualified_independence(self):
        report = json.loads((ROOT / "studies/dental-regeneration-2026-10-09/geo_qualification.json").read_text(encoding="utf-8"))
        datasets = {d["accession"]: d for d in report["datasets"]}
        self.assertEqual(datasets["GSE307437"]["n_source_sample_records"], 6)
        self.assertEqual(datasets["GSE184749"]["n_source_sample_records"], 19)
        self.assertEqual(datasets["GSE307437"]["declared_cell_line_labels"], ["WTC-11"])
        first_sample = datasets["GSE307437"]["samples"][0]
        self.assertEqual(first_sample["sample_accession"], "GSM9224208")
        self.assertEqual(first_sample["source_relations"], [
            "BioSample: https://www.ncbi.nlm.nih.gov/biosample/SAMN51222985",
            "SRA: https://www.ncbi.nlm.nih.gov/sra?term=SRX30400796",
        ])
        for sample in datasets["GSE307437"]["samples"]:
            self.assertEqual(len([item for item in sample["source_relations"] if item.startswith("BioSample: ")]), 1)
            self.assertEqual(len([item for item in sample["source_relations"] if item.startswith("SRA: ")]), 1)
        for dataset in datasets.values():
            self.assertFalse(dataset["eligible_for_donor_heldout_claim"])
            self.assertFalse(dataset["reuse_license_qualified"])
            self.assertFalse(dataset["matrix_columns_qualified"])


if __name__ == "__main__":
    unittest.main()
