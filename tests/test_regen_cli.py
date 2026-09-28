from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import regen  # noqa: E402


class RegenCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        root = Path(self.tempdir.name)
        for name, value in (
            ("DATA", root / "data"),
            ("CACHE", root / "cache"),
            ("PROV", root / "data" / "provenance"),
        ):
            patcher = patch.object(regen, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        regen.ensure_dirs()

    def test_afdb_pdb_fallback_uses_pdb_extension(self) -> None:
        with patch.object(regen, "http_json", return_value=[{"pdbUrl": "https://example.org/model.pdb"}]), \
             patch.object(regen, "http_bytes", return_value=b"HEADER\n"), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            regen.cmd_afdb(["P04637"])

        structure = regen.DATA / "structures" / "AF-P04637.pdb"
        self.assertEqual(structure.read_bytes(), b"HEADER\n")
        summary = json.loads(output.getvalue().split("# provenance", 1)[0])
        self.assertEqual(summary["format"], "pdb")
        self.assertEqual(summary["structure"], str(structure))

    def test_afdb_cif_keeps_existing_summary_field(self) -> None:
        with patch.object(regen, "http_json", return_value=[{"cifUrl": "https://example.org/model.cif"}]), \
             patch.object(regen, "http_bytes", return_value=b"data_model\n"), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            regen.cmd_afdb(["P04637"])

        structure = regen.DATA / "structures" / "AF-P04637.cif"
        summary = json.loads(output.getvalue().split("# provenance", 1)[0])
        self.assertEqual(summary["cif"], str(structure))
        self.assertEqual(summary["format"], "cif")

    def test_interpro_combines_all_pages(self) -> None:
        responses = [
            {"count": 2, "results": [{"metadata": {"accession": "IPR001"}}], "next": "?page=2"},
            {"count": 2, "results": [{"metadata": {"accession": "IPR002"}}], "next": None},
        ]
        with patch.object(regen, "http_json", side_effect=responses) as fetch, \
             contextlib.redirect_stdout(io.StringIO()):
            regen.cmd_interpro(["P04637"])

        saved = json.loads((regen.DATA / "sequences" / "interpro_P04637.json").read_text())
        self.assertEqual([entry["metadata"]["accession"] for entry in saved["results"]], ["IPR001", "IPR002"])
        self.assertEqual(saved["pages_fetched"], 2)
        self.assertIsNone(saved["next"])
        self.assertEqual(fetch.call_count, 2)

    def test_interpro_rejects_external_pagination_url(self) -> None:
        with patch.object(regen, "http_json", return_value={"results": [], "next": "https://example.org/elsewhere"}), \
             contextlib.redirect_stderr(io.StringIO()), \
             self.assertRaises(SystemExit):
            regen.cmd_interpro(["P04637"])
        self.assertFalse((regen.DATA / "sequences" / "interpro_P04637.json").exists())

    def test_doctor_records_missing_tools(self) -> None:
        with patch.object(regen.shutil, "which", return_value=None), \
             patch.object(regen.subprocess, "check_output", side_effect=FileNotFoundError), \
             patch.object(regen, "record") as record, \
             contextlib.redirect_stdout(io.StringIO()):
            regen.cmd_doctor([])

        status = record.call_args.args[1]
        self.assertFalse(status["ok"])
        self.assertIn("jupyter", status["missing_binaries"])
        self.assertFalse(status["gpu_visible"])

    def test_openalex_sends_key_as_bearer_header(self) -> None:
        with patch.object(regen, "OPENALEX_KEY", "example-test-key"), \
             patch.object(regen, "http_json", return_value={"results": []}) as fetch, \
             contextlib.redirect_stdout(io.StringIO()):
            regen.cmd_openalex(["cell biology", "--limit", "1"])

        self.assertNotIn("example-test-key", fetch.call_args.args[0])
        self.assertEqual(fetch.call_args.kwargs["headers"], {"Authorization": "Bearer example-test-key"})

    def test_cmd_pipeline_dispatches_properly(self) -> None:
        with patch("regen_compute.pipeline") as mock_pipeline:
            regen.cmd_pipeline(["--matrix", "matrix.csv", "--samples", "samples.csv"])
            mock_pipeline.assert_called_once()
            self.assertEqual(mock_pipeline.call_args.args[0], ["--matrix", "matrix.csv", "--samples", "samples.csv"])

    def test_cmd_pipeline_handles_error(self) -> None:
        with patch("regen_compute.pipeline", side_effect=ValueError("bad group")), \
             contextlib.redirect_stderr(io.StringIO()), \
             self.assertRaises(SystemExit):
            regen.cmd_pipeline(["--bad"])


class RetryTests(unittest.TestCase):
    """Tests for _http_with_retry exponential backoff."""

    def test_retries_on_503_then_succeeds(self) -> None:
        from urllib.error import HTTPError
        from urllib.request import Request

        call_count = 0

        def mock_urlopen(req, timeout=60):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise HTTPError(req.full_url, 503, "Service Unavailable", {}, None)

            class FakeResp:
                def read(self):
                    return b'{"ok": true}'
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    pass

            return FakeResp()

        req = Request("https://example.com/test")
        with patch.object(regen, "urlopen", mock_urlopen), \
             patch.object(regen.time, "sleep"):
            resp = regen._http_with_retry(req, 60)
            data = json.loads(resp.read())
        self.assertTrue(data["ok"])
        self.assertEqual(call_count, 3)

    def test_does_not_retry_on_404(self) -> None:
        from urllib.error import HTTPError
        from urllib.request import Request

        call_count = 0

        def mock_urlopen(req, timeout=60):
            nonlocal call_count
            call_count += 1
            raise HTTPError(req.full_url, 404, "Not Found", {}, None)

        req = Request("https://example.com/missing")
        with patch.object(regen, "urlopen", mock_urlopen), \
             self.assertRaises(HTTPError) as ctx:
            regen._http_with_retry(req, 60)
        self.assertEqual(ctx.exception.code, 404)
        self.assertEqual(call_count, 1)  # no retries on 404

    def test_retries_on_connection_error(self) -> None:
        from urllib.request import Request

        call_count = 0

        def mock_urlopen(req, timeout=60):
            nonlocal call_count
            call_count += 1
            if call_count <= regen._MAX_RETRIES:
                raise OSError("Connection refused")

            class FakeResp:
                def read(self):
                    return b"ok"
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    pass

            return FakeResp()

        req = Request("https://example.com/test")
        with patch.object(regen, "urlopen", mock_urlopen), \
             patch.object(regen.time, "sleep"):
            resp = regen._http_with_retry(req, 60)
        self.assertEqual(resp.read(), b"ok")
        self.assertEqual(call_count, regen._MAX_RETRIES + 1)

    def test_raises_after_exhausting_retries(self) -> None:
        from urllib.error import HTTPError
        from urllib.request import Request

        def mock_urlopen(req, timeout=60):
            raise HTTPError(req.full_url, 429, "Too Many Requests", {}, None)

        req = Request("https://example.com/test")
        with patch.object(regen, "urlopen", mock_urlopen), \
             patch.object(regen.time, "sleep"), \
             self.assertRaises(HTTPError) as ctx:
            regen._http_with_retry(req, 60)
        self.assertEqual(ctx.exception.code, 429)

    def test_backoff_delays_double(self) -> None:
        from urllib.error import HTTPError
        from urllib.request import Request

        sleep_calls = []

        def mock_urlopen(req, timeout=60):
            raise HTTPError(req.full_url, 503, "Unavailable", {}, None)

        def mock_sleep(seconds):
            sleep_calls.append(seconds)

        req = Request("https://example.com/test")
        with patch.object(regen, "urlopen", mock_urlopen), \
             patch.object(regen.time, "sleep", mock_sleep), \
             self.assertRaises(HTTPError):
            regen._http_with_retry(req, 60)
        # Backoff: 1s, 2s, 4s
        self.assertEqual(sleep_calls, [1.0, 2.0, 4.0])


if __name__ == "__main__":
    unittest.main()
