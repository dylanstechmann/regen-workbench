from __future__ import annotations

import copy
import hashlib
import json
import io
import sys
import tempfile
import time
import unittest
import zipfile
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
    def test_shared_ancestor_diamond_is_not_a_cycle(self):
        bundle = load("minimal.json")
        template = bundle["hypotheses"][0]
        bundle["hypotheses"] = [dict(copy.deepcopy(template), id=name)
                                for name in ("root", "left", "right", "leaf")]
        bundle["hypotheses"][1]["parentHypothesisIds"] = ["root"]
        bundle["hypotheses"][2]["parentHypothesisIds"] = ["root"]
        bundle["hypotheses"][3]["parentHypothesisIds"] = ["left", "right"]
        self.assertEqual(len(bx.validate_bundle(bundle)["hypotheses"]), 4)
        bundle["hypotheses"][0]["parentHypothesisIds"] = ["leaf"]
        with self.assertRaisesRegex(ValueError, "acyclic"):
            bx.validate_bundle(bundle)

    def test_duplicate_ids_in_all_record_groups_are_rejected(self):
        for group in ("queries", "modelRuns", "evidence"):
            with self.subTest(group=group):
                bundle = load("roundtrip.json")
                bundle[group].append(copy.deepcopy(bundle[group][0]))
                with self.assertRaisesRegex(ValueError, "Duplicate"):
                    bx.validate_bundle(bundle)

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
                "artifacts": load("roundtrip.json")["artifacts"],
                "files": [("synthetic.json", (FIXTURES / "synthetic.json").read_bytes())],
            }, Path(tmp) / "out")
            manifest = json.loads(Path(report["manifest"]).read_text())
            self.assertEqual(manifest["publicationReviewStatus"], "not-approved")
            self.assertIn("synthetic.json", report["files"])
            with self.assertRaises(ValueError):
                bx.export_selected_results({"bundleId": "bad", "createdAt": "2026-11-03T12:00:00Z", "files": [("../escape.json", b"x")]}, Path(tmp) / "out2")

    def test_export_preflight_and_failures_never_publish_partial_files(self):
        selection = {"bundleId": "bundle-results", "createdAt": "2026-11-03T12:00:00Z",
                     "artifacts": load("roundtrip.json")["artifacts"],
                     "files": [("synthetic.json", (FIXTURES / "synthetic.json").read_bytes())]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            for files in ([], [("synthetic.json", b"wrong")], selection["files"] * 2,
                          [("bioprint-results.json", b"x")]):
                with self.subTest(files=files):
                    with self.assertRaises(ValueError):
                        bx.export_selected_results({**selection, "files": files}, root)
                    self.assertFalse(root.exists())
                    self.assertEqual(list(Path(tmp).iterdir()), [])
            with patch.object(Path, "write_bytes", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    bx.export_selected_results(selection, root)
            self.assertEqual(list(Path(tmp).iterdir()), [])
            bx.export_selected_results(selection, root)
            before = (root / "bioprint-results.json").read_bytes()
            with self.assertRaises(ValueError):
                bx.export_selected_results(selection, root)
            self.assertEqual((root / "bioprint-results.json").read_bytes(), before)

    def test_export_rejects_symlink_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "link"
            root.symlink_to(Path(tmp) / "missing", target_is_directory=True)
            with self.assertRaises(ValueError):
                bx.export_selected_results({"bundleId": "bundle-results", "createdAt": "2026-11-03T12:00:00Z"}, root)

    def test_export_finalization_fsync_failure_publishes_nothing(self):
        selection = {"bundleId": "bundle-results", "createdAt": "2026-11-03T12:00:00Z",
                     "artifacts": load("roundtrip.json")["artifacts"],
                     "files": [("synthetic.json", (FIXTURES / "synthetic.json").read_bytes())]}
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "exports"
            root = parent / "run-1"
            with patch("bioprint_exchange.os.fsync", side_effect=OSError("injected fsync failure")):
                with self.assertRaises(OSError):
                    bx.export_selected_results(selection, root)
            self.assertFalse(root.exists())
            self.assertEqual(list(parent.glob(".bioprint-export-*")), [])

    def test_export_finalization_never_overwrites_a_foreign_directory(self):
        # A hostile local writer that creates the target between the existence check and the
        # atomic rename makes publication fail loudly; its content survives untouched. This
        # documents filesystem-hygiene hardening, not an adversarial sandbox.
        selection = {"bundleId": "bundle-results", "createdAt": "2026-11-03T12:00:00Z",
                     "artifacts": load("roundtrip.json")["artifacts"],
                     "files": [("synthetic.json", (FIXTURES / "synthetic.json").read_bytes())]}
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "exports"
            root = parent / "run-1"
            real_replace = bx.os.replace
            def hostile(src, dst):
                Path(dst).mkdir()
                (Path(dst) / "hostile.txt").write_text("foreign", encoding="utf-8")
                return real_replace(src, dst)
            with patch("bioprint_exchange.os.replace", side_effect=hostile):
                with self.assertRaises(OSError):
                    bx.export_selected_results(selection, root)
            self.assertEqual((root / "hostile.txt").read_text(encoding="utf-8"), "foreign")
            self.assertEqual(list(parent.glob(".bioprint-export-*")), [])


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

    def test_apply_token_is_checked_under_store_lock(self):
        bundle = load("minimal.json")
        token = self.desk.preview_bioprint_import(bundle)
        forged = {**token, "bundleSha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "stale"):
            self.desk.apply_bioprint_import(bundle, forged)
        self.desk.apply_bioprint_import(bundle, token)
        with self.assertRaisesRegex(ValueError, "stale"):
            self.desk.apply_bioprint_import(bundle, token)

    def test_download_failure_messages_are_bounded_and_named(self):
        for kind in ("missing-artifact", "oversize-artifact", "hash-mismatch"):
            message = desk_module._download_failure(kind)
            self.assertIn("Download failed", message)
            self.assertIn("Nothing was downloaded", message)
            self.assertLess(len(message), 200)
        with self.assertRaises(ValueError):
            desk_module._download_failure("ghost-kind")

    def test_export_paths_are_generated_not_taken_from_bundle_id(self):
        result = self.desk.export_bioprint_results({"bundleId": "../outside", "createdAt": "2026-11-03T12:00:00Z"})
        manifest = Path(result["manifest"])
        self.assertEqual(manifest.parent.parent, self.desk.root / "bioprint-exports")
        self.assertEqual(manifest.parent.name, result["exportId"])

    def test_explicit_query_submission_is_idempotent_and_export_preserves_status(self):
        bundle = load("roundtrip.json")
        bundle["queries"][0]["providerIds"] = ["pubmed"]
        self.desk.apply_bioprint_import(bundle)
        blueprint = self.desk.store["blueprints"][0]["id"]
        request = {"queryId": bundle["queries"][0]["id"], "blueprintId": blueprint}
        review = self.desk.preview_bioprint_submission(request)
        request.update(reviewToken=review["reviewToken"], confirmed=True)
        run_id = "a" * 32
        with patch.object(self.desk, "submit", return_value={"id": run_id, "status": "queued"}) as submit:
            first = self.desk.submit_bioprint_query(request)
            self.assertEqual(self.desk.submit_bioprint_query(request), first)
            self.assertEqual(submit.call_count, 1)
        path = self.desk.runs / run_id
        path.mkdir()
        (path / "run.json").write_text(json.dumps({"id": run_id, "status": "partial", "summary": "mock provider result"}))
        archive = self.desk.export_bioprint_archive({"deskRunIds": [run_id]})
        with zipfile.ZipFile(io.BytesIO(archive)) as exported:
            manifest = bx.validate_bundle(json.loads(exported.read("bioprint-results.json")))
            self.assertEqual(manifest["modelRuns"][0]["status"], "partial")
            descriptor = manifest["artifacts"][0]
            self.assertEqual(hashlib.sha256(exported.read(descriptor["filename"])).hexdigest(), descriptor["sha256"])
        with self.assertRaises(ValueError):
            self.desk.export_bioprint_archive({"deskRunIds": ["../escape"]})

    def test_ambiguous_submission_is_never_automatically_retried(self):
        bundle = load("roundtrip.json")
        bundle["queries"][0]["providerIds"] = ["pubmed"]
        self.desk.apply_bioprint_import(bundle)
        request = {"queryId": bundle["queries"][0]["id"], "blueprintId": self.desk.store["blueprints"][0]["id"]}
        review = self.desk.preview_bioprint_submission(request)
        request.update(reviewToken=review["reviewToken"], confirmed=True)
        with patch.object(self.desk, "submit", side_effect=OSError("dispatch interrupted")) as submit:
            with self.assertRaises(OSError):
                self.desk.submit_bioprint_query(request)
            result = self.desk.submit_bioprint_query(request)
            self.assertEqual(result["status"], "submission-unknown")
            self.assertEqual(submit.call_count, 1)

    def test_mock_provider_runs_through_actual_queue_and_returns_verified_archive(self):
        bundle = load("roundtrip.json")
        bundle["queries"][0]["providerIds"] = ["pubmed"]
        self.desk.apply_bioprint_import(bundle)
        request = {"queryId": bundle["queries"][0]["id"], "blueprintId": self.desk.store["blueprints"][0]["id"]}
        review = self.desk.preview_bioprint_submission(request)
        request.update(reviewToken=review["reviewToken"], confirmed=True)
        with patch.object(desk_module, "search_provider", return_value=({"fixture": True}, [{
                "title": "Mock bibliography lead", "url": "https://example.invalid/mock", "provider": "pubmed"}])) as provider:
            receipt = self.desk.submit_bioprint_query(request)
            path = self.desk.runs / receipt["deskRunId"] / "run.json"
            deadline = time.monotonic() + 10
            run = {}
            while time.monotonic() < deadline:
                run = json.loads(path.read_text())
                if run["status"] not in {"queued", "running"}:
                    break
                time.sleep(0.01)
            self.assertEqual(run["status"], "complete", run)
            self.assertEqual(provider.call_count, 1)
        with zipfile.ZipFile(io.BytesIO(self.desk.export_bioprint_archive({"deskRunIds": [run["id"]]}))) as archive:
            returned = bx.validate_bundle(json.loads(archive.read("bioprint-results.json")))
            self.assertEqual(returned["modelRuns"][0]["status"], "succeeded")
            artifact = returned["artifacts"][0]
            self.assertEqual(hashlib.sha256(archive.read(artifact["filename"])).hexdigest(), artifact["sha256"])


if __name__ == "__main__":
    unittest.main()
