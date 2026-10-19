"""Checks for estimand, unit, sample hierarchy and unsupported-transport errors."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("rapamycin_translation", HERE / "analyze_rapamycin.py")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


class RapamycinTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
        cls.results, cls.tissues = model.calculate(cls.inputs)

    def test_source_ic50_scale_and_biological_unit(self):
        values = self.results["PC3_cell_selectivity"]
        self.assertAlmostEqual(values["rapamycin"]["C1_ic50_pM"]["mean"], 63.30875)
        self.assertAlmostEqual(values["DL001"]["C2_ic50_pM"]["mean"], 26245.41275)
        self.assertEqual(values["rapamycin"]["C1_ic50_pM"]["n"], 4)
        self.assertEqual(values["DL001"]["mean_of_paired_ratios"]["n"], 4)
        self.assertEqual(self.inputs["dl001_ic50"]["technical_replicates_per_biological_experiment"], 3)

    def test_mean_ratio_is_distinct_from_ratio_of_means(self):
        values = self.results["PC3_cell_selectivity"]
        self.assertAlmostEqual(values["DL001"]["mean_of_paired_ratios"]["mean"], 433.37688912504683)
        self.assertAlmostEqual(values["DL001"]["ratio_of_mean_ic50s"], 350.2377061759368)
        comparison = values["relative_DL001_vs_rapamycin"]
        self.assertAlmostEqual(comparison["ratio_of_compound_mean_paired_selectivities"], 44.70379250082162)
        self.assertAlmostEqual(comparison["ratio_of_compound_ratios_of_mean_ic50s"], 41.45316492822587)
        self.assertFalse(comparison["cross_compound_replicate_pairing_assumed"])

    def test_broken_replicate_pairing_is_rejected(self):
        rows = copy.deepcopy(self.inputs["dl001_ic50"]["replicates"])
        rows[0]["c2_ic50_source_fM"], rows[1]["c2_ic50_source_fM"] = rows[1]["c2_ic50_source_fM"], rows[0]["c2_ic50_source_fM"]
        with self.assertRaises(ValueError):
            model.selectivity_summaries(rows)

    def test_invalid_potency_does_not_generate_selectivity(self):
        for invalid in [0, -1, True, None, "1", float("nan"), float("inf")]:
            with self.subTest(invalid=invalid):
                rows = copy.deepcopy(self.inputs["dl001_ic50"]["replicates"])
                rows[0]["c1_ic50_source_fM"] = invalid
                with self.assertRaises(ValueError):
                    model.selectivity_summaries(rows)

    def test_tissue_readouts_and_unequal_c1_effects_remain_visible(self):
        def row(tissue, pathway, compound):
            return next(r for r in self.tissues if r["tissue"] == tissue and r["pathway_readout"] == pathway and r["compound"] == compound)
        self.assertEqual(len(self.tissues), 18)
        self.assertAlmostEqual(row("liver", "C1", "DL001")["mean"], .44924725)
        self.assertAlmostEqual(row("liver", "C1", "rapamycin")["mean"], .046831)
        self.assertEqual(row("heart", "C1", "rapamycin")["mean"], 0)
        self.assertGreater(row("heart", "C2", "DL001")["mean"], 1)
        self.assertFalse(self.inputs["dl001_tissue_pathway"]["free_parent_exposure_measured"])
        self.assertFalse(self.inputs["dl001_tissue_pathway"]["testis_in_11_tissue_panel"])

    def test_blood_source_values_do_not_become_matched_testis_exposure(self):
        blood = self.results["reported_whole_blood_compound_concentration_ng_per_mL"]
        self.assertEqual(blood["DL001"]["n"], 9)
        self.assertEqual(blood["rapamycin"]["n"], 18)
        self.assertAlmostEqual(blood["DL001"]["mean"], 186.27777777777777)
        self.assertAlmostEqual(blood["rapamycin"]["sem"], 41.130858819189108)
        self.assertFalse(self.inputs["dl001_blood_parent"]["same_population_as_figure3d"])
        self.assertIsNone(self.inputs["dl001_blood_parent"]["target_or_testis_intracellular_concentrations"])

    def test_reproductive_gate_cannot_be_passed_by_c2_sparing(self):
        for compound in ["DL001", "rapamycin"]:
            self.assertFalse(self.results["candidate_joint_evidence_gates"][compound]["joint_human_reproductive_protection_comparison_eligible"])
        outcome = model.reproductive_gate({"mTORC2_sparing": True})
        self.assertIn("direct_reproductive_endpoints", outcome["missing"])
        self.assertIsNone(outcome["human_reproductive_risk_reduction_estimate"])
        complete = {k: True for k in self.inputs["reproductive_comparison_gate_inputs"]["DL001"]}
        self.assertTrue(model.reproductive_gate(complete)["joint_human_reproductive_protection_comparison_eligible"])
        for value in [1, "true", None, False]:
            self.assertFalse(model.reproductive_gate({**complete, "direct_reproductive_endpoints": value})["joint_human_reproductive_protection_comparison_eligible"])

    def test_mouse_weight_and_human_respondents_do_not_fill_missing_endpoints(self):
        mouse = self.results["adult_mouse_testis_mass"]
        self.assertAlmostEqual(mouse["rapamycin_to_control_reported_mean_ratio"], .4609740670461733)
        self.assertEqual(mouse["control_n_animals"], 5)
        self.assertEqual(mouse["rapamycin_n_animals"], 4)
        self.assertIsNone(mouse["human_testicular_volume_inference"])
        self.assertEqual(self.inputs["human_reproductive"]["respondents"], 95)
        self.assertIsNone(self.inputs["human_reproductive"]["n_semen_analysis_by_regimen"])
        self.assertIsNone(self.results["human_transplant_descriptive_contrasts"]["probability_of_infertility_or_recovery"])
        self.assertFalse(self.results["human_safe_analogue_or_equivalent_benefit_identified"])


if __name__ == "__main__":
    unittest.main()
