#!/usr/bin/env python3
"""Register a verified, label-free organoid annotation plan in ResearchDesk."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
from typing import Any

from import_organoid_phenotyping import (
    BONN_DATASET_ID,
    BONN_SOURCE_ARCHIVE_SHA256,
    MAX_ARTIFACT_BYTES,
    MAX_BUNDLE_BYTES,
    ReceiptImportError,
    STUDY_RELATIVE,
    _read_json,
    _sha256_bytes,
    _sha256_file,
    _validator_module,
    record_analysis_run,
)


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = {
    "annotation_queue_round1.csv": "Treatment-concealed first-round manual annotation tasks; images remain in the sibling annotation pack.",
    "annotation_queue_round2.csv": "Five concealed repeat tasks for independent annotation review.",
    "annotation_protocol.md": "Provisional annotation instructions and source-method limits.",
    "pilot_plan.json": "Hash-bound, development-only annotation pilot plan; no masks or biological outcomes.",
    "annotation_contact_sheet.png": "Low-resolution, treatment-concealed navigation sheet; not a measurement source.",
}
ARTIFACT_NAMES = {
    "annotation_queue_round1.csv": "queue1",
    "annotation_queue_round2.csv": "queue2",
    "annotation_protocol.md": "protocol",
    "pilot_plan.json": "plan",
    "annotation_contact_sheet.png": "contact-sheet",
}
KEY_FIELDS = {
    "task_id", "round", "frame_id", "biological_unit_id", "culture_condition", "treatment",
    "technical_replicate", "timepoint_h", "source_image_path", "source_image_sha256", "repeat_of_task_id",
}
QUEUE_FIELDS = {
    "task_id", "image_path", "image_sha256", "annotation_target", "mask_path", "status",
    "status_reason", "annotator_id", "annotation_protocol_version",
}


def _safe_file(root: Path, relative: str, *, max_bytes: int = MAX_ARTIFACT_BYTES) -> tuple[Path, bytes]:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ReceiptImportError(f"unsafe path in annotation pilot: {relative}")
    path = (root / Path(*rel.parts)).resolve(strict=True)
    try:
        path.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise ReceiptImportError(f"annotation pilot path escapes its source directory: {relative}") from exc
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise ReceiptImportError(f"annotation pilot file is missing or exceeds its size limit: {relative}")
    return path, path.read_bytes()


def _read_csv(data: bytes, label: str) -> tuple[list[str], list[dict[str, str]]]:
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
        fields = reader.fieldnames or []
        if not fields or len(fields) != len(set(fields)):
            raise ReceiptImportError(f"{label} has missing or duplicate CSV columns")
        return fields, list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ReceiptImportError(f"cannot parse {label}: {exc}") from exc


def _load_manifest_rows(path: Path) -> dict[str, dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "frame_id" not in reader.fieldnames:
                raise ReceiptImportError("acquisition manifest has no frame_id column")
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise ReceiptImportError(f"cannot read source acquisition manifest: {exc}") from exc
    result = {}
    for row in rows:
        frame_id = (row.get("frame_id") or "").strip()
        if not frame_id or frame_id in result:
            raise ReceiptImportError("source acquisition manifest frame IDs must be nonblank and unique")
        result[frame_id] = row
    return result


def _validate_task_files(public_root: Path, queues: dict[str, list[dict[str, str]]], key_rows: list[dict[str, str]],
                         acquisition_rows: dict[str, dict[str, str]], manifest_path: Path,
                         development: set[str], final_test: set[str], receipt: dict[str, Any]) -> None:
    task_by_id = {}
    task_round = {}
    for round_name, rows in queues.items():
        for row in rows:
            task_id = (row.get("task_id") or "").strip()
            if not task_id or task_id in task_by_id:
                raise ReceiptImportError("annotation task IDs must be nonblank and unique")
            task_by_id[task_id] = row
            task_round[task_id] = round_name
    key_by_id = {}
    for row in key_rows:
        task_id = (row.get("task_id") or "").strip()
        if not task_id or task_id in key_by_id:
            raise ReceiptImportError("private assignment-key task IDs must be nonblank and unique")
        key_by_id[task_id] = row
    if not task_by_id:
        raise ReceiptImportError("annotation task IDs must be nonblank and unique")
    if set(task_by_id) != set(key_by_id):
        raise ReceiptImportError("public annotation queues and private assignment key contain different tasks")
    primary_by_frame = {}
    strata = set()
    for task_id, task in task_by_id.items():
        key = key_by_id[task_id]
        if key.get("round") != task_round[task_id]:
            raise ReceiptImportError("private assignment-key round does not match its public queue")
        if any(not (key.get(field) or "").strip() for field in (
                "frame_id", "biological_unit_id", "culture_condition", "treatment",
                "timepoint_h", "source_image_path", "source_image_sha256")):
            raise ReceiptImportError("private assignment key contains a blank source identity field")
        row = acquisition_rows.get(key.get("frame_id", ""))
        if row is None:
            raise ReceiptImportError("private assignment key references an unknown source frame")
        group_id = (row.get("biological_unit_id") or "").strip()
        if group_id not in development or group_id in final_test:
            raise ReceiptImportError("final-test or non-development source group entered the annotation pilot")
        if (row.get("status") != "pending_annotation" or row.get("timepoint_h") != str(receipt["timepoint_h"])
                or key.get("biological_unit_id") != group_id
                or key.get("culture_condition") != row.get("culture_condition")
                or key.get("treatment") != row.get("treatment")
                or key.get("technical_replicate") != row.get("technical_replicate")
                or key.get("timepoint_h") != row.get("timepoint_h")
                or key.get("source_image_path") != row.get("image_path")):
            raise ReceiptImportError("private key metadata does not match its pending source acquisition")
        if task.get("status") != "pending_annotation" or task.get("mask_path") != f"masks/{task_id}.tif":
            raise ReceiptImportError("annotation tasks must remain pending and point to a future mask path")
        expected_target = "whole_tubuloid_outer_boundary" if row.get("culture_condition") == "Domes" else "visible_cyst_boundary"
        if task.get("annotation_target") != expected_target:
            raise ReceiptImportError("annotation target does not match the provisional culture-specific target")
        expected_image_path = f"images/{task_id}.tif"
        if task.get("image_path") != expected_image_path:
            raise ReceiptImportError("annotation task image path must use its opaque task ID")
        source_path, source_bytes = _safe_file(manifest_path.parent, row.get("image_path", ""), max_bytes=200_000_000)
        source_hash = _sha256_bytes(source_bytes)
        if source_hash != key.get("source_image_sha256") or task.get("image_sha256") != source_hash:
            raise ReceiptImportError("source image bytes do not match the blinded queue and assignment key")
        copied_path, copied_bytes = _safe_file(public_root, expected_image_path, max_bytes=200_000_000)
        if _sha256_bytes(copied_bytes) != source_hash:
            raise ReceiptImportError("blinded image copy differs from its exact source TIFF")
        frame_id = key["frame_id"]
        round_name = key["round"]
        if round_name == "primary":
            if frame_id in primary_by_frame:
                raise ReceiptImportError("one source frame appears more than once in the primary queue")
            primary_by_frame[frame_id] = task_id
            stratum = (group_id, row.get("culture_condition"), row.get("treatment"), row.get("timepoint_h"))
            if stratum in strata:
                raise ReceiptImportError("primary queue contains more than one frame in a frozen annotation stratum")
            strata.add(stratum)
        elif round_name != "concealed_repeat":
            raise ReceiptImportError("private assignment key contains an unknown annotation round")

    for task_id, key in key_by_id.items():
        if key.get("round") == "concealed_repeat":
            primary_task = primary_by_frame.get(key.get("frame_id", ""))
            if not primary_task or key.get("repeat_of_task_id") != primary_task or primary_task == task_id:
                raise ReceiptImportError("concealed repeat does not map to its primary task")
    if len(primary_by_frame) != receipt["n_unique_frames"]:
        raise ReceiptImportError("annotation receipt unique-frame count does not match its primary queue")
    if len({row["biological_unit_id"] for row in key_by_id.values() if row["round"] == "primary"}) != receipt["n_development_source_groups"]:
        raise ReceiptImportError("annotation receipt development-group count does not match its primary queue")


def register_annotation_pilot(source_pack: str | Path, input_manifest: str | Path,
                              study_plan: str | Path, repo_root: str | Path = ROOT) -> dict[str, Any]:
    """Verify a manual annotation pilot and register only its public review assets."""
    repo_root = Path(repo_root).resolve(strict=True)
    source_root = Path(source_pack).resolve(strict=True)
    if not source_root.is_dir():
        raise ReceiptImportError("annotation pilot package must be a directory")
    public_root = (source_root / "public").resolve(strict=True)
    curator_root = (source_root / "curator").resolve(strict=True)
    manifest_path = Path(input_manifest).resolve(strict=True)
    plan_path = Path(study_plan).resolve(strict=True)
    receipt = _read_json(curator_root / "pilot_receipt.json")
    if (receipt.get("schema_version") != 1 or receipt.get("tool") != "organoid-phenotyping"
            or receipt.get("activity") != "manual_annotation_pilot_plan"):
        raise ReceiptImportError("unsupported organoid annotation pilot receipt")
    dataset = receipt.get("dataset")
    if (not isinstance(dataset, dict) or dataset.get("dataset_id") != BONN_DATASET_ID
            or dataset.get("license") != "CC-BY-4.0"
            or dataset.get("source_archive_sha256") != BONN_SOURCE_ARCHIVE_SHA256):
        raise ReceiptImportError("annotation pilot does not match the pinned CC BY Bonn kidney-tubuloid archive")
    manifest_hash, plan_hash = _sha256_file(manifest_path), _sha256_file(plan_path)
    if receipt.get("input_manifest_sha256") != manifest_hash or receipt.get("study_plan_sha256") != plan_hash:
        raise ReceiptImportError("annotation pilot inputs do not match the exact acquisition manifest and study plan")
    plan = _read_json(plan_path)
    split = plan.get("split")
    if (not isinstance(split, dict) or split.get("frozen_before_model_fit") is not True
            or split.get("grouping_field") != "biological_unit_id"):
        raise ReceiptImportError("source study plan has no frozen source-kidney split")
    development, final_test = split.get("development_group_ids"), split.get("final_test_group_ids")
    if (not isinstance(development, list) or not isinstance(final_test, list)
            or any(not isinstance(value, str) or not value for value in development + final_test)
            or len(set(development)) != len(development) or len(set(final_test)) != len(final_test)
            or set(development) & set(final_test)
            or sorted(final_test) != receipt.get("excluded_final_test_group_ids")
            or receipt.get("selected_final_test_overlap") != []):
        raise ReceiptImportError("annotation pilot must preserve the frozen final-test source group")
    if (receipt.get("masks_generated") is not False or receipt.get("biological_results_generated") is not False
            or receipt.get("n_total_tasks") != receipt.get("n_round1_tasks", -1) + receipt.get("n_round2_concealed_repeat_tasks", -1)
            or receipt.get("n_round1_tasks") != receipt.get("n_unique_frames")):
        raise ReceiptImportError("annotation pilot receipt must describe a label-free plan with consistent task counts")
    for count_name in ("n_unique_frames", "n_round1_tasks", "n_round2_concealed_repeat_tasks",
                       "n_total_tasks", "n_development_source_groups"):
        value = receipt.get(count_name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ReceiptImportError(f"annotation pilot receipt has an invalid {count_name}")

    output_hashes = receipt.get("outputs")
    if not isinstance(output_hashes, dict) or set(output_hashes) != set(PUBLIC_FILES):
        raise ReceiptImportError("annotation pilot has an unexpected public output index")
    copied: dict[str, bytes] = {}
    total_bytes = 0
    for filename in PUBLIC_FILES:
        _path, raw = _safe_file(public_root, filename)
        if _sha256_bytes(raw) != output_hashes.get(filename):
            raise ReceiptImportError(f"annotation pilot output hash mismatch for {filename}")
        copied[filename] = raw
        total_bytes += len(raw)
    if total_bytes > MAX_BUNDLE_BYTES:
        raise ReceiptImportError("annotation pilot public outputs exceed the ResearchDesk bundle limit")
    contact_sheet = copied["annotation_contact_sheet.png"]
    if not contact_sheet.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ReceiptImportError("annotation contact sheet is not a PNG image")

    pilot_plan = _read_json(public_root / "pilot_plan.json")
    selection = pilot_plan.get("selection")
    if (pilot_plan.get("dataset_id") != BONN_DATASET_ID
            or pilot_plan.get("license") != "CC-BY-4.0"
            or pilot_plan.get("source_archive_sha256") != BONN_SOURCE_ARCHIVE_SHA256
            or pilot_plan.get("acquisition_manifest_sha256") != manifest_hash
            or pilot_plan.get("study_plan_sha256") != plan_hash
            or pilot_plan.get("masks_generated") is not False
            or pilot_plan.get("biological_results_generated") is not False
            or not isinstance(selection, dict)
            or selection.get("timepoint_h") != receipt.get("timepoint_h")
            or selection.get("n_unique_frames") != receipt.get("n_unique_frames")
            or selection.get("n_round1_tasks") != receipt.get("n_round1_tasks")
            or selection.get("n_round2_concealed_repeat_tasks") != receipt.get("n_round2_concealed_repeat_tasks")
            or selection.get("n_total_tasks") != receipt.get("n_total_tasks")
            or selection.get("n_development_source_groups_represented") != receipt.get("n_development_source_groups")
            or selection.get("final_test_group_excluded") is not True):
        raise ReceiptImportError("public annotation pilot plan does not match its verified receipt")

    key_rel = receipt.get("private_assignment_key_path")
    if key_rel != "curator/assignment_key.csv":
        raise ReceiptImportError("annotation pilot private key path is unsupported")
    _key_path, key_bytes = _safe_file(source_root, key_rel)
    if _sha256_bytes(key_bytes) != receipt.get("private_assignment_key_sha256"):
        raise ReceiptImportError("private assignment-key hash mismatch")
    key_fields, key_rows = _read_csv(key_bytes, "private assignment key")
    if not KEY_FIELDS.issubset(key_fields):
        raise ReceiptImportError("private assignment key is missing required columns")
    queues = {}
    for filename, round_name in (("annotation_queue_round1.csv", "primary"),
                                 ("annotation_queue_round2.csv", "concealed_repeat")):
        fields, rows = _read_csv(copied[filename], filename)
        if set(fields) != QUEUE_FIELDS:
            raise ReceiptImportError(f"{filename} must contain exactly the approved blinded annotation fields")
        if any(row.get("round") not in {None, ""} for row in rows):
            raise ReceiptImportError(f"{filename} cannot expose repeat mapping")
        queues[round_name] = rows
    if len(queues["primary"]) != receipt["n_round1_tasks"] or len(queues["concealed_repeat"]) != receipt["n_round2_concealed_repeat_tasks"]:
        raise ReceiptImportError("annotation queue row counts do not match the signed receipt")
    acquisition_rows = _load_manifest_rows(manifest_path)
    _validate_task_files(public_root, queues, key_rows, acquisition_rows, manifest_path,
                         set(development), set(final_test), receipt)

    bundle_hash = hashlib.sha256(json.dumps({
        "input_manifest_sha256": manifest_hash,
        "study_plan_sha256": plan_hash,
        "private_assignment_key_sha256": receipt["private_assignment_key_sha256"],
        "outputs": output_hashes,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    study_dir = (repo_root / STUDY_RELATIVE).resolve(strict=True)
    manifest_in_repo = study_dir / "experiment.json"
    document = _read_json(manifest_in_repo)
    if document.get("manifest_schema_version") != "1.4.0":
        raise ReceiptImportError("the organoid study card must use experiment-manifest schema 1.4.0")
    validator = _validator_module()
    validator.validate_experiment_manifest(manifest_in_repo, repo_root=repo_root)

    bundle_rel = STUDY_RELATIVE / "derived" / f"annotation-pilot-{bundle_hash}"
    bundle_dir = repo_root / bundle_rel
    bundle_dir.parent.mkdir(parents=True, exist_ok=True)
    created_bundle = False
    if bundle_dir.exists():
        for name, raw in copied.items():
            path = bundle_dir / name
            if not path.is_file() or path.read_bytes() != raw:
                raise ReceiptImportError("existing annotation pilot bundle conflicts with the verified output")
    else:
        stage = Path(tempfile.mkdtemp(prefix=f".{bundle_hash}-", dir=bundle_dir.parent))
        try:
            for name, raw in copied.items():
                (stage / name).write_bytes(raw)
            stage.rename(bundle_dir)
            created_bundle = True
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise

    artifact_ids = {}
    try:
        existing = {artifact["id"]: artifact for artifact in document["artifacts"]}
        for filename, description in PUBLIC_FILES.items():
            artifact_id = f"organoid-pilot-{ARTIFACT_NAMES[filename]}-{bundle_hash}"
            path = bundle_dir / filename
            raw = path.read_bytes()
            record = {
                "id": artifact_id,
                "kind": "analysis_output",
                "description": description,
                "repository": document["repository_id"],
                "path": (bundle_rel / filename).as_posix(),
                "sha256": _sha256_bytes(raw),
                "size_bytes": len(raw),
            }
            if artifact_id in existing:
                if existing[artifact_id] != record:
                    raise ReceiptImportError("annotation pilot artifact ID conflicts with a different manifest record")
            else:
                document["artifacts"].append(record)
            artifact_ids[filename] = artifact_id
        record_analysis_run(document, bundle_hash, "annotation_pilot",
                            list(artifact_ids.values()), "plan_only")
        temporary_manifest = manifest_in_repo.with_name("experiment.annotation-pilot.tmp.json")
        temporary_manifest.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        try:
            validator.validate_experiment_manifest(temporary_manifest, repo_root=repo_root)
            os.replace(temporary_manifest, manifest_in_repo)
        finally:
            temporary_manifest.unlink(missing_ok=True)
    except BaseException:
        if created_bundle:
            shutil.rmtree(bundle_dir, ignore_errors=True)
        raise
    return {
        "experiment_id": document["experiment_id"],
        "bundle_path": bundle_dir.relative_to(repo_root).as_posix(),
        "registered_artifacts": len(artifact_ids),
        "n_unique_frames": receipt["n_unique_frames"],
        "n_total_tasks": receipt["n_total_tasks"],
        "private_assignment_key_imported": False,
        "masks_generated": False,
        "assay_status": document["assays"][0].get("status", "measured"),
        "interpretation": "ResearchDesk exposes the public annotation plan and navigation sheet; source images and the private unblinding key remain in the sibling annotation pack.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="organoid annotation pilot directory")
    parser.add_argument("--manifest", required=True, type=Path, help="exact acquisition CSV used for the pilot")
    parser.add_argument("--plan", required=True, type=Path, help="exact frozen study plan used for the pilot")
    parser.add_argument("--repo-root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        result = register_annotation_pilot(args.output, args.manifest, args.plan, args.repo_root)
    except (ReceiptImportError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"Unable to register annotation pilot: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
