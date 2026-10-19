"""Check whether declared PK evidence can support specified calculations.

This study utility does not estimate PK from prose or certify source metadata.
It computes eligibility only; numerical estimates stay null. Synthetic tests
are not observations of SLU-PP-915.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def assess_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Distinguish numerical signal integration from qualified parent exposure."""
    if not isinstance(profile, dict):
        raise ValueError("A context profile must be an object.")
    reasons: list[str] = []
    points = profile.get("points", [])
    source = profile.get("numeric_source", {})
    if not isinstance(source, dict):
        raise ValueError("Numeric-source qualification must be an object.")
    if profile.get("curve_kind") != "concentration_time":
        reasons.append("The observations are not one concentration-time curve.")
    if not isinstance(points, list) or len(points) < 2:
        reasons.append("At least two retrieved quantitative time-concentration points are missing.")
        points = points if isinstance(points, list) else []
    if source.get("kind") not in {"measured_table", "digitized_figure"}:
        reasons.append("No numeric primary table or calibrated figure extraction was acquired.")
    if source.get("metadata_only") is not False:
        reasons.append("Source is metadata only or its numeric-content status is unknown.")
    if not _digest(source.get("sha256")) or not source.get("location"):
        reasons.append("Numeric-source bytes and their table/figure location are not linked.")
    if profile.get("time_unit") not in {"min", "h"} or profile.get("concentration_unit") not in {"ng/mL", "nmol/L"}:
        reasons.append("Supported and consistent time/concentration units are not established.")
    if profile.get("censoring_policy") != "all_points_quantified":
        reasons.append("No all-quantified-point record is established; censored data need separate reviewed handling.")
    valid_points = bool(points) and all(
        isinstance(p, dict) and _number(p.get("time")) and p["time"] >= 0
        and _number(p.get("concentration")) and p["concentration"] >= 0
        and p.get("quantitation") == "quantified"
        for p in points
    )
    if points and not valid_points:
        reasons.append("Points contain missing, nonfinite, negative or censored values requiring an explicit policy.")
    if valid_points and any(points[i]["time"] >= points[i + 1]["time"] for i in range(len(points) - 1)):
        reasons.append("Time points must be strictly increasing within a single profile.")
    if source.get("kind") == "digitized_figure":
        if not source.get("axis_calibration_verified"):
            reasons.append("Figure axes have not been calibrated and checked.")
        for point in points:
            if not isinstance(point, dict):
                continue
            for field, bounds in (("time", "time_bounds"), ("concentration", "concentration_bounds")):
                interval = point.get(bounds)
                if not (
                    isinstance(interval, list) and len(interval) == 2
                    and all(_number(x) for x in interval) and interval[0] >= 0
                    and _number(point.get(field)) and interval[0] <= point[field] <= interval[1]
                ):
                    reasons.append("Digitized point bounds are incomplete or do not contain the extracted value.")
                    break
    signal_reasons = list(dict.fromkeys(reasons))
    parent_reasons = list(signal_reasons)
    if profile.get("analyte") != "SLU-PP-915":
        parent_reasons.append("The analyte is not intact SLU-PP-915.")
    assay = profile.get("assay_qualification", {})
    if not isinstance(assay, dict):
        raise ValueError("Assay qualification must be an object.")
    for key in ("parent_identity", "calibration", "selectivity", "sample_stability"):
        if assay.get(key) is not True:
            parent_reasons.append(f"Intact-parent assay qualification is missing: {key}.")
    if profile.get("matrix") != "plasma":
        parent_reasons.append("Plasma matrix identity is not established for this intake.")
    if profile.get("species") != "mouse":
        parent_reasons.append("The mouse study population is not established for this intake.")
    if profile.get("route") not in {"oral_gavage", "oral_voluntary_suspension", "intraperitoneal", "intravenous"}:
        parent_reasons.append("An unambiguous supported administration route is missing.")
    if profile.get("route_or_time_conflict") is not False:
        parent_reasons.append("A route/timing conflict is unresolved or its status is unknown.")
    sampling = profile.get("sampling", {})
    if not isinstance(sampling, dict):
        raise ValueError("Sampling qualification must be an object.")
    if sampling.get("design") not in {"serial_individual", "terminal_cross_sectional"}:
        parent_reasons.append("Serial versus terminal sampling design is not resolved.")
    if sampling.get("curve_unit") not in {"individual", "group_mean"}:
        parent_reasons.append("Individual versus group-mean curve identity is missing.")
    if sampling.get("statistical_unit") != "mouse":
        parent_reasons.append("The independent biological unit is not established as a mouse.")
    if valid_points and any(not isinstance(p.get("n_subjects"), int) or isinstance(p.get("n_subjects"), bool) or p["n_subjects"] < 1 for p in points):
        parent_reasons.append("The number of biological subjects at each time is missing or invalid.")
    if valid_points and sampling.get("curve_unit") == "individual":
        ids = [p.get("subject_id") for p in points]
        valid_ids = all(isinstance(subject, str) and subject.strip() for subject in ids)
        if sampling.get("design") != "serial_individual" or not valid_ids or len(set(ids)) != 1:
            parent_reasons.append("Individual AUC requires one identified serially sampled subject.")
        if any(p.get("n_subjects") != 1 for p in points):
            parent_reasons.append("Individual AUC requires exactly one biological subject at every time point.")
    parent_reasons = list(dict.fromkeys(parent_reasons))
    # Group SEMs do not supply within-animal or between-time covariance.
    uncertainty_ok = (
        not parent_reasons and sampling.get("individual_curves_and_covariance_available") is True
    )
    return {
        "profile_id": profile["id"],
        "evidence_scope": "synthetic_test_fixture" if profile.get("fixture_only") else "source_intake",
        "retrieved_point_count": len(points),
        "observed_signal_integration_input_eligible": not signal_reasons,
        "qualified_intact_parent_auc_input_eligible": not parent_reasons,
        "individual_or_population_auc_uncertainty_input_eligible": uncertainty_ok,
        "signal_integration_reasons": signal_reasons,
        "intact_parent_auc_reasons": parent_reasons,
        "uncertainty_limit": None if uncertainty_ok else "No qualified individual curves/covariance; do not infer AUC uncertainty from group SEMs or technical replicates.",
        "observed_interval": [points[0]["time"], points[-1]["time"]] if not signal_reasons else None,
        "auc_estimate": None,
        "absolute_oral_F_estimate": None,
        "terminal_half_life_refit": None,
        "calculation_performed": False,
    }


def assess_intake(intake: dict[str, Any]) -> dict[str, Any]:
    if intake.get("schema_version") != 1:
        raise ValueError("Unsupported intake schema.")
    profiles = intake.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("At least one context profile is required.")
    if any(not isinstance(p, dict) for p in profiles):
        raise ValueError("Every context profile must be an object.")
    ids = [p.get("id") for p in profiles]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("Profiles require unique nonempty identifiers.")
    results = [assess_profile(p) for p in profiles]
    reference = intake.get("absolute_F_reference", {})
    if not isinstance(reference, dict):
        raise ValueError("Absolute-F reference qualification must be an object.")
    oral = [r for r, p in zip(results, profiles) if p.get("id") == reference.get("oral_profile_id") and p.get("route") in {"oral_gavage", "oral_voluntary_suspension"} and r["qualified_intact_parent_auc_input_eligible"]]
    intravenous = [r for r, p in zip(results, profiles) if p.get("id") == reference.get("intravenous_profile_id") and p.get("route") == "intravenous" and r["qualified_intact_parent_auc_input_eligible"]]
    reference_ok = (
        bool(oral) and bool(intravenous)
        and reference.get("exposure_normalization_qualified") is True
        and reference.get("matched_population_and_clearance_qualified") is True
        and reference.get("route_matched_auc_window_or_terminal_coverage_qualified") is True
    )
    return {
        "schema_version": 1,
        "study_id": intake.get("study_id"),
        "scope": "Eligibility of declared evidence, not source certification or PK estimation.",
        "profiles": results,
        "absolute_oral_F_input_eligible": reference_ok,
        "absolute_F_limit": None if reference_ok else "No qualified oral/IV reference pair with normalization, population/clearance comparability and matched AUC coverage. Intraperitoneal reference alone cannot supply absolute F.",
        "absolute_oral_F_estimate": None,
        "human_exposure_estimate": None,
        "calculation_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake", type=Path, default=Path(__file__).with_name("pk_context_intake.json"))
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("eligibility_report.json"))
    args = parser.parse_args()
    raw = args.intake.read_bytes()
    result = assess_intake(json.loads(raw))
    result["intake_sha256"] = hashlib.sha256(raw).hexdigest()
    result["assessor_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"contexts": len(result["profiles"]), "qualified_parent_auc_contexts": sum(p["qualified_intact_parent_auc_input_eligible"] for p in result["profiles"]), "absolute_F_input_eligible": result["absolute_oral_F_input_eligible"]}))


if __name__ == "__main__":
    main()
