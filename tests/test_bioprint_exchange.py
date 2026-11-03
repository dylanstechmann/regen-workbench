from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import bioprint_exchange as bx
import regen
import regen_desk as desk_module

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bioprint_exchange"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class BundleValidationTests(unittest.TestCase):
    def test_minimal_and_roundtrip_validate_invalid_schema_fails_closed(self):
        minimal = bx.validate_bundle(load("minimal.json"))
        self.assertEqual(minimal["schema"], bx.SCHEMA)
        roundtrip = bx.validate_bundle(load("roundtrip.json"))
        self.assertEqual(len(roundtrip["hypotheses"]), 2)
        self.assertEqual(roundtrip["modelRuns"][0]["status"], "unsupported-foreign")
        with self.assertRaises(ValueError):
            bx.validate_bundle(load("invalid.json"))
        with self.assertRaises(TypeError):
            bx.validate_bundle(json.loads('{"schema":"%s","__proto__":{"x":1}}' % bx.SCHEMA))

    def test_rejects_dangling_references_cycles_and_duplicates(self):
        base = load("roundtrip.json")
        dangling = copy.deepcopy(base)
        dangling["queries"][0]["hypothesisId"] = "ghost"
        with self.assertRaises(ValueError):
            bx.validate_bundle(dangling)
        cyclic = copy.deepcopy(base)
        cyclic["hypotheses"][0]["parentHypothesisIds"] = ["hyp-b"]
        with self.assertRaises(ValueError):
            bx.validate_bundle(cyclic)
        dup = copy.deepcopy(base)
        dup["hypotheses"].append(copy.deepcopy(dup["hypotheses"][0]))
        with self.assertRaises(ValueError):
            bx.validate_bundle(dup)

    def test_artifact_verification_hashes_exact_bytes(self):
        bundle = load("roundtrip.json")
        data = (FIXTURES / "synthetic.json").read_bytes()
        good = bx.verify_artifact_files(bundle, [("synthetic.json", data)])
        self.assertEqual(good["verified"], ["art-1"])
        wrong = bx.verify_artifact_files(bundle, [("synthetic.json", b"123")])
        self.assertEqual(wrong["failed"][0]["reason"], "size mismatch")
        missing = bx.verify_artifact_files(bundle, [])
        self.assertEqual(missing["failed"][0]["reason"], "file not selected")

    def test_cross_language_golden_bytes(self):
        self.assertEqual(bx.canonical_json_bytes({"b": 2, "a": 1}), b'{"a":1,"b":2}\n')

    def test_fixture_golden_digests(self):
        golden = json.loads((FIXTURES / "golden-digests.json").read_text(encoding="utf-8"))
        self.assertEqual(golden["canonicalizer"], "sorted-json-lf/1")
        self.assertEqual(bx.canonical_json_bytes(golden["vector"]["input"]),
                         golden["vector"]["canonical"].encode("utf-8"))
        self.assertEqual(hashlib.sha256(bx.canonical_json_bytes(golden["vector"]["input"])).hexdigest(),
                         golden["vector"]["sha256"])
        for name, digest in golden["fixtures"].items():
            parsed = load(name)
            self.assertEqual(hashlib.sha256(bx.canonical_json_bytes(parsed)).hexdigest(), digest,
                             f"{name} canonical digest must match the JS side")
        for name, digest in golden["artifacts"].items():
            self.assertEqual(hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest(), digest,
                             f"{name} exact-byte digest must match the JS side")

    def test_preview_classifies_and_apply_is_idempotent(self):
        bundle = load("minimal.json")
        first = bx.preview_import(bundle, bx.empty_state())
        self.assertEqual(first["creates"], ["hypotheses:hyp-a"])
        self.assertTrue(any("not-approved" in w for w in first["warnings"]))
        applied = bx.apply_import(bundle, bx.empty_state())
        self.assertEqual(len(applied["hypotheses"]), 1)
        second = bx.preview_import(bundle, applied)
        self.assertEqual(second["duplicates"], ["hypotheses:hyp-a"])
        again = bx.apply_import(bundle, applied)
        self.assertEqual(len(again["hypotheses"]), 1)
        conflict = bx.preview_import(load("conflicts.json"), applied)
        self.assertEqual(conflict["conflicts"], ["hypotheses:hyp-a"])
        with self.assertRaises(ValueError):
            bx.apply_import(load("conflicts.json"), applied)

    def test_receipt_statuses_are_preserved_verbatim(self):
        bundle = copy.deepcopy(load("minimal.json"))
        bundle["modelRuns"] = [
            {"modelId": "desk-run", "id": "r1", "status": "partial", "note": "one provider failed", "queryPlanId": "q1", "deskRunId": "d1"},
            {"modelId": "desk-run", "id": "r2", "status": "interrupted", "note": "server restarted", "queryPlanId": "q1", "deskRunId": "d2"},
            {"modelId": "desk-run", "id": "r3", "status": "submission-unknown", "note": "ambiguous response", "queryPlanId": "q1", "deskRunId": None},
        ]
        validated = bx.validate_bundle(bundle)
        self.assertEqual([run["status"] for run in validated["modelRuns"]],
                         ["partial", "interrupted", "submission-unknown"])

    def test_to_desk_question_requires_competing_hypotheses(self):
        question = bx.to_desk_question(load("minimal.json")["hypotheses"][0])
        self.assertEqual(len(question["competing_hypotheses"]), 2)
        self.assertEqual(question["review_state"], "unreviewed")
        weak = copy.deepcopy(load("minimal.json")["hypotheses"][0])
        weak["alternatives"] = weak["alternatives"][:1]
        with self.assertRaises(ValueError):
            bx.to_desk_question(weak)

    def test_export_selected_results_writes_bounded_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = bx.export_selected_results({
                "bundleId": "bundle-results", "createdAt": "2026-11-03T12:00:00Z",
                "modelRuns": [{"modelId": "desk-run", "id": "r1", "status": "succeeded", "note": "mock result", "queryPlanId": "q1", "deskRunId": "d1"}],
                "files": [("synthetic.json", (FIXTURES / "synthetic.json").read_bytes())],
            }, Path(tmp) / "out")
            manifest = json.loads(Path(report["manifest"]).read_text())
            self.assertEqual(manifest["publicationReviewStatus"], "not-approved")
            self.assertIn("synthetic.json", report["files"])
            with self.assertRaises(ValueError):
                bx.export_selected_results({"bundleId": "bad", "createdAt": "2026-11-03T12:00:00Z", "files": [("../escape.json", b"x")]}, Path(tmp) / "out2")


class DeskExchangeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for name, value in (("DATA", root / "data"), ("CACHE", root / "cache"), ("PROV", root / "provenance")):
            patcher = patch.object(regen, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.desk = desk_module.Desk(root / "desk")
        self.addCleanup(lambda: self.desk.executor.shutdown(wait=True))

    def test_import_never_submits_and_is_atomic_under_save_failure(self):
        bundle = load("minimal.json")
        preview = self.desk.preview_bioprint_import(copy.deepcopy(bundle))
        self.assertEqual(preview["creates"], ["hypotheses:hyp-a"])
        with patch.object(self.desk, "submit", side_effect=AssertionError("submit must not be called")) as submit:
            result = self.desk.apply_bioprint_import(copy.deepcopy(bundle))
        self.assertEqual(submit.call_count, 0)
        self.assertTrue(result["applied"])
        self.assertEqual(len(self.desk.store["bioprint_state"]["hypotheses"]), 1)
        self.assertEqual(len(self.desk.store["bioprint_imports"]), 1)
        before = json.loads(json.dumps(self.desk.store))
        other = load("minimal.json")
        other["bundleId"] = "bundle-other"
        other["hypotheses"][0]["id"] = "hyp-new"
        other["hypotheses"][0]["title"] = "A different synthetic question"
        with patch.object(self.desk, "save_store", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.desk.apply_bioprint_import(other)
        self.assertEqual(json.loads(json.dumps(self.desk.store)), before)

    def test_reapplying_identical_bundle_is_idempotent(self):
        bundle = load("minimal.json")
        self.desk.apply_bioprint_import(copy.deepcopy(bundle))
        second = self.desk.apply_bioprint_import(copy.deepcopy(bundle))
        self.assertEqual(second["creates"], [])
        self.assertEqual(second["duplicates"], ["hypotheses:hyp-a"])
        self.assertEqual(len(self.desk.store["bioprint_state"]["hypotheses"]), 1)


if __name__ == "__main__":
    unittest.main()
