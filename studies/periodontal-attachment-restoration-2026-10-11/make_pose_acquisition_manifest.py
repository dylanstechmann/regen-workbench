#!/usr/bin/env python3
"""Create a blinded, balanced acquisition schedule for known-pose scans."""

from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path


POSE_AXES = ("tx_mm", "ty_mm", "tz_mm", "rx_deg", "ry_deg", "rz_deg")
REQUIRED = {"pose_condition_id", "fixture_id", *(f"truth_{axis}" for axis in POSE_AXES)}
SCHEDULE_FIELDS = [
    "run_code", "session_id", "within_session_order", "operator_id", "modality", "pipeline_id",
]
KEY_FIELDS = [
    "run_code", "fixture_id", "repeat_group_id", "replicate_id", "session_id",
    "within_session_order", "operator_id", "modality", "pipeline_id",
    *(f"truth_{axis}" for axis in POSE_AXES), "randomization_seed",
]


def load_conditions(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"conditions file is missing: {', '.join(sorted(missing))}")
        raw_rows = list(reader)
    if not raw_rows:
        raise ValueError("conditions file contains no poses")

    conditions = []
    seen = set()
    for line_number, raw in enumerate(raw_rows, start=2):
        pose_id = (raw.get("pose_condition_id") or "").strip()
        fixture_id = (raw.get("fixture_id") or "").strip()
        if not pose_id or not fixture_id:
            raise ValueError(f"line {line_number}: pose_condition_id and fixture_id are required")
        if pose_id in seen:
            raise ValueError(f"line {line_number}: duplicate pose_condition_id {pose_id!r}")
        seen.add(pose_id)
        row = {"pose_condition_id": pose_id, "fixture_id": fixture_id}
        for axis in POSE_AXES:
            field = f"truth_{axis}"
            try:
                value = float(raw[field])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"line {line_number}: {field} must be numeric") from exc
            if not math.isfinite(value):
                raise ValueError(f"line {line_number}: {field} must be finite")
            row[field] = f"{value:.12g}"
        conditions.append(row)
    return sorted(conditions, key=lambda row: row["pose_condition_id"])


def build_manifest(
    conditions: list[dict[str, str]],
    sessions: int,
    repeats_per_pose_per_session: int,
    seed: int,
    operator_id: str,
    modality: str,
    pipeline_id: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if sessions < 1 or repeats_per_pose_per_session < 1:
        raise ValueError("sessions and repeats_per_pose_per_session must both be positive integers")
    if seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if not all(value.strip() for value in (operator_id, modality, pipeline_id)):
        raise ValueError("operator_id, modality, and pipeline_id must be nonblank")
    if not conditions:
        raise ValueError("at least one pose condition is required")

    rng = random.Random(seed)
    schedule, key = [], []
    used_codes = set()
    for session_number in range(1, sessions + 1):
        assignments = [
            (condition, repeat_number)
            for condition in conditions
            for repeat_number in range(1, repeats_per_pose_per_session + 1)
        ]
        rng.shuffle(assignments)
        for order, (condition, repeat_number) in enumerate(assignments, start=1):
            code = f"RUN-{rng.getrandbits(32):08X}"
            while code in used_codes:
                code = f"RUN-{rng.getrandbits(32):08X}"
            used_codes.add(code)
            session_id = f"S{session_number:02d}"
            schedule.append({
                "run_code": code,
                "session_id": session_id,
                "within_session_order": str(order),
                "operator_id": operator_id,
                "modality": modality,
                "pipeline_id": pipeline_id,
            })
            key.append({
                "run_code": code,
                "fixture_id": condition["fixture_id"],
                "repeat_group_id": condition["pose_condition_id"],
                "replicate_id": code,
                "session_id": session_id,
                "within_session_order": str(order),
                "operator_id": operator_id,
                "modality": modality,
                "pipeline_id": pipeline_id,
                **{f"truth_{axis}": condition[f"truth_{axis}"] for axis in POSE_AXES},
                "randomization_seed": str(seed),
            })
    return schedule, key


def write_tsv(path: Path, rows: list[dict[str, str]], fields: list[str], force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"output file already exists: {path}; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temp_path.replace(path)


def validate_separate_key(schedule_path: Path, key_path: Path) -> None:
    schedule_dir = schedule_path.parent.resolve()
    resolved_key = key_path.resolve()
    if resolved_key == schedule_path.resolve():
        raise ValueError("operator schedule and analysis key must be different files")
    try:
        resolved_key.relative_to(schedule_dir)
    except ValueError:
        return
    raise ValueError("analysis key must be outside the operator schedule directory to support separate access")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conditions", required=True, type=Path, help="TSV of investigator-defined known fixture poses")
    parser.add_argument("--schedule-out", required=True, type=Path, help="operator-facing schedule path")
    parser.add_argument("--key-out", required=True, type=Path, help="restricted analysis-key path outside the schedule directory")
    parser.add_argument("--sessions", required=True, type=int, help="number of acquisition sessions, chosen by the study design")
    parser.add_argument("--repeats-per-pose-per-session", required=True, type=int, help="independent acquisitions per pose in each session")
    parser.add_argument("--seed", required=True, type=int, help="recorded randomization seed; keep with the restricted key")
    parser.add_argument("--operator-id", required=True, help="coded acquisition operator identifier")
    parser.add_argument("--modality", required=True, help="single imaging modality for this run")
    parser.add_argument("--pipeline-id", required=True, help="single reconstruction/registration pipeline identifier")
    parser.add_argument("--force", action="store_true", help="overwrite existing output files")
    args = parser.parse_args(argv)
    try:
        validate_separate_key(args.schedule_out, args.key_out)
        conditions = load_conditions(args.conditions)
        schedule, key = build_manifest(
            conditions, args.sessions, args.repeats_per_pose_per_session, args.seed,
            args.operator_id, args.modality, args.pipeline_id,
        )
        if not args.force and (args.schedule_out.exists() or args.key_out.exists()):
            existing = args.schedule_out if args.schedule_out.exists() else args.key_out
            raise FileExistsError(f"output file already exists: {existing}; pass --force to overwrite")
        write_tsv(args.schedule_out, schedule, SCHEDULE_FIELDS, args.force)
        write_tsv(args.key_out, key, KEY_FIELDS, args.force)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(
        f"Created {len(schedule)} blinded run codes across {args.sessions} sessions and "
        f"{len(conditions)} investigator-defined pose conditions. Keep the analysis key restricted."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
