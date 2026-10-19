"""Real pilot records keep visit, patient, censoring and surrogate boundaries."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/"studies/checklist-integration-2026-10-19/pulp"
SPEC=importlib.util.spec_from_file_location("nakashima_pulp_endpoint_audit",HERE/"analyze_patient_endpoints.py")
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

class PulpEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=M.load_json(HERE/"patient_records.json")
        cls.result=M.analyze(cls.data)
        cls.by_id={r["patient_id"]:r for r in cls.data["patient_records"]}

    def test_all_patients_and_teeth_kept(self):
        self.assertEqual(set(self.by_id),set("12345"))
        self.assertEqual(len({r["affected_tooth"] for r in self.by_id.values()}),5)
        self.assertEqual(self.result["patient_registry"]["enrolled"],5)
        self.assertIsNone(self.result["patient_registry"]["screened_or_approached"])
        self.assertIsNone(self.result["patient_registry"]["reported_formal_dropout_flow"])

    def test_enrollment_and_pretransplant_baselines_are_distinct(self):
        for r in self.by_id.values():
            self.assertTrue(r["enrollment_EPT_table1"]["core_text"].startswith("+"))
            self.assertTrue(r["pre_transplant_EPT_negative_narrative"])
        self.assertFalse(self.by_id["2"]["EPT_24wk_table4"]["source_positive"])

    def test_positive_onset_days_and_late_note_do_not_merge(self):
        self.assertEqual({p:self.by_id[p]["onset_EPT_table4"]["first_positive_day_if_reported"] for p in "1345"},{"1":6,"3":6,"4":28,"5":14})
        self.assertIsNone(self.by_id["2"]["onset_EPT_table4"]["first_positive_day_if_reported"])
        self.assertIn("after36weeks",self.by_id["2"]["EPT_24wk_table4"]["late_positive_note"])
        self.assertFalse(self.result["patient_registry"]["complete36wk_cohort_inferred"])

    def test_device_readings_are_nested_and_censored(self):
        audit=self.result["EPT_reading_audit"]
        self.assertEqual(audit["nested_device_readings"],36)
        self.assertEqual(audit["independent_patients"],5)
        self.assertEqual([r["patient_id"] for r in audit["right_censored_readings"]],["4","5"])
        self.assertTrue(all(r["source_token"]=="80+" for r in audit["right_censored_readings"]))
        self.assertIsNone(audit["normalized_longitudinal_sensory_recovery_percent"])

    def test_changing_control_teeth_retained(self):
        self.assertEqual(self.result["EPT_reading_audit"]["changed_control_tooth_patient_ids"],["1","3","4"])
        self.assertEqual(self.by_id["3"]["EPT_12wk_table4"]["control_tooth_literal"],"left upper incisor")
        self.assertEqual(self.by_id["3"]["EPT_24wk_table4"]["control_tooth_literal"],"left upper canine")
        self.assertEqual(self.by_id["4"]["EPT_24wk_table4"]["control_tooth_literal"],"right lower 1st premolar")

    def test_exact_24week_observed_pattern_retains_discordance(self):
        pattern=self.result["linked_measured_patterns"]["24wk_EPT_positive_MRI_value_available_and_unambiguous_XR_radiolucency_absence"]
        self.assertEqual(pattern["observed_pattern_patient_ids"],["1","3","5"])
        self.assertEqual(pattern["observed_not_pattern_patient_ids"],["2","4"])
        self.assertEqual(pattern["count_bounds"],[3,3])
        self.assertEqual(pattern["proportion_bounds"],[.6,.6])

    def test_ambiguous_radiolucency_not_zero_imputed(self):
        self.assertEqual(self.by_id["2"]["XR_24wk_source"]["core_text"],"–/+")
        self.assertIsNone(self.by_id["2"]["XR_24wk_radiolucency_absent"])
        pattern=self.result["linked_measured_patterns"]["24wk_MRI_value_available_and_unambiguous_XR_radiolucency_absence"]
        self.assertEqual(pattern["unknown_patient_ids"],["2"])
        self.assertEqual(pattern["count_bounds"],[3,4])
        self.assertEqual(pattern["proportion_bounds"],[.6,.8])

    def test_ept_positive_can_coexist_with_radiographic_finding(self):
        pattern=self.result["linked_measured_patterns"]["24wk_EPT_positive_with_XR_radiolucency_present"]
        self.assertEqual(pattern["observed_pattern_patient_ids"],["4"])
        self.assertEqual(pattern["count_bounds"],[1,1])
        self.assertTrue(self.result["safety_and_limits"]["new_patient4_radiographic_abnormality_preserved"])

    def test_mri_is_continuous_and_not_perfusion_fraction(self):
        mri=self.result["MRI_24wk_apical_signal"]
        self.assertEqual([r["relative_signal"] for r in mri["patient_values"]],[.8,.9,.9,.7,.9])
        self.assertAlmostEqual(mri["mean"],.84)
        self.assertEqual(mri["median"],.9)
        self.assertIsNone(mri["source_defined_healthy_threshold"])
        self.assertIsNone(mri["direct_blood_flow"])
        self.assertIn("dentin",mri["source_ratio_definition"])
        self.assertTrue(all(r["blood_flow_direct_measurement"] is None for r in self.by_id.values()))

    def test_cbct_visit_not_assigned_from_neighboring_table_row(self):
        self.assertTrue(all(r["CBCT_table4_time_weeks"] is None for r in self.by_id.values()))
        self.assertEqual(self.result["CBCT_separate_source_flags"]["reported_lateral_mineralization_patient_ids"],["1","4","5"])
        changed=copy.deepcopy(self.data)
        changed["patient_records"][0]["CBCT_table4_time_weeks"]=24
        with self.assertRaises(ValueError):M.analyze(changed)

    def test_same_unit_volume_is_low_density_space_change_only(self):
        volume=self.result["CBCT_separate_source_flags"]["volume_audits"][0]
        self.assertEqual(volume["patient_id"],"1")
        self.assertEqual(volume["status"],"same_unit_printed_pair")
        self.assertAlmostEqual(volume["decrease_value"],.0018)
        self.assertAlmostEqual(volume["decrease_fraction"],.0018/.0143)
        self.assertEqual(volume["results_narrative_times_weeks"],[16,28])
        self.assertFalse(volume["eligible_for_24wk_joint_pattern"])

    def test_source_unit_time_conflict_and_missing_initial_scan_stay_uncomputed(self):
        cbct=self.result["CBCT_separate_source_flags"]
        volume=cbct["volume_audits"][1]
        self.assertEqual(volume["patient_id"],"4")
        self.assertEqual([volume["before_unit_literal"],volume["after_unit_literal"]],["cm3","m3"])
        self.assertIsNone(volume["decrease_fraction"])
        self.assertIn("12/24weeks",volume["timing_qualification"])
        self.assertTrue(cbct["missing_initial_CBCT_patient5"])
        self.assertIsNone(cbct["cohort_mean_volume_change"])

    def test_three_state_logic_and_all_assigned_denominator(self):
        self.assertFalse(M.tri_and([False,None]))
        self.assertIsNone(M.tri_and([True,None]))
        self.assertTrue(M.tri_and([True,True]))
        self.assertEqual(M.bounds([("1",True),("2",None),("3",False)])["proportion_bounds"],[1/3,2/3])
        for values in ([],[1],["true"]):
            with self.assertRaises(ValueError):M.tri_and(values)
        with self.assertRaises(ValueError):M.bounds([("1",True),("1",None)])

    def test_duplicate_or_missing_patient_and_invalid_mri_fail(self):
        for records in (self.data["patient_records"][:-1],self.data["patient_records"][:-1]+[self.data["patient_records"][0]]):
            changed=copy.deepcopy(self.data);changed["patient_records"]=records
            with self.assertRaises(ValueError):M.analyze(changed)
        for invalid in (None,True,float("nan"),0):
            changed=copy.deepcopy(self.data);changed["patient_records"][0]["MRI_24wk_apical_relative_signal"]=invalid
            with self.assertRaises(ValueError):M.analyze(changed)

    def test_safety_and_regeneration_are_not_inferred(self):
        safety=self.result["safety_and_limits"]
        self.assertTrue(safety["source_reports_no_attributed_systemic_or_clinical_events_through24wk"])
        self.assertFalse(safety["long_term_safety_proven"])
        self.assertIsNone(safety["controlled_treatment_effect"])
        self.assertIsNone(safety["full_regeneration_success_count"])
        self.assertEqual(safety["directly_measured_perfusion_or_human_pulp_histology_n"],0)
        self.assertEqual(len(self.data["source_cell_karyotype_literals_not_clinical_adverse_adjudication"]),5)

    def test_pinned_offline_reproduction(self):
        receipt=M.load_json(HERE/"derived/analysis_receipt.json")
        mapping={"source_receipts_text_sha256":"source_receipts.json","patient_records_text_sha256":"patient_records.json",
            "analysis_plan_text_sha256":"analysis_plan.json","analysis_script_text_sha256":"analyze_patient_endpoints.py",
            "results_text_sha256":"derived/patient_endpoint_summary.json"}
        for key,path in mapping.items():self.assertEqual(receipt[key],M.text_sha(HERE/path))
        self.assertEqual(self.data["extractor_text_sha256"],M.text_sha(HERE/"extract_nakashima.py"))
        self.assertEqual(self.result,M.load_json(HERE/"derived/patient_endpoint_summary.json"))

if __name__=="__main__":unittest.main()
