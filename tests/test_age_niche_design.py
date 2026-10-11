"""Focused checks for age-by-niche allocation and power-planning utilities."""

import csv
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1] / "studies" / "organoid" / "periodontal-ligament-interface"
sys.path.insert(0, str(STUDY_DIR))

from make_age_niche_allocation import build_rows, load_roster, write_manifest
from simulate_age_niche_interaction import interaction_se, simulate_power, t_critical_approx


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.roster_path = Path(self.temp.name) / "roster.tsv"
        with self.roster_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
            writer.writerow(["donor_id", "role", "age_years", "age_stratum"])
            writer.writerows([
                ["T01", "target", "24", "younger"],
                ["T02", "target", "27", "younger"],
                ["T03", "target", "58", "older"],
                ["T04", "target", "63", "older"],
                ["N01", "niche", "25", "younger"],
                ["N02", "niche", "29", "younger"],
                ["N03", "niche", "56", "older"],
                ["N04", "niche", "61", "older"],
            ])

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_cross_controls_batches_and_determinism(self):
        targets, niches = load_roster(self.roster_path)
        rows = build_rows(targets, niches, 2, 1, 42, 8)
        rows_again = build_rows(targets, niches, 2, 1, 42, 8)
        self.assertEqual(rows, rows_again)
        self.assertEqual(len(rows), 4 * 4 * 2 + 4)
        self.assertEqual(len({row["allocation_id"] for row in rows}), len(rows))
        self.assertEqual(len({row["blinded_code"] for row in rows}), len(rows))
        self.assertTrue(all(len(batch) <= 8 for batch in self._group(rows, "batch_id").values()))
        for target in targets:
            assigned = [row for row in rows if row["target_donor_id"] == target["donor_id"]]
            self.assertEqual(sum(row["exposure_condition"] == "unconditioned" for row in assigned), 1)
            self.assertEqual(sum(row["exposure_condition"] == "conditioned" for row in assigned), 8)
            self.assertEqual(
                {row["niche_donor_id"] for row in assigned if row["niche_donor_id"]},
                {niche["donor_id"] for niche in niches},
            )
        for batch in self._group(rows, "batch_id").values():
            orders = [int(row["randomized_order"]) for row in batch]
            self.assertEqual(sorted(orders), list(range(1, len(batch) + 1)))
            counts = self._group(batch, "condition_key")
            group_counts = [len(group) for group in counts.values()]
            self.assertLessEqual(max(group_counts) - min(group_counts), 1)

        output = Path(self.temp.name) / "manifest.tsv"
        write_manifest(rows, output)
        with output.open(encoding="utf-8", newline="") as stream:
            saved = list(csv.DictReader(stream, delimiter="\t"))
        self.assertEqual(saved, rows)

    def test_rejects_role_overlap(self):
        text = self.roster_path.read_text(encoding="utf-8")
        self.roster_path.write_text(text.replace("N04\tniche", "T01\tniche"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "independent donors"):
            load_roster(self.roster_path)

    def test_cli_writes_manifest_and_refuses_accidental_overwrite(self):
        script = STUDY_DIR / "make_age_niche_allocation.py"
        output = Path(self.temp.name) / "allocation.tsv"
        command = [
            sys.executable, str(script), "--roster", str(self.roster_path),
            "--out", str(output), "--seed", "19", "--batch-capacity", "8",
        ]
        first = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(first.returncode, 0, first.stderr)
        original = output.read_bytes()
        second = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(second.returncode, 2)
        self.assertIn("output already exists", second.stderr)
        self.assertEqual(output.read_bytes(), original)

    @staticmethod
    def _group(rows, field):
        groups = {}
        for row in rows:
            groups.setdefault(row[field], []).append(row)
        return groups


class PowerPlanningTests(unittest.TestCase):
    def test_standard_error_formula(self):
        expected = math.sqrt(2 * 0.4**2 / 10 + 2 * 0.3**2 / 10 + 4 * 0.7**2 / (10**2 * 2))
        self.assertAlmostEqual(interaction_se(10, 0.4, 0.3, 0.7, 2), expected)

    def test_t_critical_approximation(self):
        self.assertAlmostEqual(t_critical_approx(0.05, 30), 2.0423, delta=0.002)

    def test_null_calibration(self):
        rejection, mcse = simulate_power(0, 1, 30, 0.05, 30000, 11)
        self.assertLessEqual(abs(rejection - 0.05), 3 * mcse)


if __name__ == "__main__":
    unittest.main()
