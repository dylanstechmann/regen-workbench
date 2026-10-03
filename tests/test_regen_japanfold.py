from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import regen_japanfold as japanfold  # noqa: E402


JOB_ID = "13b37012d933375e5ccdd3ee025a2a3b"
SEQUENCE = "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"


def archive_bytes(*, filename: str = "target_1.cif") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("results.json", '[{"id":"target_1","status":"ok"}]')
        archive.writestr(filename, "data_target_1\n#\n")
    return buffer.getvalue()


class FakeClient:
    def __init__(self, archive: bytes | None = None) -> None:
        self.requests = []
        self.archive = archive if archive is not None else archive_bytes()
        self.status = "succeeded"

    def json(self, method, path, payload=None, idempotency_key=None):
        self.requests.append((method, path, payload, idempotency_key))
        if path == "/v1/models":
            return {"models": [{"id": "openfold3", "max_residues": 1664, "measured_wall": 1664}]}
        if path == "/v1/predictions":
            return {"id": JOB_ID, "model": "openfold3", "status": "queued", "links": {"archive_url": "https://secret.example"}}
        if path == f"/v1/jobs/{JOB_ID}":
            return {"id": JOB_ID, "model": "openfold3", "status": self.status,
                    "results_ready": self.status == "succeeded"}
        if path == f"/v1/jobs/{JOB_ID}/results":
            return {"job_id": JOB_ID, "ready": True,
                    "rows": [{"id": "target_1", "plddt": 0.7}],
                    "artifacts": [{"path": "target_1.cif", "type": "structure", "url": "https://signed.example/token"}],
                    "archive_url": "https://signed.example/archive"}
        raise AssertionError(path)

    def download_archive(self, job_id, dest):
        assert job_id == JOB_ID
        dest.write_bytes(self.archive)


class JapanFoldTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.run = self.root / "run"
        self.fasta = self.root / "one.fasta"
        self.fasta.write_text(f">public-1ubq\n{SEQUENCE}\n", encoding="utf-8")
        self.receipts = []
        receipt_patch = patch.object(japanfold.regen, "record", side_effect=self._record)
        receipt_patch.start()
        self.addCleanup(receipt_patch.stop)

    def _record(self, action, payload, files):
        self.receipts.append((action, payload, files))

    def test_submit_uses_live_limit_and_sanitizes_job(self) -> None:
        client = FakeClient()
        job = japanfold.submit_prediction(self.fasta, self.run, client=client)
        self.assertEqual(job["id"], JOB_ID)
        self.assertNotIn("links", job)
        method, path, payload, key = client.requests[-1]
        self.assertEqual((method, path), ("POST", "/v1/predictions"))
        self.assertEqual(payload["sequence"], SEQUENCE)
        self.assertEqual(payload["model"], "openfold3")
        self.assertTrue(payload["params"]["use_msa_server"])
        self.assertEqual(len(key), 32)
        plan = json.loads((self.run / "plan.json").read_text())
        self.assertEqual(plan["live_model_max_residues"], 1664)
        self.assertTrue(plan["external_msa_enabled"])
        self.assertEqual((self.run / "input.fasta").read_bytes(), self.fasta.read_bytes())
        self.assertEqual((self.run / "request.json").read_bytes(), japanfold._request_bytes(payload))
        self.assertEqual(plan["input_file_sha256"], japanfold._sha256(self.run / "input.fasta"))
        self.assertEqual(plan["request_sha256"], japanfold._sha256(self.run / "request.json"))
        self.assertNotIn(SEQUENCE, (self.run / "plan.json").read_text())
        self.assertNotIn("secret.example", (self.run / "job.json").read_text())
        self.assertNotIn(SEQUENCE, json.dumps(self.receipts, default=str))

    def test_complex_yaml_uses_input_and_rejects_ligands(self) -> None:
        complex_file = self.root / "complex.yaml"
        complex_file.write_text("sequences:\n  - protein: {id: A, sequence: ACDE}\n  - dna: {id: B, sequence: ACGT}\n")
        client = FakeClient()
        japanfold.submit_prediction(None, self.run, input_path=complex_file, use_msa_server=False, client=client)
        payload = client.requests[-1][2]
        self.assertIn("input", payload)
        self.assertNotIn("sequence", payload)
        self.assertFalse(payload["params"]["use_msa_server"])
        self.assertEqual(json.loads((self.run / "plan.json").read_text())["input_residues"], 8)
        self.assertEqual((self.run / "input.txt").read_bytes(), complex_file.read_bytes())
        self.assertEqual((self.run / "request.json").read_bytes(), japanfold._request_bytes(payload))

        ligand = self.root / "ligand.yaml"
        ligand.write_text("sequences:\n  - protein: {id: A, sequence: ACDE}\n  - ligand: {id: L, smiles: CCO}\n")
        with self.assertRaisesRegex(japanfold.JapanFoldError, "no ligands"):
            japanfold.submit_prediction(None, self.root / "ligand-run", input_path=ligand, client=FakeClient())

    def test_retry_reuses_idempotency_key_without_duplicate_submission(self) -> None:
        client = FakeClient()
        original_json = client.json
        attempts = 0

        def interrupt(method, path, payload=None, idempotency_key=None):
            nonlocal attempts
            if path == "/v1/predictions":
                attempts += 1
                if attempts == 1:
                    client.requests.append((method, path, payload, idempotency_key))
                    raise japanfold.JapanFoldError("temporary failure")
            return original_json(method, path, payload, idempotency_key)

        client.json = interrupt
        with self.assertRaises(japanfold.JapanFoldError):
            japanfold.submit_prediction(self.fasta, self.run, client=client)
        self.assertTrue((self.run / "plan.json").exists())
        japanfold.submit_prediction(self.fasta, self.run, client=client)
        submissions = [item for item in client.requests if item[1] == "/v1/predictions"]
        self.assertEqual(len(submissions), 2)
        self.assertEqual(submissions[0][3], submissions[1][3])
        japanfold.submit_prediction(self.fasta, self.run, client=client)
        self.assertEqual(len([item for item in client.requests if item[1] == "/v1/predictions"]), 2)

    def test_collect_hashes_outputs_without_signed_urls(self) -> None:
        client = FakeClient()
        japanfold.submit_prediction(self.fasta, self.run, client=client)
        manifest = japanfold.collect_prediction(self.run, client=client)
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["files"][1]["path"], "outputs/target_1.cif")
        self.assertEqual(japanfold._sha256(self.run / "outputs" / "target_1.cif"), manifest["files"][1]["sha256"])
        self.assertNotIn("signed.example", (self.run / "manifest.json").read_text())
        self.assertNotIn(SEQUENCE, json.dumps(self.receipts, default=str))
        self.assertEqual(japanfold.collect_prediction(self.run, client=client), manifest)

    def test_completed_collect_validates_local_hashes_without_network(self) -> None:
        client = FakeClient()
        japanfold.submit_prediction(self.fasta, self.run, client=client)
        manifest = japanfold.collect_prediction(self.run, client=client)
        client.requests.clear()
        self.assertEqual(japanfold.collect_prediction(self.run, client=client), manifest)
        self.assertEqual(client.requests, [])
        for filename in ("outputs/target_1.cif", "outputs.zip", "request.json", "input.fasta"):
            with self.subTest(filename=filename):
                path = self.run / filename
                original = path.read_bytes()
                path.write_bytes(original + b"corrupt")
                try:
                    with self.assertRaisesRegex(japanfold.JapanFoldError, "(hash|size) mismatch"):
                        japanfold.collect_prediction(self.run, client=client)
                    self.assertEqual(client.requests, [])
                finally:
                    path.write_bytes(original)

    def test_collect_finishes_valid_partial_legacy_run(self) -> None:
        client = FakeClient()
        japanfold.submit_prediction(self.fasta, self.run, client=client)
        plan_path = self.run / "plan.json"
        plan = json.loads(plan_path.read_text())
        for key in ("live_model_caps", "live_model_msa_default", "input_file", "input_file_sha256",
                    "request_file", "request_sha256"):
            plan.pop(key, None)
        plan_path.write_text(json.dumps(plan))
        (self.run / "input.fasta").unlink()
        (self.run / "request.json").unlink()
        (self.run / "outputs.zip").write_bytes(client.archive)
        outputs = self.run / "outputs"
        outputs.mkdir()
        with zipfile.ZipFile(self.run / "outputs.zip") as archive:
            for name in archive.namelist():
                (outputs / name).write_bytes(archive.read(name))
        manifest = japanfold.collect_prediction(self.run, client=client)
        self.assertIsNone(manifest["request_sha256"])
        self.assertEqual(manifest["files"][1]["sha256"], japanfold._sha256(outputs / "target_1.cif"))
        self.assertTrue((self.run / "manifest.json").is_file())

    def test_collect_rejects_corrupt_partial_output(self) -> None:
        client = FakeClient()
        japanfold.submit_prediction(self.fasta, self.run, client=client)
        (self.run / "outputs.zip").write_bytes(client.archive)
        outputs = self.run / "outputs"
        outputs.mkdir()
        (outputs / "results.json").write_bytes(b"bad")
        (outputs / "target_1.cif").write_bytes(b"data_target_1\n#\n")
        with self.assertRaisesRegex(japanfold.JapanFoldError, "does not match JapanFold archive"):
            japanfold.collect_prediction(self.run, client=client)
        self.assertFalse((self.run / "manifest.json").exists())

    def test_collect_rejects_traversal_without_writing_outputs(self) -> None:
        client = FakeClient(archive_bytes(filename="../escape.cif"))
        japanfold.submit_prediction(self.fasta, self.run, client=client)
        with self.assertRaisesRegex(japanfold.JapanFoldError, "Unsafe archive path"):
            japanfold.collect_prediction(self.run, client=client)
        self.assertFalse((self.root / "escape.cif").exists())
        self.assertFalse((self.run / "outputs").exists())

    def test_cli_rejects_output_outside_ignored_structures(self) -> None:
        with patch.object(japanfold.regen, "DATA", self.root / "data"):
            self.assertEqual(japanfold.main(["submit", "--fasta", str(self.fasta),
                                             "--out", str(self.root / "tracked-run")]), 1)
        self.assertFalse((self.root / "tracked-run").exists())


if __name__ == "__main__":
    unittest.main()
