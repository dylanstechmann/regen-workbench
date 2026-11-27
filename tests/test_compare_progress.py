"""Check the portable ResearchDesk catalog revision comparison."""

import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_public_desk as public
from compare_progress import compare


class CompareProgressTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.before = Path(tmp.name) / "before.json"
        self.after = self.before.with_name("after.json")
        catalog = json.loads((ROOT / "tools/data/research-progress.json").read_text(encoding="utf-8"))
        self.rows = copy.deepcopy(catalog["updates"][:3])
        self.save(self.before, self.rows)

    def save(self, path, rows):
        path.write_text(json.dumps({"schema_version": 1, "updates": rows}), encoding="utf-8")

    def test_reordering_is_ignored(self):
        for row in self.rows:
            row["artifacts"].reverse()
        self.save(self.after, self.rows[::-1])
        self.assertEqual(compare(self.before, self.after), {
            "schema_version": 1, "added_entries": [], "removed_entries": [], "changed_entries": []})

    def test_reports_new_removed_and_modified_entries_and_artifacts(self):
        modified, deleted, renamed = self.rows
        removed_entry = deleted["id"]
        old_boundary = modified["boundary"]
        modified["boundary"] = "Changed synthetic scope"
        renamed["id"] = "new-entry-id"
        reports = modified["artifacts"]
        reports[:] = reports[:1]
        original = reports[0]["sha256_lf_text"]
        reports[0]["sha256_lf_text"] = "f" * 64
        reports.append(dict(reports[0], id="new-artifact-id"))
        self.save(self.after, [renamed, modified])
        result = compare(self.before, self.after)
        self.assertIn(removed_entry, result["removed_entries"])
        self.assertEqual(result["added_entries"], ["new-entry-id"])
        changed, = result["changed_entries"]
        self.assertEqual(changed["changed_fields"]["boundary"],
                         {"before": old_boundary, "after": modified["boundary"]})
        self.assertEqual(changed["artifacts"][reports[0]["id"]]["changed_fields"]["sha256_lf_text"],
                         {"before": original, "after": "f" * 64})
        self.assertIsNone(changed["artifacts"]["new-artifact-id"]["before"])

    def test_duplicate_ids_are_rejected_before_comparing(self):
        self.save(self.after, [self.rows[0], self.rows[0]])
        with self.assertRaisesRegex(ValueError, "unique"):
            compare(self.before, self.after)


class CatalogPublicationBoundaryTests(unittest.TestCase):
    def test_metadata_diff_is_visible_but_mutated_pinned_artifact_is_not_publishable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repository"
            source_catalog = ROOT / "tools/data/research-progress.json"
            before = root / "before.json"
            before.write_bytes(source_catalog.read_bytes())
            document = json.loads(source_catalog.read_text(encoding="utf-8"))
            original_result = document["updates"][0]["result"]
            document["updates"][0]["result"] = "Synthetic metadata revision in a temporary catalog copy."
            artifact = document["updates"][0]["artifacts"][0]
            declared_artifact = copy.deepcopy(artifact)

            for row in document["updates"]:
                for declared in row["artifacts"]:
                    source = ROOT / declared["path"]
                    target = repo / declared["path"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)

            after = repo / "tools/data/research-progress.json"
            after.parent.mkdir(parents=True)
            after.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            report = compare(before, after)
            changed, = report["changed_entries"]
            self.assertEqual(changed["id"], document["updates"][0]["id"])
            self.assertEqual(changed["changed_fields"]["result"], {
                "before": original_result,
                "after": "Synthetic metadata revision in a temporary catalog copy.",
            })
            self.assertEqual(changed["artifacts"], {})
            self.assertEqual(artifact, declared_artifact)

            mutated_path = repo / artifact["path"]
            original = mutated_path.read_bytes()
            mutation_at = next(index for index, value in enumerate(original) if 32 <= value <= 126)
            mutated = bytearray(original)
            mutated[mutation_at] ^= 1
            mutated_path.write_bytes(mutated)
            self.assertEqual(len(mutated), artifact["bytes_utf8_lf"])
            self.assertEqual(sum(old != new for old, new in zip(original, mutated)), 1)
            self.assertEqual(artifact, declared_artifact, "The declared size and SHA-256 must remain unchanged")

            output = root / "public-site"
            with self.assertRaisesRegex(ValueError, "differs from the reviewed catalog version"):
                public.build(output, repo_root=repo, revision="a" * 40)
            self.assertFalse(output.exists())
            self.assertEqual((ROOT / artifact["path"]).read_bytes(), original)
