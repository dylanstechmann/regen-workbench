"""Tests for force-displacement trace validation and descriptive metrics."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1] / "studies" / "periodontal-attachment-restoration-2026-10-11"
sys.path.insert(0, str(STUDY_DIR))

from analyze_mobility_response import load_traces, summarize_traces


FIELDS = [
    "specimen_id", "tooth_id", "condition_code", "acquisition_id",
    "measurement_point", "load_axis_id", "cycle_id", "sample_index",
    "time_s", "phase", "force_n", "displacement_mm",
    "force_calibration_id", "displacement_calibration_id", "pipeline_id",
]


class MobilityResponseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "traces.tsv"

    def tearDown(self):
        self.temp.cleanup()

    def rows(self):
        samples = [
            (0.0, "baseline", 0.0, 0.0),
            (1.0, "loading", 0.5, 0.05),
            (2.0, "loading", 1.0, 0.10),
            (3.0, "loading", 1.5, 0.15),
            (4.0, "unloading", 1.0, 0.11),
            (5.0, "unloading", 0.5, 0.07),
            (6.0, "unloading", 0.0, 0.03),
            (7.0, "recovery", 0.0, 0.02),
        ]
        result = []
        for index, (time, phase, force, displacement) in enumerate(samples):
            result.append({
                "specimen_id": "specimen_1", "tooth_id": "tooth_1",
                "condition_code": "condition_A", "acquisition_id": "acq_1",
                "measurement_point": "crown", "load_axis_id": "buccolingual",
                "cycle_id": "cycle_1", "sample_index": str(index),
                "time_s": str(time), "phase": phase, "force_n": str(force),
                "displacement_mm": str(displacement),
                "force_calibration_id": "force_v1",
                "displacement_calibration_id": "disp_v1", "pipeline_id": "pipeline_v1",
            })
        return result

    def write_rows(self, rows):
        with self.path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def test_computes_path_integral_and_recovery_without_verdict(self):
        self.write_rows(self.rows())
        records, summary = summarize_traces(load_traces(self.path), "test-hash")
        self.assertEqual(len(records), 1)
        self.assertAlmostEqual(records[0]["signed_force_displacement_integral_n_mm"], 0.0225, places=8)
        self.assertAlmostEqual(records[0]["end_of_unloading_displacement_mm"], 0.03, places=8)
        self.assertAlmostEqual(records[0]["end_of_recovery_displacement_mm"], 0.02, places=8)
        self.assertAlmostEqual(records[0]["recovery_change_mm"], -0.01, places=8)
        self.assertAlmostEqual(records[0]["recovery_elapsed_s"], 1.0, places=8)
        self.assertEqual(summary["biological_pass_fail"], "not_assessed")
        self.assertTrue(summary["outputs_are_descriptive_only"])

    def test_missing_recovery_stays_missing_not_zero(self):
        rows = [row for row in self.rows() if row["phase"] != "recovery"]
        self.write_rows(rows)
        records, _ = summarize_traces(load_traces(self.path), "test-hash")
        self.assertEqual(records[0]["end_of_recovery_displacement_mm"], "")
        self.assertEqual(records[0]["recovery_change_mm"], "")

    def test_rejects_nonfinite_force(self):
        rows = self.rows()
        rows[1]["force_n"] = "nan"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "must be finite"):
            load_traces(self.path)

    def test_rejects_nonmonotonic_time(self):
        rows = self.rows()
        rows[3]["time_s"] = "1.5"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "time_s must strictly increase"):
            load_traces(self.path)

    def test_rejects_phase_order_reversal(self):
        rows = self.rows()
        rows[-1]["phase"] = "loading"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "phases must follow"):
            load_traces(self.path)

    def test_rejects_mixed_calibration_or_pipeline(self):
        rows = self.rows()
        rows[-1]["pipeline_id"] = "pipeline_v2"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "one force calibration"):
            load_traces(self.path)

    def test_rejects_insufficient_loading_or_unloading_samples(self):
        rows = self.rows()
        rows = [row for row in rows if row["sample_index"] not in {"5", "6"}]
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "each need at least two samples"):
            load_traces(self.path)


if __name__ == "__main__":
    unittest.main()

