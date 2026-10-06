#!/usr/bin/env python3
"""Register a receipt-verified manual-mask agreement audit in ResearchDesk."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import io
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any

from import_organoid_phenotyping import (
    BONN_DATASET_ID, BONN_SOURCE_ARCHIVE_SHA256, ReceiptImportError, STUDY_RELATIVE,
    _read_json, _sha256_bytes, _validator_module, record_analysis_run,
)


ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 5_000_000
MAX_TOTAL_BYTES = 10_000_000
PUBLIC_FILES = {
    "audit_report.json": "Blinded manual polygon-mask workflow and concealed-repeat agreement audit; no biological result.",
    "repeat_agreement.csv": "Foreground Dice across concealed repeat annotations with annotator-independence flags.",
}


def _read_csv(raw: bytes) -> tuple[list[str], list[dict[str, str]]]:
    import csv
    try:
        with io.StringIO(raw.decode("utf-8-sig"), newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise ReceiptImportError(f"cannot read repeat-agreement table: {exc}") from exc
    if not fields or len(fields) != len(set(fields)):
        raise ReceiptImportError("repeat-agreement table has missing or duplicate columns")
    return fields, rows


def _read_bounded(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ReceiptImportError("annotation audit file is missing or unsafe")
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ReceiptImportError("annotation audit file exceeds 5 MB")
    return raw


def _receipt_from_bytes(raw: bytes) -> dict[str, Any]:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReceiptImportError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        receipt = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptImportError("annotation audit receipt is not valid UTF-8 JSON") from exc
    if not isinstance(receipt, dict):
        raise ReceiptImportError("annotation audit receipt must be a JSON object")
    return receipt


def register_annotation_review(audit_directory: str | Path, repo_root: str | Path = ROOT) -> dict[str, Any]:
    """Verify an annotation audit receipt and append its artifacts to the study record."""
    repo_root = Path(repo_root).resolve(strict=True)
    if Path(audit_directory).is_symlink():
        raise ReceiptImportError("annotation audit must be a regular directory")
    source_root = Path(audit_directory).resolve(strict=True)
    if not source_root.is_dir() or source_root.is_symlink():
        raise ReceiptImportError("annotation audit must be a regular directory")
    receipt_path = source_root / "audit_receipt.json"
    receipt_bytes = _read_bounded(receipt_path)
    receipt = _receipt_from_bytes(receipt_bytes)
    if (receipt.get("schema_version") != 1 or receipt.get("tool") != "organoid-phenotyping"
            or receipt.get("activity") != "manual_annotation_repeat_audit"
            or receipt.get("biological_results_generated") is not False):
        raise ReceiptImportError("unsupported or biologically scoped annotation-audit receipt")
    audit_id = receipt.get("audit_id")
    if not isinstance(audit_id, str) or not re.fullmatch(r"[0-9a-f]{16}", audit_id):
        raise ReceiptImportError("annotation audit has an invalid run ID")
    outputs = receipt.get("outputs")
    if not isinstance(outputs, dict) or set(outputs) != set(PUBLIC_FILES):
        raise ReceiptImportError("annotation audit output index is incomplete or unexpected")
    copied = {"audit_receipt.json": receipt_bytes}
    total = len(receipt_bytes)
    for filename in PUBLIC_FILES:
        path = source_root / filename
        if path.is_symlink() or not path.is_file() or path.resolve(strict=True).parent != source_root:
            raise ReceiptImportError(f"annotation audit output is missing or unsafe: {filename}")
        raw = _read_bounded(path)
        record = outputs[filename]
        if (len(raw) > MAX_FILE_BYTES or not isinstance(record, dict)
                or record.get("sha256") != _sha256_bytes(raw)
                or record.get("size_bytes") != len(raw)):
            raise ReceiptImportError(f"annotation audit output failed its receipt hash: {filename}")
        copied[filename] = raw
        total += len(raw)
    if total > MAX_TOTAL_BYTES:
        raise ReceiptImportError("selected annotation audit outputs exceed 10 MB")
    if (receipt.get("pilot_receipt_sha256") is None
            or not re.fullmatch(r"[0-9a-f]{64}", str(receipt["pilot_receipt_sha256"]))
            or not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("input_manifest_sha256", "")))
            or not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("study_plan_sha256", "")))):
        raise ReceiptImportError("annotation audit receipt is missing its input bindings")
    masks = receipt.get("annotation_mask_sha256")
    n_annotated = receipt.get("n_annotated_tasks")
    n_repeat_pairs = receipt.get("n_repeat_pairs_scored")
    n_independent_pairs = receipt.get("n_repeat_pairs_with_distinct_annotator_ids")
    if (isinstance(n_annotated, bool) or not isinstance(n_annotated, int) or not 0 <= n_annotated <= 100_000
            or isinstance(n_repeat_pairs, bool) or not isinstance(n_repeat_pairs, int) or not 0 <= n_repeat_pairs <= 100_000
            or isinstance(n_independent_pairs, bool) or not isinstance(n_independent_pairs, int)
            or not 0 <= n_independent_pairs <= n_repeat_pairs
            or isinstance(receipt.get("n_total_tasks"), bool)
            or not isinstance(receipt.get("n_total_tasks"), int)
            or not n_annotated <= receipt["n_total_tasks"] <= 100_000
            or not isinstance(masks, dict) or len(masks) != n_annotated
            or any(not isinstance(task_id, str) or not re.fullmatch(r"b-[0-9a-f]{16}", task_id)
                   or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                   for task_id, digest in masks.items())):
        raise ReceiptImportError("annotation audit receipt has invalid per-task mask hashes")

    try:
        report = json.loads(copied["audit_report.json"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptImportError("annotation report is not valid UTF-8 JSON") from exc
    dataset = report.get("dataset") if isinstance(report, dict) else None
    if (not isinstance(report, dict) or report.get("schema_version") != 1
            or report.get("activity") != "manual_annotation_repeat_audit"
            or report.get("audit_id") != audit_id
            or report.get("session_id") != receipt.get("session_id")
            or report.get("biological_results_generated") is not False
            or isinstance(report.get("n_annotated_tasks"), bool)
            or not isinstance(report.get("n_annotated_tasks"), int)
            or report.get("n_annotated_tasks") != n_annotated
            or isinstance(report.get("n_repeat_pairs_scored"), bool)
            or not isinstance(report.get("n_repeat_pairs_scored"), int)
            or report.get("n_repeat_pairs_scored") != n_repeat_pairs
            or isinstance(report.get("n_repeat_pairs_with_distinct_annotator_ids"), bool)
            or not isinstance(report.get("n_repeat_pairs_with_distinct_annotator_ids"), int)
            or report.get("n_repeat_pairs_with_distinct_annotator_ids") != n_independent_pairs
            or not isinstance(report.get("repeat_agreement"), list)
            or any(not isinstance(item, dict) for item in report["repeat_agreement"])
            or not isinstance(dataset, dict)
            or dataset.get("dataset_id") != BONN_DATASET_ID
            or dataset.get("license") != "CC-BY-4.0"
            or dataset.get("source_archive_sha256") != BONN_SOURCE_ARCHIVE_SHA256):
        raise ReceiptImportError("manual annotation report does not match the pinned source or receipt")
    fields, repeat_rows = _read_csv(copied["repeat_agreement.csv"])
    required_columns = {"primary_task_id", "repeat_task_id", "different_annotator_ids", "foreground_dice"}
    if not required_columns.issubset(fields) or len(repeat_rows) != len(report["repeat_agreement"]):
        raise ReceiptImportError("repeat-agreement table differs from its report summary")
    if len(repeat_rows) != n_repeat_pairs:
        raise ReceiptImportError("repeat-agreement row count differs from the audit receipt")
    independent_rows = sum((row.get("different_annotator_ids") or "").strip().lower() == "true"
                           for row in repeat_rows)
    if (independent_rows != n_independent_pairs
            or report.get("n_repeat_pairs_with_distinct_annotator_ids") != independent_rows):
        raise ReceiptImportError("independent-review count differs from the report and agreement table")
    reported_pairs = report["repeat_agreement"]
    for row, reported in zip(repeat_rows, reported_pairs):
        primary_id = row.get("primary_task_id") or ""
        repeat_id = row.get("repeat_task_id") or ""
        independence = (row.get("different_annotator_ids") or "").strip().lower()
        try:
            dice = float(row.get("foreground_dice", ""))
        except ValueError as exc:
            raise ReceiptImportError("repeat-agreement table contains an invalid Dice value") from exc
        if (primary_id not in masks or repeat_id not in masks or primary_id == repeat_id
                or independence not in {"true", "false"} or not math.isfinite(dice) or not 0 <= dice <= 1):
            raise ReceiptImportError("repeat-agreement table has invalid task IDs, independence, or Dice values")
        if (reported.get("primary_task_id") != row.get("primary_task_id")
                or reported.get("repeat_task_id") != row.get("repeat_task_id")
                or str(reported.get("different_annotator_ids", "")).lower() != row.get("different_annotator_ids", "").lower()
                or isinstance(reported.get("foreground_dice"), bool)
                or not isinstance(reported.get("foreground_dice"), (float, int))
                or not math.isclose(reported["foreground_dice"], dice, rel_tol=1e-12, abs_tol=0)):
            raise ReceiptImportError("repeat-agreement table differs from its report rows")

    study_dir = (repo_root / STUDY_RELATIVE).resolve(strict=True)
    manifest_path = study_dir / "experiment.json"
    document = _read_json(manifest_path)
    if document.get("manifest_schema_version") != "1.4.0":
        raise ReceiptImportError("the organoid study card must use experiment-manifest schema 1.4.0")
    validator = _validator_module()
    validator.validate_experiment_manifest(manifest_path, repo_root=repo_root)
    bundle_rel = STUDY_RELATIVE / "derived" / f"annotation-review-{audit_id}"
    bundle_dir = repo_root / bundle_rel
    bundle_dir.parent.mkdir(parents=True, exist_ok=True)
    created = False
    if bundle_dir.exists():
        if bundle_dir.is_symlink() or not bundle_dir.is_dir():
            raise ReceiptImportError("existing annotation audit bundle is unsafe")
        for name, raw in copied.items():
            path = bundle_dir / name
            if path.is_symlink() or not path.is_file() or _read_bounded(path) != raw:
                raise ReceiptImportError("existing annotation audit bundle conflicts with its verified receipt")
    else:
        stage = Path(tempfile.mkdtemp(prefix=f".annotation-review-{audit_id}-", dir=bundle_dir.parent))
        try:
            for name, raw in copied.items():
                (stage / name).write_bytes(raw)
            stage.rename(bundle_dir)
            created = True
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
    artifact_ids = []
    try:
        existing = {item["id"]: item for item in document["artifacts"]}
        descriptions = {**PUBLIC_FILES, "audit_receipt.json": "Input/output hash receipt for the local annotation agreement audit."}
        for filename, description in descriptions.items():
            artifact_id = f"organoid-review-{Path(filename).stem.replace('_', '-')}-{audit_id}"
            path = bundle_dir / filename
            raw = path.read_bytes()
            record = {"id": artifact_id, "kind": "analysis_output", "description": description,
                      "repository": document["repository_id"], "path": (bundle_rel / filename).as_posix(),
                      "sha256": _sha256_bytes(raw), "size_bytes": len(raw)}
            if artifact_id in existing:
                if existing[artifact_id] != record:
                    raise ReceiptImportError("annotation review artifact ID conflicts with another manifest entry")
            else:
                document["artifacts"].append(record)
            artifact_ids.append(artifact_id)
        record_analysis_run(document, audit_id, "annotation_review", artifact_ids,
                            "receipt_verified", report.get("created_utc"))
        temporary = manifest_path.with_name("experiment.annotation-review.tmp.json")
        temporary.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        try:
            validator.validate_experiment_manifest(temporary, repo_root=repo_root)
            os.replace(temporary, manifest_path)
        finally:
            temporary.unlink(missing_ok=True)
    except BaseException:
        if created:
            shutil.rmtree(bundle_dir, ignore_errors=True)
        raise
    return {"experiment_id": document["experiment_id"], "bundle_path": bundle_dir.relative_to(repo_root).as_posix(),
            "registered_artifacts": len(artifact_ids), "n_annotated_tasks": report["n_annotated_tasks"],
            "n_repeat_pairs_scored": report["n_repeat_pairs_scored"],
            "n_repeat_pairs_with_distinct_annotator_ids": report["n_repeat_pairs_with_distinct_annotator_ids"],
            "biological_results_generated": False,
            "annotated_manifest_imported": False,
            "interpretation": "The verified artifacts report manual segmentation agreement only; no biological outcome or treatment effect is imported."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True, type=Path, help="annotation session audit directory")
    parser.add_argument("--repo-root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        result = register_annotation_review(args.audit, args.repo_root)
    except (ReceiptImportError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"Unable to register annotation review: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
