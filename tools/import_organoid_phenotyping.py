#!/usr/bin/env python3
"""Register a verified organoid-phenotyping receipt for ResearchDesk review."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STUDY_RELATIVE = Path("studies/organoid/kidney-tubuloid-cyst-induction")
MAX_ARTIFACT_BYTES = 20_000_000
MAX_BUNDLE_BYTES = 50_000_000
BONN_DATASET_ID = "10.60507/FK2/OM25XQ"
BONN_SOURCE_ARCHIVE_SHA256 = "9a71323938338558eafcb169eeb3dffae98d3b1fec7947bafa71d64768a3358b"
OUTPUTS = {
    "REPORT.md": "Human-readable package receipt and interpretation limits.",
    "measurements.csv": "Acquisition-level image-mask measurements and source hashes.",
    "objects.csv": "Per-label instance geometry from supplied masks.",
    "cross_sectional_summary.csv": "Cross-sectional object-area summaries without inferred trajectories.",
    "tracked_object_growth.csv": "Object trajectories only when a reviewed track map was supplied.",
    "segmentation_comparison.csv": "Comparison with supplied reference masks, if available.",
}


class ReceiptImportError(ValueError):
    """The package receipt or artifact bundle cannot be safely registered."""


def record_analysis_run(document: dict[str, Any], bundle_id: str, kind: str,
                       artifact_ids: list[str], status: str,
                       registered_utc: str | None = None) -> None:
    """Append an immutable run record and advance only its kind-specific pointer."""
    history = document.setdefault("analysis_history", [])
    record = {"bundle_id": bundle_id, "kind": kind,
              "registered_utc": registered_utc or datetime.now(timezone.utc).isoformat(),
              "artifact_ids": sorted(set(artifact_ids)), "status": status}
    existing = next((item for item in history if item.get("bundle_id") == bundle_id), None)
    if existing:
        if any(existing.get(key) != value for key, value in record.items()
               if key != "registered_utc"):
            raise ReceiptImportError("analysis bundle ID conflicts with a different registered run")
    else:
        history.append(record)
    document.setdefault("current_analysis_by_kind", {})[kind] = bundle_id


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReceiptImportError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptImportError(f"cannot read JSON file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReceiptImportError(f"expected a JSON object in {path}")
    return value


def _validator_module():
    path = ROOT / "tools" / "validate_experiment_manifest.py"
    spec = importlib.util.spec_from_file_location("organoid_import_manifest_validator", path)
    if spec is None or spec.loader is None:
        raise ReceiptImportError("shared experiment manifest validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safe_source_artifact(source_root: Path, relative: str, expected_hash: Any) -> tuple[Path, bytes]:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or ".." in rel.parts or len(rel.parts) != 1:
        raise ReceiptImportError(f"unsupported package output path: {relative}")
    path = (source_root / relative).resolve(strict=True)
    try:
        path.relative_to(source_root.resolve())
    except ValueError as exc:
        raise ReceiptImportError(f"package output escapes its source directory: {relative}") from exc
    if not path.is_file() or path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ReceiptImportError(f"package output is missing or exceeds the 20 MB import limit: {relative}")
    raw = path.read_bytes()
    if not isinstance(expected_hash, str) or _sha256_bytes(raw) != expected_hash.lower():
        raise ReceiptImportError(f"package receipt hash mismatch for {relative}")
    return path, raw


def register_receipt(source_output: str | Path, input_manifest: str | Path,
                     study_plan: str | Path, repo_root: str | Path = ROOT) -> dict[str, Any]:
    """Validate inputs and package outputs, then atomically add bounded Desk artifacts."""
    repo_root = Path(repo_root).resolve(strict=True)
    source_root = Path(source_output).resolve(strict=True)
    if not source_root.is_dir():
        raise ReceiptImportError("package output must be a directory")
    receipt_path = source_root / "receipt.json"
    receipt_bytes = receipt_path.read_bytes()
    receipt = _read_json(receipt_path)
    if receipt.get("schema_version") != 1 or receipt.get("tool") != "organoid-phenotyping":
        raise ReceiptImportError("receipt is not a supported organoid-phenotyping schema version")
    dataset = receipt.get("dataset")
    if (not isinstance(dataset, dict) or dataset.get("dataset_id") != BONN_DATASET_ID
            or dataset.get("license") != "CC-BY-4.0"
            or dataset.get("source_archive_sha256") != BONN_SOURCE_ARCHIVE_SHA256):
        raise ReceiptImportError("receipt does not match the pinned CC BY Bonn kidney-tubuloid archive")

    manifest_path = Path(input_manifest).resolve(strict=True)
    plan_path = Path(study_plan).resolve(strict=True)
    input_manifest_hash = _sha256_file(manifest_path)
    plan_hash = _sha256_file(plan_path)
    if receipt.get("input_manifest_sha256") != input_manifest_hash:
        raise ReceiptImportError("acquisition manifest SHA-256 does not match the package receipt")
    if receipt.get("study_plan_sha256") != plan_hash:
        raise ReceiptImportError("study-plan SHA-256 does not match the package receipt")

    counts = [receipt.get(name) for name in (
        "n_manifest_rows", "n_measured_frames", "n_pending_annotation_frames", "n_missing_frames", "n_failed_frames"
    )]
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts):
        raise ReceiptImportError("receipt frame counts must be nonnegative integers")
    if sum(counts[1:]) != counts[0]:
        raise ReceiptImportError("receipt frame-status counts do not add up to n_manifest_rows")
    split = receipt.get("split")
    if (not isinstance(split, dict) or split.get("specimen_overlap") != []
            or split.get("grouping_field") != "biological_unit_id"
            or split.get("grouping_unit") != "source kidney identifier"
            or split.get("development_group_count") != 4
            or split.get("final_test_group_count") != 1
            or receipt.get("n_biological_units") != 5):
        raise ReceiptImportError("receipt must contain a specimen-disjoint frozen split")
    output_hashes = receipt.get("outputs")
    if not isinstance(output_hashes, dict):
        raise ReceiptImportError("receipt has no output-hash index")

    copied: dict[str, bytes] = {}
    total_bytes = 0
    for filename in OUTPUTS:
        _path, raw = _safe_source_artifact(source_root, filename, output_hashes.get(filename))
        copied[filename] = raw
        total_bytes += len(raw)
    if len(receipt_bytes) > MAX_ARTIFACT_BYTES:
        raise ReceiptImportError("receipt.json exceeds the 20 MB import limit")
    total_bytes += len(receipt_bytes)
    if total_bytes > MAX_BUNDLE_BYTES:
        raise ReceiptImportError("selected package outputs exceed the 50 MB ResearchDesk bundle limit")

    bundle_hashes = {name: _sha256_bytes(raw) for name, raw in copied.items()}
    bundle_key = hashlib.sha256(json.dumps({
        "input_manifest_sha256": input_manifest_hash,
        "study_plan_sha256": plan_hash,
        "receipt_sha256": _sha256_bytes(receipt_bytes),
        "outputs": bundle_hashes,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    study_dir = (repo_root / STUDY_RELATIVE).resolve(strict=True)
    manifest_path_in_repo = study_dir / "experiment.json"
    document = _read_json(manifest_path_in_repo)
    if document.get("manifest_schema_version") != "1.4.0":
        raise ReceiptImportError("the organoid study card must use experiment-manifest schema 1.4.0")
    validator = _validator_module()
    validator.validate_experiment_manifest(manifest_path_in_repo, repo_root=repo_root)

    artifact_dir_rel = STUDY_RELATIVE / "derived" / bundle_key
    artifact_dir = repo_root / artifact_dir_rel
    artifact_dir.parent.mkdir(parents=True, exist_ok=True)
    created_bundle = False
    if artifact_dir.exists():
        for filename, raw in copied.items():
            existing = artifact_dir / filename
            if not existing.is_file() or existing.read_bytes() != raw:
                raise ReceiptImportError(f"existing derived bundle conflicts with verified receipt: {artifact_dir}")
        if (artifact_dir / "receipt.json").read_bytes() != receipt_bytes:
            raise ReceiptImportError(f"existing receipt bundle conflicts with this run: {artifact_dir}")
    else:
        stage = Path(tempfile.mkdtemp(prefix=f".{bundle_key}-", dir=artifact_dir.parent))
        try:
            for filename, raw in copied.items():
                (stage / filename).write_bytes(raw)
            (stage / "receipt.json").write_bytes(receipt_bytes)
            stage.rename(artifact_dir)
            created_bundle = True
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise

    try:
        artifact_ids = {}
        descriptions = {**OUTPUTS, "receipt.json": "Hash-bound run receipt with source, split and frame-status metadata."}
        existing = {artifact["id"]: artifact for artifact in document["artifacts"]}
        for filename, description in descriptions.items():
            artifact_id = f"phenotyping-{Path(filename).stem.replace('_', '-').lower()}-{bundle_key}"
            path = artifact_dir / filename
            raw = path.read_bytes()
            artifact_ids[filename] = artifact_id
            record = {
                "id": artifact_id,
                "kind": "analysis_output",
                "description": description,
                "repository": document["repository_id"],
                "path": (artifact_dir_rel / filename).as_posix(),
                "sha256": _sha256_bytes(raw),
                "size_bytes": len(raw),
            }
            if artifact_id in existing:
                if existing[artifact_id] != record:
                    raise ReceiptImportError("phenotyping artifact ID conflicts with a different manifest record")
            else:
                document["artifacts"].append(record)
        record_analysis_run(document, bundle_key, "organoid_phenotyping",
                            list(artifact_ids.values()), "receipt_verified",
                            receipt.get("created_utc"))
        document["modeling"]["result_artifact_id"] = artifact_ids["receipt.json"]
        assay = document["assays"][0]
        assay["status"] = "not_available"
        assay.pop("raw_artifact_id", None)
        assay["source_n"] = (
            f"{counts[0]} indexed source images; {counts[1]} image masks measured, "
            f"{counts[2]} pending annotation, {counts[3]} missing, {counts[4]} failed."
        )
        if counts[1] > 0:
            assay["notes"] = (
                f"The linked package outputs include geometry from {counts[1]} supplied masks. "
                "This record keeps the cyst-specific assay unavailable until mask semantics and "
                "the source-level measurements are reviewed; no kidney-function endpoint is measured."
            )
        else:
            assay["notes"] = (
                "The linked intake indexed the source images but measured no masks. "
                "No cyst morphology or biological outcome is claimed."
            )

        temporary_manifest = manifest_path_in_repo.with_name("experiment.import.tmp.json")
        temporary_manifest.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        try:
            validator.validate_experiment_manifest(temporary_manifest, repo_root=repo_root)
            os.replace(temporary_manifest, manifest_path_in_repo)
        finally:
            temporary_manifest.unlink(missing_ok=True)
    except BaseException:
        if created_bundle:
            shutil.rmtree(artifact_dir, ignore_errors=True)
        raise
    return {
        "experiment_id": document["experiment_id"],
        "manifest_path": manifest_path_in_repo.relative_to(repo_root).as_posix(),
        "bundle_path": artifact_dir.relative_to(repo_root).as_posix(),
        "bundle_key": bundle_key,
        "n_manifest_rows": counts[0],
        "n_measured_frames": counts[1],
        "n_pending_annotation_frames": counts[2],
        "registered_artifacts": len(artifact_ids),
        "assay_status": "not_available",
        "interpretation": "Package outputs are linked for review; importing a receipt does not validate mask semantics or create a biological claim.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="organoid-phenotyping package output directory")
    parser.add_argument("--manifest", required=True, type=Path, help="exact acquisition CSV used for the run")
    parser.add_argument("--plan", required=True, type=Path, help="exact study-plan JSON used for the run")
    parser.add_argument("--repo-root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        result = register_receipt(args.output, args.manifest, args.plan, args.repo_root)
    except (ReceiptImportError, OSError) as exc:
        print(f"Unable to register organoid analysis: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
