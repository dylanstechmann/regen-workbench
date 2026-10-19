"""MOTS-c analytical scale separation and source-aware eligibility, not PK fitting."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def positive(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite positive numeric source data")
    return float(value)


def ng_per_mL(value, unit: str) -> float:
    factors = {"pg/mL": 0.001, "ng/mL": 1.0}
    if unit not in factors:
        raise ValueError("Only explicitly supported concentration units are accepted")
    return positive(value, "concentration/limit") * factors[unit]


def analytical_scale_separation(summary: dict) -> dict:
    """Compare two reported scales, never impute a true native concentration."""
    lod = ng_per_mL(summary["llod_value"], summary["llod_unit"])
    limits = summary["elisa_reported_range"]
    if len(limits) != 2:
        raise ValueError("Require a reported concentration range")
    values = [ng_per_mL(x, summary["elisa_range_unit"]) for x in limits]
    if values[0] > values[1]:
        raise ValueError("Reversed source range")
    return {
        "reported_LLOD_ng_per_mL": lod,
        "reported_ELISA_signal_range_ng_per_mL": values,
        "reported_ELISA_signal_to_LLOD_scale_ratio_range": [x / lod for x in values],
        "n_reference_subjects": summary["n_subjects"],
        "individual_paired_concentrations_available": summary["individual_paired_concentrations"] is not None,
        "true_intact_parent_concentrations": None,
        "assay_bias_or_cross_reactivity_estimate": None,
        "universal_ELISA_failure_inferred": False,
        "interpretation": "Reported immunoassay-signal/LCMS-detection-limit scale separation only; not a true concentration bound, specificity proof, calibration slope, or PK parameter."
    }


def require_true(evidence: dict, keys: list[str]) -> list[str]:
    return [key for key in keys if evidence.get(key) is not True]


def assess_pk(evidence: dict) -> dict:
    keys = ["source_reports_parent_specific_detection", "source_reports_quantitative_matrix_assay_validation", "baseline_or_endogenous_component_resolved", "administered_systemic_route_known", "serial_concentration_time_data"]
    missing_auc = require_true(evidence, keys)
    if evidence.get("context") not in {"systemic_administration", "steady_state_extravascular_infusion"}:
        missing_auc.append("in_vivo_systemic_administration_context")
    count = evidence.get("reported_timepoint_count")
    valid_count = isinstance(count, int) and not isinstance(count, bool) and count >= 0
    if not valid_count or count < 2:
        missing_auc.append("at_least_two_quantified_concentration_time_pairs")
    missing_terminal = missing_auc + require_true(evidence, ["sufficient_terminal_phase_sampling"])
    missing_clearance = missing_auc + require_true(evidence, ["systemic_input_fraction_known", "administered_parent_amount_known", "complete_parent_AUC_or_qualified_extrapolation"])
    missing_oral = missing_auc + require_true(evidence, ["paired_oral_iv_parent_auc_available", "dose_normalization_known", "route_comparison_context_qualified", "both_routes_complete_parent_AUC_or_qualified_extrapolation"])
    return {
        "case_id": evidence["case_id"], "context": evidence["context"],
        "reported_timepoint_count": count,
        "finite_interval_parent_AUC_intake_eligible": not missing_auc,
        "terminal_half_life_intake_eligible": not missing_terminal,
        "absolute_parent_clearance_from_AUC_intake_eligible": not missing_clearance,
        "absolute_oral_F_intake_eligible": not missing_oral,
        "missing_for_AUC": missing_auc,
        "missing_for_terminal_half_life": missing_terminal,
        "missing_for_absolute_clearance_from_AUC": missing_clearance,
        "missing_for_oral_F": missing_oral,
        "numerical_AUC_half_life_clearance_or_F": None,
        "gate_limit": "Source-presence checks for concentration-time/AUC accounting only; the separate steady-state identity does not require a decay series. No data fit or quantitative inference is made by a passing gate."
    }


def assess_donor_linkage(evidence: dict) -> dict:
    keys = ["numeric_metabolic_values", "numeric_repair_values", "stable_individual_donor_ids", "culture_to_donor_crosswalk", "recipient_to_donor_crosswalk", "endpoint_unit_hierarchy_resolved"]
    missing = require_true(evidence, keys)
    return {"numerical_donor_linked_metabolism_repair_reanalysis_eligible": not missing, "missing": missing, "effect_or_correlation_estimate": None}


def calculate(inputs: dict) -> tuple[dict, list[dict]]:
    cases = [assess_pk(e) for e in inputs["pk_evidence_cases"]]
    msc = inputs["msc_intake"]
    result = {
        "status": "Source-data unavailability qualified; authorized pivot to primary analytical specificity and PK intake",
        "inputs_sha256_lf_text": hashlib.sha256((HERE / "inputs.json").read_text(encoding="utf-8").encode("utf-8")).hexdigest(),
        "hash_convention": "UTF-8 text after universal-newline normalization to LF",
        "MSC_units": {"human_donors": msc["human_donors"]["lean_n"] + msc["human_donors"]["obese_n"], "recipient_mice": msc["recipient_mice"]["n_groups"] * msc["recipient_mice"]["n_mice_per_group"], "combined_independent_sample_size": None, "histology_field_n_can_replace_mouse_n": False, "donor_linkage": assess_donor_linkage(msc["donor_linked_reanalysis_inputs"])},
        "analytical_scale_comparison": analytical_scale_separation(inputs["knoop_analytical_comparison"]),
        "steady_state_identity": {
            "expression": "C_ss = F * R / CL",
            "scope": "Simple linear steady-state parent mass balance; R is administered parent input rate, F its systemic fraction, C_ss its exogenous intact-parent increment with endogenous contribution resolved.",
            "half_life_expression": "t_half = ln(2) * V / CL",
            "half_life_scope": "One-compartment linear disposition (or appropriate terminal distribution volume); neither V nor terminal slope follows from one steady-state immunoreactive concentration.",
            "K14Q_reported_apparent_clearance_slowing_factor": inputs["k14q_steady_state"]["reported_relative_apparent_clearance_slowing_factor"],
            "variant_specific_plasma_calibration_preserved": inputs["k14q_steady_state"]["calibration_is_corrective_evidence"],
            "interpretation": "Variant-specific calibration corrects lower assay sensitivity and is real evidence. It does not resolve intact molecular species, every product's cross-reactivity, endogenous baseline, input F or a decay half-life. Knoop's different commercial assay does not universally invalidate it.",
            "new_native_clearance_or_half_life_estimate": None
        },
        "pk_eligibility": cases,
        "eligible_numerical_parent_pk_datasets": sum(case["finite_interval_parent_AUC_intake_eligible"] for case in cases),
        "oral_F_assigned": None,
        "delivery_or_analogue_functional_rank": None,
        "source_observations_digitized_or_synthesized": False
    }
    rows = [{k: case[k] for k in ["case_id", "context", "reported_timepoint_count", "finite_interval_parent_AUC_intake_eligible", "terminal_half_life_intake_eligible", "absolute_parent_clearance_from_AUC_intake_eligible", "absolute_oral_F_intake_eligible"]} | {"missing_for_AUC": "; ".join(case["missing_for_AUC"])} for case in cases]
    return result, rows


def verify_cache(manifest: dict) -> dict:
    for source in manifest["source_files"]:
        path = REPO / source["relative_cached_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"Source hash mismatch: {source['source_id']}")
    return {"downloaded_source_hashes_checked": len(manifest["source_files"]), "all_match": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-cache", action="store_true")
    args = parser.parse_args()
    inputs = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
    manifest = json.loads((HERE / "source_manifest.json").read_text(encoding="utf-8"))
    result, rows = calculate(inputs)
    if args.check_cache:
        print(json.dumps(verify_cache(manifest)))
    (HERE / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (HERE / "pk_eligibility.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"PK_cases": len(result["pk_eligibility"]), "eligible_parent_PK_datasets": result["eligible_numerical_parent_pk_datasets"], "scale_ratio_range": result["analytical_scale_comparison"]["reported_ELISA_signal_to_LLOD_scale_ratio_range"]}))


if __name__ == "__main__":
    main()
