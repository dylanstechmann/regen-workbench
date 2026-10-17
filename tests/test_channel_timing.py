"""Tests for force/displacement channel timing qualification."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1] / "studies" / "periodontal-attachment-restoration-2026-10-11"
sys.path.insert(0, str(STUDY_DIR))

from analyze_channel_timing import REQUIRED_FIELDS, load_criteria, load_events, summarize  # noqa: E402


class ChannelTimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.input_path = self.root / "timing.tsv"

    def tearDown(self):
        self.temp.cleanup()

    def rows(self):
        return [
            {"run_id": "run_a", "pipeline_id": "pipe_a", "timebase_id": "clock_a", "condition_id": "fast", "replicate_id": "r1", "rate_id": "fastest", "reference_time_s": "0", "force_event_time_s": "0.001", "displacement_event_time_s": "0.002", "max_velocity_mm_s": "2"},
            {"run_id": "run_a", "pipeline_id": "pipe_a", "timebase_id": "clock_a", "condition_id": "fast", "replicate_id": "r2", "rate_id": "fastest", "reference_time_s": "1", "force_event_time_s": "1.0015", "displacement_event_time_s": "1.0025", "max_velocity_mm_s": "2"},
            {"run_id": "run_a", "pipeline_id": "pipe_a", "timebase_id": "clock_a", "condition_id": "fast", "replicate_id": "r3", "rate_id": "fastest", "reference_time_s": "2", "force_event_time_s": "2.0005", "displacement_event_time_s": "2.001", "max_velocity_mm_s": "2"},
            {"run_id": "run_a", "pipeline_id": "pipe_a", "timebase_id": "clock_a", "condition_id": "slow", "replicate_id": "r1", "rate_id": "slower", "reference_time_s": "3", "force_event_time_s": "3.001", "displacement_event_time_s": "3.0015", "max_velocity_mm_s": "0.5"},
            {"run_id": "run_a", "pipeline_id": "pipe_a", "timebase_id": "clock_a", "condition_id": "slow", "replicate_id": "r2", "rate_id": "slower", "reference_time_s": "4", "force_event_time_s": "4.0015", "displacement_event_time_s": "4.002", "max_velocity_mm_s": "0.5"},
            {"run_id": "run_a", "pipeline_id": "pipe_a", "timebase_id": "clock_a", "condition_id": "slow", "replicate_id": "r3", "rate_id": "slower", "reference_time_s": "5", "force_event_time_s": "5.0005", "displacement_event_time_s": "5.001", "max_velocity_mm_s": "0.5"},
        ]

    def write_rows(self, rows):
        with self.input_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=sorted(REQUIRED_FIELDS), delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def criteria(self, max_error=0.003):
        return {
            "criteria_id": "timing_limits_locked_before_review",
            "locked_before_outcome_review": True,
            "limits": {
                "max_abs_channel_offset_s": 0.0011,
                "max_channel_offset_jitter_sd_s": 0.0004,
                "max_observed_timing_error_mm": max_error,
            },
        }

    def test_reports_channel_offset_jitter_and_velocity_scaled_error(self):
        self.write_rows(self.rows())
        groups = load_events(self.input_path)
        records, summary = summarize(groups, None, "hash")
        fast = next(row for row in records if row["condition_id"] == "fast")
        self.assertAlmostEqual(fast["mean_channel_offset_s"], 0.0008333333333, places=9)
        self.assertAlmostEqual(fast["max_abs_channel_offset_s"], 0.001)
        self.assertAlmostEqual(fast["max_observed_timing_error_mm"], 0.002)
        self.assertAlmostEqual(fast["predicted_error_from_jitter_mm"], 2 * fast["channel_offset_jitter_sd_s"])
        self.assertEqual(summary["overall_status"], "not_assessed")

    def test_frozen_criteria_pass_and_fail(self):
        self.write_rows(self.rows())
        groups = load_events(self.input_path)
        criteria_path = self.root / "criteria.json"
        criteria_path.write_text(json.dumps(self.criteria()), encoding="utf-8")
        records, summary = summarize(groups, load_criteria(criteria_path), "hash")
        self.assertEqual(summary["overall_status"], "pass")
        self.assertTrue(all(row["status"] == "pass" for row in records))
        _, failed = summarize(groups, self.criteria(max_error=0.001), "hash")
        self.assertEqual(failed["overall_status"], "fail")

    def test_rejects_mixed_timebases_velocity_changes_and_negative_speed(self):
        rows = self.rows()
        rows[-1]["timebase_id"] = "another_clock"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "one run_id, pipeline_id, and timebase_id"):
            load_events(self.input_path)
        rows = self.rows()
        rows[1]["max_velocity_mm_s"] = "3"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "max velocity changes"):
            load_events(self.input_path)
        rows = self.rows()
        rows[0]["max_velocity_mm_s"] = "-1"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "must be nonnegative"):
            load_events(self.input_path)

    def test_rejects_duplicate_replicates_and_single_repeat(self):
        rows = self.rows()
        rows.append(dict(rows[0]))
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "duplicate replicate_id"):
            load_events(self.input_path)
        self.write_rows(self.rows()[:1] + self.rows()[3:])
        with self.assertRaisesRegex(ValueError, "at least two repeated events"):
            load_events(self.input_path)

    def test_criteria_require_locked_exact_nonnegative_limits(self):
        path = self.root / "criteria.json"
        criteria = self.criteria()
        criteria["limits"]["max_observed_timing_error_mm"] = -0.1
        path.write_text(json.dumps(criteria), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "finite and nonnegative"):
            load_criteria(path)


if __name__ == "__main__":
    unittest.main()
