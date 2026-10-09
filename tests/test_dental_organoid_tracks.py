"""New default-area migration and typed campaign scopes; no biological tests."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import regen_desk as desk


class DentalOrganoidTracks(unittest.TestCase):
    def test_seed_migration_preserves_saved_question_and_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            first = desk.Desk(Path(directory))
            first.executor.shutdown(wait=True)
            first.store["blueprints"] = [p for p in first.store["blueprints"] if p["id"] not in {"dental","organoids"}]
            first.store["blueprints"][0]["question"] = "Saved user question"
            first.store["notes"] = [{"claim":"Saved observation"}]
            first.save_store()
            second = desk.Desk(Path(directory))
            self.addCleanup(lambda: second.executor.shutdown(wait=True))
            self.assertEqual(second.store["blueprints"][0]["question"],"Saved user question")
            self.assertEqual(second.store["notes"],[{"claim":"Saved observation"}])
            ids = [p["id"] for p in second.store["blueprints"]]
            self.assertIn("dental",ids)
            self.assertIn("organoids",ids)
            self.assertEqual(len(ids),len(set(ids)))

    def test_campaign_evidence_axes_and_scopes_are_explicit(self):
        seeds = json.loads((desk.HOME / "config/research-blueprints.json").read_text(encoding="utf-8"))
        for key, count in [("dental",4),("organoids",2)]:
            axes = {axis["id"] for axis in seeds["campaign_frameworks"][key]}
            starters = seeds["campaign_starters"][key]
            self.assertEqual(len(starters),count)
            self.assertEqual(len({s["id"] for s in starters}),count)
            for s in starters:
                for field in ("hypothesis","endpoint","falsifier","evidence_stage","study_design","structure_notes"):
                    self.assertTrue(s[field].strip())
                self.assertTrue(s["reference_url"].startswith("https://"))
                for e in s["evidence"]:
                    self.assertIn(e["axis_id"],axes)
                    self.assertIn(e["status"],desk.EVIDENCE_STATUS)
        periodontal = next(s for s in seeds["campaign_starters"]["dental"] if s["id"]=="periodontal-controlled-contrasts")
        self.assertEqual(periodontal["evidence"][0]["status"],"source reports no signal")
        self.assertIn("no significant",periodontal["structure_notes"])


if __name__ == "__main__":
    unittest.main()
