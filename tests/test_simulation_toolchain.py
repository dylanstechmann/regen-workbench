from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "studies" / "simulation-toolchain" / "validate.py"
spec = importlib.util.spec_from_file_location("simulation_toolchain_validate", VALIDATOR)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema is required for simulation manifest validation")
class SimulationToolchainManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.document = json.loads(module.MANIFEST.read_bytes())
        # Standalone CI verifies actual bytes without needing sibling clones.
        for index, artifact in enumerate(self.document["artifacts"]):
            data = f"software fixture {index}\n".encode()
            path = self.workspace / artifact["repository"] / artifact["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            artifact["sha256"] = hashlib.sha256(data).hexdigest()
            artifact["size_bytes"] = len(data)
        self.manifest = self.workspace / "manifest.json"

    def validate(self):
        self.manifest.write_text(json.dumps(self.document))
        return module.validate(self.manifest, workspace=self.workspace)

    def test_golden_structure_validates_without_external_repositories(self):
        document = module.validate(verify_files=False)
        self.assertEqual(document["workflow_id"], "giwi-oxygen-calibration-software-fixture")
        self.assertEqual(len(document["artifacts"]), 11)
        self.assertNotIn("physical_measurement",
                         {item["evidence_status"] for item in document["artifacts"]})

    def test_hashes_and_step_references_validate_in_any_workspace(self):
        self.assertEqual(len(self.validate()["artifacts"]), 11)

    def test_changed_artifact_bytes_are_rejected(self):
        artifact = self.document["artifacts"][0]
        (self.workspace / artifact["repository"] / artifact["path"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.validate()

    def test_duplicate_steps_and_multiple_producers_are_rejected(self):
        self.document["steps"][1]["step_id"] = self.document["steps"][0]["step_id"]
        with self.assertRaisesRegex(ValueError, "duplicate step_id"):
            self.validate()
        self.document["steps"][1]["step_id"] = "unique-step"
        self.document["steps"][1]["output_artifacts"].append("giwi-constraints")
        with self.assertRaisesRegex(ValueError, "multiple producers"):
            self.validate()

    def test_forward_dependency_and_unrun_producer_are_rejected(self):
        self.document["steps"][0]["input_artifacts"].append("oxygen-summary")
        with self.assertRaisesRegex(ValueError, "before it is produced"):
            self.validate()
        self.document["steps"][0]["input_artifacts"] = []
        self.document["steps"][0]["execution_status"] = "not_run"
        with self.assertRaisesRegex(ValueError, "unrun step"):
            self.validate()

    def test_path_traversal_and_windows_drives_are_rejected(self):
        for unsafe in ("../outside", "/outside", "C:/outside", "dir\\outside"):
            self.document["artifacts"][0]["path"] = unsafe
            with self.subTest(path=unsafe), self.assertRaisesRegex(ValueError, "unsafe artifact path"):
                self.validate()

    def test_repository_traversal_and_physical_claims_are_rejected(self):
        import jsonschema
        for field, value in (("repository", "../outside"),
                             ("evidence_status", "physical_measurement")):
            self.document = json.loads(module.MANIFEST.read_bytes())
            self.document["artifacts"][0][field] = value
            with self.subTest(field=field), self.assertRaises(jsonschema.ValidationError):
                self.validate()


if __name__ == "__main__":
    unittest.main()
