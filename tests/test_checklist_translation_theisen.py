"""Actual deposited dental tables: identity and denominator failure handling."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "studies/checklist-translation-2026-10-19/dental"
SPEC = importlib.util.spec_from_file_location("theisen_translation", HERE / "analyze_theisen_linked.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class TheisenTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = M.read_json(HERE / "source_extract.json")
        cls.result = M.analyze(cls.data)

    def test_complete_observed_registry(self):
        self.assertEqual(self.result["n_registered_teeth"], 48)
        self.assertEqual(self.result["n_marginal_rows"], 384)
        self.assertEqual(self.data["data_kind"], "observed_public_numeric_tables_not_synthetic")

    def test_identity_conflict_includes_destination_teeth(self):
        audit = self.result["identity_audit"]
        self.assertEqual(audit["n_conflicting_rows"], 57)
        self.assertEqual(audit["n_ambiguous_teeth"], 11)
        self.assertIn("G3_T4", audit["ambiguous_tooth_keys_both_ends"])
        self.assertIn("G4_T10", audit["ambiguous_tooth_keys_both_ends"])
        self.assertEqual(audit["n_internally_consistent_teeth"], 37)

    def test_ambiguous_rows_retained_without_numeric_correction(self):
        row = next(r for r in self.data["marginal_rows"] if r["cells"][0] == "G3_T12_M_R2_InT")
        self.assertEqual(row["cells"][2], "4")
        self.assertEqual(row["source_page"], 4)
        self.assertEqual(row["source_table_row"], 76)

    def test_literal_low_load_retained(self):
        g1 = self.result["literal_fracture_summaries"][0]
        self.assertEqual(g1["n_literal_loads"], 12)
        self.assertAlmostEqual(g1["literal_mean_N"], 1790.9675)
        diagnostic = self.result["g1_load_ambiguity_diagnostic"]
        self.assertEqual(diagnostic["literal_G1_T11_N"], 6.76)
        self.assertEqual(diagnostic["omit_G1_T11_n"], 11)
        self.assertEqual(round(diagnostic["omit_G1_T11_mean_N"], 1), 1953.2)
        self.assertEqual(round(diagnostic["omit_G1_T11_sample_sd_N"], 1), 483.4)

    def test_face_and_tooth_denominators_differ(self):
        rows = self.result["literal_fracture_summaries"]
        self.assertEqual([r["face_category_counts"]["3"] for r in rows], [16, 19, 20, 15])
        self.assertEqual([r["tooth_any_category_counts"]["3"] for r in rows], [7, 9, 11, 8])
        self.assertEqual(sum(r["tooth_any_category_counts"]["3"] for r in rows), 35)

    def test_unknown_margin_field_not_zero_imputed(self):
        margins, _, _ = M.parse_data(self.data)
        row = next(r for r in margins if r["code"] == "G1_T11_D_R2_InCm")
        self.assertIsNone(row["not_assessable_um"])
        low, high = M.full_margin_bounds(row)
        self.assertAlmostEqual(low, 100 * 430.434 / 2609.956)
        self.assertEqual(high, 100)
        self.assertEqual(len(self.result["blank_nonassessable_fields"]), 5)

    def test_known_unassessable_length_expands_whole_margin_interval(self):
        margins, _, _ = M.parse_data(self.data)
        row = next(r for r in margins if r["code"] == "G1_T6_M_R2_InT")
        low, high = M.full_margin_bounds(row)
        self.assertAlmostEqual(low, 100 * 2914.629 / 7956.292)
        self.assertAlmostEqual(high, 100 * (2914.629 + 168.273) / 7956.292)

    def test_primary_subset_and_conditional_code_sensitivity(self):
        strict = self.result["strict_internal_identity_paired_margin_summaries"]
        conditional = self.result["conditional_trust_row_codes_paired_margin_summaries"]
        self.assertEqual([r["n_teeth"] for r in strict], [12, 12, 12, 12, 3, 3, 10, 10])
        self.assertEqual([r["n_teeth"] for r in conditional], [12] * 8)
        self.assertTrue(all(r["interface"] in ("InCm", "InT") for r in strict))
        self.assertAlmostEqual(strict[0]["mean_paired_change_percentage_points"], 0.8643479238315744)

    def test_joint_bounds_keep_all_assigned_teeth(self):
        joint = self.result["joint_recorded_gap_and_terminal_below_bone_fracture"]
        self.assertEqual(joint["denominator_teeth"], 48)
        self.assertEqual(joint["known_joint_positive"], 19)
        self.assertEqual(joint["unknown_from_identity"], 9)
        self.assertEqual(joint["finite_cohort_proportion_bounds"], [19 / 48, 28 / 48])
        self.assertEqual(joint["conditional_trust_row_codes_joint_positive"], 26)

    def test_absent_depth_leakage_fatigue_are_not_filled_from_other_assays(self):
        bridge = self.result["prior_bridge"]
        self.assertEqual(bridge["measured_repair_depth_n"], 0)
        self.assertEqual(bridge["tracer_leakage_n"], 0)
        self.assertEqual(bridge["fatigue_event_time_n"], 0)
        self.assertEqual(bridge["depth_example_result"]["depth_state"], "unassessed_missing_depth")
        self.assertEqual(bridge["fatigue_example_result"], ["unknown", "unmeasured"])
        self.assertTrue(all(r["donor_id"] is None and r["measured_repair_depth_um"] is None for r in self.result["specimen_links"]))

    def test_duplicate_or_lost_row_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["marginal_rows"][1] = copy.deepcopy(bad["marginal_rows"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            M.analyze(bad)
        bad = copy.deepcopy(self.data)
        bad["fracture_rows"].pop()
        with self.assertRaisesRegex(ValueError, "complete"):
            M.analyze(bad)

    def test_impossible_lengths_and_nonfinite_numbers_rejected(self):
        for index, value in ((8, "-1"), (11, "10000"), (8, "NaN")):
            bad = copy.deepcopy(self.data)
            bad["marginal_rows"][0]["cells"][index] = value
            with self.assertRaises(ValueError):
                M.analyze(bad)

    def test_endpoint_state_cannot_be_silently_changed(self):
        bad = copy.deepcopy(self.data)
        bad["marginal_rows"][0]["cells"][5] = "baseline_Inlay"
        with self.assertRaisesRegex(ValueError, "state"):
            M.analyze(bad)

    def test_source_fetch_manifest_has_eight_distinct_retained_byte_hashes(self):
        manifest = M.read_json(HERE / "source_manifest.json")
        retained = manifest["retained_fetches"]
        self.assertEqual(len(retained), 8)
        self.assertEqual(len({r["sha256"] for r in retained}), 8)
        self.assertTrue(all(r["bytes"] > 0 and len(r["sha256"]) == 64 for r in retained))
        self.assertTrue(all(r["cache_path"].startswith("data/literature/checklist-translation-2026-10-19/dental/") for r in retained))

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
                M.read_json(path)


if __name__ == "__main__":
    unittest.main()
