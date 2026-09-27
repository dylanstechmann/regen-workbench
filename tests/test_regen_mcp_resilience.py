from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import regen_mcp  # noqa: E402


class McpResilienceTests(unittest.TestCase):
    def test_invalid_resource_uris_are_protocol_errors(self) -> None:
        for uri in (None, True, 17, [], {}, "", "  ", "regen://data/provenance/bad\0.json"):
            with self.subTest(uri=uri), patch.object(regen_mcp, "_read_resource") as read:
                response = regen_mcp.handle_message(
                    {"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": uri}},
                    {"initialized": True},
                )
                self.assertEqual(response["error"]["code"], -32602)
                self.assertEqual(response["id"], 2)
                read.assert_not_called()

    def test_invalid_resource_request_does_not_disconnect_client(self) -> None:
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": None}},
            {"jsonrpc": "2.0", "id": 3, "method": "ping"},
        ]
        result = subprocess.run(
            [sys.executable, "-B", str(TOOLS_DIR / "regen_mcp.py")],
            input="\n".join(json.dumps(message) for message in messages) + "\n",
            text=True, capture_output=True, check=True, timeout=5,
        )
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([response["id"] for response in responses], [1, 2, 3])
        self.assertEqual(responses[1]["error"]["code"], -32602)
        self.assertEqual(responses[2]["result"], {})
        self.assertEqual(result.stderr, "")

    def test_resource_filesystem_errors_do_not_end_session_or_expose_details(self) -> None:
        request = {"jsonrpc": "2.0", "id": 2, "method": "resources/read",
                   "params": {"uri": "regen://config/tools.yaml"}}
        ping = {"jsonrpc": "2.0", "id": 3, "method": "ping"}
        for error in (PermissionError("private path"), FileNotFoundError("private path"),
                      RuntimeError("symlink loop at private path")):
            with self.subTest(error=error), patch.object(regen_mcp, "_read_resource", side_effect=error), \
                 contextlib.redirect_stderr(io.StringIO()):
                state = {"initialized": True}
                response = regen_mcp.handle_message(request, state)
                self.assertEqual(response["error"]["code"], -32603)
                self.assertNotIn("private path", json.dumps(response))
                self.assertEqual(regen_mcp.handle_message(ping, state)["result"], {})

    def _serve(self, stream: io.StringIO, limit: int = 128) -> list[dict]:
        with patch.object(regen_mcp.sys, "stdin", stream), \
             patch.object(regen_mcp, "MAX_INPUT_CHARS", limit), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            regen_mcp.serve()
        return [json.loads(line) for line in output.getvalue().splitlines()]

    def test_oversized_request_is_drained_with_bounded_reads_then_ping_succeeds(self) -> None:
        class BoundedInput(io.StringIO):
            def readline(self, size=-1):
                if not 0 < size <= 129:
                    raise AssertionError(f"unbounded read: {size}")
                return super().readline(size)

        ping = json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"}) + "\n"
        responses = self._serve(BoundedInput("x" * 400 + "\n" + ping))
        self.assertEqual(len(responses), 2)
        self.assertEqual(responses[0]["error"]["code"], -32600)
        self.assertEqual(responses[1]["id"], 3)
        self.assertEqual(responses[1]["result"], {})

    def test_oversized_unterminated_request_at_eof_returns_one_error(self) -> None:
        responses = self._serve(io.StringIO("x" * 400))
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["error"]["code"], -32600)

    def test_request_at_exact_limit_remains_valid(self) -> None:
        ping = json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"})
        responses = self._serve(io.StringIO(ping.ljust(127) + "\n"))
        self.assertEqual(responses, [{"jsonrpc": "2.0", "id": 3, "result": {}}])

    def test_excessively_nested_json_does_not_disconnect_client(self) -> None:
        nested = "[" * 2000 + "0" + "]" * 2000
        ping = json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"})
        responses = self._serve(io.StringIO(nested + "\n" + ping + "\n"), limit=10000)
        self.assertEqual(responses[0]["error"]["code"], -32700)
        self.assertEqual(responses[1]["result"], {})

    def test_resource_file_reads_are_bounded_before_truncation(self) -> None:
        class BoundedFile(io.StringIO):
            def read(self, size=-1):
                if size != 11:
                    raise AssertionError(f"unbounded resource read: {size}")
                return super().read(size)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config"
            config.mkdir()
            (config / "tools.yaml").touch()
            receipts = root / "data" / "provenance"
            receipts.mkdir(parents=True)
            (receipts / "123_test.json").touch()
            for uri in ("regen://config/tools.yaml", "regen://data/provenance/123_test.json"):
                with self.subTest(uri=uri), patch.object(regen_mcp, "CONFIG_DIR", config), \
                     patch.object(regen_mcp, "DATA_DIR", root / "data"), \
                     patch.object(regen_mcp, "MAX_OUTPUT_CHARS", 10), \
                     patch.object(Path, "open", return_value=BoundedFile("x" * 100)):
                    text = regen_mcp._read_resource(uri)["contents"][0]["text"]
                self.assertTrue(text.startswith("x" * 10 + "\n"))
                self.assertIn("[truncated]", text)
                self.assertLess(len(text), 30)


if __name__ == "__main__":
    unittest.main()
