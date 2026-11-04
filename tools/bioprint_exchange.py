"""Bioprinting Workbench <-> ResearchDesk exchange adapter (Phase F/G).

File-based, provenance-preserving import/export for the local ResearchDesk. Mirrors the
Workbench contract in docs/RESEARCH_EXCHANGE.md (schema bioprinting-workbench/research-exchange/1).
Personal hobby/learning project, AI-assisted. Import never calls Desk.submit() and never
launches subprocesses or providers; hashes attest byte integrity only, review status is
software metadata, and imported bundles stay publication-not-approved. Cross-language digests
of records are guaranteed identical to the JS side only for portable-number fixtures; artifact
integrity always hashes exact producer bytes.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

SCHEMA = "bioprinting-workbench/research-exchange/1"
MAX_BUNDLE_BYTES = 5 * 1024 * 1024
MAX_ARTIFACT_BYTES = 10 * 1024 * 1024
MAX_TOTAL_ARTIFACT_BYTES = 25 * 1024 * 1024
MAX_NESTING = 20
FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
ISO_INSTANT_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d{1,3})?Z$")


def _iso_instant(value, path):
    # Strict UTC instant, identical to the JavaScript validator: YYYY-MM-DDTHH:MM:SS[.sss]Z
    # with a real calendar date. Offset forms and loose date strings are rejected on both sides.
    if not isinstance(value, str) or not ISO_INSTANT_RE.match(value):
        raise TypeError(f"{path} must be an ISO instant")
    try:
        datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TypeError(f"{path} must be an ISO instant") from exc
    return value


def utc_instant():
    """Produce a strict UTC instant (matching ISO_INSTANT_RE) for exchange-generated fields."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
MEDIA_TYPES = {"application/json", "text/csv", "text/markdown", "image/png"}
DANGEROUS = ("__proto__", "prototype", "constructor")
RUN_STATUSES = {"succeeded", "out-of-domain", "numerical-failure", "cancelled", "failed",
                "unsupported-foreign", "queued", "running", "partial", "interrupted", "submission-unknown"}


def canonical_json_bytes(value) -> bytes:
    """sorted-key compact JSON + one trailing LF; matches the JS side for portable values."""
    _reject_dangerous(value)
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def _reject_dangerous(value, depth=0):
    if depth > MAX_NESTING:
        raise ValueError(f"Bundle JSON nesting exceeds {MAX_NESTING}")
    if isinstance(value, dict):
        for key, item in value.items():
            if key in DANGEROUS:
                raise ValueError(f"{key} is forbidden")
            _reject_dangerous(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _reject_dangerous(item, depth + 1)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _plain(value, path):
    if not isinstance(value, dict):
        raise TypeError(f"{path} must be an object")
    for key in value:
        if key in DANGEROUS:
            raise TypeError(f"{path}.{key} is forbidden")
    return value


def _text(value, maximum, path):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise TypeError(f"{path} must be nonempty text (max {maximum})")
    return value


def _id_list(value, maximum, path):
    if not isinstance(value, list) or len(value) > maximum:
        raise TypeError(f"{path} must be an array (max {maximum})")
    for item in value:
        if not isinstance(item, str) or not ID_RE.match(item):
            raise TypeError(f"{path} entries must be ids")
    return list(value)
def validate_hypothesis_card(raw, path="hypothesis"):
    _plain(raw, path)
    allowed = {"id", "revision", "title", "question", "scope", "claimBoundary", "status", "system",
               "mechanism", "alternatives", "predictions", "falsifiers", "confounders",
               "missingMeasurements", "modelIds", "supportingEvidenceIds", "contradictingEvidenceIds",
               "queryPlanIds", "parentHypothesisIds", "authorship", "reviewStatus"}
    for key in raw:
        if key not in allowed:
            raise TypeError(f"{path}.{key} is unsupported")
    card = {
        "id": _text(raw.get("id"), 64, f"{path}.id"),
        "revision": raw.get("revision"),
        "title": _text(raw.get("title"), 300, f"{path}.title"),
        "question": _text(raw.get("question"), 3000, f"{path}.question"),
        "scope": _text(raw.get("scope"), 3000, f"{path}.scope"),
        "claimBoundary": _text(raw.get("claimBoundary"), 3000, f"{path}.claimBoundary"),
        "status": raw.get("status"),
        "system": _text(raw.get("system"), 500, f"{path}.system"),
        "mechanism": _text(raw.get("mechanism"), 3000, f"{path}.mechanism"),
    }
    if not ID_RE.match(card["id"]):
        raise TypeError(f"{path}.id must be a lower-case id")
    if not isinstance(card["revision"], int) or isinstance(card["revision"], bool) or card["revision"] < 1:
        raise ValueError(f"{path}.revision must be a positive integer")
    if card["status"] not in {"draft", "ready-for-review", "archived"}:
        raise ValueError(f"{path}.status unsupported")
    alternatives = raw.get("alternatives")
    if not isinstance(alternatives, list) or not 2 <= len(alternatives) <= 8:
        raise ValueError("2-8 competing alternatives are required")
    card["alternatives"] = []
    for index, alt in enumerate(alternatives):
        _plain(alt, f"{path}.alternatives[{index}]")
        for key in alt:
            if key not in {"id", "prediction", "falsifier"}:
                raise TypeError(f"{path}.alternatives[{index}].{key} is unsupported")
        card["alternatives"].append({
            "id": _text(alt.get("id"), 64, f"{path}.alternatives[{index}].id"),
            "prediction": _text(alt.get("prediction"), 500, f"{path}.alternatives[{index}].prediction"),
            "falsifier": _text(alt.get("falsifier"), 500, f"{path}.alternatives[{index}].falsifier"),
        })
    for field, maximum in (("predictions", 500), ("falsifiers", 500), ("confounders", 500),
                           ("missingMeasurements", 500), ("modelIds", 64), ("supportingEvidenceIds", 64),
                           ("contradictingEvidenceIds", 64), ("queryPlanIds", 64), ("parentHypothesisIds", 64)):
        values = raw.get(field)
        if not isinstance(values, list) or len(values) > 30:
            raise TypeError(f"{path}.{field} must be an array (max 30)")
        card[field] = [_text(item, maximum, f"{path}.{field}[]") for item in values]
    if card["status"] == "ready-for-review" and (not card["predictions"] or not card["falsifiers"]):
        raise ValueError("ready-for-review cards need predictions and falsifiers")
    review = raw.get("reviewStatus")
    if review not in {"unreviewed", "owner-reviewed"}:
        raise ValueError("reviewStatus unsupported")
    card["reviewStatus"] = review
    authorship = _plain(raw.get("authorship"), f"{path}.authorship")
    for key in authorship:
        if key not in {"createdBy", "method", "reviewedBy"}:
            raise TypeError(f"{path}.authorship.{key} is unsupported")
    if authorship.get("createdBy") not in {"owner", "agent", "import"}:
        raise ValueError("authorship.createdBy unsupported")
    card["authorship"] = {
        "createdBy": authorship["createdBy"],
        "method": _text(authorship.get("method"), 500, f"{path}.authorship.method"),
        "reviewedBy": None if authorship.get("reviewedBy") is None else _text(authorship.get("reviewedBy"), 200, f"{path}.authorship.reviewedBy"),
    }
    return card
def validate_artifact_descriptor(raw, path="artifact"):
    _plain(raw, path)
    for key in raw:
        if key not in {"id", "filename", "mediaType", "bytes", "sha256", "provenance"}:
            raise TypeError(f"{path}.{key} is unsupported")
    filename = raw.get("filename")
    if not isinstance(filename, str) or not FILENAME_RE.match(filename) or ".." in filename:
        raise TypeError(f"{path}.filename must be a flat safe basename")
    if raw.get("mediaType") not in MEDIA_TYPES:
        raise ValueError(f"{path}.mediaType unsupported")
    size = raw.get("bytes")
    if not isinstance(size, int) or isinstance(size, bool) or not 0 <= size <= MAX_ARTIFACT_BYTES:
        raise ValueError(f"{path}.bytes out of range")
    digest = raw.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise TypeError(f"{path}.sha256 must be lowercase hex")
    provenance = _plain(raw.get("provenance"), f"{path}.provenance")
    return {
        "id": _text(raw.get("id"), 64, f"{path}.id"), "filename": filename, "mediaType": raw["mediaType"],
        "bytes": size, "sha256": digest,
        "provenance": {
            "modelRunIds": _id_list(provenance.get("modelRunIds", []), 50, f"{path}.provenance.modelRunIds"),
            "evidenceIds": _id_list(provenance.get("evidenceIds", []), 50, f"{path}.provenance.evidenceIds"),
            "producer": _text(provenance.get("producer", "unknown producer"), 200, f"{path}.provenance.producer"),
        },
    }


def validate_query_plan(raw, path="query"):
    _plain(raw, path)
    for key in raw:
        if key not in {"id", "hypothesisId", "query", "providerIds", "limit", "purpose", "disclosure", "executionStatus"}:
            raise TypeError(f"{path}.{key} is unsupported")
    limit = raw.get("limit")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10:
        raise ValueError(f"{path}.limit out of range")
    if raw.get("executionStatus") not in {"planned", "not-supported"}:
        raise ValueError(f"{path}.executionStatus unsupported")
    return {
        "id": _text(raw.get("id"), 64, f"{path}.id"), "hypothesisId": _text(raw.get("hypothesisId"), 64, f"{path}.hypothesisId"),
        "query": _text(raw.get("query"), 500, f"{path}.query"), "providerIds": _id_list(raw.get("providerIds"), 8, f"{path}.providerIds"),
        "limit": limit, "purpose": _text(raw.get("purpose"), 500, f"{path}.purpose"),
        "disclosure": _text(raw.get("disclosure"), 500, f"{path}.disclosure"), "executionStatus": raw["executionStatus"],
    }


def validate_foreign_model_run(raw, path="modelRun"):
    _plain(raw, path)
    for key in raw:
        if key not in {"modelId", "id", "status", "note", "queryPlanId", "deskRunId"}:
            raise TypeError(f"{path}.{key} is unsupported")
    status = raw.get("status")
    if status not in RUN_STATUSES:
        raise ValueError(f"{path}.status unsupported")
    return {
        "modelId": _text(raw.get("modelId", "unknown-model"), 64, f"{path}.modelId"),
        "id": None if raw.get("id") is None else _text(raw.get("id"), 64, f"{path}.id"),
        "status": status,
        "note": _text(raw.get("note", "retained as foreign metadata; not executed here"), 500, f"{path}.note"),
        "queryPlanId": None if raw.get("queryPlanId") is None else _text(raw.get("queryPlanId"), 64, f"{path}.queryPlanId"),
        "deskRunId": None if raw.get("deskRunId") is None else _text(raw.get("deskRunId"), 64, f"{path}.deskRunId"),
    }


def validate_evidence_record(raw, path="evidence"):
    _plain(raw, path)
    for key in raw:
        if key not in {"id", "statement", "sourceClass", "reviewState", "locator", "sourceId"}:
            raise TypeError(f"{path}.{key} is unsupported")
    if raw.get("sourceClass") not in {"primary-source", "secondhand", "synthetic-fixture", "unreviewed-lead"}:
        raise ValueError(f"{path}.sourceClass unsupported")
    if raw.get("reviewState") not in {"unreviewed", "owner-reviewed"}:
        raise ValueError(f"{path}.reviewState unsupported")
    return {
        "id": _text(raw.get("id"), 64, f"{path}.id"), "statement": _text(raw.get("statement"), 2000, f"{path}.statement"),
        "sourceClass": raw["sourceClass"], "reviewState": raw["reviewState"],
        "locator": _text(raw.get("locator"), 500, f"{path}.locator"),
        "sourceId": None if raw.get("sourceId") is None else _text(raw.get("sourceId"), 64, f"{path}.sourceId"),
    }
def validate_bundle(raw):
    _plain(raw, "bundle")
    allowed = {"schema", "bundleId", "createdAt", "producer", "sourceRevision", "hypotheses", "queries",
               "modelRuns", "evidence", "artifacts", "privacyClassification", "publicationReviewStatus"}
    for key in raw:
        if key not in allowed:
            raise TypeError(f"bundle.{key} is unsupported")
    if raw.get("schema") != SCHEMA:
        raise ValueError("Unknown exchange schema")
    producer = _plain(raw.get("producer"), "bundle.producer")
    revision = _plain(raw.get("sourceRevision"), "bundle.sourceRevision")
    if not isinstance(revision.get("dirty"), bool):
        raise TypeError("sourceRevision.dirty must be boolean")
    if revision.get("commit") is not None and not isinstance(revision.get("commit"), str):
        raise TypeError("sourceRevision.commit must be null or text")
    impl = revision.get("implementationSha256")
    if impl is not None and (not isinstance(impl, str) or not re.fullmatch(r"[a-f0-9]{64}", impl)):
        raise TypeError("sourceRevision.implementationSha256 must be lowercase hex or null")
    if raw.get("privacyClassification") not in {"private", "selected-for-exchange"}:
        raise ValueError("privacyClassification unsupported")
    if raw.get("publicationReviewStatus") != "not-approved":
        raise ValueError("Imported/exported bundles are always not-approved for publication")
    bundle = {
        "schema": SCHEMA, "bundleId": _text(raw.get("bundleId"), 64, "bundle.bundleId"),
        "createdAt": _iso_instant(raw.get("createdAt"), "bundle.createdAt"),
        "producer": {
            "application": _text(producer.get("application"), 200, "producer.application"),
            "version": _text(producer.get("version"), 64, "producer.version"),
            "executedBy": producer.get("executedBy") if producer.get("executedBy") in {"owner", "agent", "import"} else (_ for _ in ()).throw(ValueError("producer.executedBy unsupported")),
        },
        "sourceRevision": {"commit": revision.get("commit"), "dirty": revision["dirty"], "implementationSha256": impl},
        "hypotheses": [], "queries": [], "modelRuns": [], "evidence": [], "artifacts": [],
        "privacyClassification": raw["privacyClassification"], "publicationReviewStatus": "not-approved",
    }
    for name, maximum, validate in (("hypotheses", 100, validate_hypothesis_card), ("queries", 100, validate_query_plan),
                                    ("modelRuns", 100, validate_foreign_model_run), ("evidence", 500, validate_evidence_record),
                                    ("artifacts", 500, validate_artifact_descriptor)):
        items = raw.get(name)
        if not isinstance(items, list) or len(items) > maximum:
            raise TypeError(f"bundle.{name} must be an array (max {maximum})")
        bundle[name] = [validate(item, f"bundle.{name}[{index}]") for index, item in enumerate(items)]
        if len({record["id"] for record in bundle[name]}) != len(bundle[name]):
            raise ValueError(f"Duplicate {name} ids in bundle")
    hypo_ids = [card["id"] for card in bundle["hypotheses"]]
    if len(set(hypo_ids)) != len(hypo_ids):
        raise ValueError("Duplicate hypothesis ids in bundle")
    known = set(hypo_ids)
    for plan in bundle["queries"]:
        if plan["hypothesisId"] not in known:
            raise ValueError(f"Query {plan['id']} references an unknown hypothesis")
    parents = {}
    for card in bundle["hypotheses"]:
        for parent in card["parentHypothesisIds"]:
            if parent not in known:
                raise ValueError(f"Hypothesis {card['id']} references unknown parent {parent}")
        parents[card["id"]] = card["parentHypothesisIds"]
    active, complete = set(), set()

    def visit(node):
        if node in active:
            raise ValueError("Hypothesis ancestry must be acyclic")
        if node in complete:
            return
        active.add(node)
        for parent in parents.get(node, []):
            visit(parent)
        active.remove(node)
        complete.add(node)

    for node in parents:
        visit(node)
    artifact_ids = [item["id"] for item in bundle["artifacts"]]
    if len(set(artifact_ids)) != len(artifact_ids):
        raise ValueError("Duplicate artifact ids in bundle")
    return bundle


def verify_artifact_files(bundle, files):
    """files: iterable of (filename, bytes). Byte-counts before hashing exact bytes."""
    validated = validate_bundle(bundle)
    provided, total = {}, 0
    for filename, data in files or []:
        if not isinstance(filename, str) or not isinstance(data, (bytes, bytearray)):
            raise TypeError("artifact files are (filename, bytes) pairs")
        if len(data) > MAX_ARTIFACT_BYTES:
            raise ValueError(f"Artifact {filename} exceeds {MAX_ARTIFACT_BYTES} bytes")
        total += len(data)
        if total > MAX_TOTAL_ARTIFACT_BYTES:
            raise ValueError(f"Selected artifacts exceed {MAX_TOTAL_ARTIFACT_BYTES} bytes")
        provided[filename] = bytes(data)
    verified, failed = [], []
    for descriptor in validated["artifacts"]:
        data = provided.get(descriptor["filename"])
        if data is None:
            failed.append({"id": descriptor["id"], "reason": "file not selected"})
        elif len(data) != descriptor["bytes"]:
            failed.append({"id": descriptor["id"], "reason": "size mismatch"})
        elif sha256_bytes(data) != descriptor["sha256"]:
            failed.append({"id": descriptor["id"], "reason": "hash mismatch"})
        else:
            verified.append(descriptor["id"])
    return {"verified": verified, "failed": failed}


def empty_state():
    return {"hypotheses": [], "queries": [], "modelRuns": [], "evidence": [], "artifacts": [], "receipts": []}
def preview_import(bundle, existing_records):
    """No writes, no submissions, no network. Exact id+hash duplicates are idempotent."""
    validated = validate_bundle(bundle)
    state = existing_records if isinstance(existing_records, dict) else empty_state()
    bundle_sha = sha256_bytes(canonical_json_bytes(validated))
    store_sha = sha256_bytes(canonical_json_bytes(state))
    current = {}
    for group in ("hypotheses", "queries", "modelRuns", "evidence", "artifacts", "receipts"):
        for record in state.get(group, []):
            current[f"{group}:{record['id']}"] = sha256_bytes(canonical_json_bytes(record))
    creates, duplicates, conflicts, warnings, blocked = [], [], [], [], []
    for group in ("hypotheses", "queries", "modelRuns", "evidence", "artifacts"):
        for record in validated[group]:
            key = f"{group}:{record['id']}"
            digest = sha256_bytes(canonical_json_bytes(record))
            if key not in current:
                creates.append(key)
            elif current[key] == digest:
                duplicates.append(key)
            else:
                conflicts.append(key)
    if any("foreign metadata" in run["note"] for run in validated["modelRuns"]):
        warnings.append("Foreign model runs are retained as metadata only and will never be executed or overlaid here.")
    if any(card["reviewStatus"] == "unreviewed" for card in validated["hypotheses"]):
        warnings.append("Unreviewed hypothesis records are imported as unreviewed; import never marks anything owner-reviewed.")
    warnings.append("Imported bundles always keep publicationReviewStatus not-approved.")
    if conflicts:
        blocked.append(f"{len(conflicts)} id conflicts must be resolved before apply")
    return {"bundleSha256": bundle_sha, "creates": creates, "duplicates": duplicates,
            "conflicts": conflicts, "warnings": warnings, "blockedReasons": blocked,
            "expectedStoreSha256": store_sha}


def apply_import(bundle, existing_records):
    """Constructs a NEW state dict; never partially mutates the old one."""
    validated = validate_bundle(bundle)
    state = copy.deepcopy(existing_records) if isinstance(existing_records, dict) else empty_state()
    preview = preview_import(validated, state)
    if preview["conflicts"]:
        raise ValueError("Import has unresolved id conflicts; apply refused")
    next_state = copy.deepcopy(state)
    for group in ("hypotheses", "queries", "modelRuns", "evidence", "artifacts"):
        known = {record["id"] for record in next_state.get(group, [])}
        for record in validated[group]:
            if record["id"] not in known:
                next_state.setdefault(group, []).append(copy.deepcopy(record))
    return next_state


def to_desk_question(card):
    """Map a hypothesis card to a method-neutral Desk question draft. Never writes to Desk."""
    validated = validate_hypothesis_card(card, "card")
    if not 2 <= len(validated["alternatives"]) <= 8:
        raise ValueError("Desk questions require 2-8 competing hypotheses")
    return {
        "title": validated["title"],
        "question": validated["question"],
        "claim_boundary": validated["claimBoundary"],
        "status": "draft" if validated["status"] == "draft" else "proposed",
        "competing_hypotheses": [
            {"id": alt["id"], "prediction": alt["prediction"], "falsifier": alt["falsifier"]}
            for alt in validated["alternatives"]
        ],
        "review_state": "unreviewed",
        "source": "bioprinting-workbench import",
    }


def _publish_staging(staging, root):
    """Durably publish a staging directory: fsync every written file and the staging directory,
    atomically rename into place, then fsync the parent directory. A hostile writer that creates
    the target meanwhile makes publication fail loudly; staging is cleaned by the caller and the
    foreign directory is never overwritten. This is filesystem-hygiene hardening for the normal
    app path, not an adversarial sandbox."""
    if root.exists() or root.is_symlink():
        raise ValueError("Export target already exists")
    for path in sorted(staging.iterdir()):
        with open(path, "rb") as handle:
            os.fsync(handle.fileno())
    staging_fd = os.open(staging, os.O_RDONLY)
    try:
        os.fsync(staging_fd)
    finally:
        os.close(staging_fd)
    os.replace(staging, root)
    parent_fd = os.open(root.parent, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def export_selected_results(selection, root):
    """Write a result bundle plus selected artifact files under root (bounded, flat names).
    Notes/caches are excluded by default: only explicit selection is written."""
    root = Path(root)
    bundle = {
        "schema": SCHEMA,
        "bundleId": _text(selection.get("bundleId"), 64, "selection.bundleId"),
        "createdAt": _iso_instant(selection.get("createdAt"), "selection.createdAt"),
        "producer": {"application": "regen-research-desk", "version": "dev", "executedBy": "agent"},
        "sourceRevision": {"commit": None, "dirty": True, "implementationSha256": None},
        "hypotheses": selection.get("hypotheses", []),
        "queries": selection.get("queries", []),
        "modelRuns": selection.get("modelRuns", []),
        "evidence": selection.get("evidence", []),
        "artifacts": selection.get("artifacts", []),
        "privacyClassification": "selected-for-exchange",
        "publicationReviewStatus": "not-approved",
    }
    validated = validate_bundle(bundle)
    files = preflight_export(validated, selection.get("files", []))
    if root.exists() or root.is_symlink():
        raise ValueError("Export target already exists")
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".bioprint-export-", dir=root.parent))
    written = {}
    try:
        for filename, data in files:
            (staging / filename).write_bytes(data)
            written[filename] = sha256_bytes(data)
        (staging / "bioprint-results.json").write_bytes(canonical_json_bytes(validated))
        _publish_staging(staging, root)
    except BaseException:
        shutil.rmtree(staging)
        raise
    manifest_path = root / "bioprint-results.json"
    return {"manifest": str(manifest_path), "bundleSha256": sha256_bytes(canonical_json_bytes(validated)), "files": written}


def preflight_export(bundle, files):
    """Validate and snapshot every artifact before creating any export directory."""
    descriptors = {}
    for descriptor in bundle["artifacts"]:
        name = descriptor["filename"]
        if name == "bioprint-results.json" or name in descriptors:
            raise ValueError("Duplicate or reserved artifact filename")
        descriptors[name] = descriptor
    if not isinstance(files, (list, tuple)) or len(files) > 500:
        raise ValueError("Artifact files must be a bounded list")
    checked, names, total = [], set(), 0
    for item in files:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("Artifact file must be a filename/bytes pair")
        name, data = item
        if (not isinstance(name, str) or not FILENAME_RE.fullmatch(name)
                or ".." in name or name == "bioprint-results.json" or name in names):
            raise ValueError("Unsafe, duplicate or reserved artifact filename")
        if not isinstance(data, (bytes, bytearray)) or len(data) > MAX_ARTIFACT_BYTES:
            raise ValueError("Artifact bytes out of bounds")
        data = bytes(data)
        descriptor = descriptors.get(name)
        if descriptor is None or len(data) != descriptor["bytes"] or sha256_bytes(data) != descriptor["sha256"]:
            raise ValueError("Artifact descriptor does not match exact file bytes")
        total += len(data)
        if total > MAX_TOTAL_ARTIFACT_BYTES:
            raise ValueError("Aggregate artifact bytes out of bounds")
        names.add(name)
        checked.append((name, data))
    if names != set(descriptors):
        raise ValueError("Missing artifact bytes")
    return checked
