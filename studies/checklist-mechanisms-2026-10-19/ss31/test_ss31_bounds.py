"""Study-specific rejection checks and independent source-summary expectations."""

import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ss31_bounded_accounting", HERE / "analyze_ss31.py")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


class SS31EvidenceBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
        cls.result, cls.rows = model.calculate(cls.inputs)

    def test_other_disappearance_removal_is_only_a_conditional_counterfactual(self):
        self.assertAlmostEqual(model.conditional_clearance(.10, 1), 1)
        self.assertAlmostEqual(model.conditional_clearance(.10, .5), .55)
        self.assertAlmostEqual(model.conditional_clearance(.10, 0), .10)
        self.assertIsNone(self.result["conditional_clearance_partition"]["universal_analogue_ceiling"])
        self.assertFalse(self.result["functional_analogue_equivalence_established"])

    def test_invalid_or_unknown_fraction_cannot_create_a_gain(self):
        for value in [None, True, float("nan"), float("inf"), -0.1, 1.1, "0.1"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                model.conditional_clearance(value, 0)
        with self.assertRaises(ValueError):
            model.conditional_clearance(.1, -0.1)
        with self.assertRaises(ValueError):
            model.unchanged_parent_material_ratio(.92, None)
        with self.assertRaises(ValueError):
            model.unchanged_parent_material_ratio(.92, 0)

    def test_no_oral_F_or_finite_upper_bound_is_invented(self):
        bounds = self.result["unchanged_parent_oral_material_bound"]
        self.assertIsNone(bounds["oral_F_assigned"])
        self.assertIsNone(bounds["uniform_finite_upper_bound"])
        self.assertAlmostEqual(bounds["mathematical_lower_bound_at_oral_F_equal_one"], .92)
        self.assertAlmostEqual(bounds["maximum_possible_parent_material_reduction_fraction_under_these_assumptions"], .08)
        self.assertGreater(model.unchanged_parent_material_ratio(.92, 1e-6), 900000)

    def test_missing_access_activity_and_cost_blocks_useful_rank(self):
        gate = self.result["unchanged_parent_oral_material_bound"]["useful_exposure_cost_rank"]
        self.assertFalse(gate["eligible"])
        self.assertIn("oral_F", gate["missing"])
        self.assertIn("native_intracellular_access", gate["missing"])
        self.assertIn("relative_function_at_matched_intracellular_parent_exposure", gate["missing"])
        self.assertIn("final_released_material_cost", gate["missing"])
        self.assertIsNone(gate["numerical_rank"])

    def test_invalid_measurements_cannot_pass_useful_cost_gate(self):
        valid = {"oral_F": .5, "native_intracellular_access": .5, "relative_function_at_matched_intracellular_parent_exposure": 1.0, "final_released_material_cost": 1.0}
        self.assertTrue(model.numerical_useful_cost_eligibility(valid)["eligible"])
        for field in valid:
            for value in ["1", True, float("nan"), float("inf"), 0, -1]:
                with self.subTest(field=field, value=value):
                    outcome = model.numerical_useful_cost_eligibility({**valid, field: value})
                    self.assertFalse(outcome["eligible"])
                    self.assertIn(field, outcome["invalid"])
        for field in ["oral_F", "native_intracellular_access"]:
            self.assertFalse(model.numerical_useful_cost_eligibility({**valid, field: 1.1})["eligible"])

    def test_parent_recovery_not_replaced_by_all_urine_recovery(self):
        recovery = self.inputs["urinary_recovery"]
        self.assertEqual(recovery["n_subjects"], 6)
        self.assertEqual(recovery["collection_h"], 48)
        self.assertEqual(recovery["reported_fraction_parent_approx"], .10)
        self.assertAlmostEqual(self.result["human_context"]["rounded_parent_plus_metabolite_urine_fraction_sum"], 1.01)
        self.assertEqual(self.result["conditional_clearance_partition"]["parent_urine_fraction_anchor_approx"], .10)

    def test_source_means_reproduce_correct_experimental_units(self):
        tmrm = next(r for r in self.rows if r["endpoint_id"] == "tmrm_serum_withdrawal" and r["compound"] == "SS-31")
        stressed = next(r for r in self.rows if r["endpoint_id"] == "viability_stressed" and r["compound"] == "SS-31")
        unstressed = next(r for r in self.rows if r["endpoint_id"] == "viability_unstressed" and r["compound"] == "SS-31")
        self.assertEqual(len(self.rows), 21)
        self.assertEqual(tmrm["n_source_units"], 3)
        self.assertAlmostEqual(tmrm["mean"], 68.69607035712342)
        self.assertAlmostEqual(tmrm["sample_sd"], 4.756940356037588)
        self.assertEqual(stressed["n_source_units"], 5)
        self.assertAlmostEqual(stressed["mean"], 1.344151594)
        self.assertEqual(unstressed["n_source_units"], 6)

    def test_endpoint_directions_are_not_a_single_activity_rank(self):
        spn4 = {r["endpoint_id"]: r for r in self.rows if r["compound"] == "SPN4"}
        self.assertLess(spn4["tmrm_serum_withdrawal"]["difference_from_ss31_in_source_units"], 0)
        self.assertGreater(spn4["viability_stressed"]["difference_from_ss31_in_source_units"], 0)
        repeated = next(r for r in self.result["cross_endpoint_exact_value_audit"] if r["compound"] == "SPN10")
        self.assertEqual(repeated["same_position_exact_matches"], 5)
        self.assertTrue(repeated["entire_vectors_exactly_equal"])
        self.assertFalse(self.result["native_target_access_calibrated"])

    def test_process_area_purity_and_mass_ratio_do_not_become_parent_yield(self):
        process = self.result["process_accounting"]
        self.assertAlmostEqual(process["source_example_final_salt_to_protected_precursor_mass_ratio"], .35)
        self.assertFalse(process["mass_ratio_is_molar_yield"])
        self.assertIsNone(process["overall_released_parent_yield"])
        self.assertIsNone(process["actual_final_parent_cost"])
        self.assertAlmostEqual(process["actual_to_area_assumed_bulk_for_equal_assayed_intermediate_content_ratio"], 1.0070921985815604)
        self.assertFalse(process["area_assay_example_is_final_parent_cost_estimate"])


if __name__ == "__main__":
    unittest.main()
