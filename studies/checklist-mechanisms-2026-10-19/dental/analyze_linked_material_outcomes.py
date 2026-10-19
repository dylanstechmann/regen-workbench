"""Specimen-linked material estimands; no acceptance margins or repair score.

Depth/leakage and indentations share a declared baseline state. Terminal crack
paths retain their actual assessment cycles; fatigue is a separate follow-up
outcome. These times are never collapsed into a joint-success claim.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SUBSTRATES = {"retained_enamel", "exposed_dentin", "restorative_boundary"}
CRACK_PATHS = {"none_detected", "interfacial", "mixed", "cohesive_host", "cohesive_repair"}
FAILURE_MODES = {"interfacial", "mixed", "cohesive_host", "cohesive_repair"}


def text_sha(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def load_json(path: Path):
    def unique(pairs):
        output = {}
        for key, value in pairs:
            if key in output:
                raise ValueError("Duplicate JSON key")
            output[key] = value
        return output
    def invalid(value):
        raise ValueError(f"Non-finite JSON constant: {value}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=invalid)


def nonnegative(value, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return float(value)


def identifier(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing {name}")
    return value


def depth_result(depth, target):
    if depth is None:
        return {"depth_um": None, "target_difference_um": None, "target_difference_bounds_um": None,
                "depth_measurement_bounds_um": None, "depth_bounds_kind": None,
                "depth_state": "unassessed_missing_depth"}
    value = nonnegative(depth["value_um"], "depth")
    delta = None if target is None else value - target
    bounds = depth.get("bounds_um")
    if bounds is None:
        return {"depth_um": value, "target_difference_um": delta, "target_difference_bounds_um": None,
                "depth_measurement_bounds_um": None, "depth_bounds_kind": None,
                "depth_state": "unassessed_missing_target" if target is None else "observed_without_measurement_bounds"}
    if not isinstance(bounds, list) or len(bounds) != 2:
        raise ValueError("Depth needs two measurement bounds")
    low, high = [nonnegative(v, "depth bound") for v in bounds]
    if not low <= value <= high:
        raise ValueError("Depth bounds must bracket the measured value")
    identifier(depth.get("bounds_kind"), "depth bounds interpretation")
    if target is None:
        return {"depth_um": value, "target_difference_um": None, "target_difference_bounds_um": None,
                "depth_measurement_bounds_um": [low, high], "depth_bounds_kind": depth["bounds_kind"],
                "depth_state": "unassessed_missing_target"}
    status = ("below_target_with_given_bounds" if high < target else
              "at_or_above_target_with_given_bounds" if low >= target else "bounds_overlap_target")
    return {"depth_um": value, "target_difference_um": delta,
            "target_difference_bounds_um": [low - target, high - target],
            "depth_measurement_bounds_um": [low, high], "depth_bounds_kind": depth["bounds_kind"], "depth_state": status}


def leakage_bounds(record):
    """Nonnegative-scale identification bounds; no substitution of LOD/2."""
    if record is None:
        return 0.0, None, "unmeasured"
    value = nonnegative(record["value"], "leakage")
    kind = record["kind"]
    if kind == "exact":
        return value, value, kind
    if kind == "left_censored":
        return 0.0, value, kind
    if kind == "right_censored":
        return value, None, kind
    raise ValueError("Unsupported leakage censoring kind")


def fatigue_state(record, horizon):
    """Failure by H: censoring or interval timing can leave state unknown."""
    if record is None:
        return "unknown", "unmeasured"
    if record["kind"] == "right_censored":
        cycles = nonnegative(record["cycles"], "censor cycles")
        if record.get("reason") not in {"planned_runout", "technical_loss", "withdrawal", "lost_follow_up"}:
            raise ValueError("Declare why fatigue follow-up ended")
        return ("known_no_failure_by_horizon" if cycles >= horizon else "unknown"), record["reason"]
    if record["kind"] != "event" or record.get("failure_mode") not in FAILURE_MODES:
        raise ValueError("Fatigue event must be a defined material failure, not fixture loss")
    interval = record["cycle_bounds"]
    if not isinstance(interval, list) or len(interval) != 2:
        raise ValueError("Event timing requires a two-bound cycle interval")
    low, high = [nonnegative(v, "event cycle") for v in interval]
    if low > high:
        raise ValueError("Event cycle bounds reversed")
    state = ("known_failure_by_horizon" if high <= horizon else
             "known_no_failure_by_horizon" if low > horizon else "unknown")
    return state, record["failure_mode"]


def hierarchical_mean(registry, values):
    """Each indent is first summarized within specimen; balance teeth/donors."""
    observed = [r for r in registry if r["specimen_id"] in values]
    base = {"n_assigned_specimens": len(registry), "n_observed_specimens": len(observed),
            "n_missing_endpoint": len(registry) - len(observed),
            "observed_specimen_weighted_mean": statistics.mean(values[r["specimen_id"]] for r in observed) if observed else None,
            "tooth_then_donor_balanced_mean": None, "n_observed_donors": None,
            "qualification": "Observed endpoint subset only; no confidence interval or independent-replicate inference"}
    if not observed:
        return {**base, "hierarchy_status": "unavailable_no_endpoint"}
    if any(not r.get("donor_id") or not r.get("tooth_id") for r in observed):
        return {**base, "hierarchy_status": "unavailable_missing_donor_or_tooth_identity"}
    teeth = defaultdict(list)
    for row in observed:
        teeth[(row["donor_id"], row["tooth_id"])].append(values[row["specimen_id"]])
    donors = defaultdict(list)
    for (donor, _), points in teeth.items():
        donors[donor].append(statistics.mean(points))
    return {**base, "tooth_then_donor_balanced_mean": statistics.mean(statistics.mean(v) for v in donors.values()),
            "n_observed_donors": len(donors), "hierarchy_status": "descriptive_hierarchy_preserved"}


def validate_registry(payload):
    registry, tooth_donors = {}, {}
    for row in payload["specimens"]:
        specimen = identifier(row["specimen_id"], "specimen ID")
        if specimen in registry:
            raise ValueError("Duplicate assigned specimen")
        for name in ["batch_id", "region_id", "condition", "architecture"]:
            identifier(row[name], name)
        if row["substrate"] not in SUBSTRATES:
            raise ValueError("Unknown substrate; do not pool its interface evidence")
        for name in ["donor_id", "tooth_id"]:
            if row.get(name) is not None:
                identifier(row[name], name)
        if row.get("tooth_id") and row.get("donor_id"):
            prior = tooth_donors.setdefault(row["tooth_id"], row["donor_id"])
            if prior != row["donor_id"]:
                raise ValueError("A tooth cannot belong to different donors")
        if row.get("target_depth_um") is not None:
            nonnegative(row["target_depth_um"], "intended depth")
        registry[specimen] = row
    return registry


def check_link(row, registry, payload):
    specimen = row["specimen_id"]
    if specimen not in registry or row["region_id"] != registry[specimen]["region_id"]:
        raise ValueError("Unregistered specimen or a different repair region")
    if row["state_id"] != payload["baseline_material_state_id"]:
        raise ValueError("Material snapshots from different states cannot be pooled")
    if nonnegative(row["assessment_cycles"], "snapshot cycles") != payload["baseline_assessment_cycles"]:
        raise ValueError("Material snapshots from different exposure times cannot be pooled")


def analyze_linked(payload):
    registry = validate_registry(payload)
    if not registry:
        if payload["measurements"] or payload["indentations"]:
            raise ValueError("Measurements require a specimen registry")
        return {"status": "empty_template_no_data", "groups": [], "specimen_outcomes": []}
    identifier(payload["assay_id"], "common assay ID")
    identifier(payload["baseline_material_state_id"], "material snapshot state")
    baseline = nonnegative(payload["baseline_assessment_cycles"], "snapshot time")
    horizon = nonnegative(payload["fatigue_horizon_cycles"], "prespecified fatigue observation horizon")
    if horizon <= 0 or horizon < baseline or payload["depth_statistic"] != "minimum_over_registered_region":
        raise ValueError("Require a positive observation horizon and the declared regional depth statistic")
    if payload["leakage_unit"] != "nonnegative_normalized_assay_units":
        raise ValueError("Leakage scales cannot be silently interchanged")
    packets = {}
    for row in payload["measurements"]:
        check_link(row, registry, payload)
        if row["specimen_id"] in packets:
            raise ValueError("One declared snapshot per assigned specimen; repeated fields are not new specimens")
        packets[row["specimen_id"]] = row
    indents, indent_ids = defaultdict(list), set()
    for row in payload["indentations"]:
        check_link(row, registry, payload)
        if row["indent_id"] in indent_ids:
            raise ValueError("Duplicate indentation")
        indent_ids.add(row["indent_id"])
        if row["endpoint"] != "indentation_apparent_fracture_toughness" or row["unit"] != "MPa m^0.5":
            raise ValueError("This endpoint cannot inherit bulk/interface toughness meaning or another unit")
        indents[row["specimen_id"]].append(nonnegative(row["value"], "indentation value"))
    outcomes, groups = [], defaultdict(list)
    for specimen, record in registry.items():
        packet = packets.get(specimen, {})
        missing_reasons = packet.get("missing_reasons", {}) if packet else {"all": "no_measurement_packet"}
        if packet:
            for endpoint in ["depth", "leakage", "terminal_crack_path", "fatigue"]:
                if packet.get(endpoint) is None:
                    identifier(missing_reasons.get(endpoint), f"missing-outcome reason for {endpoint}")
        depth = depth_result(packet.get("depth"), record.get("target_depth_um"))
        lower, upper, leak_kind = leakage_bounds(packet.get("leakage"))
        followup = packet.get("fatigue")
        fatigue, reason = fatigue_state(followup, horizon)
        followup_end = None
        if followup is not None:
            followup_start = followup["cycle_bounds"][0] if followup["kind"] == "event" else followup["cycles"]
            followup_end = followup["cycle_bounds"][1] if followup["kind"] == "event" else followup["cycles"]
            if followup_start < baseline:
                raise ValueError("Failure/censoring cannot precede the declared baseline material snapshot")
        crack = packet.get("terminal_crack_path")
        if crack is not None:
            if crack["category"] not in CRACK_PATHS:
                raise ValueError("Unknown terminal crack path")
            crack_time = nonnegative(crack["assessment_cycles"], "terminal crack assessment time")
            if crack_time < baseline or (followup_end is not None and crack_time < followup_end):
                raise ValueError("Terminal crack assessment cannot precede baseline or the recorded follow-up endpoint")
        outcome = {**record, **depth, "leakage_lower": lower, "leakage_upper": upper,
                   "leakage_kind": leak_kind, "fatigue_state_by_horizon": fatigue,
                   "fatigue_reason": reason, "terminal_crack_path": crack,
                   "indentations_count": len(indents[specimen]),
                   "specimen_mean_apparent_toughness": statistics.mean(indents[specimen]) if indents[specimen] else None,
                   "missing_outcome_reasons": missing_reasons,
                   "measurement_packet_missing": specimen not in packets}
        outcomes.append(outcome)
        groups[(record["condition"], record["substrate"], record["architecture"], record.get("target_depth_um"))].append(outcome)
    summaries = []
    for key, rows in sorted(groups.items(), key=lambda item: str(item[0])):
        n = len(rows)
        fatigue = Counter(r["fatigue_state_by_horizon"] for r in rows)
        depth_values = {r["specimen_id"]: r["depth_um"] for r in rows if r["depth_um"] is not None}
        toughness = {r["specimen_id"]: r["specimen_mean_apparent_toughness"] for r in rows if r["specimen_mean_apparent_toughness"] is not None}
        numeric_indents = [v for r in rows for v in indents[r["specimen_id"]]]
        summaries.append({"condition": key[0], "substrate": key[1], "architecture": key[2], "target_depth_um": key[3],
            "assigned_specimens": n, "manufacturing_batches": sorted({r["batch_id"] for r in rows}),
            "depth": hierarchical_mean(rows, depth_values),
            "depth_states": dict(Counter(r["depth_state"] for r in rows)),
            "apparent_toughness": hierarchical_mean(rows, toughness),
            "naive_indent_weighted_mean_diagnostic_only": statistics.mean(numeric_indents) if numeric_indents else None,
            "fatigue_horizon_cycles": horizon, "fatigue_state_counts": dict(fatigue),
            "fatigue_failure_fraction_bounds": [fatigue["known_failure_by_horizon"] / n,
                                                  (fatigue["known_failure_by_horizon"] + fatigue["unknown"]) / n],
            "fatigue_estimand": "Fraction of all assigned specimens with first material failure by H; unknown/censored outcomes retained, no independent-censoring assumption",
            "leakage_all_assigned_mean_bounds": [sum(r["leakage_lower"] for r in rows) / n,
                None if any(r["leakage_upper"] is None for r in rows) else sum(r["leakage_upper"] for r in rows) / n],
            "leakage_upper_null_meaning": "No finite upper bound; not zero, an exact mean or a confidence interval",
            "leakage_observation_kinds": dict(Counter(r["leakage_kind"] for r in rows)),
            "terminal_crack_paths_at_recorded_times": dict(Counter(r["terminal_crack_path"]["category"] if r["terminal_crack_path"] else "unmeasured" for r in rows)),
            "terminal_crack_path_limit": "Assessment cycles differ and remain in specimen records; these are not crack-path frequencies at H or a baseline predictor",
            "joint_restoration_success": "unassessed_no_joint_acceptance_rule"})
    contract = load_json(ROOT / "studies/periodontal-attachment-restoration-2026-10-11/restoration_contract.json")
    return {"status": "linked_descriptive_estimands_only", "data_kind": payload["data_kind"],
            "groups": summaries, "specimen_outcomes": outcomes,
            "full_restoration_domains": {d["domain"]: "unassessed" for d in contract["restoration_domains"]},
            "limits": ["No numerical clinical acceptance thresholds, p-values, confidence intervals or causal depth effect are estimated.",
                       "Depth/leakage/indent snapshots precede separate fatigue follow-up; terminal crack paths retain assessment cycles. No simultaneous joint-success claim.",
                       "All-assigned leakage bounds use only nonnegativity; zero is a lower bound for missing measurements, never an imputed observed value.",
                       "PDL, pulp, gingiva, full crown load transfer and position after finite support remain unassessed."]}


def audit_unlinked_source(manifest_path):
    manifest = load_json(manifest_path)
    path = manifest_path.parent / manifest["numeric_table"]
    if text_sha(path) != manifest["numeric_table_sha256_lf_text"]:
        raise ValueError("Actual source-position table changed")
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    if any(r.get("specimen_id") or r.get("donor_id") for r in rows):
        raise ValueError("Source linkage changed; requalify instead of applying the unlinked adapter")
    available = dict(Counter(r["endpoint"] for r in rows))
    return {"source_citation": manifest["source_citation"], "source_license": manifest["source_license"],
            "numeric_table_sha256_lf_text": text_sha(path), "stored_numeric_positions": len(rows),
            "ambiguous_cells_retained": [f'{r["sheet"]}!{r["cell"]}' for r in rows if r["observation_status"] == "ambiguous_trailing_cell_not_a_specimen"],
            "marginal_endpoint_positions_available": available,
            "invented_specimen_ids": False, "linked_specimens_available": 0,
            "estimand_availability": {
                "per_specimen_depth_target_distribution": "unavailable: no per-specimen depth/target and crosswalk",
                "depth_vs_interface_crack_path": "unavailable: no specimen-linked crack-path record",
                "leakage_mean_bounds_by_depth": "unavailable: no linked leakage outcomes or assigned specimen registry",
                "fatigue_failure_bounds_by_depth": "unavailable: wear endpoint values are not failure times, censoring records or a linked registry",
                "tooth_then_donor_balanced_indentation_analysis": "unavailable: no indentation-to-specimen/tooth/donor crosswalk",
                "marginal_toughness_and_wear_descriptions": "available in prior source reanalysis; adverse enamel wear and trailing-cell ambiguity remain"},
            "claim": "Actual numerical source data remain unlinked; approximate article layer examples cannot be attached to these positions as measured specimen depth"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE / "synthetic_linked_fixture.json")
    parser.add_argument("--source", type=Path, default=HERE / "hasan_unlinked_source.json")
    parser.add_argument("--out", type=Path, default=HERE / "derived")
    args = parser.parse_args()
    result = analyze_linked(load_json(args.input))
    result["receipts"] = {"input_sha256_lf_text": text_sha(args.input), "script_sha256_lf_text": text_sha(Path(__file__))}
    source = audit_unlinked_source(args.source)
    source["manifest_sha256_lf_text"] = text_sha(args.source)
    args.out.mkdir(parents=True, exist_ok=True)
    for filename, payload in [("linked_specimen_analysis.json", result), ("source_linkage_availability.json", source)]:
        (args.out / filename).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"data_kind": result.get("data_kind", result["status"]), "linked_fixture_specimens": len(result["specimen_outcomes"]),
                      "actual_source_linked_specimens": source["linked_specimens_available"]}))


if __name__ == "__main__":
    main()
