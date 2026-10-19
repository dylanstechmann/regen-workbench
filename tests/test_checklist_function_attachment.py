"""Observed aggregate mechanics must not become donor or attachment claims."""
import copy
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "studies/checklist-function-2026-10-19/attachment"
SPEC = importlib.util.spec_from_file_location("attachment_function_summaries", HERE / "analyze_mechanical_summaries.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

class AttachmentSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.extract = M.load_json(HERE / "source_summary_extract.json")
        cls.result = M.analyze(cls.extract)

    def test_all_observed_native_rows_and_nested_units_retained(self):
        rows = self.extract["native"]["table2_rows"]
        self.assertEqual(len(rows), 6)
        native = self.result["native_passive_reference"]
        self.assertEqual([native[k] for k in ("independent_human_donors_reported", "teeth_reported", "slices_reported")], [3, 6, 18])
        self.assertFalse(native["individual_donor_ages_or_crosswalk_available"])
        self.assertEqual(len(native["per_regime_branch_ratios"]), 6)

    def test_post_units_do_not_become_tissue_modulus(self):
        r = self.result["magnetic_construct"]
        self.assertEqual(r["post_stiffness_N_per_m"], .95)
        self.assertEqual(r["post_stiffness_N_per_mm"], .00095)
        self.assertAlmostEqual(r["source_active_force_mean_N"], .000739)
        self.assertEqual(r["tissue_modulus"]["status"], "unavailable")
        self.assertEqual(len(r["tissue_modulus"]["missing"]), 3)
        with self.assertRaises(ValueError):
            M.tissue_modulus_gate(.95, 7, 2, .2)

    def test_force_length_algebra_not_independent_validation(self):
        r = self.result["magnetic_construct"]
        self.assertEqual(r["bare_post_force_recomputed_uN"], 408.5)
        self.assertEqual(r["baseline_mean_shortening_um"], 777)
        self.assertEqual(r["baseline_mean_shortening_fraction"], .097125)
        self.assertAlmostEqual(r["force_from_reported_mean_length_and_post_stiffness_uN"], 738.15)
        self.assertAlmostEqual(r["force_mean_relative_difference_percent"], .11502029769959712)
        self.assertIsNone(r["uncertainty_interval"])
        self.assertIn("not independent validation", r["interpretation"])

    def test_source_spreads_preserve_sem_sd_and_unspecified(self):
        magnetic = self.extract["magnetic"]
        self.assertEqual(magnetic["PTC_length_SEM_um"], 37)
        self.assertEqual(magnetic["PTC_active_force_SEM_uN"], 37)
        self.assertIn("Not specified", magnetic["bare_post_spread_definition"])
        self.assertEqual(self.extract["native"]["table2_rows"][0]["E1_SD_MPa"], .45)

    def test_native_regime_changes_are_ratios_of_means_only(self):
        r = self.result["native_passive_reference"]
        central, lateral = r["regime_effects"]
        self.assertAlmostEqual(central["E1_5N_regime_to_1N_regime_ratio_of_means"], 1.82 / .67)
        self.assertAlmostEqual(lateral["E2_5N_regime_to_1N_regime_ratio_of_means"], 4.14 / 2.32)
        self.assertTrue(r["loading_rate_and_peak_load_identically_coupled"])
        changed = copy.deepcopy(self.extract)
        changed["native"]["regimes"][0]["loading_rate_N_per_min"] = 2
        self.assertFalse(M.analyze(changed)["native_passive_reference"]["loading_rate_and_peak_load_identically_coupled"])

    def test_discussion_upper_value_is_not_an_observed_individual_maximum(self):
        r = self.result["native_passive_reference"]
        self.assertEqual(r["all_branch_summary_mean_max_MPa"], 5.59)
        self.assertEqual(r["upper_discussion_value_MPa"], 6.82)
        self.assertEqual(r["largest_E2_mean_plus_its_SD_MPa"], 6.82)
        self.assertIsNone(r["individual_extreme_range"])
        self.assertAlmostEqual(r["ratio_of_largest_to_smallest_summary_mean"], 5.59 / .33)

    def test_transition_strain_not_rupture_and_recovery_not_age_trajectory(self):
        self.assertTrue(all("not a measured rupture" in r["strain_definition"] for r in self.extract["native"]["table2_rows"]))
        context = self.extract["magnetic"]["recovery_measurement_context"]
        self.assertEqual([context[k] for k in ("4h_constructs", "24h_constructs", "1week_constructs")], [5,6,6])
        self.assertIsNone(context["numeric_individual_before_during_after_lengths"])
        self.assertIsNone(self.result["individual_construct_recovery_fraction"])
        self.assertIsNone(self.result["donor_age_effect"])
        self.assertFalse(self.result["rejuvenation_claim"])

    def test_missing_and_duplicate_native_rows_fail(self):
        for replacement in (self.extract["native"]["table2_rows"][:-1], self.extract["native"]["table2_rows"][:-1] + [self.extract["native"]["table2_rows"][0]]):
            altered = copy.deepcopy(self.extract)
            altered["native"]["table2_rows"] = replacement
            with self.assertRaises(ValueError):
                M.analyze(altered)

    def test_nonfinite_nonpositive_and_boolean_values_fail(self):
        for bad in (0, -1, math.nan, math.inf, True):
            altered = copy.deepcopy(self.extract)
            altered["native"]["table2_rows"][0]["E1_mean_MPa"] = bad
            with self.assertRaises(ValueError):
                M.analyze(altered)

    def test_unavailable_attachment_age_and_pose_gates_remain_separate(self):
        rows = M.load_json(HERE / "source_qualification.json")["sources"]
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["donor_count"] for r in rows], [1,3,6])
        for row in rows:
            for field in ("numeric_individual_age", "age_crossed_with_niche", "bilateral_inserted_attachment_measured", "post_washout_age_niche_function_measured", "tooth_pose_after_support_withdrawal_measured"):
                self.assertFalse(row[field])

    def test_actual_download_challenge_is_not_a_supplement(self):
        receipts = M.load_json(HERE / "source_receipts.json")
        self.assertEqual(len(receipts["actual_fetches"]), 4)
        rejected = [r for r in receipts["actual_fetches"] if not r["expected_document_received"]]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["bytes"], 1816)
        self.assertEqual(rejected[0]["classification"], "HTML_download_challenge_not_a_DOCX")
        self.assertEqual(rejected[0]["content_type"], "text/html")
        self.assertEqual({r["http_status"] for r in receipts["failed_attempts"]}, {403,500})
        self.assertTrue(all(not r["fetch_receipt_created"] for r in receipts["failed_attempts"]))

    def test_receipts_pin_inputs_scripts_and_outputs(self):
        receipt = M.load_json(HERE / "derived/analysis_receipt.json")
        mapping = {"analysis_text_sha256": "analyze_mechanical_summaries.py", "plan_text_sha256": "analysis_plan.json",
            "extract_text_sha256": "source_summary_extract.json", "qualification_text_sha256": "source_qualification.json",
            "source_receipts_text_sha256": "source_receipts.json", "results_text_sha256": "derived/mechanical_summary_results.json"}
        for field, name in mapping.items():
            self.assertEqual(receipt[field], M.text_sha(HERE / name))
        self.assertEqual(self.extract["extractor_text_sha256"], M.text_sha(HERE / "extract_numeric_summaries.py"))
        self.assertEqual(self.result, M.load_json(HERE / "derived/mechanical_summary_results.json"))

    def test_duplicate_json_and_nonfinite_constants_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invalid.json"
            for content in ('{"a":1,"a":2}', '{"a":NaN}'):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    M.load_json(path)

if __name__ == "__main__":
    unittest.main()
