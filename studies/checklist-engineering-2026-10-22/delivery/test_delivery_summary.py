"""Meaningful guards for source-summary scope, timing, precision and provenance."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("delivery_source_summary_20261022", HERE / "analyze_delivery.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class DeliverySourceSummaryTests(unittest.TestCase):
    def setUp(self):
        self.inputs = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))

    def test_printed_annotations_and_signed_differences(self):
        rows = module.compare(self.inputs)["within_formulation_organ_comparisons"]
        self.assertEqual([r["reported_difference_1h_minus_24h"] for r in rows], [.04, .05, .12])
        self.assertEqual([(r["reported_r_squared_1h"],r["reported_r_squared_24h"]) for r in rows], [(.97,.93),(.92,.87),(.98,.86)])

    def test_rounding_enclosures_are_display_only(self):
        result = module.compare(self.inputs)
        self.assertEqual([r["display_rounding_difference_enclosure"] for r in result["within_formulation_organ_comparisons"]], [[.03,.05],[.04,.06],[.11,.13]])
        self.assertIsNone(result["association_difference_significance"])
        self.assertEqual(result["earlier_higher_count_under_rounding_assumption"], 3)

    def test_fixed_reporter_time_does_not_become_two_longitudinal_assays(self):
        for row in module.compare(self.inputs)["within_formulation_organ_comparisons"]:
            self.assertEqual(row["early_association_time_pair_h"], {"qpcr":1,"reporter":24})
            self.assertEqual(row["late_association_time_pair_h"], {"qpcr":24,"reporter":24})

    def test_missing_whole_group_is_rejected(self):
        self.inputs["reported_associations"] = self.inputs["reported_associations"][:4]
        with self.assertRaises(ValueError): module.compare(self.inputs)

    def test_missing_time_is_rejected(self):
        self.inputs["reported_associations"].pop()
        with self.assertRaises(ValueError): module.compare(self.inputs)

    def test_duplicate_panel_or_measurement_is_rejected(self):
        self.inputs["reported_associations"].append(copy.deepcopy(self.inputs["reported_associations"][0]))
        with self.assertRaises(ValueError): module.compare(self.inputs)

    def test_mismatched_organ_panel_cannot_be_repaired_by_position(self):
        self.inputs["reported_associations"][0]["target_organ"] = "spleen"
        with self.assertRaises(ValueError): module.compare(self.inputs)

    def test_boolean_time_is_rejected(self):
        self.inputs["reported_associations"][0]["qpcr_time_h"] = True
        with self.assertRaises(ValueError): module.compare(self.inputs)

    def test_invalid_or_nonfinite_r_squared_is_rejected(self):
        for value in (True, "0.97", -0.01, 1.01, math.inf, math.nan):
            with self.subTest(value=value):
                inputs = copy.deepcopy(self.inputs)
                inputs["reported_associations"][0]["reported_r_squared"] = value
                with self.assertRaises(ValueError): module.compare(inputs)

    def test_no_new_fit_coverage_or_animal_n_is_invented(self):
        result = module.compare(self.inputs)
        self.assertFalse(result["new_correlation_fit"])
        self.assertIsNone(result["out_of_sample_prediction_error"])
        self.assertIsNone(result["independent_animal_n_from_image_fields"])
        self.assertTrue(all(v is None for v in result["unavailable_endpoints"].values()))
        self.assertIsNone(self.inputs["source_units"]["individual_observations_used_per_correlation_fit"])

    def test_late_off_target_accumulation_is_retained(self):
        row = module.compare(self.inputs)["source_reported_discordance"]
        self.assertEqual((row["late_qpcr_predominant_organ"],row["reporter_predominant_organ"]), ("spleen","liver"))
        self.assertIsNone(row["cross_animal_pairing"])

    def test_retained_cache_and_real_receipts_when_available(self):
        manifest = json.loads((HERE / "source_manifest.json").read_text(encoding="utf-8"))
        if not all((module.ROOT / row["cache_path"]).exists() for row in manifest["retained_sources"]):
            self.skipTest("Ignored source cache unavailable; public annotation analysis still reproducible offline")
        self.assertEqual(module.verify_sources(manifest), ["main_xml","figure2"])

    def test_changed_source_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/"source").write_bytes(b"changed")
            manifest={"retained_sources":[{"source_id":"fixture", "cache_path":"source", "bytes":8,"sha256":"0"*64,"actual_fetch_receipt":"receipt"}]}
            with self.assertRaises(ValueError): module.verify_sources(manifest,root)

if __name__ == "__main__":
    unittest.main()
