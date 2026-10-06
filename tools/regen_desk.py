"""Local research orchestration, source intake and bounded RDKit exploration."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import mimetypes
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

import regen
from regen_compute import compound_screen, manifest, write_json

HOME = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).with_name("desk")
ECTOGENESIS_MODEL_ROOT = Path("/lab/ectogenesis-models")
ECTOGENESIS_BUNDLE_KINDS = {
    "reviewed_evidence_map": "Evidence map",
    "synthetic_exchange_software_fixture": "Dimensionless exchange simulation",
    "synthetic_exchange_observability_diagnostic": "Dimensionless identifiability report",
    "synthetic_exchange_design_sweep": "Dimensionless cadence/noise design sweep",
    "dimensionless_transport_theory": "Dimensionless two-compartment transport theory",
    "dimensionless_mechanics_theory": "Dimensionless Kelvin–Voigt mechanics theory",
    "dimensionless_transport_numerical_verification": "Dimensionless transport numerical verification",
    "dimensionless_mechanics_numerical_verification": "Dimensionless mechanics numerical verification",
    "dimensionless_transport_parameter_matrix_numerical_verification": "Dimensionless transport parameter matrix",
}
ECTOGENESIS_SWEEP_METRICS = {
    "median_prospective_forecast_rmse": {
        "label": "Forward forecast RMSE", "estimable_count": "prospective_forecast_estimable_replicates"},
    "median_prospective_forecast_baseline_rmse": {
        "label": "Last-reading baseline RMSE", "estimable_count": "prospective_forecast_estimable_replicates"},
    "median_prospective_forecast_coverage_95": {
        "label": "Approx. 95% interval coverage", "estimable_count": "prospective_forecast_interval_available_replicates"},
    "median_prospective_forecast_interval_width_95": {
        "label": "Approx. 95% interval width", "estimable_count": "prospective_forecast_interval_available_replicates"},
    "median_cross_replicate_holdout_fixture_scale_rmse": {
        "label": "Leave-one-seed-out balance residual (not forecast)",
        "estimable_count": "cross_replicate_holdout_estimable_replicates"},
    "median_temporal_holdout_fixture_scale_rmse": {
        "label": "Same-run balance residual (not forecast)",
        "estimable_count": "temporal_holdout_estimable_replicates"},
    "median_design_condition_number": {
        "label": "Balance-regression condition number", "estimable_count": "replicates"},
}
ECTOGENESIS_ARTIFACT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\.(?:json|csv|md)")
ECTOGENESIS_BUNDLE_BYTE_LIMIT = 24_000_000
PROVIDERS = {
    "pubmed": ("PubMed", "NCBI_API_KEY", False),
    "europepmc": ("Europe PMC", None, False),
    "openalex": ("OpenAlex", "OPENALEX_API_KEY", False),
    "trials": ("ClinicalTrials.gov", None, False),
    "semantic": ("Semantic Scholar", "SEMANTIC_SCHOLAR_API_KEY", False),
    "core": ("CORE", "CORE_API_KEY", True),
    "brave": ("Brave web / forums", "BRAVE_SEARCH_API_KEY", True),
    "exa": ("Exa web / forums", "EXA_API_KEY", True),
}
KINDS = {"search", "compound", "neighbors", "variants", "compare", "conformers", "docking"}
BLUEPRINT_FIELDS = ("title", "area", "query", "question", "who", "what", "where", "when", "why", "how", "falsifier", "desired_changes")
CAMPAIGN_FIELDS = ("title", "target", "species", "tissue", "hypothesis", "endpoint", "falsifier", "evidence_stage", "study_design", "reference_url", "receptor", "structure_notes", "starter_id")
EVIDENCE_STATUS = {"not assessed", "source reports positive signal", "source reports mixed signal", "source reports no signal", "conflicting sources"}
EVIDENCE_FIELDS = ("status", "value", "unit", "comparator", "timepoint", "source_url", "notes")
EVIDENCE_RECORD_FIELDS = ("source_type", "source_title", "source_url", "license", "species", "stage_track",
                          "developmental_interval", "model_system", "comparator", "outcome", "measure",
                          "value", "unit", "independent_unit", "sample_size", "follow_up", "status",
                          "direction", "notes", "dataset_sha256")


def experiment_manifest_tools():
    """Load the shared experiment validator without adding a methods package here."""
    path = HOME / "tools" / "validate_experiment_manifest.py"
    spec = importlib.util.spec_from_file_location("regen_experiment_manifest_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Shared experiment manifest validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def text_field(data, key, default="", maximum=4000):
    value = data.get(key, default)
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"{key} must be text of at most {maximum} characters")
    return value.strip()


def bounded_int(value, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"Expected an integer from {low} to {high}")
    return value


def bounded_number(value, low, high, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number from {low} to {high}")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a finite number from {low} to {high}") from None
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{label} must be a finite number from {low} to {high}")
    return result


def campaign_structure_path(value, label):
    raw = Path(value)
    if not raw.is_absolute():
        raw = regen.ROOT / raw
    try:
        path = raw.resolve(strict=True)
        structures = (regen.DATA / "structures").resolve(strict=True)
    except OSError:
        raise ValueError(f"{label} must exist under data/structures") from None
    if path == structures or structures not in path.parents or not path.is_file():
        raise ValueError(f"{label} must be a regular file under data/structures")
    if path.suffix.lower() != ".pdbqt" or path.stat().st_size > 25 * 1024 * 1024:
        raise ValueError(f"{label} must be a .pdbqt file no larger than 25 MiB")
    return path


def public_url(value):
    if not isinstance(value, str) or len(value) > 3000:
        return ""
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password else ""
    except ValueError:
        return ""


def redact(value):
    encoded = json.dumps(value, ensure_ascii=True, allow_nan=False)
    for name, secret in os.environ.items():
        if name == "EMAIL" or any(word in name for word in ("API_KEY", "TOKEN", "SECRET")):
            if len(secret) >= 5:
                encoded = encoded.replace(json.dumps(secret)[1:-1], "[redacted]")
                encoded = encoded.replace(quote(secret, safe=""), "[redacted]")
    return json.loads(encoded)


def ectogenesis_artifact_bundle(path):
    """Summarize a receipt-bound sibling bundle without changing its files."""
    try:
        if path.is_symlink() or not path.is_dir():
            return None
        base = path.resolve(strict=True)
        root = path.parent.resolve(strict=True)
        if base.parent != root:
            return None
        receipt_path = base / "receipt.json"
        if receipt_path.is_symlink() or not receipt_path.is_file() or receipt_path.stat().st_size > 512_000:
            raise ValueError
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (not isinstance(receipt, dict) or receipt.get("schema_version") != 1
                or isinstance(receipt.get("schema_version"), bool)):
            raise ValueError
        if any(not isinstance(receipt.get(field), str) or len(receipt[field]) > 128
               for field in ("package_version", "python_version")):
            raise ValueError
        kind = receipt.get("bundle_kind")
        if kind not in ECTOGENESIS_BUNDLE_KINDS:
            return None
        if not isinstance(receipt.get("input_sha256"), str) or not re.fullmatch(
                r"[0-9a-f]{64}", receipt["input_sha256"]):
            raise ValueError
        implementation = receipt.get("implementation_sha256")
        if not isinstance(implementation, dict) or not 1 <= len(implementation) <= 64:
            raise ValueError
        if any(not isinstance(name, str)
               or not re.fullmatch(r"(?:src/wombmodels/[A-Za-z0-9_.-]+\.py|pyproject\.toml)", name)
               or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
               for name, digest in implementation.items()):
            raise ValueError
        if not isinstance(receipt.get("metadata"), dict):
            raise ValueError
        input_file = {"reviewed_evidence_map": "input_ledger.json",
                      "synthetic_exchange_software_fixture": "input_config.json",
                      "synthetic_exchange_observability_diagnostic": "source_manifest.json",
                      "synthetic_exchange_design_sweep": "input_config.json",
                      "dimensionless_transport_theory": "input_config.json",
                      "dimensionless_mechanics_theory": "input_config.json",
                      "dimensionless_transport_numerical_verification": "input_config.json",
                      "dimensionless_mechanics_numerical_verification": "input_config.json",
                      "dimensionless_transport_parameter_matrix_numerical_verification": "input_config.json"}[kind]
        outputs = receipt.get("outputs")
        if (not isinstance(outputs, dict) or not 1 <= len(outputs) <= 12
                or input_file not in outputs):
            raise ValueError
        input_contract = outputs[input_file]
        if not isinstance(input_contract, dict) or input_contract.get("sha256") != receipt["input_sha256"]:
            raise ValueError
        bundle_bytes = 0
        for filename, contract in outputs.items():
            if not isinstance(filename, str) or not ECTOGENESIS_ARTIFACT_NAME.fullmatch(filename):
                raise ValueError
            source = base / filename
            if source.is_symlink() or not source.is_file() or source.resolve(strict=True).parent != base:
                raise ValueError
            size = source.stat().st_size
            bundle_bytes += size
            if bundle_bytes > ECTOGENESIS_BUNDLE_BYTE_LIMIT:
                raise ValueError
            if (not isinstance(contract, dict) or isinstance(contract.get("size_bytes"), bool)
                    or not isinstance(contract.get("size_bytes"), int) or contract["size_bytes"] < 0):
                raise ValueError
            if size > 12_000_000 or size != contract.get("size_bytes"):
                raise ValueError
            digest = contract.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError
            if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise ValueError
        summary = {}
        summary_file = {"reviewed_evidence_map": "evidence_report.json",
                        "synthetic_exchange_software_fixture": "simulation_summary.json",
                        "synthetic_exchange_observability_diagnostic": "observability_report.json",
                        "synthetic_exchange_design_sweep": "design_sweep_report.json",
                        "dimensionless_transport_theory": "transport_report.json",
                        "dimensionless_mechanics_theory": "mechanics_report.json",
                        "dimensionless_transport_numerical_verification": "numerical_verification_report.json",
                        "dimensionless_mechanics_numerical_verification": "mechanics_verification_report.json",
                        "dimensionless_transport_parameter_matrix_numerical_verification": "transport_matrix_report.json"}[kind]
        if summary_file not in outputs:
            raise ValueError
        summary_path = base / summary_file
        if summary_path.stat().st_size > 2_000_000:
            raise ValueError
        detail = json.loads(summary_path.read_text(encoding="utf-8"))
        if not isinstance(detail, dict):
            raise ValueError
        expected_report_version = 2 if kind in {
            "synthetic_exchange_observability_diagnostic", "synthetic_exchange_design_sweep"
        } else 1
        if detail.get("schema_version") != expected_report_version or isinstance(detail.get("schema_version"), bool):
            raise ValueError
        limits = detail.get("limits")
        if (not isinstance(limits, list) or len(limits) > 12
                or not all(isinstance(item, str) and len(item) <= 2_000 for item in limits)):
            raise ValueError
        summary["limitations"] = limits
        if kind == "reviewed_evidence_map":
            if (detail.get("report_kind") != kind
                    or detail.get("biological_assay_performed") is not False):
                raise ValueError
            summary.update(source_count=len(detail.get("sources", [])),
                           claim_count=len(detail.get("claims", [])),
                           requirement_count=len(detail.get("requirements", [])),
                           reviewed_on=detail.get("reviewed_on"))
        elif kind == "synthetic_exchange_software_fixture":
            if (detail.get("result_kind") != kind or any(detail.get(flag) is not False for flag in
                   ("biological_assay_performed", "physiologically_calibrated", "human_gestation_prediction"))):
                raise ValueError
            summary.update(n_samples=detail.get("n_samples"),
                           n_monitor_samples=detail.get("n_monitor_samples"),
                           balances=detail.get("balances"),
                           fault_metrics=detail.get("software_fault_metrics"))
        elif kind == "synthetic_exchange_observability_diagnostic":
            if (detail.get("result_kind") != kind or any(detail.get(flag) is not False for flag in
                   ("biological_measurements", "physiologically_calibrated", "human_gestation_prediction"))):
                raise ValueError
            summary.update(full_series_fit=detail.get("full_series_fit"),
                           early_series_fit=detail.get("early_series_fit"),
                           balance_residual_diagnostic=detail.get("balance_residual_diagnostic"),
                           noise_aware_state_model=detail.get("noise_aware_state_model"),
                           simulation_binding=detail.get("simulation_binding"),
                           n_usable_readings=detail.get("n_usable_readings"))
        elif kind == "synthetic_exchange_design_sweep":
            if (detail.get("result_kind") != kind or any(detail.get(flag) is not False for flag in
                   ("biological_measurements", "physiologically_calibrated", "human_gestation_prediction"))):
                raise ValueError
            designs = detail.get("design_summaries")
            runs = detail.get("n_synthetic_runs")
            count = detail.get("n_designs")
            if (not isinstance(designs, list) or not 1 <= len(designs) <= 36
                    or not all(isinstance(item, dict) for item in designs)
                    or isinstance(runs, bool) or not isinstance(runs, int) or not 1 <= runs <= 720
                    or isinstance(count, bool) or not isinstance(count, int) or count != len(designs)):
                raise ValueError
            coordinates = set()
            replicate_total = 0
            for item in designs:
                cadence = item.get("cadence_factor_requested")
                noise = item.get("noise_multiplier_requested")
                fault_profile = item.get("monitor_fault_profile")
                timing_profile = item.get("event_timing_profile")
                if (isinstance(cadence, bool) or not isinstance(cadence, (int, float))
                        or not math.isfinite(cadence) or cadence <= 0
                        or isinstance(noise, bool) or not isinstance(noise, (int, float))
                        or not math.isfinite(noise) or noise < 0
                        or not isinstance(fault_profile, str) or not fault_profile or len(fault_profile) > 256
                        or (timing_profile is not None and
                            (not isinstance(timing_profile, str) or not timing_profile or len(timing_profile) > 256))):
                    raise ValueError
                coordinate = (float(cadence), float(noise), fault_profile, timing_profile)
                if coordinate in coordinates:
                    raise ValueError
                coordinates.add(coordinate)
                replicates = item.get("replicates")
                if (isinstance(replicates, bool) or not isinstance(replicates, int)
                        or not 1 <= replicates <= 720):
                    raise ValueError
                replicate_total += replicates
                for name in ("actual_output_step", "actual_noise_sd"):
                    value = item.get(name)
                    if (isinstance(value, bool) or not isinstance(value, (int, float))
                            or not math.isfinite(value) or (value <= 0 if name == "actual_output_step" else value < 0)):
                        raise ValueError
                for name in ECTOGENESIS_SWEEP_METRICS:
                    value = item.get(name)
                    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                              or not math.isfinite(value)):
                        raise ValueError
                for name in ("prospective_forecast_estimable_replicates",
                             "prospective_forecast_interval_available_replicates",
                             "cross_replicate_holdout_estimable_replicates",
                             "temporal_holdout_estimable_replicates"):
                    value = item.get(name)
                    if (value is not None and (isinstance(value, bool) or not isinstance(value, int)
                                               or not 0 <= value <= replicates)):
                        raise ValueError
            if replicate_total != runs:
                raise ValueError
            summary.update(n_designs=count, n_synthetic_runs=runs,
                           design_summaries=designs,
                           prospective_forecast_contract=detail.get("prospective_forecast_contract"),
                           prospective_forecast_training_cutoff=detail.get("prospective_forecast_training_cutoff"),
                           temporal_holdout_contract=detail.get("temporal_holdout_contract"))
        elif kind == "dimensionless_transport_numerical_verification":
            if (detail.get("result_kind") != kind or detail.get("input_sha256") != receipt["input_sha256"]
                    or any(detail.get(flag) is not False for flag in
                           ("biological_measurements", "physiologically_calibrated", "human_gestation_prediction"))):
                raise ValueError
            method = detail.get("reference_method")
            levels = detail.get("convergence")
            count = detail.get("n_refinement_levels")
            total_points = detail.get("n_total_timepoints")
            if (not isinstance(method, str) or not method or len(method) > 1_000
                    or not isinstance(levels, list) or not 1 <= len(levels) <= 5
                    or isinstance(count, bool) or not isinstance(count, int) or count != len(levels)
                    or isinstance(total_points, bool) or not isinstance(total_points, int)
                    or not 1 <= total_points <= 100_000):
                raise ValueError
            checked_levels = []
            point_total = 0
            previous_factor = math.inf
            for item in levels:
                if not isinstance(item, dict):
                    raise ValueError
                factor = item.get("refinement_factor")
                requested_step = item.get("requested_step")
                actual_max_step = item.get("actual_max_step")
                intervals = item.get("n_intervals")
                timepoints = item.get("n_timepoints")
                if (isinstance(factor, bool) or not isinstance(factor, (int, float))
                        or not math.isfinite(factor) or not 0 < factor <= 1 or factor >= previous_factor
                        or isinstance(requested_step, bool) or not isinstance(requested_step, (int, float))
                        or not math.isfinite(requested_step) or requested_step <= 0
                        or isinstance(actual_max_step, bool) or not isinstance(actual_max_step, (int, float))
                        or not math.isfinite(actual_max_step) or actual_max_step <= 0
                        or actual_max_step > requested_step * (1 + 1e-9)
                        or isinstance(intervals, bool) or not isinstance(intervals, int) or intervals < 1
                        or isinstance(timepoints, bool) or not isinstance(timepoints, int)
                        or timepoints != intervals + 1):
                    raise ValueError
                previous_factor = factor
                point_total += timepoints
                for name in ("max_abs_interface_error", "max_abs_core_error",
                             "max_abs_state_error", "state_rmse"):
                    value = item.get(name)
                    if (isinstance(value, bool) or not isinstance(value, (int, float))
                            or not math.isfinite(value) or value < 0):
                        raise ValueError
                for name in ("error_ratio_from_previous", "observed_order"):
                    value = item.get(name)
                    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                              or not math.isfinite(value)):
                        raise ValueError
                checked_levels.append(item)
            if point_total != total_points:
                raise ValueError
            summary.update(reference_method=method, n_refinement_levels=count,
                           n_total_timepoints=total_points, convergence=checked_levels)
        elif kind == "dimensionless_mechanics_numerical_verification":
            required_outputs = {"mechanics_verification_report.json", "mechanics_pointwise_errors.csv",
                                "mechanics_boundary_errors.csv"}
            if (detail.get("result_kind") != kind or detail.get("input_sha256") != receipt["input_sha256"]
                    or any(detail.get(flag) is not False for flag in
                           ("biological_measurements", "physiologically_calibrated", "human_gestation_prediction"))
                    or not required_outputs.issubset(outputs)):
                raise ValueError
            method = detail.get("reference_method")
            points = detail.get("n_timepoints")
            boundaries = detail.get("n_load_boundaries")
            tolerance = detail.get("relative_tolerance")
            maximum_scaled_error = detail.get("maximum_scaled_error")
            errors = detail.get("errors")
            if (not isinstance(method, str) or not method or len(method) > 1_000
                    or isinstance(points, bool) or not isinstance(points, int) or not 1 <= points <= 100_000
                    or isinstance(boundaries, bool) or not isinstance(boundaries, int)
                    or not 0 <= boundaries <= min(points, 200)
                    or isinstance(tolerance, bool) or not isinstance(tolerance, (int, float))
                    or not math.isfinite(tolerance) or not 0 < tolerance <= 1e-6
                    or isinstance(maximum_scaled_error, bool)
                    or not isinstance(maximum_scaled_error, (int, float))
                    or not math.isfinite(maximum_scaled_error) or not 0 <= maximum_scaled_error <= tolerance
                    or detail.get("verification_passed") is not True or not isinstance(errors, dict)):
                raise ValueError
            checked_errors = {}
            for name in ("max_absolute", "rmse", "max_boundary_absolute"):
                value = errors.get(name)
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value) or value < 0):
                    raise ValueError
                checked_errors[name] = value
            summary.update(reference_method=method, n_timepoints=points,
                           n_load_boundaries=boundaries,
                           relative_tolerance=tolerance,
                           maximum_scaled_error=maximum_scaled_error,
                           verification_passed=True, errors=checked_errors)
        elif kind == "dimensionless_transport_parameter_matrix_numerical_verification":
            scenario_names = {"configured_baseline", "zero_dynamics", "exchange_only",
                              "transfer_only", "unequal_coupled", "high_mixing",
                              "near_degenerate"}
            required_outputs = {"transport_matrix_report.json", "transport_matrix_convergence.csv",
                                "transport_matrix_scenario_configs.json"}
            required_outputs.update(f"transport_{name}_finest_errors.csv" for name in scenario_names)
            if (detail.get("result_kind") != kind or detail.get("input_sha256") != receipt["input_sha256"]
                    or any(detail.get(flag) is not False for flag in
                           ("biological_measurements", "physiologically_calibrated", "human_gestation_prediction"))
                    or not required_outputs.issubset(outputs)):
                raise ValueError
            method = detail.get("reference_method")
            scenarios = detail.get("scenarios")
            count = detail.get("n_scenarios")
            levels = detail.get("n_refinement_levels")
            total_points = detail.get("n_total_timepoints")
            if (not isinstance(method, str) or not method or len(method) > 1_000
                    or not isinstance(scenarios, list) or len(scenarios) != 7
                    or isinstance(count, bool) or not isinstance(count, int) or count != len(scenarios)
                    or isinstance(levels, bool) or not isinstance(levels, int) or levels != 5
                    or isinstance(total_points, bool) or not isinstance(total_points, int)
                    or not 1 <= total_points <= 160_000):
                raise ValueError
            observed_names = set()
            point_sum = 0
            checked_scenarios = []
            for item in scenarios:
                if not isinstance(item, dict):
                    raise ValueError
                name = item.get("name")
                config_sha = item.get("config_sha256")
                rates = item.get("rates")
                if (name not in scenario_names or name in observed_names
                        or not isinstance(config_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", config_sha)
                        or not isinstance(rates, dict)
                        or set(rates) != {"boundary_exchange", "intercompartment_transport", "loss"}):
                    raise ValueError
                observed_names.add(name)
                for rate in rates.values():
                    if (isinstance(rate, bool) or not isinstance(rate, (int, float))
                            or not math.isfinite(rate) or rate < 0):
                        raise ValueError
                for field in ("requested_step", "stability_product",
                              "finest_actual_max_step", "finest_max_abs_state_error", "finest_state_rmse"):
                    value = item.get(field)
                    if (isinstance(value, bool) or not isinstance(value, (int, float))
                            or not math.isfinite(value) or value < 0):
                        raise ValueError
                if (item["requested_step"] <= 0 or item["finest_actual_max_step"] <= 0
                        or item["finest_actual_max_step"] > item["requested_step"] * (1 + 1e-9)
                        or item["stability_product"] > 1.0 + 1e-9):
                    raise ValueError
                points = item.get("n_total_timepoints")
                if (isinstance(points, bool) or not isinstance(points, int) or not 1 <= points <= 100_000):
                    raise ValueError
                point_sum += points
                checked_scenarios.append(item)
            if observed_names != scenario_names or point_sum != total_points:
                raise ValueError
            config_manifest_path = base / "transport_matrix_scenario_configs.json"
            if config_manifest_path.stat().st_size > 2_000_000:
                raise ValueError
            config_manifest = json.loads(config_manifest_path.read_text(encoding="utf-8"))
            manifest_scenarios = config_manifest.get("scenario_configs") if isinstance(config_manifest, dict) else None
            if (config_manifest.get("schema_version") != 1
                    or not isinstance(manifest_scenarios, list) or len(manifest_scenarios) != 7):
                raise ValueError
            manifest_hashes = {}
            for item in manifest_scenarios:
                if not isinstance(item, dict):
                    raise ValueError
                name = item.get("name")
                config_hash = item.get("config_sha256")
                config_text = item.get("config_json")
                if (name not in scenario_names or name in manifest_hashes
                        or not isinstance(config_hash, str)
                        or not re.fullmatch(r"[0-9a-f]{64}", config_hash)
                        or not isinstance(config_text, str) or len(config_text.encode("utf-8")) > 2_000_000
                        or hashlib.sha256(config_text.encode("utf-8")).hexdigest() != config_hash):
                    raise ValueError
                scenario_config = json.loads(config_text)
                if (not isinstance(scenario_config, dict)
                        or set(scenario_config) != {"schema_version", "fixture_notice", "context",
                                                    "dimensionless_time", "initial", "rates",
                                                    "boundary_concentration"}
                        or isinstance(scenario_config.get("schema_version"), bool)
                        or scenario_config.get("schema_version") != 1
                        or not isinstance(scenario_config.get("fixture_notice"), str)
                        or not 1 <= len(scenario_config["fixture_notice"]) <= 512):
                    raise ValueError
                context = scenario_config.get("context")
                if (not isinstance(context, dict)
                        or set(context) != {"stage_track", "species", "interval_label"}
                        or any(not isinstance(context[field], str) or len(context[field]) > 256
                               for field in ("stage_track", "species", "interval_label"))):
                    raise ValueError
                time_config = scenario_config.get("dimensionless_time")
                if not isinstance(time_config, dict) or set(time_config) != {"duration", "step"}:
                    raise ValueError
                duration, step = time_config["duration"], time_config["step"]
                if (isinstance(duration, bool) or not isinstance(duration, (int, float))
                        or not math.isfinite(duration) or duration <= 0
                        or isinstance(step, bool) or not isinstance(step, (int, float))
                        or not math.isfinite(step) or not 0 < step <= duration):
                    raise ValueError
                rates = scenario_config.get("rates")
                if not isinstance(rates, dict) or set(rates) != {
                        "boundary_exchange", "intercompartment_transport", "loss"}:
                    raise ValueError
                initial = scenario_config.get("initial")
                boundary_concentration = scenario_config.get("boundary_concentration")
                if (not isinstance(initial, dict) or set(initial) != {"interface", "core"}
                        or isinstance(boundary_concentration, bool)
                        or not isinstance(boundary_concentration, (int, float))
                        or not math.isfinite(boundary_concentration)):
                    raise ValueError
                if any(isinstance(value, bool) or not isinstance(value, (int, float))
                       or not math.isfinite(value) for value in initial.values()):
                    raise ValueError
                rate_sum = 0.0
                for value in rates.values():
                    if (isinstance(value, bool) or not isinstance(value, (int, float))
                            or not math.isfinite(value) or value < 0):
                        raise ValueError
                    rate_sum += value
                scenario_summary = next(value for value in checked_scenarios if value["name"] == name)
                if (config_hash != scenario_summary["config_sha256"]
                        or step != scenario_summary["requested_step"]
                        or rates != scenario_summary["rates"]
                        or not math.isclose(step * rate_sum, scenario_summary["stability_product"],
                                            rel_tol=1e-12, abs_tol=1e-15)
                        or (name != "configured_baseline" and step * rate_sum > 0.5 + 1e-9)
                        or sum(math.ceil(duration / (step * factor)) + 1
                               for factor in (1.0, 0.5, 0.25, 0.125, 0.0625)
                               ) != scenario_summary["n_total_timepoints"]):
                    raise ValueError
                manifest_hashes[name] = config_hash
            if manifest_hashes != {item["name"]: item["config_sha256"] for item in checked_scenarios}:
                raise ValueError
            if manifest_hashes.get("configured_baseline") != receipt["input_sha256"]:
                raise ValueError
            with (base / "transport_matrix_convergence.csv").open("r", encoding="utf-8", newline="") as stream:
                curve_rows = list(csv.DictReader(stream))
            curve_counts = {}
            if len(curve_rows) != 35:
                raise ValueError
            for row in curve_rows:
                name = row.get("scenario")
                factor = row.get("refinement_factor")
                if (name not in scenario_names or factor not in {"1.0", "0.5", "0.25", "0.125", "0.0625"}):
                    raise ValueError
                curve_counts[(name, factor)] = curve_counts.get((name, factor), 0) + 1
            if (len(curve_counts) != 35 or any(count != 1 for count in curve_counts.values())):
                raise ValueError
            summary.update(reference_method=method, n_scenarios=count,
                           n_refinement_levels=levels, n_total_timepoints=total_points,
                           scenarios=checked_scenarios)
        else:
            expected_result_kind = {
                "dimensionless_transport_theory": "dimensionless_two_compartment_transport",
                "dimensionless_mechanics_theory": "dimensionless_kelvin_voigt_mechanics",
            }[kind]
            if (detail.get("result_kind") != expected_result_kind
                    or any(detail.get(flag) is not False for flag in
                           ("biological_measurements", "physiologically_calibrated", "human_gestation_prediction"))
                    or not isinstance(detail.get("outputs"), dict)
                    or not isinstance(detail.get("alternative_model"), dict)
                    or not isinstance(detail.get("assumptions"), list)):
                raise ValueError
            summary.update(result_kind=detail["result_kind"], stage_context=detail.get("stage_context"),
                           outputs=detail["outputs"], alternative_model=detail["alternative_model"],
                           assumptions=detail["assumptions"])
        return {"bundle_id": path.name, "bundle_kind": kind,
                "label": ECTOGENESIS_BUNDLE_KINDS[kind],
                "verified": True,
                "input_sha256": receipt.get("input_sha256"),
                "package_version": receipt.get("package_version"),
                "python_version": receipt.get("python_version"),
                "implementation_sha256": receipt.get("implementation_sha256", {}),
                "outputs": sorted(outputs), "summary": summary}
    except (AttributeError, OSError, UnicodeError, TypeError, ValueError, OverflowError):
        return {"bundle_id": path.name, "verified": False,
                "label": "Artifact bundle requires review",
                "error": "Receipt, expected scope flags or output hashes did not validate."}


def ectogenesis_artifact_bundle_by_id(root, bundle_id):
    """Load one artifact only after validating its safe local identifier and receipt."""
    if (not isinstance(bundle_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,255}", bundle_id)
            or bundle_id in {".", ".."}):
        raise FileNotFoundError
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise FileNotFoundError
    bundle = ectogenesis_artifact_bundle(root / bundle_id)
    if bundle is None:
        raise FileNotFoundError
    if bundle.get("verified") is not True:
        raise ValueError("Selected artifact bundle did not pass receipt verification")
    return bundle


def ectogenesis_design_sweep_comparison(bundle_a, bundle_b, metric):
    """Compare summaries from compatible receipt-verified synthetic sweeps."""
    if metric not in ECTOGENESIS_SWEEP_METRICS:
        raise ValueError("Unsupported design-sweep metric")
    descriptor = ECTOGENESIS_SWEEP_METRICS[metric]
    if any(bundle.get("verified") is not True or
           bundle.get("bundle_kind") != "synthetic_exchange_design_sweep"
           for bundle in (bundle_a, bundle_b)):
        return {"compatible": False, "reason": "Choose two receipt-verified design-sweep bundles."}
    if bundle_a.get("bundle_id") == bundle_b.get("bundle_id"):
        return {"compatible": False, "reason": "Choose two different bundles."}
    if bundle_a.get("input_sha256") != bundle_b.get("input_sha256"):
        return {"compatible": False, "reason": "Input configuration hashes differ."}

    def index(bundle):
        result = {}
        for item in bundle.get("summary", {}).get("design_summaries", []):
            coordinate = (float(item["cadence_factor_requested"]),
                          float(item["noise_multiplier_requested"]),
                          item["monitor_fault_profile"], item.get("event_timing_profile"))
            if coordinate in result:
                return None
            result[coordinate] = item
        return result

    rows_a, rows_b = index(bundle_a), index(bundle_b)
    if not rows_a or not rows_b or rows_a.keys() != rows_b.keys():
        return {"compatible": False, "reason": "Design-condition coordinate sets differ."}

    count_key = descriptor["estimable_count"]
    rows = []
    for coordinate in sorted(rows_a, key=lambda item: (item[0], item[1], item[2], item[3] or "")):
        cadence, noise, fault_profile, timing_profile = coordinate
        left, right = rows_a[coordinate], rows_b[coordinate]
        value_a, value_b = left.get(metric), right.get(metric)
        delta = value_b - value_a if value_a is not None and value_b is not None else None
        rows.append({
            "coordinate": {"cadence_factor_requested": cadence,
                           "noise_multiplier_requested": noise,
                           "monitor_fault_profile": fault_profile,
                           "event_timing_profile": timing_profile},
            "value_a": value_a, "value_b": value_b, "delta_b_minus_a": delta,
            "estimable_a": left.get(count_key), "estimable_b": right.get(count_key),
            "replicates_a": left.get("replicates"), "replicates_b": right.get("replicates"),
        })
    return {
        "compatible": True, "metric": metric, "metric_label": descriptor["label"],
        "input_sha256": bundle_a["input_sha256"],
        "implementation_hashes_match": bundle_a.get("implementation_sha256") ==
                                        bundle_b.get("implementation_sha256"),
        "bundle_a": {"bundle_id": bundle_a["bundle_id"],
                     "package_version": bundle_a.get("package_version"),
                     "n_synthetic_runs": bundle_a["summary"].get("n_synthetic_runs")},
        "bundle_b": {"bundle_id": bundle_b["bundle_id"],
                     "package_version": bundle_b.get("package_version"),
                     "n_synthetic_runs": bundle_b["summary"].get("n_synthetic_runs")},
        "rows": rows,
        "interpretation": "Descriptive differences between report medians; runs are not pooled and no model ranking or biological inference is made.",
    }


def ectogenesis_artifacts(root=ECTOGENESIS_MODEL_ROOT):
    """Read a capped inventory from the dedicated read-only sibling mount."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        return {"available": False, "read_only": True, "bundles": [],
                "message": "Mount artificial-womb-models/artifacts at /lab/ectogenesis-models to display its local reports."}
    cards = []
    try:
        paths = sorted((entry for entry in root.iterdir() if entry.is_dir() and not entry.is_symlink()),
                       key=lambda entry: entry.name, reverse=True)[:50]
        for path in paths:
            card = ectogenesis_artifact_bundle(path)
            if card is not None:
                cards.append(card)
    except OSError:
        return {"available": False, "read_only": True, "bundles": [],
                "message": "The local model artifact directory is not readable."}
    return {"available": True, "read_only": True, "bundles": cards,
            "message": "Receipt hashes verify file integrity; they do not review scientific validity."}


def ectogenesis_artifact_file(root, bundle_id, filename):
    if (not isinstance(bundle_id, str) or bundle_id in {".", ".."}
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,255}", bundle_id)
            or not isinstance(filename, str) or not ECTOGENESIS_ARTIFACT_NAME.fullmatch(filename)):
        raise FileNotFoundError
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise FileNotFoundError
    bundle = root / bundle_id
    if bundle.is_symlink() or not bundle.is_dir():
        raise FileNotFoundError
    card = ectogenesis_artifact_bundle(bundle)
    if not card or not card.get("verified") or filename not in card.get("outputs", []):
        raise FileNotFoundError
    path = bundle / filename
    if path.is_symlink() or not path.is_file() or path.resolve(strict=True).parent != bundle.resolve(strict=True):
        raise FileNotFoundError
    if path.stat().st_size > 12_000_000:
        raise ValueError("Research artifact exceeds the display limit")
    return path.read_bytes(), mimetypes.guess_type(filename)[0] or "application/octet-stream"


class ProviderError(Exception):
    pass


def fetch_json(url, headers=None, body=None):
    """Only internal adapters supply URLs. Never return credential-bearing errors."""
    headers = {"User-Agent": regen.UA, "Accept": "application/json", **(headers or {})}
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode()
    for attempt in range(2):
        try:
            with urlopen(Request(url, headers=headers, data=payload), timeout=25) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ProviderError("Provider response exceeded 8 MiB")
            result = redact(json.loads(raw))
            if isinstance(result, dict) and (result.get("error") or result.get("errors")):
                raise ProviderError("Provider returned an error object")
            return result
        except HTTPError as exc:
            code = exc.code
            exc.close()
            if attempt == 0 and code in {429, 500, 502, 503, 504}:
                time.sleep(1)
                continue
            raise ProviderError(f"HTTP {code}; provider did not return usable data") from None
        except (URLError, OSError, TimeoutError):
            if attempt == 0:
                continue
            raise ProviderError("Network timeout or connection failure") from None
        except (ValueError, UnicodeError):
            raise ProviderError("Provider returned invalid JSON") from None


def hit(provider, title, url, date="", **extra):
    return {"provider": provider, "title": title or "Untitled record", "url": public_url(url or ""),
            "date": date or "", "evidence_type": "bibliographic record; design not reviewed", **extra}


def search_provider(provider, query, limit):
    key_name = PROVIDERS[provider][1]
    key = os.environ.get(key_name, "") if key_name else ""
    if PROVIDERS[provider][2] and not key:
        raise ProviderError("API key is not configured")
    if provider == "pubmed":
        base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        params = {"db": "pubmed", "retmode": "json", "tool": "regen-workbench", "email": regen.EMAIL}
        if key:
            params["api_key"] = key
        search = fetch_json(base + "esearch.fcgi?" + urlencode({**params, "term": query, "retmax": limit}))
        if "error" in search or "esearchresult" not in search:
            raise ProviderError("PubMed rejected the search")
        ids = search["esearchresult"].get("idlist", [])
        summaries = fetch_json(base + "esummary.fcgi?" + urlencode({**params, "id": ",".join(ids)})) if ids else {}
        rows = []
        for pmid in ids:
            item = summaries.get("result", {}).get(pmid, {})
            rows.append(hit(provider, item.get("title"), f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", item.get("pubdate"), pmid=pmid,
                            doi=next((a["value"] for a in item.get("articleids", []) if a.get("idtype") == "doi"), "")))
        return {"search": search, "summaries": summaries}, rows
    if provider == "europepmc":
        raw = fetch_json("https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urlencode({"query": query, "format": "json", "pageSize": limit, "resultType": "core"}))
        rows = [hit(provider, r.get("title"), f"https://europepmc.org/article/{r.get('source', 'MED')}/{r.get('id')}", r.get("firstPublicationDate"),
                    pmid=r.get("pmid", ""), doi=r.get("doi", ""), abstract=r.get("abstractText", ""),
                    publication_types=r.get("pubTypeList", {}).get("pubType", []), is_retracted=r.get("isRetracted", "unknown"))
                for r in raw.get("resultList", {}).get("result", [])]
        return raw, rows
    if provider == "openalex":
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        raw = fetch_json("https://api.openalex.org/works?" + urlencode({"search": query, "per-page": limit, "mailto": regen.EMAIL}), headers)
        rows = [hit(provider, r.get("display_name"), r.get("doi") or r.get("id"), r.get("publication_date"),
                    doi=r.get("doi") or "", publication_types=[r.get("type")], is_retracted=r.get("is_retracted")) for r in raw.get("results", [])]
        return raw, rows
    if provider == "trials":
        raw = fetch_json("https://clinicaltrials.gov/api/v2/studies?" + urlencode({"query.term": query, "pageSize": limit, "format": "json"}))
        rows = []
        for study in raw.get("studies", []):
            p = study.get("protocolSection", {})
            ident, status, design = p.get("identificationModule", {}), p.get("statusModule", {}), p.get("designModule", {})
            rows.append(hit(provider, ident.get("briefTitle"), f"https://clinicaltrials.gov/study/{ident.get('nctId')}", status.get("lastUpdatePostDateStruct", {}).get("date"),
                            evidence_type="trial registry; registration is not a result", status=status.get("overallStatus"), phases=design.get("phases", []),
                            enrollment=design.get("enrollmentInfo", {}), has_results=study.get("hasResults", False)))
        return raw, rows
    if provider == "semantic":
        raw = fetch_json("https://api.semanticscholar.org/graph/v1/paper/search?" + urlencode({"query": query, "limit": limit, "fields": "title,url,year,abstract,externalIds,publicationTypes"}), {"x-api-key": key} if key else {})
        return raw, [hit(provider, r.get("title"), r.get("url"), str(r.get("year") or ""), abstract=r.get("abstract") or "",
                         doi=(r.get("externalIds") or {}).get("DOI", ""), pmid=(r.get("externalIds") or {}).get("PubMed", ""),
                         publication_types=r.get("publicationTypes") or []) for r in raw.get("data", [])]
    if provider == "core":
        raw = fetch_json("https://api.core.ac.uk/v3/search/works?" + urlencode({"q": query, "limit": limit}), {"Authorization": f"Bearer {key}"})
        return raw, [hit(provider, r.get("title"), r.get("downloadUrl") or f"https://core.ac.uk/works/{r.get('id')}", str(r.get("yearPublished") or ""),
                         doi=r.get("doi") or "", abstract=r.get("abstract") or "") for r in raw.get("results", [])]
    if provider == "brave":
        raw = fetch_json("https://api.search.brave.com/res/v1/web/search?" + urlencode({"q": query, "count": limit}), {"X-Subscription-Token": key})
        return raw, [hit(provider, r.get("title"), r.get("url"), r.get("age", ""), snippet=r.get("description", ""),
                         evidence_type="web lead; claim and source type unreviewed") for r in raw.get("web", {}).get("results", [])]
    raw = fetch_json("https://api.exa.ai/search", {"x-api-key": key}, {"query": query, "numResults": limit, "type": "auto"})
    return raw, [hit(provider, r.get("title"), r.get("url"), r.get("publishedDate", ""), evidence_type="web lead; claim and source type unreviewed") for r in raw.get("results", [])]


def molecule(smiles):
    from rdkit import Chem
    if not isinstance(smiles, str) or not 1 <= len(smiles) <= 2000:
        raise ValueError("SMILES must contain 1-2000 characters")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("Invalid SMILES")
    if mol.GetNumHeavyAtoms() > 100 or len(Chem.GetMolFrags(mol)) != 1:
        raise ValueError("This workspace computes connected small molecules with at most 100 heavy atoms; large peptides retain database records only")
    return mol


def describe(mol, parent=None):
    from rdkit import Chem, DataStructs
    from rdkit.Chem import Crippen, Descriptors, FilterCatalog, Lipinski, rdFingerprintGenerator
    catalog = FilterCatalog.FilterCatalogParams()
    catalog.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS)
    alerts = FilterCatalog.FilterCatalog(catalog).GetMatches(mol)
    row = {"smiles": Chem.MolToSmiles(mol, isomericSmiles=True), "mw": round(Descriptors.MolWt(mol), 3),
           "logp": round(Crippen.MolLogP(mol), 3), "tpsa": round(Descriptors.TPSA(mol), 3),
           "hbd": Lipinski.NumHDonors(mol), "hba": Lipinski.NumHAcceptors(mol), "rotatable": Lipinski.NumRotatableBonds(mol),
           "pains": [a.GetDescription() for a in alerts], "unspecified_stereo": sum(str(s.specified) == "Unspecified" for s in Chem.FindPotentialStereo(mol))}
    if parent is not None:
        fp = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048, includeChirality=True)
        row["similarity"] = round(DataStructs.TanimotoSimilarity(fp.GetFingerprint(mol), fp.GetFingerprint(parent)), 4)
    return row


def enumerate_variants(parent):
    """Bounded single substitutions at aromatic C-H sites; RDKit sanitizes products."""
    from rdkit import Chem
    seen = {Chem.MolToSmiles(parent)}
    results = []
    for atom in parent.GetAtoms():
        if atom.GetAtomicNum() != 6 or not atom.GetIsAromatic() or atom.GetTotalNumHs() != 1:
            continue
        for element, label in ((9, "fluoro"), (6, "methyl"), (8, "hydroxy")):
            edit = Chem.RWMol(parent)
            anchor = edit.GetAtomWithIdx(atom.GetIdx())
            anchor.SetNumExplicitHs(0)
            anchor.SetNoImplicit(True)
            added = edit.AddAtom(Chem.Atom(element))
            edit.AddBond(atom.GetIdx(), added, Chem.BondType.SINGLE)
            product = edit.GetMol()
            try:
                Chem.SanitizeMol(product)
                smiles = Chem.MolToSmiles(product, isomericSmiles=True)
                molecule(smiles)
            except (ValueError, RuntimeError):
                continue
            if smiles not in seen:
                seen.add(smiles)
                results.append((product, f"{label} at parent atom {atom.GetIdx()}"))
            if len(results) == 18:
                return results
    return results


class Desk:
    def __init__(self, root=None, recover_pending=False):
        self.root = Path(root) if root else regen.DATA / "research-desk"
        self.runs = self.root / "runs"
        self.runs.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.pending = 0
        self._docking_status_cache = None
        self.store_path = self.root / "workspace.json"
        seeds = json.loads((HOME / "config" / "research-blueprints.json").read_text(encoding="utf-8"))
        self.seed_findings = seeds.get("findings", [])
        self.store = json.loads(self.store_path.read_text(encoding="utf-8")) if self.store_path.exists() else {"blueprints": seeds["blueprints"], "notes": [], "campaigns": []}
        self.store.setdefault("campaigns", [])
        self.store.setdefault("notes", [])
        self.campaign_frameworks = seeds.get("campaign_frameworks", {})
        self.campaign_starters = seeds.get("campaign_starters", {})
        known = {item["id"] for item in self.store["blueprints"]}
        added = [item for item in seeds["blueprints"] if item["id"] not in known]
        self.store["blueprints"].extend(added)
        priority = seeds.get("focus_order", [item["id"] for item in seeds["blueprints"]])
        rank = {area_id: index for index, area_id in enumerate(priority)}
        ordered = sorted(self.store["blueprints"], key=lambda item: rank.get(item["id"], len(rank)))
        if added or ordered != self.store["blueprints"]:
            self.store["blueprints"] = ordered
            self.save_store()
        for path in self.runs.glob("*/run.json") if recover_pending else []:
            run = json.loads(path.read_text())
            if run["status"] in {"queued", "running"}:
                run.update(status="interrupted", error="Server restarted before completion; submit a new run")
                self.save_run(path.parent, run)

    def save_store(self):
        temp = self.store_path.with_suffix(".tmp")
        write_json(temp, redact(self.store))
        temp.replace(self.store_path)

    def blueprint(self, data):
        item = {k: text_field(data, k) for k in BLUEPRINT_FIELDS}
        if not item["title"]:
            raise ValueError("Blueprint title is required")
        supplied_id = text_field(data, "id", maximum=64)
        with self.lock:
            old = next((x for x in self.store["blueprints"] if x["id"] == supplied_id), None)
            item.update(id=old["id"] if old else uuid.uuid4().hex, updated_utc=regen.now())
            if old:
                self.store["blueprints"][self.store["blueprints"].index(old)] = item
            else:
                self.store["blueprints"].append(item)
            self.save_store()
        return item

    def campaign(self, data):
        item = {key: text_field(data, key, maximum=4000) for key in CAMPAIGN_FIELDS}
        item["blueprint_id"] = text_field(data, "blueprint_id", maximum=64)
        supplied_id = text_field(data, "id", maximum=64)
        if not item["title"] or not item["target"] or not item["hypothesis"]:
            raise ValueError("Campaign title, target and hypothesis are required")
        blueprint = next((b for b in self.store["blueprints"] if b["id"] == item["blueprint_id"]), None)
        if blueprint is None:
            raise ValueError("Unknown blueprint")
        if item["reference_url"] and not public_url(item["reference_url"]):
            raise ValueError("Reference source must be an http(s) URL")
        starters = self.campaign_starters.get(item["blueprint_id"], [])
        if item["starter_id"] and item["starter_id"] not in {starter["id"] for starter in starters}:
            raise ValueError("Unknown campaign starter for this blueprint")
        if item["receptor"]:
            receptor = campaign_structure_path(item["receptor"], "Receptor")
            item["receptor"] = receptor.relative_to(regen.ROOT).as_posix()
        if not isinstance(data.get("experiment_ids", []), list) or not isinstance(data.get("model_bundle_ids", []), list):
            raise ValueError("Linked experiment and model bundle IDs must be lists")
        experiment_ids = data.get("experiment_ids", [])
        model_bundle_ids = data.get("model_bundle_ids", [])
        if len(experiment_ids) > 20 or len(model_bundle_ids) > 20:
            raise ValueError("A campaign may link at most 20 experiment cards and 20 model bundles")
        experiment_ids = [text_field({"id": value}, "id", maximum=96) for value in experiment_ids]
        model_bundle_ids = [text_field({"id": value}, "id", maximum=255) for value in model_bundle_ids]
        if len(set(experiment_ids)) != len(experiment_ids) or len(set(model_bundle_ids)) != len(model_bundle_ids):
            raise ValueError("Linked experiment and model bundle IDs must be unique")
        if experiment_ids:
            valid_ids = {record["experiment_id"] for record in self.experiments()["experiments"]
                         if record["validation_status"] == "valid"}
            if set(experiment_ids) - valid_ids:
                raise ValueError("Campaign links must reference currently valid experiment cards")
        if model_bundle_ids:
            verified_ids = {record["bundle_id"] for record in ectogenesis_artifacts(ECTOGENESIS_MODEL_ROOT).get("bundles", [])
                            if record.get("verified") is True}
            if set(model_bundle_ids) - verified_ids:
                raise ValueError("Campaign links must reference currently receipt-verified model bundles")
        center = [bounded_number(data.get(f"center_{axis}", 0), -10000, 10000, f"Box center {axis}") for axis in "xyz"]
        size = [bounded_number(data.get(f"size_{axis}", 20), 1, 80, f"Box size {axis}") for axis in "xyz"]
        with self.lock:
            old = next((x for x in self.store["campaigns"] if x["id"] == supplied_id), None)
            if old and old["blueprint_id"] != item["blueprint_id"]:
                raise ValueError("A campaign cannot be moved to another blueprint")
            previous_evidence = {entry.get("axis_id"): entry for entry in (old or {}).get("evidence", [])}
            incoming_evidence = data.get("evidence")
            if incoming_evidence is None:
                incoming_evidence = list(previous_evidence.values())
            if not isinstance(incoming_evidence, list):
                raise ValueError("Campaign evidence must be a list")
            submitted_evidence = {}
            for entry in incoming_evidence:
                if not isinstance(entry, dict):
                    raise ValueError("Each evidence entry must be an object")
                axis_id = text_field(entry, "axis_id", maximum=64)
                if axis_id in submitted_evidence:
                    raise ValueError("Evidence axes must be unique")
                submitted_evidence[axis_id] = entry
            framework = self.campaign_frameworks.get(item["blueprint_id"], [])
            known_axes = {axis["id"] for axis in framework}
            if set(submitted_evidence) - known_axes:
                raise ValueError("Evidence contains an axis not defined for this blueprint")
            evidence = []
            for axis in framework:
                entry = submitted_evidence.get(axis["id"], {})
                status = text_field(entry, "status", "not assessed", 64) or "not assessed"
                if status not in EVIDENCE_STATUS:
                    raise ValueError(f"Unknown evidence status for {axis['label']}")
                saved = {"axis_id": axis["id"], "status": status}
                for field in EVIDENCE_FIELDS[1:]:
                    saved[field] = text_field(entry, field, maximum=3000)
                if saved["source_url"] and not public_url(saved["source_url"]):
                    raise ValueError(f"Evidence source for {axis['label']} must be an http(s) URL")
                evidence.append(saved)
            incoming_records = data.get("evidence_records", (old or {}).get("evidence_records", []))
            if not isinstance(incoming_records, list) or len(incoming_records) > 100:
                raise ValueError("Campaign source observations must be a list of at most 100 records")
            evidence_records = []
            record_ids = set()
            for index, entry in enumerate(incoming_records):
                if not isinstance(entry, dict):
                    raise ValueError("Each source observation must be an object")
                axis_id = text_field(entry, "axis_id", maximum=64)
                if axis_id not in known_axes:
                    raise ValueError(f"Source observation {index + 1} references an unknown evidence axis")
                record = {"axis_id": axis_id}
                for field in EVIDENCE_RECORD_FIELDS:
                    record[field] = text_field(entry, field, maximum=3000 if field in {"notes", "source_url"} else 800)
                if record["source_type"] not in {"publication", "preprint", "dataset", "trial_registry", "patent", "protocol", "other"}:
                    raise ValueError(f"Source observation {index + 1} has an unknown source type")
                if record["status"] not in EVIDENCE_STATUS:
                    raise ValueError(f"Source observation {index + 1} has an unknown source status")
                if record["direction"] not in {"supports", "contradicts", "mixed", "unclear"}:
                    raise ValueError(f"Source observation {index + 1} has an unknown direction")
                if not record["source_title"] and not record["source_url"]:
                    raise ValueError(f"Source observation {index + 1} needs a title or source URL")
                if record["source_url"] and not public_url(record["source_url"]):
                    raise ValueError(f"Source observation {index + 1} URL must be http(s)")
                digest = record["dataset_sha256"]
                if digest and not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
                    raise ValueError(f"Source observation {index + 1} dataset hash must be a SHA-256 digest")
                record["record_id"] = text_field(entry, "record_id", maximum=64) or uuid.uuid4().hex
                if not re.fullmatch(r"[a-f0-9]{32}", record["record_id"]) or record["record_id"] in record_ids:
                    raise ValueError(f"Source observation {index + 1} has an invalid or duplicate record ID")
                record_ids.add(record["record_id"])
                evidence_records.append(record)
            item.update(
                id=old["id"] if old else uuid.uuid4().hex,
                evidence=evidence,
                evidence_records=evidence_records,
                experiment_ids=experiment_ids,
                model_bundle_ids=model_bundle_ids,
                center=center,
                size=size,
                created_utc=old["created_utc"] if old else regen.now(),
                updated_utc=regen.now(),
            )
            if old:
                self.store["campaigns"][self.store["campaigns"].index(old)] = item
            else:
                self.store["campaigns"].append(item)
            self.save_store()
        return item

    def note(self, data):
        item = {k: text_field(data, k) for k in ("blueprint_id", "title", "url", "claim", "species", "confounders")}
        kind = text_field(data, "kind")
        direction = text_field(data, "direction")
        if kind not in {"anecdote", "vendor claim", "personal observation", "paper", "preprint", "other"}:
            raise ValueError("Unknown source kind")
        if direction not in {"supports", "contradicts", "mixed", "unclear"}:
            raise ValueError("Unknown claim direction")
        if not item["claim"] or (item["url"] and not public_url(item["url"])):
            raise ValueError("Supply a claim and a valid http(s) source URL, when known")
        if not any(b["id"] == item["blueprint_id"] for b in self.store["blueprints"]):
            raise ValueError("Unknown blueprint")
        item.update(id=uuid.uuid4().hex, kind=kind, direction=direction, review_status="unreviewed", recorded_utc=regen.now(), origin="manually entered; URL not fetched")
        with self.lock:
            self.store["notes"].append(item)
            self.save_store()
        return item

    def state(self):
        with self.lock:
            runs = [json.loads(p.read_text()) for p in self.runs.glob("*/run.json")]
            runs.sort(key=lambda r: r["created_utc"], reverse=True)
            tools = self.docking_tool_status()
            return {**self.store, "findings": self.seed_findings, "runs": [{k: r.get(k) for k in ("id", "kind", "blueprint_id", "campaign_id", "created_utc", "status", "error", "summary")} for r in runs[:100]],
                    "providers": [{"id": k, "name": v[0], "key_configured": bool(os.environ.get(v[1], "")) if v[1] else None, "key_required": v[2]} for k, v in PROVIDERS.items()],
                    "campaign_frameworks": self.campaign_frameworks,
                    "campaign_starters": self.campaign_starters,
                    "rdkit_available": importlib.util.find_spec("rdkit") is not None,
                    "docking_tools": {"vina": tools["vina"]["available"], "gnina": tools["gnina"]["available"], "details": tools}}

    def docking_tool_status(self, force=False):
        vina_path = shutil.which("vina")
        gnina_path = regen.CACHE / "gnina" / "gnina"
        fingerprint = (vina_path, (gnina_path.stat().st_size, gnina_path.stat().st_mtime_ns) if gnina_path.is_file() else None)
        cached = self._docking_status_cache
        if not force and cached and cached[0] == fingerprint and time.monotonic() - cached[1] < 30:
            return cached[2]
        current = {
            "vina": regen.probe_executable(vina_path),
            "gnina": regen.probe_executable(gnina_path if gnina_path.is_file() else None, regen.GNINA_ASSET_SHA256),
        }
        if not gnina_path.is_file():
            current["gnina"]["error"] = "not installed in the research runtime"
        self._docking_status_cache = (fingerprint, time.monotonic(), current)
        return current

    def run_page(self, blueprint_id, offset=0, limit=50):
        with self.lock:
            rows = [json.loads(p.read_text()) for p in self.runs.glob("*/run.json")]
        rows = sorted((r for r in rows if r.get("blueprint_id") == blueprint_id), key=lambda r: r["created_utc"], reverse=True)
        summaries = [{k: r.get(k) for k in ("id", "kind", "blueprint_id", "campaign_id", "created_utc", "status", "error", "summary")} for r in rows[offset:offset + limit]]
        return {"runs": summaries, "offset": offset, "limit": limit, "total": len(rows)}

    def experiments(self):
        """List validated experiment records discoverable under studies/ only."""
        studies_root = (HOME / "studies").resolve()
        cards = []
        validator = experiment_manifest_tools()
        for path in sorted((HOME / "studies").glob("**/experiment.json")):
            if len(cards) >= 100 or path.is_symlink():
                continue
            try:
                manifest_path = path.resolve(strict=True)
                manifest_path.relative_to(studies_root)
                document = validator.validate_experiment_manifest(manifest_path, repo_root=HOME)
                artifacts = {artifact["id"]: artifact for artifact in document["artifacts"]}
                summary = None
                annotation_pilots = []
                annotation_reviews = []
                tables = []
                result_id = document["modeling"].get("result_artifact_id")
                result_artifact = artifacts.get(result_id)
                if result_artifact and result_artifact["kind"] == "analysis_output":
                    raw = validator._artifact_bytes(HOME, document["repository_id"], result_artifact)
                    if raw is not None and len(raw) <= 2_000_000:
                        try:
                            summary = json.loads(raw.decode("utf-8"))
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            summary = None
                for artifact in document["artifacts"]:
                    if (artifact.get("repository") != document["repository_id"]
                            or artifact.get("kind") != "analysis_output"
                            or not artifact.get("id", "").startswith("organoid-pilot-plan-")):
                        continue
                    raw = validator._artifact_bytes(HOME, document["repository_id"], artifact)
                    if raw is None or len(raw) > 1_000_000:
                        continue
                    try:
                        pilot_plan = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    if not isinstance(pilot_plan, dict):
                        continue
                    selection = pilot_plan.get("selection")
                    if (pilot_plan.get("schema_version") != 1 or not isinstance(selection, dict)
                            or pilot_plan.get("masks_generated") is not False
                            or pilot_plan.get("biological_results_generated") is not False):
                        continue
                    annotation_pilots.append({
                        "pilot_id": str(pilot_plan.get("pilot_id", "unidentified pilot"))[:120],
                        "purpose": str(pilot_plan.get("purpose", ""))[:300],
                        "timepoint_h": selection.get("timepoint_h"),
                        "n_unique_frames": selection.get("n_unique_frames"),
                        "n_round1_tasks": selection.get("n_round1_tasks"),
                        "n_round2_concealed_repeat_tasks": selection.get("n_round2_concealed_repeat_tasks"),
                        "n_total_tasks": selection.get("n_total_tasks"),
                        "n_development_source_groups_represented": selection.get("n_development_source_groups_represented"),
                        "final_test_group_excluded": selection.get("final_test_group_excluded") is True,
                        "blinding_limit": str(pilot_plan.get("blinding_limit", ""))[:500],
                    })
                for artifact in document["artifacts"]:
                    artifact_id = artifact.get("id", "")
                    prefix = "organoid-review-audit-report-"
                    if (artifact.get("repository") != document["repository_id"]
                            or artifact.get("kind") != "analysis_output"
                            or not artifact_id.startswith(prefix)):
                        continue
                    raw = validator._artifact_bytes(HOME, document["repository_id"], artifact)
                    if raw is None or len(raw) > 1_000_000:
                        continue
                    try:
                        report = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    audit_id = artifact_id[len(prefix):]
                    if (not isinstance(report, dict) or report.get("schema_version") != 1
                            or report.get("activity") != "manual_annotation_repeat_audit"
                            or report.get("audit_id") != audit_id
                            or report.get("biological_results_generated") is not False
                            or not isinstance(report.get("n_annotated_tasks"), int)
                            or isinstance(report.get("n_annotated_tasks"), bool)
                            or not isinstance(report.get("n_repeat_pairs_scored"), int)
                            or isinstance(report.get("n_repeat_pairs_scored"), bool)
                            or not isinstance(report.get("n_repeat_pairs_with_distinct_annotator_ids"), int)
                            or isinstance(report.get("n_repeat_pairs_with_distinct_annotator_ids"), bool)):
                        continue
                    annotation_reviews.append({
                        "audit_id": audit_id,
                        "n_annotated_tasks": report["n_annotated_tasks"],
                        "n_repeat_pairs_scored": report["n_repeat_pairs_scored"],
                        "n_repeat_pairs_with_distinct_annotator_ids": report[
                            "n_repeat_pairs_with_distinct_annotator_ids"],
                        "annotation_review_needed": report.get("annotation_review_needed") is True,
                        "interpretation": str(report.get("interpretation", ""))[:600],
                    })
                for artifact in document["artifacts"]:
                    if (artifact.get("repository") != document["repository_id"]
                            or Path(artifact.get("member_path", artifact["path"])).suffix.lower() != ".csv"
                            or artifact["kind"] not in {"raw_assay_data", "analysis_output"}):
                        continue
                    raw = validator._artifact_bytes(HOME, document["repository_id"], artifact)
                    if raw is None or len(raw) > 2_000_000:
                        continue
                    try:
                        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
                        columns = (reader.fieldnames or [])[:24]
                        rows = []
                        total_rows = 0
                        for row in reader:
                            total_rows += 1
                            if len(rows) < 100:
                                rows.append({key: row.get(key, "") or "Not reported" for key in columns})
                        if columns:
                            tables.append({"artifact_id": artifact["id"], "columns": columns, "rows": rows,
                                           "total_rows": total_rows, "truncated": total_rows > len(rows)})
                    except (UnicodeDecodeError, csv.Error):
                        continue
                cards.append({
                    "experiment_id": document["experiment_id"],
                    "title": document["title"],
                    "question": document["question"],
                    "model_system": document["scope"]["model_system"],
                    "claim_boundary": document["scope"]["claim_boundary"],
                    "design": document["design"],
                    "developmental_context": document.get("developmental_context"),
                    "assays": document["assays"],
                    "validation_endpoints": document.get("validation_endpoints", []),
                    "modeling": document["modeling"],
                    "calibration": document["calibration"],
                    "environmental_conditions": document.get("environmental_conditions", []),
                    "analysis_history": document.get("analysis_history", []),
                    "current_analysis_by_kind": document.get("current_analysis_by_kind", {}),
                    "limitations": document["limitations"],
                    "artifacts": [{"id": item["id"], "kind": item["kind"], "description": item["description"],
                                   "uri": item.get("uri"), "local": item.get("repository") == document["repository_id"],
                                   "previewable": item.get("repository") == document["repository_id"]
                                   and Path(item.get("member_path", item["path"])).suffix.lower()
                                   in {".json", ".csv", ".md", ".txt", ".pdf", ".xlsx", ".png"}}
                                  for item in document["artifacts"]],
                    "summary": summary,
                    "annotation_pilots": annotation_pilots,
                    "annotation_reviews": annotation_reviews,
                    "tables": tables,
                    "manifest_path": manifest_path.relative_to(HOME).as_posix(),
                    "validation_status": "valid",
                })
            except Exception as exc:
                fallback = {}
                try:
                    fallback = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    pass
                cards.append({"experiment_id": fallback.get("experiment_id", path.parent.name),
                              "title": fallback.get("title", path.parent.name),
                              "manifest_path": path.relative_to(HOME).as_posix(),
                              "validation_status": "invalid",
                              "validation_error": str(exc)[:1000]})
        return {"experiments": cards, "count": len(cards),
                "discovery_scope": "Validated experiment.json files beneath studies/ only; linked local artifacts must match declared hashes and byte counts."}

    def experiment_artifact(self, experiment_id, artifact_id):
        """Read one declared local artifact from a currently valid study manifest."""
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,95}", experiment_id):
            raise ValueError("Invalid experiment ID")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,63}", artifact_id):
            raise ValueError("Invalid artifact ID")
        studies_root = (HOME / "studies").resolve()
        validator = experiment_manifest_tools()
        for path in studies_root.glob("**/experiment.json"):
            if path.is_symlink():
                continue
            try:
                manifest_path = path.resolve(strict=True)
                manifest_path.relative_to(studies_root)
                document = validator.validate_experiment_manifest(manifest_path, repo_root=HOME)
            except Exception:
                continue
            if document["experiment_id"] != experiment_id:
                continue
            artifact = next((item for item in document["artifacts"] if item["id"] == artifact_id), None)
            if artifact is None or artifact.get("repository") != document["repository_id"]:
                raise ValueError("Artifact is not a declared local artifact for this experiment")
            content = validator._artifact_bytes(HOME, document["repository_id"], artifact)
            if content is None or len(content) > 20_000_000:
                raise ValueError("Artifact is unavailable or exceeds the 20 MB preview limit")
            suffix = Path(artifact.get("member_path", artifact["path"])).suffix.lower()
            if suffix not in {".json", ".csv", ".md", ".txt", ".pdf", ".xlsx", ".png"}:
                raise ValueError("Artifact type is not available through the research view")
            return content, mimetypes.guess_type("artifact" + suffix)[0] or "application/octet-stream"
        raise ValueError("Unknown or invalid experiment")

    def save_run(self, path, run):
        with self.lock:
            temp = path / "run.tmp"
            write_json(temp, redact(run))
            temp.replace(path / "run.json")

    def run(self, run_id):
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise ValueError("Invalid run ID")
        with self.lock:
            path = self.runs / run_id
            result = json.loads((path / "run.json").read_text())
            result["artifacts"] = {name: (path / name).is_file() for name in ("submission.json", "manifest.json", "result.json")}
            return result

    def submit(self, data):
        kind = data.get("kind")
        if kind not in KINDS:
            raise ValueError("Unknown job type")
        blueprint_id = text_field(data, "blueprint_id", maximum=64)
        if not any(b["id"] == blueprint_id for b in self.store["blueprints"]):
            raise ValueError("Unknown blueprint")
        params = {"kind": kind, "blueprint_id": blueprint_id}
        campaign_id = text_field(data, "campaign_id", maximum=64)
        campaign = next((c for c in self.store["campaigns"] if c["id"] == campaign_id and c["blueprint_id"] == blueprint_id), None) if campaign_id else None
        if campaign_id and campaign is None:
            raise ValueError("Unknown campaign for this blueprint")
        if kind == "docking":
            if campaign is None:
                raise ValueError("Save or select a campaign before docking")
            engine = text_field(data, "engine", maximum=16)
            if engine not in {"vina", "gnina"}:
                raise ValueError("Docking engine must be Vina or GNINA")
            tool_status = self.docking_tool_status(force=True)[engine]
            if not tool_status["available"]:
                raise ValueError(f"{engine.upper()} is unavailable: {tool_status['error']}")
            receptor = campaign_structure_path(campaign["receptor"], "Receptor") if campaign["receptor"] else None
            if receptor is None:
                raise ValueError("Add a prepared receptor .pdbqt file to the campaign first")
            ligand = campaign_structure_path(text_field(data, "ligand", maximum=1000), "Ligand")
            role = text_field(data, "role", maximum=32)
            if role not in {"candidate", "known_active", "known_inactive", "reference_pose"}:
                raise ValueError("Choose candidate, known active, known inactive or reference pose")
            params.update(
                engine=engine,
                receptor=receptor.relative_to(regen.ROOT).as_posix(),
                ligand=ligand.relative_to(regen.ROOT).as_posix(),
                label=text_field(data, "label", maximum=200),
                role=role,
                center=campaign["center"],
                size=campaign["size"],
                exhaustiveness=bounded_int(data.get("exhaustiveness", 8), 1, 32),
                num_modes=bounded_int(data.get("num_modes", 9), 1, 20),
                cpu=bounded_int(data.get("cpu", 4), 1, 8),
                seed=bounded_int(data.get("seed", 42), 1, 2147483647),
            )
        elif kind == "search":
            params["query"] = text_field(data, "query", maximum=500)
            providers = data.get("providers", ["pubmed", "europepmc", "trials"])
            if not isinstance(providers, list) or not providers or len(providers) > 8 or any(not isinstance(p, str) or p not in PROVIDERS for p in providers):
                raise ValueError("Select 1-8 known providers")
            if not params["query"]:
                raise ValueError("Search query is required")
            params.update(providers=list(dict.fromkeys(providers)), limit=bounded_int(data.get("limit", 5), 1, 10))
        elif kind in {"compound", "neighbors"}:
            params["name"] = text_field(data, "name", maximum=200)
            if not params["name"]:
                raise ValueError("Compound name or CID is required")
            params["threshold"] = bounded_int(data.get("threshold", 90), 80, 99)
        else:
            params["smiles"] = text_field(data, "smiles", maximum=2000)
            molecule(params["smiles"])
            if kind == "compare":
                params["candidate"] = text_field(data, "candidate", maximum=2000)
                molecule(params["candidate"])
            if kind == "conformers":
                params.update(seed=bounded_int(data.get("seed", 42), 0, 2147483647), conformers=bounded_int(data.get("conformers", 5), 1, 10), max_iters=500)
            if kind == "variants":
                params["max_mw"] = bounded_int(data.get("max_mw", 600), 50, 2000)
                params["max_tpsa"] = bounded_int(data.get("max_tpsa", 160), 0, 500)
        if campaign_id:
            params["campaign_id"] = campaign_id
        with self.lock:
            if self.pending >= 8:
                raise ValueError("Queue is full; wait for current runs")
            self.pending += 1
            run_id = uuid.uuid4().hex
            path = self.runs / run_id
            path.mkdir()
            created = regen.now()
            blueprint = next(b for b in self.store["blueprints"] if b["id"] == blueprint_id)
            context = {"schema_version": 1, "submitted_utc": created, "blueprint": blueprint, "campaign": campaign, "parameters": params}
            snapshot_bytes = json.dumps(redact(context), ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
            (path / "submission.json").write_bytes(snapshot_bytes)
            run = {"id": run_id, "kind": kind, "blueprint_id": blueprint_id, "campaign_id": campaign_id or None, "created_utc": created, "status": "queued", "parameters": params, "submission_sha256": hashlib.sha256(snapshot_bytes).hexdigest()}
            self.save_run(path, run)
            self.executor.submit(self.execute, path, run)
        return run

    def snapshot(self, path, provider, raw):
        file = path / f"{provider}.json"
        write_json(file, redact(raw))
        receipt = regen.record("desk-fetch", {"provider": provider, "run_id": path.name, "snapshot": "JSON reserialized with configured credentials redacted"}, [file])
        return {"file": file.name, "sha256": regen.sha256_file(file), "receipt": receipt.name}

    def chemical_rows(self, path, pairs, parent=None):
        from rdkit.Chem import Draw
        rows = []
        for index, (mol, label) in enumerate(pairs):
            row = {"label": label, **describe(mol, parent)}
            filename = f"molecule-{index}.png"
            Draw.MolToImage(mol, size=(520, 320)).save(path / filename)
            row["image"] = f"/api/artifact/{path.name}/{filename}"
            rows.append(row)
        return rows

    def compute(self, path, params):
        from rdkit import Chem, rdBase
        kind = params["kind"]
        parent = molecule(params["smiles"])
        common = {"rdkit_version": rdBase.rdkitVersion, "fingerprint": "Morgan radius=2, 2048 bits, chirality enabled", "interpretation": "Computed properties and structural hypotheses; no measured activity, safety, brain exposure or rejuvenation prediction"}
        if kind == "conformers":
            with (path / "input.csv").open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "smiles"])
                writer.writerow(["candidate", Chem.MolToSmiles(parent)])
            compound_screen(["--input", str(path / "input.csv"), "--out", str(path / "conformers"), "--conformers", str(params["conformers"]), "--seed", str(params["seed"]), "--max-iters", "500"], regen.record)
            result = json.loads((path / "conformers" / "compounds.json").read_text())
            return {**common, **result, "molecules": self.chemical_rows(path, [(parent, "Input molecule")]),
                    "interpretation": "ETKDGv3 / MMFF94s conformer sampling. Relative energies only within this molecule; not docking, molecular dynamics or efficacy"}
        pairs = [(parent, "Reference")]
        if kind == "compare":
            pairs.append((molecule(params["candidate"]), "Submitted variant; unmeasured"))
        else:
            pairs.extend(enumerate_variants(parent))
        rows = self.chemical_rows(path, pairs, parent)
        for row in rows:
            row["delta"] = {k: round(row[k] - rows[0][k], 3) for k in ("mw", "logp", "tpsa", "hbd", "hba")}
            row["novelty"] = "Not checked against databases"
            if kind == "variants":
                row["passes_constraints"] = row["mw"] <= params["max_mw"] and row["tpsa"] <= params["max_tpsa"] and not row["pains"]
        return {**common, "molecules": rows, "enumeration": "Single fluoro, methyl or hydroxy replacement of aromatic C-H; up to 18 unique products. No synthesis or stability claim" if kind == "variants" else None,
                "message": "No eligible aromatic C-H sites" if kind == "variants" and len(rows) == 1 else ""}

    def compounds(self, path, params):
        from rdkit import rdBase
        name = params["name"]
        namespace = "cid" if name.isdigit() else "name"
        props = "SMILES,ConnectivitySMILES,MolecularWeight,IUPACName,Title,InChIKey"
        base = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
        raw = fetch_json(base + f"{namespace}/{quote(name, safe='')}/property/{props}/JSON")
        snapshots = [self.snapshot(path, "pubchem-reference", raw)]
        records = raw.get("PropertyTable", {}).get("Properties", [])
        if not records:
            raise ProviderError("PubChem returned no compound records")
        reference = records[0]
        if params["kind"] == "neighbors":
            if len(records) > 1:
                raise ValueError("Name resolved to multiple structures; resolve the compound and use an exact CID for neighbor search")
            similar = fetch_json(base + f"fastsimilarity_2d/cid/{reference['CID']}/property/{props}/JSON?" + urlencode({"Threshold": params["threshold"], "MaxRecords": 12}))
            snapshots.append(self.snapshot(path, "pubchem-neighbors", similar))
            records = [reference] + [x for x in similar.get("PropertyTable", {}).get("Properties", []) if x.get("CID") != reference["CID"]]
        reference_smiles = reference.get("SMILES") or reference.get("IsomericSMILES")
        try:
            parent = molecule(reference_smiles)
        except ValueError:
            parent = None
        rows = []
        for record in records[:13]:
            smiles = record.get("SMILES") or record.get("IsomericSMILES")
            row = {"label": record.get("Title") or str(record["CID"]), "cid": record["CID"], "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{record['CID']}",
                   "smiles": smiles or "", "record": record, "status": "database record"}
            try:
                mol = molecule(smiles)
                computed = self.chemical_rows(path, [(mol, row["label"])], parent)[0]
                old = path / "molecule-0.png"
                dest = path / f"pubchem-{record['CID']}.png"
                old.replace(dest)
                computed["image"] = f"/api/artifact/{path.name}/{dest.name}"
                row.update(computed, status="computed descriptors")
            except ValueError as exc:
                row["status"] = str(exc)
            rows.append(row)
        return {"molecules": rows, "snapshots": snapshots, "rdkit_version": rdBase.rdkitVersion, "identity_note": "Multiple database records match this name; inspect stereochemistry and choose an exact CID" if params["kind"] == "compound" and len(records) > 1 else "",
                "interpretation": "PubChem identity and structural neighbors, not shared biological effects. PubChem similarity and local Morgan similarity use different fingerprints"}

    def docking(self, path, params):
        import contextlib

        receptor = campaign_structure_path(params["receptor"], "Receptor")
        ligand = campaign_structure_path(params["ligand"], "Ligand")
        receptor_copy = path / "receptor-input.pdbqt"
        ligand_copy = path / "ligand-input.pdbqt"
        shutil.copyfile(receptor, receptor_copy)
        shutil.copyfile(ligand, ligand_copy)
        suffix = ".sdf" if params["engine"] == "gnina" else ".pdbqt"
        output = path / f"poses{suffix}"
        runner = regen.run_gnina_docking if params["engine"] == "gnina" else regen.run_vina_docking
        options = {
            "center": tuple(params["center"]),
            "size": tuple(params["size"]),
            "exhaustiveness": params["exhaustiveness"],
            "num_modes": params["num_modes"],
            "cpu": params["cpu"],
            "seed": params["seed"],
        }
        if params["engine"] == "gnina":
            options["cnn_scoring"] = "rescore"
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                receipt = runner(str(receptor_copy), str(ligand_copy), str(output), **options)
        except SystemExit as exc:
            detail = str(exc.code) if exc.code not in (None, 0) else "Docking engine stopped without a result"
            raise ValueError(detail[:4000]) from None
        metrics = {}
        if params["engine"] == "vina":
            try:
                for line in output.read_text(encoding="ascii", errors="ignore").splitlines():
                    match = re.match(r"REMARK VINA RESULT:\s*(-?\d+(?:\.\d+)?)", line)
                    if match:
                        metrics["vina_energy_kcal_mol"] = float(match.group(1))
                        break
            except OSError:
                pass
        else:
            try:
                from rdkit import Chem
                poses = Chem.SDMolSupplier(str(output), removeHs=False)
                first = next((mol for mol in poses if mol is not None), None)
                if first is not None:
                    for prop, key in (("minimizedAffinity", "minimized_affinity_kcal_mol"), ("CNNscore", "cnnscore"), ("CNNaffinity", "cnnaffinity")):
                        if first.HasProp(prop):
                            try:
                                metrics[key] = float(first.GetProp(prop))
                            except ValueError:
                                pass
            except Exception:
                metrics["score_note"] = "GNINA score properties could not be parsed; inspect the retained SDF"
        receipt["label"] = params["label"] or Path(params["ligand"]).stem
        receipt["role"] = params["role"]
        receipt["metrics"] = metrics
        receipt["output_artifact"] = f"/api/artifact/{path.name}/{output.name}"
        receipt["input_artifacts"] = [
            f"/api/artifact/{path.name}/{receptor_copy.name}",
            f"/api/artifact/{path.name}/{ligand_copy.name}",
        ]
        receipt["interpretation"] = (
            "Exploratory docking only. These scores are not measured binding, target engagement, "
            "cellular senolysis, mutation correction, tissue repair, efficacy, safety or anti-aging benefit. "
            "Vina and GNINA share method lineage; score agreement is not independent confirmation."
        )
        return receipt

    def execute(self, path, run):
        run["status"] = "running"
        self.save_run(path, run)
        try:
            params = run["parameters"]
            if run["kind"] == "search":
                result = {"hits": [], "providers": []}
                for provider in params["providers"]:
                    try:
                        raw, hits = search_provider(provider, params["query"], params["limit"])
                        snapshot = self.snapshot(path, provider, raw)
                        result["providers"].append({"provider": provider, "status": "ok", "count": len(hits), **snapshot})
                        for row in hits:
                            doi = (row.get("doi") or "").lower().replace("https://doi.org/", "")
                            row["duplicate_key"] = doi or row.get("pmid") or re.sub(r"\W", "", row["title"].lower())
                            row["retrieved_utc"] = regen.now()
                        result["hits"].extend(hits)
                    except (ProviderError, ValueError, KeyError, TypeError) as exc:
                        result["providers"].append({"provider": provider, "status": "error", "error": str(exc) if isinstance(exc, ProviderError) else "Unexpected provider response schema"})
                    run["result"] = result
                    self.save_run(path, run)
                successes = sum(p["status"] == "ok" for p in result["providers"])
                run["status"] = "complete" if successes == len(result["providers"]) else "partial" if successes else "failed"
                run["summary"] = f"{len(result['hits'])} source records; {successes}/{len(result['providers'])} providers succeeded"
            elif run["kind"] in {"compound", "neighbors"}:
                result = self.compounds(path, params)
                run.update(status="complete", summary=f"{len(result['molecules'])} database structures")
            elif run["kind"] == "docking":
                result = self.docking(path, params)
                label = result.get("label") or "Ligand"
                summary_score = next((f"{key} {value}" for key, value in result.get("metrics", {}).items() if isinstance(value, (int, float))), "score unavailable")
                run.update(status="complete", summary=f"{label} · {params['engine'].upper()} · {params['role'].replace('_', ' ')} · {summary_score}")
            else:
                result = self.compute(path, params)
                run.update(status="complete", summary=f"{len(result.get('molecules', []))} computed structures")
            run["result"] = result
        except (ProviderError, ValueError) as exc:
            run.update(status="failed", error=str(exc))
        except Exception as exc:
            run.update(status="failed", error=f"{type(exc).__name__}: run failed; raw exception suppressed to protect credentials")
        finally:
            run["finished_utc"] = regen.now()
            try:
                params = run.get("parameters", {})
                result = redact(run.get("result", {}))
                write_json(path / "result.json", result)
                write_json(path / "parameters.json", params)
                write_json(path / "completion.json", {k: run.get(k) for k in ("id", "kind", "status", "summary", "error", "created_utc", "finished_utc")})
                inputs = {"submission.json": (path / "submission.json").read_bytes()} if (path / "submission.json").is_file() else {}
                if run["kind"] == "docking":
                    for name in ("receptor-input.pdbqt", "ligand-input.pdbqt"):
                        input_path = path / name
                        if input_path.is_file():
                            inputs[name] = input_path.read_bytes()
                versions = {"desk_implementation_sha256": regen.sha256_file(Path(__file__)), "rdkit": result.get("rdkit_version", "not recorded / lookup")}
                if run["kind"] == "docking":
                    versions["docking_engine"] = result.get("version", params.get("engine", "unknown"))
                manifest(path, "research-desk", params, inputs, versions)
                report = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
                report["outputs"].pop("run.json", None)
                for artifact in path.rglob("*"):
                    if artifact.is_file() and artifact not in {path / "manifest.json", path / "run.json"}:
                        relative = artifact.relative_to(path).as_posix()
                        report["outputs"][relative] = {"sha256": regen.sha256_file(artifact), "bytes": artifact.stat().st_size}
                write_json(path / "manifest.json", report)
                regen.record("desk-run", {"run_id": run["id"], "kind": run["kind"], "status": run["status"]}, [path / "manifest.json", path / "result.json"])
            except Exception as exc:
                run.update(status="failed", error=f"Provenance finalization failed: {type(exc).__name__}")
            self.save_run(path, run)
            with self.lock:
                self.pending -= 1

    def _verified_linked_research(self, campaigns):
        """Collect only freshly validated experiment outputs and receipt-bound model files."""
        experiment_ids = sorted({value for campaign in campaigns for value in campaign.get("experiment_ids", [])})
        bundle_ids = sorted({value for campaign in campaigns for value in campaign.get("model_bundle_ids", [])})
        files = {}
        total_bytes = 0

        def add_file(archive_path, raw, metadata):
            nonlocal total_bytes
            if len(raw) > 20_000_000:
                raise ValueError("A selected research artifact exceeds the 20 MB dossier limit")
            if archive_path in files:
                if files[archive_path] != raw:
                    raise ValueError("Selected research artifacts have a conflicting archive path")
                return
            total_bytes += len(raw)
            if total_bytes > 100_000_000:
                raise ValueError("Selected research artifacts exceed the 100 MB dossier limit")
            files[archive_path] = raw
            metadata.append({"archive_path": archive_path, "sha256": hashlib.sha256(raw).hexdigest(),
                             "bytes": len(raw)})

        linked_experiments = []
        cards = {item["experiment_id"]: item for item in self.experiments()["experiments"]
                 if item.get("validation_status") == "valid"}
        validator = experiment_manifest_tools()
        for experiment_id in experiment_ids:
            card = cards.get(experiment_id)
            if card is None:
                raise ValueError(f"Selected experiment is no longer valid: {experiment_id}")
            manifest_path = (HOME / card["manifest_path"]).resolve(strict=True)
            document = validator.validate_experiment_manifest(manifest_path, repo_root=HOME)
            archived = []
            manifest_archive = f"linked-research/experiments/{experiment_id}/experiment.json"
            manifest_bytes = manifest_path.read_bytes()
            add_file(manifest_archive, manifest_bytes, archived)
            for artifact in document["artifacts"]:
                if artifact["kind"] != "analysis_output" or artifact.get("repository") != document["repository_id"]:
                    continue
                raw = validator._artifact_bytes(HOME, document["repository_id"], artifact)
                if raw is None:
                    raise ValueError(f"Selected experiment output is unavailable: {artifact['id']}")
                suffix = Path(artifact.get("member_path", artifact["path"])).suffix.lower()
                archive_path = f"linked-research/experiments/{experiment_id}/outputs/{artifact['id']}{suffix}"
                add_file(archive_path, raw, archived)
            linked_experiments.append({"experiment_id": experiment_id, "title": document["title"],
                                       "manifest_path": card["manifest_path"],
                                       "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                                       "files": archived})

        linked_model_bundles = []
        if bundle_ids:
            inventory = ectogenesis_artifacts(ECTOGENESIS_MODEL_ROOT)
            if not inventory.get("available"):
                raise ValueError("Selected artificial-womb model bundle directory is unavailable")
            verified = {item["bundle_id"]: item for item in inventory.get("bundles", [])
                        if item.get("verified") is True}
            for bundle_id in bundle_ids:
                card = verified.get(bundle_id)
                if card is None:
                    raise ValueError(f"Selected model bundle is no longer receipt-verified: {bundle_id}")
                archived = []
                receipt_path = ECTOGENESIS_MODEL_ROOT / bundle_id / "receipt.json"
                if receipt_path.is_symlink() or not receipt_path.is_file() or receipt_path.stat().st_size > 512_000:
                    raise ValueError(f"Selected model receipt is unavailable: {bundle_id}")
                add_file(f"linked-research/model-bundles/{bundle_id}/receipt.json",
                         receipt_path.read_bytes(), archived)
                for filename in card.get("outputs", []):
                    raw, _content_type = ectogenesis_artifact_file(ECTOGENESIS_MODEL_ROOT, bundle_id, filename)
                    add_file(f"linked-research/model-bundles/{bundle_id}/{filename}", raw, archived)
                linked_model_bundles.append({"bundle_id": bundle_id, "bundle_kind": card["bundle_kind"],
                                             "files": archived})
        return {"experiments": linked_experiments, "model_bundles": linked_model_bundles}, files

    def export(self, blueprint_id, include_notes=False):
        with self.lock:
            blueprint = next(b for b in self.store["blueprints"] if b["id"] == blueprint_id)
            all_notes = [n for n in self.store["notes"] if n["blueprint_id"] == blueprint_id]
            notes = all_notes if include_notes else []
            campaigns = [c for c in self.store["campaigns"] if c["blueprint_id"] == blueprint_id]
            runs = [json.loads(p.read_text()) for p in self.runs.glob("*/run.json")]
            runs = sorted((r for r in runs if r.get("blueprint_id") == blueprint_id), key=lambda r: r["created_utc"])
        for run in runs:
            submission_path = self.runs / run["id"] / "submission.json"
            if submission_path.is_file():
                run["submission"] = json.loads(submission_path.read_text(encoding="utf-8"))
                run["submission_sha256_valid"] = hashlib.sha256(submission_path.read_bytes()).hexdigest() == run.get("submission_sha256")
        parts = [f"# {blueprint['title']}", "Research hypothesis. Computational outputs, source reports, and demonstrated effects remain distinct."]
        for field in BLUEPRINT_FIELDS[2:]:
            parts.extend([f"## {field.replace('_', ' ').title()}", blueprint.get(field) or "Not specified"])
        findings = [f for f in self.seed_findings if f["blueprint_id"] == blueprint_id]
        parts.append("## Source-reviewed starting points")
        for finding in findings:
            parts.append(f"- {finding['claim']} {finding['boundary']} Source: {finding['url']}")
        parts.append("## Target-centered campaigns")
        for campaign in campaigns:
            parts.append(f"### {campaign['title']} - {campaign['target']}")
            parts.append(f"Hypothesis: {campaign['hypothesis']}\nEndpoint: {campaign['endpoint'] or 'Not specified'}\nFalsifier: {campaign['falsifier'] or 'Not specified'}")
            if campaign.get("reference_url"):
                parts.append(f"Reference ({campaign.get('evidence_stage') or 'stage not specified'}; {campaign.get('study_design') or 'design not specified'}): {campaign['reference_url']}")
            for item in campaign.get("evidence", []):
                axis = next((axis for axis in self.campaign_frameworks.get(blueprint_id, []) if axis["id"] == item["axis_id"]), {"label": item["axis_id"]})
                parts.append(f"- {axis['label']}: {item['status']}; {item.get('value') or 'no value recorded'} {item.get('unit', '')}; comparator: {item.get('comparator') or 'not recorded'}; timepoint: {item.get('timepoint') or 'not recorded'}; source: {item.get('source_url') or 'not recorded'}")
            for item in campaign.get("evidence_records", []):
                axis = next((axis for axis in self.campaign_frameworks.get(blueprint_id, []) if axis["id"] == item["axis_id"]), {"label": item["axis_id"]})
                parts.append(f"- Source observation · {axis['label']} · {item.get('source_type')} · {item.get('source_title') or item.get('source_url')} · {item.get('species') or 'species unreported'} / {item.get('stage_track') or 'stage unreported'} / {item.get('developmental_interval') or 'interval unreported'} · {item.get('outcome') or 'outcome unreported'}: {item.get('value') or 'value unreported'} {item.get('unit')}; comparator {item.get('comparator') or 'unreported'}; independent unit {item.get('independent_unit') or 'unreported'}; reported n {item.get('sample_size') or 'unreported'}; source status {item.get('status')}; direction {item.get('direction')}; license {item.get('license') or 'unreported'}; dataset SHA-256 {item.get('dataset_sha256') or 'not supplied'}; notes {item.get('notes') or 'none'}")
            if campaign.get("experiment_ids"):
                parts.append("Linked experiment cards: " + ", ".join(campaign["experiment_ids"]))
            if campaign.get("model_bundle_ids"):
                parts.append("Linked receipt-verified model bundles: " + ", ".join(campaign["model_bundle_ids"]))
            campaign_runs = [r for r in runs if r.get("campaign_id") == campaign["id"]]
            for run in campaign_runs:
                snapshot = run.get("submission", {}).get("campaign")
                frozen_title = snapshot.get("title") if snapshot else campaign["title"]
                parts.append(f"- {run['id']} | {run['kind']} | {run['status']} | submitted under: {frozen_title} | snapshot hash valid: {run.get('submission_sha256_valid', False)} | {run.get('summary', run.get('error', ''))}")
        if include_notes:
            parts.append("## Source notes (manually entered; not independently verified)")
            for note in notes:
                parts.append(f"- [{note['kind']}; {note['direction']}] {note['claim']}\n  Source: {note['url'] or 'not provided'}\n  Confounders: {note['confounders'] or 'not assessed'}")
        else:
            parts.append(f"## Private notes\n{len(all_notes)} manually entered note(s) excluded from this export.")
        parts.append("## Reproducible runs")
        for run in runs:
            parts.append(f"- {run['id']} | {run['kind']} | {run['status']} | {run.get('summary', run.get('error', ''))}")
            for h in run.get("result", {}).get("hits", []):
                parts.append(f"  - {h['title']} | {h['url']} | {h['evidence_type']}")
        public_parts = [f"# Discussion draft: {blueprint['title']}", "Human review required. This draft summarizes local research records and does not establish efficacy, safety or anti-aging benefit."]
        public_parts.extend(f"- {f['claim']} {f['boundary']} Source: {f['url']}" for f in findings)
        for campaign in campaigns:
            public_parts.append(f"## {campaign['title']}\nHypothesis: {campaign['hypothesis']}\nEndpoint: {campaign['endpoint'] or 'Not specified'}\nFalsifier: {campaign['falsifier'] or 'Not specified'}")
            if campaign.get("reference_url"):
                public_parts.append(f"Reference source: {campaign['reference_url']}")
            for item in campaign.get("evidence_records", []):
                public_parts.append(f"- Source metadata only · {item.get('source_title') or item.get('source_url')} · {item.get('species') or 'species unreported'} / {item.get('stage_track') or 'stage unreported'} · {item.get('outcome') or 'outcome unreported'} · independent unit {item.get('independent_unit') or 'unreported'} · reported n {item.get('sample_size') or 'unreported'} · status {item.get('status')} · source {item.get('source_url') or 'not supplied'}")
        for run in runs:
            public_parts.append(f"- Run {run['id']}: {run['kind']} / {run['status']} / {run.get('summary', run.get('error', ''))}; submission snapshot hash valid: {run.get('submission_sha256_valid', False)}")
        linked_research, _linked_files = self._verified_linked_research(campaigns)
        if linked_research["experiments"] or linked_research["model_bundles"]:
            parts.append("## Selected verified experiment and model artifacts")
            for experiment in linked_research["experiments"]:
                parts.append(f"- Experiment {experiment['experiment_id']} · {experiment['title']} · {len(experiment['files'])} archived files including the validated manifest and local analysis outputs.")
                parts.extend(f"  - {file['archive_path']} · SHA-256 {file['sha256']} · {file['bytes']} bytes" for file in experiment["files"])
            for bundle in linked_research["model_bundles"]:
                parts.append(f"- Model bundle {bundle['bundle_id']} · {bundle['bundle_kind']} · receipt and {len(bundle['files'])-1} hash-matched outputs archived.")
                parts.extend(f"  - {file['archive_path']} · SHA-256 {file['sha256']} · {file['bytes']} bytes" for file in bundle["files"])
        return {"blueprint": blueprint, "campaigns": campaigns, "findings": findings, "notes": notes, "notes_excluded": not include_notes, "runs": runs, "linked_research": linked_research, "markdown": "\n\n".join(parts), "public_draft": "\n\n".join(public_parts), "exported_utc": regen.now()}

    def export_archive(self, blueprint_id, include_notes=False):
        dossier = self.export(blueprint_id, include_notes=include_notes)
        linked_research, linked_files = self._verified_linked_research(dossier["campaigns"])
        if linked_research != dossier.get("linked_research"):
            raise ValueError("Selected linked research changed while the dossier was being prepared")
        buffer = io.BytesIO()
        index = []
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in (("research_dossier.md", dossier["markdown"]), ("public_draft.md", dossier["public_draft"])):
                blob = content.encode("utf-8")
                archive.writestr(name, blob)
                index.append({"path": name, "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)})
            dossier_blob = json.dumps(dossier, ensure_ascii=True, indent=2, allow_nan=False).encode("utf-8")
            archive.writestr("dossier.json", dossier_blob)
            index.append({"path": "dossier.json", "sha256": hashlib.sha256(dossier_blob).hexdigest(), "bytes": len(dossier_blob)})
            for run in dossier["runs"]:
                run_id = run.get("id", "")
                if not re.fullmatch(r"[a-f0-9]{32}", run_id):
                    continue
                run_dir = self.runs / run_id
                manifest_path = run_dir / "manifest.json"
                declared = {}
                if manifest_path.is_file():
                    try:
                        declared = json.loads(manifest_path.read_text(encoding="utf-8")).get("outputs", {})
                    except (OSError, json.JSONDecodeError):
                        declared = {}
                for artifact in sorted(run_dir.rglob("*")):
                    if not artifact.is_file() or artifact.name.endswith(".tmp"):
                        continue
                    relative = artifact.relative_to(run_dir).as_posix()
                    if relative in {"run.json"}:
                        source_bytes = json.dumps(redact(run), ensure_ascii=True, indent=2, allow_nan=False).encode("utf-8")
                    else:
                        source_bytes = artifact.read_bytes()
                        if artifact.suffix.lower() in {".json", ".md", ".txt", ".csv"}:
                            try:
                                decoded = source_bytes.decode("utf-8")
                                parsed = json.loads(decoded) if artifact.suffix.lower() == ".json" else decoded
                                safe = redact(parsed)
                                source_bytes = (json.dumps(safe, ensure_ascii=True, indent=2, allow_nan=False) if artifact.suffix.lower() == ".json" else safe).encode("utf-8")
                            except (UnicodeDecodeError, json.JSONDecodeError):
                                pass
                    archived_path = f"runs/{run_id}/{relative}"
                    archive.writestr(archived_path, source_bytes)
                    expected = declared.get(relative, {})
                    index.append({"path": archived_path, "sha256": hashlib.sha256(source_bytes).hexdigest(), "source_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                                  "bytes": len(source_bytes), "listed_in_run_manifest": relative in declared,
                                  "source_matches_run_manifest": relative in declared and expected.get("sha256") == hashlib.sha256(artifact.read_bytes()).hexdigest()})
            for archived_path, source_bytes in sorted(linked_files.items()):
                archive.writestr(archived_path, source_bytes)
                index.append({"path": archived_path, "sha256": hashlib.sha256(source_bytes).hexdigest(),
                              "bytes": len(source_bytes), "selected_research_artifact": True})
            index_blob = json.dumps({"schema_version": 1, "notes_included": include_notes, "files": index}, ensure_ascii=True, indent=2).encode("utf-8")
            archive.writestr("archive-index.json", index_blob)
        return buffer.getvalue()


def make_handler(desk):
    class Handler(BaseHTTPRequestHandler):
        server_version = "RegenDesk/1"

        def log_message(self, *_):
            pass

        def send(self, status, data, content_type="application/json"):
            if content_type == "application/json" and not isinstance(data, bytes):
                data = json.dumps(data, allow_nan=False).encode()
            if isinstance(data, str):
                data = data.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(data)

        def allowed(self, mutation=False):
            host = self.headers.get("Host", "")
            if not re.fullmatch(r"(?:localhost|127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?", host):
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://{host}", f"https://{host}"}:
                return False
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                return False
            return not mutation or self.headers.get("Content-Type", "").split(";")[0] == "application/json"

        def do_GET(self):
            if not self.allowed():
                return self.send(403, {"error": "Local same-origin requests only"})
            route = urlsplit(self.path).path
            try:
                if route == "/api/state":
                    return self.send(200, desk.state())
                if route == "/api/experiments":
                    return self.send(200, desk.experiments())
                if route == "/api/ectogenesis/models":
                    if not any(item["id"] == "ectogenesis" for item in desk.store["blueprints"]):
                        raise ValueError("The ectogenesis research area is not configured")
                    return self.send(200, ectogenesis_artifacts())
                if route == "/api/ectogenesis/model-comparison":
                    if not any(item["id"] == "ectogenesis" for item in desk.store["blueprints"]):
                        raise ValueError("The ectogenesis research area is not configured")
                    query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                    values = [query.get(name, []) for name in ("bundle_a", "bundle_b", "metric")]
                    if any(len(items) != 1 or not items[0] for items in values):
                        raise ValueError("Select two bundles and one design-sweep metric")
                    bundle_a = ectogenesis_artifact_bundle_by_id(ECTOGENESIS_MODEL_ROOT, values[0][0])
                    bundle_b = ectogenesis_artifact_bundle_by_id(ECTOGENESIS_MODEL_ROOT, values[1][0])
                    result = ectogenesis_design_sweep_comparison(bundle_a, bundle_b, values[2][0])
                    return self.send(200, result)
                if route.startswith("/api/ectogenesis/model-artifact/"):
                    if not any(item["id"] == "ectogenesis" for item in desk.store["blueprints"]):
                        raise ValueError("The ectogenesis research area is not configured")
                    values = unquote(route.removeprefix("/api/ectogenesis/model-artifact/")).split("/")
                    if len(values) != 2:
                        raise FileNotFoundError
                    content, content_type = ectogenesis_artifact_file(
                        ECTOGENESIS_MODEL_ROOT, values[0], values[1])
                    return self.send(200, content, content_type)
                if route == "/api/experiment/artifact":
                    query = parse_qs(urlsplit(self.path).query)
                    experiment_id = query.get("experiment_id", [""])[0]
                    artifact_id = query.get("artifact_id", [""])[0]
                    content, content_type = desk.experiment_artifact(experiment_id, artifact_id)
                    return self.send(200, content, content_type)
                if route == "/api/runs":
                    query = parse_qs(urlsplit(self.path).query)
                    blueprint_id = query.get("blueprint_id", [""])[0]
                    if not any(b["id"] == blueprint_id for b in desk.store["blueprints"]):
                        raise ValueError("Unknown blueprint")
                    offset = bounded_int(int(query.get("offset", ["0"])[0]), 0, 1_000_000)
                    limit = bounded_int(int(query.get("limit", ["50"])[0]), 1, 100)
                    return self.send(200, desk.run_page(blueprint_id, offset, limit))
                if route.startswith("/api/run/"):
                    return self.send(200, desk.run(route.rsplit("/", 1)[1]))
                if route.startswith("/api/export/") and route.endswith(".zip"):
                    blueprint_id = route.removeprefix("/api/export/").removesuffix(".zip")
                    include_notes = parse_qs(urlsplit(self.path).query).get("include_notes") == ["1"]
                    return self.send(200, desk.export_archive(blueprint_id, include_notes=include_notes), "application/zip")
                if route.startswith("/api/export/"):
                    return self.send(200, desk.export(route.rsplit("/", 1)[1]))
                if route.startswith("/api/artifact/"):
                    relative = route.removeprefix("/api/artifact/")
                    path = (desk.runs / relative).resolve()
                    if not path.is_relative_to(desk.runs.resolve()) or path.suffix not in {".json", ".png", ".csv", ".sdf", ".pdbqt", ".md"}:
                        return self.send(403, {"error": "Artifact path is not allowed"})
                    return self.send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")
                static = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}.get(route)
                if static:
                    return self.send(200, (STATIC / static).read_bytes(), {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript", "style.css": "text/css"}[static])
                self.send(404, {"error": "Not found"})
            except (FileNotFoundError, StopIteration):
                self.send(404, {"error": "Record not found"})
            except ValueError as exc:
                self.send(400, {"error": str(exc)})

        def do_POST(self):
            if not self.allowed(True):
                return self.send(403, {"error": "Local same-origin JSON requests only"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 64000:
                    return self.send(413, {"error": "Request must be 1-64000 bytes"})
                self.connection.settimeout(10)
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object")
                route = urlsplit(self.path).path
                action = {"/api/jobs": desk.submit, "/api/blueprints": desk.blueprint, "/api/campaigns": desk.campaign, "/api/notes": desk.note}.get(route)
                if not action:
                    return self.send(404, {"error": "Not found"})
                self.send(202 if route == "/api/jobs" else 200, action(data))
            except (ValueError, TypeError) as exc:
                self.send(400, {"error": str(exc)})
            except Exception:
                self.send(500, {"error": "Request could not be saved"})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["serve", "run"])
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "0.0.0.0"])
    parser.add_argument("--port", type=int, default=8092)
    parser.add_argument("--request", type=Path, help="JSON request file for a reproducible CLI run")
    args = parser.parse_args()
    if args.command == "serve":
        server = ThreadingHTTPServer((args.host, args.port), BaseHTTPRequestHandler)
        desk = Desk(recover_pending=True)
        server.RequestHandlerClass = make_handler(desk)
        print(f"Regen research desk: http://127.0.0.1:{args.port}")
        server.serve_forever()
    else:
        if not args.request:
            parser.error("run requires --request")
        # CLI dispatches to the single running service so recovery and writes have one owner.
        endpoint = f"http://127.0.0.1:{args.port}"
        request = Request(endpoint + "/api/jobs", data=args.request.read_bytes(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=15) as response:
            finished = json.load(response)
        while finished["status"] in {"queued", "running"}:
            time.sleep(1)
            with urlopen(endpoint + "/api/run/" + finished["id"], timeout=15) as response:
                finished = json.load(response)
        print(json.dumps({k: finished.get(k) for k in ("id", "status", "summary", "error")}, indent=2))
        if finished["status"] in {"failed", "interrupted"}:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
