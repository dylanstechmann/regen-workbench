from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from import_organoid_phenotyping import ReceiptImportError, OUTPUTS, STUDY_RELATIVE, register_receipt


class OrganoidPhenotypingImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        study = self.root / STUDY_RELATIVE
        study.mkdir(parents=True)
        shutil.copyfile(
            ROOT / STUDY_RELATIVE / "experiment.json",
            study / "experiment.json",
        )
        # The checked-in working tree may already contain a successful local
        # intake. Keep this isolated test fixture independent of that bundle.
        study_manifest = study / "experiment.json"
        document = json.loads(study_manifest.read_text(encoding="utf-8"))
        document["artifacts"] = [
            artifact for artifact in document["artifacts"]
            if not artifact["id"].startswith(("phenotyping-", "organoid-pilot-"))
        ]
        document["modeling"].pop("result_artifact_id", None)
        document["analysis_history"] = []
        document["current_analysis_by_kind"] = {}
        study_manifest.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        self.output = self.root / "package-output"
        self.output.mkdir()
        self.manifest = self.root / "acquisitions.csv"
        self.plan = self.root / "study-plan.json"
        self.manifest.write_text("frame_id,status\nimage_1,pending_annotation\n", encoding="utf-8")
        self.plan.write_text('{"schema_version":1}\n', encoding="utf-8")
        output_hashes = {}
        for filename in OUTPUTS:
            data = (f"frame_id,value\nfixture,{filename}\n").encode("utf-8")
            (self.output / filename).write_bytes(data)
            output_hashes[filename] = hashlib.sha256(data).hexdigest()
        (self.output / "receipt.json").write_text(json.dumps({
            "schema_version": 1,
            "tool": "organoid-phenotyping",
            "tool_version": "0.1.0",
            "dataset": {"dataset_id": "10.60507/FK2/OM25XQ", "license": "CC-BY-4.0",
                        "source_archive_sha256": "9a71323938338558eafcb169eeb3dffae98d3b1fec7947bafa71d64768a3358b"},
            "input_manifest_sha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
            "study_plan_sha256": hashlib.sha256(self.plan.read_bytes()).hexdigest(),
            "n_manifest_rows": 1,
            "n_measured_frames": 0,
            "n_pending_annotation_frames": 1,
            "n_missing_frames": 0,
            "n_failed_frames": 0,
            "n_biological_units": 5,
            "split": {"specimen_overlap": [], "grouping_field": "biological_unit_id",
                      "grouping_unit": "source kidney identifier", "development_group_count": 4,
                      "final_test_group_count": 1},
            "object_tracking": {"status": "no_track_map", "n_tracked_object_trajectories": 0},
            "outputs": output_hashes,
        }, indent=2) + "\n", encoding="utf-8")

    def test_registers_hash_checked_outputs_and_keeps_biological_assay_unavailable(self):
        result = register_receipt(self.output, self.manifest, self.plan, self.root)
        self.assertEqual(result["assay_status"], "not_available")
        self.assertEqual(result["registered_artifacts"], len(OUTPUTS) + 1)
        document = json.loads((self.root / STUDY_RELATIVE / "experiment.json").read_text(encoding="utf-8"))
        self.assertEqual(document["assays"][0]["status"], "not_available")
        self.assertNotIn("raw_artifact_id", document["assays"][0])
        self.assertTrue(document["modeling"]["result_artifact_id"].startswith("phenotyping-receipt-"))
        self.assertTrue((self.root / result["bundle_path"] / "objects.csv").is_file())
        first_artifact_ids = {artifact["id"] for artifact in document["artifacts"]}
        register_receipt(self.output, self.manifest, self.plan, self.root)
        reimported = json.loads((self.root / STUDY_RELATIVE / "experiment.json").read_text(encoding="utf-8"))
        self.assertEqual({artifact["id"] for artifact in reimported["artifacts"]}, first_artifact_ids)
        self.assertEqual(len(reimported["analysis_history"]), 1)
        self.assertEqual(reimported["current_analysis_by_kind"]["organoid_phenotyping"], result["bundle_key"])

    def test_rejects_changed_package_output_before_registering(self):
        (self.output / "objects.csv").write_text("corrupted\n", encoding="utf-8")
        with self.assertRaisesRegex(ReceiptImportError, "package receipt hash mismatch"):
            register_receipt(self.output, self.manifest, self.plan, self.root)
        document = json.loads((self.root / STUDY_RELATIVE / "experiment.json").read_text(encoding="utf-8"))
        self.assertIsNone(document["modeling"].get("result_artifact_id"))


if __name__ == "__main__":
    unittest.main()
