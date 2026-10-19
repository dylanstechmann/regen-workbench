"""Source linkage, nested units and missing/censored material outcomes."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "studies/checklist-mechanisms-2026-10-19/dental"
SPEC = importlib.util.spec_from_file_location("linked_material_outcomes", STUDY / "analyze_linked_material_outcomes.py")
MODEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODEL)


class LinkedMaterialOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = MODEL.load_json(STUDY / "synthetic_linked_fixture.json")

    def group(self, result, condition):
        return next(g for g in result["groups"] if g["condition"] == condition)

    def test_repeated_indents_do_not_become_independent_teeth_or_donors(self):
        group = self.group(MODEL.analyze_linked(self.fixture), "thin_fixture")
        self.assertEqual(group["apparent_toughness"]["n_observed_specimens"], 3)
        self.assertEqual(group["apparent_toughness"]["n_observed_donors"], 2)
        self.assertAlmostEqual(group["apparent_toughness"]["observed_specimen_weighted_mean"], 1.0666666666666667)
        self.assertAlmostEqual(group["apparent_toughness"]["tooth_then_donor_balanced_mean"], 1.125)
        self.assertAlmostEqual(group["naive_indent_weighted_mean_diagnostic_only"], 1.1714285714285715)

    def test_coupon_then_tooth_then_donor_weighting(self):
        rows = [{"specimen_id": "a", "donor_id": "d1", "tooth_id": "t1"},
                {"specimen_id": "b", "donor_id": "d1", "tooth_id": "t1"},
                {"specimen_id": "c", "donor_id": "d1", "tooth_id": "t2"},
                {"specimen_id": "d", "donor_id": "d2", "tooth_id": "t3"}]
        result = MODEL.hierarchical_mean(rows, {"a": 1, "b": 3, "c": 8, "d": 10})
        self.assertEqual(result["observed_specimen_weighted_mean"], 5.5)
        self.assertEqual(result["tooth_then_donor_balanced_mean"], 7.5)

    def test_missing_depth_is_not_zero_and_missing_target_does_not_erase_measurement(self):
        missing = MODEL.depth_result(None, 50)
        self.assertIsNone(missing["depth_um"])
        observed = MODEL.depth_result({"value_um": 12, "bounds_um": [10, 14], "bounds_kind": "fixture"}, None)
        self.assertEqual(observed["depth_um"], 12)
        self.assertEqual(observed["depth_measurement_bounds_um"], [10, 14])
        self.assertIsNone(observed["target_difference_um"])

    def test_depth_bounds_show_shortfall_without_declaring_material_acceptance(self):
        result = MODEL.analyze_linked(self.fixture)
        point = next(p for p in result["specimen_outcomes"] if p["specimen_id"] == "SYN_B1")
        self.assertEqual(point["target_difference_bounds_um"], [-10, -6])
        self.assertEqual(point["depth_state"], "below_target_with_given_bounds")
        self.assertEqual(set(result["full_restoration_domains"].values()), {"unassessed"})

    def test_fatigue_exact_horizon_and_interval_censoring(self):
        self.assertEqual(MODEL.fatigue_state({"kind": "event", "cycle_bounds": [100, 100], "failure_mode": "interfacial"}, 100)[0], "known_failure_by_horizon")
        self.assertEqual(MODEL.fatigue_state({"kind": "event", "cycle_bounds": [90, 110], "failure_mode": "mixed"}, 100)[0], "unknown")
        self.assertEqual(MODEL.fatigue_state({"kind": "event", "cycle_bounds": [101, 120], "failure_mode": "mixed"}, 100)[0], "known_no_failure_by_horizon")
        for time, expected in [(99, "unknown"), (100, "known_no_failure_by_horizon")]:
            self.assertEqual(MODEL.fatigue_state({"kind": "right_censored", "cycles": time, "reason": "technical_loss"}, 100)[0], expected)

    def test_all_assigned_fatigue_denominator_retains_censoring_and_missingness(self):
        result = MODEL.analyze_linked(self.fixture)
        thin = self.group(result, "thin_fixture")
        thick = self.group(result, "greater_depth_fixture")
        self.assertEqual(thin["fatigue_failure_fraction_bounds"], [1 / 3, 2 / 3])
        self.assertEqual(thick["fatigue_failure_fraction_bounds"], [0, 2 / 3])
        self.assertEqual(thick["assigned_specimens"], 3)
        self.assertEqual(thick["fatigue_state_counts"]["unknown"], 2)

    def test_technical_fixture_failure_cannot_be_a_material_event(self):
        with self.assertRaises(ValueError):
            MODEL.fatigue_state({"kind": "event", "cycle_bounds": [10, 10], "failure_mode": "fixture_failure"}, 100)

    def test_leakage_limits_are_bounds_not_imputed_measurements(self):
        self.assertEqual(MODEL.leakage_bounds({"kind": "left_censored", "value": 0.2}), (0, 0.2, "left_censored"))
        self.assertEqual(MODEL.leakage_bounds({"kind": "right_censored", "value": 0.5}), (0.5, None, "right_censored"))
        thick = self.group(MODEL.analyze_linked(self.fixture), "greater_depth_fixture")
        self.assertAlmostEqual(thick["leakage_all_assigned_mean_bounds"][0], 1.1 / 3)
        self.assertIsNone(thick["leakage_all_assigned_mean_bounds"][1])
        self.assertEqual(thick["leakage_observation_kinds"]["unmeasured"], 1)

    def test_missing_whole_packet_remains_in_registry_denominator(self):
        self.fixture["measurements"].pop()
        result = MODEL.analyze_linked(self.fixture)
        self.assertEqual(len(result["specimen_outcomes"]), 6)
        point = result["specimen_outcomes"][-1]
        self.assertTrue(point["measurement_packet_missing"])
        self.assertEqual(point["missing_outcome_reasons"], {"all": "no_measurement_packet"})
        self.assertEqual(self.group(result, "greater_depth_fixture")["assigned_specimens"], 3)

    def test_wrong_region_state_time_or_duplicate_measurement_rejected(self):
        for field, wrong in [("region_id", "different"), ("state_id", "later"), ("assessment_cycles", 10)]:
            payload = copy.deepcopy(self.fixture)
            payload["measurements"][0][field] = wrong
            with self.assertRaises(ValueError):
                MODEL.analyze_linked(payload)
        self.fixture["measurements"].append(copy.deepcopy(self.fixture["measurements"][0]))
        with self.assertRaises(ValueError):
            MODEL.analyze_linked(self.fixture)

    def test_tooth_donor_identity_cannot_change(self):
        self.fixture["specimens"][1]["donor_id"] = "different_donor"
        with self.assertRaises(ValueError):
            MODEL.analyze_linked(self.fixture)

    def test_followup_and_terminal_assessment_cannot_precede_baseline_or_endpoint(self):
        self.fixture["measurements"][0]["terminal_crack_path"]["assessment_cycles"] = 119
        with self.assertRaises(ValueError):
            MODEL.analyze_linked(self.fixture)
        self.fixture["measurements"][0]["terminal_crack_path"]["assessment_cycles"] = 120
        self.fixture["fatigue_horizon_cycles"] = 0
        with self.assertRaises(ValueError):
            MODEL.analyze_linked(self.fixture)

    def test_unknown_identity_prevents_balanced_donor_estimand(self):
        self.fixture["specimens"][0]["donor_id"] = None
        group = self.group(MODEL.analyze_linked(self.fixture), "thin_fixture")
        self.assertIsNone(group["depth"]["tooth_then_donor_balanced_mean"])
        self.assertEqual(group["depth"]["hierarchy_status"], "unavailable_missing_donor_or_tooth_identity")

    def test_actual_source_positions_cannot_become_linked_specimens(self):
        result = MODEL.audit_unlinked_source(STUDY / "hasan_unlinked_source.json")
        self.assertEqual(result["stored_numeric_positions"], 75)
        self.assertEqual(result["linked_specimens_available"], 0)
        self.assertFalse(result["invented_specimen_ids"])
        self.assertEqual(set(result["ambiguous_cells_retained"]), {"Fig. 6!AC13", "Fig. 6!AD13"})
        self.assertTrue(result["estimand_availability"]["fatigue_failure_bounds_by_depth"].startswith("unavailable"))

    def test_empty_template_does_not_emit_zero_outcomes_or_a_pass(self):
        result = MODEL.analyze_linked(MODEL.load_json(STUDY / "measurement_template.json"))
        self.assertEqual(result["status"], "empty_template_no_data")
        self.assertEqual(result["specimen_outcomes"], [])

    def test_adverse_terminal_paths_and_missing_reasons_remain_visible(self):
        result = MODEL.analyze_linked(self.fixture)
        paths = self.group(result, "greater_depth_fixture")["terminal_crack_paths_at_recorded_times"]
        self.assertEqual(paths, {"interfacial": 1, "unmeasured": 1, "mixed": 1})
        del self.fixture["measurements"][-1]["missing_reasons"]
        with self.assertRaises(ValueError):
            MODEL.analyze_linked(self.fixture)

    def test_persisted_input_and_script_receipts_match(self):
        result = MODEL.load_json(STUDY / "derived/linked_specimen_analysis.json")
        self.assertEqual(result["receipts"]["input_sha256_lf_text"], MODEL.text_sha(STUDY / "synthetic_linked_fixture.json"))
        self.assertEqual(result["receipts"]["script_sha256_lf_text"], MODEL.text_sha(STUDY / "analyze_linked_material_outcomes.py"))


if __name__ == "__main__":
    unittest.main()
