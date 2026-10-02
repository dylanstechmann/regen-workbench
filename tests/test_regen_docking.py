from __future__ import annotations

import contextlib
import io
import json
import hashlib
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import regen  # noqa: E402


class VinaRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.data = self.root / "data"
        self.cache = self.root / "cache"
        self.provenance = self.data / "provenance"
        self.previous = (regen.ROOT, regen.DATA, regen.CACHE, regen.PROV)
        regen.ROOT, regen.DATA, regen.CACHE, regen.PROV = (
            self.root, self.data, self.cache, self.provenance
        )
        inputs = self.data / "structures"
        inputs.mkdir(parents=True)
        self.receptor = inputs / "receptor.pdbqt"
        self.ligand = inputs / "ligand.pdbqt"
        self.output = inputs / "docked.pdbqt"
        self.receptor.write_text("ATOM      1  C   GLY A   1      0.000   0.000   0.000  0.00  0.00    +0.000 C\n")
        self.ligand.write_text("HETATM    1  C1  UNL     1      0.000   0.000   0.000  0.00  0.00    +0.000 C\n")

    def tearDown(self) -> None:
        regen.ROOT, regen.DATA, regen.CACHE, regen.PROV = self.previous
        self.tempdir.cleanup()

    def test_run_writes_pose_and_hash_linked_provenance(self) -> None:
        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if command[-1] == "--version":
                return subprocess.CompletedProcess(command, 0, "AutoDock Vina 1.2.5\n", "")
            pose = Path(command[command.index("--out") + 1])
            pose.write_text("MODEL 1\nATOM      1  C   UNL     1      0.000   0.000   0.000  0.00  0.00    +0.000 C\nENDMDL\n")
            return subprocess.CompletedProcess(command, 0, f"1 -8.2 0.0 0.0 {pose}\n", "")

        output = io.StringIO()
        with patch.object(regen.shutil, "which", return_value="/usr/bin/vina"), patch.object(
            regen.subprocess, "run", side_effect=fake_run
        ), contextlib.redirect_stdout(output):
            result = regen.run_vina_docking(
                str(self.receptor), str(self.ligand), str(self.output),
                center=(1.0, 2.0, 3.0), size=(20.0, 20.0, 20.0), seed=17,
            )

        self.assertEqual(result["version"], "AutoDock Vina 1.2.5")
        self.assertEqual(result["seed"], 17)
        self.assertTrue(self.output.is_file())
        receipts = list(self.provenance.glob("*_dock-vina.json"))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text())
        self.assertEqual(receipt["payload"]["ligand_sha256"], regen.sha256_file(self.ligand))
        self.assertEqual(receipt["outputs"][0]["sha256"], regen.sha256_file(self.output))
        self.assertEqual(receipt["payload"]["status"], "succeeded")
        self.assertIn(str(self.output.resolve()), receipt["payload"]["transcript"])
        self.assertNotIn(".regen-vina-", receipt["payload"]["transcript"])
        self.assertIn("not measured binding affinity", receipt["payload"]["interpretation"])

    def test_failed_vina_exit_keeps_hashes_and_diagnostics(self) -> None:
        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if command[-1] == "--version":
                return subprocess.CompletedProcess(command, 0, "AutoDock Vina 1.2.5\n", "")
            return subprocess.CompletedProcess(command, 2, "", "invalid atom type\n")

        with patch.object(regen.shutil, "which", return_value="/usr/bin/vina"), patch.object(
            regen.subprocess, "run", side_effect=fake_run
        ), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                regen.run_vina_docking(
                    str(self.receptor), str(self.ligand), str(self.output),
                    center=(1.0, 2.0, 3.0), size=(20.0, 20.0, 20.0), seed=17,
                )

        self.assertFalse(self.output.exists())
        receipts = list(self.provenance.glob("*_dock-vina.json"))
        self.assertEqual(len(receipts), 1)
        payload = json.loads(receipts[0].read_text())["payload"]
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["receptor_sha256"], regen.sha256_file(self.receptor))
        self.assertEqual(payload["ligand_sha256"], regen.sha256_file(self.ligand))
        self.assertIn("invalid atom type", payload["transcript"])
        self.assertIn("exited with status 2", payload["error"])

    def test_vina_timeout_keeps_partial_output(self) -> None:
        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if command[-1] == "--version":
                return subprocess.CompletedProcess(command, 0, "AutoDock Vina 1.2.5\n", "")
            raise subprocess.TimeoutExpired(command, 900, output=b"search started", stderr=b"interrupted")

        with patch.object(regen.shutil, "which", return_value="/usr/bin/vina"), patch.object(
            regen.subprocess, "run", side_effect=fake_run
        ), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                regen.run_vina_docking(
                    str(self.receptor), str(self.ligand), str(self.output),
                    center=(1.0, 2.0, 3.0), size=(20.0, 20.0, 20.0), seed=17,
                )

        receipts = list(self.provenance.glob("*_dock-vina.json"))
        self.assertEqual(len(receipts), 1)
        payload = json.loads(receipts[0].read_text())["payload"]
        self.assertEqual(payload["status"], "failed")
        self.assertIn("search started", payload["transcript"])
        self.assertIn("interrupted", payload["transcript"])
        self.assertTrue(payload["receptor_sha256"])

    def test_runner_refuses_paths_outside_research_roots(self) -> None:
        outside = self.root / "outside.pdbqt"
        outside.write_text("ATOM test\n")
        with self.assertRaises(SystemExit):
            regen._docking_input_path(str(outside), "receptor")

    def test_gnina_download_is_hash_verified_before_install(self) -> None:
        payload = b"pinned test binary"

        class Response(io.BytesIO):
            headers = {"Content-Length": str(len(payload))}

        with patch.object(regen, "GNINA_ASSET_SIZE", len(payload)), patch.object(
            regen, "GNINA_ASSET_SHA256", hashlib.sha256(payload).hexdigest()
        ), patch.object(regen, "GNINA_ASSET_URL", "https://example.invalid/gnina"), patch.object(
            regen, "urlopen", return_value=Response(payload)
        ), contextlib.redirect_stdout(io.StringIO()):
            result = regen.install_gnina()

        installed = self.cache / "gnina" / "gnina"
        self.assertEqual(result["status"], "installed")
        self.assertEqual(installed.read_bytes(), payload)
        if os.name != "nt":
            self.assertTrue(installed.stat().st_mode & stat.S_IXUSR)
        self.assertEqual(regen.sha256_file(installed), hashlib.sha256(payload).hexdigest())
        self.assertEqual(len(list(self.provenance.glob("*_install-gnina.json"))), 1)

    def test_gnina_rescores_to_sdf_without_gpu_and_records_provenance(self) -> None:
        executable = self.cache / "gnina" / "gnina"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"mock executable")

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if command[-1] == "--version":
                return subprocess.CompletedProcess(command, 0, "gnina 1.3.3\n", "")
            pose = Path(command[command.index("--out") + 1])
            pose.write_text("$$$$\n>  <CNNscore>\n0.84\n\n$$$$\n")
            return subprocess.CompletedProcess(command, 0, "CNNscore 0.84\nCNNaffinity 7.1\n", "")

        output = io.StringIO()
        with patch.object(regen, "GNINA_ASSET_SHA256", hashlib.sha256(b"mock executable").hexdigest()), \
             patch.object(regen.subprocess, "run", side_effect=fake_run) as run, contextlib.redirect_stdout(output):
            result = regen.run_gnina_docking(
                str(self.receptor), str(self.ligand), str(self.data / "structures" / "gnina.sdf"),
                center=(1.0, 2.0, 3.0), size=(20.0, 20.0, 20.0), seed=17,
            )

        command = run.call_args_list[-1].args[0]
        self.assertEqual(result["version"], "gnina 1.3.3")
        self.assertTrue(result["output"].endswith("gnina.sdf"))
        self.assertEqual(result["cnn_scoring"], "rescore")
        self.assertFalse(result["gpu"])
        self.assertEqual(command[command.index("--cnn_scoring") + 1], "rescore")
        self.assertIn("--no_gpu", command)
        self.assertIn("CNNscore 0.84", result["transcript"])
        self.assertTrue(Path(result["output"]).is_file())
        receipt = json.loads(next(self.provenance.glob("*_dock-gnina.json")).read_text())
        self.assertEqual(receipt["payload"]["status"], "succeeded")
        self.assertEqual(receipt["payload"]["executable_sha256"], hashlib.sha256(b"mock executable").hexdigest())
        self.assertEqual(receipt["outputs"][0]["sha256"], regen.sha256_file(Path(result["output"])))

    def test_gnina_runner_rejects_binary_with_wrong_hash(self) -> None:
        executable = self.cache / "gnina" / "gnina"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"untrusted executable")
        with patch.object(regen, "GNINA_ASSET_SHA256", hashlib.sha256(b"pinned executable").hexdigest()), \
             patch.object(regen.subprocess, "run") as run, contextlib.redirect_stderr(io.StringIO()), \
             self.assertRaises(SystemExit):
            regen.run_gnina_docking(
                str(self.receptor), str(self.ligand), str(self.data / "structures" / "gnina.sdf"),
                center=(1.0, 2.0, 3.0), size=(20.0, 20.0, 20.0), seed=17,
            )
        run.assert_not_called()

    def test_gnina_restricts_expensive_cnn_modes(self) -> None:
        with self.assertRaises(SystemExit):
            regen.run_gnina_docking(
                str(self.receptor), str(self.ligand), str(self.data / "structures" / "gnina.sdf"),
                center=(1.0, 2.0, 3.0), size=(20.0, 20.0, 20.0), cnn_scoring="all",
            )


if __name__ == "__main__":
    unittest.main()
