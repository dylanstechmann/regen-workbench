#!/usr/bin/env python3
"""Audit reference-based force and displacement calibration points."""

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
CHANNEL_UNITS = {"force": "N", "displacement": "mm"}
REQUIRED_FIELDS = {
    "calibration_id", "channel", "instrument_id", "reference_id",
    "reference_certificate_id", "pipeline_id", "point_id", "replicate_id",
    "direction", "rate_id", "timepoint", "reference_value",
    "indicated_value", "reference_uncertainty", "unit",
}
GROUP_FIELDS = (
    "calibration_id", "channel", "instrument_id", "reference_id",
    "reference_certificate_id", "pipeline_id", "point_id", "direction",
    "rate_id", "timepoint", "unit",
)
MATCH_FIELDS = tuple(field for field in GROUP_FIELDS if field != "timepoint")
GROUP_OUTPUT_FIELDS = (
    *GROUP_FIELDS, "n_replicates", "reference_value", "reference_uncertainty",
    "mean_indicated_value", "mean_bias", "max_abs_error", "rmse",
    "repeatability_sd", "repeatability_coefficient_95", "criteria_id", "status",
)
DRIFT_OUTPUT_FIELDS = (
    "calibration_id", "channel", "instrument_id", "reference_id",
    "reference_certificate_id", "pipeline_id", "point_id", "direction",
    "rate_id", "unit", "n_pre", "n_post", "mean_pre", "mean_post",
    "pre_post_drift", "max_allowed_drift", "criteria_id", "status",
)
CRITERIA_FIELDS = {
    "max_abs_group_bias", "max_rmse", "max_repeatability_coefficient_95",
    "max_pre_post_drift",
}


def parse_finite(value: str, field: str, row_number: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"row {row_number}: {field} must be finite")
    return number


def load_calibration_points(path: Path) -> dict[tuple[str, ...], list[dict]]:
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
        raise ValueError("input contains no calibration rows")

    groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    seen_replicates: set[tuple[tuple[str, ...], str]] = set()
    point_truth: dict[tuple[str, str, str], tuple[float, float, str]] = {}
    channel_methods: dict[str, tuple[str, str, str, str]] = {}
    calibration_methods: set[tuple[str, str]] = set()

    for row_number, raw in enumerate(raw_rows, start=2):
        values = {field: (raw.get(field) or "").strip() for field in REQUIRED_FIELDS}
        blank = sorted(field for field, value in values.items() if value == "")
        if blank:
            raise ValueError(f"row {row_number}: required fields are blank: {', '.join(blank)}")
        channel = values["channel"]
        if channel not in CHANNEL_UNITS:
            raise ValueError("channel must be force or displacement")
        if values["unit"] != CHANNEL_UNITS[channel]:
            raise ValueError(f"channel {channel} requires unit {CHANNEL_UNITS[channel]}")
        if values["timepoint"] not in {"pre", "post"}:
            raise ValueError("timepoint must be pre or post")

        reference = parse_finite(values["reference_value"], "reference_value", row_number)
        indicated = parse_finite(values["indicated_value"], "indicated_value", row_number)
        uncertainty = parse_finite(values["reference_uncertainty"], "reference_uncertainty", row_number)
        if uncertainty < 0:
            raise ValueError(f"row {row_number}: reference_uncertainty must be nonnegative")

        point_key = (values["calibration_id"], channel, values["point_id"])
        point_definition = (reference, uncertainty, values["unit"])
        prior_definition = point_truth.setdefault(point_key, point_definition)
        if prior_definition[2] != point_definition[2] or any(
            not math.isclose(prior_definition[index], point_definition[index], rel_tol=0.0, abs_tol=1e-12)
            for index in (0, 1)
        ):
            raise ValueError(f"row {row_number}: reference value or uncertainty changes for point {values['point_id']!r}")

        channel_method = (
            values["instrument_id"], values["reference_id"],
            values["reference_certificate_id"], values["unit"],
        )
        prior_method = channel_methods.setdefault(channel, channel_method)
        if prior_method != channel_method:
            raise ValueError(f"channel {channel} mixes instruments, reference standards, certificates, or units")
        calibration_methods.add((values["calibration_id"], values["pipeline_id"]))

        group_key = tuple(values[field] for field in GROUP_FIELDS)
        replicate_key = (group_key, values["replicate_id"])
        if replicate_key in seen_replicates:
            raise ValueError(f"row {row_number}: duplicate replicate_id {values['replicate_id']!r} within one point group")
        seen_replicates.add(replicate_key)
        groups[group_key].append({
            "replicate_id": values["replicate_id"],
            "reference_value": reference,
            "reference_uncertainty": uncertainty,
            "indicated_value": indicated,
        })

    if len(calibration_methods) != 1:
        raise ValueError("an analysis run must use one calibration_id and one pipeline_id")
    undersized = [key for key, rows in groups.items() if len(rows) < 2]
    if undersized:
        raise ValueError("each calibration point and timepoint needs at least two replicates")

    timepoints_by_match: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for key in groups:
        match_key = tuple(key[GROUP_FIELDS.index(field)] for field in MATCH_FIELDS)
        timepoints_by_match[match_key].add(key[GROUP_FIELDS.index("timepoint")])
    unmatched = [key for key, timepoints in timepoints_by_match.items() if timepoints != {"pre", "post"}]
    if unmatched:
        raise ValueError("each matched calibration point, direction, and rate needs both pre and post measurements")

    return groups


def load_criteria(path: Path | None, channels: set[str]) -> dict | None:
    if path is None:
        return None
    try:
        criteria = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"criteria file is not valid JSON: {exc}") from exc
    if not isinstance(criteria, dict):
        raise ValueError("criteria must be a JSON object")
    missing = {"criteria_id", "locked_before_outcome_review", "channels"} - set(criteria)
    if missing:
        raise ValueError(f"criteria file is missing: {', '.join(sorted(missing))}")
    if not str(criteria["criteria_id"]).strip():
        raise ValueError("criteria_id must be nonblank")
    if criteria["locked_before_outcome_review"] is not True:
        raise ValueError("criteria must affirm locked_before_outcome_review=true")
    if not isinstance(criteria["channels"], dict) or set(criteria["channels"]) != channels:
        raise ValueError("criteria channels must specify exactly the channels present in the input")
    for channel, limits in criteria["channels"].items():
        if not isinstance(limits, dict) or set(limits) != CRITERIA_FIELDS:
            raise ValueError(f"criteria for {channel} must define exactly: {', '.join(sorted(CRITERIA_FIELDS))}")
        for name, value in limits.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"criteria {channel}.{name} must be a finite nonnegative number")
    return criteria


def summarize(groups: dict, criteria: dict | None, input_sha256: str) -> tuple[list[dict], list[dict], dict]:
    group_records: list[dict] = []
    drift_records: list[dict] = []
    match_groups: dict[tuple[str, ...], dict[str, tuple[tuple[str, ...], list[dict]]]] = defaultdict(dict)
    channel_results: dict[str, dict] = {}

    for key, observations in sorted(groups.items()):
        metadata = dict(zip(GROUP_FIELDS, key))
        errors = [obs["indicated_value"] - obs["reference_value"] for obs in observations]
        bias = statistics.fmean(errors)
        rmse = math.sqrt(statistics.fmean(error * error for error in errors))
        repeatability_sd = statistics.stdev(errors)
        repeatability_95 = 1.96 * math.sqrt(2.0) * repeatability_sd
        max_abs_error = max(abs(error) for error in errors)
        reference_value = observations[0]["reference_value"]
        reference_uncertainty = observations[0]["reference_uncertainty"]
        channel = metadata["channel"]
        limits = criteria["channels"][channel] if criteria else None
        status = "not_assessed"
        if limits:
            status = "pass" if (
                abs(bias) <= limits["max_abs_group_bias"]
                and rmse <= limits["max_rmse"]
                and repeatability_95 <= limits["max_repeatability_coefficient_95"]
            ) else "fail"

        group_records.append({
            **metadata,
            "n_replicates": len(errors),
            "reference_value": reference_value,
            "reference_uncertainty": reference_uncertainty,
            "mean_indicated_value": statistics.fmean(obs["indicated_value"] for obs in observations),
            "mean_bias": bias,
            "max_abs_error": max_abs_error,
            "rmse": rmse,
            "repeatability_sd": repeatability_sd,
            "repeatability_coefficient_95": repeatability_95,
            "criteria_id": criteria["criteria_id"] if criteria else "",
            "status": status,
        })

        match_key = tuple(metadata[field] for field in MATCH_FIELDS)
        match_groups[match_key][metadata["timepoint"]] = (key, observations)

    for match_key, matched in sorted(match_groups.items()):
        pre_key, pre_rows = matched["pre"]
        post_key, post_rows = matched["post"]
        metadata = dict(zip(MATCH_FIELDS, match_key))
        drift = (
            statistics.fmean(row["indicated_value"] for row in post_rows)
            - statistics.fmean(row["indicated_value"] for row in pre_rows)
        )
        channel = metadata["channel"]
        max_drift = criteria["channels"][channel]["max_pre_post_drift"] if criteria else ""
        status = "not_assessed"
        if criteria:
            status = "pass" if abs(drift) <= max_drift else "fail"
        drift_records.append({
            **metadata,
            "n_pre": len(pre_rows),
            "n_post": len(post_rows),
            "mean_pre": statistics.fmean(row["indicated_value"] for row in pre_rows),
            "mean_post": statistics.fmean(row["indicated_value"] for row in post_rows),
            "pre_post_drift": drift,
            "max_allowed_drift": max_drift,
            "criteria_id": criteria["criteria_id"] if criteria else "",
            "status": status,
        })

    for channel in sorted({key[GROUP_FIELDS.index("channel")] for key in groups}):
        channel_group_records = [row for row in group_records if row["channel"] == channel]
        channel_drift_records = [row for row in drift_records if row["channel"] == channel]
        group_statuses = [row["status"] for row in channel_group_records]
        drift_statuses = [row["status"] for row in channel_drift_records]
        status = "not_assessed" if criteria is None else (
            "pass" if all(value == "pass" for value in group_statuses + drift_statuses) else "fail"
        )
        channel_results[channel] = {
            "unit": CHANNEL_UNITS[channel],
            "n_calibration_groups": len(channel_group_records),
            "n_matched_pre_post_points": len(channel_drift_records),
            "max_abs_group_bias": max(abs(row["mean_bias"]) for row in channel_group_records),
            "max_group_rmse": max(row["rmse"] for row in channel_group_records),
            "max_repeatability_coefficient_95": max(row["repeatability_coefficient_95"] for row in channel_group_records),
            "max_abs_pre_post_drift": max(abs(row["pre_post_drift"]) for row in channel_drift_records),
            "status": status,
        }

    summary = {
        "method_version": METHOD_VERSION,
        "input_sha256": input_sha256,
        "calibration_id": next(iter({key[0] for key in groups})),
        "pipeline_id": next(iter({key[5] for key in groups})),
        "criteria_id": criteria["criteria_id"] if criteria else None,
        "locked_before_outcome_review": criteria["locked_before_outcome_review"] if criteria else None,
        "overall_status": "not_assessed" if criteria is None else (
            "pass" if all(result["status"] == "pass" for result in channel_results.values()) else "fail"
        ),
        "channels": channel_results,
        "interpretation_limits": [
            "This report audits reference-based calibration points; it is not a calibration certificate or an independent accreditation.",
            "Reference uncertainty is reported but not combined with the observed errors; include it in the study uncertainty budget.",
            "The repeatability coefficient is 1.96*sqrt(2)*sample SD within each point group; it can be unstable with few replicates.",
            "Results cover only the channels, levels, directions, rates, instruments, references, and pipeline present in this file.",
            "A pass does not establish fixture compliance correction, biological validity, or suitability of any injury force.",
        ],
    }
    return group_records, drift_records, summary


def write_outputs(group_records: list[dict], drift_records: list[dict], summary: dict, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for filename, fields, records in (
        ("calibration_group_metrics.tsv", GROUP_OUTPUT_FIELDS, group_records),
        ("calibration_drift_metrics.tsv", DRIFT_OUTPUT_FIELDS, drift_records),
    ):
        with (outdir / filename).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            for record in records:
                writer.writerow({
                    field: f"{record[field]:.9g}" if isinstance(record[field], float) else record[field]
                    for field in fields
                })
    with (outdir / "calibration_summary.json").open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(summary, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="tab-separated reference and indicated calibration points")
    parser.add_argument("--outdir", required=True, type=Path, help="directory for calibration metrics and summary")
    parser.add_argument("--criteria", type=Path, help="optional criteria JSON locked before outcome review")
    args = parser.parse_args()

    try:
        groups = load_calibration_points(args.input)
        channels = {key[GROUP_FIELDS.index("channel")] for key in groups}
        criteria = load_criteria(args.criteria, channels)
        input_sha256 = hashlib.sha256(args.input.read_bytes()).hexdigest()
        group_records, drift_records, summary = summarize(groups, criteria, input_sha256)
        write_outputs(group_records, drift_records, summary, args.outdir)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"output": str(args.outdir), "groups": len(group_records), "status": summary["overall_status"]}))


if __name__ == "__main__":
    main()
