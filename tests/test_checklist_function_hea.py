"""Observed HEA source accounting, common-support math and assay boundaries."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "studies/checklist-function-2026-10-19/dental"
SPEC = importlib.util.spec_from_file_location("hea_function", HERE / "analyze_hea_mechanics.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class HEAFunctionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = M.load(HERE / "inputs.json")
        cls.results = M.calculate(cls.data)

    def test_complete_observed_source_set(self):
        self.assertEqual(self.data["source_sheet_count"], 53)
        self.assertEqual(len(self.data["selected_xml_audit"]), 8)
        self.assertEqual(len(self.data["bulk_R_curves"]), 14)
        self.assertEqual(len(self.data["fatigue_displacement_traces"]), 3)
        self.assertEqual(self.results["hierarchy_and_missingness"]["serial_R_curve_points"], 154)
        self.assertEqual(self.results["hierarchy_and_missingness"]["serial_fatigue_points"], 477)

    def test_common_extension_uses_every_curves_support(self):
        main = self.results["main_bulk_R_curve_comparison"]
        direction = self.results["source_label_directional_R_curve_comparison"]
        self.assertEqual(main["common_observed_crack_extension_mm"], [0, 0.0784])
        self.assertEqual(direction["common_observed_crack_extension_mm"], [0, 0.04577])
        for key, context in (("main_bulk_R_curve_comparison", "main_perpendicular"), ("source_label_directional_R_curve_comparison", None)):
            low, high = self.results[key]["common_observed_crack_extension_mm"]
            curves = [c for c in self.data["bulk_R_curves"] if (c["architecture_context"] == context if context else c["architecture_context"] != "main_perpendicular")]
            self.assertTrue(all(c["points"][0][0] <= low < high <= c["points"][-1][0] for c in curves))

    def test_source_curve_midpoint_interpolation(self):
        curve = self.data["bulk_R_curves"][0]["points"]
        left, right = curve[2:4]
        x = (left[0] + right[0]) / 2
        self.assertAlmostEqual(M.interpolate(curve, x), (left[1] + right[1]) / 2)
        self.assertAlmostEqual(M.clipped_integral(curve, left[0], right[0]), (right[0] - left[0]) * (left[1] + right[1]) / 2)

    def test_no_extrapolation_or_silent_coordinate_repair(self):
        curve = self.data["bulk_R_curves"][0]["points"]
        with self.assertRaisesRegex(ValueError, "extrapolation"):
            M.interpolate(curve, curve[-1][0] + 0.001)
        for points in (list(reversed(curve)), curve[:2] + [curve[1]] + curve[2:]):
            with self.assertRaisesRegex(ValueError, "increase strictly"):
                M.validate_trace(points)

    def test_full_clipped_curve_integral_uses_observed_knots(self):
        curve = self.data["bulk_R_curves"][0]["points"]
        upper = 0.0784
        stop_left, stop_right = curve[2:4]
        endpoint = stop_left[1] + (stop_right[1] - stop_left[1]) * (upper - stop_left[0]) / (stop_right[0] - stop_left[0])
        expected = sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(curve[:3], curve[1:3]))
        expected += (upper - stop_left[0]) * (stop_left[1] + endpoint) / 2
        self.assertAlmostEqual(M.clipped_integral(curve, 0, upper), expected)

    def test_actual_aligned_bulk_values_and_ranges(self):
        rows = self.results["main_bulk_R_curve_comparison"]["trace_summaries"]
        self.assertAlmostEqual(rows[0]["trace_mean_K_at_common_upper"], 14.13382983969078)
        self.assertAlmostEqual(rows[1]["trace_mean_K_at_common_upper"], 5.544876646808511)
        self.assertAlmostEqual(rows[2]["trace_mean_K_at_common_upper"], 7.711468045960187)
        self.assertTrue(all(r["n_listed_traces"] == 2 and r["independent_specimen_or_donor_n"] is None for r in rows))
        self.assertTrue(all(r["new_sem_or_confidence_interval"] is None for r in rows))

    def test_unequal_terminal_extensions_not_collapsed(self):
        traces = self.results["main_bulk_R_curve_comparison"]["traces"]
        self.assertEqual(len({t["last_source_crack_extension_mm"] for t in traces}), 6)
        self.assertAlmostEqual(traces[0]["last_source_K"], 19.79316)
        self.assertAlmostEqual(traces[0]["K_at_common_upper_MPa_sqrt_m"], 14.001304642857143)

    def test_fatigue_actual_window_and_nonmonotone_points_retained(self):
        traces = self.results["fatigue_trace_summaries"]
        self.assertEqual([r["decreasing_displacement_steps_retained"] for r in traces], [31, 15, 2])
        self.assertTrue(all(r["observed_cycle_window"] == [100, 150000] for r in traces))
        self.assertAlmostEqual(traces[1]["change_over_observed_window_mm"], 0.15526)
        self.assertAlmostEqual(traces[1]["cycle_weighted_mean_displacement_mm"], 0.0780218512341561)
        self.assertTrue(all(r["failure_time_or_survival_probability"] is None for r in traces))

    def test_roughness_adverse_direction_is_not_recast_as_equivalence(self):
        rows = self.results["roughness_summary_changes"]
        self.assertEqual([r["material"] for r in rows], ["HEA", "enamel", "EA"])
        self.assertAlmostEqual(rows[0]["relative_change_of_reported_means_percent"], 23.283582089552233)
        self.assertAlmostEqual(rows[2]["difference_of_reported_means_nm"], 8.73)
        self.assertTrue(all(r["difference_of_reported_means_nm"] > 0 and r["paired_individual_change_variance_or_CI"] is None for r in rows))

    def test_source_summary_is_separate_from_listed_curves(self):
        summary = self.results["published_toughness_summaries_kept_separate"][0]
        self.assertEqual(summary["KIC_mean"], 3.79)
        self.assertEqual(summary["KJC_source_sd"], 2.9)
        self.assertIsNone(summary["raw_specimen_crosswalk"])
        self.assertFalse(self.results["source_summary_reconstruction_from_two_curves_attempted"])

    def test_calibration_is_not_host_bond_data(self):
        audit = self.results["interface_assay_audit"]
        self.assertEqual(audit["sheet"], "Supplementary Fig. 48")
        self.assertFalse(audit["is_host_enamel_shear_bond_dataset"])
        self.assertTrue(audit["numeric_force_curve_not_used_as_interface_data"])
        self.assertEqual(audit["identified_host_bond_numeric_table"], "Supplementary Fig. 8")
        self.assertFalse(self.results["full_repair_depth_interface_durability_eligible"])

    def test_actual_fig8_interface_traces_are_not_fig48_calibration(self):
        comparison = self.results["host_enamel_delamination_source_ordinate_comparison"]
        self.assertEqual([r["n_serial_points"] for r in comparison["traces"]], [298, 193])
        self.assertEqual([r["peak_source_stress_ordinate"] for r in comparison["traces"]], [63.39339, 18.50492])
        self.assertAlmostEqual(comparison["peak_ordinate_ratio_HEA_to_ZrO2"], 3.425758663101489)
        self.assertTrue(all(r["absolute_stress_unit_validated"] is None for r in comparison["traces"]))
        self.assertIsNone(comparison["host_interface_fatigue_or_repair_depth_linkage"])
        bad = copy.deepcopy(self.data)
        bad["interface_delamination_traces"][0]["source_sheet"] = "Supplementary Fig. 48"
        with self.assertRaisesRegex(ValueError, "delamination"):
            M.calculate(bad)

    def test_missing_thickness_donors_and_full_restoration_not_imputed(self):
        missing = self.results["hierarchy_and_missingness"]
        for key in ("donor_count", "independent_specimen_count_from_deposited_vectors", "per_specimen_measured_repair_thickness", "joint_host_interface_fatigue_or_leakage", "native_PDL_gum_pulp_and_pose_after_finite_support"):
            self.assertIsNone(missing[key])
        self.assertIsNone(self.results["calendar_life_or_growth_forecast"])

    def test_nonfinite_source_value_rejected(self):
        for value in (True, None, "1", float("nan"), float("inf"), -1):
            with self.subTest(value=value):
                bad = copy.deepcopy(self.data)
                bad["bulk_R_curves"][0]["points"][0][1] = value
                with self.assertRaises(ValueError):
                    M.calculate(bad)

    def test_incomplete_or_duplicate_observed_trace_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["fatigue_displacement_traces"][0]["points"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            M.calculate(bad)
        bad = copy.deepcopy(self.data)
        bad["bulk_R_curves"][1]["trace_identity"] = bad["bulk_R_curves"][0]["trace_identity"]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            M.calculate(bad)


if __name__ == "__main__":
    unittest.main()
