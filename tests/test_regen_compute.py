from __future__ import annotations

import hashlib
import json
import math
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


if __name__ == "__main__":
    unittest.main()
