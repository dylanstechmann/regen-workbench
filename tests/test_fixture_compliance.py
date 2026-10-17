"""Tests for blocked-fixture compliance qualification summaries."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1] / "studies" / "periodontal-attachment-restoration-2026-10-11"
sys.path.insert(0, str(STUDY_DIR))

from analyze_fixture_compliance import GROUP_FIELDS, REQUIRED_FIELDS, load_criteria, load_measurements, summarize  # noqa: E402


class FixtureComplianceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.input_path = self.root / "fixture.tsv"

    def tearDown(self):
        self.temp.cleanup()

    def rows(self):
        rows = []
        states = [
            ("dev_blank", "blank", "development", 0.0),
            ("dev_motion", "known_motion", "development", 0.1),
            ("held_blank", "blank", "held_out", 0.0),
            ("held_motion", "known_motion", "held_out", 0.2),
        ]
        for state_id, state_type, split, truth in states:
            for force_level, force in (("f1", 1.0), ("f2", 2.0)):
                for replicate, noise in enumerate((-0.001, 0.0, 0.001), start=1):
                    residual = 0.0005 * force + noise / 2
                    rows.append({
                        "fixture_id": "fixture_a", "pipeline_id": "pipe_a",
                        "correction_id": "correction_v1", "state_id": state_id,
                        "state_type": state_type, "split": split, "direction": "ascending",
                        "rate_id": "static", "force_level_id": force_level,
                        "replicate_id": f"r{replicate}", "force_n": str(force),
                        "reference_displacement_mm": str(truth),
                        "raw_displacement_mm": str(truth + 0.01 * force + noise),
                        "corrected_displacement_mm": str(truth + residual),
                    })
        return rows

    def write_rows(self, rows):
        with self.input_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=sorted(REQUIRED_FIELDS), delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def criteria(self, max_residual=0.003):
        return {
            "criteria_id": "fixture_limits_locked_before_review",
            "locked_before_outcome_review": True,
            "limits": {
                "max_abs_final_residual_mm": max_residual,
                "max_final_rmse_mm": 0.003,
                "max_repeatability_coefficient_95_mm": 0.002,
            },
        }

    def test_reports_raw_blank_movement_and_held_out_corrected_residual(self):
        self.write_rows(self.rows())
        groups = load_measurements(self.input_path)
        records, summary = summarize(groups, None, "hash")
        held_blank = next(row for row in records if row["state_type"] == "blank" and row["split"] == "held_out" and row["force_n"] == 2.0)
        self.assertAlmostEqual(held_blank["max_abs_raw_residual_mm"], 0.021)
        self.assertAlmostEqual(held_blank["max_abs_final_residual_mm"], 0.0015)
        self.assertEqual(summary["overall_status"], "not_assessed")

    def test_only_held_out_groups_decide_frozen_criteria(self):
        self.write_rows(self.rows())
        criteria_path = self.root / "criteria.json"
        criteria_path.write_text(json.dumps(self.criteria()), encoding="utf-8")
        groups = load_measurements(self.input_path)
        records, summary = summarize(groups, load_criteria(criteria_path), "hash")
        self.assertEqual(summary["overall_status"], "pass")
        self.assertTrue(all(row["status"] == "development_only" for row in records if row["split"] == "development"))
        self.assertTrue(all(row["status"] == "pass" for row in records if row["split"] == "held_out"))

    def test_held_out_residual_failure_fails_summary(self):
        self.write_rows(self.rows())
        groups = load_measurements(self.input_path)
        _, summary = summarize(groups, self.criteria(max_residual=0.001), "hash")
        self.assertEqual(summary["overall_status"], "fail")

    def test_rejects_truth_inconsistency_and_nonzero_blank_truth(self):
        rows = self.rows()
        rows[0]["reference_displacement_mm"] = "0.01"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "blank fixture reference displacement must be zero"):
            load_measurements(self.input_path)
        rows = self.rows()
        rows[7]["reference_displacement_mm"] = "0.11"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "state_id changes type or reference"):
            load_measurements(self.input_path)

    def test_rejects_missing_correction_values_and_missing_held_out_motion(self):
        rows = self.rows()
        rows[0]["corrected_displacement_mm"] = ""
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "corrected_displacement_mm must be supplied"):
            load_measurements(self.input_path)
        rows = [row for row in self.rows() if row["state_type"] != "known_motion" or row["split"] != "held_out"]
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "held-out blank and known-motion"):
            load_measurements(self.input_path)

    def test_rejects_duplicate_replicates_and_unfrozen_criteria(self):
        rows = self.rows()
        rows.append(dict(rows[0]))
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "duplicate replicate_id"):
            load_measurements(self.input_path)
        path = self.root / "criteria.json"
        criteria = self.criteria()
        criteria["locked_before_outcome_review"] = False
        path.write_text(json.dumps(criteria), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "locked_before_outcome_review=true"):
            load_criteria(path)


if __name__ == "__main__":
    unittest.main()
