#!/usr/bin/env python3
"""Summarize calibrated tooth force-displacement traces without efficacy thresholds."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

METHOD_VERSION = "0.1.0"
REQUIRED_FIELDS = {
    "specimen_id", "tooth_id", "condition_code", "acquisition_id",
    "measurement_point", "load_axis_id", "cycle_id", "sample_index",
    "time_s", "phase", "force_n", "displacement_mm",
    "force_calibration_id", "displacement_calibration_id", "pipeline_id",
}
PHASE_ORDER = {"baseline": 0, "loading": 1, "unloading": 2, "recovery": 3}
GROUP_FIELDS = (
    "specimen_id", "tooth_id", "condition_code", "acquisition_id",
    "measurement_point", "load_axis_id", "cycle_id",
    "force_calibration_id", "displacement_calibration_id", "pipeline_id",
)
OUTPUT_FIELDS = (
    *GROUP_FIELDS, "n_samples", "loading_samples", "unloading_samples",
    "recovery_samples", "start_force_n", "end_force_n", "peak_force_n",
    "displacement_at_peak_force_mm", "max_abs_displacement_mm",
    "end_of_unloading_displacement_mm", "end_of_recovery_displacement_mm",
    "recovery_change_mm", "recovery_elapsed_s",
    "signed_force_displacement_integral_n_mm",
)


def parse_finite(value: str, field: str, row_number: int) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"row {row_number}: {field} must be finite")
    return result


def parse_nonnegative_int(value: str, field: str, row_number: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number}: {field} must be a nonnegative integer") from exc
    if result < 0:
        raise ValueError(f"row {row_number}: {field} must be a nonnegative integer")
    return result


def load_traces(path: Path) -> dict[tuple[str, ...], list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        missing = REQUIRED_FIELDS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"input is missing columns: {', '.join(sorted(missing))}")
        raw_rows = list(reader)

    if not raw_rows:
        raise ValueError("input contains no measurement rows")

    traces: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    seen_samples: set[tuple[tuple[str, ...], int]] = set()
    method_ids: set[tuple[str, str, str]] = set()

    for row_number, raw in enumerate(raw_rows, start=2):
        values = {field: (raw.get(field) or "").strip() for field in REQUIRED_FIELDS}
        blank = sorted(field for field, value in values.items() if value == "")
        if blank:
            raise ValueError(f"row {row_number}: required fields are blank: {', '.join(blank)}")
        if values["phase"] not in PHASE_ORDER:
            allowed = ", ".join(PHASE_ORDER)
            raise ValueError(f"row {row_number}: phase must be one of {allowed}")

        sample_index = parse_nonnegative_int(values["sample_index"], "sample_index", row_number)
        sample = {
            **{field: values[field] for field in GROUP_FIELDS},
            "sample_index": sample_index,
            "time_s": parse_finite(values["time_s"], "time_s", row_number),
            "force_n": parse_finite(values["force_n"], "force_n", row_number),
            "displacement_mm": parse_finite(values["displacement_mm"], "displacement_mm", row_number),
            "phase": values["phase"],
        }
        key = tuple(sample[field] for field in GROUP_FIELDS)
        sample_key = (key, sample_index)
        if sample_key in seen_samples:
            raise ValueError(f"row {row_number}: duplicate sample_index {sample_index} within one trace")
        seen_samples.add(sample_key)
        traces[key].append(sample)
        method_ids.add((
            values["force_calibration_id"],
            values["displacement_calibration_id"],
            values["pipeline_id"],
        ))

    if len(method_ids) != 1:
        raise ValueError("an analysis run must use one force calibration, displacement calibration, and pipeline")

    for key, samples in traces.items():
        samples.sort(key=lambda row: row["sample_index"])
        if any(b["time_s"] <= a["time_s"] for a, b in zip(samples, samples[1:])):
            raise ValueError(f"trace {key[6]!r}: time_s must strictly increase with sample_index")
        phase_values = [PHASE_ORDER[row["phase"]] for row in samples]
        if any(b < a for a, b in zip(phase_values, phase_values[1:])):
            raise ValueError(f"trace {key[6]!r}: phases must follow baseline, loading, unloading, recovery order")
        counts = {phase: sum(row["phase"] == phase for row in samples) for phase in PHASE_ORDER}
        if counts["loading"] < 2 or counts["unloading"] < 2:
            raise ValueError(f"trace {key[6]!r}: loading and unloading each need at least two samples")

    return traces


def integrate_force_displacement(samples: list[dict]) -> float:
    """Trapezoidal integral of signed force against signed displacement, in N·mm."""
    total = 0.0
    for first, second in zip(samples, samples[1:]):
        mean_force = (first["force_n"] + second["force_n"]) / 2.0
        total += mean_force * (second["displacement_mm"] - first["displacement_mm"])
    return total


def summarize_traces(traces: dict[tuple[str, ...], list[dict]], input_sha256: str) -> tuple[list[dict], dict]:
    records: list[dict] = []
    for key, samples in sorted(traces.items()):
        phases = {phase: [row for row in samples if row["phase"] == phase] for phase in PHASE_ORDER}
        peak = max(samples, key=lambda row: abs(row["force_n"]))
        unloading_end = phases["unloading"][-1]
        recovery_end = phases["recovery"][-1] if phases["recovery"] else None

        record = dict(zip(GROUP_FIELDS, key))
        record.update({
            "n_samples": len(samples),
            "loading_samples": len(phases["loading"]),
            "unloading_samples": len(phases["unloading"]),
            "recovery_samples": len(phases["recovery"]),
            "start_force_n": samples[0]["force_n"],
            "end_force_n": samples[-1]["force_n"],
            "peak_force_n": peak["force_n"],
            "displacement_at_peak_force_mm": peak["displacement_mm"],
            "max_abs_displacement_mm": max(abs(row["displacement_mm"]) for row in samples),
            "end_of_unloading_displacement_mm": unloading_end["displacement_mm"],
            "end_of_recovery_displacement_mm": recovery_end["displacement_mm"] if recovery_end else "",
            "recovery_change_mm": recovery_end["displacement_mm"] - unloading_end["displacement_mm"] if recovery_end else "",
            "recovery_elapsed_s": recovery_end["time_s"] - unloading_end["time_s"] if recovery_end else "",
            "signed_force_displacement_integral_n_mm": integrate_force_displacement(samples),
        })
        records.append(record)

    summary = {
        "method_version": METHOD_VERSION,
        "input_sha256": input_sha256,
        "trace_count": len(records),
        "biological_unit_count": len({record["specimen_id"] for record in records}),
        "unit_of_analysis": "one measured point, load axis, and cycle; cycles/teeth are nested within specimen",
        "outputs_are_descriptive_only": True,
        "biological_pass_fail": "not_assessed",
        "interpretation_limit": (
            "The signed path integral is not automatically a tissue dissipation estimate. "
            "Interpret it as a closed-cycle hysteresis measure only when the force path, "
            "sensor calibration, fixture compliance, and sign convention support that interpretation."
        ),
    }
    return records, summary


def write_outputs(records: list[dict], summary: dict, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    with (outdir / "cycle_metrics.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({
                field: f"{record[field]:.9g}" if isinstance(record[field], float) else record[field]
                for field in OUTPUT_FIELDS
            })
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="tab-separated one-row-per-sample force-displacement traces")
    parser.add_argument("--outdir", required=True, type=Path, help="directory for descriptive cycle metrics and summary")
    args = parser.parse_args()

    try:
        traces = load_traces(args.input)
        input_sha256 = hashlib.sha256(args.input.read_bytes()).hexdigest()
        records, summary = summarize_traces(traces, input_sha256)
        write_outputs(records, summary, args.outdir)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"output": str(args.outdir), "traces": len(records), "status": "descriptive_only"}))


if __name__ == "__main__":
    main()

