#!/usr/bin/env python3
"""Compare known phantom pose with repeated measured pose by component."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


POSE_AXES = {
    "tx_mm": "mm",
    "ty_mm": "mm",
    "tz_mm": "mm",
    "rx_deg": "degrees",
    "ry_deg": "degrees",
    "rz_deg": "degrees",
}
REQUIRED_INPUT = {
    "fixture_id",
    "repeat_group_id",
    "replicate_id",
    "modality",
    "pipeline_id",
    *(f"truth_{axis}" for axis in POSE_AXES),
    *(f"measured_{axis}" for axis in POSE_AXES),
}
CRITERIA_REQUIRED = {"criteria_id", "locked_before_outcome_review", "axes"}


def wrapped_angle_error(measured: float, truth: float) -> float:
    """Return signed angular error in [-180, 180)."""
    return (measured - truth + 180.0) % 360.0 - 180.0


def parse_number(value: str, field: str, row_number: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"row {row_number}: {field} must be finite")
    return number


def load_measurements(path: Path) -> dict[tuple[str, str, str, str], list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        missing = REQUIRED_INPUT - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"input is missing columns: {', '.join(sorted(missing))}")
        rows = list(reader)

    if not rows:
        raise ValueError("input contains no measurement rows")

    groups: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    seen_replicates: set[tuple[str, str, str, str, str]] = set()
    truth_by_group: dict[tuple[str, str, str, str], dict[str, float]] = {}
    for row_number, raw in enumerate(rows, start=2):
        fixture = (raw.get("fixture_id") or "").strip()
        repeat_group = (raw.get("repeat_group_id") or "").strip()
        replicate = (raw.get("replicate_id") or "").strip()
        modality = (raw.get("modality") or "").strip()
        pipeline = (raw.get("pipeline_id") or "").strip()
        if not all((fixture, repeat_group, replicate, modality, pipeline)):
            raise ValueError(f"row {row_number}: fixture, repeat group, replicate, modality, and pipeline IDs are required")

        key = (fixture, repeat_group, modality, pipeline)
        replicate_key = (*key, replicate)
        if replicate_key in seen_replicates:
            raise ValueError(f"row {row_number}: duplicate replicate_id {replicate!r} in one repeat group")
        seen_replicates.add(replicate_key)

        truth = {
            axis: parse_number(raw[f"truth_{axis}"], f"truth_{axis}", row_number)
            for axis in POSE_AXES
        }
        prior_truth = truth_by_group.setdefault(key, truth)
        if any(not math.isclose(truth[axis], prior_truth[axis], rel_tol=0.0, abs_tol=1e-9) for axis in POSE_AXES):
            raise ValueError(f"row {row_number}: truth pose changes within repeat group {repeat_group!r}")

        errors = {}
        for axis in POSE_AXES:
            measured = parse_number(raw[f"measured_{axis}"], f"measured_{axis}", row_number)
            errors[axis] = (
                wrapped_angle_error(measured, truth[axis])
                if axis.endswith("_deg")
                else measured - truth[axis]
            )
        groups[key].append({"replicate_id": replicate, "errors": errors})

    undersized = [key[1] for key, values in groups.items() if len(values) < 2]
    if undersized:
        raise ValueError(f"each repeat group needs at least two acquisitions; undersized: {sorted(set(undersized))}")
    method_pairs = {(key[2], key[3]) for key in groups}
    if len(method_pairs) != 1:
        raise ValueError("an analysis run must use one modality and one pipeline; analyze methods separately")
    return groups


def load_criteria(path: Path | None) -> dict | None:
    if path is None:
        return None
    criteria = json.loads(path.read_text(encoding="utf-8"))
    missing = CRITERIA_REQUIRED - set(criteria)
    if missing:
        raise ValueError(f"criteria file is missing: {', '.join(sorted(missing))}")
    if not str(criteria["criteria_id"]).strip():
        raise ValueError("criteria_id must be nonblank")
    if criteria["locked_before_outcome_review"] is not True:
        raise ValueError("criteria must affirm locked_before_outcome_review=true")
    if set(criteria["axes"]) != set(POSE_AXES):
        raise ValueError("criteria axes must specify exactly tx_mm, ty_mm, tz_mm, rx_deg, ry_deg, and rz_deg")
    for axis, limits in criteria["axes"].items():
        if set(limits) != {"max_abs_group_bias", "max_repeatability_coefficient_95"}:
            raise ValueError(f"criteria for {axis} must define max_abs_group_bias and max_repeatability_coefficient_95")
        for name, value in limits.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"criteria {axis}.{name} must be a finite nonnegative number")
    return criteria


def summarize(groups: dict, criteria: dict | None) -> tuple[list[dict], dict]:
    records = []
    axis_details: dict[str, dict] = {}
    for axis, unit in POSE_AXES.items():
        all_errors: list[float] = []
        within_ss = 0.0
        within_df = 0
        group_biases = []
        group_rcs = []
        group_results = []

        for key, observations in sorted(groups.items()):
            errors = [obs["errors"][axis] for obs in observations]
            bias = statistics.fmean(errors)
            within_ss_group = sum((value - bias) ** 2 for value in errors)
            sw_group = math.sqrt(within_ss_group / (len(errors) - 1))
            rc_group = 1.96 * math.sqrt(2.0) * sw_group
            rmse_group = math.sqrt(statistics.fmean(value * value for value in errors))
            all_errors.extend(errors)
            within_ss += within_ss_group
            within_df += len(errors) - 1
            group_biases.append(abs(bias))
            group_rcs.append(rc_group)

            criteria_axis = criteria["axes"][axis] if criteria else None
            status = "not_assessed"
            if criteria_axis is not None:
                status = (
                    "pass"
                    if abs(bias) <= criteria_axis["max_abs_group_bias"]
                    and rc_group <= criteria_axis["max_repeatability_coefficient_95"]
                    else "fail"
                )
            group_results.append(status)
            records.append({
                "row_type": "repeat_group",
                "fixture_id": key[0],
                "repeat_group_id": key[1],
                "modality": key[2],
                "pipeline_id": key[3],
                "axis": axis,
                "unit": unit,
                "n_acquisitions": len(errors),
                "mean_bias": f"{bias:.6f}",
                "repeatability_sd_within_group": f"{sw_group:.6f}",
                "repeatability_coefficient_95": f"{rc_group:.6f}",
                "rmse": f"{rmse_group:.6f}",
                "max_abs_group_bias": f"{abs(bias):.6f}",
                "criteria_id": criteria["criteria_id"] if criteria else "",
                "status": status,
            })

        pooled_sw = math.sqrt(within_ss / within_df) if within_df else float("nan")
        pooled_rc = 1.96 * math.sqrt(2.0) * pooled_sw
        mean_bias = statistics.fmean(all_errors)
        overall_rmse = math.sqrt(statistics.fmean(value * value for value in all_errors))
        max_group_bias = max(group_biases)
        criteria_axis = criteria["axes"][axis] if criteria else None
        status = "not_assessed"
        if criteria_axis is not None:
            status = (
                "pass"
                if max_group_bias <= criteria_axis["max_abs_group_bias"]
                and pooled_rc <= criteria_axis["max_repeatability_coefficient_95"]
                and all(result == "pass" for result in group_results)
                else "fail"
            )
        records.append({
            "row_type": "all_pose_groups",
            "fixture_id": "all",
            "repeat_group_id": "all",
            "modality": "single modality/pipeline required per analysis",
            "pipeline_id": "single modality/pipeline required per analysis",
            "axis": axis,
            "unit": unit,
            "n_acquisitions": len(all_errors),
            "mean_bias": f"{mean_bias:.6f}",
            "repeatability_sd_within_group": f"{pooled_sw:.6f}",
            "repeatability_coefficient_95": f"{pooled_rc:.6f}",
            "rmse": f"{overall_rmse:.6f}",
            "max_abs_group_bias": f"{max_group_bias:.6f}",
            "criteria_id": criteria["criteria_id"] if criteria else "",
            "status": status,
        })
        axis_details[axis] = {
            "unit": unit,
            "n_acquisitions": len(all_errors),
            "n_repeat_groups": len(groups),
            "mean_bias": mean_bias,
            "pooled_within_group_sd": pooled_sw,
            "repeatability_coefficient_95": pooled_rc,
            "rmse": overall_rmse,
            "max_abs_group_bias": max_group_bias,
            "status": status,
        }

    overall_status = "not_assessed" if criteria is None else (
        "pass" if all(item["status"] == "pass" for item in axis_details.values()) else "fail"
    )
    summary = {
        "schema_version": 1,
        "analysis": "known-pose accuracy and within-repeat-group precision by component",
        "criteria_id": criteria["criteria_id"] if criteria else None,
        "locked_before_outcome_review": criteria["locked_before_outcome_review"] if criteria else None,
        "overall_status": overall_status,
        "axis_results": axis_details,
        "assumptions_and_limits": [
            "A repeat_group_id represents independent acquisitions of the same known fixture pose under one modality and one pipeline; repeated exports of one scan do not count as independent acquisitions.",
            "Component-wise angle differences are wrapped to [-180, 180); this does not replace a validated joint rotation-matrix or quaternion pose-error analysis.",
            "Repeatability coefficient is 1.96*sqrt(2)*pooled within-group SD and assumes approximately independent, homoscedastic, normally distributed errors within the tested pose range.",
            "The estimated repeatability SD has no confidence interval in this minimal analysis; small replicate counts make it unstable, so design the number of independent acquisitions before collecting data.",
            "The summary covers only the fixture poses, acquisition conditions, raters, modality, and pipeline present in the input; passing does not validate a trauma model or biological outcome.",
            "The six rotation inputs are component-wise angles under a convention that must be fixed externally; this script does not validate a joint six-dimensional pose error or guarantee coverage of the intended motion range.",
            "Criteria are self-reported as frozen before outcome review; this script cannot verify when they were chosen.",
        ],
    }
    return records, summary


def write_outputs(outdir: Path, records: list[dict], summary: dict, force: bool) -> None:
    if outdir.exists() and any(outdir.iterdir()) and not force:
        raise FileExistsError(f"output directory is not empty: {outdir}; pass --force to overwrite generated result files")
    outdir.mkdir(parents=True, exist_ok=True)
    tsv_path = outdir / "position_metrology_by_axis.tsv"
    json_path = outdir / "position_metrology_summary.json"
    fields = list(records[0])
    with tsv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="TSV with known and measured pose for each independent acquisition")
    parser.add_argument("--outdir", required=True, type=Path, help="directory for TSV and JSON results")
    parser.add_argument("--criteria", type=Path, help="optional frozen JSON criteria; no pass/fail is assigned without it")
    parser.add_argument("--force", action="store_true", help="replace outputs in a nonempty output directory")
    args = parser.parse_args(argv)
    try:
        groups = load_measurements(args.input)
        criteria = load_criteria(args.criteria)
        records, summary = summarize(groups, criteria)
        write_outputs(args.outdir, records, summary, args.force)
    except (OSError, ValueError, json.JSONDecodeError, FileExistsError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "overall_status": summary["overall_status"],
        "repeat_groups": len(groups),
        "acquisitions": sum(len(values) for values in groups.values()),
        "criteria_id": summary["criteria_id"],
        "output_dir": str(args.outdir),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
