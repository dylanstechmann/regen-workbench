#!/usr/bin/env python3
"""Validate an experiment manifest, its artifact links, and local file hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import jsonschema
except ImportError:  # pragma: no cover - guarded by the runtime check below
    jsonschema = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = Path(__file__).resolve().parent / "schemas" / "experiment-manifest.schema.json"


class ManifestValidationError(ValueError):
    """Raised when a manifest or a linked local artifact is invalid."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_bytes(repo_root: Path, local_repository_id: str, artifact: dict[str, Any]) -> bytes | None:
    if artifact.get("repository") != local_repository_id:
        return None
    rel = PurePosixPath(artifact["path"])
    if rel.is_absolute() or ".." in rel.parts:
        raise ManifestValidationError(f"artifact path must stay inside the repository: {artifact['path']}")
    path = (repo_root / Path(*rel.parts)).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ManifestValidationError(f"artifact path resolves outside the repository: {artifact['path']}") from exc
    if not path.is_file():
        raise ManifestValidationError(f"linked local artifact does not exist: {artifact['path']}")
    if "member_path" not in artifact:
        return path.read_bytes()
    member = PurePosixPath(artifact["member_path"])
    if member.is_absolute() or ".." in member.parts:
        raise ManifestValidationError(f"archive member path is invalid: {artifact['member_path']}")
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.read(member.as_posix())
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ManifestValidationError(
            f"archive member is missing or unreadable: {artifact['path']}!/{artifact['member_path']}"
        ) from exc


def _referenced_artifact_ids(document: dict[str, Any]) -> list[tuple[str, str]]:
    refs = [("protocol.source_artifact_id", document["protocol"]["source_artifact_id"])]
    for i, assay in enumerate(document["assays"]):
        if "raw_artifact_id" in assay:
            refs.append((f"assays[{i}].raw_artifact_id", assay["raw_artifact_id"]))
    modeling = document["modeling"]
    refs.append(("modeling.source_model.artifact_id", modeling["source_model"]["artifact_id"]))
    donor_validation = modeling["donor_validation"]
    for name in ("heldout_result_artifact_id", "success_criterion_artifact_id"):
        if name in donor_validation:
            refs.append((f"modeling.donor_validation.{name}", donor_validation[name]))
    if "result_artifact_id" in modeling:
        refs.append(("modeling.result_artifact_id", modeling["result_artifact_id"]))
    calibration = document["calibration"]
    for name in ("record_artifact_id", "related_tool_artifact_id"):
        if name in calibration:
            refs.append((f"calibration.{name}", calibration[name]))
    for i, condition in enumerate(calibration.get("reported_conditions", [])):
        refs.append((f"calibration.reported_conditions[{i}].source_artifact_id", condition["source_artifact_id"]))
    for i, condition in enumerate(document.get("environmental_conditions", [])):
        refs.append((f"environmental_conditions[{i}].source_artifact_id", condition["source_artifact_id"]))
    for i, endpoint in enumerate(document.get("validation_endpoints", [])):
        if "artifact_id" in endpoint:
            refs.append((f"validation_endpoints[{i}].artifact_id", endpoint["artifact_id"]))
    context = document.get("developmental_context")
    if context:
        refs.append(("developmental_context.source_artifact_id", context["source_artifact_id"]))
    for i, run in enumerate(document.get("analysis_history", [])):
        for artifact_id in run.get("artifact_ids", []):
            refs.append((f"analysis_history[{i}].artifact_ids", artifact_id))
    return refs


def validate_experiment_manifest(
    manifest_path: Path,
    repo_root: Path = ROOT,
    schema_path: Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    if jsonschema is None:  # pragma: no cover - guarded by the test skip
        raise SystemExit("jsonschema is required to validate experiment manifests")
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestValidationError(str(exc)) from exc
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = sorted(
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        rendered = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            rendered.append(f"{location}: {error.message}")
        raise ManifestValidationError("schema validation failed:\n- " + "\n- ".join(rendered))

    artifacts = document["artifacts"]
    by_id: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        artifact_id = artifact["id"]
        if artifact_id in by_id:
            raise ManifestValidationError(f"duplicate artifact id: {artifact_id}")
        by_id[artifact_id] = artifact

    assays_by_id: dict[str, dict[str, Any]] = {}
    for assay in document["assays"]:
        assay_id = assay["assay_id"]
        if assay_id in assays_by_id:
            raise ManifestValidationError(f"duplicate assay id: {assay_id}")
        assays_by_id[assay_id] = assay

    for location, artifact_id in _referenced_artifact_ids(document):
        if artifact_id not in by_id:
            raise ManifestValidationError(f"{location} references unknown artifact id: {artifact_id}")

    analysis_history = document.get("analysis_history", [])
    runs_by_bundle: dict[str, dict[str, Any]] = {}
    for index, run in enumerate(analysis_history):
        bundle_id = run["bundle_id"]
        if bundle_id in runs_by_bundle:
            raise ManifestValidationError(f"analysis_history contains duplicate bundle_id: {bundle_id}")
        runs_by_bundle[bundle_id] = run
        expected_status = {"annotation_pilot": "plan_only",
                           "organoid_phenotyping": "receipt_verified"}.get(run["kind"])
        if expected_status is not None and run["status"] != expected_status:
            raise ManifestValidationError(
                f"analysis_history[{index}] kind {run['kind']} must have status {expected_status}"
            )
        for artifact_id in run["artifact_ids"]:
            if by_id[artifact_id]["kind"] != "analysis_output":
                raise ManifestValidationError(
                    f"analysis_history[{index}] references non-output artifact: {artifact_id}"
                )

    for kind, bundle_id in document.get("current_analysis_by_kind", {}).items():
        run = runs_by_bundle.get(bundle_id)
        if run is None or run["kind"] != kind:
            raise ManifestValidationError(
                f"current_analysis_by_kind.{kind} must point to an analysis-history bundle of the same kind"
            )
    if document.get("manifest_schema_version") == "1.4.0":
        for run in analysis_history:
            if run["bundle_id"] not in document.get("current_analysis_by_kind", {}).values():
                continue
            if run["kind"] == "organoid_phenotyping" and document["modeling"].get("result_artifact_id") not in run["artifact_ids"]:
                raise ManifestValidationError("current organoid phenotyping run must contain modeling.result_artifact_id")

    for index, assay in enumerate(document["assays"]):
        status = assay.get("status", "measured")
        raw_artifact_id = assay.get("raw_artifact_id")
        if status == "measured":
            if raw_artifact_id is None:
                raise ManifestValidationError(f"assays[{index}] is measured without a linked data artifact")
            if by_id[raw_artifact_id]["kind"] not in {"raw_assay_data", "source_dataset"}:
                raise ManifestValidationError(
                    f"assays[{index}] measured status cannot cite {by_id[raw_artifact_id]['kind']} evidence"
                )

    allowed_environmental_evidence = {
        "measured": {"raw_assay_data", "source_dataset", "calibration_record"},
        "reported": {"publication", "source_dataset", "author_analysis"},
        "simulated": {"analysis_code", "analysis_output"},
        "assumed": {"analysis_specification", "analysis_code"},
        "not_available": {"publication", "source_dataset", "analysis_output", "analysis_specification"},
    }
    for index, condition in enumerate(document.get("environmental_conditions", [])):
        artifact = by_id[condition["source_artifact_id"]]
        allowed = allowed_environmental_evidence[condition["status"]]
        if artifact["kind"] not in allowed:
            raise ManifestValidationError(
                f"environmental_conditions[{index}] status {condition['status']} "
                f"cannot cite {artifact['kind']} evidence"
            )

    validation_endpoints = document.get("validation_endpoints")
    if validation_endpoints is not None:
        required_roles = {
            "functional", "cell_identity", "viability", "genome_stability", "adverse_effects", "durability"
        }
        reported_roles = {endpoint["role"] for endpoint in validation_endpoints}
        missing_roles = sorted(required_roles - reported_roles)
        if missing_roles:
            raise ManifestValidationError(
                "validation_endpoints must report each core domain; missing: " + ", ".join(missing_roles)
            )
        for index, endpoint in enumerate(validation_endpoints):
            assay_id = endpoint.get("assay_id")
            artifact_id = endpoint.get("artifact_id")
            if assay_id is not None and assay_id not in assays_by_id:
                raise ManifestValidationError(
                    f"validation_endpoints[{index}].assay_id references unknown assay id: {assay_id}"
                )
            if endpoint["status"] == "measured":
                if assay_id is None and artifact_id is None:
                    raise ManifestValidationError(
                        f"validation_endpoints[{index}] is marked measured without an assay or evidence artifact"
                    )
                allowed_kinds = {"raw_assay_data", "source_dataset", "author_analysis", "analysis_output"}
                evidence_artifact_ids = [artifact_id] if artifact_id is not None else []
                if assay_id is not None:
                    if assays_by_id[assay_id].get("status", "measured") != "measured":
                        raise ManifestValidationError(
                            f"validation_endpoints[{index}] cannot cite an assay that is not measured"
                        )
                    evidence_artifact_ids.append(assays_by_id[assay_id]["raw_artifact_id"])
                for evidence_artifact_id in evidence_artifact_ids:
                    evidence_kind = by_id[evidence_artifact_id]["kind"]
                    if evidence_kind not in allowed_kinds:
                        raise ManifestValidationError(
                            f"validation_endpoints[{index}] links {evidence_kind}, not an assay-data artifact"
                        )

    for artifact in artifacts:
        data = _artifact_bytes(repo_root, document["repository_id"], artifact)
        if data is None:
            continue
        actual_hash = _sha256(data)
        if actual_hash.lower() != artifact["sha256"].lower():
            raise ManifestValidationError(
                f"SHA-256 mismatch for {artifact['id']}: expected {artifact['sha256']}, got {actual_hash}"
            )
        if len(data) != artifact["size_bytes"]:
            raise ManifestValidationError(
                f"byte-count mismatch for {artifact['id']}: expected {artifact['size_bytes']}, got {len(data)}"
            )

    modeling = document["modeling"]
    donor_validation = modeling["donor_validation"]
    if donor_validation["status"] == "passed":
        donors = document["design"]["donor_structure"]
        if donors["disease_donor_count"] < donor_validation["minimum_independent_donors"]:
            raise ManifestValidationError("donor validation is marked passed below its minimum donor count")
        if not donors["observation_level_ids_available"]:
            raise ManifestValidationError("donor validation cannot pass without observation-level donor IDs")
        result_id = donor_validation["heldout_result_artifact_id"]
        criterion_id = donor_validation["success_criterion_artifact_id"]
        if by_id[result_id]["kind"] != "analysis_output":
            raise ManifestValidationError("passed donor validation must link a held-out analysis_output artifact")
        if by_id[criterion_id]["kind"] != "analysis_specification":
            raise ManifestValidationError("passed donor validation must link a prespecified analysis_specification artifact")

    calibration = document["calibration"]
    if calibration["status"] == "measured":
        record_id = calibration.get("record_artifact_id")
        if not record_id or by_id[record_id]["kind"] != "calibration_record":
            raise ManifestValidationError("measured calibration must link a calibration_record artifact")

    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="path to experiment.json")
    parser.add_argument("--repo-root", type=Path, default=ROOT, help="repository root for local artifact paths")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="JSON Schema file")
    args = parser.parse_args(argv)
    try:
        document = validate_experiment_manifest(args.manifest, args.repo_root, args.schema)
    except ManifestValidationError as exc:
        print(f"Invalid experiment manifest: {exc}", file=sys.stderr)
        return 1
    print(
        f"Valid experiment manifest: {document['experiment_id']} "
        f"(donor validation: {document['modeling']['donor_validation']['status']}; "
        f"calibration: {document['calibration']['status']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
