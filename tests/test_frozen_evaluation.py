from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import frozen_evaluation as fe  # noqa: E402

FROZEN_AT = "2026-10-07T12:00:00+00:00"
BEFORE_FREEZE = "2026-10-07T11:00:00+00:00"
AFTER_FREEZE = "2026-10-07T13:00:00+00:00"
COMMIT = "a" * 40
DATA_SHA = "b" * 64
PLAN_SHA = "c" * 64
PLAN_ID = "0a" * 16
QUESTION_ID = "0b" * 16
DATASET_ID = "0d" * 16
FREEZE_ID = "0f" * 16


def stored(record_type, title, content, revision_id, *, current=True, stale=()):
    record = {"record_type": record_type, "title": title, "content": content, "revision_id": revision_id,
              "content_sha256": fe.record_hash(record_type, title, content), "created_utc": FROZEN_AT,
              "is_current_revision": current, "stale_dependency_revision_ids": list(stale),
              "content_integrity_valid": True}
    return record


def question():
    return stored("question", "Does X separate from Y?", {"question": "q", "hypotheses": []}, QUESTION_ID)


def dataset(sha=DATA_SHA, unit="source well", reported=True, revision=DATASET_ID):
    return stored("dataset_card", "Feature table", {
        "independent_unit_level": unit,
        "unit_hierarchy": [{"level": unit, "kind": "well", "source_field": "source_well",
                            "identity_status": "reported" if reported else "not_reported"}],
        "files": [{"path": "features.csv", "format": "csv", "sha256": sha, "rows": 192}]}, revision)


def plan(status="proposed_confirmatory", **kwargs):
    return stored("analysis_plan", "Frozen comparison", {
        "question_revision_id": QUESTION_ID, "dataset_revision_ids": [DATASET_ID],
        "analysis_status": status}, PLAN_ID, **kwargs)


def request(**overrides):
    value = {
        "plan_revision_id": PLAN_ID,
        "method": {"owner_repository": "regen-benchmark-kit", "revision": COMMIT, "version": "0.2.0",
                   "entry_point": "regenbench regress features.csv --group-by source_well",
                   "preprocessing": "none beyond fold-local scaling", "parameters": "seed 0"},
        "split": {"grouping_unit": "source well", "development_group_ids": ["well-a", "well-b"],
                  "final_test_group_ids": ["well-c"]},
        "primary_metric": {"name": "equal_group_mae", "direction": "lower_is_better",
                           "baseline": "mean_baseline"},
        "results_inspected_before_freeze": False, "inspection_statement": ""}
    value.update(overrides)
    return fe.validate_freeze_request(value)


def freeze_record(req=None, *, plan_record=None, datasets=None, revision=FREEZE_ID):
    content = fe.build_freeze_content(req or request(), plan=plan_record or plan(), question=question(),
                                      datasets=datasets or [dataset()], frozen_utc=FROZEN_AT)
    fe.validate_freeze_content(content)
    return stored("plan_freeze", "Freeze", content, revision)


def event(freeze, sequence, previous, scope="development", action="evaluate", **overrides):
    content = {"freeze_revision_id": freeze["revision_id"], "freeze_content_sha256": freeze["content_sha256"],
               "sequence": sequence, "previous_event_sha256": previous, "scope": scope, "action": action,
               "actor": "agent: test", "reference": "", "note": "", "recorded_utc": AFTER_FREEZE}
    content.update(overrides)
    return stored("holdout_access", f"event {sequence}", content, f"{sequence:032x}")


def chain(freeze, *specs):
    events, previous = [], None
    for number, (scope, action) in enumerate(specs, start=1):
        item = event(freeze, number, previous, scope, action)
        events.append(item)
        previous = item["content_sha256"]
    return events


def regenbench_receipt(groups=("well-a", "well-b"), tests=None, dataset_sha=DATA_SHA, overlap=0):
    pseudonyms = {name: f"group-{index:06d}" for index, name in enumerate(groups)}
    tests = tests or [[name] for name in groups]
    folds = [{"fold": index, "train_groups": [pseudonyms[g] for g in groups if g not in test],
              "test_groups": [pseudonyms[g] for g in test]} for index, test in enumerate(tests)]
    model = {"mae": 0.1, "rmse": 0.2, "r2": 0.5, "mean_signed_error": 0.0, "equal_group_mae": 0.1,
             "per_group": {}}
    return {"schema_version": 1, "task": "regression", "dataset_sha256": dataset_sha,
            "group_metadata": {pseudonyms[g]: {"source_well": [g]} for g in groups},
            "configuration": {"group_by": ["source_well"], "seed": 0, "split": "leave_one_group_out"},
            "environment": {"regenbench": "0.2.0"}, "folds": folds,
            "models": {"mean_baseline": dict(model), "ridge": dict(model)},
            "unblocked_overlap_counts": {"batch_id": [overlap] * len(folds)}}


def generic_receipt(**overrides):
    value = {"schema": "regen-workbench/evaluation-receipt/1",
             "producer": {"tool": "t", "version": "0.2.0", "code_revision": COMMIT},
             "created_utc": AFTER_FREEZE, "input_sha256": [DATA_SHA],
             "folds": [{"train_groups": ["well-a", "well-b"], "test_groups": ["well-c"]}],
             "model_names": ["mean_baseline", "ridge"], "metric_names": ["equal_group_mae"],
             "reported_leakage": [{"id": "unblocked_overlap:batch_id", "count": 0}]}
    value.update(overrides)
    return value


class FreezeTests(unittest.TestCase):
    def test_confirmatory_requires_every_gate(self):
        record = freeze_record()
        content = record["content"]
        self.assertEqual(content["freeze_status"], "confirmatory")
        self.assertEqual(content["confirmatory_blockers"], [])
        self.assertEqual(content["pins"]["plan"]["content_sha256"], plan()["content_sha256"])
        self.assertEqual(content["pins"]["datasets"][0]["files"][0]["sha256"], DATA_SHA)
        self.assertTrue(fe.SHA256_HEX.fullmatch(content["split"]["split_sha256"]))

    def test_each_missing_gate_blocks_confirmatory_and_says_why(self):
        cases = {
            "No final-test groups are sealed": request(split={
                "grouping_unit": "source well", "development_group_ids": ["well-a"], "final_test_group_ids": []}),
            "method revision is not pinned": request(method={
                "owner_repository": "r", "revision": "", "version": "0.2.0", "entry_point": "e",
                "preprocessing": "p", "parameters": "s"}),
        }
        for expected, req in cases.items():
            with self.subTest(expected=expected):
                content = freeze_record(req)["content"]
                self.assertEqual(content["freeze_status"], "exploratory")
                self.assertTrue(any(expected in item for item in content["confirmatory_blockers"]))
        unhashed = freeze_record(datasets=[dataset(sha=None)])["content"]
        self.assertEqual(unhashed["freeze_status"], "exploratory")
        self.assertTrue(any("no SHA-256" in item for item in unhashed["confirmatory_blockers"]))
        wrong_unit = freeze_record(datasets=[dataset(unit="culture")])["content"]
        self.assertTrue(any("independent-unit level" in item for item in wrong_unit["confirmatory_blockers"]))
        unidentified = freeze_record(datasets=[dataset(reported=False)])["content"]
        self.assertEqual(unidentified["freeze_status"], "exploratory")

    def test_an_exploratory_plan_never_becomes_confirmatory(self):
        content = freeze_record(plan_record=plan(status="exploratory"))["content"]
        self.assertEqual(content["freeze_status"], "exploratory")
        self.assertEqual(content["confirmatory_blockers"], [])

    def test_inspected_results_make_the_freeze_retrospective(self):
        content = freeze_record(request(results_inspected_before_freeze=True,
                                        inspection_statement="Ran the pipeline once before writing this plan."))["content"]
        self.assertEqual(content["freeze_status"], "retrospective")
        self.assertTrue(any("inspected" in item for item in content["confirmatory_blockers"]))
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "Inspection statement"):
            request(results_inspected_before_freeze=True, inspection_statement="")

    def test_only_the_current_unstale_plan_can_be_frozen(self):
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "superseded by a newer revision"):
            freeze_record(plan_record=plan(current=False))
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "superseded; create a new plan"):
            freeze_record(plan_record=plan(stale=[DATASET_ID]))
        tampered = plan()
        tampered["content"]["estimand"] = "edited after saving"
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "plan revision failed its content hash"):
            freeze_record(plan_record=tampered)
        other = copy.deepcopy(question())
        other["record_type"] = "dataset_card"
        with self.assertRaises(fe.FrozenEvaluationError):
            fe.build_freeze_content(request(), plan=other, question=question(), datasets=[dataset()],
                                    frozen_utc=FROZEN_AT)
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "Every dataset-card revision"):
            freeze_record(datasets=[dataset(revision="e" * 32)])

    def test_split_validation_and_canonical_hash(self):
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "both development and final-test"):
            request(split={"grouping_unit": "w", "development_group_ids": ["x", "y"],
                           "final_test_group_ids": ["y"]})
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "must not repeat"):
            request(split={"grouping_unit": "w", "development_group_ids": ["x", "x"],
                           "final_test_group_ids": []})
        with self.assertRaises(fe.FrozenEvaluationError):
            request(split={"grouping_unit": "w", "development_group_ids": [], "final_test_group_ids": []})
        forward = request(split={"grouping_unit": "w", "development_group_ids": ["a", "b"],
                                 "final_test_group_ids": ["c", "d"]})
        backward = request(split={"grouping_unit": "w", "development_group_ids": ["b", "a"],
                                  "final_test_group_ids": ["d", "c"]})
        digests = []
        for req in (forward, backward):
            digests.append(freeze_record(req)["content"]["split"]["split_sha256"])
        self.assertEqual(digests[0], digests[1])

    def test_request_rejects_unknown_fields_bad_commits_and_non_boolean_attestation(self):
        base = {"plan_revision_id": PLAN_ID, "method": request()["method"], "split": request()["split"],
                "primary_metric": request()["primary_metric"],
                "results_inspected_before_freeze": False, "inspection_statement": ""}
        with self.assertRaises(fe.FrozenEvaluationError):
            fe.validate_freeze_request({**base, "confirmatory": True})
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "40-character"):
            request(method={**request()["method"], "revision": "abc123"})
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "true or false"):
            fe.validate_freeze_request({**base, "results_inspected_before_freeze": "no"})
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "metric direction"):
            request(primary_metric={"name": "m", "direction": "sideways", "baseline": "b"})


class LedgerTests(unittest.TestCase):
    def test_events_chain_by_hash_and_sequence(self):
        freeze = freeze_record()
        first = fe.build_access_content(
            fe.validate_access_request({"freeze_revision_id": freeze["revision_id"], "scope": "development",
                                        "action": "evaluate", "actor": "agent", "reference": "", "note": ""}),
            freeze=freeze, events=[], recorded_utc=AFTER_FREEZE)
        self.assertEqual((first["sequence"], first["previous_event_sha256"]), (1, None))
        record = stored("holdout_access", "e1", first, "1" * 32)
        second = fe.build_access_content(
            fe.validate_access_request({"freeze_revision_id": freeze["revision_id"], "scope": "final_test",
                                        "action": "evaluate", "actor": "agent", "reference": "run", "note": ""}),
            freeze=freeze, events=[record], recorded_utc=AFTER_FREEZE)
        self.assertEqual((second["sequence"], second["previous_event_sha256"]), (2, record["content_sha256"]))
        self.assertEqual(fe.ledger_problems(freeze, [record]), [])

    def test_stale_expected_head_is_refused(self):
        freeze = freeze_record()
        events = chain(freeze, ("development", "evaluate"))
        req = fe.validate_access_request({
            "freeze_revision_id": freeze["revision_id"], "scope": "development", "action": "evaluate",
            "actor": "a", "reference": "", "note": "", "expected_previous_event_sha256": "0" * 64})
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "ledger head changed"):
            fe.build_access_content(req, freeze=freeze, events=events, recorded_utc=AFTER_FREEZE)

    def test_tampering_is_detected_and_blocks_appending(self):
        freeze = freeze_record()
        events = chain(freeze, ("development", "evaluate"), ("development", "tune"), ("final_test", "evaluate"))
        self.assertEqual(fe.ledger_problems(freeze, events), [])
        removed = [events[0], events[2]]
        self.assertTrue(any("sequence" in item for item in fe.ledger_problems(freeze, removed)))
        reordered = copy.deepcopy(events)
        reordered[1]["content"]["previous_event_sha256"] = "0" * 64
        self.assertTrue(any("previous event" in item for item in fe.ledger_problems(freeze, reordered)))
        rebound = copy.deepcopy(events)
        rebound[2]["content"]["freeze_content_sha256"] = "0" * 64
        self.assertTrue(any("different freeze" in item for item in fe.ledger_problems(freeze, rebound)))
        flagged = copy.deepcopy(events)
        flagged[0]["content_integrity_valid"] = False
        self.assertTrue(any("hash check" in item for item in fe.ledger_problems(freeze, flagged)))
        req = fe.validate_access_request({"freeze_revision_id": freeze["revision_id"], "scope": "development",
                                          "action": "evaluate", "actor": "a", "reference": "", "note": ""})
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "failed its integrity check"):
            fe.build_access_content(req, freeze=freeze, events=removed, recorded_utc=AFTER_FREEZE)

    def test_final_test_access_needs_sealed_groups(self):
        freeze = freeze_record(request(split={"grouping_unit": "source well",
                                              "development_group_ids": ["well-a"], "final_test_group_ids": []}))
        req = fe.validate_access_request({"freeze_revision_id": freeze["revision_id"], "scope": "final_test",
                                          "action": "evaluate", "actor": "a", "reference": "", "note": ""})
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "seals no final-test groups"):
            fe.build_access_content(req, freeze=freeze, events=[], recorded_utc=AFTER_FREEZE)

    def test_request_validation(self):
        good = {"freeze_revision_id": FREEZE_ID, "scope": "development", "action": "evaluate",
                "actor": "a", "reference": "", "note": ""}
        for bad in ({**good, "scope": "test"}, {**good, "action": "peek"}, {**good, "actor": ""},
                    {**good, "expected_previous_event_sha256": "short"}, {**good, "extra": 1}):
            with self.subTest(bad=bad):
                with self.assertRaises(fe.FrozenEvaluationError):
                    fe.validate_access_request(bad)


class AssessmentTests(unittest.TestCase):
    def binding(self, freeze, stage="final_test", status="bound_prospective", evaluated=("well-c",),
                in_training=()):
        content = {"freeze_revision_id": freeze["revision_id"], "stage": stage, "binding_status": status,
                   "receipt": {"sha256": "9" * 64}, "final_test_groups_evaluated": list(evaluated),
                   "final_test_groups_in_training": list(in_training)}
        return stored("evaluation_binding", "b", content, "9" * 32)

    def assess(self, freeze, specs=(), bindings=()):
        return fe.assess_freeze(freeze, chain(freeze, *specs), list(bindings))

    def test_confirmatory_record_progresses_from_sealed_to_single_evaluation(self):
        freeze = freeze_record()
        self.assertEqual(self.assess(freeze)["claim_status"], "holdout_sealed")
        development = self.assess(freeze, [("development", "evaluate"), ("development", "tune")])
        self.assertEqual(development["claim_status"], "holdout_sealed")
        single = self.assess(freeze, [("development", "tune"), ("final_test", "evaluate")],
                             [self.binding(freeze)])
        self.assertEqual(single["claim_status"], "single_final_evaluation_recorded")
        self.assertTrue(single["record_supports_confirmatory_claim"])
        self.assertEqual(single["violations"], [])
        self.assertTrue(any("not establish that the analysis was correct" in item
                            for item in single["claim_limits"]))

    def test_a_ledger_entry_without_a_verified_receipt_does_not_support_a_claim(self):
        freeze = freeze_record()
        cases = {
            "no receipt bound": [],
            "retrospective binding": [self.binding(freeze, status="bound_retrospective")],
            "timing unverified": [self.binding(freeze, status="bound_timing_unverified")],
            "mismatched binding": [self.binding(freeze, status="mismatch", evaluated=())],
            "development-stage binding": [self.binding(freeze, stage="development", evaluated=())],
        }
        for label, bindings in cases.items():
            with self.subTest(label):
                result = self.assess(freeze, [("final_test", "evaluate")], bindings)
                self.assertEqual(result["claim_status"], "single_final_evaluation_recorded")
                self.assertFalse(result["record_supports_confirmatory_claim"])
        supported = self.assess(freeze, [("final_test", "evaluate")], [self.binding(freeze)])
        self.assertTrue(supported["record_supports_confirmatory_claim"])

    def test_reuse_and_tuning_compromise_the_holdout(self):
        freeze = freeze_record()
        reused = self.assess(freeze, [("final_test", "evaluate"), ("final_test", "evaluate")])
        self.assertEqual(reused["claim_status"], "holdout_reused_not_independent")
        self.assertIn("final_test_reused", {item["id"] for item in reused["violations"]})
        self.assertFalse(reused["record_supports_confirmatory_claim"])

        tuned_on = self.assess(freeze, [("final_test", "tune")])
        self.assertEqual(tuned_on["claim_status"], "holdout_compromised")
        self.assertIn("tuned_on_final_test", {item["id"] for item in tuned_on["violations"]})

        retuned = self.assess(freeze, [("final_test", "evaluate"), ("development", "tune")])
        self.assertEqual(retuned["claim_status"], "holdout_compromised")
        self.assertIn("tuned_after_final_test_opened", {item["id"] for item in retuned["violations"]})

        before = self.assess(freeze, [("development", "tune"), ("final_test", "evaluate")],
                             [self.binding(freeze)])
        self.assertNotIn("tuned_after_final_test_opened", {item["id"] for item in before["violations"]})

    def test_bindings_expose_access_that_was_never_recorded(self):
        freeze = freeze_record()
        unrecorded = self.assess(freeze, [], [self.binding(freeze)])
        self.assertEqual(unrecorded["claim_status"], "holdout_compromised")
        self.assertIn("unrecorded_final_test_evaluation", {item["id"] for item in unrecorded["violations"]})
        leaked = self.assess(freeze, [], [self.binding(freeze, stage="development", status="mismatch",
                                                       evaluated=(), in_training=("well-c",))])
        self.assertIn("final_test_data_used_in_development_run", {item["id"] for item in leaked["violations"]})
        self.assertEqual(leaked["claim_status"], "holdout_compromised")

    def test_exploratory_and_retrospective_freezes_never_claim_confirmation(self):
        exploratory = freeze_record(plan_record=plan(status="exploratory"))
        self.assertEqual(self.assess(exploratory)["claim_status"], "exploratory_only")
        retrospective = freeze_record(request(results_inspected_before_freeze=True,
                                              inspection_statement="Looked at the metrics first."))
        result = self.assess(retrospective, [("final_test", "evaluate")], [self.binding(retrospective)])
        self.assertEqual(result["claim_status"], "retrospective_not_confirmatory")
        self.assertFalse(result["record_supports_confirmatory_claim"])

    def test_a_broken_chain_overrides_every_other_status(self):
        freeze = freeze_record()
        events = chain(freeze, ("development", "evaluate"), ("final_test", "evaluate"))
        events[1]["content"]["previous_event_sha256"] = "0" * 64
        result = fe.assess_freeze(freeze, events, [self.binding(freeze)])
        self.assertEqual(result["claim_status"], "ledger_integrity_failed")
        self.assertFalse(result["ledger"]["chain_valid"])
        self.assertFalse(result["record_supports_confirmatory_claim"])

    def test_malformed_stored_events_do_not_raise(self):
        freeze = freeze_record()
        broken = stored("holdout_access", "bad", {"sequence": 1}, "1" * 32)
        result = fe.assess_freeze(freeze, [broken], [])
        self.assertEqual(result["claim_status"], "ledger_integrity_failed")


class AdapterTests(unittest.TestCase):
    def test_regenbench_groups_use_source_values_not_pseudonyms(self):
        normalized = fe.adapt_regenbench_metrics(regenbench_receipt())
        self.assertEqual(normalized["input_sha256"], [DATA_SHA])
        self.assertEqual(normalized["folds"][0], {"train_groups": ["well-b"], "test_groups": ["well-a"]})
        self.assertEqual(normalized["producer"]["version"], "0.2.0")
        self.assertIn("equal_group_mae", normalized["metric_names"])
        self.assertNotIn("per_group", normalized["metric_names"])
        self.assertEqual(normalized["reported_leakage"], [{"id": "unblocked_overlap:batch_id", "count": 0}])

    def test_regenbench_rejects_foreign_or_inconsistent_documents(self):
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "Not a regenbench"):
            fe.adapt_regenbench_metrics({"task": "regression"})
        broken = regenbench_receipt()
        broken["folds"][0]["test_groups"] = ["group-999999"]
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "missing from group_metadata"):
            fe.adapt_regenbench_metrics(broken)
        bad_hash = regenbench_receipt(dataset_sha="short")
        with self.assertRaisesRegex(fe.FrozenEvaluationError, "not a SHA-256"):
            fe.adapt_regenbench_metrics(bad_hash)

    def test_generic_receipt_contract_is_strict(self):
        normalized = fe.adapt_evaluation_receipt(generic_receipt())
        self.assertEqual(normalized["producer"]["code_revision"], COMMIT)
        for bad in ({"schema": "other"}, {"input_sha256": []}, {"input_sha256": ["nothex"]},
                    {"folds": []}, {"folds": [{"train_groups": ["a"], "test_groups": []}]},
                    {"created_utc": "yesterday"}, {"created_utc": "2026-10-07T12:00:00"},
                    {"producer": {"tool": "t", "version": "1", "code_revision": "abc"}},
                    {"reported_leakage": [{"id": "x", "count": -1}]}):
            with self.subTest(bad=list(bad)):
                with self.assertRaises(fe.FrozenEvaluationError):
                    fe.adapt_evaluation_receipt(generic_receipt(**bad))

    def test_receipt_json_parsing_rejects_ambiguous_documents(self):
        for raw in (b"", b"[1]", b"not json", b'{"a": 1, "a": 2}', b'{"a": NaN}', b"\xff\xfe"):
            with self.subTest(raw=raw):
                with self.assertRaises(fe.FrozenEvaluationError):
                    fe.parse_receipt_json(raw)
        with self.assertRaises(fe.FrozenEvaluationError):
            fe.parse_receipt_json(b"{" + b" " * fe.MAX_RECEIPT_BYTES + b"}")
        self.assertEqual(fe.parse_receipt_json(b'\xef\xbb\xbf{"a": 1}'), {"a": 1})


class BindingTests(unittest.TestCase):
    def evaluate(self, freeze, receipt, adapter="evaluation-receipt/1", stage="final_test"):
        raw = json.dumps(receipt).encode()
        return fe.build_binding_content(
            {"freeze_revision_id": freeze["revision_id"], "adapter": adapter, "stage": stage,
             "receipt_path": "x.json"}, freeze=freeze, receipt_bytes=raw, receipt_name="r.json",
            bound_utc=AFTER_FREEZE)

    def statuses(self, content):
        return {item["id"]: item["status"] for item in content["checks"]}

    def test_a_matching_postdated_final_test_receipt_binds_prospectively(self):
        content = self.evaluate(freeze_record(), generic_receipt())
        self.assertEqual(content["binding_status"], "bound_prospective")
        self.assertEqual(content["final_test_groups_evaluated"], ["well-c"])
        self.assertEqual(content["final_test_groups_in_training"], [])
        self.assertEqual(set(self.statuses(content).values()), {"pass"})
        self.assertEqual(content["receipt"]["bytes"], len(json.dumps(generic_receipt()).encode()))

    def test_final_test_stage_requires_training_on_development_and_testing_on_final(self):
        freeze = freeze_record()
        leaky = generic_receipt(folds=[{"train_groups": ["well-a", "well-c"], "test_groups": ["well-b"]}])
        content = self.evaluate(freeze, leaky)
        self.assertEqual(content["binding_status"], "mismatch")
        self.assertEqual(content["final_test_groups_in_training"], ["well-c"])
        self.assertEqual(self.statuses(content)["final_test_not_in_training"], "fail")
        self.assertEqual(self.statuses(content)["split_matches_freeze"], "fail")

    def test_a_development_run_must_not_touch_the_sealed_groups(self):
        freeze = freeze_record()
        development = generic_receipt(folds=[{"train_groups": ["well-a"], "test_groups": ["well-b"]}])
        self.assertEqual(self.evaluate(freeze, development, stage="development")["binding_status"],
                         "bound_prospective")
        touched = generic_receipt(folds=[{"train_groups": ["well-a"], "test_groups": ["well-c"]}])
        content = self.evaluate(freeze, touched, stage="development")
        self.assertEqual(content["binding_status"], "mismatch")
        self.assertIn("final-test group(s) used in a development run", content["checks"][1]["detail"])

    def test_groups_outside_the_frozen_split_are_a_mismatch(self):
        content = self.evaluate(freeze_record(), generic_receipt(
            folds=[{"train_groups": ["well-a", "well-z"], "test_groups": ["well-c"]}]))
        self.assertEqual(content["binding_status"], "mismatch")
        self.assertIn("well-z", content["checks"][1]["detail"])

    def test_unpinned_inputs_code_and_metric_mismatches_are_reported_separately(self):
        freeze = freeze_record()
        unpinned = self.evaluate(freeze, generic_receipt(input_sha256=["e" * 64]))
        self.assertEqual((unpinned["binding_status"], self.statuses(unpinned)["inputs_pinned"]),
                         ("mismatch", "fail"))
        wrong_code = self.evaluate(freeze, generic_receipt(
            producer={"tool": "t", "version": "0.2.0", "code_revision": "f" * 40}))
        self.assertEqual(self.statuses(wrong_code)["method_revision_matches"], "fail")
        no_metric = self.evaluate(freeze, generic_receipt(metric_names=["rmse"]))
        self.assertEqual(self.statuses(no_metric)["primary_metric_present"], "fail")
        no_baseline = self.evaluate(freeze, generic_receipt(model_names=["ridge"]))
        self.assertIn("baseline", [i for i in no_baseline["checks"] if i["id"] == "primary_metric_present"][0]["detail"])
        overlap = self.evaluate(freeze, generic_receipt(
            reported_leakage=[{"id": "unblocked_overlap:batch_id", "count": 2}]))
        self.assertEqual((overlap["binding_status"], self.statuses(overlap)["producer_reported_overlap"]),
                         ("mismatch", "fail"))

    def test_timing_decides_prospective_versus_retrospective(self):
        freeze = freeze_record()
        early = self.evaluate(freeze, generic_receipt(created_utc=BEFORE_FREEZE))
        self.assertEqual((early["binding_status"], self.statuses(early)["result_postdates_freeze"]),
                         ("bound_retrospective", "fail"))
        undated = self.evaluate(freeze, generic_receipt(created_utc=None))
        self.assertEqual((undated["binding_status"], self.statuses(undated)["result_postdates_freeze"]),
                         ("bound_timing_unverified", "unavailable"))
        retro = freeze_record(request(results_inspected_before_freeze=True, inspection_statement="saw it"))
        self.assertEqual(self.evaluate(retro, generic_receipt())["binding_status"], "bound_retrospective")

    def test_a_receipt_that_shares_nothing_checkable_is_unverifiable(self):
        freeze = freeze_record(request(method={"owner_repository": "r", "revision": "", "version": "",
                                               "entry_point": "e", "preprocessing": "p", "parameters": "s"}))
        receipt = generic_receipt(input_sha256=[DATA_SHA])
        receipt["producer"] = {"tool": "t", "version": "", "code_revision": None}
        receipt["folds"] = [{"train_groups": [], "test_groups": ["well-c"]}]
        receipt["folds"][0]["train_groups"] = []
        content = self.evaluate(freeze, receipt)
        self.assertNotEqual(content["binding_status"], "mismatch")
        bare = generic_receipt(input_sha256=["e" * 64])
        bare["metric_names"] = ["equal_group_mae"]
        self.assertEqual(self.evaluate(freeze, bare)["binding_status"], "mismatch")

    def test_binding_requests_validate_their_adapter_and_stage(self):
        good = {"freeze_revision_id": FREEZE_ID, "adapter": "regenbench-metrics/1", "stage": "development",
                "receipt_path": "studies/x/metrics.json"}
        self.assertEqual(fe.validate_binding_request(good)["stage"], "development")
        for bad in ({**good, "adapter": "nope"}, {**good, "stage": "test"}, {**good, "receipt_path": ""},
                    {**good, "extra": True}):
            with self.subTest(bad=bad):
                with self.assertRaises(fe.FrozenEvaluationError):
                    fe.validate_binding_request(bad)

    def test_regenbench_receipts_bind_through_the_registry(self):
        freeze = freeze_record(plan_record=plan(status="exploratory"), req=request(split={
            "grouping_unit": "source well", "development_group_ids": ["well-a", "well-b"],
            "final_test_group_ids": []}))
        raw = json.dumps(regenbench_receipt()).encode()
        content = fe.build_binding_content(
            {"freeze_revision_id": freeze["revision_id"], "adapter": "regenbench-metrics/1",
             "stage": "development", "receipt_path": "m.json"}, freeze=freeze, receipt_bytes=raw,
            receipt_name="metrics.json", bound_utc=AFTER_FREEZE)
        # The kit's report has no creation time, so a development binding is never 'prospective'.
        self.assertEqual(content["binding_status"], "bound_timing_unverified")
        self.assertEqual(self.statuses(content)["split_matches_freeze"], "pass")


if __name__ == "__main__":
    unittest.main()
