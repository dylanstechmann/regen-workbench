from __future__ import annotations

import csv
import importlib.util
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import docking_benchmark  # noqa: E402


class DockingBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.data = self.root / "data"
        self.data.mkdir()

    def write_table(self, rows, name="controls.csv"):
        path = self.data / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["compound_id", "role", "score", "method", "assay_id", "label_source"])
            for row in rows:
                row.setdefault("method", "AutoDock Vina affinity")
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_lower_and_higher_score_directions_and_ties(self):
        rows = [
            {"compound_id": "a1", "role": "active_control", "score": -9.0},
            {"compound_id": "a2", "role": "active_control", "score": -6.0},
            {"compound_id": "i1", "role": "inactive_control", "score": -6.0},
            {"compound_id": "i2", "role": "inactive_control", "score": -4.0},
            {"compound_id": "d1", "role": "decoy", "score": -10.0},
            {"compound_id": "c1", "role": "candidate", "score": -11.0},
        ]
        lower = docking_benchmark._ranking_metrics(rows, "lower")
        higher = docking_benchmark._ranking_metrics(rows, "higher")
        self.assertEqual(lower["roc_auc"], 0.875)
        self.assertEqual(higher["roc_auc"], 0.125)
        self.assertEqual(lower["decoys_excluded_from_primary_metrics"], 1)
        self.assertEqual(lower["candidates_excluded_from_control_metrics"], 1)
        self.assertTrue(lower["small_control_set_warning"])
        tied = docking_benchmark._ranking_metrics([
            {"compound_id": "a", "role": "active_control", "score": -5},
            {"compound_id": "i1", "role": "inactive_control", "score": -5},
            {"compound_id": "i2", "role": "inactive_control", "score": -5},
        ], "lower")
        self.assertAlmostEqual(tied["enrichment"]["1%"]["active_hits"], 1 / 3)

    def test_report_snapshots_input_and_hashes_outputs(self):
        source = self.write_table([
            {"compound_id": "a1", "role": "active_control", "score": -9.0, "assay_id": "assay-1", "label_source": "https://example.org/data"},
            {"compound_id": "a2", "role": "active_control", "score": -7.0, "assay_id": "assay-1", "label_source": "https://example.org/data"},
            {"compound_id": "i1", "role": "inactive_control", "score": -4.0, "assay_id": "assay-1", "label_source": "https://example.org/data"},
            {"compound_id": "i2", "role": "inactive_control", "score": -3.0, "assay_id": "assay-1", "label_source": "https://example.org/data"},
            {"compound_id": "d1", "role": "decoy", "score": -10.0, "assay_id": "", "label_source": ""},
            {"compound_id": "c1", "role": "candidate", "score": -11.0, "assay_id": "", "label_source": ""},
        ])
        destination = self.data / "benchmark-01"
        receipt = Mock()
        result = docking_benchmark.create_report(
            str(source), str(destination), "lower", workbench_root=self.root,
            data_root=self.data, record=receipt,
        )
        metrics = json.loads((destination / "metrics.json").read_text(encoding="utf-8"))
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        with (destination / "ranked-results.csv").open(encoding="utf-8", newline="") as handle:
            ranked = list(csv.DictReader(handle))
        self.assertEqual(metrics["ranking"]["roc_auc"], 1.0)
        self.assertEqual(metrics["method"], "AutoDock Vina affinity")
        self.assertEqual(metrics["ranking"]["decoys_excluded_from_primary_metrics"], 1)
        self.assertTrue((destination / "source-manifest.csv").is_file())
        self.assertTrue((destination / "input.csv").is_file())
        self.assertEqual(ranked[0]["compound_id"], "c1")
        self.assertEqual(Path(result["output"]), destination.resolve())
        self.assertEqual(receipt.call_args.args[0], "docking-benchmark")
        for name, record in manifest["outputs"].items():
            artifact = destination / name
            self.assertEqual(artifact.stat().st_size, record["bytes"])
            self.assertEqual(docking_benchmark.sha256_file(artifact), record["sha256"])
        with self.assertRaisesRegex(ValueError, "never overwritten"):
            docking_benchmark.create_report(str(source), str(destination), "lower", workbench_root=self.root,
                                            data_root=self.data, record=receipt)

    def test_rejects_bad_scores_missing_controls_and_escaping_input(self):
        source = self.write_table([
            {"compound_id": "a", "role": "active_control", "score": "nan", "assay_id": "", "label_source": ""},
            {"compound_id": "i", "role": "inactive_control", "score": 1, "assay_id": "", "label_source": ""},
        ])
        with self.assertRaisesRegex(ValueError, "finite"):
            docking_benchmark.create_report(str(source), str(self.data / "out"), "lower", workbench_root=self.root,
                                            data_root=self.data, record=Mock())
        source = self.write_table([
            {"compound_id": "a", "role": "active_control", "score": 1, "assay_id": "assay-1", "label_source": "https://example.org/assay"},
            {"compound_id": "c", "role": "candidate", "score": 2, "assay_id": "", "label_source": ""},
        ], "no-inactive.csv")
        with self.assertRaisesRegex(ValueError, "inactive_control"):
            docking_benchmark.create_report(str(source), str(self.data / "out-2"), "lower", workbench_root=self.root,
                                            data_root=self.data, record=Mock())
        outside = self.root / "outside.csv"
        outside.write_text("compound_id,role,score,method\na,active_control,-1,vina\ni,inactive_control,1,vina\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "data/ or projects/"):
            docking_benchmark.create_report(str(outside), str(self.data / "out-3"), "lower", workbench_root=self.root,
                                            data_root=self.data, record=Mock())

    def test_rejects_mixed_methods_and_controls_without_a_label_source(self):
        source = self.write_table([
            {"compound_id": "a", "role": "active_control", "score": -8, "method": "vina", "label_source": "https://example.org/assay"},
            {"compound_id": "i", "role": "inactive_control", "score": -2, "method": "gnina", "label_source": "https://example.org/assay"},
        ], "mixed-methods.csv")
        with self.assertRaisesRegex(ValueError, "exactly one method"):
            docking_benchmark.create_report(str(source), str(self.data / "out-4"), "lower", workbench_root=self.root,
                                            data_root=self.data, record=Mock())
        source = self.write_table([
            {"compound_id": "a", "role": "active_control", "score": -8, "method": "vina", "label_source": ""},
            {"compound_id": "i", "role": "inactive_control", "score": -2, "method": "vina", "label_source": ""},
        ], "unreferenced-controls.csv")
        with self.assertRaisesRegex(ValueError, "needs a label_source"):
            docking_benchmark.create_report(str(source), str(self.data / "out-5"), "lower", workbench_root=self.root,
                                            data_root=self.data, record=Mock())

    def test_pose_rmsd_is_symmetry_aware_and_does_not_align(self):
        if not importlib.util.find_spec("rdkit"):
            self.skipTest("RDKit is optional outside the research image")
        from rdkit import Chem
        from rdkit.Chem import AllChem

        structures = self.data / "structures"
        structures.mkdir()
        molecule = Chem.AddHs(Chem.MolFromSmiles("c1ccccc1"))
        self.assertGreaterEqual(AllChem.EmbedMolecule(molecule, randomSeed=19), 0)
        AllChem.MMFFOptimizeMolecule(molecule)
        reference = Chem.RemoveHs(molecule)
        pose = Chem.Mol(reference)
        conformer = pose.GetConformer()
        for index in range(pose.GetNumAtoms()):
            point = conformer.GetAtomPosition(index)
            conformer.SetAtomPosition(index, (point.x + 2.0, point.y, point.z))
        for name, item in (("reference.sdf", reference), ("pose.sdf", pose)):
            writer = Chem.SDWriter(str(structures / name))
            writer.write(item)
            writer.close()
        source = self.data / "posed-controls.csv"
        with source.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["compound_id", "role", "score", "method", "label_source", "pose_sdf", "reference_sdf"])
            writer.writeheader()
            writer.writerow({"compound_id": "a", "role": "active_control", "score": -8, "method": "vina", "label_source": "https://example.org/assay", "pose_sdf": "data/structures/pose.sdf", "reference_sdf": "data/structures/reference.sdf"})
            writer.writerow({"compound_id": "i", "role": "inactive_control", "score": -2, "method": "vina", "label_source": "https://example.org/assay"})
        destination = self.data / "posed-report"
        docking_benchmark.create_report(str(source), str(destination), "lower", workbench_root=self.root,
                                       data_root=self.data, record=Mock())
        metrics = json.loads((destination / "metrics.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(metrics["pose_validation"]["n_compared"], 1)
        self.assertTrue(math.isclose(metrics["pose_validation"].get("mean_rmsd_angstrom", 2.0), 2.0, abs_tol=1e-6))
        with (destination / "ranked-results.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["pose_rmsd_status"], "computed")
        self.assertTrue(rows[0]["pose_sdf"].startswith("inputs/"))


if __name__ == "__main__":
    unittest.main()
