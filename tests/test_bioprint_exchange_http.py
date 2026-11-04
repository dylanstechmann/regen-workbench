"""Loopback-only exchange integration: no providers or submissions."""
import copy
import http.client
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import regen
import regen_desk


class ExchangeHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for name in ("DATA", "CACHE", "PROV"):
            patcher = patch.object(regen, name, root / name.lower())
            patcher.start()
            self.addCleanup(patcher.stop)
        self.desk = regen_desk.Desk(root / "desk")
        self.addCleanup(lambda: self.desk.executor.shutdown(wait=True))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), regen_desk.make_handler(self.desk))
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_address[1]
        fixture = Path(__file__).parent / "fixtures" / "bioprint_exchange" / "minimal.json"
        self.bundle = json.loads(fixture.read_text())

    def post(self, route, value, origin=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/json", "Origin": origin or f"http://127.0.0.1:{self.port}"}
        connection.request("POST", route, json.dumps(value), headers)
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_preview_apply_token_round_trip_never_submits(self):
        with patch.object(self.desk, "submit", side_effect=AssertionError("Import submitted work")) as submit:
            status, preview = self.post("/api/bioprint/preview", self.bundle)
            self.assertEqual(status, 200)
            self.assertNotIn("bioprint_state", self.desk.store)
            payload = {"bundle": self.bundle, "preview": preview}
            status, result = self.post("/api/bioprint/apply", payload)
            self.assertEqual(status, 200, result)
            self.assertTrue(result["applied"])
            status, stale = self.post("/api/bioprint/apply", payload)
            self.assertEqual(status, 400)
            self.assertIn("stale", stale["error"])
            self.assertEqual(submit.call_count, 0)

    def test_bare_apply_and_cross_origin_requests_are_rejected(self):
        self.assertEqual(self.post("/api/bioprint/apply", self.bundle)[0], 400)
        self.assertEqual(self.post("/api/bioprint/preview", self.bundle, "https://example.invalid")[0], 403)