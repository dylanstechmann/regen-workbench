from __future__ import annotations

import copy
import hashlib
import http.client
import io
import json
import os
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import frozen_evaluation as fe
import regen
import regen_desk as desk

AREA = "tissues"
DATA_SHA = "ab" * 32
COMMIT = "c" * 40


def question_content(**overrides):
    value = {"question": "Does the signal separate treated from control wells?",
             "scope": "Three source wells of one public imaging study.",
             "claim_boundary": "Associations within these wells only.",
             "hypotheses": [{"id": "h1", "prediction": "Treated wells separate.", "falsifier": "No separation."},
                            {"id": "h2", "prediction": "Only density separates.", "falsifier": "Separation persists."}],
             "source_refs": [{"label": "Source", "url": "https://example.org/study"}]}
    value.update(overrides)
    return value


def dataset_content(sha=DATA_SHA, unit="source well", **overrides):
    value = {"citation": "Public dataset", "source_url": "https://example.org/data", "access_status": "public_open",
             "license": "CC0-1.0", "scope": "Feature table.", "species_or_model": "human iPSC",
             "stage_or_interval": "day 3", "data_granularity": "individual_level",
             "files": [{"path": "features.csv", "format": "csv", "sha256": sha, "rows": 192}],
             "unit_hierarchy": [{"level": unit, "kind": "well", "source_field": "source_well",
                                 "identity_status": "reported"}],
             "independent_unit_level": unit,
             "observed_quantities": [{"endpoint": "nuclear fraction", "unit": "fraction",
                                      "measurement_role": "reference", "calibration_status": "documented"}],
             "groups": [{"label": "well", "source_fields": ["source_well"], "role": "grouping"}],
             "missingness": "None reported.", "exclusions": "None."}
    value.update(overrides)
    return value


def plan_content(question_id, dataset_ids, status="proposed_confirmatory", **overrides):
    value = {"question_revision_id": question_id, "dataset_revision_ids": list(dataset_ids),
             "estimand": "Group-level MAE difference from the baseline.",
             "primary_outcome": {"endpoint": "nuclear fraction", "unit": "fraction", "timepoint": "day 3",
                                 "comparator": "training-fold mean", "independent_unit": "source well"},
             "alternatives": [{"hypothesis_id": "h1", "prediction": "Lower error than baseline."},
                              {"hypothesis_id": "h2", "prediction": "No improvement over baseline."}],
             "baseline": "Training-fold mean.", "split": "Leave one well out.",
             "uncertainty": "Group bootstrap.", "missingness_rule": "Exclude missing tiles.",
             "confounding": "Well density.", "falsification_rule": "No improvement.",
             "ambiguity_rule": "Report both.", "analysis_status": status}
    value.update(overrides)
    return value


def freeze_request(plan_id, **overrides):
    value = {"plan_revision_id": plan_id,
             "method": {"owner_repository": "regen-benchmark-kit", "revision": COMMIT, "version": "0.2.0",
                        "entry_point": "regenbench regress features.csv", "preprocessing": "fold-local scaling",
                        "parameters": "seed 0"},
             "split": {"grouping_unit": "source well", "development_group_ids": ["well-a", "well-b"],
                       "final_test_group_ids": ["well-c"]},
             "primary_metric": {"name": "equal_group_mae", "direction": "lower_is_better",
                                "baseline": "mean_baseline"},
             "results_inspected_before_freeze": False, "inspection_statement": ""}
    value.update(overrides)
    return value


def generic_receipt(**overrides):
    value = {"schema": "regen-workbench/evaluation-receipt/1",
             "producer": {"tool": "t", "version": "0.2.0", "code_revision": COMMIT},
             "created_utc": "2999-01-01T00:00:00+00:00", "input_sha256": [DATA_SHA],
             "folds": [{"train_groups": ["well-a", "well-b"], "test_groups": ["well-c"]}],
             "model_names": ["mean_baseline", "ridge"], "metric_names": ["equal_group_mae"],
             "reported_leakage": [{"id": "unblocked_overlap:batch_id", "count": 0}]}
    value.update(overrides)
    return value


class StudyRecordCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, value in (("DATA", self.root / "data"), ("CACHE", self.root / "cache"),
                            ("PROV", self.root / "provenance")):
            patcher = patch.object(regen, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        (self.root / "data").mkdir()
        self.desk = desk.Desk(self.root / "desk")
        self.addCleanup(lambda: self.desk.executor.shutdown(wait=True))

    def save(self, record_type, title, content, **extra):
        return self.desk.research_record({"record_type": record_type, "blueprint_id": AREA, "title": title,
                                          "content": content, **extra})

    def revise(self, record, content):
        return self.save(record["record_type"], record["title"], content, family_id=record["family_id"],
                         supersedes_revision_id=record["revision_id"])

    def foundation(self, status="proposed_confirmatory", sha=DATA_SHA):
        question = self.save("question", "Separation question", question_content())
        card = self.save("dataset_card", "Feature table", dataset_content(sha=sha))
        plan = self.save("analysis_plan", "Frozen comparison",
                         plan_content(question["revision_id"], [card["revision_id"]], status))
        return question, card, plan

    def freeze(self, plan, **overrides):
        return self.save("plan_freeze", "Freeze", freeze_request(plan["revision_id"], **overrides))

    def state(self):
        return {item["revision_id"]: item for item in self.desk.research_record_state(AREA)}

    def write_receipt(self, name="receipt.json", value=None):
        directory = self.root / "data" / "receipts"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_bytes(json.dumps(value if value is not None else generic_receipt()).encode())
        return path

    def bind(self, freeze, path, stage="final_test", adapter="evaluation-receipt/1"):
        return self.save("evaluation_binding", "Binding", {
            "freeze_revision_id": freeze["revision_id"], "adapter": adapter, "stage": stage,
            "receipt_path": str(path)})

    def record_access(self, freeze, scope="development", action="evaluate", **extra):
        return self.save("holdout_access", "Access", {
            "freeze_revision_id": freeze["revision_id"], "scope": scope, "action": action,
            "actor": "agent: test", "reference": "", "note": "", **extra})


class ExistingStudyDesignTests(StudyRecordCase):
    """The layer the freeze builds on had no tests when it shipped."""

    def test_records_are_hash_addressed_and_start_as_drafts(self):
        record = self.save("question", "Q", question_content())
        self.assertEqual(record["revision_number"], 1)
        self.assertEqual(record["record_state"], "draft")
        self.assertEqual(record["content_sha256"], desk.research_record_hash("question", "Q", record["content"]))
        self.assertEqual(record["content_sha256"], fe.record_hash("question", "Q", record["content"]))
        self.assertFalse(record["source_urls_fetched"])

    def test_question_validation_rejects_weak_or_malformed_content(self):
        cases = {
            "one hypothesis": question_content(hypotheses=question_content()["hypotheses"][:1]),
            "duplicate hypothesis ids": question_content(hypotheses=[
                {"id": "h1", "prediction": "a", "falsifier": "b"}, {"id": "h1", "prediction": "c", "falsifier": "d"}]),
            "upper-case hypothesis id": question_content(hypotheses=[
                {"id": "H1", "prediction": "a", "falsifier": "b"}, {"id": "h2", "prediction": "c", "falsifier": "d"}]),
            "non-http citation": question_content(source_refs=[{"label": "x", "url": "ftp://example.org"}]),
            "credentials in citation": question_content(source_refs=[{"label": "x", "url": "https://u:p@example.org"}]),
            "blank question": question_content(question="  "),
        }
        for label, content in cases.items():
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    self.save("question", "Q", content)
        extra = question_content()
        extra["confirmed"] = True
        with self.assertRaisesRegex(ValueError, "exactly its documented fields"):
            self.save("question", "Q", extra)

    def test_dataset_cards_reject_unsafe_paths_and_unidentified_units(self):
        for path in ("/etc/passwd", "../outside.csv", "C:\\data.csv", "a/../b.csv", "a//b.csv"):
            with self.subTest(path=path):
                content = dataset_content()
                content["files"][0]["path"] = path
                with self.assertRaises(ValueError):
                    self.save("dataset_card", "D", content)
        duplicate = dataset_content()
        duplicate["files"].append(dict(duplicate["files"][0]))
        with self.assertRaisesRegex(ValueError, "unique"):
            self.save("dataset_card", "D", duplicate)
        with self.assertRaisesRegex(ValueError, "sha256 must be 64"):
            self.save("dataset_card", "D", dataset_content(sha="not-a-hash"))
        with self.assertRaisesRegex(ValueError, "declared hierarchy level"):
            self.save("dataset_card", "D", dataset_content(independent_unit_level="donor"))

    def test_gap_list_names_what_is_missing_without_scoring_eligibility(self):
        gappy = self.save("dataset_card", "D", dataset_content(
            sha=None, data_granularity="unknown", access_status="request_required",
            species_or_model="", missingness="", exclusions="", observed_quantities=[], groups=[]))
        gaps = " ".join(gappy["data_qualification_gaps"])
        for expected in ("Species or model", "Individual-record availability", "Public file access",
                         "SHA-256 is missing", "No observed endpoint", "No source-defined comparison groups",
                         "Missingness has not been described", "Exclusions have not been described"):
            self.assertIn(expected, gaps)
        self.assertEqual(self.save("dataset_card", "D2", dataset_content())["data_qualification_gaps"], [])

    def test_revisions_must_extend_the_current_family_head(self):
        first = self.save("question", "Q", question_content())
        second = self.revise(first, question_content(scope="Narrowed scope."))
        self.assertEqual((second["revision_number"], second["family_id"]), (2, first["family_id"]))
        with self.assertRaisesRegex(ValueError, "current family revision"):
            self.save("question", "Q", question_content(), family_id=first["family_id"],
                      supersedes_revision_id=first["revision_id"])
        with self.assertRaisesRegex(ValueError, "unrelated revision"):
            self.save("question", "Q", question_content(), supersedes_revision_id=first["revision_id"])
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.save("dataset_card", "D", dataset_content(), family_id=first["family_id"],
                      supersedes_revision_id=second["revision_id"])
        state = self.state()
        self.assertFalse(state[first["revision_id"]]["is_current_revision"])
        self.assertTrue(state[second["revision_id"]]["is_current_revision"])

    def test_plans_must_link_saved_revisions_and_known_hypotheses(self):
        question, card, _plan = self.foundation()
        bad_hypothesis = plan_content(question["revision_id"], [card["revision_id"]])
        bad_hypothesis["alternatives"][0]["hypothesis_id"] = "h9"
        with self.assertRaisesRegex(ValueError, "hypothesis IDs from the linked question"):
            self.save("analysis_plan", "P", bad_hypothesis)
        with self.assertRaisesRegex(ValueError, "saved question revision"):
            self.save("analysis_plan", "P", plan_content("0" * 32, [card["revision_id"]]))
        with self.assertRaisesRegex(ValueError, "saved dataset-card revisions"):
            self.save("analysis_plan", "P", plan_content(question["revision_id"], ["0" * 32]))
        with self.assertRaisesRegex(ValueError, "1-20 unique"):
            self.save("analysis_plan", "P", plan_content(question["revision_id"],
                                                         [card["revision_id"], card["revision_id"]]))
        with self.assertRaisesRegex(ValueError, "analysis status"):
            self.save("analysis_plan", "P", plan_content(question["revision_id"], [card["revision_id"]],
                                                         status="confirmed"))

    def test_a_superseded_input_marks_the_dependent_plan_stale(self):
        question, card, plan = self.foundation()
        self.assertEqual(self.state()[plan["revision_id"]]["stale_dependency_revision_ids"], [])
        newer = self.revise(card, dataset_content(sha="cd" * 32))
        state = self.state()
        self.assertEqual(state[plan["revision_id"]]["stale_dependency_revision_ids"], [card["revision_id"]])
        self.assertEqual(state[plan["revision_id"]]["dependency_revision_ids"],
                         [question["revision_id"], card["revision_id"]])
        self.assertTrue(state[newer["revision_id"]]["is_current_revision"])

    def test_tampered_stored_content_is_flagged_and_blocks_further_revisions(self):
        record = self.save("question", "Q", question_content())
        stored = next(item for item in self.desk.store["research_records"] if item["revision_id"] == record["revision_id"])
        stored["content"]["scope"] = "edited outside the Desk"
        flagged = self.state()[record["revision_id"]]
        self.assertFalse(flagged["content_integrity_valid"])
        with self.assertRaisesRegex(ValueError, "failed its content hash check"):
            self.revise(record, question_content(scope="honest revision"))

    def test_size_and_blueprint_guards(self):
        with self.assertRaisesRegex(ValueError, "Unknown research area"):
            self.desk.research_record({"record_type": "question", "blueprint_id": "no-such-area",
                                       "title": "Q", "content": question_content()})
        with self.assertRaisesRegex(ValueError, "Unknown research record type"):
            self.desk.research_record({"record_type": "result", "blueprint_id": AREA, "title": "Q",
                                       "content": {}})
        huge = question_content(scope="x" * 3000)
        huge["source_refs"] = [{"label": "l" * 400, "url": "https://example.org/" + "a" * 900}] * 40
        with self.assertRaisesRegex(ValueError, "32 KB"):
            self.save("question", "Q", huge)


class FrozenPlanDeskTests(StudyRecordCase):
    def test_full_lifecycle_from_freeze_to_a_supported_procedural_claim(self):
        _question, card, plan = self.foundation()
        freeze = self.freeze(plan)
        self.assertEqual((freeze["record_state"], freeze["content"]["freeze_status"]), ("frozen", "confirmatory"))
        self.assertEqual(freeze["content"]["pins"]["plan"]["content_sha256"], plan["content_sha256"])
        self.assertEqual(freeze["content"]["pins"]["datasets"][0]["files"][0]["sha256"], DATA_SHA)
        self.assertEqual(freeze["dependency_revision_ids"][0], plan["revision_id"])

        sealed = self.state()[freeze["revision_id"]]["freeze_assessment"]
        self.assertEqual(sealed["claim_status"], "holdout_sealed")
        first = self.record_access(freeze, "development", "tune")
        second = self.record_access(freeze, "final_test", "evaluate", reference="run-1")
        self.assertEqual((first["content"]["sequence"], first["content"]["previous_event_sha256"]), (1, None))
        self.assertEqual(second["content"]["previous_event_sha256"], first["content_sha256"])

        path = self.write_receipt()
        binding = self.bind(freeze, path)
        self.assertEqual(binding["content"]["binding_status"], "bound_prospective")
        self.assertEqual(binding["content"]["receipt"]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertNotIn(str(self.root), json.dumps(binding["content"]))

        record = self.state()[freeze["revision_id"]]
        assessment = record["freeze_assessment"]
        self.assertEqual(assessment["claim_status"], "single_final_evaluation_recorded")
        self.assertTrue(assessment["record_supports_confirmatory_claim"])
        self.assertEqual(assessment["ledger"]["head_sha256"], second["content_sha256"])
        self.assertTrue(record["pins_resolve"]["all_resolve"])
        self.assertTrue(record["content_integrity_valid"])

    def test_a_confirmatory_plan_is_downgraded_with_reasons_rather_than_refused(self):
        _question, _card, plan = self.foundation(sha=None)
        freeze = self.freeze(plan)
        self.assertEqual(freeze["content"]["freeze_status"], "exploratory")
        self.assertTrue(any("no SHA-256" in item for item in freeze["content"]["confirmatory_blockers"]))
        inspected = self.freeze(plan, results_inspected_before_freeze=True,
                                inspection_statement="Already looked at the pooled metrics.")
        self.assertEqual(inspected["content"]["freeze_status"], "retrospective")
        self.assertEqual(self.state()[inspected["revision_id"]]["freeze_assessment"]["claim_status"],
                         "retrospective_not_confirmatory")

    def test_only_the_current_plan_with_current_inputs_can_be_frozen(self):
        question, card, plan = self.foundation()
        newer_plan = self.revise(plan, plan_content(question["revision_id"], [card["revision_id"]],
                                                    estimand="A narrower estimand."))
        with self.assertRaisesRegex(ValueError, "superseded by a newer revision"):
            self.freeze(plan)
        self.revise(card, dataset_content(sha="cd" * 32))
        with self.assertRaisesRegex(ValueError, "superseded; create a new plan"):
            self.freeze(newer_plan)
        with self.assertRaisesRegex(ValueError, "saved analysis-plan revision"):
            self.freeze({"revision_id": question["revision_id"]})
        with self.assertRaisesRegex(ValueError, "saved analysis-plan revision"):
            self.freeze({"revision_id": "0" * 32})

    def test_freezes_events_and_bindings_are_append_only(self):
        _question, _card, plan = self.foundation()
        freeze = self.freeze(plan)
        with self.assertRaisesRegex(ValueError, "append-only"):
            self.save("plan_freeze", "Freeze", freeze_request(plan["revision_id"]),
                      family_id=freeze["family_id"], supersedes_revision_id=freeze["revision_id"])
        with self.assertRaisesRegex(ValueError, "append-only"):
            self.save("holdout_access", "A", {}, supersedes_revision_id=freeze["revision_id"])
        for bad in ({"freeze_revision_id": plan["revision_id"], "scope": "development", "action": "evaluate",
                     "actor": "a", "reference": "", "note": ""},
                    {"freeze_revision_id": "0" * 32, "scope": "development", "action": "evaluate",
                     "actor": "a", "reference": "", "note": ""}):
            with self.subTest(bad=bad["freeze_revision_id"][:4]):
                with self.assertRaisesRegex(ValueError, "saved plan freeze"):
                    self.save("holdout_access", "A", bad)

    def test_a_forged_ledger_is_detected_and_refuses_further_events(self):
        _question, _card, plan = self.foundation()
        freeze = self.freeze(plan)
        self.record_access(freeze, "development", "evaluate")
        second = self.record_access(freeze, "development", "tune")
        self.record_access(freeze, "final_test", "evaluate")
        stored = next(item for item in self.desk.store["research_records"]
                      if item["revision_id"] == second["revision_id"])
        self.desk.store["research_records"].remove(stored)
        record = self.state()[freeze["revision_id"]]
        self.assertEqual(record["freeze_assessment"]["claim_status"], "ledger_integrity_failed")
        self.assertFalse(record["freeze_assessment"]["ledger"]["chain_valid"])
        with self.assertRaisesRegex(ValueError, "failed its integrity check"):
            self.record_access(freeze, "development", "evaluate")

    def test_retuning_after_the_holdout_was_opened_is_recorded_not_blocked(self):
        _question, _card, plan = self.foundation()
        freeze = self.freeze(plan)
        self.record_access(freeze, "final_test", "evaluate")
        self.record_access(freeze, "development", "tune")
        assessment = self.state()[freeze["revision_id"]]["freeze_assessment"]
        self.assertEqual(assessment["claim_status"], "holdout_compromised")
        self.assertIn("tuned_after_final_test_opened", {item["id"] for item in assessment["violations"]})
        self.assertFalse(assessment["record_supports_confirmatory_claim"])

    def test_stale_expected_head_and_unsealed_final_test_are_refused(self):
        _question, _card, plan = self.foundation()
        freeze = self.freeze(plan)
        self.record_access(freeze)
        with self.assertRaisesRegex(ValueError, "ledger head changed"):
            self.record_access(freeze, expected_previous_event_sha256="0" * 64)
        open_plan = self.freeze(plan, split={"grouping_unit": "source well",
                                             "development_group_ids": ["well-a"], "final_test_group_ids": []})
        with self.assertRaisesRegex(ValueError, "seals no final-test groups"):
            self.record_access(open_plan, "final_test", "evaluate")

    def test_a_later_plan_revision_does_not_disturb_an_existing_freeze(self):
        question, card, plan = self.foundation()
        freeze = self.freeze(plan)
        self.revise(plan, plan_content(question["revision_id"], [card["revision_id"]], estimand="Changed after."))
        record = self.state()[freeze["revision_id"]]
        self.assertTrue(record["pins_resolve"]["all_resolve"])
        self.assertTrue(record["pins_resolve"]["plan_superseded_since_freeze"])
        self.assertEqual(record["stale_dependency_revision_ids"], [])
        stored = next(item for item in self.desk.store["research_records"] if item["revision_id"] == plan["revision_id"])
        stored["content"]["estimand"] = "rewritten in place"
        changed = self.state()[freeze["revision_id"]]["pins_resolve"]
        self.assertFalse(changed["all_resolve"])
        self.assertEqual(changed["changed_revision_ids"], [plan["revision_id"]])

    def test_receipt_paths_are_contained_and_read_once(self):
        _question, _card, plan = self.foundation()
        freeze = self.freeze(plan)
        outside = self.root / "outside.json"
        outside.write_text(json.dumps(generic_receipt()))
        for bad in (outside, "../outside.json", "/etc/hostname", self.root / "data" / "missing.json"):
            with self.subTest(bad=str(bad)):
                with self.assertRaises(ValueError):
                    self.bind(freeze, bad)
        wrong_suffix = self.root / "data" / "receipt.txt"
        wrong_suffix.write_text(json.dumps(generic_receipt()))
        with self.assertRaisesRegex(ValueError, r"\.json"):
            self.bind(freeze, wrong_suffix)
        big = self.root / "data" / "big.json"
        big.write_bytes(b"{" + b" " * fe.MAX_RECEIPT_BYTES + b"}")
        with self.assertRaisesRegex(ValueError, "between 1 byte"):
            self.bind(freeze, big)
        link = self.root / "data" / "link.json"
        try:
            link.symlink_to(self.write_receipt())
        except (OSError, NotImplementedError):
            self.skipTest("this platform does not permit creating test symlinks")
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            self.bind(freeze, link)

    def test_rebinding_the_same_receipt_is_refused_but_other_stages_are_allowed(self):
        _question, _card, plan = self.foundation()
        freeze = self.freeze(plan)
        path = self.write_receipt()
        self.bind(freeze, path)
        with self.assertRaisesRegex(ValueError, "already bound"):
            self.bind(freeze, path)
        other_stage = self.bind(freeze, path, stage="development")
        self.assertEqual(other_stage["content"]["stage"], "development")

    def test_dossier_carries_freeze_state_and_the_exact_records(self):
        _question, _card, plan = self.foundation()
        freeze = self.freeze(plan)
        self.record_access(freeze, "final_test", "evaluate")
        self.bind(freeze, self.write_receipt())
        dossier = self.desk.export(AREA)
        self.assertIn("Freeze status confirmatory", dossier["markdown"])
        self.assertIn("claim state single_final_evaluation_recorded", dossier["markdown"])
        self.assertIn("procedural bookkeeping, not a result or a review", dossier["markdown"])
        self.assertIn("Binding bound_prospective at the final_test stage", dossier["markdown"])
        archive = zipfile.ZipFile(io.BytesIO(self.desk.export_archive(AREA)))
        records = json.loads(archive.read("research_records.json"))["records"]
        types = sorted(item["record_type"] for item in records)
        self.assertEqual(types, ["analysis_plan", "dataset_card", "evaluation_binding", "holdout_access",
                                 "plan_freeze", "question"])
        stored = next(item for item in records if item["record_type"] == "plan_freeze")
        self.assertIn("freeze_assessment", stored)
        self.assertEqual(stored["content_sha256"], fe.record_hash("plan_freeze", stored["title"], stored["content"]))


class FrozenPlanHttpTests(StudyRecordCase):
    def serve(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), desk.make_handler(self.desk))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(5)))
        return server.server_address[1]

    def request(self, port, method, path, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        headers = {"Content-Type": "application/json", "Host": f"127.0.0.1:{port}"}
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        return response.status, payload

    def test_http_round_trip_exposes_the_derived_assessment(self):
        _question, _card, plan = self.foundation()
        port = self.serve()
        status, freeze = self.request(port, "POST", "/api/research-records", {
            "record_type": "plan_freeze", "blueprint_id": AREA, "title": "Freeze",
            "content": freeze_request(plan["revision_id"])})
        self.assertEqual((status, freeze["record_state"]), (200, "frozen"))
        status, event = self.request(port, "POST", "/api/research-records", {
            "record_type": "holdout_access", "blueprint_id": AREA, "title": "Access",
            "content": {"freeze_revision_id": freeze["revision_id"], "scope": "development",
                        "action": "evaluate", "actor": "agent: http", "reference": "", "note": ""}})
        self.assertEqual((status, event["content"]["sequence"]), (200, 1))
        status, page = self.request(port, "GET", f"/api/research-records?blueprint_id={AREA}&limit=20")
        listed = next(item for item in page["records"] if item["record_type"] == "plan_freeze")
        self.assertEqual(status, 200)
        self.assertEqual(listed["freeze_assessment"]["claim_status"], "holdout_sealed")
        self.assertEqual(listed["freeze_assessment"]["ledger"]["n_events"], 1)

    def test_http_rejects_client_asserted_status_and_reports_the_reason(self):
        _question, _card, plan = self.foundation()
        port = self.serve()
        forged = freeze_request(plan["revision_id"])
        forged["freeze_status"] = "confirmatory"
        status, payload = self.request(port, "POST", "/api/research-records", {
            "record_type": "plan_freeze", "blueprint_id": AREA, "title": "Freeze", "content": forged})
        self.assertEqual(status, 400)
        self.assertIn("exactly its documented fields", payload["error"])
        status, payload = self.request(port, "POST", "/api/research-records", {
            "record_type": "evaluation_binding", "blueprint_id": AREA, "title": "B",
            "content": {"freeze_revision_id": "0" * 32, "adapter": "regenbench-metrics/1",
                        "stage": "development", "receipt_path": "/etc/passwd"}})
        self.assertEqual(status, 400)
        self.assertIn("saved plan freeze", payload["error"])


class PortableLineageTests(StudyRecordCase):
    """A relocated dossier proves its research lineage without the Desk that wrote it."""

    def export_lifecycle(self):
        _question, _card, plan = self.foundation()
        freeze = self.freeze(plan)
        self.record_access(freeze, "development", "tune")
        self.record_access(freeze, "final_test", "evaluate")
        self.bind(freeze, self.write_receipt())
        path = self.root / "dossier.zip"
        path.write_bytes(self.desk.export_archive(AREA))
        return path, freeze

    def rewrite(self, source, mutate, *, fix_inventory=True):
        """Copy an archive, mutating research_records.json; optionally repair the inventory to match."""
        target = self.root / f"edited-{source.stem}.zip"
        with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "w") as edited:
            records = mutate(json.loads(original.read("research_records.json")))
            blob = json.dumps(records, indent=2).encode()
            for name in original.namelist():
                content = original.read(name)
                if name == "research_records.json":
                    content = blob
                elif name == "archive-index.json" and fix_inventory:
                    index = json.loads(content)
                    for row in index["files"]:
                        if row["path"] == "research_records.json":
                            row["sha256"], row["bytes"] = hashlib.sha256(blob).hexdigest(), len(blob)
                    content = json.dumps(index).encode()
                edited.writestr(name, content)
        return target

    def verify(self, path, strict=True):
        import verify_dossier
        return verify_dossier.verify_dossier(path, strict=strict)

    def test_an_exported_lifecycle_verifies_bytes_and_lineage_separately(self):
        path, _freeze = self.export_lifecycle()
        report = self.verify(path)
        self.assertTrue(report["bytes_verified"], report["errors"])
        self.assertTrue(report["verified"])
        self.assertEqual(report["scientific_lineage"], "resolved")
        self.assertEqual(report["scientific_review"], "not_established_by_this_tool")
        row = report["lineage"]["freezes"][0]
        self.assertEqual((row["pins_resolve"], row["ledger_chain_valid"], row["claim_status_matches_export"]),
                         (True, True, True))
        self.assertEqual(row["claim_status"], "single_final_evaluation_recorded")
        self.assertEqual(report["lineage"]["n_records"], 7)

    def test_content_edited_with_a_repaired_inventory_passes_bytes_but_not_lineage(self):
        path, _freeze = self.export_lifecycle()

        def edit_plan(payload):
            plan = next(item for item in payload["records"] if item["record_type"] == "analysis_plan")
            plan["content"]["estimand"] = "A different estimand, edited after the freeze."
            return payload

        edited = self.rewrite(path, edit_plan)
        report = self.verify(edited, strict=True)
        self.assertTrue(report["bytes_verified"], report["errors"])
        self.assertEqual(report["scientific_lineage"], "unresolved")
        self.assertFalse(report["verified"])
        problems = " ".join(report["lineage"]["problems"])
        self.assertIn("does not hash to its declared content_sha256", problems)
        self.assertIn("archived content differs from the pinned hash", problems)
        lenient = self.verify(edited, strict=False)
        self.assertTrue(lenient["verified"])
        self.assertEqual(lenient["scientific_lineage"], "unresolved")

    def test_a_removed_ledger_event_breaks_the_recomputed_chain(self):
        path, _freeze = self.export_lifecycle()

        def drop_first_event(payload):
            events = [item for item in payload["records"] if item["record_type"] == "holdout_access"]
            payload["records"].remove(min(events, key=lambda item: item["content"]["sequence"]))
            return payload

        report = self.verify(self.rewrite(path, drop_first_event))
        self.assertEqual(report["scientific_lineage"], "unresolved")
        self.assertTrue(any("ledger" in item for item in report["lineage"]["problems"]))
        self.assertFalse(report["lineage"]["freezes"][0]["ledger_chain_valid"])

    def test_a_flattering_exported_claim_state_is_recomputed_not_trusted(self):
        path, _freeze = self.export_lifecycle()

        def forge_claim(payload):
            for item in payload["records"]:
                if item["record_type"] == "holdout_access" and item["content"]["scope"] == "final_test":
                    payload["records"].remove(item)
                    break
            freeze = next(item for item in payload["records"] if item["record_type"] == "plan_freeze")
            freeze["freeze_assessment"]["claim_status"] = "single_final_evaluation_recorded"
            freeze["freeze_assessment"]["record_supports_confirmatory_claim"] = True
            return payload

        report = self.verify(self.rewrite(path, forge_claim))
        self.assertEqual(report["scientific_lineage"], "unresolved")
        self.assertFalse(report["lineage"]["freezes"][0]["claim_status_matches_export"])

    def test_a_missing_pinned_revision_is_reported_by_name(self):
        path, _freeze = self.export_lifecycle()

        def drop_question(payload):
            payload["records"] = [item for item in payload["records"] if item["record_type"] != "question"]
            return payload

        report = self.verify(self.rewrite(path, drop_question))
        self.assertTrue(any("question" in item and "absent from the archive" in item
                            for item in report["lineage"]["problems"]), report["lineage"]["problems"])

    def test_without_the_sibling_module_lineage_is_not_checked_rather_than_passed(self):
        import verify_dossier
        path, _freeze = self.export_lifecycle()
        with patch.object(verify_dossier, "_fe", None):
            report = verify_dossier.verify_dossier(path, strict=True)
        self.assertEqual(report["scientific_lineage"], "not_checked")
        self.assertTrue(report["bytes_verified"])
        self.assertTrue(any("frozen_evaluation.py was not found" in item for item in report["warnings"]))

    def test_a_dossier_with_no_research_records_has_no_lineage_to_check(self):
        import verify_dossier
        path = self.root / "empty.zip"
        path.write_bytes(self.desk.export_archive(AREA))
        report = verify_dossier.verify_dossier(path, strict=True)
        self.assertEqual(report["scientific_lineage"], "no_research_records")
        self.assertTrue(report["verified"], report["errors"])


if __name__ == "__main__":
    unittest.main()
