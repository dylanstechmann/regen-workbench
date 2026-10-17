"""Check frozen transport plans reject computational drift and source swaps."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1] / "studies" / "periodontal-attachment-restoration-2026-10-11"
spec = importlib.util.spec_from_file_location("patch_replication", HERE / "replicate_missing_tooth_patches.py")
replication = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replication)


class FrozenPatchReplicationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((HERE / "derived/patch_replication/frozen_intake.json").read_text())
        self.source = self.manifest["specimens"][0]
        self.plan = json.loads((HERE / "derived/patch_replication/M3_88/plan.json").read_text())
        self.pilot = (HERE / "patch_reconstruction_plan.json").read_text(encoding="utf-8").encode()

    def validate(self):
        replication.validate_plan(self.manifest, self.source, self.plan, self.pilot)

    def test_recorded_plans_retain_original_settings(self):
        for source in self.manifest["specimens"]:
            plan = json.loads((HERE / f'derived/patch_replication/M3_{source["model_id"]}/plan.json').read_text())
            replication.validate_plan(self.manifest, source, plan, self.pilot)

    def test_changed_patch_radius_is_rejected(self):
        self.plan["patch_radii_mm"][0] = .5
        with self.assertRaisesRegex(ValueError, "settings"):
            self.validate()

    def test_joint_settings_and_manifest_edit_cannot_hide_pilot_drift(self):
        self.plan["grid_spacing_mm"] = .25
        self.manifest["settings"]["grid_spacing_mm"] = .25
        with self.assertRaisesRegex(ValueError, "settings"):
            self.validate()

    def test_changed_pilot_bytes_are_rejected(self):
        self.pilot += b" "
        with self.assertRaisesRegex(ValueError, "settings"):
            self.validate()

    def test_source_identity_and_label_swaps_are_rejected(self):
        for key, value in (("model_id", 90), ("specimen_identifier", "wrong"),
                           ("archive_sha256", "0" * 64), ("source_model", "wrong")):
            with self.subTest(key=key):
                saved = copy.deepcopy(self.plan)
                self.plan[key] = value
                with self.assertRaisesRegex(ValueError, "Source"):
                    self.validate()
                self.plan = saved


if __name__ == "__main__":
    unittest.main()
