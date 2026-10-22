"""Offline checks for aggregate denominators and the narrowly scoped source verifier."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1] / "studies/checklist-engineering-2026-10-22/barrier"


def load(name):
    spec = importlib.util.spec_from_file_location("barrier_20261022_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


analysis = load("analyze_oral_measurements")
verifier = load("verify_source_tables")


class OralMeasurementComparisonTests(unittest.TestCase):
    def setUp(self):
        self.facts = json.loads((HERE / "source_facts.json").read_text(encoding="utf-8"))

    def test_ali_ratios_use_distinct_measured_endpoints(self):
        row = analysis.compare(self.facts)["comparison_ali_over_submerged"]
        self.assertAlmostEqual(row["thickness_ratio_of_reported_means"], 7.542857142857143)
        self.assertAlmostEqual(row["teer_ratio_of_reported_means"], 1.0161290322580645)
        self.assertAlmostEqual(row["fd20_papp_relative_difference_percent"], -42.2680412371134)

    def test_commercial_total_thickness_not_equivalent_resistance(self):
        row = analysis.compare(self.facts)["comparison_full_thickness_over_microtissue"]
        self.assertGreater(row["thickness_ratio_of_reported_means"], 8)
        self.assertLess(row["teer_ratio_of_reported_means"], 1)

    def test_no_donors_pairing_or_clinical_effect_invented(self):
        result = analysis.compare(self.facts)
        for key in ["independent_donor_count", "joint_thickness_teer_transport_per_insert", "clinical_equivalence", "gingival_restoration_outcome"]:
            self.assertIsNone(result[key])
        self.assertIsNone(result["comparison_ali_over_submerged"]["confidence_interval"])

    def test_sem_not_silently_relabelled_sd(self):
        self.facts["physical_properties"][0]["dispersion"] = "SD"
        with self.assertRaises(ValueError):
            analysis.compare(self.facts)

    def test_reported_replicate_count_preserved(self):
        self.facts["physical_properties"][0]["replicates_per_group"] = 6
        with self.assertRaises(ValueError):
            analysis.compare(self.facts)

    def test_ohms_are_not_ohm_cm2(self):
        self.facts["physical_properties"][0]["teer_unit"] = "ohm"
        with self.assertRaises(ValueError):
            analysis.compare(self.facts)

    def test_unavailable_crosswalk_cannot_be_assumed(self):
        self.facts["fd20_transport"]["crosswalk_to_physical_properties"] = "assumed"
        with self.assertRaises(ValueError):
            analysis.compare(self.facts)

    def test_invalid_denominators_rejected(self):
        for value in [0, -1, float("nan"), float("inf"), True]:
            facts = copy.deepcopy(self.facts)
            facts["physical_properties"][0]["thickness_mean"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                analysis.compare(facts)

    def test_saved_results_match_current_calculation(self):
        saved = json.loads((HERE / "results.json").read_text())
        saved.pop("source_facts_sha256")
        self.assertEqual(saved, analysis.compare(self.facts))

    def test_source_scope_rejects_other_table(self):
        with self.assertRaises(ValueError):
            verifier.selected_section('<section id="tbl3"></section>', "tbl3")

    def test_source_number_parser_preserves_exponent(self):
        self.assertAlmostEqual(verifier.scientific_number("9.7 × 10–7"), 9.7e-7)
        self.assertEqual(verifier.mean_sem("126 ± 2"), (126, 2))
        with self.assertRaises(ValueError):
            verifier.scientific_number("missing")

    def test_source_verifier_detects_mismatch_and_duplicate_models(self):
        header = '<section id="tbl2"><table><tr><th>Model</th><th>TEER</th><th>Thickness</th></tr>'
        rows = ''.join('<tr><td>{}</td><td>{} ± {}</td><td>{} ± {}</td></tr>'.format(r["model"], r["teer_mean"], r["teer_sem"], r["thickness_mean"], r["thickness_sem"]) for r in self.facts["physical_properties"])
        fd = '<section id="tbl7"><table><tr><td>FD20</td><td>9.7 × 10–7</td><td>5.6 × 10–7</td><td>unused</td></tr></table></section>'
        fixture = header + rows + '</table></section>' + fd
        self.assertEqual(verifier.verify(fixture, self.facts)["physical_summary_rows_verified"], 4)
        for bad in [fixture.replace('126 ± 2', '127 ± 2'), fixture.replace('Hu-Mic', 'ALI')]:
            with self.assertRaises(ValueError):
                verifier.verify(bad, self.facts)


if __name__ == "__main__":
    unittest.main()
