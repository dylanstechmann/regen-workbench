"""Integrity checks on the committed GSE160356 freeze, receipt and dossiers.

These read only committed files: no Desk, no network and no sibling checkout. They check that the
procedural record is internally consistent (the freeze came first, the bound receipt is the one
the producer wrote, the dossiers verify) and that it claims no more than it should.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "studies" / "senescence-endothelial-challenge"
sys.path.insert(0, str(ROOT / "tools"))

import frozen_evaluation as fe  # noqa: E402
import verify_dossier  # noqa: E402


def records(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("research_records.json"))["records"]


def utc(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


@unittest.skipUnless((STUDY / "derived" / "dossier.zip").is_file(), "committed dossier not present")
class SenescenceEndothelialChallengeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = json.loads((STUDY / "freeze_state.json").read_text(encoding="utf-8"))
        cls.result = json.loads((STUDY / "derived" / "binding_result.json").read_text(encoding="utf-8"))
        cls.receipt_bytes = (STUDY / "inputs" / "evaluation_receipt.json").read_bytes()
        cls.receipt = json.loads(cls.receipt_bytes)
        cls.provenance = json.loads((STUDY / "inputs" / "PROVENANCE.json").read_text(encoding="utf-8"))
        cls.before = records(STUDY / "derived" / "dossier-before-run.zip")
        cls.after = records(STUDY / "derived" / "dossier.zip")

    def one(self, rows, record_type):
        found = [row for row in rows if row["record_type"] == record_type]
        self.assertEqual(len(found), 1, record_type)
        return found[0]

    def test_the_vendored_receipt_is_the_one_the_producer_wrote(self):
        self.assertEqual(hashlib.sha256(self.receipt_bytes).hexdigest(), self.provenance["receipt_sha256"])
        self.assertEqual(len(self.receipt_bytes), self.provenance["receipt_bytes"])
        self.assertEqual(self.receipt["producer"]["code_revision"], self.provenance["receipt_code_revision"])
        self.assertIs(self.provenance["tracked_changes_when_copied"], False)

    def test_the_freeze_pins_the_same_method_revision_the_receipt_reports(self):
        freeze = self.one(self.after, "plan_freeze")
        self.assertEqual(freeze["content"]["method"]["revision"], self.state["method_revision"])
        self.assertEqual(self.receipt["producer"]["code_revision"], self.state["method_revision"])
        self.assertIn(self.state["plan_sha256"], freeze["content"]["method"]["parameters"])
        self.assertEqual(freeze["content_sha256"], self.state["freeze_content_sha256"])
        self.assertEqual(freeze["revision_id"], self.state["freeze_revision_id"])

    def test_the_freeze_existed_before_the_run_and_the_ledger_and_binding_came_after(self):
        before_freeze = self.one(self.before, "plan_freeze")
        self.assertEqual(before_freeze["content_sha256"], self.state["freeze_content_sha256"])
        self.assertFalse([row for row in self.before if row["record_type"] in {"holdout_access", "evaluation_binding"}])
        frozen = utc(before_freeze["content"]["frozen_utc"])
        self.assertLess(frozen, utc(self.receipt["created_utc"]))
        event = self.one(self.after, "holdout_access")
        binding = self.one(self.after, "evaluation_binding")
        self.assertLess(utc(self.receipt["created_utc"]), utc(event["content"]["recorded_utc"]))
        self.assertLessEqual(utc(event["content"]["recorded_utc"]), utc(binding["content"]["bound_utc"]))

    def test_the_freeze_is_honestly_exploratory_with_its_blocker_listed(self):
        freeze = self.one(self.after, "plan_freeze")
        self.assertEqual(freeze["content"]["freeze_status"], "exploratory")
        self.assertFalse(freeze["content"]["results_inspected_before_freeze"])
        self.assertTrue(any("independent-unit" in item for item in freeze["content"]["confirmatory_blockers"]))
        self.assertEqual(len(freeze["content"]["split"]["development_group_ids"]), 3)
        self.assertEqual(len(freeze["content"]["split"]["final_test_group_ids"]), 6)
        self.assertIn("Sixteen count lines", freeze["content"]["inspection_statement"])

    def test_the_binding_passes_every_check_and_the_record_claims_nothing_confirmatory(self):
        binding = self.one(self.after, "evaluation_binding")
        self.assertEqual(binding["content"]["binding_status"], "bound_prospective")
        self.assertEqual({item["id"]: item["status"] for item in binding["content"]["checks"]}, {
            "inputs_pinned": "pass", "split_matches_freeze": "pass", "final_test_not_in_training": "pass",
            "producer_reported_overlap": "pass", "method_revision_matches": "pass",
            "primary_metric_present": "pass", "result_postdates_freeze": "pass"})
        self.assertEqual(binding["content"]["receipt"]["sha256"], hashlib.sha256(self.receipt_bytes).hexdigest())
        freeze = self.one(self.after, "plan_freeze")
        assessment = freeze["freeze_assessment"]
        self.assertEqual(assessment["claim_status"], "exploratory_only")
        self.assertFalse(assessment["record_supports_confirmatory_claim"])
        self.assertEqual(self.result["binding_status"], "bound_prospective")
        self.assertEqual(self.result["claim_status"], "exploratory_only")
        self.assertFalse(self.result["record_supports_confirmatory_claim"])
        self.assertEqual(self.result["violations"], [])

    def test_the_binding_is_what_the_current_adapter_produces_from_the_committed_receipt(self):
        freeze = self.one(self.after, "plan_freeze")
        normalized = fe.adapt_evaluation_receipt(self.receipt)
        recomputed = fe.evaluate_binding(freeze, normalized, "final_test")
        stored = self.one(self.after, "evaluation_binding")["content"]
        self.assertEqual(recomputed["binding_status"], stored["binding_status"])
        self.assertEqual(recomputed["checks"], stored["checks"])

    def test_both_dossiers_verify_strictly_and_lineage_resolves(self):
        for name in ("dossier-before-run.zip", "dossier.zip"):
            with self.subTest(name=name):
                report = verify_dossier.verify_dossier(STUDY / "derived" / name, strict=True)
                self.assertTrue(report["verified"], report["errors"] + report["lineage"]["problems"])
                self.assertEqual(report["scientific_lineage"], "resolved")
                self.assertEqual(report["scientific_review"], "not_established_by_this_tool")
                self.assertEqual(report["reproduction"], "not_attempted")

    def test_the_dataset_card_pins_every_input_the_receipt_names(self):
        card = self.one(self.after, "dataset_card")
        pinned = {item["sha256"] for item in card["content"]["files"] if item["sha256"]}
        self.assertTrue(set(self.receipt["input_sha256"]) <= pinned)


if __name__ == "__main__":
    unittest.main()
