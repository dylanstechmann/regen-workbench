from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import regen_desk as desk


class EctogenesisDeskTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.desk = desk.Desk(self.root)
        self.addCleanup(lambda: self.desk.executor.shutdown(wait=True))

    def test_starter_campaigns_keep_complete_gestation_unassessed_and_growth_limits_visible(self):
        state = self.desk.state()
        self.assertTrue(any(item["id"] == "ectogenesis" for item in state["blueprints"]))
        saved = []
        for starter in state["campaign_starters"]["ectogenesis"]:
            data = {key: value for key, value in starter.items() if key != "id"}
            saved.append(self.desk.campaign({"blueprint_id": "ectogenesis", **data}))
        complete = next(item for item in saved if item["title"] == "Complete ectogenesis capability map")
        axis = next(item for item in complete["evidence"] if item["axis_id"] == "complete_gestation")
        self.assertEqual(axis["status"], "not assessed")
        partial = next(item for item in saved if item["title"] == "Partial support versus normal development")
        growth = next(item for item in partial["evidence"] if item["axis_id"] == "developmental_outcomes")
        self.assertEqual(growth["status"], "source reports mixed signal")
        self.assertIn("reduced", growth["value"])

    def test_seed_migration_adds_area_and_preserves_saved_questions_and_focus_priorities(self):
        self.desk.store["blueprints"] = [item for item in self.desk.store["blueprints"]
                                         if item["id"] != "ectogenesis"]
        organs = next(item for item in self.desk.store["blueprints"] if item["id"] == "organs")
        organs["question"] = "My saved research question"
        self.desk.save_store()
        reloaded = desk.Desk(self.root)
        self.addCleanup(lambda: reloaded.executor.shutdown(wait=True))
        identifiers = [item["id"] for item in reloaded.store["blueprints"]]
        self.assertEqual(identifiers[:3], ["reprogramming", "tissues", "nanomedicine"])
        self.assertEqual(identifiers.count("ectogenesis"), 1)
        self.assertEqual(identifiers.index("ectogenesis"), identifiers.index("organs") + 1)
        organs = next(item for item in reloaded.store["blueprints"] if item["id"] == "organs")
        self.assertEqual(organs["question"], "My saved research question")


if __name__ == "__main__":
    unittest.main()
