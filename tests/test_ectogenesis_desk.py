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

    def test_summarizes_receipt_bound_transport_numerical_verification(self):
        bundle = self.root / "transport-verification"
        bundle.mkdir()
        input_bytes = b'{"dimensionless_fixture":true}\n'
        input_sha = hashlib.sha256(input_bytes).hexdigest()
        report = {
            "schema_version": 1,
            "result_kind": "dimensionless_transport_numerical_verification",
            "biological_measurements": False,
            "physiologically_calibrated": False,
            "human_gestation_prediction": False,
            "input_sha256": input_sha,
            "reference_method": "Closed-form two-state matrix exponential.",
            "n_refinement_levels": 2,
            "n_total_timepoints": 8,
            "convergence": [
                {"refinement_factor": 1.0, "requested_step": 0.2, "actual_max_step": 0.2,
                 "n_intervals": 2, "n_timepoints": 3, "max_abs_interface_error": 0.1,
                 "max_abs_core_error": 0.08, "max_abs_state_error": 0.1, "state_rmse": 0.06,
                 "error_ratio_from_previous": None, "observed_order": None},
                {"refinement_factor": 0.5, "requested_step": 0.1, "actual_max_step": 0.1,
                 "n_intervals": 4, "n_timepoints": 5, "max_abs_interface_error": 0.05,
                 "max_abs_core_error": 0.04, "max_abs_state_error": 0.05, "state_rmse": 0.03,
                 "error_ratio_from_previous": 2.0, "observed_order": 1.0},
            ],
            "limits": ["Dimensionless numerical check; no biological validation."],
        }
        report_bytes = json.dumps(report, sort_keys=True, allow_nan=False).encode() + b"\n"
        curve_bytes = b"refinement_factor,max_abs_state_error\n1,0.1\n0.5,0.05\n"
        point_bytes = b"dimensionless_time,absolute_error\n0,0\n1,0.05\n"
        (bundle / "input_config.json").write_bytes(input_bytes)
        (bundle / "numerical_verification_report.json").write_bytes(report_bytes)
        (bundle / "transport_convergence.csv").write_bytes(curve_bytes)
        (bundle / "finest_step_trajectory.csv").write_bytes(point_bytes)
        outputs = {}
        for name, content in (("input_config.json", input_bytes),
                              ("numerical_verification_report.json", report_bytes),
                              ("transport_convergence.csv", curve_bytes),
                              ("finest_step_trajectory.csv", point_bytes)):
            outputs[name] = {"sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
        receipt = {
            "schema_version": 1,
            "bundle_kind": "dimensionless_transport_numerical_verification",
            "package_version": "0.2.2", "python_version": "3.x", "input_sha256": input_sha,
            "implementation_sha256": {"pyproject.toml": "b" * 64}, "metadata": {}, "outputs": outputs,
        }
        (bundle / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
        result = desk.ectogenesis_artifact_bundle(bundle)
        self.assertTrue(result["verified"], result)
        self.assertEqual(result["summary"]["n_refinement_levels"], 2)
        self.assertEqual(result["summary"]["convergence"][1]["observed_order"], 1.0)
        self.assertIn("finest_step_trajectory.csv", result["outputs"])

        report["convergence"][1]["n_timepoints"] = 4
        malformed_bytes = json.dumps(report, sort_keys=True, allow_nan=False).encode() + b"\n"
        (bundle / "numerical_verification_report.json").write_bytes(malformed_bytes)
        receipt["outputs"]["numerical_verification_report.json"] = {
            "sha256": hashlib.sha256(malformed_bytes).hexdigest(), "size_bytes": len(malformed_bytes)}
        (bundle / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
        self.assertFalse(desk.ectogenesis_artifact_bundle(bundle)["verified"])

    def test_summarizes_receipt_bound_mechanics_numerical_verification(self):
        bundle = self.root / "mechanics-verification"
        bundle.mkdir()
        input_bytes = b'{"dimensionless_fixture":true}\n'
        input_sha = hashlib.sha256(input_bytes).hexdigest()
        report = {
            "schema_version": 1,
            "result_kind": "dimensionless_mechanics_numerical_verification",
            "biological_measurements": False,
            "physiologically_calibrated": False,
            "human_gestation_prediction": False,
            "input_sha256": input_sha,
            "reference_method": "Piecewise rectangular-load convolution.",
            "n_timepoints": 401,
            "n_load_boundaries": 4,
            "relative_tolerance": 1e-10,
            "maximum_scaled_error": 2e-16,
            "verification_passed": True,
            "errors": {"max_absolute": 2e-16, "rmse": 1e-16,
                       "max_boundary_absolute": 1e-16},
            "limits": ["Dimensionless mathematical check; no biological validation."],
        }
        report_bytes = json.dumps(report, sort_keys=True, allow_nan=False).encode() + b"\n"
        point_bytes = b"dimensionless_time,solver_strain,convolution_reference_strain,absolute_error,is_load_boundary\n"
        boundary_bytes = point_bytes
        files = {"input_config.json": input_bytes,
                 "mechanics_verification_report.json": report_bytes,
                 "mechanics_pointwise_errors.csv": point_bytes,
                 "mechanics_boundary_errors.csv": boundary_bytes}
        for name, content in files.items():
            (bundle / name).write_bytes(content)
        outputs = {name: {"sha256": hashlib.sha256(content).hexdigest(),
                          "size_bytes": len(content)} for name, content in files.items()}
        receipt = {
            "schema_version": 1,
            "bundle_kind": "dimensionless_mechanics_numerical_verification",
            "package_version": "0.2.2", "python_version": "3.x", "input_sha256": input_sha,
            "implementation_sha256": {"pyproject.toml": "b" * 64}, "metadata": {}, "outputs": outputs,
        }
        (bundle / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
        result = desk.ectogenesis_artifact_bundle(bundle)
        self.assertTrue(result["verified"], result)
        self.assertEqual(result["summary"]["n_load_boundaries"], 4)
        self.assertTrue(result["summary"]["verification_passed"])
        self.assertIn("mechanics_boundary_errors.csv", result["outputs"])

        report["maximum_scaled_error"] = 1e-4
        malformed = json.dumps(report, sort_keys=True, allow_nan=False).encode() + b"\n"
        (bundle / "mechanics_verification_report.json").write_bytes(malformed)
        receipt["outputs"]["mechanics_verification_report.json"] = {
            "sha256": hashlib.sha256(malformed).hexdigest(), "size_bytes": len(malformed)}
        (bundle / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
        self.assertFalse(desk.ectogenesis_artifact_bundle(bundle)["verified"])

    def test_summarizes_receipt_bound_transport_parameter_matrix(self):
        bundle = self.root / "transport-matrix"
        bundle.mkdir()
        names = ["configured_baseline", "zero_dynamics", "exchange_only",
                 "transfer_only", "unequal_coupled", "high_mixing"]
        scenarios = []
        config_json_by_name = {}
        rates_by_name = {
            "configured_baseline": {"boundary_exchange": 0.2, "intercompartment_transport": 0.3, "loss": 0.1},
            "zero_dynamics": {"boundary_exchange": 0.0, "intercompartment_transport": 0.0, "loss": 0.0},
            "exchange_only": {"boundary_exchange": 0.8, "intercompartment_transport": 0.0, "loss": 0.0},
            "transfer_only": {"boundary_exchange": 0.0, "intercompartment_transport": 1.3, "loss": 0.0},
            "unequal_coupled": {"boundary_exchange": 0.17, "intercompartment_transport": 0.83, "loss": 0.06},
            "high_mixing": {"boundary_exchange": 0.8, "intercompartment_transport": 20.0, "loss": 0.1},
        }
        for index, name in enumerate(names):
            rates = rates_by_name[name]
            scenario_config = {
                "schema_version": 1,
                "fixture_notice": "Dimensionless software test fixture.",
                "context": {"stage_track": "postimplantation_embryonic",
                            "species": "unspecified", "interval_label": "test"},
                "dimensionless_time": {"duration": 2.0, "step": 0.01},
                "initial": {"interface": 0.2, "core": 0.4},
                "rates": rates,
                "boundary_concentration": 1.0,
            }
            config_json = json.dumps(scenario_config, indent=2, sort_keys=True,
                                     ensure_ascii=False, allow_nan=False) + "\n"
            config_json_by_name[name] = config_json
            config_digest = hashlib.sha256(config_json.encode()).hexdigest()
            scenarios.append({
                "name": name, "config_sha256": config_digest, "rates": rates,
                "requested_step": 0.01,
                "stability_product": 0.01 * sum(rates.values()),
                "n_total_timepoints": 6205,
                "finest_actual_max_step": 0.000625,
                "finest_max_abs_state_error": 0.001 * (index + 1),
                "finest_state_rmse": 0.0005 * (index + 1),
            })
        input_bytes = config_json_by_name["configured_baseline"].encode()
        input_sha = hashlib.sha256(input_bytes).hexdigest()
        report = {
            "schema_version": 1,
            "result_kind": "dimensionless_transport_parameter_matrix_numerical_verification",
            "biological_measurements": False,
            "physiologically_calibrated": False,
            "human_gestation_prediction": False,
            "input_sha256": input_sha,
            "reference_method": "Closed-form two-state matrix exponential.",
            "n_scenarios": 6, "n_refinement_levels": 5, "n_total_timepoints": 37230,
            "scenarios": scenarios,
            "limits": ["Dimensionless software checks; no biological validation."],
        }
        config_manifest = {"schema_version": 1, "scenario_configs": [
            {"name": item["name"], "config_sha256": item["config_sha256"],
             "config_json": config_json_by_name[item["name"]]} for item in scenarios]}
        report_bytes = json.dumps(report, sort_keys=True, allow_nan=False).encode() + b"\n"
        manifest_bytes = json.dumps(config_manifest, sort_keys=True, allow_nan=False).encode() + b"\n"
        curve_text = "scenario,refinement_factor\n" + "".join(
            f"{name},{factor}\n" for name in names for factor in (1.0, 0.5, 0.25, 0.125, 0.0625))
        files = {
            "input_config.json": input_bytes,
            "transport_matrix_report.json": report_bytes,
            "transport_matrix_convergence.csv": curve_text.encode(),
            "transport_matrix_scenario_configs.json": manifest_bytes,
        }
        point_bytes = b"scenario,dimensionless_time,absolute_interface_error,absolute_core_error\n"
        for name in names:
            files[f"transport_{name}_finest_errors.csv"] = point_bytes
        for name, content in files.items():
            (bundle / name).write_bytes(content)
        outputs = {name: {"sha256": hashlib.sha256(content).hexdigest(),
                          "size_bytes": len(content)} for name, content in files.items()}
        receipt = {
            "schema_version": 1,
            "bundle_kind": "dimensionless_transport_parameter_matrix_numerical_verification",
            "package_version": "0.2.2", "python_version": "3.x", "input_sha256": input_sha,
            "implementation_sha256": {"pyproject.toml": "b" * 64}, "metadata": {}, "outputs": outputs,
        }
        (bundle / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
        result = desk.ectogenesis_artifact_bundle(bundle)
        self.assertTrue(result["verified"], result)
        self.assertEqual(result["summary"]["n_scenarios"], 6)
        self.assertEqual(len(result["summary"]["scenarios"]), 6)
        self.assertIn("transport_high_mixing_finest_errors.csv", result["outputs"])

        report["scenarios"][-1]["stability_product"] = 1.2
        malformed = json.dumps(report, sort_keys=True, allow_nan=False).encode() + b"\n"
        (bundle / "transport_matrix_report.json").write_bytes(malformed)
        receipt["outputs"]["transport_matrix_report.json"] = {
            "sha256": hashlib.sha256(malformed).hexdigest(), "size_bytes": len(malformed)}
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
