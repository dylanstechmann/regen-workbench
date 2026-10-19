"""Progress cards must preserve evidence types and withhold stale or undeclared files."""
import copy
import hashlib
import http.client
from http.server import ThreadingHTTPServer
import json
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import research_progress as progress
import regen_desk as desk


class ProgressTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.index = self.root / "tools/data/research-progress.json"
        self.index.parent.mkdir(parents=True)
        self.report = self.root / "studies/demo/REPORT.md"
        self.report.parent.mkdir(parents=True)
        self.report.write_text("# Synthetic software fixture\n", encoding="utf-8", newline="\n")
        self.result = self.report.with_name("results.json")
        self.result.write_text('{"measured":false}\n', encoding="utf-8", newline="\n")
        def artifact(ident, path):
            content = path.read_text(encoding="utf-8").encode("utf-8")
            return {"id": ident, "label": ident, "path": path.relative_to(self.root).as_posix(),
                    "sha256_lf_text": hashlib.sha256(content).hexdigest(), "bytes_utf8_lf": len(content)}
        self.document = {"schema_version": 1, "updates": [{"id": "demo-model", "title": "Demonstration model",
            "topic": "Software fixture", "updated_on": "2026-10-19", "evidence_kind": "illustrative_model",
            "result": "Entirely synthetic demonstration.", "boundary": "No biological observations.",
            "next_step": "Qualify measured inputs.", "artifacts": [artifact("report", self.report), artifact("results", self.result)]}]}
        self.save()

    def save(self):
        self.index.write_text(json.dumps(self.document), encoding="utf-8")

    def test_matching_card_has_plain_text_downloads_and_evidence_kind(self):
        card = progress.catalog(self.root)["updates"][0]
        self.assertTrue(card["available"])
        self.assertEqual(card["evidence_label"], "Illustrative model")
        self.assertNotIn("path", card["artifacts"][0])
        content, mime = progress.artifact_file(self.root, "demo-model", "report")
        self.assertEqual(content, b"# Synthetic software fixture\n")
        self.assertEqual(mime, "text/plain; charset=utf-8")

    def test_one_changed_file_withholds_whole_summary_and_all_downloads(self):
        self.result.write_text('{"measured":true}\n', encoding="utf-8")
        card = progress.catalog(self.root)["updates"][0]
        self.assertFalse(card["available"])
        self.assertNotIn("result", card)
        self.assertNotIn("artifacts", card)
        self.assertEqual(card["title"], "Progress entry needs review")
        with self.assertRaises(ValueError):
            progress.artifact_file(self.root, "demo-model", "report")

    def test_windows_line_endings_do_not_invalidate_same_text(self):
        self.report.write_bytes(b"# Synthetic software fixture\r\n")
        self.assertTrue(progress.catalog(self.root)["updates"][0]["available"])
        content, _ = progress.artifact_file(self.root, "demo-model", "report")
        self.assertNotIn(b"\r", content)

    def test_undeclared_private_absolute_and_traversal_paths_are_not_served(self):
        with self.assertRaises(ValueError):
            progress.artifact_file(self.root, "demo-model", "undeclared")
        original = copy.deepcopy(self.document)
        for name in ["data/private.json", "studies/../../private.json", str(self.report), "studies\\demo\\REPORT.md"]:
            with self.subTest(path=name):
                self.document = copy.deepcopy(original)
                self.document["updates"][0]["artifacts"][0]["path"] = name
                self.save()
                self.assertFalse(progress.catalog(self.root)["updates"][0]["available"])
                with self.assertRaises((ValueError, OSError)):
                    progress.artifact_file(self.root, "demo-model", "report")

    def test_symlink_does_not_make_an_external_file_a_study_artifact(self):
        external = self.root / "outside.md"
        external.write_bytes(self.report.read_bytes())
        link = self.report.with_name("linked.md")
        try:
            link.symlink_to(external)
        except OSError:
            self.skipTest("Host does not permit creating symlink test fixtures")
        self.document["updates"][0]["artifacts"][0]["path"] = "studies/demo/linked.md"
        self.save()
        self.assertFalse(progress.catalog(self.root)["updates"][0]["available"])

    def test_invalid_classification_and_duplicate_identifiers_are_rejected(self):
        self.document["updates"][0]["evidence_kind"] = "proven-human-rejuvenation"
        self.save()
        with self.assertRaises(ValueError):
            progress.catalog(self.root)
        self.document["updates"][0]["evidence_kind"] = "illustrative_model"
        self.document["updates"].append(copy.deepcopy(self.document["updates"][0]))
        self.save()
        with self.assertRaises(ValueError):
            progress.catalog(self.root)

    def test_http_read_only_routes_recheck_files_and_reject_ambiguous_ids(self):
        workspace = desk.Desk(self.root / "workspace")
        self.addCleanup(lambda: workspace.executor.shutdown(wait=True))
        patcher = patch.object(desk, "HOME", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        server = ThreadingHTTPServer(("127.0.0.1", 0), desk.make_handler(workspace))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
        self.addCleanup(connection.close)
        before = workspace.store_path.read_bytes()
        for url, status in [("/api/research-progress", 200),
            ("/api/research-progress/artifact?update_id=demo-model&artifact_id=report", 200),
            ("/api/research-progress/artifact?update_id=demo-model&update_id=other&artifact_id=report", 400),
            ("/api/research-progress/artifact?update_id=demo-model&artifact_id=missing", 400)]:
            connection.request("GET", url)
            response = connection.getresponse()
            self.assertEqual(response.status, status)
            response.read()
        self.assertEqual(workspace.store_path.read_bytes(), before)
        self.result.write_text("changed", encoding="utf-8")
        connection.request("GET", "/api/research-progress/artifact?update_id=demo-model&artifact_id=report")
        response = connection.getresponse()
        self.assertEqual(response.status, 400)
        response.read()

    def test_public_catalog_matches_local_files_and_keeps_goal_and_model_labels(self):
        cards = progress.catalog(ROOT)["updates"]
        self.assertTrue(cards)
        self.assertTrue(all(card["available"] for card in cards))
        self.assertIn("research_plan", {card["evidence_kind"] for card in cards})
        self.assertIn("illustrative_model", {card["evidence_kind"] for card in cards})
        self.assertIn("observational_reanalysis", {card["evidence_kind"] for card in cards})

    @unittest.skipUnless(shutil.which("node"), "Node runtime needed for frontend regression")
    def test_frontend_failed_refresh_withholds_previously_visible_results(self):
        subprocess.run([shutil.which("node"), str(ROOT / "tests/research_progress_ui.test.js")], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
