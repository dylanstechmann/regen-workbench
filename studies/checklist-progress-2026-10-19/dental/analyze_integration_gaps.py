"""Reproduce qualified scale arithmetic and synthetic contact-moment sensitivity.

This study script predicts no growth, interface strength, PDL strain or drift.
It uses only the Python standard library. No patient/source mesh is required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def number(value: object, label: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or (nonnegative and result < 0):
        raise ValueError(f"{label} has an invalid value")
    return result


def bounds(value: object, nominal: float, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} needs two bounds")
    low, high = (number(x, label, nonnegative=True) for x in value)
    if not low <= nominal <= high:
        raise ValueError(f"{label} must bracket the nominal depth")
    return low, high


def vector(value: object, label: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{label} needs three coordinates")
    return tuple(number(x, label) for x in value)


def cross(a: tuple[float, ...], b: tuple[float, ...]) -> list[float]:
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def norm(value: list[float]) -> float:
    return math.sqrt(sum(x * x for x in value))


def gap_budgets(inputs: dict) -> dict:
    footprint = inputs["reference_footprint_mm"]
    if not isinstance(footprint, list) or len(footprint) != 2:
        raise ValueError("reference footprint needs two dimensions")
    width, length = [number(v, "footprint", nonnegative=True) for v in footprint]
    if min(width, length) <= 0:
        raise ValueError("reference footprint dimensions must be positive")
    area = width * length
    configurations = inputs["source_configurations"]
    config_ids = [c["id"] for c in configurations]
    if len(set(config_ids)) != len(config_ids):
        raise ValueError("duplicate source configuration")
    for config in configurations:
        depth = number(config["nominal_depth_um"], "source depth", nonnegative=True)
        if depth <= 0:
            raise ValueError("source depth must be positive")
        if config["measurement_uncertainty_um"] is not None:
            raise ValueError("source uncertainty requires a separately specified propagation model")
    scenarios, comparisons = [], []
    scenario_ids = set()
    for case in inputs["defect_scenarios"]:
        if case["id"] in scenario_ids:
            raise ValueError("duplicate defect scenario")
        scenario_ids.add(case["id"])
        if case["status"] != "synthetic_flat_prism":
            raise ValueError("this arithmetic is qualified only for the labeled synthetic prism")
        enamel = number(case["missing_enamel_depth_mm"], "enamel depth", nonnegative=True)
        dentin = number(case["missing_dentin_depth_mm"], "dentin depth", nonnegative=True)
        if enamel <= 0:
            raise ValueError("these comparisons require a positive enamel deficit")
        eb = bounds(case["enamel_depth_sensitivity_bounds_mm"], enamel, "enamel bounds")
        db = bounds(case["dentin_depth_sensitivity_bounds_mm"], dentin, "dentin bounds")
        if eb[0] <= 0:
            raise ValueError("a depth fraction is undefined when the lower target depth is zero")
        matching = [c for c in configurations if c["substrate"] == case["substrate"]]
        scenarios.append({
            "scenario_id": case["id"], "substrate": case["substrate"],
            "missing_enamel_volume_mm3": area * enamel,
            "enamel_volume_sensitivity_bounds_mm3": [area * x for x in eb],
            "missing_dentin_volume_mm3": area * dentin,
            "dentin_volume_sensitivity_bounds_mm3": [area * x for x in db],
            "matching_source_configurations": len(matching),
            "source_transfer_state": "nominal_scale_comparison_only" if matching else "unsupported_substrate",
        })
        for config in matching:
            layer_mm = config["nominal_depth_um"] / 1000.0
            comparisons.append({
                "scenario_id": case["id"], "source_configuration": config["id"],
                "nominal_prism_equivalent_layer_volume_mm3": area * layer_mm,
                "nominal_layer_to_missing_enamel_depth_percent": 100.0 * layer_mm / enamel,
                "target_bounds_only_depth_percent_range": [100.0 * layer_mm / eb[1], 100.0 * layer_mm / eb[0]],
                "qualified_dentin_volume_recovery_mm3": None,
                "dentin_recovery_state": "not_established_by_enamel_like_layer",
                "full_area_coverage_verified": False,
                "source_measurement_uncertainty_um": None,
            })
    return {"reference_area_mm2": area, "scenarios": scenarios, "comparisons": comparisons}


def moment_sensitivity(inputs: dict) -> list[dict]:
    setup = inputs["moment_sensitivity"]
    if setup["status"] != "synthetic_rigid_body_equilibrium_only":
        raise ValueError("unqualified mechanical-model status")
    for key in ("load_magnitude_N", "support_load_share", "PDL_material_law", "interface_strength"):
        if setup[key] is not None:
            raise ValueError(f"{key} is not estimated in this sensitivity")
    baseline = vector(setup["damaged_contact_mm"], "damaged contact")
    output = []
    for load in setup["unit_load_directions"]:
        direction = vector(load["vector"], "load direction")
        if not math.isclose(norm(list(direction)), 1.0, rel_tol=0, abs_tol=1e-12):
            raise ValueError("load direction must be unit length; no load magnitude is inferred")
        original = cross(baseline, direction)
        original_magnitude = norm(original)
        for contact in setup["restored_contacts_mm"]:
            repaired = cross(vector(contact["point"], "restored contact"), direction)
            magnitude = norm(repaired)
            output.append({
                "load_direction": load["id"], "contact_case": contact["id"],
                "damaged_moment_vector_Nmm_per_N": original,
                "restored_moment_vector_Nmm_per_N": repaired,
                "damaged_moment_magnitude_Nmm_per_N": original_magnitude,
                "restored_moment_magnitude_Nmm_per_N": magnitude,
                "moment_magnitude_change_percent": (
                    100.0 * (magnitude / original_magnitude - 1.0)
                    if original_magnitude > 1e-15 else None),
                "PDL_strain": None, "predicted_pose_drift_mm": None,
            })
    return output


def audit_contract(contract: dict, parent: dict) -> dict:
    domains = contract["required_domains"]
    parent_domains = [d["domain"] for d in parent["restoration_domains"]]
    if len(domains) != len(set(domains)) or set(domains) != set(parent_domains):
        raise ValueError("integration contract must preserve every parent restoration domain")
    if [stage["id"] for stage in contract["stage_sequence"]] != ["I0", "I1", "I2", "I3"]:
        raise ValueError("measurement, material, assembly and living transfer stages are required")
    if contract["clinical_pass_margin"] is not None:
        raise ValueError("this design has no qualified clinical pass margin")
    return {
        "domains_preserved": len(domains),
        "domain_results": {name: "unassessed" for name in domains},
        "integrated_success": False,
        "reason": "No experimental observations or qualified numerical margins are supplied.",
    }


def load_json(path: Path) -> dict:
    def invalid_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant: {value}")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid_constant)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=HERE / "inputs.json")
    parser.add_argument("--out", type=Path, default=HERE / "derived/integration_gap_results.json")
    args = parser.parse_args()
    inputs = load_json(args.inputs)
    contract_path = HERE / "integration_contract.json"
    contract = load_json(contract_path)
    parent_path = HERE / contract["parent_contract"]
    result = {
        "status": "computed_scale_arithmetic_and_synthetic_sensitivity_no_biological_experiment",
        "receipt": {"inputs_sha256": sha256(args.inputs), "script_sha256": sha256(Path(__file__)),
                    "integration_contract_sha256": sha256(contract_path),
                    "parent_contract_sha256": sha256(parent_path)},
        "volume_budget": gap_budgets(inputs),
        "contact_moment_sensitivity": moment_sensitivity(inputs),
        "restoration_goal_audit": audit_contract(contract, load_json(parent_path)),
        "limits": [
            "Prism-equivalent volumes assume complete uniform coverage of a flat 8 mm2 reference footprint; actual coverage and recovered volumes are unmeasured.",
            "Approximate source layer depths are configuration labels, not confidence bounds or a growth law; no cycle count, time to repair or clinical efficacy is predicted.",
            "Target-depth sensitivity bounds are synthetic choices, not empirical measurement uncertainties. Source layer uncertainty remains unknown.",
            "Moment differences follow r cross a unit load direction about a fixed origin. No force magnitude, PDL constitutive law, interface strength, support load sharing or tooth drift is inferred.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {len(result['volume_budget']['comparisons'])} substrate-matched scale comparisons, "
          f"{len(result['contact_moment_sensitivity'])} synthetic contact/load cases; "
          f"{result['restoration_goal_audit']['domains_preserved']} domains retained, all unassessed.")


if __name__ == "__main__":
    main()
