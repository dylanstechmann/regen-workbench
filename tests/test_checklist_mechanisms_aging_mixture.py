"""Audit partial coverage, nonoverlapping compartments and donor/RNA units."""
import importlib.util
import json
from pathlib import Path
import unittest

try:
    import numpy as np
except ImportError:
    np = None

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "studies/checklist-mechanisms-2026-10-19/aging"
SPEC = importlib.util.spec_from_file_location("mechanism_aging_freeze", HERE / "freeze_composition_reference.py")
FREEZE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FREEZE)


class MechanismMixtureMetadataTests(unittest.TestCase):
    def test_overlapping_parent_and_child_cannot_double_count_a_label(self):
        coverage = {"T cells": {"mapped_to_groups": ["all_immune", "t_cells"], "n_cells": 9, "exclusion_reason": ""}}
        with self.assertRaisesRegex(ValueError, "double-count"):
            FREEZE.audit_labels(coverage, ["all_immune", "t_cells"], 9)

    def test_partial_capture_never_acquires_unknown_UMI_coverage(self):
        coverage = {"main": {"mapped_to_groups": ["all_main"], "n_cells": 99, "exclusion_reason": ""},
                    "rare": {"mapped_to_groups": [], "n_cells": 1, "exclusion_reason": "not retained"}}
        result = FREEZE.audit_labels(coverage, ["all_main"], 100)
        self.assertEqual(result["status"], "partial_captured_cell_mixture")
        self.assertEqual(result["captured_cell_fraction"], .99)
        self.assertIsNone(result["omitted_cell_UMIs"])
        self.assertFalse(result["whole_tissue_reconstruction"])

    @staticmethod
    def reference_fixture():
        rows = []
        for donor in range(13):
            for group, umis in [("A", 900 if donor == 12 else 1), ("B", 100 if donor == 12 else 9)]:
                rows.append({"donor": f"h{donor}", "cell_group": group, "condition": "healthy", "age": "40",
                             "sex": "female", "samples": f"s{donor}", "cellranger_versions": "3.0.1",
                             "n_cells": "1", "total_raw_umis": str(umis)})
        return rows

    def test_equal_donor_RNA_reference_is_not_pooled_counts(self):
        _, frozen, _ = FREEZE.freeze_reference(self.reference_fixture(), ["A", "B"])
        self.assertAlmostEqual(frozen["weights"]["A"], (12*.1+.9)/13)
        self.assertNotAlmostEqual(frozen["weights"]["A"], (12+900)/(120+1000))
        self.assertFalse(frozen["pooled_donor_counts_used"])

    def test_disease_donor_cannot_change_common_healthy_reference(self):
        rows = self.reference_fixture()
        rows.extend({**row, "donor": "disease", "condition": "periodontitis", "total_raw_umis": "100000"}
                    for row in rows[:2])
        _, frozen, _ = FREEZE.freeze_reference(rows, ["A", "B"])
        self.assertEqual(frozen["n_reference_donors"], 13)
        self.assertNotIn("disease", frozen["reference_donors"])
        self.assertAlmostEqual(frozen["weights"]["A"], (12*.1+.9)/13)

    def test_actual_omitted_labels_and_sparse_donors_remain_visible(self):
        coverage = json.loads((HERE / "derived/capture_coverage_audit.json").read_text())
        self.assertEqual(coverage["included_cells"], 85752)
        self.assertEqual(coverage["captured_cells"], 86138)
        self.assertEqual(sum(row["n_cells"] for row in coverage["omitted_labels"].values()), 386)
        self.assertEqual(sum(row["condition"] == "healthy" and row["strict20_eligible"] for row in coverage["donor_coverage"]), 8)
        self.assertFalse(coverage["whole_tissue_reconstruction"])


@unittest.skipIf(np is None, "optional NumPy runtime required")
class MechanismMixtureAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("mechanism_aging_analysis", HERE / "analyze_compartment_mixture.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_common_RNA_mixture_operates_before_log_and_preserves_observed_sum(self):
        observed, common, error = self.module.mix_gene_cpm(np.asarray([[10.], [0.]]), np.asarray([100., 900.]), np.asarray([.5, .5]))
        self.assertAlmostEqual(observed[0], 10000)
        self.assertAlmostEqual(common[0], 50000)
        self.assertAlmostEqual(error, 0)
        self.assertNotAlmostEqual(float(np.log1p(common[0])), float(.5*np.log1p(100000)))

    def test_raw_count_and_weight_failures_are_not_silent_scores(self):
        for counts in [np.asarray([[10.5], [0.]]), np.asarray([[-1.], [0.]]), np.asarray([[101.], [0.]]), np.asarray([[np.nan], [0.]])]:
            with self.assertRaises(ValueError):
                self.module.mix_gene_cpm(counts, np.asarray([100., 900.]), np.asarray([.5, .5]))
        with self.assertRaises(ValueError):
            self.module.mix_gene_cpm(np.asarray([[10.], [0.]]), np.asarray([100., 900.]), np.asarray([.3, .3]))

    def test_one_row_per_healthy_donor_required(self):
        row = {"donor": "one", "condition": "healthy", "age": 30, "sex": "female", "version": "3.0.1", "score": 1}
        with self.assertRaisesRegex(ValueError, "one row per"):
            self.module.fit_age([row, row], "all_healthy_age")
        with self.assertRaisesRegex(ValueError, "one row per"):
            self.module.fit_age([{**row, "condition": "periodontitis"}], "all_healthy_age")

    def test_known_age_slope_and_rank_failure(self):
        rows = [{"donor": str(i), "condition": "healthy", "age": age, "sex": "female", "version": "3.0.1", "score": 4+.03*age}
                for i, age in enumerate([20, 30, 40, 50])]
        self.assertAlmostEqual(self.module.fit_age(rows, "all_healthy_age")["slope_per_decade"], .3)
        failed = self.module.fit_age(rows, "all_healthy_age_sex_version")
        self.assertEqual(failed["status"], "rank_deficient")
        self.assertEqual(failed["slope_per_decade"], "")

    def test_same_donor_sets_are_used_across_score_types(self):
        effects = FREEZE.read_tsv(HERE / "derived/healthy_age_effects.tsv")
        self.assertEqual(len(effects), 6*3*5)
        for panel in {row["panel"] for row in effects}:
            for model in {row["model"] for row in effects}:
                current = [row for row in effects if row["panel"] == panel and row["model"] == model]
                self.assertEqual(len(current), 3)
                self.assertEqual(len({row["n_donors"] for row in current}), 1)

    def test_frozen_reference_and_published_output_hashes(self):
        summary = json.loads((HERE / "derived/analysis_summary.json").read_text())
        frozen = json.loads((HERE / "frozen_RNA_weights.json").read_text())
        self.assertEqual(summary["plan_sha256_lf_text"], FREEZE.sha_text(HERE / "analysis_plan.json"))
        self.assertEqual(summary["script_sha256_lf_text"], FREEZE.sha_text(HERE / "analyze_compartment_mixture.py"))
        self.assertEqual(summary["frozen_RNA_weights_sha256_lf_text"], FREEZE.sha_text(HERE / "frozen_RNA_weights.json"))
        self.assertEqual(frozen["metadata_script_sha256_lf_text"], FREEZE.sha_text(HERE / "freeze_composition_reference.py"))
        for name, expected in {**summary["output_sha256_lf_text"], **summary["metadata_output_sha256_lf_text"]}.items():
            self.assertEqual(FREEZE.sha_text(HERE / "derived" / name), expected)
        self.assertFalse(summary["whole_tissue_reconstruction"])

    def test_omission_rows_are_people_not_compartments_or_genes(self):
        rows = FREEZE.read_tsv(HERE / "derived/healthy_age_donor_omissions.tsv")
        self.assertEqual(len(rows), 6*3*2*13)
        self.assertEqual(len({row["omitted_donor"] for row in rows}), 13)


if __name__ == "__main__":
    unittest.main()
