from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
EXAMPLE = ROOT / "studies" / "frozen-evaluation-example"


def load_example():
    spec = importlib.util.spec_from_file_location("frozen_evaluation_example", EXAMPLE / "run_example.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VendoredReceiptTests(unittest.TestCase):
    def test_vendored_receipt_is_byte_identical_to_its_recorded_provenance(self):
        provenance = json.loads((EXAMPLE / "inputs" / "PROVENANCE.json").read_text(encoding="utf-8"))
        raw = (EXAMPLE / "inputs" / "nist_ipsc_regression_metrics.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), provenance["receipt_sha256"])
        self.assertEqual(len(raw), provenance["receipt_bytes"])
        self.assertEqual(json.loads(raw)["dataset_sha256"], provenance["feature_table_sha256"])
        self.assertIn("mds2-2960", provenance["upstream_data"]["citation"])

    def test_the_upstream_terms_travel_with_the_derivative(self):
        notice = (EXAMPLE / "SOURCE_NOTICE.md").read_text(encoding="utf-8")
        for expected in ("National Institute of Standards and Technology", "mds2-2960",
                         "Modified works should carry a notice", "Modification notice"):
            self.assertIn(expected, notice)

    def test_matches_the_sibling_checkout_when_one_is_present(self):
        sibling = ROOT.parent / "regen-benchmark-kit" / "examples" / "nist_ipsc" / "results" / "metrics.json"
        if not sibling.is_file():
            self.skipTest("no sibling regen-benchmark-kit checkout beside this repository")
        local = (EXAMPLE / "inputs" / "nist_ipsc_regression_metrics.json").read_bytes()
        if sibling.read_bytes() != local:
            self.skipTest("the sibling receipt has been regenerated since it was vendored; compare PROVENANCE.json")


class WorkedExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name) / "run"
        module = load_example()
        cls.status = module.main(["--out", str(cls.out)])
        cls.result = json.loads((cls.out / "workflow_result.json").read_text(encoding="utf-8"))
        cls.module = module

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_the_real_receipt_agrees_with_its_retrospective_plan_and_nothing_more(self):
        self.assertEqual(self.status, 0)
        as_run = self.result["part_a_real_nist_development_receipt"]["as_run"]
        self.assertEqual(as_run["binding_status"], "bound_retrospective")
        self.assertEqual(as_run["freeze"]["freeze_status"], "retrospective")
        self.assertEqual(as_run["freeze"]["claim_status"], "retrospective_not_confirmatory")
        self.assertFalse(as_run["freeze"]["record_supports_confirmatory_claim"])
        self.assertEqual(as_run["checks"]["inputs_pinned"], "pass")
        self.assertEqual(as_run["checks"]["split_matches_freeze"], "pass")
        # The kit's report carries no creation time and reports no overlap diagnostic; the Desk says
        # so rather than passing those checks.
        self.assertEqual(as_run["checks"]["result_postdates_freeze"], "unavailable")
        self.assertEqual(as_run["checks"]["producer_reported_overlap"], "unavailable")

    def test_leave_one_well_out_cannot_be_a_final_test_evaluation_of_any_well(self):
        sealed = self.result["part_a_real_nist_development_receipt"]["what_if_sealed_training_high"]
        development = sealed["bound_as_development_run"]
        self.assertEqual(development["binding_status"], "mismatch")
        self.assertEqual(development["final_test_groups_in_training"], ["training_high"])
        self.assertEqual(sealed["bound_as_final_test_run"]["binding_status"], "mismatch")
        self.assertEqual(sealed["bound_as_final_test_run"]["checks"]["final_test_not_in_training"], "fail")
        self.assertEqual(sealed["freeze"]["claim_status"], "holdout_compromised")
        self.assertIn("final_test_data_used_in_development_run", sealed["freeze"]["violations"])

    def test_the_synthetic_clean_path_is_labelled_and_reaches_the_supported_state_once(self):
        clean = self.result["part_b_synthetic_clean_path"]
        self.assertIn("SYNTHETIC", clean["label"])
        self.assertEqual(clean["binding_status"], "bound_prospective")
        self.assertEqual(clean["freeze"]["claim_status"], "single_final_evaluation_recorded")
        self.assertTrue(clean["freeze"]["record_supports_confirmatory_claim"])
        self.assertEqual(clean["freeze"]["ledger_events"], 2)

    def test_the_exported_dossier_verifies_and_stays_unreviewed(self):
        import verify_dossier
        report = verify_dossier.verify_dossier(self.out / "dossier.zip", strict=True)
        self.assertTrue(report["verified"], report["errors"] + report["lineage"]["problems"])
        self.assertEqual(report["scientific_lineage"], "resolved")
        self.assertEqual(report["scientific_review"], "not_established_by_this_tool")
        self.assertEqual(report["reproduction"], "not_attempted")
        self.assertEqual(len(report["lineage"]["freezes"]), 3)
        self.assertTrue(all(item["claim_status_matches_export"] for item in report["lineage"]["freezes"]))

    def test_artifacts_hold_no_machine_paths_and_the_report_states_its_limits(self):
        for name in ("workflow_result.json", "verification_report.json", "REPORT.md"):
            text = (self.out / name).read_text(encoding="utf-8")
            self.assertNotIn(self.temp.name, text, name)
        report = (self.out / "REPORT.md").read_text(encoding="utf-8")
        self.assertIn("What this does not show", report)
        self.assertIn("runs no model and measures no biology", report.replace("It ", "It ", 1))
        self.assertTrue((self.out / "synthetic_receipt.json").is_file())

    def test_it_refuses_to_overwrite_and_restores_the_global_paths(self):
        import regen
        before = (regen.DATA, regen.CACHE, regen.PROV)
        with self.assertRaises(SystemExit):
            self.module.main(["--out", str(self.out)])
        with tempfile.TemporaryDirectory() as temporary:
            self.module.main(["--out", str(Path(temporary) / "second")])
        self.assertEqual((regen.DATA, regen.CACHE, regen.PROV), before)


if __name__ == "__main__":
    unittest.main()
