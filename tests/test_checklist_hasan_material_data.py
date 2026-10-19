"""Guard source-cell identity, replicate limits and material comparison arithmetic."""
import csv
import importlib.util
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "studies/checklist-followup-2026-10-19/dental"
SPEC = importlib.util.spec_from_file_location("hasan_material_data", STUDY / "analyze_hasan_material_data.py")
MODEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODEL)


def cell(value, style="8", formula=None):
    return {"value": str(value), "stored_text": str(value), "type": "n", "style": style, "formula": formula}


class HasanMaterialDataTests(unittest.TestCase):
    def test_source_value_is_not_recalculated_formula_or_string(self):
        self.assertEqual(MODEL.numeric_cell({"A1": cell(0)}, "A1"), 0)
        for value in (cell(1, formula="AVERAGE(A2:A3)"), {**cell(1), "type": "s"}, cell(float("nan")), cell(-1)):
            with self.assertRaises(ValueError):
                MODEL.numeric_cell({"A1": value}, "A1")

    def test_oo_xml_reader_preserves_cell_value_style_and_formula(self):
        xml = b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" s="8"><v>1.2300</v></c><c r="B1" t="s"><v>0</v></c><c r="C1"><f>A1*2</f><v>2.46</v></c></row></sheetData></worksheet>'
        parsed = MODEL.parse_sheet(xml, ["Native"])
        self.assertEqual(parsed["A1"]["stored_text"], "1.2300")
        self.assertEqual(parsed["A1"]["style"], "8")
        self.assertEqual(parsed["B1"]["value"], "Native")
        self.assertEqual(parsed["C1"]["formula"], "A1*2")

    def test_ranges_cannot_silently_include_another_group(self):
        self.assertEqual(MODEL.addresses("AA20:AA22"), ["AA20", "AA21", "AA22"])
        for reference in ("A1:B3", "A3:A1", "A0:A3", "A1", "a1:a3"):
            with self.assertRaises(ValueError):
                MODEL.addresses(reference)

    def test_sd_conventions_are_explicit_and_distinct(self):
        result = MODEL.describe([1, 2, 3])
        self.assertEqual(result["mean"], 2)
        self.assertEqual(result["sample_sd_n_minus_1"], 1)
        self.assertAlmostEqual(result["population_divisor_sd_n"], math.sqrt(2 / 3))
        self.assertNotIn("confidence_interval", result)

    def test_ambiguous_trailing_value_stays_unknown_after_mean_median_checks(self):
        cells = {"AC13": cell(2.51), "AE13": {**cell(0, style="7"), "value": None, "stored_text": None},
                 "AF13": {**cell(0, style="7"), "value": None, "stored_text": None}}
        first8 = [2.931, 1.26, 1.739, 3.899, 2.101, 3.576, 3.105, 1.396]
        result = MODEL.trailing_audit(cells, first8, "AC13")
        self.assertAlmostEqual(result["first8_mean"], 2.500875)
        self.assertAlmostEqual(result["first8_median"], 2.516)
        self.assertIn("unresolved", result["identity"])
        self.assertIsNone(result["same_row_height_values"]["AE13"])
        self.assertIsNone(result["formula"])

    def test_selected_point_count_must_match_declared_caption(self):
        plan = {"workbook_sheet": "fixture", "header_checks": {}, "series": [
            {"id": "fixture", "endpoint": "wear", "substrate": "enamel", "condition": "native", "unit": "mm^3", "range": "A1:A3", "caption_n_samples": 8}]}
        with self.assertRaises(ValueError):
            MODEL.analyze_series({"A1": cell(1), "A2": cell(2), "A3": cell(3)}, plan)

    def test_unfavorable_and_equal_means_are_retained(self):
        plan = {"contrasts": [{"id": "loss", "reference": "native", "candidate": "repaired", "favorable_direction": "lower"}]}
        result = MODEL.contrasts({"native": [2, 4], "repaired": [3, 5]}, plan)[0]
        self.assertEqual(result["observed_direction"], "unfavorable_mean_direction")
        self.assertAlmostEqual(result["mean_change_percent"], 100 / 3)
        equal = MODEL.contrasts({"native": [2, 4], "repaired": [3, 3]}, plan)[0]
        self.assertEqual(equal["observed_direction"], "equal_means")

    def test_published_numeric_extract_has_no_invented_specimen_ids(self):
        with (STUDY / "derived/material_observations.tsv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        self.assertEqual(len(rows), 75)
        self.assertTrue(all(not r["specimen_id"] and not r["donor_id"] for r in rows))
        extra = [r for r in rows if r["observation_status"] == "ambiguous_trailing_cell_not_a_specimen"]
        self.assertEqual({r["cell"] for r in extra}, {"AC13", "AD13"})
        self.assertTrue(all(not r["source_position_not_specimen_id"] for r in extra))

    def test_nine_numeric_values_never_become_nine_caption_samples(self):
        with (STUDY / "derived/material_summary.tsv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        sensitivity = [r for r in rows if r["qualification"] == "intake_sensitivity_not_9_specimens"]
        self.assertEqual(len(sensitivity), 2)
        self.assertTrue(all(r["n_numeric_values"] == "9" and r["caption_n_samples"] == "8" for r in sensitivity))

    def test_persisted_receipts_and_source_pins_match(self):
        audit = json.loads((STUDY / "derived/intake_and_hierarchy_audit.json").read_text(encoding="utf-8"))
        plan = json.loads((STUDY / "analysis_plan.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["plan_sha256_lf_text"], MODEL.text_sha(STUDY / "analysis_plan.json"))
        self.assertEqual(audit["script_sha256_lf_text"], MODEL.text_sha(STUDY / "analyze_hasan_material_data.py"))
        for filename, digest in audit["output_sha256_lf_text"].items():
            self.assertEqual(MODEL.text_sha(STUDY / "derived" / filename), digest)
        for source, value in audit["source_files"].items():
            self.assertEqual(value["sha256"], plan["source_files"][source]["sha256"])
        self.assertFalse(audit["source_workbook_or_article_files_redistributed"])


if __name__ == "__main__":
    unittest.main()
