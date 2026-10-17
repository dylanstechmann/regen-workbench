#!/usr/bin/env python3
"""Audit force/displacement timing offset, jitter, and displacement error."""

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
    "run_id", "pipeline_id", "timebase_id", "condition_id", "replicate_id",
    "rate_id", "reference_time_s", "force_event_time_s",
    "displacement_event_time_s", "max_velocity_mm_s",
}
GROUP_FIELDS = ("run_id", "pipeline_id", "timebase_id", "condition_id", "rate_id")
OUTPUT_FIELDS = (
    *GROUP_FIELDS, "n_replicates", "mean_force_lag_s", "force_lag_sd_s",
    "mean_displacement_lag_s", "displacement_lag_sd_s",
    "mean_channel_offset_s", "channel_offset_jitter_sd_s",
    "max_abs_channel_offset_s", "max_velocity_mm_s",
    "predicted_error_from_jitter_mm", "max_observed_timing_error_mm",
    "criteria_id", "status",
)
CRITERIA_FIELDS = {
    "max_abs_channel_offset_s", "max_channel_offset_jitter_sd_s",
    "max_observed_timing_error_mm",
}


def finite(value: str, field: str, row_number: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"row {row_number}: {field} must be finite")
    return number


def load_events(path: Path) -> dict[tuple[str, ...], list[dict]]:
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
        raise ValueError("input contains no timing events")

    groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    seen: set[tuple[tuple[str, ...], str]] = set()
    run_methods: set[tuple[str, str, str]] = set()
    condition_velocities: dict[tuple[str, ...], float] = {}
    for row_number, raw in enumerate(raw_rows, start=2):
        values = {field: (raw.get(field) or "").strip() for field in REQUIRED_FIELDS}
        blank = sorted(field for field, value in values.items() if value == "")
        if blank:
            raise ValueError(f"row {row_number}: required fields are blank: {', '.join(blank)}")
        reference = finite(values["reference_time_s"], "reference_time_s", row_number)
        force = finite(values["force_event_time_s"], "force_event_time_s", row_number)
        displacement = finite(values["displacement_event_time_s"], "displacement_event_time_s", row_number)
        velocity = finite(values["max_velocity_mm_s"], "max_velocity_mm_s", row_number)
        if velocity < 0:
            raise ValueError(f"row {row_number}: max_velocity_mm_s must be nonnegative")

        method = (values["run_id"], values["pipeline_id"], values["timebase_id"])
        run_methods.add(method)
        group_key = tuple(values[field] for field in GROUP_FIELDS)
        condition_key = (values["condition_id"], values["rate_id"])
        prior_velocity = condition_velocities.setdefault(condition_key, velocity)
        if not math.isclose(prior_velocity, velocity, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"row {row_number}: max velocity changes within condition and rate")
        replicate_key = (group_key, values["replicate_id"])
        if replicate_key in seen:
            raise ValueError(f"row {row_number}: duplicate replicate_id within one timing condition")
        seen.add(replicate_key)
        groups[group_key].append({
            "replicate_id": values["replicate_id"],
            "force_lag": force - reference,
            "displacement_lag": displacement - reference,
            "offset": displacement - force,
            "velocity": velocity,
        })

    if len(run_methods) != 1:
        raise ValueError("one analysis run must use one run_id, pipeline_id, and timebase_id")
    if any(len(rows) < 2 for rows in groups.values()):
        raise ValueError("each timing condition needs at least two repeated events")
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
        force_lags = [row["force_lag"] for row in observations]
        displacement_lags = [row["displacement_lag"] for row in observations]
        offsets = [row["offset"] for row in observations]
        velocity = max(row["velocity"] for row in observations)
        offset_sd = statistics.stdev(offsets)
        max_offset = max(abs(value) for value in offsets)
        max_error = velocity * max_offset
        status = "not_assessed"
        if criteria:
            limits = criteria["limits"]
            status = "pass" if (
                max_offset <= limits["max_abs_channel_offset_s"]
                and offset_sd <= limits["max_channel_offset_jitter_sd_s"]
                and max_error <= limits["max_observed_timing_error_mm"]
            ) else "fail"
        records.append({
            **metadata,
            "n_replicates": len(observations),
            "mean_force_lag_s": statistics.fmean(force_lags),
            "force_lag_sd_s": statistics.stdev(force_lags),
            "mean_displacement_lag_s": statistics.fmean(displacement_lags),
            "displacement_lag_sd_s": statistics.stdev(displacement_lags),
            "mean_channel_offset_s": statistics.fmean(offsets),
            "channel_offset_jitter_sd_s": offset_sd,
            "max_abs_channel_offset_s": max_offset,
            "max_velocity_mm_s": velocity,
            "predicted_error_from_jitter_mm": velocity * offset_sd,
            "max_observed_timing_error_mm": max_error,
            "criteria_id": criteria["criteria_id"] if criteria else "",
            "status": status,
        })

    overall_status = "not_assessed" if criteria is None else (
        "pass" if all(row["status"] == "pass" for row in records) else "fail"
    )
    summary = {
        "method_version": METHOD_VERSION,
        "input_sha256": input_sha256,
        "run_id": records[0]["run_id"],
        "pipeline_id": records[0]["pipeline_id"],
        "timebase_id": records[0]["timebase_id"],
        "criteria_id": criteria["criteria_id"] if criteria else None,
        "locked_before_outcome_review": criteria["locked_before_outcome_review"] if criteria else None,
        "n_conditions": len(records),
        "max_abs_channel_offset_s": max(row["max_abs_channel_offset_s"] for row in records),
        "max_channel_offset_jitter_sd_s": max(row["channel_offset_jitter_sd_s"] for row in records),
        "max_observed_timing_error_mm": max(row["max_observed_timing_error_mm"] for row in records),
        "overall_status": overall_status,
        "interpretation_limits": [
            "The displacement error bound uses the largest observed absolute channel offset times the declared maximum velocity for each condition.",
            "Repeated trigger tests characterize observed timing only; they do not prove clock accuracy between triggers or across untested waveforms.",
            "The reference event, detection method, sampling rates, filters, and timebase must be documented and held fixed.",
            "A pass does not establish biological validity, an injury dose, or suitability for patient use.",
        ],
    }
    return records, summary


def write_outputs(records: list[dict], summary: dict, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    with (outdir / "channel_timing_metrics.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({field: f"{record[field]:.9g}" if isinstance(record[field], float) else record[field] for field in OUTPUT_FIELDS})
    with (outdir / "channel_timing_summary.json").open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(summary, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="tab-separated repeated common-trigger timing events")
    parser.add_argument("--outdir", required=True, type=Path, help="directory for channel timing metrics")
    parser.add_argument("--criteria", type=Path, help="optional numeric criteria locked before outcome review")
    args = parser.parse_args()
    try:
        groups = load_events(args.input)
        criteria = load_criteria(args.criteria)
        records, summary = summarize(groups, criteria, hashlib.sha256(args.input.read_bytes()).hexdigest())
        write_outputs(records, summary, args.outdir)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"output": str(args.outdir), "conditions": len(records), "status": summary["overall_status"]}))


if __name__ == "__main__":
    main()
