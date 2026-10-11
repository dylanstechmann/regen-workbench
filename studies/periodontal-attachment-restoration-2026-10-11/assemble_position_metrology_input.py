#!/usr/bin/env python3
"""Join finalized blind pose measurements to the restricted known-pose key."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


POSE_AXES = ("tx_mm", "ty_mm", "tz_mm", "rx_deg", "ry_deg", "rz_deg")
KEY_FIELDS = (
    "run_code", "fixture_id", "repeat_group_id", "replicate_id", "session_id",
    "within_session_order", "operator_id", "modality", "pipeline_id",
    *(f"truth_{axis}" for axis in POSE_AXES), "randomization_seed",
)
MEASUREMENT_FIELDS = ("run_code", *(f"measured_{axis}" for axis in POSE_AXES))
OUTPUT_FIELDS = (
    "run_code", "session_id", "within_session_order", "operator_id", "fixture_id",
    "repeat_group_id", "replicate_id", "modality", "pipeline_id",
    *(f"truth_{axis}" for axis in POSE_AXES),
    *(f"measured_{axis}" for axis in POSE_AXES), "randomization_seed",
)


def parse_finite(value: str | None, field: str, line_number: int) -> str:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"line {line_number}: {field} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"line {line_number}: {field} must be finite")
    return f"{number:.12g}"


def load_tsv(
    path: Path,
    required: tuple[str, ...],
    description: str,
    forbidden: set[str] | None = None,
    forbidden_prefixes: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)):
            raise ValueError(f"{description} contains duplicate column names")
        missing = set(required) - set(fields)
        if missing:
            raise ValueError(f"{description} is missing columns: {', '.join(sorted(missing))}")
        disallowed = sorted(
            field for field in fields
            if field in (forbidden or set()) or any(field.startswith(prefix) for prefix in forbidden_prefixes)
        )
        if disallowed:
            raise ValueError(f"{description} contains key or unblinding columns: {', '.join(disallowed)}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{description} contains no rows")
    return rows


def load_analysis_key(path: Path) -> list[dict[str, str]]:
    rows = load_tsv(path, KEY_FIELDS, "analysis key")
    seen_codes: set[str] = set()
    truth_by_group: dict[tuple[str, str], tuple[str, ...]] = {}
    method_pairs: set[tuple[str, str]] = set()
    for line_number, row in enumerate(rows, start=2):
        code = (row.get("run_code") or "").strip()
        identifiers = [(row.get(field) or "").strip() for field in KEY_FIELDS[:9]]
        if not code or not all(identifiers):
            raise ValueError(f"analysis key line {line_number}: run and acquisition identifiers must be nonblank")
        if code in seen_codes:
            raise ValueError(f"analysis key line {line_number}: duplicate run_code {code!r}")
        seen_codes.add(code)
        for axis in POSE_AXES:
            row[f"truth_{axis}"] = parse_finite(row.get(f"truth_{axis}"), f"truth_{axis}", line_number)
        grouping = (row["fixture_id"].strip(), row["repeat_group_id"].strip())
        truth = tuple(row[f"truth_{axis}"] for axis in POSE_AXES)
        prior_truth = truth_by_group.setdefault(grouping, truth)
        if truth != prior_truth:
            raise ValueError(f"analysis key line {line_number}: truth pose changes within repeat group {grouping[1]!r}")
        method_pairs.add((row["modality"].strip(), row["pipeline_id"].strip()))
    if len(method_pairs) != 1:
        raise ValueError("analysis key must contain one modality and one pipeline; assemble methods separately")
    return rows


def load_measurements(path: Path) -> dict[str, dict[str, str]]:
    rows = load_tsv(
        path,
        MEASUREMENT_FIELDS,
        "blind measurements",
        forbidden=(set(KEY_FIELDS) - {"run_code"}) | {"pose_condition_id"},
        forbidden_prefixes=("truth_",),
    )
    measurements: dict[str, dict[str, str]] = {}
    for line_number, row in enumerate(rows, start=2):
        code = (row.get("run_code") or "").strip()
        if not code:
            raise ValueError(f"blind measurements line {line_number}: run_code is required")
        if code in measurements:
            raise ValueError(f"blind measurements line {line_number}: duplicate run_code {code!r}")
        measurements[code] = {
            f"measured_{axis}": parse_finite(row.get(f"measured_{axis}"), f"measured_{axis}", line_number)
            for axis in POSE_AXES
        }
    return measurements


def assemble(key_rows: list[dict[str, str]], measurements: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    key_codes = {row["run_code"].strip() for row in key_rows}
    measured_codes = set(measurements)
    missing = sorted(key_codes - measured_codes)
    unknown = sorted(measured_codes - key_codes)
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing measurements for {len(missing)} scheduled run(s): {', '.join(missing[:5])}")
        if unknown:
            details.append(f"unknown run_code(s): {', '.join(unknown[:5])}")
        raise ValueError("run-code sets do not match; " + "; ".join(details))

    output = []
    for key_row in key_rows:
        code = key_row["run_code"].strip()
        output.append({
            **{field: key_row[field].strip() for field in KEY_FIELDS},
            **measurements[code],
        })
    return output


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_outputs(
    output_path: Path,
    rows: list[dict[str, str]],
    key_path: Path,
    measurements_path: Path,
    receipt_path: Path | None,
    force: bool,
) -> None:
    targets = [output_path, *( [receipt_path] if receipt_path is not None else [])]
    resolved_targets = [path.resolve() for path in targets]
    if len(set(resolved_targets)) != len(resolved_targets):
        raise ValueError("analysis input and receipt must be different files")
    protected = {key_path.resolve(), measurements_path.resolve()}
    if any(path in protected for path in resolved_targets):
        raise ValueError("output files must not overwrite the analysis key or blind measurements")
    existing = [path for path in targets if path.exists()]
    if existing and not force:
        raise FileExistsError(f"output file already exists: {existing[0]}; pass --force to overwrite")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_suffix(output_path.suffix + ".tmp")
    with temp_output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    temp_receipt = None
    if receipt_path is not None:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_data = {
            "schema_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "analysis_input": str(output_path),
            "analysis_input_sha256": sha256(temp_output),
            "analysis_key_sha256": sha256(key_path),
            "blind_measurements_sha256": sha256(measurements_path),
            "n_acquisitions": len(rows),
            "claim_limit": "This receipt records file hashes; it does not prove when measurements were finalized or who had access to the key.",
        }
        temp_receipt = receipt_path.with_suffix(receipt_path.suffix + ".tmp")
        temp_receipt.write_text(json.dumps(receipt_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    temp_output.replace(output_path)
    if receipt_path is not None and temp_receipt is not None:
        temp_receipt.replace(receipt_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-key", required=True, type=Path, help="restricted key from make_pose_acquisition_manifest.py")
    parser.add_argument("--measurements", required=True, type=Path, help="finalized operator measurements keyed only by run_code")
    parser.add_argument("--out", required=True, type=Path, help="joined TSV accepted by analyze_position_metrology.py")
    parser.add_argument("--receipt", type=Path, help="optional JSON with SHA-256 hashes and row count")
    parser.add_argument("--force", action="store_true", help="overwrite existing output files")
    args = parser.parse_args(argv)
    try:
        if args.analysis_key.resolve() == args.measurements.resolve():
            raise ValueError("analysis key and blind measurements must be different files")
        key_rows = load_analysis_key(args.analysis_key)
        measurements = load_measurements(args.measurements)
        rows = assemble(key_rows, measurements)
        write_outputs(args.out, rows, args.analysis_key, args.measurements, args.receipt, args.force)
    except (OSError, ValueError, json.JSONDecodeError, FileExistsError) as exc:
        parser.error(str(exc))
    print(f"Assembled {len(rows)} measurements; output: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
