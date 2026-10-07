from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from verify_dossier import (  # noqa: E402
    DossierVerificationError,
    _unsafe_member_reason,
    main,
    verify_dossier,
)


def archive_bytes(members: dict[str, bytes], *, index_paths: list[str] | None = None,
                  overrides: dict[str, dict] | None = None, extra_index: list[dict] | None = None) -> bytes:
    """Build a dossier-shaped archive and derive archive-index.json from its members."""
    overrides = overrides or {}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        index = []
        for name in (index_paths if index_paths is not None else list(members)):
            blob = members.get(name, b"")
            row = {"path": name, "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}
            row.update(overrides.get(name, {}))
            index.append(row)
        index.extend(extra_index or [])
        for name, blob in members.items():
            archive.writestr(name, blob)
        archive.writestr("archive-index.json",
                         json.dumps({"schema_version": 1, "notes_included": False, "files": index}).encode())
    return buffer.getvalue()


def dossier_document(linked: dict | None = None) -> bytes:
    return json.dumps({
        "blueprint": {"id": "tissues", "title": "Tissue regeneration"},
        "campaigns": [],
        "runs": [],
        "linked_research": linked or {"experiments": [], "model_bundles": []},
        "exported_utc": "2026-10-07T00:00:00Z",
    }).encode()


def plan_document(inputs: list[dict] | None = None) -> bytes:
    return json.dumps({
        "schema_version": 1,
        "generated_utc": "2026-10-07T00:00:00Z",
        "workbench_revision": {"revision": "unknown", "detail": "test fixture"},
        "python_version": "3.12.3",
        "declared_dependencies": {"verification": ["python>=3.10 standard library only"], "rerun": []},
        "commands": {"verify_archive": "python tools/verify_dossier.py <archive.zip> --strict"},
        "inputs": inputs or [],
        "expected_outputs": [],
        "limits": ["fixture"],
    }).encode()


def minimal_members(**extra: bytes) -> dict[str, bytes]:
    members = {
        "dossier.json": dossier_document(),
        "research_records.json": json.dumps({"schema_version": 1, "records": []}).encode(),
        "research_dossier.md": b"# Tissue regeneration\n",
        "public_draft.md": b"# Discussion draft\n",
        "reproduction-plan.json": plan_document(),
    }
    members.update(extra)
    return members


def write_archive(directory: Path, blob: bytes, name: str = "dossier.zip") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(blob)
    return path


class VerifyDossierTests(unittest.TestCase):
    def test_intact_archive_verifies_and_separates_review_from_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = write_archive(Path(temp), archive_bytes(minimal_members()))
            report = verify_dossier(path, strict=True)
        self.assertTrue(report["bytes_verified"], report["errors"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["ancestry_resolved"], "no_linked_sources_declared")
        self.assertEqual(report["scientific_review"], "not_established_by_this_tool")
        self.assertEqual(report["reproduction"], "not_attempted")
        self.assertTrue(report["reproduction_requirements"]["plan_present"])
        self.assertEqual(report["inventory"]["indexed_files"], 5)

    def test_changed_bytes_fail_with_the_offending_path(self):
        members = minimal_members()
        blob = archive_bytes(members)
        tampered = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(blob)) as source, zipfile.ZipFile(tampered, "w") as target:
            for name in source.namelist():
                content = source.read(name)
                if name == "research_dossier.md":
                    content = content + b"appended after export\n"
                target.writestr(name, content)
        with tempfile.TemporaryDirectory() as temp:
            report = verify_dossier(write_archive(Path(temp), tampered.getvalue()))
        self.assertFalse(report["bytes_verified"])
        self.assertTrue(any("research_dossier.md" in error and "inventory hash" in error
                            for error in report["errors"]), report["errors"])

    def test_missing_inventoried_file_is_reported(self):
        members = minimal_members()
        paths = list(members) + ["runs/" + "a" * 32 + "/run.json"]
        with tempfile.TemporaryDirectory() as temp:
            path = write_archive(Path(temp), archive_bytes(members, index_paths=paths))
            report = verify_dossier(path)
        self.assertFalse(report["bytes_verified"])
        self.assertTrue(any("does not contain" in error for error in report["errors"]), report["errors"])

    def test_required_documents_must_be_present(self):
        members = minimal_members()
        del members["research_records.json"]
        with tempfile.TemporaryDirectory() as temp:
            report = verify_dossier(write_archive(Path(temp), archive_bytes(members)))
        self.assertFalse(report["bytes_verified"])
        self.assertIn("required document is missing: research_records.json", report["errors"])

    def test_escaping_and_absolute_member_paths_are_rejected(self):
        for unsafe in ("../escape.md", "/etc/passwd", "runs/../../escape.md", " leading.md"):
            with self.subTest(unsafe=unsafe):
                members = minimal_members()
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w") as archive:
                    for name, blob in members.items():
                        archive.writestr(name, blob)
                    archive.writestr(unsafe, b"payload")
                    index = [{"path": name, "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}
                             for name, blob in members.items()]
                    archive.writestr("archive-index.json",
                                     json.dumps({"schema_version": 1, "files": index}).encode())
                with tempfile.TemporaryDirectory() as temp:
                    report = verify_dossier(write_archive(Path(temp), buffer.getvalue()))
                self.assertFalse(report["bytes_verified"])
                # The verifier quotes the raw member name with !r, so compare the same way.
                self.assertTrue(any("unsafe archive member" in error and repr(unsafe) in error
                                    for error in report["errors"]), report["errors"])

    def test_member_name_rule_rejects_backslashes_and_traversal(self):
        # Exercised directly because Windows zipfile rewrites os.sep both when
        # writing and when reading names, so a backslash member cannot be built
        # portably through an archive. A foreign archiver can still emit one.
        for unsafe, reason in (
            ("dir\\file.md", "backslash"),
            ("..", "relative traversal"),
            ("a/../../b.md", "relative traversal"),
            ("./a.md", "non-canonical"),
            ("a//b.md", "non-canonical"),
            ("/abs.md", "absolute"),
            ("C:/abs.md", "absolute"),
            ("trailing /file.md", "whitespace"),
            ("", "empty"),
            ("runs/", "empty or directory"),
        ):
            with self.subTest(unsafe=unsafe):
                detected = _unsafe_member_reason(unsafe)
                self.assertIsNotNone(detected, unsafe)
                self.assertIn(reason, detected)
        for safe in ("dossier.json", "runs/abc/metrics.json", "linked-research/experiments/e1/experiment.json"):
            with self.subTest(safe=safe):
                self.assertIsNone(_unsafe_member_reason(safe))

    def test_symlink_member_is_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, blob in minimal_members().items():
                archive.writestr(name, blob)
            info = zipfile.ZipInfo("linked-research/experiments/e1/experiment.json")
            info.external_attr = (0o120777 << 16)
            archive.writestr(info, "/etc/passwd")
            archive.writestr("archive-index.json", json.dumps({"schema_version": 1, "files": [
                {"path": "dossier.json", "sha256": "0" * 64, "bytes": 1}]}).encode())
        with tempfile.TemporaryDirectory() as temp:
            report = verify_dossier(write_archive(Path(temp), buffer.getvalue()))
        self.assertFalse(report["bytes_verified"])
        self.assertTrue(any("symlink" in error for error in report["errors"]), report["errors"])

    def test_duplicate_member_is_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, blob in minimal_members().items():
                archive.writestr(name, blob)
            archive.writestr("research_dossier.md", b"# A second copy\n")
            archive.writestr("archive-index.json", json.dumps({"schema_version": 1, "files": [
                {"path": "dossier.json", "sha256": "0" * 64, "bytes": 1}]}).encode())
        with tempfile.TemporaryDirectory() as temp:
            report = verify_dossier(write_archive(Path(temp), buffer.getvalue()))
        self.assertFalse(report["bytes_verified"])
        self.assertTrue(any("duplicate archive member" in error for error in report["errors"]), report["errors"])

    def test_oversize_member_is_rejected_without_reading_it(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, blob in minimal_members().items():
                archive.writestr(name, blob)
            archive.writestr("runs/" + "b" * 32 + "/huge.csv", b"0" * 20_000_001)
            archive.writestr("archive-index.json", json.dumps({"schema_version": 1, "files": [
                {"path": "dossier.json", "sha256": "0" * 64, "bytes": 1}]}).encode())
        with tempfile.TemporaryDirectory() as temp:
            report = verify_dossier(write_archive(Path(temp), buffer.getvalue()))
        self.assertFalse(report["bytes_verified"])
        self.assertTrue(any("exceeds the" in error and "huge.csv" in error for error in report["errors"]),
                        report["errors"])

    def test_undeclared_member_is_a_warning_and_a_strict_failure(self):
        members = minimal_members()
        declared = [name for name in members if name != "public_draft.md"]
        with tempfile.TemporaryDirectory() as temp:
            path = write_archive(Path(temp), archive_bytes(members, index_paths=declared))
            lenient = verify_dossier(path)
            strict = verify_dossier(path, strict=True)
        self.assertTrue(lenient["bytes_verified"], lenient["errors"])
        self.assertIn("public_draft.md", lenient["inventory"]["undeclared_members"])
        self.assertTrue(any("not listed in the inventory" in warning for warning in lenient["warnings"]))
        self.assertFalse(strict["bytes_verified"])

    def test_run_output_mismatched_at_export_is_surfaced(self):
        run_path = "runs/" + "c" * 32 + "/metrics.json"
        members = minimal_members(**{run_path: b'{"metric": 1}'})
        overrides = {run_path: {"listed_in_run_manifest": True, "source_matches_run_manifest": False,
                                "source_sha256": "d" * 64}}
        with tempfile.TemporaryDirectory() as temp:
            path = write_archive(Path(temp), archive_bytes(members, overrides=overrides))
            lenient = verify_dossier(path)
            strict = verify_dossier(path, strict=True)
        self.assertTrue(lenient["bytes_verified"], lenient["errors"])
        self.assertEqual(lenient["inventory"]["run_outputs_mismatched_at_export"], [run_path])
        self.assertFalse(strict["bytes_verified"])
        self.assertTrue(any("run manifest hash" in error for error in strict["errors"]))

    def test_declared_linked_source_must_resolve_inside_the_archive(self):
        output = "linked-research/experiments/e1/outputs/receipt.json"
        blob = b'{"receipt": true}'
        linked = {"experiments": [{"experiment_id": "e1", "title": "Imaging", "files": [
            {"archive_path": output, "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}]}],
            "model_bundles": []}
        members = minimal_members(**{output: blob})
        members["dossier.json"] = dossier_document(linked)
        with tempfile.TemporaryDirectory() as temp:
            resolved = verify_dossier(write_archive(Path(temp), archive_bytes(members)), strict=True)
            self.assertEqual(resolved["ancestry_resolved"], "resolved", resolved["errors"])
            self.assertEqual(resolved["ancestry"]["resolved"], [output])

            absent = dict(members)
            del absent[output]
            report = verify_dossier(write_archive(Path(temp), archive_bytes(absent), name="absent.zip"))
            self.assertEqual(report["ancestry_resolved"], "unresolved")
            self.assertIn(output, report["ancestry"]["missing"])

            swapped = dict(members)
            swapped[output] = b'{"receipt": false}'
            report = verify_dossier(write_archive(Path(temp), archive_bytes(swapped), name="swapped.zip"))
            self.assertEqual(report["ancestry_resolved"], "unresolved")
            self.assertIn(output, report["ancestry"]["mismatched"])

    def test_archive_without_a_plan_warns_instead_of_failing(self):
        members = minimal_members()
        del members["reproduction-plan.json"]
        with tempfile.TemporaryDirectory() as temp:
            report = verify_dossier(write_archive(Path(temp), archive_bytes(members)))
        self.assertTrue(report["bytes_verified"], report["errors"])
        self.assertFalse(report["reproduction_requirements"]["plan_present"])
        self.assertTrue(any("no reproduction-plan.json" in warning for warning in report["warnings"]))

    def test_unreadable_and_absent_archives_raise_actionable_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(DossierVerificationError, "does not exist"):
                verify_dossier(Path(temp) / "missing.zip")
            broken = write_archive(Path(temp), b"not a zip file", name="broken.zip")
            with self.assertRaisesRegex(DossierVerificationError, "readable zip"):
                verify_dossier(broken)

    def test_relocated_archive_verifies_and_cli_reports_status(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            original = write_archive(Path(first) / "nested", archive_bytes(minimal_members()))
            moved = Path(second) / "renamed-copy.zip"
            moved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, moved)
            report_path = Path(second) / "report.json"
            self.assertEqual(main([str(moved), "--strict", "--out", str(report_path)]), 0)
            saved = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(saved["bytes_verified"])
            self.assertEqual(saved["archive"], "renamed-copy.zip")
            self.assertEqual(main([str(moved), "--out", str(report_path)]), 2)

    def test_cli_returns_one_for_a_failed_verification(self):
        members = minimal_members()
        del members["dossier.json"]
        with tempfile.TemporaryDirectory() as temp:
            path = write_archive(Path(temp), archive_bytes(members))
            self.assertEqual(main([str(path)]), 1)


if __name__ == "__main__":
    unittest.main()
