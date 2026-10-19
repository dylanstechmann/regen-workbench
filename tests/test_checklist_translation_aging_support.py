"""Check fixed-gene linearity and metadata-only cohort support diagnostics."""
import importlib.util
import json
from pathlib import Path
import unittest

try:
    import numpy as np
except ImportError:
    np = None

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "studies/checklist-translation-2026-10-19/aging"
SPEC = importlib.util.spec_from_file_location("translation_freeze", HERE / "freeze_populations.py")
FREEZE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FREEZE)


class TranslationSupportMetadataTests(unittest.TestCase):
    @staticmethod
    def rows(ages, prefix):
        return [{"donor": prefix+str(i), "age": age, "sex": "female", "processing_label": "A"} for i, age in enumerate(ages)]

    def test_shared_bins_do_not_mean_matched_ages(self):
        result = FREEZE.populations(self.rows([21, 30, 61], "a"), self.rows([28, 39, 68], "b"))
        self.assertEqual(result["rules"]["shared_age_span"], [28, 61])
        self.assertEqual(result["rules"]["shared_decade_starts"], [20, 30, 60])
        self.assertEqual(result["populations"]["shared_observed_age_span"]["GSE173078"]["ages_sorted"], [28, 39])
        self.assertEqual(result["populations"]["shared_nonempty_decade_bins"]["GSE173078"]["ages_sorted"], [28, 39, 68])

    def test_duplicate_donor_cannot_increase_metadata_n(self):
        rows = self.rows([20, 30], "a")
        with self.assertRaisesRegex(ValueError, "unique"):
            FREEZE.populations(rows+[rows[0]], self.rows([25, 35], "b"))

    def test_disjoint_age_ranges_are_not_silent_overlap(self):
        with self.assertRaisesRegex(ValueError, "No common"):
            FREEZE.populations(self.rows([20, 30], "a"), self.rows([60, 70], "b"))

    def test_real_population_changes_are_explicit(self):
        frozen = json.loads((HERE / "frozen_populations.json").read_text())
        restricted = frozen["populations"]["shared_observed_age_span"]
        self.assertEqual(restricted["GSE164241"]["n_donors"], 9)
        self.assertEqual(restricted["GSE173078"]["n_donors"], 8)
        self.assertEqual(max(restricted["GSE173078"]["ages_sorted"]), 45)
        self.assertEqual(max(restricted["GSE164241"]["ages_sorted"]), 61)
        self.assertFalse(frozen["clinical_age_matching"])
        self.assertFalse(frozen["gene_expression_used"])


@unittest.skipIf(np is None, "optional NumPy runtime required")
class TranslationGeneAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("translation_gene_analysis", HERE / "analyze_gene_support.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    @staticmethod
    def metadata():
        return [{"donor": str(i), "age": age, "sex": "male" if male else "female", "processing": version}
                for i, (age, male, version) in enumerate((age, male, version) for age in [20, 40, 60] for male in [0, 1] for version in [0, 1])]

    def test_joint_gene_OLS_reconstructs_mean_panel_with_known_slope(self):
        metadata = self.metadata()
        slopes = np.arange(1, 9) / 10
        y = np.asarray([3+slopes*row["age"]/10 + 2*(row["sex"] == "male") + row["processing"] for row in metadata])
        fit = self.module.fit_genes(metadata, y, "age_sex_processing")
        self.assertEqual(fit["status"], "descriptive_only")
        np.testing.assert_allclose(fit["gene_slopes"], slopes, rtol=0, atol=1e-12)
        self.assertAlmostEqual(fit["panel_slope"], slopes.mean(), places=12)

    def test_all_gene_omissions_are_equal_weight_diagnostics(self):
        slopes = [-1, 2, 3, 4, 5, 6, 7, 8]
        result = self.module.omission_slopes(slopes)
        self.assertEqual(len(result), 8)
        for i, value in enumerate(result):
            self.assertAlmostEqual(value, (sum(slopes)-slopes[i])/7)

    def test_duplicate_or_unknown_covariates_do_not_enter_a_fit(self):
        metadata = self.metadata()
        y = np.ones((len(metadata), 8))
        with self.assertRaisesRegex(ValueError, "One row per donor"):
            self.module.fit_genes(metadata+[metadata[0]], np.vstack([y, y[0]]), "age_only")
        metadata[0]["processing"] = 2
        with self.assertRaisesRegex(ValueError, "Unknown source"):
            self.module.fit_genes(metadata, y, "age_sex_processing")

    def test_rank_failure_keeps_missing_coefficient_instead_of_dropping_covariate(self):
        metadata = [{**row, "sex": "female"} for row in self.metadata()]
        fit = self.module.fit_genes(metadata, np.ones((len(metadata), 8)), "age_sex_processing")
        self.assertEqual(fit["status"], "rank_deficient")
        self.assertIsNone(fit["panel_slope"])
        self.assertIsNone(fit["gene_slopes"])

    def test_small_residual_df_remains_an_explicit_failure(self):
        metadata = self.metadata()[:3]
        fit = self.module.fit_genes(metadata, np.ones((3, 8)), "age_only")
        self.assertNotEqual(fit["status"], "descriptive_only")
        self.assertIsNone(fit["panel_slope"])

    def test_published_rows_keep_every_gene_omission_and_shared_donor_design(self):
        genes = self.module.read_tsv(HERE / "derived/gene_contributions.tsv")
        omissions = self.module.read_tsv(HERE / "derived/all_gene_omissions.tsv")
        self.assertEqual(len(genes), 192)
        self.assertEqual(len(omissions), 192)
        plan = json.loads((HERE / "analysis_plan.json").read_text())
        self.assertEqual({row["gene"] for row in genes}, set(plan["genes"]))
        panels = self.module.read_tsv(HERE / "derived/fixed_panel_age_effects.tsv")
        for panel in panels:
            current = [row for row in genes if all(row[key] == panel[key] for key in ["population", "score_mode", "model"])]
            self.assertEqual(len(current), 8)
            self.assertEqual({row["n_donors"] for row in current}, {panel["n_donors"]})
            self.assertAlmostEqual(sum(float(row["equal_weight_panel_contribution"]) for row in current), float(panel["panel_slope"]), places=12)

    def test_all_donor_influence_rows_remain_distinct_from_gene_replicates(self):
        rows = self.module.read_tsv(HERE / "derived/donor_omissions.tsv")
        self.assertEqual(len(rows), 252)
        self.assertEqual(len({(row["cohort"], row["omitted_donor"]) for row in rows}), 25)

    def test_receipts_pin_inputs_populations_and_all_output_tables(self):
        summary = json.loads((HERE / "derived/analysis_summary.json").read_text())
        self.assertEqual(summary["plan_sha256_lf_text"], FREEZE.text_sha(HERE / "analysis_plan.json"))
        self.assertEqual(summary["script_sha256_lf_text"], FREEZE.text_sha(HERE / "analyze_gene_support.py"))
        self.assertEqual(summary["frozen_populations_sha256_lf_text"], FREEZE.text_sha(HERE / "frozen_populations.json"))
        for name, expected in summary["output_sha256_lf_text"].items():
            self.assertEqual(FREEZE.text_sha(HERE / "derived" / name), expected)
        self.assertEqual(summary["new_source_fetches"], 0)


if __name__ == "__main__":
    unittest.main()
