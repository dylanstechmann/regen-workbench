"""Boundaries between assay signal, parent exposure and donor-linked function."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("motsc_specificity", HERE / "analyze_motsc.py")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


class MOTScSpecificityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
        cls.results, cls.rows = model.calculate(cls.inputs)

    def test_pg_ng_conversion_and_reported_scale_separation(self):
        self.assertAlmostEqual(model.ng_per_mL(100, "pg/mL"), .1)
        value = self.results["analytical_scale_comparison"]
        self.assertEqual(value["n_reference_subjects"], 20)
        self.assertAlmostEqual(value["reported_ELISA_signal_to_LLOD_scale_ratio_range"][0], 459)
        self.assertAlmostEqual(value["reported_ELISA_signal_to_LLOD_scale_ratio_range"][1], 2185)

    def test_units_invalid_values_and_reversed_ranges_are_rejected(self):
        for value in [None, "100", True, 0, -1, float("nan"), float("inf")]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                model.ng_per_mL(value, "pg/mL")
        with self.assertRaises(ValueError):
            model.ng_per_mL(100, "ng/L")
        changed = copy.deepcopy(self.inputs["knoop_analytical_comparison"])
        changed["elisa_reported_range"] = [200, 10]
        with self.assertRaises(ValueError):
            model.analytical_scale_separation(changed)

    def test_detection_limit_is_not_concentration_or_universal_assay_failure(self):
        value = self.results["analytical_scale_comparison"]
        self.assertIsNone(value["true_intact_parent_concentrations"])
        self.assertIsNone(value["assay_bias_or_cross_reactivity_estimate"])
        self.assertFalse(value["universal_ELISA_failure_inferred"])
        self.assertFalse(value["individual_paired_concentrations_available"])
        self.assertFalse(self.inputs["knoop_analytical_comparison"]["lcms_nondetects_replaced_by_zero"])

    def test_demographic_and_recipient_counts_do_not_create_combined_n(self):
        units = self.results["MSC_units"]
        self.assertEqual(units["human_donors"], 12)
        self.assertEqual(units["recipient_mice"], 36)
        self.assertIsNone(units["combined_independent_sample_size"])
        self.assertFalse(units["histology_field_n_can_replace_mouse_n"])
        self.assertFalse(units["donor_linkage"]["numerical_donor_linked_metabolism_repair_reanalysis_eligible"])
        self.assertIsNone(units["donor_linkage"]["effect_or_correlation_estimate"])

    def test_validated_parent_detection_does_not_make_endogenous_reference_a_pk_series(self):
        source = next(e for e in self.inputs["pk_evidence_cases"] if e["case_id"] == "Knoop_endogenous_reference")
        self.assertTrue(source["source_reports_parent_specific_detection"])
        self.assertTrue(source["source_reports_quantitative_matrix_assay_validation"])
        gate = model.assess_pk(source)
        self.assertFalse(gate["finite_interval_parent_AUC_intake_eligible"])
        self.assertIn("administered_systemic_route_known", gate["missing_for_AUC"])
        self.assertIn("serial_concentration_time_data", gate["missing_for_AUC"])

    def test_variant_specific_calibration_preserved_without_decay_or_clearance_invention(self):
        self.assertTrue(self.inputs["k14q_steady_state"]["calibration_is_corrective_evidence"])
        self.assertEqual(self.inputs["k14q_steady_state"]["reported_relative_apparent_clearance_slowing_factor"], 2.6)
        self.assertFalse(self.inputs["k14q_steady_state"]["serial_postinput_concentrations_available"])
        self.assertIsNone(self.inputs["k14q_steady_state"]["pk_experiment_n_in_retrieved_methods"])
        self.assertIsNone(self.results["steady_state_identity"]["new_native_clearance_or_half_life_estimate"])

    def test_only_explicit_evidence_and_quantified_time_pairs_pass_source_presence_gate(self):
        case = copy.deepcopy(self.inputs["pk_evidence_cases"][0])
        for key in ["source_reports_parent_specific_detection", "source_reports_quantitative_matrix_assay_validation", "baseline_or_endogenous_component_resolved", "administered_systemic_route_known", "serial_concentration_time_data"]:
            case[key] = True
        case["context"] = "systemic_administration"
        case["reported_timepoint_count"] = 2
        gate = model.assess_pk(case)
        self.assertTrue(gate["finite_interval_parent_AUC_intake_eligible"])
        self.assertFalse(gate["terminal_half_life_intake_eligible"])
        self.assertFalse(gate["absolute_parent_clearance_from_AUC_intake_eligible"])
        self.assertFalse(gate["absolute_oral_F_intake_eligible"])
        for bad in [1, True, "2", -1, None]:
            self.assertFalse(model.assess_pk({**case, "reported_timepoint_count": bad})["finite_interval_parent_AUC_intake_eligible"])
        self.assertFalse(model.assess_pk({**case, "source_reports_parent_specific_detection": "true"})["finite_interval_parent_AUC_intake_eligible"])
        self.assertFalse(model.assess_pk({**case, "context": "sample_storage"})["finite_interval_parent_AUC_intake_eligible"])

    def test_actual_sources_never_generate_oral_F_or_functional_rank(self):
        self.assertEqual(self.results["eligible_numerical_parent_pk_datasets"], 0)
        self.assertEqual(len(self.rows), 4)
        self.assertTrue(all(not r["absolute_oral_F_intake_eligible"] for r in self.rows))
        self.assertIsNone(self.results["oral_F_assigned"])
        self.assertIsNone(self.results["delivery_or_analogue_functional_rank"])
        self.assertFalse(self.results["source_observations_digitized_or_synthesized"])

    def test_partial_AUC_and_known_fraction_do_not_qualify_absolute_clearance(self):
        case = copy.deepcopy(self.inputs["pk_evidence_cases"][0])
        case.update(context="systemic_administration", reported_timepoint_count=2)
        for key in ["source_reports_parent_specific_detection", "source_reports_quantitative_matrix_assay_validation", "baseline_or_endogenous_component_resolved", "administered_systemic_route_known", "serial_concentration_time_data", "systemic_input_fraction_known"]:
            case[key] = True
        gate = model.assess_pk(case)
        self.assertTrue(gate["finite_interval_parent_AUC_intake_eligible"])
        self.assertFalse(gate["absolute_parent_clearance_from_AUC_intake_eligible"])
        self.assertIn("administered_parent_amount_known", gate["missing_for_absolute_clearance_from_AUC"])
        self.assertIn("complete_parent_AUC_or_qualified_extrapolation", gate["missing_for_absolute_clearance_from_AUC"])
        case["administered_parent_amount_known"] = True
        self.assertFalse(model.assess_pk(case)["absolute_parent_clearance_from_AUC_intake_eligible"])
        case["complete_parent_AUC_or_qualified_extrapolation"] = True
        gate = model.assess_pk(case)
        self.assertTrue(gate["absolute_parent_clearance_from_AUC_intake_eligible"])
        self.assertIsNone(gate["numerical_AUC_half_life_clearance_or_F"])

    def test_partial_route_AUCs_do_not_qualify_absolute_oral_bioavailability(self):
        case = copy.deepcopy(self.inputs["pk_evidence_cases"][0])
        case.update(context="systemic_administration", reported_timepoint_count=2)
        for key in ["source_reports_parent_specific_detection", "source_reports_quantitative_matrix_assay_validation", "baseline_or_endogenous_component_resolved", "administered_systemic_route_known", "serial_concentration_time_data", "paired_oral_iv_parent_auc_available", "dose_normalization_known", "route_comparison_context_qualified"]:
            case[key] = True
        self.assertTrue(model.assess_pk(case)["finite_interval_parent_AUC_intake_eligible"])
        gate = model.assess_pk(case)
        self.assertFalse(gate["absolute_oral_F_intake_eligible"])
        self.assertIn("both_routes_complete_parent_AUC_or_qualified_extrapolation", gate["missing_for_oral_F"])
        case["complete_parent_AUC_or_qualified_extrapolation"] = True
        self.assertFalse(model.assess_pk(case)["absolute_oral_F_intake_eligible"])
        case["both_routes_complete_parent_AUC_or_qualified_extrapolation"] = True
        gate = model.assess_pk(case)
        self.assertTrue(gate["absolute_oral_F_intake_eligible"])
        self.assertIsNone(gate["numerical_AUC_half_life_clearance_or_F"])


if __name__ == "__main__":
    unittest.main()
