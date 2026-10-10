import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "studies" / "dental-regeneration-2026-10-09" / "fetch_pdls_maturity_metadata.py"
SPEC = importlib.util.spec_from_file_location("fetch_pdls_maturity_metadata", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PDLsMaturityMetadataTests(unittest.TestCase):
    def test_source_sample_labels_are_kept_separate_from_donor_units(self):
        soft = """^SERIES = GSE306722
!Series_sample_id = GSM9206804
!Series_sample_id = GSM9206805
^SAMPLE = GSM9206804
!Sample_title = Periodontal ligament, immature
!Sample_characteristics_ch1 = development stage: Immature
!Sample_relation = SRA: https://www.ncbi.nlm.nih.gov/sra?term=SRX1
!Sample_supplementary_file_1 = https://example.org/immature_matrix.mtx.gz
^SAMPLE = GSM9206805
!Sample_title = Periodontal ligament, mature
!Sample_characteristics_ch1 = development stage: Mature
!Sample_relation = SRA: https://www.ncbi.nlm.nih.gov/sra?term=SRX2
"""
        metadata = MODULE.parse_soft(soft)
        report = MODULE.summarize(metadata, b"fixture", "fixture.json", "2026-10-10T00:00:00Z")
        self.assertEqual(report["n_geo_sample_records"], 2)
        self.assertEqual(report["sample_records_by_stage_label"], {"immature": 1, "mature": 1, "unclassified": 0})
        self.assertTrue(all(sample["donor_id"] is None for sample in report["samples"]))
        self.assertEqual(report["samples"][0]["supplementary_files"], ["https://example.org/immature_matrix.mtx.gz"])
        self.assertFalse(report["qualification"]["biological_replicates_qualified"])
        self.assertFalse(report["qualification"]["donor_held_out_comparison_eligible"])

    def test_rejects_series_sample_list_mismatch(self):
        soft = """^SERIES = GSE306722
!Series_sample_id = GSM1
^SAMPLE = GSM2
!Sample_title = unrelated
"""
        with self.assertRaisesRegex(ValueError, "sample list"):
            MODULE.parse_soft(soft)


if __name__ == "__main__":
    unittest.main()
