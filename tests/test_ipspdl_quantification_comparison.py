"""Integrity and descriptive-sensitivity checks on small synthetic estimates."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


STUDY = Path(__file__).resolve().parents[1] / "studies/dental-regeneration-2026-10-09"
SPEC = importlib.util.spec_from_file_location("ipspdl_comparison", STUDY / "compare_ipspdl_quantification.py")
comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparison)
HAS_SCIENCE = all(importlib.util.find_spec(module) is not None for module in ("numpy", "pandas", "matplotlib"))


def quant_file(path: Path, rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["Name", "Length", "EffectiveLength", "TPM", "NumReads"])
        writer.writerows((name, length, length-10, tpm, tpm) for name, length, tpm in rows)


def record(layout: str = "paired") -> dict:
    return {"command": {"salmon_version": "2.7.0", "libType": "A", "threads": 8,
                        "mates1": ["/reads/R1.fastq.gz"] if layout == "paired" else [],
                        "mates2": ["/reads/R2.fastq.gz"] if layout == "paired" else [],
                        "unmatedReads": [] if layout == "paired" else ["/reads/R.fastq.gz"]},
            "metadata": {"salmon_version": "2.7.0", "num_processed": 1000,
                         "num_valid_targets": 6, "num_mapped": 900, "percent_mapped": 90,
                         "num_decoy_targets": 0, "num_decoy_fragments": 0,
                         "meta_info_complete": True, "em_converged": True, "quant_errors": [],
                         "seq_bias_correct": True, "gc_bias_correct": True,
                         "detected_library_type": "IU" if layout == "paired" else "U", "diagnostics": []},
            "library": {"expected_format": "IU" if layout == "paired" else "U",
                        "strand_mapping_bias": 0.51, "num_incompatible_fragments": 0}}


class InputIntegrity(unittest.TestCase):
    def test_large_reference_sensitive_gene_changes_are_exposed_without_common_zeros(self):
        rows = comparison.largest_gene_changes({"lost": 1000., "stable": 20., "zero": 0.},
                                               {"lost": 0., "stable": 20., "zero": 0., "gained": 100.}, 1., 2)
        self.assertEqual([row["gene_id"] for row in rows], ["lost", "gained"])
        self.assertEqual(rows[0]["TPM_change"], -1000.)
        self.assertLess(rows[0]["log2_TPM_plus_1_change"], -9.)
        self.assertGreater(rows[1]["log2_TPM_plus_1_change"], 6.)

    def test_one_run_using_a_different_index_is_rejected(self):
        metadata = {"R1": {"baseline": record(), "candidate": record()},
                    "R2": {"baseline": record(), "candidate": record()}}
        comparison.validate_index_consistency(metadata)
        metadata["R2"]["candidate"]["metadata"]["index_seq_hash"] = "other-index"
        with self.assertRaisesRegex(ValueError, "Inconsistent candidate index"):
            comparison.validate_index_consistency(metadata)

    def test_reference_receipt_hash_mismatch_stops_comparison(self):
        inputs = {"transcripts": {"path": "/ref/transcripts.fa.gz", "sha256": "abc", "bytes": 123},
                  "gtf": {"path": "/ref/genes.gtf.gz", "sha256": "def", "bytes": 456}}
        receipt = {"baseline": {"receipt": {"files": [{"filename": "transcripts.fa.gz", "sha256": "abc", "bytes": 123}]}}}
        checks = comparison.validate_reference_files(inputs, receipt)
        self.assertEqual(checks[0]["explicit_filename_hash_entries_checked"], 1)
        self.assertEqual(checks[1]["explicit_filename_hash_entries_checked"], 0)
        receipt["baseline"]["receipt"]["files"][0]["sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "receipt hash mismatch"):
            comparison.validate_reference_files(inputs, receipt)
        with self.assertRaisesRegex(ValueError, "candidate reference receipt hash mismatch"):
            comparison.validate_reference_files(inputs, {"candidate": {"receipt": {"transcript_sha256": "different"}}})

    def test_reordered_targets_allowed_but_missing_renamed_and_changed_length_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quant.sf"
            rows = [("ENST1.1|ENSG1.1|x", 100, 1.0), ("ENST2.1|ENSG1.1|x", 200, 2.0)]
            quant_file(path, rows)
            values, expected = comparison.read_quant(path)
            self.assertEqual(values, {"ENSG1": 3.0})
            quant_file(path, list(reversed(rows)))
            self.assertEqual(comparison.read_quant(path, expected)[0], values)
            for changed in (rows[:1], [rows[0], ("ENST3.1|ENSG1.1|x", 200, 2)],
                            [rows[0], (rows[1][0], 201, 2)]):
                with self.subTest(changed=changed):
                    quant_file(path, changed)
                    with self.assertRaisesRegex(ValueError, "Target.*mismatch"):
                        comparison.read_quant(path, expected)

    def test_duplicate_negative_and_nan_estimates_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quant.sf"
            good = ("ENST1|ENSG1|x", 100, 1)
            for rows in ([good, good], [(good[0], 100, -1)], [(good[0], 100, "nan")]):
                quant_file(path, rows)
                with self.assertRaises(ValueError):
                    comparison.read_quant(path)

    def test_missing_and_extra_sample_outputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = [{"run": "R1"}, {"run": "R2"}]
            quant_file(root / "R1/quant.sf", [("ENST1|ENSG1|x", 100, 1)])
            with self.assertRaisesRegex(ValueError, "missing=.*R2"):
                comparison.validate_sample_directories(expected, root)
            quant_file(root / "R2/quant.sf", [("ENST1|ENSG1|x", 100, 1)])
            comparison.validate_sample_directories(expected, root)
            quant_file(root / "R3/quant.sf", [("ENST1|ENSG1|x", 100, 1)])
            with self.assertRaisesRegex(ValueError, "extra=.*R3"):
                comparison.validate_sample_directories(expected, root)

    def test_read_identity_fragment_totals_and_layout_must_agree(self):
        sample = {"run": "R1", "layout": "paired"}
        baseline, candidate = record(), record()
        candidate["command"]["mates1"] = ["/different-mount/R1.fastq.gz"]
        comparison.validate_run_pair(sample, baseline, candidate)
        candidate["command"]["mates1"] = ["/reads/wrong.fastq.gz"]
        with self.assertRaisesRegex(ValueError, "Input-read mismatch"):
            comparison.validate_run_pair(sample, baseline, candidate)
        candidate = record()
        candidate["metadata"]["num_processed"] += 1
        with self.assertRaisesRegex(ValueError, "Processed-fragment mismatch"):
            comparison.validate_run_pair(sample, baseline, candidate)
        with self.assertRaisesRegex(ValueError, "layout disagrees"):
            comparison.validate_run_pair({"run": "R1", "layout": "single/unspecified"}, baseline, baseline)

    def test_other_setting_changes_are_retained_without_expected_path_and_thread_changes(self):
        baseline, candidate = record(), record()
        baseline["command"].update({"index": "/old", "output": "/old/R1"})
        candidate["command"].update({"index": "/new", "output": "/new/R1", "threads": 2})
        self.assertEqual(comparison.setting_changes(baseline, candidate), [])
        candidate["metadata"]["gc_bias_correct"] = False
        candidate["command"]["libType"] = "ISF"
        self.assertEqual({row["setting"] for row in comparison.setting_changes(baseline, candidate)},
                         {"metadata.gc_bias_correct", "command.libType"})


@unittest.skipUnless(HAS_SCIENCE, "NumPy, pandas and matplotlib required; run in workbench image")
class DescriptiveSensitivity(unittest.TestCase):
    def test_common_zero_genes_do_not_inflate_expression_correlation(self):
        left, right = {"g1": 1., "g2": 2., "g3": 4.}, {"g1": 4., "g2": 2., "g3": 1.}
        empty = {f"zero{i}": 0. for i in range(5000)}
        result = comparison.expression_agreement({**empty, **left}, {**empty, **right}, 1.0)
        self.assertEqual(result["expressed_either_gene_count"], 3)
        self.assertEqual(result["excluded_below_threshold_gene_count"], 5000)
        self.assertAlmostEqual(result["spearman_expressed_tpm"], -1.)
        self.assertLess(result["pearson_log2_tpm_plus_1"], -.9)
        zero = comparison.expression_agreement(empty, empty, 1.)
        self.assertIsNone(zero["pearson_log2_tpm_plus_1"])

    def test_marker_sums_and_paired_exclusion_retain_different_group_n(self):
        samples = [{"run": f"R{i}", "sample_name": f"P{i}", "group": "primary PDL",
                    "layout": "single/unspecified" if i == 3 else "paired"} for i in (1, 2, 3)]
        baseline = {f"R{i}": {"ENSG1": value, "ENSG2": value} for i, value in ((1, 1.), (2, 4.), (3, 50.))}
        candidate = {run: {gene: value/2 for gene, value in values.items()} for run, values in baseline.items()}
        rows, groups, _ = comparison.marker_tables(samples, {"baseline": baseline, "candidate": candidate},
                                                   {"ENSG1": "POSTN", "ENSG2": "POSTN"}, ["POSTN", "MISSING"])
        postn = [row for row in groups if row["gene_symbol"] == "POSTN"]
        self.assertEqual([(row["scope"], row["n"], row["baseline_median_TPM"]) for row in postn],
                         [("all", 3, 8.), ("paired_only", 2, 5.)])
        self.assertEqual(postn[1]["candidate_median_TPM"], 2.5)
        self.assertTrue(all(not row["annotation_present"] for row in rows if row["gene_symbol"] == "MISSING"))

    def test_pca_rotation_and_sign_are_arbitrary_but_changed_geometry_is_reported(self):
        import numpy as np
        base = {"genes": ["a", "b"], "coordinates": np.array([[-1., 0.], [0., 1.], [1., -1.]]), "explained": np.array([.6, .4])}
        rotated = {**base, "coordinates": base["coordinates"] @ np.array([[0., 1.], [-1., 0.]])}
        agreement, _ = comparison.pca_agreement(base, rotated)
        self.assertLess(agreement["orthogonal_alignment_relative_residual"], 1e-12)
        self.assertAlmostEqual(agreement["pairwise_distance_pearson"], 1.)
        changed = {**base, "genes": ["b", "c"], "coordinates": base["coordinates"] * np.array([3., 1.])}
        agreement, _ = comparison.pca_agreement(base, changed)
        self.assertGreater(agreement["orthogonal_alignment_relative_residual"], .5)
        self.assertEqual(agreement["selected_gene_overlap"], 1)

    def test_complete_comparison_retains_hashes_changes_and_library_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples = [{"run": f"R{i}", "sample_name": f"S{i}", "group": group,
                        "layout": "single/unspecified" if i == 8 else "paired"}
                       for i, group in enumerate(["iPS-PDL"]*3 + ["iPS"]*3 + ["primary PDL"]*3)]
            manifest = root / "manifest.tsv"
            comparison.write_tsv(manifest, samples)
            targets = [(f"ENST{i}|ENSG{i}|x", 100+i) for i in range(6)]
            for version in ("baseline", "candidate"):
                for index, sample in enumerate(samples):
                    run_root = root/version/sample["run"]
                    values = [(name, length, (index+1)**((i % 3)+1)+(i*2)) for i, (name, length) in enumerate(targets)]
                    if version == "candidate":
                        values = [(name, length, tpm*(.8 if i % 2 else 1.1)) for i, (name, length, tpm) in enumerate(values)]
                    quant_file(run_root/"quant.sf", values)
                    item = record(sample["layout"])
                    if version == "candidate":
                        item["metadata"].update({"num_decoy_targets": 194, "num_decoy_fragments": 40, "percent_mapped": 86., "num_mapped": 860})
                        if index == 0:
                            item["metadata"]["detected_library_type"] = "ISF"
                            item["metadata"]["gc_bias_correct"] = False
                    (run_root/"aux_info").mkdir()
                    for path, value in ((run_root/"cmd_info.json", item["command"]), (run_root/"aux_info/meta_info.json", item["metadata"]),
                                        (run_root/"lib_format_counts.json", item["library"])):
                        path.write_text(json.dumps(value), encoding="utf-8")
            gtf = root/"genes.gtf"
            gtf.write_text("".join(f'chr1\tx\tgene\t1\t100\t.\t+\t.\tgene_id "ENSG{i}"; gene_name "{symbol}";\n' for i, symbol in enumerate(["POSTN", "COL1A1", "SCX", "TNMD", "SOX2", "NANOG"])), encoding="utf-8")
            transcripts = root/"transcripts.fa"
            transcripts.write_text(">fixture\nA\n", encoding="utf-8")
            receipts = {}
            for version in ("baseline", "candidate"):
                receipts[version] = root/f"{version}_receipt.json"
                receipts[version].write_text(json.dumps({"scope": version, "fixture": True}), encoding="utf-8")
            args = argparse.Namespace(manifest=manifest, gtf=gtf, transcripts=transcripts, baseline_dir=root/"baseline", candidate_dir=root/"candidate",
                                      baseline_reference_manifest=receipts["baseline"], candidate_reference_manifest=receipts["candidate"], out_dir=root/"sensitivity",
                                      minimum_tpm=1., pca_maximum_genes=4)
            result = comparison.compare(args)
            self.assertEqual(result["target_validation"]["target_count"], 6)
            self.assertEqual(result["pca"]["paired_only"]["group_n"], {"iPS-PDL": 3, "iPS": 3, "primary PDL": 2})
            self.assertEqual(result["quantification_setting_changes"], [{"run": "R0", "setting": "metadata.gc_bias_correct", "baseline": True, "candidate": False}])
            self.assertTrue(result["mapping_by_run"][0]["detected_library_type_changed"])
            self.assertEqual(result["mapping_by_run"][0]["mapping_rate_change_percentage_points"], -4.)
            persisted = json.loads((args.out_dir/"candidate_reference_manifest.json").read_text())
            self.assertEqual(persisted["file"]["sha256"], comparison.sha256_file(receipts["candidate"]))
            self.assertEqual(persisted["receipt"], {"scope": "candidate", "fixture": True})
            self.assertTrue((args.out_dir/"pca_reference_sensitivity.png").is_file())
            self.assertTrue((args.out_dir/"gene_TPM_candidate.tsv").is_file())
            self.assertEqual(result["largest_gene_change_table"]["rows"], 9*6)
            self.assertTrue(any("No assigned donor pairing" in item for item in result["limitations"]))
            # A later failed/incomplete library must stop the comparison rather than silently
            # converting it into an unbalanced reference comparison.
            shutil.rmtree(args.candidate_dir/"R8")
            with self.assertRaisesRegex(ValueError, "Sample mismatch"):
                comparison.compare(args)


if __name__ == "__main__":
    unittest.main()
