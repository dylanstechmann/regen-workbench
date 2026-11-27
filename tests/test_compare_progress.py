"""Check the portable ResearchDesk catalog revision comparison."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
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
