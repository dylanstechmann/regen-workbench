from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import regen_nvidia as nvidia  # noqa: E402


SEQUENCE = "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"
CIF = "data_model\n#\nloop_\n_atom_site.group_PDB\nATOM\n"


class NvidiaFoldTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(nvidia.os.environ, {"REGEN_DATA": str(self.root / "data")})
        env.start()
        self.addCleanup(env.stop)
        self.request = nvidia.single_protein_request(SEQUENCE, request_id="1UBQ-public")

    def test_query_only_msa_is_explicit(self) -> None:
        molecule = self.request["inputs"][0]["molecules"][0]
        self.assertEqual(molecule["msa"]["query_only"]["a3m"]["alignment"], f">query\n{SEQUENCE}\n")
        self.assertEqual(self.request["inputs"][0]["diffusion_samples"], 1)
        self.assertLess(len(nvidia.validate_request(self.request)), nvidia.MAX_REQUEST_BYTES)

    def test_rejects_missing_msa_and_ambiguous_ligand(self) -> None:
        molecule = self.request["inputs"][0]["molecules"][0]
        del molecule["msa"]
        with self.assertRaisesRegex(ValueError, "requires an MSA"):
            nvidia.validate_request(self.request)
        self.request["inputs"][0]["molecules"] = [{"type": "ligand", "smiles": "CCO", "ccd_codes": "EOH"}]
        with self.assertRaisesRegex(ValueError, "exactly one"):
            nvidia.validate_request(self.request)

    def test_rejects_excess_samples_and_bad_msa_query(self) -> None:
        self.request["inputs"][0]["diffusion_samples"] = 6
        with self.assertRaisesRegex(ValueError, "1 to 5"):
            nvidia.validate_request(self.request)
        self.request["inputs"][0]["diffusion_samples"] = 1
        self.request["inputs"][0]["molecules"][0]["msa"]["query_only"]["a3m"]["alignment"] = ">query\nAAAA\n"
        with self.assertRaisesRegex(ValueError, "first sequence"):
            nvidia.validate_request(self.request)

    def test_rejects_duplicate_chain_ids_within_one_molecule(self) -> None:
        self.request["inputs"][0]["molecules"][0]["id"] = ["A", "A"]
        with self.assertRaisesRegex(ValueError, "unique within a molecule"):
            nvidia.validate_request(self.request)

    def test_predict_writes_structures_and_safe_manifest_only(self) -> None:
        cif_with_reference = "data_model\n_audit.url https://example.test/public-reference\n#\n"
        response = {
            "request_id": "1UBQ-public",
            "signed_url": "https://example.test/private?token=secret",
            "outputs": [{
                "input_id": "1UBQ-public",
                "runtime_metrics": {"inference_seconds": 2.5, "url": "https://example.test/private"},
                "structures_with_scores": [{
                    "format": "cif", "structure": cif_with_reference,
                    "confidence_score": 0.82, "complex_plddt_score": 0.75,
                    "unknown_link": "https://example.test/private?token=secret",
                }],
            }],
        }
        output_dir = self.root / "fold"
        with patch.object(nvidia, "_send", return_value=response) as send:
            summary = nvidia.predict(self.request, output_dir, "test-only-secret")
        self.assertEqual(send.call_count, 1)
        self.assertEqual((output_dir / "request.json").read_bytes(), nvidia.validate_request(self.request))
        self.assertEqual((output_dir / "sample-01.cif").read_text(), cif_with_reference)
        manifest_text = (output_dir / "manifest.json").read_text()
        self.assertNotIn("secret", manifest_text)
        self.assertNotIn("https://example.test", manifest_text)
        self.assertEqual(json.loads(manifest_text)["outputs"][0]["scores"]["confidence_score"], 0.82)
        self.assertEqual(json.loads(manifest_text)["runtime_metrics"], {"inference_seconds": 2.5})
        self.assertEqual(summary["outputs"], [str(output_dir / "sample-01.cif")])
        receipt_text = Path(summary["provenance"]).read_text()
        self.assertNotIn("secret", receipt_text)
        self.assertNotIn("example.test", receipt_text)
        receipt = json.loads(receipt_text)
        self.assertEqual(receipt["payload"]["status"], "complete")
        self.assertEqual(len(receipt["outputs"]), 3)
        self.assertEqual(receipt["outputs"][1]["sha256"], json.loads(manifest_text)["outputs"][0]["sha256"])
        with self.assertRaises(FileExistsError):
            nvidia.predict(self.request, output_dir, "test-only-secret")
        self.assertEqual(send.call_count, 1)

    def test_http_error_does_not_echo_body_or_key(self) -> None:
        secret = "test-only-secret"
        body = f"https://example.test/?token={secret}".encode()
        error = HTTPError(nvidia.ENDPOINT, 401, "unauthorized", {}, __import__("io").BytesIO(body))
        with patch.object(nvidia, "build_opener") as opener, self.assertRaises(nvidia.NvidiaError) as caught:
            opener.return_value.open.side_effect = error
            nvidia.predict(self.request, self.root / "failed", secret)
        self.assertEqual(caught.exception.http_status, 401)
        status = (self.root / "failed" / "status.json").read_text()
        self.assertNotIn(secret, status)
        self.assertNotIn("example.test", status)
        self.assertEqual(json.loads(status)["http_status"], 401)
        receipt = json.loads(next((self.root / "data" / "provenance").glob("*_fold-nvidia.json")).read_text())
        self.assertEqual(receipt["payload"]["status"], "failed")

    def test_rejects_url_instead_of_structure(self) -> None:
        response = {"outputs": [{"structures_with_scores": [{
            "format": "cif", "structure": "https://example.test/signed?token=secret",
        }]}]}
        with patch.object(nvidia, "_send", return_value=response), self.assertRaises(nvidia.NvidiaError):
            nvidia.predict(self.request, self.root / "bad-response", "test-only-secret")
        self.assertFalse((self.root / "bad-response" / "sample-01.cif").exists())

    def test_rejects_mismatched_response_identity(self) -> None:
        response = {"request_id": "other-run", "outputs": [{
            "input_id": "1UBQ-public", "structures_with_scores": [{"format": "cif", "structure": CIF}],
        }]}
        with patch.object(nvidia, "_send", return_value=response), self.assertRaisesRegex(nvidia.NvidiaError, "request_id"):
            nvidia.predict(self.request, self.root / "wrong-run", "test-only-secret")
        self.assertFalse((self.root / "wrong-run" / "sample-01.cif").exists())

    def test_connection_failure_records_unknown_submission_state(self) -> None:
        with patch.object(nvidia, "build_opener") as opener, self.assertRaises(nvidia.NvidiaError) as caught:
            opener.return_value.open.side_effect = TimeoutError("timed out")
            nvidia.predict(self.request, self.root / "uncertain", "test-only-secret")
        self.assertTrue(caught.exception.submission_unknown)
        status = json.loads((self.root / "uncertain" / "status.json").read_text())
        self.assertEqual(status["status"], "unknown")
        receipt = json.loads(next((self.root / "data" / "provenance").glob("*_fold-nvidia.json")).read_text())
        self.assertEqual(receipt["payload"]["status"], "unknown")

    def test_transient_http_errors_leave_submission_state_unknown(self) -> None:
        for code, expected in ((408, "unknown"), (429, "unknown"),
                               (503, "unknown"), (422, "failed")):
            with self.subTest(code=code):
                error = HTTPError(nvidia.ENDPOINT, code, "provider error", {}, io.BytesIO(b"private body"))
                with patch.object(nvidia, "build_opener") as opener, self.assertRaises(nvidia.NvidiaError):
                    opener.return_value.open.side_effect = error
                    nvidia.predict(self.request, self.root / f"http-{code}", "test-only-secret")
                status = json.loads((self.root / f"http-{code}" / "status.json").read_text())
                self.assertEqual(status["status"], expected)
                self.assertEqual(status["http_status"], code)

    def test_redirect_cannot_forward_bearer_key(self) -> None:
        received = {"origin": 0, "origin_has_bearer": False, "destination": 0}
        destination = None

        class DestinationHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                received["destination"] += 1
                self.send_response(200)
                self.end_headers()

            def log_message(self, *_args):
                pass

        destination = ThreadingHTTPServer(("127.0.0.1", 0), DestinationHandler)

        class OriginHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                received["origin"] += 1
                received["origin_has_bearer"] = self.headers.get("Authorization") == "Bearer test-only-secret"
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{destination.server_port}/capture")
                self.end_headers()

            def log_message(self, *_args):
                pass

        origin = ThreadingHTTPServer(("127.0.0.1", 0), OriginHandler)
        threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in (origin, destination)]
        for thread in threads:
            thread.start()
        try:
            with patch.object(nvidia, "ENDPOINT", f"http://127.0.0.1:{origin.server_port}/predict"), \
                 self.assertRaises(nvidia.NvidiaError) as caught:
                nvidia._send(nvidia.validate_request(self.request), "test-only-secret", 5)
            self.assertEqual(caught.exception.http_status, 302)
            self.assertEqual(received, {"origin": 1, "origin_has_bearer": True, "destination": 0})
        finally:
            for server in (origin, destination):
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=2)

    def test_cli_requires_ignored_structures_output_directory(self) -> None:
        request_file = self.root / "request.json"
        request_file.write_text(json.dumps(self.request))
        with patch.dict(nvidia.os.environ, {"REGEN_DATA": str(self.root / "data")}), \
             contextlib.redirect_stderr(io.StringIO()), \
             self.assertRaises(SystemExit) as caught:
            nvidia.main(["predict", str(request_file), "--out", str(self.root / "examples" / "output")])
        self.assertEqual(caught.exception.code, 1)
        self.assertFalse((self.root / "examples" / "output").exists())

    def test_cli_predict_dispatches_under_data_structures(self) -> None:
        request_file = self.root / "request.json"
        request_file.write_text(json.dumps(self.request))
        output_dir = self.root / "data" / "structures" / "nvidia-run"
        response = {"request_id": "1UBQ-public", "outputs": [{
            "input_id": "1UBQ-public",
            "structures_with_scores": [{"format": "cif", "structure": CIF}],
        }]}
        with patch.dict(nvidia.os.environ, {"REGEN_DATA": str(self.root / "data")}), \
             patch.object(nvidia, "load_api_key", return_value="test-only-secret"), \
             patch.object(nvidia, "_send", return_value=response) as send, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            nvidia.main(["predict", str(request_file), "--out", str(output_dir)])
        self.assertEqual(send.call_count, 1)
        self.assertTrue((output_dir / "manifest.json").is_file())
        self.assertEqual(json.loads(output.getvalue())["outputs"], [str(output_dir / "sample-01.cif")])

    def test_key_loader_prefers_process_env_and_reads_host_env(self) -> None:
        env_file = self.root / ".env"
        env_file.write_text("NVIDIA_API_KEY='file-test-key'\n")
        with patch.dict(nvidia.os.environ, {"NVIDIA_API_KEY": ""}):
            self.assertEqual(nvidia.load_api_key(env_file), "file-test-key")
        with patch.dict(nvidia.os.environ, {"NVIDIA_API_KEY": "process-test-key"}):
            self.assertEqual(nvidia.load_api_key(env_file), "process-test-key")


if __name__ == "__main__":
    unittest.main()
