"""Protect cohort qualification, donor units and fixed-panel age transport."""
import csv
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
except ImportError:
    np = None

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "studies/checklist-followup-2026-10-19/aging"
SPEC = importlib.util.spec_from_file_location("followup_aging_metadata", HERE / "qualify_sources.py")
METADATA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(METADATA)


class IndependentAgingMetadataTests(unittest.TestCase):
    def test_declared_samples_cannot_hide_a_missing_or_duplicate_library(self):
        soft = "^SERIES = GSE1\n!Series_sample_id = GSM1\n!Series_sample_id = GSM2\n^SAMPLE = GSM1\n!Sample_title = one\n"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "metadata.gz"
            with gzip.open(path, "wt") as handle:
                handle.write(soft)
            with self.assertRaisesRegex(ValueError, "Declared GEO samples"):
                METADATA.read_soft(path)

    def test_same_characteristic_cannot_supply_conflicting_ages(self):
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            METADATA.characteristics({"Sample_characteristics_ch1": ["age: 35", "age: 70"]})

    def test_paired_healing_sides_are_one_volunteer(self):
        records = [{"accession": "GSM" + str(i), "Sample_title": [title], "Sample_characteristics_ch1": ["tissue: palatal gingiva"]}
                   for i, title in enumerate(["1365_01con [RNA-Seq]", "1366_01pw [RNA-Seq]"])]
        rows = METADATA.sample_rows({"accession": "GSE111523"}, records)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({row["donor_code"] for row in rows}), 1)
        self.assertEqual({row["age_years"] for row in rows}, {""})

    def test_published_metadata_keeps_sex_imbalance_and_exclusions(self):
        with (HERE / "derived/GSE173078_sample_manifest.tsv").open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        healthy = [row for row in rows if row["phenotype"] == "Healthy"]
        self.assertEqual(len(rows), 36)
        self.assertEqual(len({row["donor_code"] for row in rows}), 36)
        self.assertEqual(len(healthy), 12)
        self.assertEqual(sum(row["sex"] == "female" for row in healthy), 10)
        self.assertEqual(sorted(float(row["age_years"]) for row in healthy if row["sex"] == "male"), [32, 39])
        with (HERE / "derived/candidate_qualification.tsv").open(encoding="utf-8") as handle:
            candidates = list(csv.DictReader(handle, delimiter="\t"))
        cilia = next(row for row in candidates if row["series"] == "GSE312885")
        self.assertIn("pooled", cilia["status"])


@unittest.skipIf(np is None, "optional NumPy runtime required")
class IndependentAgingAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("followup_aging_fixed_panels", HERE / "analyze_fixed_panels.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    @staticmethod
    def records():
        return [{"donor_code": f"d{i}", "phenotype": "Healthy", "age_years": age, "sex": "female", "batch": batch,
                 "score_mean_log1p_cpm": 4 + .02*age + (batch == "B")*3}
                for i, (batch, age) in enumerate([(batch, age) for batch in ["A", "B"] for age in [25, 45, 65]])]

    def test_age_slope_unit_and_batch_adjustment_recover_known_effect(self):
        result = self.module.fit_age(self.records(), "female_age_batch")
        self.assertEqual(result["status"], "descriptive_only")
        self.assertAlmostEqual(result["slope_per_decade"], .2, places=12)

    def test_disease_or_duplicate_donor_cannot_expand_healthy_n(self):
        records = self.records()
        with self.assertRaisesRegex(ValueError, "one independent"):
            self.module.fit_age(records + [records[0]], "female_age_batch")
        records[0]["phenotype"] = "Periodontitis"
        with self.assertRaisesRegex(ValueError, "Disease/gingivitis"):
            self.module.fit_age(records, "female_age_batch")

    def test_unsupported_sex_covariate_fails_without_dropping_it(self):
        result = self.module.fit_age(self.records(), "all_healthy_age_sex_batch")
        self.assertEqual(result["status"], "rank_deficient")
        self.assertEqual(result["slope_per_decade"], "")

    def test_unknown_batch_cannot_silently_become_reference_batch(self):
        records = self.records()
        records[0]["batch"] = "unknown"
        with self.assertRaisesRegex(ValueError, "Unknown sex or batch"):
            self.module.fit_age(records, "female_age_batch")

    def test_gene_counts_use_all_features_for_library_denominator(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "counts.gz"
            with gzip.open(path, "wt") as handle:
                handle.write('"A"\t"B"\n"PANEL"\t10\t20\n"OTHER"\t90\t80\n')
            names, totals, selected, n = self.module.read_counts(path, {"A", "B"}, {"PANEL"})
            self.assertEqual(names, ["A", "B"])
            self.assertEqual(totals.tolist(), [100, 100])
            self.assertEqual(set(selected), {"PANEL"})
            self.assertEqual(n, 2)

    def test_duplicate_gene_or_fractional_count_cannot_be_picked_or_summed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "counts.gz"
            for data in ['"A"\n"G"\t1\n"G"\t2\n', '"A"\n"G"\t1.5\n']:
                with gzip.open(path, "wt") as handle:
                    handle.write(data)
                with self.assertRaises(ValueError):
                    self.module.read_counts(path, {"A"}, {"G"})

    def test_receipt_pins_primary_and_posthoc_outputs_separately(self):
        summary = json.loads((HERE / "derived/analysis_summary.json").read_text())
        self.assertEqual(summary["plan_sha256_lf_text"], self.module.sha_text(HERE / "analysis_plan.json"))
        self.assertEqual(summary["script_sha256_lf_text"], self.module.sha_text(HERE / "analyze_fixed_panels.py"))
        self.assertEqual(summary["source_receipts_sha256_lf_text"], self.module.sha_text(HERE / "source_receipts.json"))
        self.assertEqual(summary["annotation_sensitivity_plan_sha256_lf_text"], self.module.sha_text(HERE / "annotation_sensitivity_plan.json"))
        for name, expected in summary["output_sha256_lf_text"].items():
            self.assertEqual(self.module.sha_text(HERE / "derived" / name), expected)
        coverage = self.module.read_tsv(HERE / "derived/fixed_panel_coverage.tsv")
        self.assertEqual(next(row for row in coverage if row["panel"] == "inflammation")["missing_genes"], "CXCL8")
        alias = self.module.read_tsv(HERE / "derived/annotation_sensitivity_age_effects.tsv")
        self.assertTrue(all(row["analysis_status"] == "posthoc_annotation_sensitivity" and row["n_genes"] == "9" for row in alias))

    def test_donor_omission_counts_do_not_use_genes_as_replicates(self):
        rows = self.module.read_tsv(HERE / "derived/healthy_age_donor_omissions.tsv")
        self.assertEqual(len(rows), 6*(10+12))
        for panel in {row["panel"] for row in rows}:
            self.assertEqual(len([row for row in rows if row["panel"] == panel and row["model"] == "female_age_batch"]), 10)


if __name__ == "__main__":
    unittest.main()
