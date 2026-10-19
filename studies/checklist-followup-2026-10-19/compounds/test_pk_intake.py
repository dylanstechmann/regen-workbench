"""Scientific counterexamples and input checks; every numeric curve is synthetic."""
from __future__ import annotations

import copy
import importlib.util
import json
import math
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("followup_compound_pk", HERE / "assess_pk_intake.py")
PK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PK)


def fixture(route="oral_gavage"):
    # Artificial values and fake source hash exercise logic, not compound PK.
    return {
        "id": "synthetic_" + route,
        "fixture_only": True,
        "analyte": "SLU-PP-915",
        "matrix": "plasma",
        "species": "mouse",
        "curve_kind": "concentration_time",
        "route": route,
        "route_or_time_conflict": False,
        "time_unit": "min",
        "concentration_unit": "ng/mL",
        "censoring_policy": "all_points_quantified",
        "numeric_source": {"kind": "measured_table", "metadata_only": False, "sha256": "a" * 64, "location": "synthetic fixture only"},
        "assay_qualification": {k: True for k in ("parent_identity", "calibration", "selectivity", "sample_stability")},
        "sampling": {"design": "terminal_cross_sectional", "curve_unit": "group_mean", "statistical_unit": "mouse", "individual_curves_and_covariance_available": False},
        "points": [{"time": t, "concentration": c, "quantitation": "quantified", "n_subjects": 3} for t, c in [(0, 0), (5, 3), (10, 2)]],
    }


class TestPKIntake(unittest.TestCase):
    def test_actual_source_intake_withholds_every_unavailable_estimate(self):
        actual = json.loads((HERE / "pk_context_intake.json").read_text(encoding="utf-8"))
        report = PK.assess_intake(actual)
        self.assertEqual(sum(p["retrieved_point_count"] for p in report["profiles"]), 0)
        self.assertFalse(any(p["qualified_intact_parent_auc_input_eligible"] for p in report["profiles"]))
        self.assertFalse(report["absolute_oral_F_input_eligible"])
        self.assertIsNone(report["absolute_oral_F_estimate"])
        for p in report["profiles"]:
            self.assertIsNone(p["auc_estimate"])
            self.assertIsNone(p["terminal_half_life_refit"])

    def test_http_success_cannot_turn_metadata_into_numeric_evidence(self):
        p = fixture()
        p["numeric_source"].update(metadata_only=True, http_status=200)
        r = PK.assess_profile(p)
        self.assertFalse(r["observed_signal_integration_input_eligible"])
        self.assertTrue(any("metadata" in s for s in r["signal_integration_reasons"]))

    def test_one_time_and_cross_exposure_comparisons_are_not_time_courses(self):
        for kind in ["cross_exposure_single_time", "repeated_single_time"]:
            p = fixture()
            p["curve_kind"] = kind
            self.assertFalse(PK.assess_profile(p)["observed_signal_integration_input_eligible"])
        p = fixture()
        p["points"] = p["points"][:1]
        self.assertFalse(PK.assess_profile(p)["observed_signal_integration_input_eligible"])

    def test_numeric_signal_and_intact_parent_claims_remain_distinct(self):
        p = fixture()
        p["assay_qualification"]["selectivity"] = None
        r = PK.assess_profile(p)
        self.assertTrue(r["observed_signal_integration_input_eligible"])
        self.assertFalse(r["qualified_intact_parent_auc_input_eligible"])
        p = fixture()
        p["analyte"] = "Ddit4_mRNA"
        self.assertFalse(PK.assess_profile(p)["qualified_intact_parent_auc_input_eligible"])

    def test_group_means_do_not_supply_individual_auc_uncertainty(self):
        r = PK.assess_profile(fixture())
        self.assertTrue(r["qualified_intact_parent_auc_input_eligible"])
        self.assertFalse(r["individual_or_population_auc_uncertainty_input_eligible"])
        self.assertEqual(r["evidence_scope"], "synthetic_test_fixture")
        self.assertIsNone(r["auc_estimate"])

    def test_unknown_sampling_and_false_serial_pairing_cannot_pass(self):
        p = fixture()
        p["sampling"]["design"] = None
        self.assertFalse(PK.assess_profile(p)["qualified_intact_parent_auc_input_eligible"])
        p = fixture()
        p["sampling"].update(design="serial_individual", curve_unit="individual")
        for i, point in enumerate(p["points"]):
            point["subject_id"] = "different_mouse_" + str(i)
        self.assertFalse(PK.assess_profile(p)["qualified_intact_parent_auc_input_eligible"])

    def test_individual_curve_requires_one_subject_and_nonempty_string_identity(self):
        p = fixture()
        p["sampling"].update(design="serial_individual", curve_unit="individual")
        for point in p["points"]:
            point["subject_id"] = "one_mouse"
        self.assertFalse(PK.assess_profile(p)["qualified_intact_parent_auc_input_eligible"])
        for point in p["points"]:
            point["n_subjects"] = 1
        self.assertTrue(PK.assess_profile(p)["qualified_intact_parent_auc_input_eligible"])
        for bad in [None, "", "   ", 1, ["one_mouse"]]:
            invalid = copy.deepcopy(p)
            for point in invalid["points"]:
                point["subject_id"] = bad
            self.assertFalse(PK.assess_profile(invalid)["qualified_intact_parent_auc_input_eligible"])

    def test_digitization_requires_calibration_and_readout_bounds(self):
        p = fixture()
        p["numeric_source"].update(kind="digitized_figure", axis_calibration_verified=True)
        self.assertFalse(PK.assess_profile(p)["observed_signal_integration_input_eligible"])
        for point in p["points"]:
            point["time_bounds"] = [max(0, point["time"] - 0.1), point["time"] + 0.1]
            point["concentration_bounds"] = [max(0, point["concentration"] - 0.1), point["concentration"] + 0.1]
        self.assertTrue(PK.assess_profile(p)["observed_signal_integration_input_eligible"])
        p["points"][1]["concentration_bounds"] = [4, 5]
        self.assertFalse(PK.assess_profile(p)["observed_signal_integration_input_eligible"])

    def test_missing_censoring_or_nondetect_as_zero_is_not_silently_accepted(self):
        p = fixture()
        p["points"][0]["quantitation"] = "below_quantification_limit"
        self.assertFalse(PK.assess_profile(p)["observed_signal_integration_input_eligible"])
        p = fixture()
        p["censoring_policy"] = None
        self.assertFalse(PK.assess_profile(p)["observed_signal_integration_input_eligible"])

    def test_duplicates_nonfinite_values_and_boolean_counts_are_rejected(self):
        p = fixture()
        p["points"][1]["time"] = p["points"][0]["time"]
        self.assertFalse(PK.assess_profile(p)["observed_signal_integration_input_eligible"])
        for bad in [math.nan, math.inf, -1, True]:
            p = fixture()
            p["points"][1]["concentration"] = bad
            self.assertFalse(PK.assess_profile(p)["observed_signal_integration_input_eligible"])
        p = fixture()
        p["points"][1]["n_subjects"] = True
        self.assertFalse(PK.assess_profile(p)["qualified_intact_parent_auc_input_eligible"])

    def test_intraperitoneal_reference_cannot_supply_absolute_oral_f(self):
        reference = {k: True for k in ["exposure_normalization_qualified", "matched_population_and_clearance_qualified", "route_matched_auc_window_or_terminal_coverage_qualified"]}
        reference.update(oral_profile_id="synthetic_oral_gavage", intravenous_profile_id="synthetic_intraperitoneal")
        data = {"schema_version": 1, "profiles": [fixture(), fixture("intraperitoneal")], "absolute_F_reference": reference}
        self.assertFalse(PK.assess_intake(data)["absolute_oral_F_input_eligible"])
        data["profiles"][1] = fixture("intravenous")
        data["absolute_F_reference"]["intravenous_profile_id"] = "synthetic_intravenous"
        result = PK.assess_intake(data)
        self.assertTrue(result["absolute_oral_F_input_eligible"])
        self.assertIsNone(result["absolute_oral_F_estimate"])
        data["absolute_F_reference"]["exposure_normalization_qualified"] = False
        self.assertFalse(PK.assess_intake(data)["absolute_oral_F_input_eligible"])

    def test_schema_and_duplicate_profiles_fail_explicitly(self):
        p = fixture()
        for data in [{"schema_version": 2, "profiles": [p]}, {"schema_version": 1, "profiles": [p, copy.deepcopy(p)]}, {"schema_version": 1, "profiles": [None]}]:
            with self.assertRaises(ValueError):
                PK.assess_intake(data)


if __name__ == "__main__":
    unittest.main()
