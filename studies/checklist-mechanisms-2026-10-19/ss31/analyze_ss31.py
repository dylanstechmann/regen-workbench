"""Exploratory, source-pinned SS-31 accounting; no concentration curve or regimen.

Run: python analyze_ss31.py
Optional --check-cache verifies the downloaded source hashes if present locally.
Only Python's standard library is required for the derived-data calculation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def fraction(value: float, name: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a measured or explicitly hypothetical fraction")
    if not math.isfinite(value) or value > 1 or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{name} must be {'in [0,1]' if allow_zero else 'in (0,1]'}")
    return float(value)


def conditional_clearance(parent_urine_fraction: float, remaining_other_fraction: float) -> float:
    """Counterfactual, not an empirical prediction for a delivery system/analogue.

    The unchanged-parent urinary fraction can stand in for renal parent CL/total
    parent CL only with adequate collection and linear, time-invariant PK.
    Other disappearance includes any metabolism, possibly in the kidney, and is
    not equated to plasma proteolysis or nonrenal clearance. Fixed parent renal
    clearance is essential; volume is also held fixed in the stated scenario.
    """
    fe = fraction(parent_urine_fraction, "parent urinary recovery anchor")
    q = fraction(remaining_other_fraction, "remaining other parent disappearance", allow_zero=True)
    return fe + (1.0 - fe) * q


def unchanged_parent_material_ratio(reference_F: float, new_F: float, clearance_ratio: float = 1.0) -> float:
    """Assayed unchanged-parent mass to match systemic parent AUC, linear PK.

    Does not match Cmax, time above threshold, site exposure, function or safety.
    It cannot be applied to a covalent analogue as if activity were preserved.
    """
    ref = fraction(reference_F, "reference F")
    new = fraction(new_F, "new F")
    if isinstance(clearance_ratio, bool) or not isinstance(clearance_ratio, (int, float)):
        raise ValueError("clearance ratio must be known")
    if not math.isfinite(clearance_ratio) or clearance_ratio <= 0:
        raise ValueError("clearance ratio must be positive and finite")
    return clearance_ratio * ref / new


def numerical_useful_cost_eligibility(values: dict) -> dict:
    """Reject a numeric useful-exposure/cost ranking when evidence is missing.

    This audit intentionally does not multiply normalized cell endpoints by F
    or treat protein unbound fraction as target mitochondrial access.
    """
    required = ["oral_F", "native_intracellular_access", "relative_function_at_matched_intracellular_parent_exposure", "final_released_material_cost"]
    missing = [key for key in required if values.get(key) is None]
    invalid = []
    for key in required:
        value = values.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            invalid.append(key)
        elif key in ["oral_F", "native_intracellular_access"] and value > 1:
            invalid.append(key)
    return {"eligible": not missing and not invalid, "missing": missing, "invalid": invalid, "numerical_rank": None}


def mean_sd(values: list[float]) -> tuple[float, float]:
    if len(values) < 2 or any(not math.isfinite(x) for x in values):
        raise ValueError("At least two finite source observations are required")
    return statistics.mean(values), statistics.stdev(values)


def summarize_cells(endpoints: list[dict]) -> tuple[list[dict], list[dict]]:
    rows = []
    for endpoint in endpoints:
        parent = next(s for s in endpoint["series"] if s["compound"] == "SS-31")
        parent_mean, _ = mean_sd(parent["replicate_values"])
        for series in endpoint["series"]:
            mean, sd = mean_sd(series["replicate_values"])
            if not math.isclose(mean, series["source_mean"], rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError(f"Source mean discrepancy: {series['source_cells']}")
            if not math.isclose(sd, series["source_sd"], rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError(f"Source SD discrepancy: {series['source_cells']}")
            rows.append({"endpoint_id": endpoint["endpoint_id"], "compound": series["compound"], "cell_line": endpoint["cell_line"], "n_source_units": len(series["replicate_values"]), "mean": mean, "sample_sd": sd, "difference_from_ss31_in_source_units": mean - parent_mean, "source_cells": series["source_cells"], "normalization": endpoint["normalization"], "source_unit": endpoint["source_unit"]})
    by_id = {e["endpoint_id"]: {s["compound"]: s for s in e["series"]} for e in endpoints}
    matches = []
    for compound, left in by_id["viability_stressed"].items():
        if compound == "Control":
            continue  # Normalization makes all control entries exactly one.
        right = by_id["atp_stressed"][compound]
        a, b = left["replicate_values"], right["replicate_values"]
        matches.append({"compound": compound, "left_cells": left["source_cells"], "right_cells": right["source_cells"], "same_position_exact_matches": sum(x == y for x, y in zip(a, b)), "compared_positions": min(len(a), len(b)), "entire_vectors_exactly_equal": a == b, "interpretation": "Source-data dependence/reuse cannot be resolved here; no cause inferred. These endpoints do not supply established independent replication."})
    return rows, matches


def check_source_cache(manifest: dict, repo: Path) -> list[dict]:
    results = []
    for source in manifest["source_files"]:
        path = repo / source["relative_cached_path"]
        if not path.exists():
            results.append({"source_id": source["source_id"], "status": "not_cached"})
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != source["sha256"]:
            raise ValueError(f"Source hash mismatch: {source['source_id']}")
        results.append({"source_id": source["source_id"], "status": "hash_matches"})
    return results


def calculate(inputs: dict) -> tuple[dict, list[dict]]:
    ref_F = inputs["fda_label"]["human_sc_absolute_bioavailability_approx"]
    recovery = inputs["urinary_recovery"]
    fe = recovery["reported_fraction_parent_approx"]
    scenarios = []
    for q in [1.0, 0.5, 0.0]:
        cl = conditional_clearance(fe, q)
        scenarios.append({"remaining_other_parent_disappearance_fraction_q_hypothetical": q, "relative_parent_clearance_conditional": cl, "systemic_parent_auc_gain_at_fixed_F_and_parent_input_conditional": 1 / cl, "oral_F_needed_for_equal_material_to_reference_sc": ref_F * cl, "threshold_status": "algebraic break-even condition; not a measured oral F or attainable modification"})
    sensitivity = [{"parent_urine_fraction_hypothetical": f, "conditional_gain_if_all_other_disappearance_removed": 1 / conditional_clearance(f, 0.0)} for f in [0.05, 0.10, 0.20]]
    rows, duplicates = summarize_cells(inputs["cell_endpoints"])
    q = inputs["process"]["intermediate_quality"]
    iv = inputs["human_iv_parent_pk"]["cohorts"]
    sc = inputs["human_sc_parent_pk"]["cohorts"]
    result = {
        "analysis_status": "Exploratory conditional accounting, no new molecule, no fitted concentration-time or efficacy model",
        "inputs_sha256": hashlib.sha256((HERE / "inputs.json").read_text(encoding="utf-8").encode("utf-8")).hexdigest(),
        "inputs_hash_convention": "UTF-8 text after universal-newline normalization to LF",
        "human_context": {
            "iv_parent_terminal_half_life_mean_range_h": [min(x["terminal_half_life_h_mean"] for x in iv), max(x["terminal_half_life_h_mean"] for x in iv)],
            "iv_parent_mean_residence_time_mean_range_h": [min(x["mean_residence_time_h_mean"] for x in iv), max(x["mean_residence_time_h_mean"] for x in iv)],
            "sc_parent_terminal_half_life_geometric_mean_range_h": [min(x["terminal_half_life_h_geometric_mean"] for x in sc), max(x["terminal_half_life_h_geometric_mean"] for x in sc)],
            "in_vitro_human_plasma_fitted_half_life_range_h": sorted(inputs["human_plasma_stability"]["reported_half_life_h"]),
            "range_interpretation": "Across source cohort means or assay inputs, not confidence intervals or interchangeable routes; no half-life quotient used",
            "rounded_parent_plus_metabolite_urine_fraction_sum": sum(recovery[k] for k in ["reported_fraction_parent_approx", "reported_fraction_m1_approx", "reported_fraction_m2_approx"]),
            "recovery_sum_interpretation": "Rounded source values retained, not normalized; adequate collection is an assumption for the clearance calculation, not established from individual records here"
        },
        "conditional_clearance_partition": {
            "parent_urine_fraction_anchor_approx": fe,
            "assumptions": ["adequate IV unchanged-parent recovery collection", "linear time-invariant parent disposition", "fixed unchanged-parent renal clearance", "fixed distribution volume in this counterfactual; no half-life prediction made", "q applies to all other parent disappearance, which can include renal metabolism and is not identified as plasma proteolysis", "SC label F used as a separate approximate reference, not a matched-cohort estimate"],
            "scenarios": scenarios,
            "sensitivity_scenarios_not_a_confidence_interval": sensitivity,
            "universal_analogue_ceiling": None,
            "uncertainty": "Rounded recovery and small normal-renal IV cohort; modification may change renal clearance, distribution, analyte identity, activity and route exposure. No universal ten-fold bound follows."
        },
        "unchanged_parent_oral_material_bound": {
            "clearance_unchanged": True,
            "oral_F_assigned": None,
            "matched_outcome": "systemic intact-parent AUC, not useful intracellular exposure or duration",
            "parent_mass_ratio_to_sc_formula": "0.92 / oral_F",
            "mathematical_lower_bound_at_oral_F_equal_one": unchanged_parent_material_ratio(ref_F, 1.0),
            "uniform_finite_upper_bound": None,
            "maximum_possible_parent_material_reduction_fraction_under_these_assumptions": 1 - ref_F,
            "finite_upper_bound_absence_reason": "Oral F can approach zero; no numeric SS-31 oral F is established by these sources.",
            "useful_exposure_cost_rank": numerical_useful_cost_eligibility(inputs["comparison_unknowns"])
        },
        "process_accounting": {
            "source_example_final_salt_to_protected_precursor_mass_ratio": inputs["process"]["final_parent"]["isolated_final_salt_mass_g"] / inputs["process"]["final_parent"]["protected_precursor_input_mass_g"],
            "mass_ratio_is_molar_yield": False,
            "overall_released_parent_yield": None,
            "actual_final_parent_cost": None,
            "purity_assay_example_material": q["material"],
            "actual_to_area_assumed_bulk_for_equal_assayed_intermediate_content_ratio": q["hplc_area_purity_fraction"] / q["weight_assay_fraction"],
            "area_assay_example_is_final_parent_cost_estimate": False,
            "cost_identity": "cost per released assayed-parent mass = total process + QC/release + rejected-batch cost / released assayed-parent mass; both numerator and denominator unidentified here",
            "missing": inputs["process"]["final_parent"]["missing"]
        },
        "cell_endpoint_rows": len(rows),
        "cell_endpoint_values_reproduced": True,
        "cross_endpoint_exact_value_audit": duplicates,
        "native_target_access_calibrated": False,
        "functional_analogue_equivalence_established": False
    }
    return result, rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-cache", action="store_true")
    args = parser.parse_args()
    inputs = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
    manifest = json.loads((HERE / "source_manifest.json").read_text(encoding="utf-8"))
    results, rows = calculate(inputs)
    if args.check_cache:
        print(json.dumps({"source_cache": check_source_cache(manifest, HERE.parents[2])}))
    (HERE / "results.json").write_text(json.dumps(results, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (HERE / "cell_endpoint_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"endpoint_series_reproduced": len(rows), "useful_cost_rank_eligible": results["unchanged_parent_oral_material_bound"]["useful_exposure_cost_rank"]["eligible"], "results": "results.json"}))


if __name__ == "__main__":
    main()
