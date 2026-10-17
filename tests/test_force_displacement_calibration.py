"""Tests for force/displacement calibration point auditing."""

import csv
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1] / "studies" / "periodontal-attachment-restoration-2026-10-11"
sys.path.insert(0, str(STUDY_DIR))

from analyze_force_displacement_calibration import (  # noqa: E402
    GROUP_FIELDS,
    REQUIRED_FIELDS,
    load_calibration_points,
    load_criteria,
    summarize,
    write_outputs,
)


class ForceDisplacementCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.input_path = self.root / "calibration.tsv"
        self.fields = sorted(REQUIRED_FIELDS)

    def tearDown(self):
        self.temp.cleanup()

    def example_rows(self):
        rows = []
        channel_specs = {
            "force": ("N", "force_standard", "force_certificate", "force_low", 1.0, 0.01, [-0.1, 0, 0.1], -0.01),
            "displacement": ("mm", "length_standard", "length_certificate", "disp_low", 0.1, 0.001, [-0.01, 0, 0.01], 0.002),
        }
        for channel, (unit, reference, certificate, point, truth, uncertainty, errors, drift) in channel_specs.items():
            for timepoint, shift in (("pre", 0.0), ("post", drift)):
                for replicate, error in enumerate(errors, start=1):
                    rows.append({
                        "calibration_id": "cal_1", "channel": channel,
                        "instrument_id": f"{channel}_sensor", "reference_id": reference,
                        "reference_certificate_id": certificate, "pipeline_id": "pipeline_1",
                        "point_id": point, "replicate_id": f"r{replicate}",
                        "direction": "ascending", "rate_id": "static", "timepoint": timepoint,
                        "reference_value": str(truth), "indicated_value": str(truth + error + shift),
                        "reference_uncertainty": str(uncertainty), "unit": unit,
                    })
        return rows

    def write_rows(self, rows):
        with self.input_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.fields, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def criteria(self, force_drift=0.02, displacement_drift=0.005):
        return {
            "criteria_id": "test_limits_locked_before_review",
            "locked_before_outcome_review": True,
            "channels": {
                "force": {
                    "max_abs_group_bias": 0.02, "max_rmse": 0.12,
                    "max_repeatability_coefficient_95": 0.3,
                    "max_pre_post_drift": force_drift,
                },
                "displacement": {
                    "max_abs_group_bias": 0.02, "max_rmse": 0.02,
                    "max_repeatability_coefficient_95": 0.04,
                    "max_pre_post_drift": displacement_drift,
                },
            },
        }

    def test_metrics_capture_bias_repeatability_and_pre_post_drift(self):
        self.write_rows(self.example_rows())
        groups = load_calibration_points(self.input_path)
        records, drift, summary = summarize(groups, None, "input-hash")
        force_pre = next(row for row in records if row["channel"] == "force" and row["timepoint"] == "pre")
        self.assertAlmostEqual(force_pre["mean_bias"], 0.0)
        self.assertAlmostEqual(force_pre["repeatability_sd"], 0.1)
        self.assertAlmostEqual(force_pre["rmse"], math.sqrt(0.02 / 3))
        force_drift = next(row for row in drift if row["channel"] == "force")
        displacement_drift = next(row for row in drift if row["channel"] == "displacement")
        self.assertAlmostEqual(force_drift["pre_post_drift"], -0.01)
        self.assertAlmostEqual(displacement_drift["pre_post_drift"], 0.002)
        self.assertEqual(summary["overall_status"], "not_assessed")

    def test_frozen_criteria_gate_all_groups_and_drift(self):
        self.write_rows(self.example_rows())
        criteria_path = self.root / "criteria.json"
        criteria_path.write_text(json.dumps(self.criteria()), encoding="utf-8")
        groups = load_calibration_points(self.input_path)
        criteria = load_criteria(criteria_path, {key[GROUP_FIELDS.index("channel")] for key in groups})
        records, drift, summary = summarize(groups, criteria, "input-hash")
        self.assertEqual(summary["overall_status"], "pass")
        self.assertTrue(all(row["status"] == "pass" for row in records + drift))

    def test_drift_failure_fails_the_channel_and_overall_gate(self):
        self.write_rows(self.example_rows())
        groups = load_calibration_points(self.input_path)
        criteria = self.criteria(displacement_drift=0.001)
        records, drift, summary = summarize(groups, criteria, "input-hash")
        self.assertEqual(next(row for row in drift if row["channel"] == "displacement")["status"], "fail")
        self.assertEqual(summary["channels"]["displacement"]["status"], "fail")
        self.assertEqual(summary["overall_status"], "fail")

    def test_outputs_are_written_as_machine_readable_files(self):
        self.write_rows(self.example_rows())
        groups = load_calibration_points(self.input_path)
        records, drift, summary = summarize(groups, None, "input-hash")
        outdir = self.root / "out"
        write_outputs(records, drift, summary, outdir)
        self.assertTrue((outdir / "calibration_group_metrics.tsv").exists())
        self.assertTrue((outdir / "calibration_drift_metrics.tsv").exists())
        summary_bytes = (outdir / "calibration_summary.json").read_bytes()
        self.assertNotIn(b"\r", summary_bytes)
        self.assertEqual(json.loads(summary_bytes)["overall_status"], "not_assessed")

    def test_rejects_missing_pre_or_post_measurement(self):
        rows = self.example_rows()
        rows = rows[:-3]
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "both pre and post"):
            load_calibration_points(self.input_path)

    def test_rejects_duplicate_replicate_within_point_group(self):
        rows = self.example_rows()
        rows.append(dict(rows[0]))
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "duplicate replicate_id"):
            load_calibration_points(self.input_path)

    def test_rejects_inconsistent_reference_truth_and_channel_units(self):
        rows = self.example_rows()
        rows[1]["reference_value"] = "1.01"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "reference value or uncertainty changes"):
            load_calibration_points(self.input_path)
        rows = self.example_rows()
        rows[0]["unit"] = "mm"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "requires unit N"):
            load_calibration_points(self.input_path)

    def test_criteria_must_be_frozen_complete_and_channel_matched(self):
        criteria = self.criteria()
        criteria["locked_before_outcome_review"] = False
        path = self.root / "criteria.json"
        path.write_text(json.dumps(criteria), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "locked_before_outcome_review=true"):
            load_criteria(path, {"force", "displacement"})
        criteria = self.criteria()
        del criteria["channels"]["force"]["max_rmse"]
        path.write_text(json.dumps(criteria), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must define exactly"):
            load_criteria(path, {"force", "displacement"})


if __name__ == "__main__":
    unittest.main()
