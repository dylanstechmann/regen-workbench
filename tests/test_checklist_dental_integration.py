"""Study checks: preserve missing-volume compartments and mechanics non-claims."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "studies/checklist-progress-2026-10-19/dental"
SPEC = importlib.util.spec_from_file_location("checklist_dental_integration", STUDY / "analyze_integration_gaps.py")
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)


class DentalIntegrationStudyTests(unittest.TestCase):
    def setUp(self):
        self.inputs = ANALYSIS.load_json(STUDY / "inputs.json")

    def test_missing_compartments_are_separate_and_interval_preserved(self):
        budget = ANALYSIS.gap_budgets(self.inputs)
        combined = next(s for s in budget["scenarios"] if s["scenario_id"] == "combined_enamel_dentin_fixture")
        self.assertEqual(budget["reference_area_mm2"], 8)
        self.assertEqual(combined["missing_enamel_volume_mm3"], 4)
        self.assertEqual(combined["missing_dentin_volume_mm3"], 4)
        self.assertEqual(combined["dentin_volume_sensitivity_bounds_mm3"], [3.2, 4.8])

    def test_source_nominal_depth_conversion_and_no_dentin_recovery_inference(self):
        budget = ANALYSIS.gap_budgets(self.inputs)
        row = next(c for c in budget["comparisons"] if c["scenario_id"] == "combined_enamel_dentin_fixture")
        self.assertEqual(row["nominal_prism_equivalent_layer_volume_mm3"], 0.04)
        self.assertEqual(row["nominal_layer_to_missing_enamel_depth_percent"], 1)
        self.assertIsNone(row["qualified_dentin_volume_recovery_mm3"])
        self.assertFalse(row["full_area_coverage_verified"])

    def test_known_source_depth_has_no_fabricated_confidence_interval(self):
        rows = ANALYSIS.gap_budgets(self.inputs)["comparisons"]
        row = next(c for c in rows if c["scenario_id"] == "bulk_enamel_fixture" and c["source_configuration"] == "hasan_aprismatic_10um")
        self.assertEqual(row["nominal_layer_to_missing_enamel_depth_percent"], 2)
        self.assertAlmostEqual(row["target_bounds_only_depth_percent_range"][0], 1.8181818181818181)
        self.assertAlmostEqual(row["target_bounds_only_depth_percent_range"][1], 2.2222222222222223)
        self.assertIsNone(row["source_measurement_uncertainty_um"])

    def test_unqualified_substrate_is_retained_without_transfer_estimate(self):
        budget = ANALYSIS.gap_budgets(self.inputs)
        case = next(s for s in budget["scenarios"] if s["substrate"] == "restorative_boundary")
        self.assertEqual(case["source_transfer_state"], "unsupported_substrate")
        self.assertEqual(case["matching_source_configurations"], 0)
        self.assertFalse(any(c["scenario_id"] == case["scenario_id"] for c in budget["comparisons"]))

    def test_zero_axial_baseline_moment_does_not_create_infinite_ratio(self):
        rows = ANALYSIS.moment_sensitivity(self.inputs)
        positive = next(r for r in rows if r["load_direction"] == "axial" and r["contact_case"] == "positive_lateral_offset")
        negative = next(r for r in rows if r["load_direction"] == "axial" and r["contact_case"] == "negative_lateral_offset")
        self.assertEqual(positive["restored_moment_vector_Nmm_per_N"], [0.0, 0.5, 0.0])
        self.assertEqual(negative["restored_moment_vector_Nmm_per_N"], [0.0, -0.5, 0.0])
        self.assertIsNone(positive["moment_magnitude_change_percent"])

    def test_geometry_can_increase_or_decrease_moment_without_drift_prediction(self):
        rows = [r for r in ANALYSIS.moment_sensitivity(self.inputs) if r["load_direction"] == "oblique"]
        changes = {r["contact_case"]: r["moment_magnitude_change_percent"] for r in rows}
        self.assertAlmostEqual(changes["height_only"], 12.5)
        self.assertAlmostEqual(changes["positive_lateral_offset"], 34.15063509461096)
        self.assertAlmostEqual(changes["negative_lateral_offset"], -9.15063509461096)
        self.assertTrue(all(r["predicted_pose_drift_mm"] is None and r["PDL_strain"] is None for r in rows))

    def test_invalid_target_bounds_and_boolean_depth_rejected(self):
        for depth, bound in ((0.5, [0.6, 0.8]), (0.5, [0, 0.8]), (True, [0, 1])):
            inputs = copy.deepcopy(self.inputs)
            inputs["defect_scenarios"][0]["missing_enamel_depth_mm"] = depth
            inputs["defect_scenarios"][0]["enamel_depth_sensitivity_bounds_mm"] = bound
            with self.assertRaises(ValueError):
                ANALYSIS.gap_budgets(inputs)

    def test_unqualified_force_or_material_model_rejected(self):
        for key in ("load_magnitude_N", "support_load_share", "PDL_material_law", "interface_strength"):
            inputs = copy.deepcopy(self.inputs)
            inputs["moment_sensitivity"][key] = 1
            with self.assertRaises(ValueError):
                ANALYSIS.moment_sensitivity(inputs)
        self.inputs["moment_sensitivity"]["unit_load_directions"][0]["vector"] = [0, 0, -2]
        with self.assertRaises(ValueError):
            ANALYSIS.moment_sensitivity(self.inputs)

    def test_nonfinite_input_rejected(self):
        for value in (float("nan"), float("inf"), -1):
            self.inputs["source_configurations"][0]["nominal_depth_um"] = value
            with self.assertRaises(ValueError):
                ANALYSIS.gap_budgets(self.inputs)

    def test_all_restoration_domains_remain_unassessed_without_observations(self):
        contract = ANALYSIS.load_json(STUDY / "integration_contract.json")
        parent = ANALYSIS.load_json(STUDY / contract["parent_contract"])
        audit = ANALYSIS.audit_contract(contract, parent)
        self.assertEqual(audit["domains_preserved"], 9)
        self.assertFalse(audit["integrated_success"])
        self.assertEqual(set(audit["domain_results"].values()), {"unassessed"})
        contract["required_domains"].remove("gingiva_and_barrier")
        with self.assertRaises(ValueError):
            ANALYSIS.audit_contract(contract, parent)


if __name__ == "__main__":
    unittest.main()
