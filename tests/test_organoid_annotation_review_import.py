from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import regen_desk as desk
from import_organoid_annotation_review import (
    PUBLIC_FILES,
    ReceiptImportError,
    STUDY_RELATIVE,
    register_annotation_review,
)


class OrganoidAnnotationReviewImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        study = self.root / STUDY_RELATIVE
        study.mkdir(parents=True)
        document = json.loads((ROOT / STUDY_RELATIVE / "experiment.json").read_text(encoding="utf-8"))
        document["artifacts"] = [artifact for artifact in document["artifacts"]
                                if artifact.get("repository") != document["repository_id"]]
        document["modeling"].pop("result_artifact_id", None)
        document["analysis_history"] = []
        document["current_analysis_by_kind"] = {}
        (study / "experiment.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        tools_dir = self.root / "tools"
        (tools_dir / "schemas").mkdir(parents=True)
        for relative in (Path("validate_experiment_manifest.py"), Path("schemas/experiment-manifest.schema.json")):
            (tools_dir / relative).write_bytes((ROOT / "tools" / relative).read_bytes())

        self.audit = self.root / "audit"
        self.audit.mkdir()
        self.audit_id = "abcdef0123456789"
        pair = {
            "primary_task_id": "b-1111111111111111",
            "repeat_task_id": "b-2222222222222222",
            "source_frame_id": "source-frame-hidden",
            "biological_unit_id": "source-unit-hidden",
            "different_annotator_ids": True,
            "primary_annotator_id": "reviewer-a",
            "repeat_annotator_id": "reviewer-b",
            "foreground_dice": 0.75,
            "interpretation": "Segmentation agreement only.",
        }
        report = {
            "schema_version": 1,
            "activity": "manual_annotation_repeat_audit",
            "session_id": "0123456789abcdef",
            "audit_id": self.audit_id,
            "created_utc": "2026-10-06T12:00:00+00:00",
            "dataset": {
                "dataset_id": "10.60507/FK2/OM25XQ",
                "license": "CC-BY-4.0",
                "source_archive_sha256": "9a71323938338558eafcb169eeb3dffae98d3b1fec7947bafa71d64768a3358b",
            },
            "n_annotated_tasks": 2,
            "n_total_tasks": 3,
            "n_repeat_pairs_scored": 1,
            "n_repeat_pairs_with_distinct_annotator_ids": 1,
            "biological_results_generated": False,
            "annotation_review_needed": True,
            "interpretation": "Manual segmentation agreement only; no biological effect.",
            "repeat_agreement": [pair],
        }
        (self.audit / "audit_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (self.audit / "repeat_agreement.csv").write_text(
            "primary_task_id,repeat_task_id,different_annotator_ids,foreground_dice\n"
            "b-1111111111111111,b-2222222222222222,true,0.75\n", encoding="utf-8")
        for filename in PUBLIC_FILES:
            raw = (self.audit / filename).read_bytes()
            self.output_record = getattr(self, "output_record", {})
            self.output_record[filename] = {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
        (self.audit / "audit_receipt.json").write_text(json.dumps({
            "schema_version": 1,
            "tool": "organoid-phenotyping",
            "activity": "manual_annotation_repeat_audit",
            "session_id": report["session_id"],
            "audit_id": self.audit_id,
            "pilot_receipt_sha256": "a" * 64,
            "input_manifest_sha256": "b" * 64,
            "study_plan_sha256": "c" * 64,
            "n_annotated_tasks": 2,
            "n_total_tasks": 3,
            "n_repeat_pairs_scored": 1,
            "n_repeat_pairs_with_distinct_annotator_ids": 1,
            "biological_results_generated": False,
            "annotation_mask_sha256": {
                "b-1111111111111111": "d" * 64,
                "b-2222222222222222": "e" * 64,
            },
            "outputs": self.output_record,
        }, indent=2) + "\n", encoding="utf-8")

    def test_registers_review_history_and_researchdesk_summary_without_biology_claim(self):
        result = register_annotation_review(self.audit, self.root)
        self.assertFalse(result["biological_results_generated"])
        self.assertFalse(result["annotated_manifest_imported"])
        self.assertEqual(result["registered_artifacts"], 3)
        study_path = self.root / STUDY_RELATIVE / "experiment.json"
        document = json.loads(study_path.read_text(encoding="utf-8"))
        self.assertEqual(len(document["analysis_history"]), 1)
        self.assertEqual(document["analysis_history"][0]["kind"], "annotation_review")
        artifact_ids = {artifact["id"] for artifact in document["artifacts"]}
        self.assertTrue(any(value.startswith("organoid-review-audit-report-") for value in artifact_ids))
        with patch.object(desk, "HOME", self.root.resolve()):
            cards = desk.Desk.experiments(object.__new__(desk.Desk))["experiments"]
        card = next(value for value in cards if value["experiment_id"] == document["experiment_id"])
        self.assertEqual(card["validation_status"], "valid", card)
        self.assertEqual(card["annotation_reviews"][0]["n_repeat_pairs_with_distinct_annotator_ids"], 1)
        self.assertTrue(any(row["artifact_id"].startswith("organoid-review-repeat-agreement-")
                            for row in card["tables"]))

        previous_ids = {artifact["id"] for artifact in document["artifacts"]}
        register_annotation_review(self.audit, self.root)
        repeated = json.loads(study_path.read_text(encoding="utf-8"))
        self.assertEqual({artifact["id"] for artifact in repeated["artifacts"]}, previous_ids)
        self.assertEqual(len(repeated["analysis_history"]), 1)

    def test_rejects_changed_agreement_output_without_changing_manifest(self):
        (self.audit / "repeat_agreement.csv").write_text("corrupted\n", encoding="utf-8")
        with self.assertRaisesRegex(ReceiptImportError, "failed its receipt hash"):
            register_annotation_review(self.audit, self.root)
        document = json.loads((self.root / STUDY_RELATIVE / "experiment.json").read_text(encoding="utf-8"))
        self.assertEqual(document["analysis_history"], [])


if __name__ == "__main__":
    unittest.main()
