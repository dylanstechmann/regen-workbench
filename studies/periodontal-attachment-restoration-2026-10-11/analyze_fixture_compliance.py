#!/usr/bin/env python3
"""Summarize blocked-fixture apparent movement and held-out residuals."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

METHOD_VERSION = "0.1.0"
REQUIRED_FIELDS = {
    "fixture_id", "pipeline_id", "correction_id", "state_id", "state_type",
    "split", "direction", "rate_id", "force_level_id", "replicate_id",
    "force_n", "reference_displacement_mm", "raw_displacement_mm",
    "corrected_displacement_mm",
}
GROUP_FIELDS = (
    "fixture_id", "pipeline_id", "correction_id", "state_id", "state_type",
    "split", "direction", "rate_id", "force_level_id",
)
OUTPUT_FIELDS = (
    *GROUP_FIELDS, "force_n", "n_replicates", "reference_displacement_mm",
    "mean_raw_displacement_mm", "max_abs_raw_residual_mm",
    "raw_rmse_mm", "mean_final_displacement_mm", "max_abs_final_residual_mm",
    "final_rmse_mm", "final_repeatability_sd_mm",
    "final_repeatability_coefficient_95_mm", "criteria_id", "status",
)
CRITERIA_FIELDS = {
    "max_abs_final_residual_mm", "max_final_rmse_mm",
    "max_repeatability_coefficient_95_mm",
}


def finite(value: str, field: str, row_number: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"row {row_number}: {field} must be finite")
    return number


def load_measurements(path: Path) -> dict[tuple[str, ...], list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise ValueError("input contains duplicate column names")
        missing = REQUIRED_FIELDS - set(headers)
        if missing:
            raise ValueError(f"input is missing columns: {', '.join(sorted(missing))}")
        raw_rows = list(reader)
    if not raw_rows:
        raise ValueError("input contains no fixture measurements")

    groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    seen_replicates: set[tuple[tuple[str, ...], str]] = set()
    state_truth: dict[str, tuple[str, float]] = {}
    state_splits: dict[str, str] = {}
    force_truth: dict[tuple[str, ...], float] = {}
    run_methods: set[tuple[str, str, str]] = set()
    corrections: set[str] = set()
    split_types: dict[str, set[str]] = defaultdict(set)

    for row_number, raw in enumerate(raw_rows, start=2):
        values = {field: (raw.get(field) or "").strip() for field in REQUIRED_FIELDS}
        missing_values = sorted(field for field, value in values.items() if field != "corrected_displacement_mm" and not value)
        if missing_values:
            raise ValueError(f"row {row_number}: required fields are blank: {', '.join(missing_values)}")
        if values["state_type"] not in {"blank", "known_motion"}:
            raise ValueError("state_type must be blank or known_motion")
        if values["split"] not in {"development", "held_out"}:
            raise ValueError("split must be development or held_out")

        force = finite(values["force_n"], "force_n", row_number)
        truth = finite(values["reference_displacement_mm"], "reference_displacement_mm", row_number)
        raw_displacement = finite(values["raw_displacement_mm"], "raw_displacement_mm", row_number)
        corrected_text = values["corrected_displacement_mm"]
        corrected = finite(corrected_text, "corrected_displacement_mm", row_number) if corrected_text else None
        if force < 0:
            raise ValueError(f"row {row_number}: force_n must be a nonnegative magnitude")
        if values["state_type"] == "blank" and not math.isclose(truth, 0.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"row {row_number}: blank fixture reference displacement must be zero")

        state_prior = state_truth.setdefault(values["state_id"], (values["state_type"], truth))
        if state_prior[0] != values["state_type"] or not math.isclose(state_prior[1], truth, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"row {row_number}: state_id changes type or reference displacement")
        prior_split = state_splits.setdefault(values["state_id"], values["split"])
        if prior_split != values["split"]:
            raise ValueError(f"row {row_number}: state_id cannot be shared between development and held_out")
        force_key = tuple(values[field] for field in ("state_id", "direction", "rate_id", "force_level_id"))
        force_prior = force_truth.setdefault(force_key, force)
        if not math.isclose(force_prior, force, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"row {row_number}: force changes within force_level_id")

        method = (values["fixture_id"], values["pipeline_id"], values["correction_id"])
        run_methods.add(method)
        corrections.add(values["correction_id"])
        split_types[values["split"]].add(values["state_type"])
        group_key = tuple(values[field] for field in GROUP_FIELDS)
        replicate_key = (group_key, values["replicate_id"])
        if replicate_key in seen_replicates:
            raise ValueError(f"row {row_number}: duplicate replicate_id within one fixture point group")
        seen_replicates.add(replicate_key)
        groups[group_key].append({
            "replicate_id": values["replicate_id"], "force_n": force,
            "truth": truth, "raw": raw_displacement, "corrected": corrected,
        })

    if len(run_methods) != 1:
        raise ValueError("one analysis run must use one fixture, pipeline, and correction_id")
    corrected_flags = {row["corrected"] is not None for rows in groups.values() for row in rows}
    if len(corrected_flags) != 1:
        raise ValueError("corrected_displacement_mm must be supplied for every row or none")
    has_correction = next(iter(corrections)) not in {"none", "no_correction"}
    if has_correction != next(iter(corrected_flags)):
        raise ValueError("correction_id and corrected_displacement_mm must agree")
    if "held_out" not in split_types or "blank" not in split_types["held_out"]:
        raise ValueError("input must include at least one held-out blocked-fixture state")
    if has_correction and not {"development", "held_out"} <= set(split_types):
        raise ValueError("a correction audit requires development and held_out measurements")
    if has_correction and not {"blank", "known_motion"} <= split_types["held_out"]:
        raise ValueError("a correction audit requires held-out blank and known-motion states")
    if has_correction and not {"blank", "known_motion"} <= split_types["development"]:
        raise ValueError("a correction audit requires development blank and known-motion states")
    if any(len(rows) < 2 for rows in groups.values()):
        raise ValueError("each fixture point group needs at least two replicates")
    return groups


def load_criteria(path: Path | None) -> dict | None:
    if path is None:
        return None
    try:
        criteria = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"criteria file is not valid JSON: {exc}") from exc
    if not isinstance(criteria, dict):
        raise ValueError("criteria must be a JSON object")
    missing = {"criteria_id", "locked_before_outcome_review", "limits"} - set(criteria)
    if missing:
        raise ValueError(f"criteria file is missing: {', '.join(sorted(missing))}")
    if not str(criteria["criteria_id"]).strip() or criteria["locked_before_outcome_review"] is not True:
        raise ValueError("criteria need a nonblank criteria_id and locked_before_outcome_review=true")
    limits = criteria["limits"]
    if not isinstance(limits, dict) or set(limits) != CRITERIA_FIELDS:
        raise ValueError(f"limits must define exactly: {', '.join(sorted(CRITERIA_FIELDS))}")
    for name, value in limits.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"criteria {name} must be finite and nonnegative")
    return criteria


def summarize(groups: dict, criteria: dict | None, input_sha256: str) -> tuple[list[dict], dict]:
    records = []
    for key, observations in sorted(groups.items()):
        metadata = dict(zip(GROUP_FIELDS, key))
        truth = observations[0]["truth"]
        raw_errors = [row["raw"] - truth for row in observations]
        final_values = [row["corrected"] if row["corrected"] is not None else row["raw"] for row in observations]
        final_errors = [value - truth for value in final_values]
        raw_mean = statistics.fmean(row["raw"] for row in observations)
        final_mean = statistics.fmean(final_values)
        final_sd = statistics.stdev(final_errors)
        final_rmse = math.sqrt(statistics.fmean(error * error for error in final_errors))
        final_rc95 = 1.96 * math.sqrt(2.0) * final_sd
        status = "not_assessed"
        if criteria:
            status = "development_only" if metadata["split"] == "development" else (
                "pass" if max(abs(error) for error in final_errors) <= criteria["limits"]["max_abs_final_residual_mm"]
                and final_rmse <= criteria["limits"]["max_final_rmse_mm"]
                and final_rc95 <= criteria["limits"]["max_repeatability_coefficient_95_mm"]
                else "fail"
            )
        records.append({
            **metadata,
            "force_n": observations[0]["force_n"],
            "n_replicates": len(observations),
            "reference_displacement_mm": truth,
            "mean_raw_displacement_mm": raw_mean,
            "max_abs_raw_residual_mm": max(abs(value - truth) for value in (row["raw"] for row in observations)),
            "raw_rmse_mm": math.sqrt(statistics.fmean(error * error for error in raw_errors)),
            "mean_final_displacement_mm": final_mean,
            "max_abs_final_residual_mm": max(abs(error) for error in final_errors),
            "final_rmse_mm": final_rmse,
            "final_repeatability_sd_mm": final_sd,
            "final_repeatability_coefficient_95_mm": final_rc95,
            "criteria_id": criteria["criteria_id"] if criteria else "",
            "status": status,
        })

    held_out = [row for row in records if row["split"] == "held_out"]
    overall_status = "not_assessed" if criteria is None else (
        "pass" if all(row["status"] == "pass" for row in held_out) else "fail"
    )
    blank_held_out = [row for row in held_out if row["state_type"] == "blank"]
    summary = {
        "method_version": METHOD_VERSION,
        "input_sha256": input_sha256,
        "fixture_id": records[0]["fixture_id"],
        "pipeline_id": records[0]["pipeline_id"],
        "correction_id": records[0]["correction_id"],
        "criteria_id": criteria["criteria_id"] if criteria else None,
        "locked_before_outcome_review": criteria["locked_before_outcome_review"] if criteria else None,
        "n_groups": len(records),
        "n_held_out_groups": len(held_out),
        "max_held_out_blank_raw_apparent_movement_mm": max(
            row["max_abs_raw_residual_mm"] for row in blank_held_out
        ),
        "max_held_out_final_residual_mm": max(row["max_abs_final_residual_mm"] for row in held_out),
        "max_held_out_final_rmse_mm": max(row["final_rmse_mm"] for row in held_out),
        "max_held_out_repeatability_coefficient_95_mm": max(
            row["final_repeatability_coefficient_95_mm"] for row in held_out
        ),
        "overall_status": overall_status,
        "interpretation_limits": [
            "This report summarizes blocked-fixture or known-motion phantom measurements; it is not a fixture certificate.",
            "The tool does not fit a compliance correction or verify how correction values were generated; corrected results must be evaluated on genuinely held-out states.",
            "Force, direction, rate, contact point, and fixture configuration define the qualified domain; do not extrapolate beyond it.",
            "A pass does not establish biological validity, an injury dose, or suitability for patient use.",
        ],
    }
    return records, summary


def write_outputs(records: list[dict], summary: dict, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    with (outdir / "fixture_compliance_group_metrics.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({field: f"{record[field]:.9g}" if isinstance(record[field], float) else record[field] for field in OUTPUT_FIELDS})
    with (outdir / "fixture_compliance_summary.json").open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(summary, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="tab-separated blocked-fixture and phantom displacement measurements")
    parser.add_argument("--outdir", required=True, type=Path, help="directory for fixture compliance metrics")
    parser.add_argument("--criteria", type=Path, help="optional numeric criteria locked before outcome review")
    args = parser.parse_args()
    try:
        groups = load_measurements(args.input)
        criteria = load_criteria(args.criteria)
        records, summary = summarize(groups, criteria, hashlib.sha256(args.input.read_bytes()).hexdigest())
        write_outputs(records, summary, args.outdir)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"output": str(args.outdir), "groups": len(records), "status": summary["overall_status"]}))


if __name__ == "__main__":
    main()
