"""New default-area migration and typed campaign scopes; no biological tests."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        for key, count in [("dental",7),("organoids",3)]:
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
        attachment_summary = next(e for e in periodontal["evidence"] if e["axis_id"]=="attachment")
        self.assertEqual(attachment_summary["status"],"source reports mixed signal")
        self.assertIn("1.905 mm", attachment_summary["value"])
        self.assertIn("no significant between-group CAL", attachment_summary["value"])
        self.assertIn("no significant",periodontal["structure_notes"])

    def test_ips_pdl_starter_preserves_iPSC_line_and_batch_scope(self):
        seeds = json.loads((desk.HOME / "config/research-blueprints.json").read_text(encoding="utf-8"))
        starter = next(s for s in seeds["campaign_starters"]["dental"] if s["id"] == "ips-pdl-cell-function")
        self.assertEqual(len(starter["evidence_records"]), 2)
        source_record = starter["evidence_records"][0]
        self.assertIn("same iPSC line", source_record["independent_unit"])
        self.assertIn("batch #1", starter["structure_notes"])
        graft_record = starter["evidence_records"][1]
        self.assertIn("subcutaneous", graft_record["model_system"])
        self.assertIn("not stated", graft_record["sample_size"].lower())
        self.assertIn("load transfer", graft_record["notes"].lower())
        with tempfile.TemporaryDirectory() as directory:
            instance = desk.Desk(Path(directory))
            self.addCleanup(lambda: instance.executor.shutdown(wait=True))
            saved = instance.campaign({**starter, "starter_id": starter["id"], "blueprint_id": "dental", "id": ""})
            self.assertEqual(saved["evidence_records"][0]["independent_unit"], source_record["independent_unit"])
            self.assertIn("One iPSC line", saved["evidence_records"][0]["sample_size"])

    def test_orthotopic_rat_starter_keeps_ankylosis_and_animal_denominator(self):
        seeds = json.loads((desk.HOME / "config/research-blueprints.json").read_text(encoding="utf-8"))
        starter = next(s for s in seeds["campaign_starters"]["dental"] if s["id"] == "ips-bmp6-rat-periodontal-defect")
        record = starter["evidence_records"][0]
        self.assertIn("n=4/group", record["sample_size"])
        self.assertIn("ankylosis", record["notes"].lower())
        self.assertIn("iPSCs-only", record["comparator"])
        self.assertEqual(record["status"], "source reports mixed signal")

    def test_root_preseeding_starter_keeps_timing_conflict_and_nested_denominator(self):
        seeds = json.loads((desk.HOME / "config/research-blueprints.json").read_text(encoding="utf-8"))
        starter = next(s for s in seeds["campaign_starters"]["dental"] if s["id"] == "pdl-progenitor-root-preseed-replant")
        record = starter["evidence_records"][0]
        self.assertIn("four athymic nude rats", record["sample_size"].lower())
        self.assertIn("eight molars", record["sample_size"].lower())
        self.assertIn("six months", record["follow_up"].lower())
        self.assertIn("six weeks", record["follow_up"].lower())
        self.assertIn("no direct mobility", record["notes"].lower())
        self.assertEqual(record["status"], "source reports positive signal")

    def test_fulltext_observations_roundtrip_with_outcome_specific_intervals(self):
        seeds = json.loads((desk.HOME / "config/research-blueprints.json").read_text(encoding="utf-8"))
        authored = json.loads((desk.HOME / "studies/dental-regeneration-2026-10-09/endpoint_review.json").read_text(encoding="utf-8"))
        starter = next(s for s in seeds["campaign_starters"]["dental"] if s["id"] == "periodontal-controlled-contrasts")
        self.assertEqual(starter["evidence_records"], authored["evidence_records"])
        with tempfile.TemporaryDirectory() as directory:
            instance = desk.Desk(Path(directory))
            self.addCleanup(lambda: instance.executor.shutdown(wait=True))
            saved = instance.campaign({**starter, "starter_id": starter["id"], "blueprint_id": "dental", "id": ""})
            records = saved["evidence_records"]
            self.assertEqual(len(records), 6)
            self.assertEqual(len({r["record_id"] for r in records}), 6)
            self.assertIn("12 months", records[0]["follow_up"])
            self.assertTrue(records[1]["follow_up"].startswith("3 months"))
            self.assertIn("post hoc", records[2]["stage_track"].lower())
            self.assertIn("-0.64", records[2]["value"])
            self.assertIn("1.905 mm", records[3]["value"])
            self.assertIn("8 ASC+PRP and 6 EMD", records[3]["sample_size"])
            self.assertIn("no significant", records[4]["value"])
            self.assertIn("equivalence margin", records[4]["notes"])
            self.assertIn("16 consented", records[5]["value"])
            self.assertEqual(records[5]["status"], "source reports mixed signal")
            self.assertTrue(all(not r["dataset_sha256"] for r in records))
            saved = instance.campaign({**saved, "title": "Edited research question"})
            self.assertEqual([r["record_id"] for r in saved["evidence_records"]], [r["record_id"] for r in records])

    def test_missing_manifest_dependency_returns_an_invalid_card_without_thread_exit(self):
        validator = desk.experiment_manifest_tools()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instance = desk.Desk(root / "state")
            self.addCleanup(lambda: instance.executor.shutdown(wait=True))
            folder = root / "studies" / "constructed-fixture"
            folder.mkdir(parents=True)
            (folder / "experiment.json").write_text("{}", encoding="utf-8")
            with patch.object(desk, "HOME", root), patch.object(desk, "experiment_manifest_tools", return_value=validator), patch.object(validator, "jsonschema", None):
                result = instance.experiments()
            self.assertEqual(len(result["experiments"]), 1)
            self.assertEqual(result["experiments"][0]["validation_status"], "invalid")
            self.assertIn("jsonschema is required", result["experiments"][0]["validation_error"])


if __name__ == "__main__":
    unittest.main()
