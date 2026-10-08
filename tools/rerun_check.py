#!/usr/bin/env python3
"""Rerun one allowlisted analysis and compare its output with a stored receipt.

This is the "reproduction" step that dossier verification deliberately does not perform. A
verified archive shows intact bytes; it does not show that the analysis can be run again and
gives the same numbers. This tool tries that for one narrow, named case and reports what
happened, nothing more.

What it will and will not run:

* The only runnable entry point is ``regenbench-regress/1``: ``regenbench regress`` from a local
  checkout of the regen-benchmark-kit repository, at a commit named in the spec. The program that
  runs is a constant in this file. No command, path to run, or argument is read from a dossier,
  a receipt or any other data; the spec supplies only values that are checked against fixed
  patterns (a group column, a target column, a seed) and file hashes.
* The producing source is taken with ``git archive`` at the named commit and unpacked into a
  fresh temporary directory, so the checkout's working tree and index are never touched and
  uncommitted changes cannot leak into the rerun.
* The child runs with ``python -I -B``, an empty environment apart from fixed variables, no
  network use of its own, and a timeout.
* The input table and the stored receipt are read once through the bounded collector and must
  match their declared SHA-256 before anything runs.

Statuses (``rerun.status``):

* ``reproduced_exact``: every field except ``environment`` is identical.
* ``reproduced_within_tolerance``: the same structure, with numeric differences no larger than
  the stated tolerance. Different numpy / scikit-learn builds routinely differ in the last digits.
* ``not_reproduced``: a field differs by more than the tolerance, or the structure differs.
* ``could_not_run``: a hash, the commit, the run itself or the time limit failed. This says
  nothing about whether the analysis reproduces.

A reproduced number is not a reviewed result, not a validated method and not a statement about
biology. The report records both environments so a reader can see what differed.

Usage:
    python tools/rerun_check.py <spec.json> --out <new report.json>

Standard library only for the harness itself; the rerun needs the producer's own dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_collector as ac  # noqa: E402

SCHEMA_VERSION = 1
ENTRY_POINT = "regenbench-regress/1"
ALLOWED_ENTRY_POINTS = (ENTRY_POINT,)
REL_TOLERANCE = 1e-9
ABS_TOLERANCE = 1e-12
TIMEOUT_SECONDS = 600
MAX_SOURCE_ARCHIVE_BYTES = 50_000_000
MAX_SOURCE_MEMBERS = 5_000
MAX_INPUT_BYTES = 20_000_000
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
COLUMN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
GROUP_LIST = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}(,[A-Za-z_][A-Za-z0-9_]{0,63}){0,3}")

# Fixed program text. Arguments arrive through argv as data and are never interpolated.
_RUNNER = (
    "import sys\n"
    "source, csv_path, group_by, target, seed, out = sys.argv[1:7]\n"
    "sys.path.insert(0, source)\n"
    "from regenbench.cli import main\n"
    "raise SystemExit(main(['regress', csv_path, '--group-by', group_by, '--target', target,"
    " '--seed', seed, '--out', out]))\n"
)
_CHILD_ENV = {"PYTHONHASHSEED": "0", "LC_ALL": "C", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}

LIMITS = [
    "A reproduced number shows that this code and this input give this output again. It is not "
    "scientific review, not a validated method and not a statement about biology.",
    "Only the named entry point can run. Nothing in a dossier, receipt or spec chooses a program.",
    "Search runs, network-dependent steps and anything outside the allowlist are not attempted.",
    "Floating-point results can differ in the last digits between numpy / scikit-learn builds; "
    "the tolerance is stated and the two environments are recorded.",
]


class RerunError(Exception):
    """The rerun could not be attempted. Carries a reason a reader can act on."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _strict_json(raw: bytes, label: str):
    def reject(constant):
        raise RerunError(f"{label} contains the non-JSON constant {constant}")

    def unique(pairs):
        keys = [key for key, _ in pairs]
        if len(keys) != len(set(keys)):
            raise RerunError(f"{label} has a repeated object key")
        return dict(pairs)

    try:
        return json.loads(raw.decode("utf-8"), parse_constant=reject, object_pairs_hook=unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RerunError(f"{label} is not readable JSON") from exc


def validate_spec(spec) -> dict:
    """Check the spec's shape and every value that could reach the child process."""
    if not isinstance(spec, dict) or set(spec) != {"schema_version", "entry_point", "producer", "input",
                                                     "receipt", "arguments"}:
        raise RerunError("spec needs exactly: schema_version, entry_point, producer, input, receipt, arguments")
    if spec["schema_version"] != SCHEMA_VERSION:
        raise RerunError("spec schema_version must be 1")
    if spec["entry_point"] not in ALLOWED_ENTRY_POINTS:
        raise RerunError(f"entry_point {spec['entry_point']!r} is not on the allowlist {list(ALLOWED_ENTRY_POINTS)}")
    producer, source, receipt, arguments = spec["producer"], spec["input"], spec["receipt"], spec["arguments"]
    if not isinstance(producer, dict) or set(producer) != {"repository", "commit"}:
        raise RerunError("producer needs exactly: repository, commit")
    if not isinstance(producer["repository"], str) or not producer["repository"]:
        raise RerunError("producer.repository must be a local path")
    if not isinstance(producer["commit"], str) or not COMMIT.fullmatch(producer["commit"]):
        raise RerunError("producer.commit must be a full 40-character lowercase commit id")
    for name, item in (("input", source), ("receipt", receipt)):
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise RerunError(f"{name} needs exactly: path, sha256")
        if not isinstance(item["path"], str) or not item["path"]:
            raise RerunError(f"{name}.path must be a non-empty string")
        if not isinstance(item["sha256"], str) or not SHA256.fullmatch(item["sha256"]):
            raise RerunError(f"{name}.sha256 must be 64 lowercase hex characters")
    if not isinstance(arguments, dict) or set(arguments) != {"group_by", "target", "seed"}:
        raise RerunError("arguments needs exactly: group_by, target, seed")
    if not isinstance(arguments["group_by"], str) or not GROUP_LIST.fullmatch(arguments["group_by"]):
        raise RerunError("arguments.group_by must be 1-4 comma-separated column names")
    if not isinstance(arguments["target"], str) or not COLUMN.fullmatch(arguments["target"]):
        raise RerunError("arguments.target must be a column name")
    if isinstance(arguments["seed"], bool) or not isinstance(arguments["seed"], int) or not 0 <= arguments["seed"] < 2**31:
        raise RerunError("arguments.seed must be an integer from 0 to 2**31 - 1")
    return spec


def _read_declared(base: Path, item: dict, label: str) -> bytes:
    path = Path(item["path"])
    root = base if not path.is_absolute() else path.parent
    relative = path.as_posix() if not path.is_absolute() else path.name
    try:
        raw = ac.read_regular_file(root, relative, limit=MAX_INPUT_BYTES)
    except ac.CollectionError as exc:
        raise RerunError(f"{label} could not be read safely: {exc}") from exc
    if _sha256(raw) != item["sha256"]:
        raise RerunError(f"{label} does not match its declared SHA-256")
    return raw


def _git(repository: Path, *args: str, limit: int = 1_000_000) -> bytes:
    try:
        completed = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(repository), *args],
                                   capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RerunError(f"git could not be run: {type(exc).__name__}") from exc
    if completed.returncode != 0:
        raise RerunError(f"git {args[0]} failed for the producer repository")
    if len(completed.stdout) > MAX_SOURCE_ARCHIVE_BYTES:
        raise RerunError("the producer source archive is larger than the limit")
    return completed.stdout


def extract_source(repository: Path, commit: str, destination: Path) -> int:
    """Unpack the producer's source at ``commit`` into ``destination`` without touching its checkout."""
    if _git(repository, "cat-file", "-t", commit).strip() != b"commit":
        raise RerunError("producer.commit is not a commit in the producer repository")
    raw = _git(repository, "archive", "--format=tar", commit)
    count = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive:
            count += 1
            if count > MAX_SOURCE_MEMBERS:
                raise RerunError("the producer source has too many entries")
            if ac.member_name_problem(member.name) is not None and member.name != ".":
                raise RerunError("the producer source contains an unsafe entry name")
            if member.isdir():
                (destination / member.name).mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target = destination / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
            # Links and special files are skipped, never followed.
    return count


def compare(expected, observed, tolerance_rel=REL_TOLERANCE, tolerance_abs=ABS_TOLERANCE) -> dict:
    """Walk two JSON values. Structure and non-numeric values must be identical."""
    state = {"compared_numbers": 0, "inexact_numbers": 0, "max_abs_deviation": 0.0,
             "max_rel_deviation": 0.0, "structural": [], "beyond_tolerance": []}

    def walk(left, right, path):
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                if key not in left or key not in right:
                    state["structural"].append(f"{path}{key}: present in only one document")
                else:
                    walk(left[key], right[key], f"{path}{key}.")
        elif isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                state["structural"].append(f"{path.rstrip('.')}: list lengths {len(left)} and {len(right)}")
                return
            for index, (a, b) in enumerate(zip(left, right)):
                walk(a, b, f"{path}{index}.")
        elif (isinstance(left, (int, float)) and not isinstance(left, bool)
              and isinstance(right, (int, float)) and not isinstance(right, bool)):
            state["compared_numbers"] += 1
            if left == right:
                return
            state["inexact_numbers"] += 1
            if not (math.isfinite(left) and math.isfinite(right)):
                state["beyond_tolerance"].append(path.rstrip("."))
                return
            absolute = abs(left - right)
            relative = absolute / max(abs(left), abs(right))
            state["max_abs_deviation"] = max(state["max_abs_deviation"], absolute)
            state["max_rel_deviation"] = max(state["max_rel_deviation"], relative)
            if absolute > tolerance_abs and relative > tolerance_rel:
                state["beyond_tolerance"].append(path.rstrip("."))
        elif left != right:
            state["structural"].append(f"{path.rstrip('.')}: values or types differ")

    walk(expected, observed, "")
    return state


def classify(comparison: dict) -> str:
    if comparison["structural"] or comparison["beyond_tolerance"]:
        return "not_reproduced"
    return "reproduced_within_tolerance" if comparison["inexact_numbers"] else "reproduced_exact"


def run_spec(spec_path, *, now=None) -> dict:
    spec_path = Path(spec_path)
    base = spec_path.resolve().parent
    started = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    report = {
        "schema_version": SCHEMA_VERSION, "tool": "tools/rerun_check.py", "generated_utc": started,
        "entry_point": None, "rerun": {"status": "could_not_run", "reason": None},
        "limits": LIMITS,
    }
    try:
        spec = validate_spec(_strict_json(ac.read_regular_file(base, spec_path.name, limit=1_000_000), "spec"))
        report["entry_point"] = spec["entry_point"]
        report["spec_sha256"] = _sha256(spec_path.read_bytes())
        report["producer"] = dict(spec["producer"], repository=Path(spec["producer"]["repository"]).name)
        report["arguments"] = spec["arguments"]
        table = _read_declared(base, spec["input"], "input table")
        stored_raw = _read_declared(base, spec["receipt"], "stored receipt")
        report["input_sha256"], report["receipt_sha256"] = spec["input"]["sha256"], spec["receipt"]["sha256"]
        stored = _strict_json(stored_raw, "stored receipt")
        if not isinstance(stored, dict) or stored.get("dataset_sha256") != spec["input"]["sha256"]:
            raise RerunError("the stored receipt does not name the declared input table as its dataset")
        repository = Path(spec["producer"]["repository"])
        if not repository.is_absolute():
            repository = (base / repository).resolve()
        with tempfile.TemporaryDirectory(prefix="rerun-check-") as temporary:
            work = Path(temporary)
            (work / "source").mkdir()
            extract_source(repository, spec["producer"]["commit"], work / "source")
            (work / "input.csv").write_bytes(table)
            arguments = spec["arguments"]
            try:
                child = subprocess.run(
                    [sys.executable, "-I", "-B", "-c", _RUNNER, str(work / "source" / "src"),
                     str(work / "input.csv"), arguments["group_by"], arguments["target"],
                     str(arguments["seed"]), str(work / "out")],
                    capture_output=True, timeout=TIMEOUT_SECONDS, cwd=work, env=dict(_CHILD_ENV), check=False)
            except subprocess.TimeoutExpired as exc:
                raise RerunError(f"the rerun exceeded {TIMEOUT_SECONDS} seconds") from exc
            if child.returncode != 0:
                tail = child.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["no error text"]
                raise RerunError(f"the rerun exited with status {child.returncode}: {tail[0][:300]}")
            observed = _strict_json(ac.read_regular_file(work / "out", "metrics.json", limit=MAX_INPUT_BYTES),
                                    "rerun metrics")
        report["environments"] = {"stored": stored.get("environment"), "rerun": observed.get("environment")}
        expected = {key: value for key, value in stored.items() if key != "environment"}
        actual = {key: value for key, value in observed.items() if key != "environment"}
        comparison = compare(expected, actual)
        report["rerun"] = {
            "status": classify(comparison),
            "reason": None,
            "tolerance": {"relative": REL_TOLERANCE, "absolute": ABS_TOLERANCE},
            "compared_numbers": comparison["compared_numbers"],
            "inexact_numbers": comparison["inexact_numbers"],
            "max_abs_deviation": comparison["max_abs_deviation"],
            "max_rel_deviation": comparison["max_rel_deviation"],
            "structural_differences": comparison["structural"][:20],
            "beyond_tolerance": comparison["beyond_tolerance"][:20],
            "rerun_metrics_sha256_without_environment": _sha256(_canonical(actual).encode("utf-8")),
            "stored_metrics_sha256_without_environment": _sha256(_canonical(expected).encode("utf-8")),
        }
    except (RerunError, ac.CollectionError) as exc:
        report["rerun"] = {"status": "could_not_run", "reason": str(exc)}
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Rerun one allowlisted analysis and compare with its stored receipt")
    parser.add_argument("spec")
    parser.add_argument("--out", required=True, help="new report file; never overwritten")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        print("refusing to overwrite an existing report", file=sys.stderr)
        return 2
    report = run_spec(args.spec)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(f"{report['rerun']['status']}: {report['rerun'].get('reason') or ''}".rstrip(": "))
    return 0 if report["rerun"]["status"].startswith("reproduced") else 1


if __name__ == "__main__":
    raise SystemExit(main())
