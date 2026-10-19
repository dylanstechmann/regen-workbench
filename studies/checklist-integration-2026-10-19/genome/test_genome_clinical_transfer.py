import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("genome_clinical", HERE / "analyze_genome_clinical.py")
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class ClinicalTransferTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
        self.result = analysis.calculate(self.data)

    def test_source_summary_contrasts(self):
        rows = self.result["contrasts"]
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["difference_of_reported_medians"], -14)
        self.assertAlmostEqual(rows[0]["ratio_of_reported_medians"], 9 / 23)
        self.assertEqual(rows[1]["difference_of_reported_medians"], -10)
        self.assertAlmostEqual(rows[2]["ratio_of_reported_medians"], 2.4 / 1.7)
        self.assertAlmostEqual(rows[3]["difference_of_reported_medians"], 0.9)

    def test_iqr_is_dispersion_not_confidence_interval(self):
        widths = [row["IQR_width"] for row in self.result["summary_rows"]]
        for observed, expected in zip(widths, [34, 10, 19, .2, 1, 1.6]):
            self.assertAlmostEqual(observed, expected)
        self.assertNotIn("confidence_interval", json.dumps(self.result))

    def test_exact_time_and_rounded_windows_are_distinct(self):
        t = self.result["timeline"]
        self.assertEqual(t["second_intervention_day_derived"], 230)
        self.assertEqual(t["first_to_followup_end_elapsed_days"], 48)
        self.assertEqual(t["first_to_followup_end_inclusive_day_count"], 49)
        self.assertEqual(t["second_to_followup_end_elapsed_days"], 26)
        self.assertEqual(t["nominal_relative_medication_reduction_day_derived_from_weeks"], 244)
        self.assertEqual(t["nominal_relative_medication_reduction_to_followup_end_days"], 12)
        self.assertIn("not a reported exact clinical day", t["medication_timing_precision"])
        self.assertEqual(t["reported_followup_after_first_weeks"], 7)

    def test_weight_has_different_start_and_no_attributable_effect(self):
        w = self.result["weight_contrast"]
        self.assertAlmostEqual(w["difference"], 1.03)
        self.assertEqual(w["elapsed_days"], 49)
        self.assertEqual(w["reported_percentile_point_difference"], 17)
        self.assertIn("not an editing-attributable", w["interpretation"])

    def test_independent_patient_and_specimen_unknowns_retained(self):
        self.assertEqual(self.result["independent_patients"], 1)
        self.assertTrue(all(row["independent_patients"] == 1 and row["n_measurements"] is None for row in self.result["summary_rows"]))
        changed = copy.deepcopy(self.data)
        changed["study"]["independent_patients"] = 6
        with self.assertRaises(ValueError):
            analysis.calculate(changed)

    def test_missing_molecular_and_causal_links_not_calculated(self):
        unavailable = self.result["unavailable_inferences"]
        self.assertIn("patient_corrected_allele_fraction", unavailable)
        self.assertIn("ordinary_aging_coverage_fraction", unavailable)
        self.assertIn("clinical_causal_effect", unavailable)
        self.assertIn("paired_ammonia_orotic_association", unavailable)
        self.assertIsNone(self.data["study"]["patient_corrected_hepatocyte_fraction"])
        self.assertFalse(self.data["sampling_constraints"]["paired_ammonia_orotic_specimens_available"])

    def test_invalid_numerics_quartiles_and_chronology_rejected(self):
        for bad in [True, "23", float("nan"), float("inf"), -1, 0]:
            changed = copy.deepcopy(self.data)
            changed["endpoints"][0]["groups"][0]["median"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                analysis.calculate(changed)
        changed = copy.deepcopy(self.data)
        changed["endpoints"][0]["groups"][0]["q1"] = 24
        with self.assertRaises(ValueError):
            analysis.calculate(changed)
        changed = copy.deepcopy(self.data)
        changed["timeline"]["followup_end_day"] = 220
        with self.assertRaises(ValueError):
            analysis.calculate(changed)

    def test_canonical_hash_ignores_platform_newlines(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            a.write_bytes(b'{"x": 1}\n')
            b.write_bytes(b'{"x": 1}\r\n')
            self.assertEqual(analysis.canonical_hash(a), analysis.canonical_hash(b))

    def test_persisted_outputs_and_no_administration_amounts(self):
        saved = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
        expected = copy.deepcopy(self.result)
        expected["inputs_sha256_canonical_utf8_lf"] = analysis.canonical_hash(HERE / "inputs.json")
        self.assertEqual(saved, expected)
        self.assertEqual((HERE / "clinical_summary_contrasts.csv").read_text(encoding="utf-8"), analysis.tables(saved))
        for name in ["inputs.json", "results.json", "REPORT.md"]:
            text = (HERE / name).read_text(encoding="utf-8").lower()
            for forbidden in ["mg/kg", "mg per kilogram", "ml/m", "ml per square", "protospacer", "guide sequence"]:
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
