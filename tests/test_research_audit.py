from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import research_audit  # noqa: E402


class ResearchAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "research-desk"
        (self.root / "runs").mkdir(parents=True)

    def add_run(self, run_id="a" * 32, with_manifest=True):
        path = self.root / "runs" / run_id
        path.mkdir()
        payload = b'{"records": 1}\n'
        (path / "result.json").write_bytes(payload)
        (path / "run.json").write_text(json.dumps({"id": run_id, "status": "complete", "result": {}}))
        if with_manifest:
            (path / "manifest.json").write_text(json.dumps({"outputs": {"result.json": {"sha256": hashlib.sha256(payload).hexdigest()}}}))
        return path

    def test_valid_run_and_hashes_pass(self):
        self.add_run()
        result = research_audit.audit(self.root)
        self.assertTrue(result["audit_ok"])
        self.assertEqual(result["verified_artifact_hashes"], 1)

    def test_empty_root_is_not_a_false_green(self):
        self.assertFalse(research_audit.audit(self.root)["audit_ok"])
        self.assertTrue(research_audit.audit(self.root, allow_empty=True)["audit_ok"])

    def test_missing_manifest_and_unlisted_files_are_reported(self):
        self.add_run(with_manifest=False)
        result = research_audit.audit(self.root)
        self.assertFalse(result["audit_ok"])
        self.assertEqual(result["missing_manifests"][0]["status"], "complete")
        self.assertIn("result.json", result["unlisted_artifacts"][0])

    def test_hash_mismatch_and_manifest_path_escape_fail(self):
        path = self.add_run()
        (path / "result.json").write_text("changed")
        (path / "manifest.json").write_text(json.dumps({"outputs": {"../../outside.json": {"sha256": "bad"}}}))
        result = research_audit.audit(self.root)
        self.assertFalse(result["audit_ok"])
        self.assertTrue(result["hash_failures"])

    def test_orphan_run_directory_fails(self):
        (self.root / "runs" / "orphan").mkdir()
        result = research_audit.audit(self.root)
        self.assertFalse(result["audit_ok"])
        self.assertEqual(result["orphan_run_directories"], ["orphan"])


if __name__ == "__main__":
    unittest.main()
