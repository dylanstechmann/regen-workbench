"""Tests for joining finalized blind poses to their restricted truth key."""

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1] / "studies" / "periodontal-attachment-restoration-2026-10-11"
sys.path.insert(0, str(STUDY_DIR))

from analyze_position_metrology import load_measurements as load_analyzer_measurements
from assemble_position_metrology_input import (
    KEY_FIELDS,
    MEASUREMENT_FIELDS,
    assemble,
    load_analysis_key,
    load_measurements,
    write_outputs,
)


class MetrologyInputAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.key_path = self.root / "restricted" / "analysis_key.tsv"
        self.measurements_path = self.root / "operator" / "finalized_measurements.tsv"
        self.key_rows = []
        for pose, values in (("zero", (0, 0, 0, 0, 0, 0)), ("shifted", (1, -2, 0.5, 3, -2, 5))):
            for replicate in range(2):
                code = f"RUN-{pose}-{replicate}"
                self.key_rows.append({
                    "run_code": code,
                    "fixture_id": "fixture_A",
                    "repeat_group_id": pose,
                    "replicate_id": code,
                    "session_id": "S01",
                    "within_session_order": str(len(self.key_rows) + 1),
                    "operator_id": "operator_1",
                    "modality": "micro_ct",
                    "pipeline_id": "reg_v1",
                    **{f"truth_{axis}": str(value) for axis, value in zip(("tx_mm", "ty_mm", "tz_mm", "rx_deg", "ry_deg", "rz_deg"), values)},
                    "randomization_seed": "42",
                })
        self.measurement_rows = [
            {"run_code": row["run_code"], **{
                f"measured_{axis}": row[f"truth_{axis}"]
                for axis in ("tx_mm", "ty_mm", "tz_mm", "rx_deg", "ry_deg", "rz_deg")
            }}
            for row in reversed(self.key_rows)
        ]
        self.write_tsv(self.key_path, KEY_FIELDS, self.key_rows)
        self.write_tsv(self.measurements_path, MEASUREMENT_FIELDS, self.measurement_rows)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def write_tsv(path, fields, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def test_complete_join_is_ordered_by_key_and_accepted_by_analyzer(self):
        key = load_analysis_key(self.key_path)
        measurements = load_measurements(self.measurements_path)
        assembled = assemble(key, measurements)
        self.assertEqual([row["run_code"] for row in assembled], [row["run_code"] for row in self.key_rows])
        self.assertEqual(len(load_analyzer_measurements(self.write_assembled(assembled))), 2)

        output_path = self.root / "analysis" / "input.tsv"
        receipt_path = self.root / "analysis" / "receipt.json"
        write_outputs(output_path, assembled, self.key_path, self.measurements_path, receipt_path, force=False)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["n_acquisitions"], 4)
        self.assertEqual(receipt["analysis_input_sha256"], hashlib.sha256(output_path.read_bytes()).hexdigest())
        self.assertEqual(len(load_analyzer_measurements(output_path)), 2)

    def write_assembled(self, rows):
        path = self.root / "assembled_for_loader.tsv"
        self.write_tsv(path, list(rows[0]), rows)
        return path

    def test_requires_exact_run_code_match(self):
        key = load_analysis_key(self.key_path)
        measurements = load_measurements(self.measurements_path)
        measurements.pop("RUN-zero-0")
        with self.assertRaisesRegex(ValueError, "run-code sets do not match.*missing measurements"):
            assemble(key, measurements)

        measurements["RUN-extra"] = {field: "0" for field in MEASUREMENT_FIELDS[1:]}
        with self.assertRaisesRegex(ValueError, "unknown run_code"):
            assemble(key, measurements)

    def test_rejects_duplicate_run_codes_and_nonfinite_measurements(self):
        duplicate_path = self.root / "duplicate.tsv"
        self.write_tsv(duplicate_path, MEASUREMENT_FIELDS, self.measurement_rows + [self.measurement_rows[0]])
        with self.assertRaisesRegex(ValueError, "duplicate run_code"):
            load_measurements(duplicate_path)

        invalid_rows = [dict(row) for row in self.measurement_rows]
        invalid_rows[0]["measured_rx_deg"] = "inf"
        invalid_path = self.root / "invalid.tsv"
        self.write_tsv(invalid_path, MEASUREMENT_FIELDS, invalid_rows)
        with self.assertRaisesRegex(ValueError, "measured_rx_deg must be finite"):
            load_measurements(invalid_path)

    def test_rejects_known_pose_columns_in_blind_measurements(self):
        fields = (*MEASUREMENT_FIELDS, "truth_tx_mm")
        path = self.root / "unblinded_measurements.tsv"
        rows = [{**row, "truth_tx_mm": "0"} for row in self.measurement_rows]
        self.write_tsv(path, fields, rows)
        with self.assertRaisesRegex(ValueError, "contains key or unblinding columns"):
            load_measurements(path)

    def test_rejects_key_truth_changes_within_pose_group(self):
        changed = [dict(row) for row in self.key_rows]
        changed[1]["truth_tx_mm"] = "0.01"
        path = self.root / "bad_key.tsv"
        self.write_tsv(path, KEY_FIELDS, changed)
        with self.assertRaisesRegex(ValueError, "truth pose changes within repeat group"):
            load_analysis_key(path)

    def test_output_must_not_replace_source_files(self):
        with self.assertRaisesRegex(ValueError, "must not overwrite the analysis key"):
            write_outputs(self.key_path, [], self.key_path, self.measurements_path, None, force=True)


if __name__ == "__main__":
    unittest.main()
