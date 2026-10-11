"""Tests for known-pose periodontal metrology analysis."""

import csv
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1] / "studies" / "periodontal-attachment-restoration-2026-10-11"
sys.path.insert(0, str(STUDY_DIR))

from analyze_position_metrology import load_criteria, load_measurements, summarize, wrapped_angle_error


class PositionMetrologyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.input_path = Path(self.temp.name) / "measurements.tsv"
        self.axes = ["tx_mm", "ty_mm", "tz_mm", "rx_deg", "ry_deg", "rz_deg"]
        self.fields = [
            "fixture_id", "repeat_group_id", "replicate_id", "modality", "pipeline_id",
            *[f"truth_{axis}" for axis in self.axes],
            *[f"measured_{axis}" for axis in self.axes],
        ]

    def tearDown(self):
        self.temp.cleanup()

    def write_rows(self, rows):
        with self.input_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.fields, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def row(self, group, replicate, truth, errors):
        result = {
            "fixture_id": "fixture_1", "repeat_group_id": group, "replicate_id": replicate,
            "modality": "micro_ct", "pipeline_id": "v1",
        }
        for axis, true_value, error in zip(self.axes, truth, errors):
            result[f"truth_{axis}"] = str(true_value)
            result[f"measured_{axis}"] = str(true_value + error)
        return result

    def test_group_bias_and_repeatability_use_known_truth(self):
        rows = [
            self.row("pose_0", "r1", [0, 0, 0, 0, 0, 0], [-0.1] * 6),
            self.row("pose_0", "r2", [0, 0, 0, 0, 0, 0], [0.0] * 6),
            self.row("pose_0", "r3", [0, 0, 0, 0, 0, 0], [0.1] * 6),
            self.row("pose_1", "r1", [1, 1, 1, 1, 1, 1], [-0.05] * 6),
            self.row("pose_1", "r2", [1, 1, 1, 1, 1, 1], [0.0] * 6),
            self.row("pose_1", "r3", [1, 1, 1, 1, 1, 1], [0.05] * 6),
        ]
        self.write_rows(rows)
        groups = load_measurements(self.input_path)
        records, summary = summarize(groups, None)
        zero = next(row for row in records if row["row_type"] == "repeat_group" and row["repeat_group_id"] == "pose_0" and row["axis"] == "tx_mm")
        self.assertAlmostEqual(float(zero["mean_bias"]), 0.0, places=8)
        self.assertAlmostEqual(float(zero["repeatability_sd_within_group"]), 0.1, places=8)
        self.assertAlmostEqual(float(zero["repeatability_coefficient_95"]), 1.96 * math.sqrt(2) * 0.1, places=6)
        self.assertEqual(summary["overall_status"], "not_assessed")

    def test_explicit_frozen_criteria_produce_per_axis_gate(self):
        rows = [
            self.row("pose_0", f"r{i}", [0] * 6, [error] * 6)
            for i, error in enumerate([-0.01, 0.0, 0.01], start=1)
        ] + [
            self.row("pose_1", f"r{i}", [1] * 6, [error] * 6)
            for i, error in enumerate([-0.01, 0.0, 0.01], start=1)
        ]
        self.write_rows(rows)
        criteria_path = Path(self.temp.name) / "criteria.json"
        criteria_path.write_text(json.dumps({
            "criteria_id": "test_only_frozen_fixture_limits",
            "locked_before_outcome_review": True,
            "axes": {axis: {"max_abs_group_bias": 0.02, "max_repeatability_coefficient_95": 0.05} for axis in self.axes},
        }), encoding="utf-8")
        criteria = load_criteria(criteria_path)
        records, summary = summarize(load_measurements(self.input_path), criteria)
        self.assertEqual(summary["overall_status"], "pass")
        self.assertTrue(all(row["status"] == "pass" for row in records))

    def test_wraps_angular_error_across_branch_cut(self):
        self.assertAlmostEqual(wrapped_angle_error(-179.0, 179.0), 2.0)
        self.assertAlmostEqual(wrapped_angle_error(179.0, -179.0), -2.0)

    def test_rejects_truth_pose_changes_within_repeat_group(self):
        rows = [
            self.row("pose_0", "r1", [0] * 6, [0] * 6),
            self.row("pose_0", "r2", [0.01, 0, 0, 0, 0, 0], [0] * 6),
        ]
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "truth pose changes"):
            load_measurements(self.input_path)

    def test_rejects_mixed_methods_in_one_analysis(self):
        rows = [
            self.row("pose_0", "r1", [0] * 6, [0] * 6),
            self.row("pose_0", "r2", [0] * 6, [0] * 6),
            self.row("pose_1", "r1", [1] * 6, [0] * 6),
            self.row("pose_1", "r2", [1] * 6, [0] * 6),
            self.row("pose_2", "r1", [2] * 6, [0] * 6),
            self.row("pose_2", "r2", [2] * 6, [0] * 6),
        ]
        rows[-1]["pipeline_id"] = "different_pipeline"
        rows[-2]["pipeline_id"] = "different_pipeline"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "one modality and one pipeline"):
            load_measurements(self.input_path)

    def test_fails_when_a_pose_condition_exceeds_frozen_bias_limit(self):
        rows = [
            self.row("pose_0", "r1", [0] * 6, [0.2] * 6),
            self.row("pose_0", "r2", [0] * 6, [0.2] * 6),
            self.row("pose_1", "r1", [1] * 6, [0.0] * 6),
            self.row("pose_1", "r2", [1] * 6, [0.0] * 6),
        ]
        self.write_rows(rows)
        criteria_path = Path(self.temp.name) / "criteria.json"
        criteria_path.write_text(json.dumps({
            "criteria_id": "test_only_bias_gate",
            "locked_before_outcome_review": True,
            "axes": {axis: {"max_abs_group_bias": 0.1, "max_repeatability_coefficient_95": 0.1} for axis in self.axes},
        }), encoding="utf-8")
        criteria = load_criteria(criteria_path)
        _, summary = summarize(load_measurements(self.input_path), criteria)
        self.assertEqual(summary["overall_status"], "fail")
        self.assertEqual(summary["axis_results"]["tx_mm"]["status"], "fail")

    def test_rejects_unfrozen_criteria(self):
        path = Path(self.temp.name) / "criteria.json"
        path.write_text(json.dumps({
            "criteria_id": "late_choice", "locked_before_outcome_review": False,
            "axes": {axis: {"max_abs_group_bias": 1, "max_repeatability_coefficient_95": 1} for axis in self.axes},
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "locked_before_outcome_review=true"):
            load_criteria(path)


if __name__ == "__main__":
    unittest.main()
