from __future__ import annotations

import base64
import csv
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
from import_organoid_annotation_pilot import (
    BONN_DATASET_ID,
    BONN_SOURCE_ARCHIVE_SHA256,
    PUBLIC_FILES,
    QUEUE_FIELDS,
    ReceiptImportError,
    STUDY_RELATIVE,
    register_annotation_pilot,
)


class OrganoidAnnotationPilotImportTests(unittest.TestCase):
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
        self.study_manifest = study / "experiment.json"
        self.study_manifest.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        config = self.root / "config"
        config.mkdir()
        (config / "research-blueprints.json").write_bytes(
            (ROOT / "config" / "research-blueprints.json").read_bytes()
        )
        tools_dir = self.root / "tools"
        (tools_dir / "schemas").mkdir(parents=True)
        for relative in (Path("validate_experiment_manifest.py"), Path("schemas/experiment-manifest.schema.json")):
            (tools_dir / relative).write_bytes((ROOT / "tools" / relative).read_bytes())

        self.source = self.root / "source"
        (self.source / "images").mkdir(parents=True)
        self.manifest = self.source / "acquisitions.csv"
        self.plan = self.source / "study-plan.json"
        self.output = self.root / "pilot"
        (self.output / "public" / "images").mkdir(parents=True)
        (self.output / "curator").mkdir()

        source_rows = [
            {"frame_id": "frame-a", "biological_unit_id": "kidney_a", "culture_condition": "Domes",
             "treatment": "DMSO", "technical_replicate": "A", "timepoint_h": "24",
             "image_path": "images/frame-a.tif", "status": "pending_annotation"},
            {"frame_id": "frame-b", "biological_unit_id": "kidney_b", "culture_condition": "Suspension",
             "treatment": "Forskolin", "technical_replicate": "B", "timepoint_h": "24",
             "image_path": "images/frame-b.tif", "status": "pending_annotation"},
            {"frame_id": "frame-test", "biological_unit_id": "kidney_test", "culture_condition": "Domes",
             "treatment": "Media", "technical_replicate": "C", "timepoint_h": "24",
             "image_path": "images/frame-test.tif", "status": "pending_annotation"},
        ]
        for row in source_rows:
            (self.source / row["image_path"]).write_bytes(f"TIFF fixture {row['frame_id']}".encode())
        with self.manifest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(source_rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(source_rows)
        self.plan.write_text(json.dumps({
            "schema_version": 1,
            "dataset": {"dataset_id": BONN_DATASET_ID, "license": "CC-BY-4.0",
                        "source_archive_sha256": BONN_SOURCE_ARCHIVE_SHA256},
            "split": {"frozen_before_model_fit": True, "grouping_field": "biological_unit_id",
                      "development_group_ids": ["kidney_a", "kidney_b"],
                      "final_test_group_ids": ["kidney_test"]},
        }, indent=2) + "\n", encoding="utf-8")

        self.tasks = [
            ("b-1111111111111111", "primary", source_rows[0], "whole_tubuloid_outer_boundary", ""),
            ("b-2222222222222222", "primary", source_rows[1], "visible_cyst_boundary", ""),
            ("b-3333333333333333", "concealed_repeat", source_rows[0], "whole_tubuloid_outer_boundary", "b-1111111111111111"),
        ]
        public_queues = {"annotation_queue_round1.csv": [], "annotation_queue_round2.csv": []}
        key_rows = []
        for task_id, round_name, source_row, target, repeat_of in self.tasks:
            source_path = self.source / source_row["image_path"]
            raw = source_path.read_bytes()
            image_hash = hashlib.sha256(raw).hexdigest()
            queue_row = {
                "task_id": task_id,
                "image_path": f"images/{task_id}.tif",
                "image_sha256": image_hash,
                "annotation_target": target,
                "mask_path": f"masks/{task_id}.tif",
                "status": "pending_annotation",
                "status_reason": "Awaiting manual annotation; no mask has been generated.",
                "annotator_id": "",
                "annotation_protocol_version": "bonn-cyst-annotation-pilot-0.1",
            }
            public_queues["annotation_queue_round1.csv" if round_name == "primary"
                          else "annotation_queue_round2.csv"].append(queue_row)
            (self.output / "public" / queue_row["image_path"]).write_bytes(raw)
            key_rows.append({
                "task_id": task_id,
                "round": round_name,
                "frame_id": source_row["frame_id"],
                "biological_unit_id": source_row["biological_unit_id"],
                "culture_condition": source_row["culture_condition"],
                "treatment": source_row["treatment"],
                "technical_replicate": source_row["technical_replicate"],
                "timepoint_h": source_row["timepoint_h"],
                "source_image_path": source_row["image_path"],
                "source_image_sha256": image_hash,
                "repeat_of_task_id": repeat_of,
            })
        for filename, rows in public_queues.items():
            with (self.output / "public" / filename).open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(QUEUE_FIELDS), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        with (self.output / "curator" / "assignment_key.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(key_rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(key_rows)
        key_bytes = (self.output / "curator" / "assignment_key.csv").read_bytes()

        protocol = b"# Provisional protocol\nNo masks or biological results.\n"
        tiny_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jS7sAAAAASUVORK5CYII="
        )
        pilot_plan = {
            "schema_version": 1,
            "pilot_id": "bonn-kidney-cyst-annotation-24h-v1",
            "purpose": "Manual mask-workflow usability and repeatability; no biological effect estimate.",
            "dataset_id": BONN_DATASET_ID,
            "license": "CC-BY-4.0",
            "source_archive_sha256": BONN_SOURCE_ARCHIVE_SHA256,
            "acquisition_manifest_sha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
            "study_plan_sha256": hashlib.sha256(self.plan.read_bytes()).hexdigest(),
            "selection": {"timepoint_h": 24, "n_unique_frames": 2, "n_round1_tasks": 2,
                          "n_round2_concealed_repeat_tasks": 1, "n_total_tasks": 3,
                          "n_development_source_groups_represented": 2, "final_test_group_excluded": True},
            "masks_generated": False,
            "biological_results_generated": False,
            "blinding_limit": "Appearance may reveal condition.",
        }
        payloads = {
            "annotation_queue_round1.csv": (self.output / "public" / "annotation_queue_round1.csv").read_bytes(),
            "annotation_queue_round2.csv": (self.output / "public" / "annotation_queue_round2.csv").read_bytes(),
            "annotation_protocol.md": protocol,
            "pilot_plan.json": (json.dumps(pilot_plan, indent=2) + "\n").encode(),
            "annotation_contact_sheet.png": tiny_png,
        }
        (self.output / "public" / "annotation_protocol.md").write_bytes(protocol)
        (self.output / "public" / "pilot_plan.json").write_bytes(payloads["pilot_plan.json"])
        (self.output / "public" / "annotation_contact_sheet.png").write_bytes(tiny_png)
        receipt = {
            "schema_version": 1,
            "tool": "organoid-phenotyping",
            "activity": "manual_annotation_pilot_plan",
            "dataset": {"dataset_id": BONN_DATASET_ID, "license": "CC-BY-4.0",
                        "source_archive_sha256": BONN_SOURCE_ARCHIVE_SHA256},
            "input_manifest_sha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
            "study_plan_sha256": hashlib.sha256(self.plan.read_bytes()).hexdigest(),
            "timepoint_h": 24,
            "n_unique_frames": 2,
            "n_round1_tasks": 2,
            "n_round2_concealed_repeat_tasks": 1,
            "n_total_tasks": 3,
            "n_development_source_groups": 2,
            "excluded_final_test_group_ids": ["kidney_test"],
            "selected_final_test_overlap": [],
            "masks_generated": False,
            "biological_results_generated": False,
            "private_assignment_key_sha256": hashlib.sha256(key_bytes).hexdigest(),
            "private_assignment_key_path": "curator/assignment_key.csv",
            "outputs": {name: hashlib.sha256(raw).hexdigest() for name, raw in payloads.items()},
        }
        (self.output / "curator" / "pilot_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    def test_registers_only_hash_checked_public_artifacts_and_researchdesk_summary(self):
        result = register_annotation_pilot(self.output, self.manifest, self.plan, self.root)
        self.assertEqual(result["registered_artifacts"], len(PUBLIC_FILES))
        self.assertEqual(result["n_unique_frames"], 2)
        self.assertEqual(result["n_total_tasks"], 3)
        self.assertFalse(result["private_assignment_key_imported"])
        self.assertFalse(result["masks_generated"])
        self.assertEqual(result["assay_status"], "not_available")

        document = json.loads(self.study_manifest.read_text(encoding="utf-8"))
        self.assertEqual(document["assays"][0]["status"], "not_available")
        self.assertNotIn("result_artifact_id", document["modeling"])
        self.assertEqual(sum(item["id"].startswith("organoid-pilot-")
                             for item in document["artifacts"]), len(PUBLIC_FILES))
        bundle = self.root / result["bundle_path"]
        self.assertEqual({path.name for path in bundle.iterdir()}, set(PUBLIC_FILES))
        self.assertFalse((bundle / "assignment_key.csv").exists())
        self.assertFalse((bundle / "images").exists())

        with patch.object(desk, "HOME", self.root.resolve(strict=True)):
            workspace = desk.Desk(self.root / "desk")
            self.addCleanup(lambda: workspace.executor.shutdown(wait=True))
            record = next(item for item in workspace.experiments()["experiments"]
                          if item["experiment_id"] == "bonn-kidney-tubuloid-cyst-induction-imaging")
            contact = next(artifact for artifact in record["artifacts"]
                           if artifact["id"].startswith("organoid-pilot-contact-sheet-"))
            self.assertTrue(contact["previewable"])
            image_bytes, content_type = workspace.experiment_artifact(record["experiment_id"], contact["id"])
        self.assertEqual(record["validation_status"], "valid", record.get("validation_error"))
        self.assertEqual(record["assays"][0]["status"], "not_available")
        pilot = record["annotation_pilots"][0]
        self.assertEqual(pilot["n_total_tasks"], 3)
        self.assertTrue(pilot["final_test_group_excluded"])
        self.assertTrue(any(table["artifact_id"].startswith("organoid-pilot-queue1-")
                            for table in record["tables"]))
        self.assertEqual(content_type, "image/png")
        self.assertTrue(image_bytes.startswith(b"\x89PNG\r\n\x1a\n"))
        artifact_ids_before = {artifact["id"] for artifact in document["artifacts"]}
        register_annotation_pilot(self.output, self.manifest, self.plan, self.root)
        reimported = json.loads(self.study_manifest.read_text(encoding="utf-8"))
        self.assertEqual({artifact["id"] for artifact in reimported["artifacts"]}, artifact_ids_before)
        self.assertEqual(len(reimported["analysis_history"]), 1)
        self.assertEqual(reimported["current_analysis_by_kind"]["annotation_pilot"], result["bundle_path"].rsplit("-", 1)[-1])

    def test_rejects_changed_public_bytes_without_mutating_study_record(self):
        before = self.study_manifest.read_bytes()
        queue = self.output / "public" / "annotation_queue_round1.csv"
        queue.write_bytes(queue.read_bytes() + b"\n")
        with self.assertRaisesRegex(ReceiptImportError, "output hash mismatch"):
            register_annotation_pilot(self.output, self.manifest, self.plan, self.root)
        self.assertEqual(self.study_manifest.read_bytes(), before)
        self.assertFalse((self.root / STUDY_RELATIVE / "derived").exists())

    def test_rejects_queue_that_exposes_source_treatment(self):
        queue_path = self.output / "public" / "annotation_queue_round1.csv"
        with queue_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        fields = list(rows[0]) + ["treatment"]
        for row, task in zip(rows, self.tasks):
            row["treatment"] = task[2]["treatment"]
        with queue_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        receipt_path = self.output / "curator" / "pilot_receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["outputs"]["annotation_queue_round1.csv"] = hashlib.sha256(queue_path.read_bytes()).hexdigest()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ReceiptImportError, "exactly the approved blinded annotation fields"):
            register_annotation_pilot(self.output, self.manifest, self.plan, self.root)


if __name__ == "__main__":
    unittest.main()
