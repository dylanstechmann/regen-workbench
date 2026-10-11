"""Tests for blinded known-pose acquisition scheduling."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1] / "studies" / "periodontal-attachment-restoration-2026-10-11"
sys.path.insert(0, str(STUDY_DIR))

from make_pose_acquisition_manifest import build_manifest, load_conditions, validate_separate_key


class PoseAcquisitionManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.conditions_path = self.root / "conditions.tsv"
        with self.conditions_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
            writer.writerow([
                "pose_condition_id", "fixture_id", "truth_tx_mm", "truth_ty_mm", "truth_tz_mm",
                "truth_rx_deg", "truth_ry_deg", "truth_rz_deg",
            ])
            writer.writerows([
                ["zero", "fixture_A", 0, 0, 0, 0, 0, 0],
                ["pose_B", "fixture_A", 1, -2, 0.5, 3, -2, 5],
            ])

    def tearDown(self):
        self.temp.cleanup()

    def build(self, seed=42):
        return build_manifest(
            load_conditions(self.conditions_path), sessions=2,
            repeats_per_pose_per_session=3, seed=seed,
            operator_id="operator_1", modality="micro_ct", pipeline_id="reg_v1",
        )

    def test_balances_each_pose_within_session_and_is_seed_reproducible(self):
        schedule, key = self.build()
        schedule_again, key_again = self.build()
        self.assertEqual(schedule, schedule_again)
        self.assertEqual(key, key_again)
        self.assertEqual(len(schedule), 12)
        self.assertEqual(len({row["run_code"] for row in schedule}), 12)
        self.assertEqual(
            {row["run_code"] for row in schedule},
            {row["run_code"] for row in key},
        )
        for session in {row["session_id"] for row in key}:
            session_key = [row for row in key if row["session_id"] == session]
            self.assertEqual({row["repeat_group_id"] for row in session_key}, {"pose_B", "zero"})
            self.assertEqual([sum(row["repeat_group_id"] == pose for row in session_key) for pose in ("pose_B", "zero")], [3, 3])

    def test_operator_schedule_hides_pose_key_and_truth(self):
        schedule, key = self.build()
        self.assertEqual(
            set(schedule[0]),
            {"run_code", "session_id", "within_session_order", "operator_id", "modality", "pipeline_id"},
        )
        serialized_schedule = str(schedule)
        self.assertNotIn("pose_B", serialized_schedule)
        self.assertNotIn("truth_tx_mm", serialized_schedule)
        self.assertIn("truth_tx_mm", key[0])

    def test_key_path_must_be_outside_operator_schedule_directory(self):
        schedule_path = self.root / "operator" / "schedule.tsv"
        validate_separate_key(schedule_path, self.root / "analysis" / "key.tsv")
        with self.assertRaisesRegex(ValueError, "outside the operator schedule directory"):
            validate_separate_key(schedule_path, self.root / "operator" / "key.tsv")

    def test_rejects_repeated_pose_ids(self):
        text = self.conditions_path.read_text(encoding="utf-8")
        self.conditions_path.write_text(text + "zero\tfixture_A\t0\t0\t0\t0\t0\t0\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate pose_condition_id"):
            load_conditions(self.conditions_path)

    def test_rejects_invalid_session_count(self):
        with self.assertRaisesRegex(ValueError, "must both be positive"):
            build_manifest(
                load_conditions(self.conditions_path), sessions=0,
                repeats_per_pose_per_session=1, seed=1,
                operator_id="op", modality="micro_ct", pipeline_id="v1",
            )


if __name__ == "__main__":
    unittest.main()
