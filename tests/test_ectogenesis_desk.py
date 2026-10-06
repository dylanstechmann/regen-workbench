from __future__ import annotations

import sys
import hashlib
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from unittest.mock import patch

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
                    report["result_kind"] = ("dimensionless_kelvin_voigt_mechanics"
                        if kind == "dimensionless_transport_theory" else "dimensionless_two_compartment_transport")
                    swapped_bytes = json.dumps(report, sort_keys=True).encode() + b"\n"
                    (bundle / report_name).write_bytes(swapped_bytes)
                    receipt["outputs"][report_name] = {
                        "sha256": hashlib.sha256(swapped_bytes).hexdigest(), "size_bytes": len(swapped_bytes)}
                    (bundle / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
                    self.assertFalse(desk.ectogenesis_artifact_bundle(bundle)["verified"])

    def _write_design_sweep_bundle(self, bundle_id, *, input_text="same dimensionless config",
                                   rows=None, implementation_digest="b"):
        bundle = self.root / bundle_id
        bundle.mkdir()
        input_bytes = (input_text + "\n").encode()
        input_digest = hashlib.sha256(input_bytes).hexdigest()
        if rows is None:
            rows = [
                {"cadence_factor_requested": 0.5, "noise_multiplier_requested": 0.0,
                 "median_prospective_forecast_rmse": 1.0,
                 "prospective_forecast_estimable_replicates": 2},
                {"cadence_factor_requested": 1.0, "noise_multiplier_requested": 1.0,
                 "median_prospective_forecast_rmse": None,
                 "prospective_forecast_estimable_replicates": 0},
            ]
        summaries = []
        for row in rows:
            summaries.append({
                "cadence_factor_requested": row["cadence_factor_requested"],
                "noise_multiplier_requested": row["noise_multiplier_requested"],
                "actual_output_step": row["cadence_factor_requested"],
                "actual_noise_sd": row["noise_multiplier_requested"],
                "monitor_fault_profile": row.get("monitor_fault_profile", "configured faults"),
                "event_timing_profile": row.get("event_timing_profile", "as configured"),
                "replicates": 2,
                "median_prospective_forecast_rmse": row.get("median_prospective_forecast_rmse"),
                "prospective_forecast_estimable_replicates": row.get("prospective_forecast_estimable_replicates", 2),
            })
        report = {
            "schema_version": 2, "result_kind": "synthetic_exchange_design_sweep",
            "biological_measurements": False, "physiologically_calibrated": False,
            "human_gestation_prediction": False, "limits": [], "n_designs": len(summaries),
            "n_synthetic_runs": 2 * len(summaries), "design_summaries": summaries,
        }
        report_bytes = json.dumps(report, sort_keys=True, allow_nan=False).encode() + b"\n"
        (bundle / "input_config.json").write_bytes(input_bytes)
        (bundle / "design_sweep_report.json").write_bytes(report_bytes)
        outputs = {}
        for filename, content in (("input_config.json", input_bytes),
                                  ("design_sweep_report.json", report_bytes)):
            outputs[filename] = {"sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
        receipt = {
            "schema_version": 1, "bundle_kind": "synthetic_exchange_design_sweep",
            "package_version": "0.3.0", "python_version": "3.x", "input_sha256": input_digest,
            "implementation_sha256": {"pyproject.toml": implementation_digest * 64},
            "metadata": {}, "outputs": outputs,
        }
        (bundle / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
        return desk.ectogenesis_artifact_bundle(bundle)

    def test_compares_matching_receipt_verified_sweeps_and_preserves_missing_metrics(self):
        bundle_a = self._write_design_sweep_bundle("sweep-a")
        bundle_b = self._write_design_sweep_bundle("sweep-b", rows=[
            {"cadence_factor_requested": 1.0, "noise_multiplier_requested": 1.0,
             "median_prospective_forecast_rmse": 2.0,
             "prospective_forecast_estimable_replicates": 1},
            {"cadence_factor_requested": 0.5, "noise_multiplier_requested": 0.0,
             "median_prospective_forecast_rmse": 1.75,
             "prospective_forecast_estimable_replicates": 2},
        ], implementation_digest="c")
        result = desk.ectogenesis_design_sweep_comparison(
            bundle_a, bundle_b, "median_prospective_forecast_rmse")
        self.assertTrue(result["compatible"], result)
        self.assertFalse(result["implementation_hashes_match"])
        self.assertEqual(result["rows"][0]["coordinate"]["cadence_factor_requested"], 0.5)
        self.assertAlmostEqual(result["rows"][0]["delta_b_minus_a"], 0.75)
        self.assertIsNone(result["rows"][1]["delta_b_minus_a"])

    def test_comparison_blocks_changed_input_or_design_coordinates(self):
        baseline = self._write_design_sweep_bundle("sweep-base")
        different_input = self._write_design_sweep_bundle("sweep-input", input_text="other config")
        result = desk.ectogenesis_design_sweep_comparison(
            baseline, different_input, "median_prospective_forecast_rmse")
        self.assertFalse(result["compatible"])
        self.assertIn("Input configuration", result["reason"])

        changed_coordinate = self._write_design_sweep_bundle("sweep-grid", rows=[
            {"cadence_factor_requested": 0.5, "noise_multiplier_requested": 0.0,
             "median_prospective_forecast_rmse": 1.0},
            {"cadence_factor_requested": 2.0, "noise_multiplier_requested": 1.0,
             "median_prospective_forecast_rmse": 2.0},
        ])
        result = desk.ectogenesis_design_sweep_comparison(
            baseline, changed_coordinate, "median_prospective_forecast_rmse")
        self.assertFalse(result["compatible"])
        self.assertIn("coordinate sets", result["reason"])

    def test_rejects_design_sweep_with_duplicate_coordinates(self):
        duplicate_rows = [
            {"cadence_factor_requested": 0.5, "noise_multiplier_requested": 0.0,
             "median_prospective_forecast_rmse": 1.0},
            {"cadence_factor_requested": 0.5, "noise_multiplier_requested": 0.0,
             "median_prospective_forecast_rmse": 2.0},
        ]
        result = self._write_design_sweep_bundle("sweep-duplicate", rows=duplicate_rows)
        self.assertFalse(result["verified"])

    def test_read_only_comparison_route_rechecks_receipts(self):
        self._write_design_sweep_bundle("sweep-a")
        self._write_design_sweep_bundle("sweep-b", rows=[
            {"cadence_factor_requested": 1.0, "noise_multiplier_requested": 1.0,
             "median_prospective_forecast_rmse": 2.0},
            {"cadence_factor_requested": 0.5, "noise_multiplier_requested": 0.0,
             "median_prospective_forecast_rmse": 1.5},
        ])
        with patch.object(desk, "ECTOGENESIS_MODEL_ROOT", self.root):
            server = ThreadingHTTPServer(("127.0.0.1", 0), desk.make_handler(self.desk))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(thread.join, 2)
            self.addCleanup(server.shutdown)
            query = urlencode({"bundle_a": "sweep-a", "bundle_b": "sweep-b",
                               "metric": "median_prospective_forecast_rmse"})
            with urlopen(f"http://127.0.0.1:{server.server_port}/api/ectogenesis/model-comparison?{query}") as response:
                result = json.loads(response.read())
        self.assertTrue(result["compatible"], result)
        self.assertAlmostEqual(result["rows"][0]["delta_b_minus_a"], 0.5)


if __name__ == "__main__":
    unittest.main()
