"""Public exports include only pinned progress files, never local workspace state."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_public_desk as public

REVISION = "a" * 40


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        self.urls.extend(value for key, value in attrs if key in {"href", "src"})


class PublicDeskTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repository"
        self.report = self.repo / "studies/example/REPORT.md"
        self.report.parent.mkdir(parents=True)
        self.content = '# Example <script>alert("unsafe")</script>\nNot biological data.\n'
        self.report.write_text(self.content, encoding="utf-8", newline="\n")
        self.index = self.repo / "tools/data/research-progress.json"
        self.index.parent.mkdir(parents=True)
        content = self.content.encode("utf-8")
        self.document = {"schema_version": 1, "updates": [{"id": "example-entry", "title": "Example <entry>",
            "topic": "Example & fixture", "updated_on": "2026-10-22", "evidence_kind": "software_fixture",
            "result": "Synthetic fixture only.", "boundary": "No biological inference.", "next_step": "Use measured inputs.",
            "artifacts": [{"id": "report", "label": "Read <report>", "path": "studies/example/REPORT.md",
                "sha256_lf_text": hashlib.sha256(content).hexdigest(), "bytes_utf8_lf": len(content)}]}]}
        self.save()
        self.output = self.root / "site"

    def save(self):
        self.index.write_text(json.dumps(self.document), encoding="utf-8")

    def test_only_explicit_pinned_artifacts_are_exported_with_evidence_labels(self):
        for name in ["data/research-desk/store.json", ".env", "studies/example/undeclared.md"]:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("PRIVATE SENTINEL", encoding="utf-8")
        result = public.build(self.output, repo_root=self.repo, revision=REVISION)
        self.assertEqual(result["artifacts"], 1)
        self.assertEqual(result["files"], 7)
        exported = list(self.output.rglob("*"))
        self.assertFalse(any("PRIVATE SENTINEL" in p.read_text(encoding="utf-8") for p in exported if p.is_file()))
        self.assertEqual((self.output / "artifacts/example-entry/report.txt").read_text(encoding="utf-8"), self.content)
        reader = (self.output / "artifacts/example-entry/report.html").read_text(encoding="utf-8")
        self.assertNotIn('<script>alert("unsafe")</script>', reader)
        self.assertIn("&lt;script&gt;", reader)
        self.assertIn(f"/blob/{REVISION}/studies/example/REPORT.md", reader)
        catalog = json.loads((self.output / "catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["updates"][0]["evidence_kind"], "software_fixture")
        self.assertEqual(catalog["source_revision"], REVISION)

    def test_changed_or_nonstudy_artifact_aborts_before_any_output(self):
        self.report.write_text("Changed result", encoding="utf-8")
        with self.assertRaises(ValueError):
            public.build(self.output, repo_root=self.repo, revision=REVISION)
        self.assertFalse(self.output.exists())
        self.document["updates"][0]["artifacts"][0]["path"] = "data/research-desk/store.json"
        self.save()
        with self.assertRaises(ValueError):
            public.build(self.output, repo_root=self.repo, revision=REVISION)
        self.assertFalse(self.output.exists())

    def test_existing_output_is_never_overwritten_and_source_sha_is_required(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaises(ValueError):
            public.build(self.output, repo_root=self.repo, revision=REVISION)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        with self.assertRaises(ValueError):
            public.build(self.root / "other", repo_root=self.repo, revision="main")

    def test_all_public_files_work_beneath_a_project_site_subdirectory(self):
        public.build(self.output, repo_root=ROOT, revision=REVISION)
        catalog = json.loads((self.output / "catalog.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(catalog["count"], 20)
        for path in self.output.rglob("*.html"):
            parser = Links()
            parser.feed(path.read_text(encoding="utf-8"))
            for value in parser.urls:
                parsed = urlsplit(value)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                with self.subTest(page=path.name, link=value):
                    self.assertFalse(parsed.path.startswith("/"), "Project-site links must be relative")
                    target = (path.parent / unquote(parsed.path)).resolve()
                    target.relative_to(self.output.resolve())
                    self.assertTrue(target.is_file())
        for path in [self.output / "index.html", self.output / "app.js"]:
            self.assertNotIn("/api/", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
