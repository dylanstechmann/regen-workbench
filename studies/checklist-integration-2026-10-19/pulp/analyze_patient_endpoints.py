"""Linked observed patient patterns; no regenerated-pulp success classifier."""
from __future__ import annotations
import argparse
import math
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from extract_nakashima import load_json, save_json, source_root, text_sha

def tri_and(values):
    if not values: raise ValueError("A named observed pattern is required")
    if any(v is not None and type(v) is not bool for v in values):
        raise ValueError("Observed pattern states must be true, false or unknown")
    if False in values: return False
    return True if all(v is True for v in values) else None

def bounds(states):
    if not states: raise ValueError("An assigned patient registry is required")
    if len({ident for ident, _ in states}) != len(states): raise ValueError("Duplicate patient in joint pattern")
    for _, value in states:
        if value is not None and type(value) is not bool: raise ValueError("Invalid patient state")
    yes = [ident for ident, value in states if value is True]
    no = [ident for ident, value in states if value is False]
    unknown = [ident for ident, value in states if value is None]
    return {"denominator_enrolled_patients": len(states), "observed_pattern_patient_ids": yes,
        "observed_not_pattern_patient_ids": no, "unknown_patient_ids": unknown,
        "count_bounds": [len(yes), len(yes) + len(unknown)],
        "proportion_bounds": [len(yes)/len(states), (len(yes)+len(unknown))/len(states)],
        "meaning": "Exact finite-cohort identification bounds from reported categorical observations; no confidence interval, causal benefit or biological regeneration criterion"}

def volume_audit(row):
    for key in ("before_value", "after_value"):
        v = row[key]
        if isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or v <= 0:
            raise ValueError("Invalid printed volume quantity")
    if row["before_unit_literal"] not in ("cm3","m3") or row["after_unit_literal"] not in ("cm3","m3"):
        raise ValueError("Unexpected source volume unit")
    result = {**row, "eligible_for_24wk_joint_pattern": False}
    if row["before_unit_literal"] == row["after_unit_literal"]:
        result.update(status="same_unit_printed_pair", decrease_value=row["before_value"]-row["after_value"],
            decrease_fraction=(row["before_value"]-row["after_value"])/row["before_value"])
    else:
        result.update(status="source_unit_conflict", decrease_value=None, decrease_fraction=None,
            interpretation="No unit repair or conditional change computed; source unit/time conflicts remain unresolved")
    return result

def analyze(data):
    if data["data_kind"] != "observed_public_patient_table_transcription_with_explicit_narrative_annotations":
        raise ValueError("Unexpected source evidence kind")
    rows = data["patient_records"]
    if len(rows) != 5 or {r["patient_id"] for r in rows} != {str(i) for i in range(1,6)}:
        raise ValueError("Expected every unique source patient ID1-5")
    ept_counts, n_readings, censored = {}, 0, []
    changed_controls = []
    for name in ("onset_EPT_table4", "EPT_12wk_table4", "EPT_24wk_table4"):
        ept_counts[name] = bounds([(r["patient_id"], r[name]["source_positive"]) for r in rows])
        for r in rows:
            readings = r[name]["readings_nested_in_patient_visit"]
            if r[name]["source_positive"] and len(readings) != 3: raise ValueError("Source three-dentist readings missing")
            n_readings += len(readings)
            for reading in readings:
                if reading["censoring"] == "right_censored": censored.append({"patient_id":r["patient_id"], "source_endpoint":name, "source_token":reading["source_token"]})
    for r in rows:
        controls = {r[k]["control_tooth_literal"] for k in ("onset_EPT_table4", "EPT_12wk_table4", "EPT_24wk_table4") if r[k]["control_tooth_literal"] is not None}
        if len(controls)>1: changed_controls.append(r["patient_id"])
    mri = [r["MRI_24wk_apical_relative_signal"] for r in rows]
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in mri):
        raise ValueError("Missing or invalid printed24-week MRI value")
    for r in rows:
        if r["CBCT_table4_time_weeks"] is not None:
            raise ValueError("Source Table4 CBCT row has no explicit visit; do not assign one")
    patterns = {
        "EPT_positive_at_both12_and24_weeks": [(r["patient_id"],tri_and([r["EPT_12wk_table4"]["source_positive"],r["EPT_24wk_table4"]["source_positive"]])) for r in rows],
        "24wk_EPT_positive_and_MRI_value_available": [(r["patient_id"],r["EPT_24wk_table4"]["source_positive"]) for r in rows],
        "24wk_MRI_value_available_and_unambiguous_XR_radiolucency_absence": [(r["patient_id"],r["XR_24wk_radiolucency_absent"]) for r in rows],
        "24wk_EPT_positive_MRI_value_available_and_unambiguous_XR_radiolucency_absence": [(r["patient_id"],tri_and([r["EPT_24wk_table4"]["source_positive"],r["XR_24wk_radiolucency_absent"]])) for r in rows],
        "24wk_EPT_positive_with_XR_radiolucency_present": [(r["patient_id"],tri_and([r["EPT_24wk_table4"]["source_positive"],None if r["XR_24wk_radiolucency_absent"] is None else not r["XR_24wk_radiolucency_absent"]])) for r in rows]
    }
    pairs = [volume_audit(r) for r in data["source_volume_pairs"]]
    return {"evidence_kind": "Observed patient-linked pilot-study endpoint patterns, not complete pulp regeneration",
        "patient_registry": {"enrolled":5,"one_affected_tooth_per_patient":True,"screened_or_approached":None,
            "Table4_24wk_EPT_status_records":5,"Table4_24wk_apical_MRI_values":5,"Table4_24wk_XR_symbols":5,
            "unambiguous_binary_XR_radiolucency_states":4,"Table4_CBCT_flags_with_unspecified_visit":5,
            "same_unit_numeric_CBCT_volume_pairs":sum(r["status"]=="same_unit_printed_pair" for r in pairs),
            "reported_formal_dropout_flow":None,"complete36wk_cohort_inferred":False},
        "EPT_source_status_counts":ept_counts,
        "EPT_reading_audit":{"nested_device_readings":n_readings,"independent_patients":5,
            "right_censored_readings":censored,"changed_control_tooth_patient_ids":changed_controls,
            "normalized_longitudinal_sensory_recovery_percent":None,
            "interpretation":"Source categorical positivity only; device units are not linear nerve function. No averaging80+ as80 or averaging across changing control teeth."},
        "MRI_24wk_apical_signal":{"patient_values":[{"patient_id":r["patient_id"],"relative_signal":r["MRI_24wk_apical_relative_signal"]} for r in rows],
            "source_ratio_definition":data["MRI_ratio_definition"],
            "mean":statistics.mean(mri),"median":statistics.median(mri),"minimum":min(mri),"maximum":max(mri),
            "source_defined_healthy_threshold":None,"direct_blood_flow":None,"native_pulp_identity_confirmed":None,
            "interpretation":"Continuous relative image signal, not perfusion, normal-tissue equivalence or a histological identity test"},
        "linked_measured_patterns":{name:bounds(values) for name,values in patterns.items()},
        "MRI_availability_in_patterns":"All5 have a numeric Table4 ratio. Availability is not an MRI-positive or physiological-success classification.",
        "discordant_patient_records":[
            {"patient_id":"2","EPT_24wk_positive":False,"apical_MRI_ratio":next(r["MRI_24wk_apical_relative_signal"] for r in rows if r["patient_id"]=="2"),
             "XR_radiolucency":"Unresolved minus/plus, shrinking prior lesion and widened PDL; not coded absent",
             "late_EPT":"After36weeks footnote only; exact time and complete later cohort unavailable"},
            {"patient_id":"4","EPT_24wk_positive":True,"apical_MRI_ratio":next(r["MRI_24wk_apical_relative_signal"] for r in rows if r["patient_id"]=="4"),
             "XR_radiolucency":"Present at24weeks following PDL widening at12weeks; no causal attribution computed",
             "CBCT":"Positive lateral-mineralization flag at an unassigned Table4 visit; not a24-week joint criterion"}],
        "CBCT_separate_source_flags":{"reported_lateral_mineralization_patient_ids":[r["patient_id"] for r in rows if r["CBCT_lateral_mineralization_reported"]],
            "denominator_enrolled_patients":5,"exact_visit_in_Table4":None,"native_dentin_or_mechanical_strength_confirmed":None,
            "volume_audits":pairs,"missing_initial_CBCT_patient5":True,"cohort_mean_volume_change":None},
        "safety_and_limits":{"source_reports_no_attributed_systemic_or_clinical_events_through24wk":True,
            "source_lab_clinical_abnormality_symbols":{r["patient_id"]:r["blood_urine_ECG_local_examination_abnormality_source"] for r in rows},
            "new_patient4_radiographic_abnormality_preserved":True,
            "cell_karyotype_patterns_not_all_declared_normal":True,"long_term_safety_proven":False,
            "controlled_treatment_effect":None,"full_regeneration_success_count":None,
            "directly_measured_perfusion_or_human_pulp_histology_n":0}}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-cache",action="store_true")
    args=parser.parse_args()
    if args.verify_cache: source_root()
    data=load_json(HERE/"patient_records.json")
    if data["source_receipts_text_sha256"]!=text_sha(HERE/"source_receipts.json") or data["extractor_text_sha256"]!=text_sha(HERE/"extract_nakashima.py"):
        raise ValueError("Source receipt or extractor changed after extraction")
    result=analyze(data)
    out=HERE/"derived"
    save_json(out/"patient_endpoint_summary.json",result)
    save_json(out/"analysis_receipt.json",{"source_receipts_text_sha256":text_sha(HERE/"source_receipts.json"),
        "patient_records_text_sha256":text_sha(HERE/"patient_records.json"),"analysis_plan_text_sha256":text_sha(HERE/"analysis_plan.json"),
        "analysis_script_text_sha256":text_sha(Path(__file__)),"results_text_sha256":text_sha(out/"patient_endpoint_summary.json"),
        "python":sys.version.split()[0],"third_party_packages":[],"new_source_fetch_by_analysis":False})
    print("Analyzed all5 patient IDs;24-week linked EPT+/MRI-record/XR-clear pattern3/5; no regenerated-pulp success estimate")

if __name__=="__main__":main()
