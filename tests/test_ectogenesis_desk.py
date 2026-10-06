from __future__ import annotations

import sys
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import regen_desk as desk


class EctogenesisDeskTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.desk = desk.Desk(self.root)
        self.addCleanup(lambda: self.desk.executor.shutdown(wait=True))

    def test_starter_campaigns_keep_complete_gestation_unassessed_and_growth_limits_visible(self):
        state = self.desk.state()
        self.assertTrue(any(item["id"] == "ectogenesis" for item in state["blueprints"]))
        saved = []
        for starter in state["campaign_starters"]["ectogenesis"]:
            data = {key: value for key, value in starter.items() if key != "id"}
            saved.append(self.desk.campaign({"blueprint_id": "ectogenesis", **data}))
        complete = next(item for item in saved if item["title"] == "Complete ectogenesis capability map")
        axis = next(item for item in complete["evidence"] if item["axis_id"] == "complete_gestation")
        self.assertEqual(axis["status"], "not assessed")
        partial = next(item for item in saved if item["title"] == "Partial support versus normal development")
        growth = next(item for item in partial["evidence"] if item["axis_id"] == "developmental_outcomes")
        self.assertEqual(growth["status"], "source reports mixed signal")
        self.assertIn("reduced", growth["value"])

    def test_seed_migration_adds_area_and_preserves_saved_questions_and_focus_priorities(self):
        self.desk.store["blueprints"] = [item for item in self.desk.store["blueprints"]
                                         if item["id"] != "ectogenesis"]
        organs = next(item for item in self.desk.store["blueprints"] if item["id"] == "organs")
        organs["question"] = "My saved research question"
        self.desk.save_store()
        reloaded = desk.Desk(self.root)
        self.addCleanup(lambda: reloaded.executor.shutdown(wait=True))
        identifiers = [item["id"] for item in reloaded.store["blueprints"]]
        self.assertEqual(identifiers[:3], ["reprogramming", "tissues", "nanomedicine"])
        self.assertEqual(identifiers.count("ectogenesis"), 1)
        self.assertEqual(identifiers.index("ectogenesis"), identifiers.index("organs") + 1)
        organs = next(item for item in reloaded.store["blueprints"] if item["id"] == "organs")
        self.assertEqual(organs["question"], "My saved research question")

    def test_summarizes_v2_forecast_reports_and_new_theory_bundles(self):
        cases = [
            ("synthetic_exchange_observability_diagnostic", "source_manifest.json", "observability_report.json", {
                "schema_version": 2, "result_kind": "synthetic_exchange_observability_diagnostic",
                "biological_measurements": False, "physiologically_calibrated": False,
                "human_gestation_prediction": False, "limits": [], "n_usable_readings": 8,
                "full_series_fit": {"rank": 2}, "early_series_fit": {"estimable": True},
                "balance_residual_diagnostic": {"label": "same-run diagnostic"},
                "noise_aware_state_model": {"prospective_forecast": {"estimable": True}},
                "simulation_binding": {"trajectory_sha256": "a" * 64},
            }),
            ("dimensionless_transport_theory", "input_config.json", "transport_report.json", {
                "schema_version": 1, "result_kind": "dimensionless_two_compartment_transport",
                "biological_measurements": False, "physiologically_calibrated": False,
                "human_gestation_prediction": False, "limits": [], "outputs": {"final_core_state": 0.2},
                "alternative_model": {"name": "single stock"}, "assumptions": ["dimensionless fixture"]
            }),
            ("dimensionless_mechanics_theory", "input_config.json", "mechanics_report.json", {
                "schema_version": 1, "result_kind": "dimensionless_kelvin_voigt_mechanics",
                "biological_measurements": False, "physiologically_calibrated": False,
                "human_gestation_prediction": False, "limits": [], "outputs": {"final_strain": 0.1},
                "alternative_model": {"name": "elastic reference"}, "assumptions": ["dimensionless fixture"]
            }),
        ]
        for kind, input_name, report_name, report in cases:
            with self.subTest(kind=kind):
                bundle = self.root / (kind.replace("_", "-") + "-bundle")
                bundle.mkdir()
                input_bytes = b'{"fixture":"dimensionless"}\n'
                report_bytes = json.dumps(report, sort_keys=True).encode() + b"\n"
                (bundle / input_name).write_bytes(input_bytes)
                (bundle / report_name).write_bytes(report_bytes)
                files = {
                    input_name: {"sha256": hashlib.sha256(input_bytes).hexdigest(), "size_bytes": len(input_bytes)},
                    report_name: {"sha256": hashlib.sha256(report_bytes).hexdigest(), "size_bytes": len(report_bytes)},
                }
                receipt = {
                    "schema_version": 1, "bundle_kind": kind, "package_version": "0.2.0",
                    "python_version": "3.x", "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
                    "implementation_sha256": {"pyproject.toml": "b" * 64}, "metadata": {}, "outputs": files,
                }
                (bundle / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
                result = desk.ectogenesis_artifact_bundle(bundle)
                self.assertTrue(result["verified"], result)
                if kind == "synthetic_exchange_observability_diagnostic":
                    self.assertIn("prospective_forecast", result["summary"]["noise_aware_state_model"])
                    self.assertEqual(result["summary"]["simulation_binding"]["trajectory_sha256"], "a" * 64)
                else:
                    self.assertIn("outputs", result["summary"])


if __name__ == "__main__":
    unittest.main()
