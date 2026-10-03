from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import structure_compare as tool

try:
    import Bio  # noqa: F401
except ImportError:
    HAS_BIOPYTHON = False
else:
    HAS_BIOPYTHON = True


def pdb_chain(chain: str, names: list[str], *, shift: float = 0, missing_ca: int = -1) -> str:
    points = [(0, 0, 0), (1, 2, 0), (2, 1, 3), (4, 0, 2)]
    lines = []
    for index, (name, (x, y, z)) in enumerate(zip(names, points), start=1):
        if index == missing_ca:
            continue
        lines.append(f"ATOM  {index:5d}  CA  {name:3s} {chain}{index:4d}    "
                     f"{x + shift:8.3f}{y:8.3f}{z:8.3f}{1.0:6.2f}{20.0:6.2f}           C\n")
    return "".join(lines) + "TER\n"


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run = self.root / "run"
        (self.run / "outputs").mkdir(parents=True)
        self.candidate = self.run / "outputs" / "candidate.pdb"
        self.candidate.write_text(pdb_chain("A", ["ALA", "GLY", "SER", "THR"]))
        self.manifest = self.run / "manifest.json"
        self.record = {"path": "outputs/candidate.pdb", "bytes": self.candidate.stat().st_size,
                       "sha256": tool.sha256_file(self.candidate)}
        self.output_field = "output_files"
        self.write_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self):
        self.manifest.write_text(json.dumps({self.output_field: [self.record]}))

    def test_manifest_checks_selected_artifact_hash_and_bytes(self):
        for field in ("output_files", "files", "outputs"):
            with self.subTest(field=field):
                self.output_field = field
                self.write_manifest()
                result = tool.verify_manifest(self.manifest, self.candidate)
                self.assertEqual(result["outputs_verified"], 1)
                self.assertEqual(result["output_field"], field)
        self.candidate.write_text(self.candidate.read_text() + "REMARK tampered\n")
        with self.assertRaisesRegex(ValueError, "byte count differs"):
            tool.verify_manifest(self.manifest, self.candidate)
        self.record["bytes"] = self.candidate.stat().st_size
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
            tool.verify_manifest(self.manifest, self.candidate)

    def test_manifest_rejects_escape_and_unlisted_candidate(self):
        outside = self.root / "outside.pdb"
        outside.write_text("outside")
        with self.assertRaisesRegex(ValueError, "inside the manifest"):
            tool.verify_manifest(self.manifest, outside)
        self.record["path"] = "../outside.pdb"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "relative to the run"):
            tool.verify_manifest(self.manifest, self.candidate)
        self.record["path"] = "outputs/other.pdb"
        (self.run / "outputs" / "other.pdb").write_bytes(self.candidate.read_bytes())
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "not listed"):
            tool.verify_manifest(self.manifest, self.candidate)

    @unittest.skipUnless(HAS_BIOPYTHON, "Biopython is installed in the workbench image")
    def test_rigid_translation_and_hash_linked_report(self):
        reference = self.root / "reference.pdb"
        reference.write_text(pdb_chain("A", ["ALA", "GLY", "SER", "THR"]))
        self.candidate.write_text(pdb_chain("A", ["ALA", "GLY", "SER", "THR"], shift=10))
        self.record["sha256"] = tool.sha256_file(self.candidate)
        self.record["bytes"] = self.candidate.stat().st_size
        self.write_manifest()
        report = tool.compare(reference, self.candidate, manifest_path=self.manifest)
        self.assertEqual(report["alignment"]["matched_ca_atoms"], 4)
        self.assertEqual(report["alignment"]["sequence_identity"], 1)
        self.assertAlmostEqual(report["alignment"]["ca_rmsd_angstrom"], 0, places=3)
        self.assertEqual(report["candidate"]["sha256"], hashlib.sha256(self.candidate.read_bytes()).hexdigest())
        self.assertEqual(report["manifest"]["outputs_verified"], 1)

    @unittest.skipUnless(HAS_BIOPYTHON, "Biopython is installed in the workbench image")
    def test_rejects_mismatch_low_ca_coverage_and_ambiguous_chains(self):
        reference = self.root / "reference.pdb"
        reference.write_text(pdb_chain("A", ["ALA", "GLY", "SER", "THR"]))
        self.candidate.write_text(pdb_chain("A", ["ALA", "GLY", "SER", "VAL"]))
        with self.assertRaisesRegex(ValueError, "identity=0.7500"):
            tool.compare(reference, self.candidate)
        self.candidate.write_text(pdb_chain("A", ["ALA", "GLY", "SER", "THR"], missing_ca=4))
        with self.assertRaisesRegex(ValueError, "coverage"):
            tool.compare(reference, self.candidate)
        self.candidate.write_text(pdb_chain("A", ["ALA", "GLY", "SER", "THR"]) +
                                  pdb_chain("B", ["ALA", "GLY", "SER", "THR"]))
        with self.assertRaisesRegex(ValueError, "choose a chain explicitly"):
            tool.compare(reference, self.candidate)
        report = tool.compare(reference, self.candidate, candidate_chain="B")
        self.assertEqual(report["candidate"]["chain"], "B")

    @unittest.skipUnless(HAS_BIOPYTHON, "Biopython is installed in the workbench image")
    def test_partner_pose_and_ca_contact_recovery_use_receptor_frame(self):
        names = ["ALA", "GLY", "SER", "THR"]
        reference = self.root / "complex_reference.pdb"
        candidate = self.root / "complex_candidate.pdb"
        reference.write_text(pdb_chain("A", names) + pdb_chain("B", names))
        candidate.write_text(pdb_chain("A", names) + pdb_chain("B", names, shift=30))
        report = tool.compare(reference, candidate, reference_chain="A", candidate_chain="A",
                              reference_partner_chain="B", candidate_partner_chain="B")
        self.assertAlmostEqual(report["alignment"]["ca_rmsd_angstrom"], 0, places=3)
        self.assertAlmostEqual(report["partner"]["intrinsic_ca_rmsd_angstrom"], 0, places=3)
        self.assertAlmostEqual(report["partner"]["pose_ca_rmsd_angstrom"], 30, places=3)
        self.assertEqual(report["partner"]["ca_contacts"]["reference_count"], 16)
        self.assertEqual(report["partner"]["ca_contacts"]["recovered_count"], 0)
        self.assertEqual(report["partner"]["ca_contacts"]["recall"], 0)
        candidate.write_text(reference.read_text())
        perfect = tool.compare(reference, candidate, reference_chain="A", candidate_chain="A",
                               reference_partner_chain="B", candidate_partner_chain="B")
        self.assertAlmostEqual(perfect["partner"]["pose_ca_rmsd_angstrom"], 0, places=3)
        self.assertEqual(perfect["partner"]["ca_contacts"]["recall"], 1)


if __name__ == "__main__":
    unittest.main()
