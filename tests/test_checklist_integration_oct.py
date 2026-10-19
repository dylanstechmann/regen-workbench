"""Real post-thermal-cycle interface data: hierarchy, sensitivity and limits."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "studies/checklist-integration-2026-10-19/materials"
SPEC = importlib.util.spec_from_file_location("oct_integration", HERE / "analyze_oct_interface.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class OCTIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = M.load(HERE / "inputs.json")
        cls.results = M.calculate(cls.data)

    def test_complete_observed_source_and_source_group_means(self):
        rows = self.results["group_summaries"]
        self.assertEqual([r["n_source_scan_rows"] for r in rows], [50] * 4)
        self.assertEqual(self.data["oct_source"]["source_numeric_observations"], 200)
        self.assertEqual([r["source_row_mean_percent"] for r in rows], [34.34646, 33.50206, 27.29802, 30.10082])

    def test_conditional_block_summary_reproduces_paper_without_invented_ids(self):
        audit = self.results["source_table2_reconciliation"]
        self.assertTrue(all(r["rounded_block_mean_matches"] and r["rounded_block_sd_matches"] for r in audit))
        self.assertEqual(self.results["source_reported_OCT_teeth_per_group"], 5)
        self.assertIsNone(self.results["independent_donor_count"])
        self.assertTrue(all(b["tooth_id"] is None and b["donor_id"] is None for g in self.data["oct_source"]["groups"] for b in g["worksheet_blocks"]))

    def test_scan_sd_is_not_reported_tooth_sd(self):
        se = self.results["group_summaries"][2]
        self.assertAlmostEqual(se["source_row_sample_sd_percent_not_independent_tooth_sd"], 8.637869846749703)
        self.assertAlmostEqual(se["conditional_block_as_tooth_summary"]["sample_sd_of_block_means_percent"], 1.8985801186676319)
        self.assertIsNone(self.results["new_p_value_or_confidence_interval"])
        self.assertFalse(self.results["equivalence_established"])

    def test_etch_specific_contrasts_and_unfavorable_SE_direction(self):
        er, se = self.results["etch_specific_CHX_descriptive_contrasts"]
        self.assertAlmostEqual(er["difference_of_source_means_percentage_points"], -0.8444)
        self.assertAlmostEqual(se["difference_of_source_means_percentage_points"], 2.8028)
        self.assertAlmostEqual(self.results["SE_minus_ER_contrast_of_mean_differences_percentage_points"], 3.6472)

    def test_block_deletion_uses_all_unpaired_combinations(self):
        er, se = self.results["etch_specific_CHX_descriptive_contrasts"]
        self.assertEqual(er["deletion_combinations"], 25)
        for actual, expected in zip(er["independent_block_deletion_contrast_range_percentage_points"], [-4.348675, 1.87315]):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(se["independent_block_deletion_contrast_range_percentage_points"], [0.871075, 4.8865]):
            self.assertAlmostEqual(actual, expected)

    def test_repeated_run_retained_with_original_locations(self):
        repeat = self.results["group_summaries"][0]["repeated_runs_at_least_three_values"][0]
        self.assertEqual(repeat["length"], 7)
        self.assertEqual(repeat["left_source_cells"], [f"A{r}" for r in range(13, 20)])
        self.assertEqual(repeat["right_source_cells"], [f"A{r}" for r in range(46, 53)])
        self.assertEqual(self.results["group_summaries"][0]["n_source_scan_rows"], 50)

    def test_separate_tensile_summary_does_not_fill_missing_crosswalk(self):
        self.assertIsNone(self.results["cross_endpoint_specimen_pairing"])
        self.assertIsNone(self.results["OCT_to_microtensile_correlation"])
        tensile = self.results["published_unlinked_tensile_table3_not_pooled"]
        self.assertEqual(tensile[3]["mean_MPa"], 13.1)
        self.assertEqual(tensile[3]["adhesive_cohesive_mixed_counts"], [9, 0, 1])

    def test_nominal_depth_and_postchallenge_assay_do_not_become_durability_curve(self):
        self.assertEqual(self.results["source_reported_nominal_cavity_depth_mm"], 2)
        self.assertEqual(self.results["thermal_cycles_before_OCT"], 10000)
        for key in ("actual_specimen_repair_depth_um", "mechanical_fatigue_cycle_history", "baseline_OCT_before_aging", "depth_response_or_within_specimen_change", "pretest_failures_or_unreported_losses"):
            self.assertIsNone(self.results[key])
        self.assertFalse(self.results["full_native_restoration_and_finite_support_withdrawal_qualified"])

    def test_incomplete_or_reassigned_source_block_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["oct_source"]["groups"][0]["worksheet_blocks"][0]["values_percent"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            M.calculate(bad)
        bad = copy.deepcopy(self.data)
        bad["oct_source"]["groups"][0]["source_column"] = "B"
        with self.assertRaisesRegex(ValueError, "mapping"):
            M.calculate(bad)

    def test_out_of_range_or_nonfinite_percentage_rejected(self):
        for value in (None, True, "30", -1, 101, float("nan"), float("inf")):
            with self.subTest(value=value):
                bad = copy.deepcopy(self.data)
                bad["oct_source"]["groups"][0]["worksheet_blocks"][0]["values_percent"][0] = value
                with self.assertRaises(ValueError):
                    M.calculate(bad)


if __name__ == "__main__":
    unittest.main()
