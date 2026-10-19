"""Tests for donor nesting, unsupported models and mixture arithmetic."""
import importlib.util
import json
from pathlib import Path
import unittest

try:
    import numpy as np
except ImportError:
    np = None

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "studies" / "checklist-progress-2026-10-19" / "aging"


@unittest.skipIf(np is None, "optional NumPy runtime required for aging challenge")
class ChecklistAgingConfoundingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("checklist_aging_challenge", HERE / "challenge_donor_confounding.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    @staticmethod
    def records():
        # Crossed factors and a known conditional disease effect; deterministic.
        rows = []
        for disease in [False, True]:
            for male in [False, True]:
                for version in [False, True]:
                    for age in [25, 45]:
                        rows.append({"donor": str(len(rows)), "condition": "periodontitis" if disease else "healthy",
                                     "age": age, "sex": "male" if male else "female",
                                     "cellranger_versions": "3.0.1" if version else "2.0.0",
                                     "score_mean_log1p_cpm": 4 + 2*disease + .03*age - 3*male + 5*version})
        return rows

    def test_known_effect_with_crossed_confounders(self):
        result = self.module.fit_effect(self.records(), "age_sex_version")
        self.assertEqual(result["status"], "descriptive_only")
        self.assertAlmostEqual(result["coefficient"], 2, places=12)
        self.assertEqual(result["n_donors"], 16)

    def test_age_coefficient_is_per_decade_and_healthy_only(self):
        healthy = [row for row in self.records() if row["condition"] == "healthy"]
        result = self.module.fit_effect(healthy, "age_sex_version", "age")
        self.assertAlmostEqual(result["coefficient"], .3, places=12)
        with self.assertRaisesRegex(ValueError, "must not pool"):
            self.module.fit_effect(self.records(), "age", "age")

    def test_duplicate_person_is_not_extra_replication(self):
        records = self.records()
        with self.assertRaisesRegex(ValueError, "one row per donor"):
            self.module.fit_effect(records + [records[0]], "age")

    def test_rank_failure_retains_no_effect(self):
        records = self.records()
        for row in records:
            row["sex"] = "female"
        result = self.module.fit_effect(records, "age_sex_version")
        self.assertEqual(result["status"], "rank_deficient")
        self.assertEqual(result["coefficient"], "")

    def test_insufficient_residual_degrees_are_retained(self):
        records = self.records()[::4]  # Four donors, full-rank intercept/disease/age.
        records[1]["age"] = 35
        result = self.module.fit_effect(records, "age")
        self.assertEqual(result["status"], "insufficient_residual_df")
        self.assertEqual(result["coefficient"], "")

    def test_no_common_age_range_is_not_a_fitted_zero(self):
        records = self.records()
        for row in records:
            row["age"] = 70 if row["condition"] == "periodontitis" else 20
        self.assertIsNone(self.module.overlap_bounds(records))
        restricted = self.module.restrict_records(records, "age_overlap", None)
        result = self.module.fit_effect(restricted, "age_overlap")
        self.assertEqual(result["status"], "missing_condition_or_empty")
        self.assertEqual(result["coefficient"], "")

    def test_frozen_bounds_are_not_recomputed_after_removal(self):
        records = self.records()
        female = self.module.restrict_records(records, "female_age_overlap", (30, 50))
        self.assertTrue(all(row["sex"] == "female" and row["age"] == 45 for row in female))
        self.assertEqual(len(female), 4)

    @staticmethod
    def mixture_fixture():
        # Unequal RNA and cell fractions; equal-RNA averaging must occur before log.
        raw = []
        for group, umis, cells, count in [("fibroblasts_all", 1000, 100, 100),
                                           ("fibroblast_1", 100, 25, 100),
                                           ("fibroblast_2", 900, 75, 0)]:
            raw.append({"donor": "one", "cell_group": group, "total_raw_umis": umis,
                        "n_cells": cells, "gene_symbol": "G", "raw_count": count})
        scores = [{"donor": "one", "cell_group": "fibroblasts_all", "panel": "P",
                   "condition": "healthy", "age": 40, "score_mean_log1p_cpm": float(np.log1p(100000))}]
        coverage = [{"panel": "P", "included_gene_symbols": "G"}]
        plan = {"fixed_subgroup_rna_weights": [.5, .5], "minimum_cells_each_subgroup": 20}
        return raw, scores, coverage, plan

    def test_equal_rna_mixture_preserves_gene_scale_before_log(self):
        fixed, audit = self.module.build_fixed_mixture(*self.mixture_fixture())
        self.assertAlmostEqual(fixed[0]["score_mean_log1p_cpm"], np.log1p(500000), places=12)
        self.assertEqual(audit[0]["fibroblast1_rna_fraction"], .1)
        self.assertEqual(audit[0]["fibroblast1_cell_fraction"], .25)
        self.assertLess(abs(audit[0]["reconstruction_error"]), 1e-10)

    def test_broken_nesting_rejected_before_standardization(self):
        raw, scores, coverage, plan = self.mixture_fixture()
        raw[1]["raw_count"] = 99
        with self.assertRaisesRegex(ValueError, "counts do not sum"):
            self.module.build_fixed_mixture(raw, scores, coverage, plan)

    def test_original_score_is_checked_independently(self):
        raw, scores, coverage, plan = self.mixture_fixture()
        scores[0]["score_mean_log1p_cpm"] += 1
        with self.assertRaisesRegex(ValueError, "differs from original"):
            self.module.build_fixed_mixture(raw, scores, coverage, plan)

    def test_source_checksums_and_public_receipt(self):
        plan = json.loads((HERE / "analysis_plan.json").read_text())
        source = ROOT / plan["input_directory"]
        for filename, expected in plan["input_sha256_lf_text"].items():
            self.assertEqual(self.module.text_sha(source / filename), expected)
        summary = json.loads((HERE / "derived" / "analysis_summary.json").read_text())
        self.assertEqual(summary["plan_sha256_lf_text"], self.module.text_sha(HERE / "analysis_plan.json"))
        self.assertEqual(summary["script_sha256_lf_text"], self.module.text_sha(HERE / "challenge_donor_confounding.py"))
        self.assertFalse(summary["new_network_fetch"])
        for filename, expected in summary["output_sha256_lf_text"].items():
            self.assertEqual(self.module.text_sha(HERE / "derived" / filename), expected)

    def test_all_qualified_donors_preserved_in_real_mixture(self):
        audit = self.module.read_tsv(HERE / "derived" / "fibroblast_mixture_audit.tsv")
        self.assertEqual(len(audit), 18*5)
        self.assertEqual({row["status"] for row in audit}, {"included"})
        self.assertEqual(len({row["donor"] for row in audit}), 18)
        self.assertLess(max(abs(float(row["reconstruction_error"])) for row in audit), 1e-10)


if __name__ == "__main__":
    unittest.main()
