from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import regen_compute as compute
import regen_mcp

try:
    from rdkit import Chem
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False


class ComputeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.matrix = self.root / "matrix.csv"
        self.samples = self.root / "samples.csv"
        self.out = self.root / "report"
        self.matrix.write_text("gene,a,b,c,d\nUP,1,1,3,3\nFLAT,0,0,0,0\nOUTLIER,1,1,1,101\n", encoding="utf-8")
        self.samples.write_text("sample,group\na,young\nb,young\nc,old\nd,old\n", encoding="utf-8")
        self.record = Mock()

    def tearDown(self):
        self.temp.cleanup()

    def expression(self, *extra):
        compute.expression_contrast(["--matrix", str(self.matrix), "--samples", str(self.samples),
                                     "--reference", "young", "--comparison", "old", "--out", str(self.out),
                                     *extra], self.record)

    def compounds(self, text="id,smiles\nethanol,CCO\n", *extra):
        source = self.root / "compounds.csv"
        source.write_text(text, encoding="utf-8")
        compute.compound_screen(["--input", str(source), "--out", str(self.out),
                                 "--conformers", "3", *extra], self.record)

    def pipeline_fixture(self, signature_count=80, include_custom=False):
        signature, _, _ = compute._gene_set_metadata("senmayo")
        custom = list(dict.fromkeys(GENE for name in ("fridman", "sasp")
                                    for GENE in compute.GENE_SETS[name]))
        genes = list(dict.fromkeys(signature[:signature_count] + (custom if include_custom else [])
                                   + [f"BG{i}" for i in range(180)]))
        matrix = self.root / "pipeline_matrix.csv"
        samples = self.root / "pipeline_samples.csv"
        names = [f"S{i}" for i in range(8)]
        rows = ["gene," + ",".join(names)]
        for gene_index, gene in enumerate(genes):
            base = 2.0 + (gene_index % 19)
            values = []
            for sample_index in range(8):
                is_old = sample_index >= 4
                signature_shift = 3.0 if is_old and gene in signature else 0.0
                values.append(f"{base + sample_index * 0.01 + signature_shift:.4f}")
            rows.append(gene + "," + ",".join(values))
        matrix.write_text("\n".join(rows) + "\n", encoding="utf-8")
        sample_rows = ["sample,group,donor_id,batch_id"]
        for i, sample in enumerate(names):
            group = "old" if i >= 4 else "young"
            donor = ("O" if group == "old" else "Y") + str((i % 4) // 2 + 1)
            sample_rows.append(f"{sample},{group},{donor},{donor}_batch")
        samples.write_text("\n".join(sample_rows) + "\n", encoding="utf-8")
        return matrix, samples

    def test_contrast_known_effect_and_outlier_sensitivity(self):
        self.expression()
        result = json.loads((self.out / "contrast.json").read_text())
        genes = {row["gene"]: row for row in result["genes"]}
        self.assertEqual(genes["UP"]["log2_ratio"], 1.0)
        self.assertEqual(genes["UP"]["leave_one_out_min"], 1.0)
        self.assertTrue(genes["UP"]["direction_stable"])
        self.assertEqual(genes["FLAT"]["log2_ratio"], 0)
        self.assertFalse(genes["FLAT"]["direction_stable"])
        self.assertEqual(genes["OUTLIER"]["leave_one_out_min"], 0)
        self.assertFalse(genes["OUTLIER"]["direction_stable"])
        self.assertEqual(result["parameters"]["reference_n"], 2)
        self.assertIn("not confidence", (self.out / "README.md").read_text())
        self.record.assert_called_once()

    def test_sample_order_uses_identifiers(self):
        self.samples.write_text("sample,group\nd,old\nb,young\na,young\nc,old\n", encoding="utf-8")
        self.expression()
        genes = json.loads((self.out / "contrast.json").read_text())["genes"]
        self.assertEqual(next(g["log2_ratio"] for g in genes if g["gene"] == "UP"), 1)

    def test_manifest_hashes_exact_analyzed_snapshot(self):
        original = self.matrix.read_bytes()
        original_table = compute.table
        def mutate_after_read(data):
            self.matrix.write_text("changed", encoding="utf-8")
            return original_table(data)
        with patch.object(compute, "table", side_effect=mutate_after_read):
            self.expression()
        metadata = json.loads((self.out / "manifest.json").read_text())
        self.assertEqual((self.out / "matrix.input.csv").read_bytes(), original)
        self.assertEqual(metadata["inputs"]["matrix.input.csv"]["sha256"], hashlib.sha256(original).hexdigest())
        for name, info in metadata["outputs"].items():
            self.assertEqual(info["sha256"], hashlib.sha256((self.out / name).read_bytes()).hexdigest())

    def test_bad_expression_values_and_shapes_rejected_without_report(self):
        fixtures = [
            "gene,a,b,c,d\nX,1,2,nan,3\n", "gene,a,b,c,d\nX,1,2,inf,3\n",
            "gene,a,b,c,d\nX,-1,2,3,4\n", "gene,a,b,c,d\nX,1,2,3,\n",
            "gene,a,b,c,d\nX,1,2,3,4\nX,2,3,4,5\n", "gene,a,b,c,c\nX,1,2,3,4\n",
            "gene,a,b,c,d\nX,1,2,3\n", "gene,a,b,c,d\n=FORMULA,1,2,3,4\n",
        ]
        for data in fixtures:
            with self.subTest(data=data):
                self.matrix.write_text(data, encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.expression()
                self.assertFalse(self.out.exists())

    def test_bad_metadata_and_pseudocount(self):
        for value in ["nan", "inf", "0", "-1"]:
            with self.assertRaises(ValueError):
                self.expression("--pseudocount", value)
        for data in ["sample,group\na,young\na,young\nc,old\nd,old\n",
                     "sample,group\na,young\nb,old\nc,old\nd,old\n",
                     "sample,group\na,young\nb,young\nc,old\nx,old\n"]:
            self.samples.write_text(data, encoding="utf-8")
            with self.assertRaises(ValueError):
                self.expression()
        self.assertFalse(self.out.exists())

    def test_existing_output_preserved(self):
        self.out.mkdir()
        sentinel = self.out / "sentinel"
        sentinel.write_text("keep")
        with self.assertRaises(FileExistsError):
            self.expression()
        self.assertEqual(sentinel.read_text(), "keep")

    def test_failed_write_removes_only_new_report(self):
        with patch.object(compute, "write_csv", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.expression()
        self.assertFalse(self.out.exists())
        self.assertTrue(self.matrix.exists())
        self.record.assert_not_called()

    def test_reads_are_bounded(self):
        with patch.object(compute, "MAX_INPUT_BYTES", 4):
            with self.assertRaisesRegex(ValueError, "25 MiB"):
                self.expression()

    def test_bad_compound_ids_and_duplicate_ids_rejected_before_rdkit(self):
        with patch.object(compute, "load_rdkit") as load:
            for data in ["id,smiles\n../escape,CCO\n", "id,smiles\na,CCO\na,CCN\n"]:
                with self.assertRaises(ValueError):
                    self.compounds(data)
            load.assert_not_called()

    @unittest.skipUnless(HAS_RDKIT, "RDKit optional; installed in scientific CI job")
    def test_real_rdkit_statuses_coordinates_and_manifest(self):
        self.compounds("id,smiles\nethanol,CCO\nbad,not_a_smiles\nsalt,CCO.[Na+]\nunassigned,CC(O)F\n")
        result = json.loads((self.out / "compounds.json").read_text())
        records = {c["id"]: c for c in result["compounds"]}
        ethanol = records["ethanol"]
        self.assertEqual(ethanol["status"], "ok")
        self.assertAlmostEqual(ethanol["molecular_weight"], 46.069, places=2)
        self.assertEqual(ethanol["conformers_generated"], 3)
        self.assertEqual(min(c["relative_energy_kcal_mol"] for c in ethanol["conformers"]), 0)
        self.assertEqual(records["bad"]["status"], "invalid_smiles")
        self.assertEqual(records["salt"]["status"], "multiple_fragments_rejected")
        self.assertEqual(records["unassigned"]["unspecified_stereo_elements"], 1)
        structures = list(Chem.SDMolSupplier(str(self.out / ethanol["sdf_file"]), removeHs=False))
        self.assertEqual(len(structures), 3)
        self.assertTrue(all(m is not None and m.GetConformer().Is3D() for m in structures))
        metadata = json.loads((self.out / "manifest.json").read_text())
        self.assertTrue(metadata["versions"]["rdkit"])

    @unittest.skipUnless(HAS_RDKIT, "RDKit optional")
    def test_seed_repeats_energies_and_coordinates(self):
        self.compounds()
        first = (self.out / "compound-001.sdf").read_text()
        first_json = json.loads((self.out / "compounds.json").read_text())
        self.out = self.root / "repeat"
        self.compounds()
        self.assertEqual((self.out / "compound-001.sdf").read_text(), first)
        self.assertEqual(json.loads((self.out / "compounds.json").read_text()), first_json)

    @unittest.skipUnless(HAS_RDKIT, "RDKit optional")
    def test_no_convergence_never_selects_best(self):
        modules = compute.load_rdkit()
        with patch.object(modules[2], "MMFFOptimizeMoleculeConfs", return_value=[(1, 100), (1, 50), (1, 20)]):
            self.compounds()
        molecule = json.loads((self.out / "compounds.json").read_text())["compounds"][0]
        self.assertEqual(molecule["status"], "no_converged_conformers")
        self.assertNotIn("minimum_energy_kcal_mol", molecule)
        self.assertTrue(all(c["relative_energy_kcal_mol"] is None for c in molecule["conformers"]))

    @unittest.skipUnless(HAS_RDKIT, "RDKit optional")
    def test_nonconverged_lower_energy_excluded_from_best(self):
        modules = compute.load_rdkit()
        with patch.object(modules[2], "MMFFOptimizeMoleculeConfs", return_value=[(1, -999), (0, 50), (0, 20)]):
            self.compounds()
        molecule = json.loads((self.out / "compounds.json").read_text())["compounds"][0]
        self.assertEqual(molecule["status"], "partial_convergence")
        self.assertEqual(molecule["minimum_energy_kcal_mol"], 20)
        self.assertIsNone(molecule["conformers"][0]["relative_energy_kcal_mol"])

    def test_mcp_paths_limits_and_named_arguments(self):
        data = self.root / "data"
        data.mkdir()
        source = data / "input.csv"
        source.write_text("id,smiles\na,CCO\n")
        valid = {"input": str(source), "output": str(data / "result")}
        with patch.object(regen_mcp, "WORKBENCH_ROOT", self.root), patch.object(regen_mcp, "run_regen", return_value="ok") as run:
            regen_mcp.call_tool("regen_compound_screen", valid)
            argv = run.call_args.args[1]
            self.assertEqual(argv[:3], ["compound-screen", "--input", str(source.resolve())])
            self.assertIn("--out", argv)
            for patch_args in [{"seed": True}, {"conformers": 21}, {"max_iters": 0},
                               {"output": str(self.root / "outside")}, {"input": str(self.matrix)}]:
                with self.assertRaises(regen_mcp.ToolInputError):
                    regen_mcp.call_tool("regen_compound_screen", {**valid, **patch_args})
            expression = {"matrix": str(source), "samples": str(source), "reference": "a", "comparison": "b",
                          "output": str(data / "expression")}
            for value in [True, float("nan"), float("inf"), 0, "1", 10**1000]:
                with self.assertRaises(regen_mcp.ToolInputError):
                    regen_mcp.call_tool("regen_expression_contrast", {**expression, "pseudocount": value})
            regen_mcp.call_tool("regen_expression_contrast", expression)
            self.assertIn("--reference", run.call_args.args[1])

            # Test regen_pipeline via MCP
            pipeline_args = {"matrix": str(source), "samples": str(source), "reference": "young",
                             "comparison": "old", "output": str(data / "pipe_run")}
            regen_mcp.call_tool("regen_pipeline", pipeline_args)
            self.assertEqual(run.call_args.args[1][0], "pipeline")
            self.assertIn("--gene-set", run.call_args.args[1])

    def test_pipeline_end_to_end_and_provenance_chain(self):
        matrix, samples = self.pipeline_fixture()
        compute.pipeline(["--matrix", str(matrix), "--samples", str(samples),
                          "--reference", "young", "--comparison", "old", "--out", str(self.out)], self.record)

        # 1. Check directory structure
        self.assertTrue((self.out / "stage1_contrast").is_dir())
        self.assertTrue((self.out / "stage2_senescence").is_dir())
        self.assertTrue((self.out / "stage3_benchmark").is_dir())
        self.assertTrue((self.out / "pipeline_manifest.json").is_file())
        self.assertTrue((self.out / "REPORT.md").is_file())

        # 2. Stage 1 checks
        s1_contrast = json.loads((self.out / "stage1_contrast" / "contrast.json").read_text())
        self.assertIn("genes", s1_contrast)
        self.assertGreater(len(s1_contrast["genes"]), 200)
        s1_manifest = json.loads((self.out / "stage1_contrast" / "manifest.json").read_text())
        self.assertEqual(s1_manifest["action"], "expression-contrast")
        self.assertIn("matrix.input.csv", s1_manifest["inputs"])

        # 3. Stage 2 checks
        s2_scores = json.loads((self.out / "stage2_senescence" / "senescence_scores.json").read_text())
        self.assertIn("scores", s2_scores)
        self.assertEqual(len(s2_scores["scores"]), 8)
        self.assertEqual(s2_scores["parameters"]["genes_matched_in_matrix"], 80)
        self.assertEqual(s2_scores["parameters"]["gene_set_source_status"], "published_gene_set")
        self.assertEqual(s2_scores["parameters"]["minimum_coverage_fraction"], 0.6)
        self.assertNotIn("CDKN1A", s2_scores["matched_genes"])
        self.assertNotIn("CDKN2A", s2_scores["matched_genes"])
        s2_manifest = json.loads((self.out / "stage2_senescence" / "manifest.json").read_text())
        self.assertEqual(s2_manifest["action"], "senescence-scoring")
        # Stage 2 inputs must link to Stage 1 manifest and contrast.csv
        self.assertIn("stage1_manifest.json", s2_manifest["inputs"])
        self.assertIn("contrast.csv", s2_manifest["inputs"])

        # 4. Stage 3 checks
        s3_results = json.loads((self.out / "stage3_benchmark" / "benchmark_results.json").read_text())
        self.assertIn("logistic_balanced_accuracy", s3_results["parameters"])
        self.assertIn("auroc", s3_results["parameters"])
        self.assertIn("brier_score", s3_results["parameters"])
        self.assertEqual(s3_results["parameters"]["scoring_and_control_fit_scope"], "training fold only")
        self.assertEqual(s3_results["parameters"]["split_fields"], ["donor_id", "batch_id"])
        predictions = s3_results["predictions"]
        for field in ("donor_id", "batch_id"):
            assignments = {}
            for prediction in predictions:
                value = prediction[field]
                if value:
                    assignments.setdefault(value, set()).add(prediction["fold"])
            self.assertTrue(all(len(folds) == 1 for folds in assignments.values()))
        for fold in s3_results["parameters"]["fold_details"]:
            self.assertEqual(len(fold["selected_marker_genes"]), 5)
            self.assertIn("differential marker selection", fold["training_only_transformations"])
        s3_manifest = json.loads((self.out / "stage3_benchmark" / "manifest.json").read_text())
        self.assertEqual(s3_manifest["action"], "benchmark-evaluation")
        # Stage 3 inputs must link to Stage 2 manifest and senescence_scores.csv
        self.assertIn("stage2_manifest.json", s3_manifest["inputs"])
        self.assertIn("senescence_scores.csv", s3_manifest["inputs"])

        # 5. Top-level pipeline manifest and provenance audit
        pipe_manifest = json.loads((self.out / "pipeline_manifest.json").read_text())
        self.assertTrue(pipe_manifest["provenance_chain_intact"])
        self.assertEqual(len(pipe_manifest["stage_provenance"]), 3)

        # Verify hash continuity
        s1_hash = hashlib.sha256((self.out / "stage1_contrast" / "manifest.json").read_bytes()).hexdigest()
        s2_hash = hashlib.sha256((self.out / "stage2_senescence" / "manifest.json").read_bytes()).hexdigest()
        s3_hash = hashlib.sha256((self.out / "stage3_benchmark" / "manifest.json").read_bytes()).hexdigest()

        self.assertEqual(pipe_manifest["stage_provenance"][0]["manifest_sha256"], s1_hash)
        self.assertEqual(pipe_manifest["stage_provenance"][1]["manifest_sha256"], s2_hash)
        self.assertEqual(pipe_manifest["stage_provenance"][2]["manifest_sha256"], s3_hash)

        # Check Report content
        report_text = (self.out / "REPORT.md").read_text()
        self.assertIn("Stage 1: Differential Expression Contrast", report_text)
        self.assertIn("Stage 2: Senescence Module Scoring", report_text)
        self.assertIn("Stage 3: Out-of-Fold Benchmark Evaluation", report_text)
        self.assertIn(s1_hash, report_text)
        self.assertIn(s2_hash, report_text)
        self.assertIn(s3_hash, report_text)
        self.assertIn("training samples only", report_text)
        self.assertIn("GSEA", report_text)

        self.record.assert_called_once()

    def test_pipeline_gene_sets_and_parameter_validation(self):
        matrix, samples = self.pipeline_fixture(include_custom=True)
        # Test alternative gene sets
        for gset in ["fridman", "sasp"]:
            out_dir = self.root / f"out_{gset}"
            compute.pipeline(["--matrix", str(matrix), "--samples", str(samples),
                              "--reference", "young", "--comparison", "old", "--gene-set", gset,
                              "--out", str(out_dir)], self.record)
            self.assertTrue((out_dir / "pipeline_manifest.json").is_file())
            scores = json.loads((out_dir / "stage2_senescence" / "senescence_scores.json").read_text())
            self.assertEqual(scores["parameters"]["gene_set_source_status"], "custom_unverified")
            self.assertIn("Custom", scores["parameters"]["gene_set_name"])

        # Test validation failures
        bad_out = self.root / "bad_out"
        with self.assertRaises(ValueError):
            # Same group
            compute.pipeline(["--matrix", str(self.matrix), "--samples", str(self.samples),
                              "--reference", "young", "--comparison", "young", "--out", str(bad_out)], self.record)
        self.assertFalse(bad_out.exists())

    def test_low_signature_coverage_fails_closed_without_fallback(self):
        matrix, samples = self.pipeline_fixture(signature_count=74)
        with self.assertRaisesRegex(ValueError, "at least 60% is required"):
            compute.pipeline(["--matrix", str(matrix), "--samples", str(samples),
                              "--reference", "young", "--comparison", "old", "--out", str(self.out)],
                             self.record)
        self.assertFalse(self.out.exists())

    def test_fold_features_ignore_held_out_expression_for_fitting(self):
        genes = {
            "SEN_A": [3, 4, 900, 800, 10, 11],
            "SEN_B": [5, 6, 700, 600, 12, 13],
            "MARKER": [1, 2, 1000, 2000, 20, 21],
            "BG_A": [2, 2, 500, 500, 3, 3],
            "BG_B": [4, 4, 400, 400, 5, 5],
            "BG_C": [8, 8, 300, 300, 9, 9],
        }
        train_idx, test_idx, train_y = [0, 1, 4, 5], [2, 3], [0, 0, 1, 1]
        original = compute._training_fold_features(genes, train_idx, test_idx,
                                                   train_y, ["SEN_A", "SEN_B"], 1)
        changed_test = {gene: list(values) for gene, values in genes.items()}
        for values in changed_test.values():
            values[2] *= 100
            values[3] *= 100
        changed = compute._training_fold_features(changed_test, train_idx, test_idx,
                                                  train_y, ["SEN_A", "SEN_B"], 1)
        self.assertEqual(original[0], changed[0])
        self.assertEqual(original[2], changed[2])

    def test_grouped_folds_keep_transitively_shared_batches_together(self):
        names = [f"S{i}" for i in range(8)]
        labels = [0, 0, 0, 0, 1, 1, 1, 1]
        info = {name: {"group": "young" if labels[i] == 0 else "old",
                       "donor_id": f"D{i}", "batch_id": f"B{i}"}
                for i, name in enumerate(names)}
        # A donor link plus a crossing batch link forms one connected component.
        info["S0"]["donor_id"] = info["S1"]["donor_id"] = "donor0"
        info["S1"]["batch_id"] = info["S2"]["batch_id"] = "batch_cross"
        folds, fields = compute._grouped_stratified_folds(names, labels, info, 2)
        assignment = {i: fold_number for fold_number, fold in enumerate(folds) for i in fold}
        self.assertEqual(assignment[0], assignment[1])
        self.assertEqual(assignment[1], assignment[2])
        self.assertEqual(fields, ["donor_id", "batch_id"])
        self.assertTrue(all({labels[i] for i in fold} == {0, 1} for fold in folds))

    def test_senmayo_registry_is_the_source_labeled_125_gene_set(self):
        genes, metadata, raw_data = compute._gene_set_metadata("senmayo")
        self.assertEqual(len(genes), 125)
        self.assertEqual(len(set(genes)), 125)
        self.assertEqual(metadata["source_status"], "published_gene_set")
        self.assertIn("10.1038/s41467-022-32552-1", metadata["citation"])
        self.assertEqual(metadata["sha256"], hashlib.sha256(raw_data).hexdigest())
        self.assertTrue({"CDKN1A", "CDKN2A"}.isdisjoint(genes))
        self.assertNotIn("senmayo", compute.GENE_SETS)

    def test_null_label_permutations_are_near_chance_across_seeds_and_coverage(self):
        signature, _, _ = compute._gene_set_metadata("senmayo")
        sample_count = 60
        balanced_groups = ["young"] * (sample_count // 2) + ["old"] * (sample_count // 2)
        accuracies, aurocs = [], []
        for seed in range(5):
            label_rng = random.Random(10_000 + seed)
            labels = list(balanced_groups)
            label_rng.shuffle(labels)
            sample_names = [f"S{i}" for i in range(sample_count)]
            sample_rows = ["sample,group,donor_id,batch_id"] + [
                f"{sample},{label},D{i},B{i}" for i, (sample, label) in enumerate(zip(sample_names, labels))
            ]
            sample_path = self.root / f"null_samples_{seed}.csv"
            sample_path.write_text("\n".join(sample_rows) + "\n", encoding="utf-8")
            for coverage_index, signature_count in enumerate((125, 75)):
                rng = random.Random(20_000 + seed * 10 + coverage_index)
                genes = signature[:signature_count] + [f"BG{i}" for i in range(1000 - signature_count)]
                matrix_path = self.root / f"null_matrix_{seed}_{coverage_index}.csv"
                matrix_rows = ["gene," + ",".join(sample_names)]
                matrix_rows.extend(gene + "," + ",".join(
                    f"{rng.uniform(0.0, 100.0):.6f}" for _ in sample_names
                ) for gene in genes)
                matrix_path.write_text("\n".join(matrix_rows) + "\n", encoding="utf-8")
                out = self.root / f"null_report_{seed}_{coverage_index}"
                compute.pipeline(["--matrix", str(matrix_path), "--samples", str(sample_path),
                                  "--reference", "young", "--comparison", "old", "--out", str(out)],
                                 self.record)
                parameters = json.loads((out / "stage3_benchmark" / "benchmark_results.json").read_text())["parameters"]
                accuracies.append(parameters["logistic_balanced_accuracy"])
                aurocs.append(parameters["auroc"])

        self.assertGreaterEqual(statistics.mean(accuracies), 0.40)
        self.assertLessEqual(statistics.mean(accuracies), 0.60)
        self.assertGreaterEqual(statistics.mean(aurocs), 0.40)
        self.assertLessEqual(statistics.mean(aurocs), 0.60)
        self.assertLess(max(accuracies), 0.80)
        self.assertLess(max(aurocs), 0.80)


if __name__ == "__main__":
    unittest.main()
