"""Loopback-only exchange integration: no providers or submissions."""
import copy
import http.client
import io
import json
import sys
import tempfile
import threading
import time
import unittest
import zipfile
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

    # ---- real queue + mocked provider boundary, explicit export selection ----

    QUEUED = json.loads((Path(__file__).parent / "fixtures" / "bioprint_exchange" / "queued.json").read_text())

    def get_json(self, route):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request("GET", route, headers={"Origin": f"http://127.0.0.1:{self.port}"})
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def post_raw(self, route, value):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"}
        connection.request("POST", route, json.dumps(value), headers)
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def mock_provider(self, calls):
        def fake(provider, query, limit):
            calls.append((provider, query, limit))
            rows = [regen_desk.hit(provider, f"Synthetic fixture record {index}", f"https://example.invalid/mock/{index}",
                                   "2026-01-01", pmid=str(1000 + index)) for index in range(min(limit, 3))]
            return {"fixture": "mocked-provider-v1"}, rows
        return patch.object(regen_desk, "search_provider", side_effect=fake)

    def apply_queued(self):
        status, preview = self.post("/api/bioprint/preview", self.QUEUED)
        self.assertEqual(status, 200, preview)
        status, result = self.post("/api/bioprint/apply", {"bundle": self.QUEUED, "preview": preview})
        self.assertEqual(status, 200, result)
        self.assertTrue(result["applied"])


    def reviewed_submission(self, calls):
        blueprint = self.desk.blueprint({"title": "Fixture blueprint"})["id"]
        status, review = self.post("/api/bioprint/review-query", {"queryId": "query-a", "blueprintId": blueprint})
        self.assertEqual(status, 200, review)
        payload = {"queryId": "query-a", "blueprintId": blueprint, "reviewToken": review["reviewToken"], "confirmed": True}
        status, receipt = self.post("/api/bioprint/submit-query", payload)
        self.assertEqual(status, 200, receipt)
        self.assertIn(receipt["status"], {"queued", "running"})
        self.assertRegex(receipt["deskRunId"], r"^[a-f0-9]{32}$")
        run = {}
        for _ in range(200):
            status, run = self.get_json(f"/api/run/{receipt['deskRunId']}")
            self.assertEqual(status, 200)
            if run["status"] in {"complete", "partial", "failed", "interrupted"}:
                break
            time.sleep(0.025)
        return blueprint, review, payload, receipt, run

    def test_reviewed_submission_runs_the_real_queue_with_mocked_provider(self):
        self.apply_queued()
        calls = []
        with self.mock_provider(calls), patch.object(regen_desk, "fetch_json",
                                                     side_effect=AssertionError("live traffic escaped the mock")):
            _, _, _, receipt, run = self.reviewed_submission(calls)
        self.assertEqual(run["status"], "complete", run.get("error"))
        self.assertEqual(calls, [("pubmed", self.QUEUED["queries"][0]["query"], 3)])
        self.assertEqual(len(run["result"]["hits"]), 3)
        self.assertEqual(run["result"]["providers"][0]["status"], "ok")
        self.assertIsNotNone(receipt["deskRunId"])

    def test_duplicate_submission_dedupes_and_stale_review_is_rejected(self):
        self.apply_queued()
        calls = []
        with self.mock_provider(calls):
            blueprint, review, payload, receipt, run = self.reviewed_submission(calls)
            status, repeated = self.post("/api/bioprint/submit-query", payload)
        self.assertEqual(status, 200)
        self.assertEqual(repeated, receipt, "a repeated reviewed submission must return the stored receipt")
        self.assertEqual(run["status"], "complete", run.get("error"))
        self.assertEqual(len(calls), 1, "deduplication must never queue duplicate provider work")
        status, stale = self.post("/api/bioprint/submit-query", {**payload, "reviewToken": "f" * 64})
        self.assertEqual(status, 400)
        self.assertIn("stale", stale["error"])
        status, unconfirmed = self.post("/api/bioprint/submit-query",
                                        {"queryId": "query-a", "blueprintId": blueprint, "reviewToken": review["reviewToken"]})
        self.assertEqual(status, 400)
        self.assertIn("confirmation", unconfirmed["error"])
        status, unknown = self.post("/api/bioprint/review-query", {"queryId": "missing", "blueprintId": blueprint})
        self.assertEqual(status, 400)
        self.assertIn("Unknown imported query", unknown["error"])

    def test_export_selection_matrix_and_zip_artifact_hashes(self):
        self.apply_queued()
        calls = []
        with self.mock_provider(calls):
            _, _, _, _, run = self.reviewed_submission(calls)
        run_id = run["id"]
        status, error = self.post("/api/bioprint/export", {"hypothesisIds": ["missing"]})
        self.assertEqual(status, 400)
        self.assertIn("Unknown selected record", error["error"])
        status, error = self.post("/api/bioprint/export", {"deskRunIds": ["not-hex"]})
        self.assertEqual(status, 400)
        self.assertIn("Invalid Desk run ID", error["error"])
        status, error = self.post("/api/bioprint/export", {"deskRunIds": ["f" * 32]})
        self.assertEqual(status, 400)
        self.assertRegex(error["error"], r"Download failed|missing")
        status, archive = self.post_raw("/api/bioprint/export", {"queryIds": ["query-a"], "deskRunIds": [run_id]})
        self.assertEqual(status, 200, archive[:200])
        self.assertEqual(archive[:2], b"PK")
        import hashlib
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            names = zipped.namelist()
            self.assertIn("bioprint-results.json", names)
            self.assertIn(f"run-{run_id}.json", names)
            manifest = json.loads(zipped.read("bioprint-results.json"))
            for descriptor in manifest["artifacts"]:
                data = zipped.read(descriptor["filename"])
                self.assertEqual(len(data), descriptor["bytes"])
                self.assertEqual(hashlib.sha256(data).hexdigest(), descriptor["sha256"])
        returned = {record["id"] for record in manifest["hypotheses"]}
        self.assertIn("hyp-a", returned)
        desk_run = next(record for record in manifest["modelRuns"] if record.get("deskRunId") == run_id)
        self.assertEqual(desk_run["status"], "succeeded", "native complete maps to exchange succeeded")
        self.assertEqual(desk_run["id"], f"desk-{run_id}")
        status, empty_archive = self.post_raw("/api/bioprint/export", {})
        self.assertEqual(status, 200)
        with zipfile.ZipFile(io.BytesIO(empty_archive)) as zipped:
            empty = json.loads(zipped.read("bioprint-results.json"))
        self.assertEqual(empty["modelRuns"], [])
