#!/usr/bin/env python3
"""Verify an exported ResearchDesk dossier archive without the workstation that made it.

The verifier uses only the Python standard library so a reviewer can run it in a
clean environment. It answers four separate questions and never merges them:

* ``bytes_verified``   — do the archived members match the inventory hashes?
* ``ancestry_resolved`` — does every archived file resolve to a declared source
  manifest or receipt entry carried inside the same archive?
* ``scientific_lineage`` — do the archived research revisions still hash to what they
  declare, do frozen-plan pins resolve to revisions inside the archive, is each
  holdout-access ledger an unbroken hash chain, and does the recorded claim state
  recompute from the archived records? It needs ``frozen_evaluation.py`` beside this
  file (also standard library only); without it the status is ``not_checked``.
* ``scientific_review`` — always ``not_established_by_this_tool``. A hash match
  is not a reviewed result.

Verification is not reproduction. ``reproduction`` reports ``not_attempted``;
the reproduction plan records what a rerun would additionally require.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

try:  # the lineage checks live beside this file; the verifier still runs without them
    import frozen_evaluation as _fe
except ImportError:  # pragma: no cover - exercised by copying this file alone
    _fe = None

MAX_MEMBER_BYTES = 20_000_000
MAX_TOTAL_BYTES = 100_000_000
MAX_MEMBERS = 5_000
REQUIRED_DOCUMENTS = ("archive-index.json", "dossier.json", "research_records.json", "research_dossier.md")
STATUS_NOT_REVIEWED = "not_established_by_this_tool"


class DossierVerificationError(ValueError):
    """Raised when the archive cannot be read safely enough to report on."""


def _unsafe_member_reason(name: str) -> str | None:
    """Reject names that could escape an extraction directory or hide a duplicate."""
    if not name or name.endswith("/"):
        return "empty or directory entry"
    if "\\" in name:
        return "backslash in archive path"
    if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        return "absolute archive path"
    parts = PurePosixPath(name).parts
    if any(part in {"..", "."} for part in parts):
        return "relative traversal segment"
    if PurePosixPath(name).as_posix() != name:
        # "./a.md" and "a//b.md" resolve to a different member than they spell, so a
        # consumer could silently read one file while the inventory names another.
        return "non-canonical archive path"
    if any(part.strip() != part for part in parts):
        return "leading or trailing whitespace in a path segment"
    return None


def _member_is_symlink(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def _structure_errors(index: dict, dossier: dict, plan: dict | None) -> list[str]:
    """Check the documents' shape in pure Python so no schema library is needed."""
    errors = []
    if index.get("schema_version") != 1:
        errors.append("archive-index.json schema_version must be 1")
    if not isinstance(index.get("files"), list) or not index["files"]:
        errors.append("archive-index.json must list at least one file")
    else:
        for position, row in enumerate(index["files"]):
            if not isinstance(row, dict):
                errors.append(f"archive-index.json files[{position}] must be an object")
                continue
            if not isinstance(row.get("path"), str) or not row["path"]:
                errors.append(f"archive-index.json files[{position}] needs a path")
            if not isinstance(row.get("sha256"), str) or len(row.get("sha256", "")) != 64:
                errors.append(f"archive-index.json files[{position}] needs a 64-character sha256")
            if not isinstance(row.get("bytes"), int) or row["bytes"] < 0:
                errors.append(f"archive-index.json files[{position}] needs a byte count")
    for field in ("blueprint", "campaigns", "runs", "linked_research", "exported_utc"):
        if field not in dossier:
            errors.append(f"dossier.json is missing {field}")
    if not isinstance(dossier.get("linked_research"), dict):
        errors.append("dossier.json linked_research must be an object")
    elif not all(isinstance(dossier["linked_research"].get(key), list) for key in ("experiments", "model_bundles")):
        errors.append("dossier.json linked_research needs experiments and model_bundles lists")
    if plan is not None:
        if plan.get("schema_version") != 1:
            errors.append("reproduction-plan.json schema_version must be 1")
        for field in ("workbench_revision", "python_version", "declared_dependencies", "commands",
                      "inputs", "expected_outputs", "limits"):
            if field not in plan:
                errors.append(f"reproduction-plan.json is missing {field}")
    return errors


def _read_json(archive: zipfile.ZipFile, name: str, errors: list[str]) -> dict | None:
    try:
        return json.loads(archive.read(name).decode("utf-8"))
    except KeyError:
        errors.append(f"required document is missing: {name}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{name} is not readable JSON: {exc}")
    return None


def _declared_ancestry(dossier: dict, plan: dict | None) -> dict[str, str]:
    """Map archive paths to the hash their source manifest, receipt or plan declares."""
    declared: dict[str, str] = {}
    linked = dossier.get("linked_research") or {}
    for group in ("experiments", "model_bundles"):
        for item in linked.get(group) or []:
            for file in item.get("files") or []:
                path, digest = file.get("archive_path"), file.get("sha256")
                if isinstance(path, str) and isinstance(digest, str):
                    declared[path] = digest
    for item in (plan or {}).get("inputs") or []:
        path, digest = item.get("archive_path"), item.get("sha256")
        if isinstance(path, str) and isinstance(digest, str):
            declared.setdefault(path, digest)
    return declared


def _lineage(archive: zipfile.ZipFile, members: dict) -> dict:
    """Check the archived research revisions without the Desk that wrote them."""
    if "research_records.json" not in members:
        return {"status": "not_applicable", "n_records": 0, "freezes": [], "problems": []}
    if _fe is None:
        return {"status": "not_checked", "n_records": None, "freezes": [], "problems": [],
                "detail": "frozen_evaluation.py was not found next to the verifier, so research "
                          "revisions were not re-hashed."}
    try:
        payload = json.loads(archive.read("research_records.json").decode("utf-8"))
        records = payload["records"]
        if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
            raise ValueError("records must be a list of objects")
    except (KeyError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"status": "unresolved", "n_records": 0, "freezes": [],
                "problems": [f"research_records.json is not readable: {exc}"]}

    problems, local = [], []
    for item in records:
        item = dict(item)
        try:
            recomputed = _fe.record_hash(item["record_type"], item["title"], item["content"])
        except (KeyError, TypeError, ValueError):
            recomputed = None
        item["content_integrity_valid"] = recomputed is not None and recomputed == item.get("content_sha256")
        if not item["content_integrity_valid"]:
            problems.append(f"research revision {item.get('revision_id')} does not hash to its declared "
                            "content_sha256")
        local.append(item)
    by_id = {item.get("revision_id"): item for item in local}
    freezes = []
    for freeze in (item for item in local if item.get("record_type") == "plan_freeze"):
        identifier = freeze.get("revision_id")
        row = {"revision_id": identifier, "pins_resolve": True, "claim_status": None,
               "claim_status_matches_export": None}
        try:
            pins = freeze["content"]["pins"]
            wanted = [(pins["plan"], "analysis_plan"), (pins["question"], "question"),
                      *[(pin, "dataset_card") for pin in pins["datasets"]]]
            for pin, record_type in wanted:
                found = by_id.get(pin["revision_id"])
                if found is None or found.get("record_type") != record_type:
                    row["pins_resolve"] = False
                    problems.append(f"freeze {identifier} pins {record_type} {pin['revision_id']}, which is "
                                    "absent from the archive")
                elif found["content_sha256"] != pin["content_sha256"] or not found["content_integrity_valid"]:
                    row["pins_resolve"] = False
                    problems.append(f"freeze {identifier} pins {record_type} {pin['revision_id']}, whose "
                                    "archived content differs from the pinned hash")
            split = freeze["content"]["split"]
            expected = _fe._canonical_sha256({key: split[key] for key in (
                "grouping_unit", "development_group_ids", "final_test_group_ids")})
            if split.get("split_sha256") != expected:
                problems.append(f"freeze {identifier} split does not hash to its declared split_sha256")
            events = [item for item in local if item.get("record_type") == "holdout_access"
                      and item.get("content", {}).get("freeze_revision_id") == identifier]
            bindings = [item for item in local if item.get("record_type") == "evaluation_binding"
                        and item.get("content", {}).get("freeze_revision_id") == identifier]
            for item in bindings:
                if item["content"].get("freeze_content_sha256") != freeze["content_sha256"]:
                    problems.append(f"binding {item.get('revision_id')} is bound to different freeze content")
            assessment = _fe.assess_freeze(freeze, events, bindings)
            row["claim_status"] = assessment["claim_status"]
            row["ledger_chain_valid"] = assessment["ledger"]["chain_valid"]
            for problem in assessment["ledger"]["chain_problems"]:
                problems.append(f"freeze {identifier} ledger: {problem}")
            exported = freeze.get("freeze_assessment")
            if isinstance(exported, dict):
                row["claim_status_matches_export"] = (
                    exported.get("claim_status") == assessment["claim_status"]
                    and exported.get("record_supports_confirmatory_claim")
                    == assessment["record_supports_confirmatory_claim"])
                if not row["claim_status_matches_export"]:
                    problems.append(f"freeze {identifier} exported claim state "
                                    f"{exported.get('claim_status')!r} differs from the recomputed "
                                    f"{assessment['claim_status']!r}")
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            row["pins_resolve"] = False
            problems.append(f"freeze {identifier} could not be checked: {exc!r}")
        freezes.append(row)
    status = "unresolved" if problems else ("resolved" if freezes or local else "no_research_records")
    return {"status": status, "n_records": len(local), "freezes": freezes, "problems": problems}


def verify_dossier(archive_path: Path, *, strict: bool = False) -> dict:
    """Return a verification report for one exported dossier archive.

    ``strict`` additionally fails the report when the archive carries members the
    inventory does not declare, or run outputs whose source hash did not match the
    run manifest at export time.
    """
    path = Path(archive_path)
    if not path.is_file():
        raise DossierVerificationError(f"dossier archive does not exist: {path}")
    if path.stat().st_size > MAX_TOTAL_BYTES:
        raise DossierVerificationError(
            f"dossier archive is larger than the {MAX_TOTAL_BYTES} byte limit: {path.stat().st_size}"
        )

    errors: list[str] = []
    warnings: list[str] = []
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise DossierVerificationError(f"dossier archive is not a readable zip file: {exc}") from exc

    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise DossierVerificationError(f"dossier archive declares more than {MAX_MEMBERS} members")
        seen: set[str] = set()
        total_declared = 0
        members: dict[str, zipfile.ZipInfo] = {}
        for info in infos:
            reason = _unsafe_member_reason(info.filename)
            if reason:
                errors.append(f"unsafe archive member rejected ({reason}): {info.filename!r}")
                continue
            if _member_is_symlink(info):
                errors.append(f"archive member is a symlink: {info.filename}")
                continue
            if info.filename in seen:
                errors.append(f"duplicate archive member: {info.filename}")
                continue
            if info.file_size > MAX_MEMBER_BYTES:
                errors.append(f"archive member exceeds the {MAX_MEMBER_BYTES} byte limit: {info.filename}")
                continue
            total_declared += info.file_size
            if total_declared > MAX_TOTAL_BYTES:
                raise DossierVerificationError("archive members exceed the uncompressed total byte budget")
            seen.add(info.filename)
            members[info.filename] = info

        for name in REQUIRED_DOCUMENTS:
            if name not in members:
                errors.append(f"required document is missing: {name}")

        index = _read_json(archive, "archive-index.json", errors) if "archive-index.json" in members else None
        dossier = _read_json(archive, "dossier.json", errors) if "dossier.json" in members else None
        plan = _read_json(archive, "reproduction-plan.json", errors) if "reproduction-plan.json" in members else None
        if plan is None and "reproduction-plan.json" not in members:
            warnings.append("archive has no reproduction-plan.json; it was exported before plans were recorded")
        if index is None or dossier is None:
            return _report(path, errors, warnings, {}, {}, None, None, None, strict)
        errors.extend(_structure_errors(index, dossier, plan))

        indexed: dict[str, dict] = {}
        for row in index.get("files") or []:
            if not isinstance(row, dict) or not isinstance(row.get("path"), str):
                continue
            if row["path"] in indexed:
                errors.append(f"archive-index.json lists {row['path']} more than once")
                continue
            indexed[row["path"]] = row

        results: dict[str, dict] = {}
        for name, row in sorted(indexed.items()):
            info = members.get(name)
            if info is None:
                errors.append(f"inventory lists a file the archive does not contain: {name}")
                results[name] = {"present": False, "bytes_match": False, "hash_match": False}
                continue
            blob = archive.read(name)
            digest = hashlib.sha256(blob).hexdigest()
            hash_match = digest == row.get("sha256")
            bytes_match = len(blob) == row.get("bytes")
            if not hash_match:
                errors.append(f"archived bytes do not match the inventory hash: {name}")
            if not bytes_match:
                errors.append(f"archived byte count does not match the inventory: {name}")
            results[name] = {"present": True, "bytes_match": bytes_match, "hash_match": hash_match,
                             "bytes": len(blob), "sha256": digest}

        undeclared = sorted(set(members) - set(indexed) - {"archive-index.json"})
        for name in undeclared:
            message = f"archive member is not listed in the inventory: {name}"
            (errors if strict else warnings).append(message)

        unmatched_runs = sorted(
            row["path"] for row in indexed.values()
            if row.get("listed_in_run_manifest") and row.get("source_matches_run_manifest") is False
        )
        for name in unmatched_runs:
            message = f"run output did not match its run manifest hash at export time: {name}"
            (errors if strict else warnings).append(message)
        unlisted_runs = sorted(
            row["path"] for row in indexed.values()
            if row["path"].startswith("runs/") and row.get("listed_in_run_manifest") is False
        )

        declared = _declared_ancestry(dossier, plan)
        ancestry = {"declared": len(declared), "resolved": [], "missing": [], "mismatched": []}
        for name, digest in sorted(declared.items()):
            result = results.get(name)
            if result is None or not result.get("present"):
                ancestry["missing"].append(name)
            elif result.get("sha256") != digest:
                ancestry["mismatched"].append(name)
            else:
                ancestry["resolved"].append(name)
        for name in ancestry["missing"]:
            errors.append(f"declared source file is absent from the archive: {name}")
        for name in ancestry["mismatched"]:
            errors.append(f"declared source hash does not match the archived bytes: {name}")

        inventory = {
            "members": len(members),
            "indexed_files": len(indexed),
            "undeclared_members": undeclared,
            "uncompressed_bytes": sum(result.get("bytes", 0) for result in results.values()),
            "run_outputs_not_in_run_manifest": unlisted_runs,
            "run_outputs_mismatched_at_export": unmatched_runs,
            "notes_included": bool(index.get("notes_included")),
        }
        lineage = _lineage(archive, members)
        if lineage["status"] == "not_checked":
            warnings.append(lineage["detail"])
        return _report(path, errors, warnings, results, inventory, ancestry, plan, lineage, strict)


def _report(path: Path, errors: list[str], warnings: list[str], files: dict, inventory: dict,
            ancestry: dict | None, plan: dict | None, lineage: dict | None, strict: bool = False) -> dict:
    if ancestry is None:
        ancestry_status = "unresolved"
    elif ancestry["missing"] or ancestry["mismatched"]:
        ancestry_status = "unresolved"
    elif ancestry["declared"] == 0:
        ancestry_status = "no_linked_sources_declared"
    else:
        ancestry_status = "resolved"
    return {
        "schema_version": 1,
        "archive": path.name,
        "bytes_verified": not errors,
        # Archive bytes and research lineage are separate questions. Under --strict an unresolved
        # lineage also fails the run, without pretending any bytes were wrong.
        "verified": not errors and not (strict and (lineage or {}).get("status") == "unresolved"),
        "ancestry_resolved": ancestry_status,
        "scientific_lineage": (lineage or {"status": "not_checked"})["status"],
        "lineage": lineage,
        "scientific_review": STATUS_NOT_REVIEWED,
        "reproduction": "not_attempted",
        "reproduction_requirements": {
            "plan_present": plan is not None,
            "workbench_revision": (plan or {}).get("workbench_revision"),
            "declared_dependencies": (plan or {}).get("declared_dependencies"),
            "commands": (plan or {}).get("commands"),
        },
        "inventory": inventory,
        "ancestry": ancestry,
        "files": files,
        "errors": errors,
        "warnings": warnings,
        "limits": [
            "Matching hashes establish archive integrity only. They do not establish that an analysis was "
            "correct, that an annotation was accepted, or that a biological claim is supported.",
            "Ancestry resolution compares archived bytes with the manifests and receipts carried inside the "
            "same archive. It cannot authenticate the original acquisition.",
            "This command never reruns an analysis. A rerun additionally needs the declared revision, "
            "dependencies and any input the archive does not contain.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify-dossier", description=__doc__.splitlines()[0])
    parser.add_argument("archive", help="path to an exported dossier .zip")
    parser.add_argument("--strict", action="store_true",
                        help="fail on undeclared members and run outputs that did not match their manifest")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    parser.add_argument("--out", help="write the JSON report to this new file path")
    args = parser.parse_args(argv)

    try:
        report = verify_dossier(Path(args.archive), strict=args.strict)
    except DossierVerificationError as exc:
        print(f"verify-dossier: {exc}", file=sys.stderr)
        return 2

    if args.out:
        out = Path(args.out)
        if out.exists():
            print(f"verify-dossier: output path already exists: {out}", file=sys.stderr)
            return 2
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"archive          {report['archive']}")
        print(f"bytes verified   {report['bytes_verified']}")
        print(f"ancestry         {report['ancestry_resolved']}")
        print(f"sci. lineage     {report['scientific_lineage']}")
        print(f"scientific review {report['scientific_review']}")
        print(f"reproduction     {report['reproduction']}")
        inventory = report["inventory"]
        print(f"members          {inventory.get('members', 0)} ({inventory.get('indexed_files', 0)} inventoried)")
        for warning in report["warnings"]:
            print(f"warning          {warning}")
        for error in report["errors"]:
            print(f"error            {error}")
        for problem in (report["lineage"] or {}).get("problems", []):
            print(f"lineage          {problem}")
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
