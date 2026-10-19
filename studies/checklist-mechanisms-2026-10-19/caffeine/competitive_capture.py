"""Finite-capacity reversible host/guest binding; all concentrations use mol/L."""
from __future__ import annotations
import csv
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent

def valid_nonnegative(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Expected finite nonnegative numeric value")
    return float(value)

def occupied_fraction(ka, free_host):
    product = ka * free_host
    if math.isinf(product):
        return 1.0
    return product / (1.0 + product)

def prepare_guests(guests):
    names = set()
    result = []
    for guest in guests:
        name = guest["name"]
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Guest names must be unique nonempty strings")
        names.add(name)
        result.append({"name": name, "total": valid_nonnegative(guest["total"]), "ka": valid_nonnegative(guest["ka"])})
    return result

def equilibrium(host_total, guests):
    """Unique mass-balance root; guests compete for the same finite host pool."""
    host_total = valid_nonnegative(host_total)
    guests = prepare_guests(guests)
    low, high = 0.0, host_total
    for _ in range(200):
        free_host = (low + high) / 2.0
        used = free_host + math.fsum(g["total"] * occupied_fraction(g["ka"], free_host) for g in guests)
        if used > host_total:
            high = free_host
        else:
            low = free_host
    free_host = (low + high) / 2.0
    states = []
    for g in guests:
        bound = g["total"] * occupied_fraction(g["ka"], free_host)
        states.append({**g, "free": g["total"] - bound, "bound": bound})
    return {"host_free": free_host, "host_total": host_total, "guests": states,
            "host_balance_error": free_host + math.fsum(g["bound"] for g in states) - host_total}

def required_host(target_name, capture_fraction, guests):
    """Analytic free-host requirement plus all occupied sites; no host excess approximation."""
    capture_fraction = valid_nonnegative(capture_fraction)
    if not 0 < capture_fraction < 1:
        raise ValueError("Target must be strictly between zero and complete capture")
    guests = prepare_guests(guests)
    target = next((g for g in guests if g["name"] == target_name), None)
    if target is None or target["ka"] <= 0 or target["total"] <= 0:
        raise ValueError("Target requires positive concentration and affinity")
    free_host = capture_fraction / ((1.0 - capture_fraction) * target["ka"])
    bound = math.fsum(g["total"] * occupied_fraction(g["ka"], free_host) for g in guests)
    return {"host_free": free_host, "host_total": free_host + bound, "bound_sites": bound}

def write_tsv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

def main():
    plan_path = HERE / "binding_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    source = plan["source"]
    center = source["caffeine_ka_per_molar"]
    delta = source["caffeine_reported_plus_minus_per_molar"]
    affinities = [("reported_minus", center-delta), ("central", center), ("reported_plus", center+delta)]
    equilibria, requirements = [], []
    max_error = 0.0
    for label, ka in affinities:
        for c_um in plan["caffeine_total_micromolar"]:
            total = c_um * 1e-6
            for case in plan["competitions"]:
                guests = [{"name": "caffeine", "ka": ka, "total": total}]
                for g in case["guests"]:
                    abundance = g["total_micromolar"] * 1e-6 if "total_micromolar" in g else total * g["total_to_caffeine_ratio"]
                    guests.append({"name": g["name"], "ka": g["ka_per_molar"], "total": abundance})
                for ratio in plan["host_to_caffeine_total_molar_ratios"]:
                    state = equilibrium(total * ratio, guests)
                    caffeine = state["guests"][0]
                    max_error = max(max_error, abs(state["host_balance_error"]))
                    equilibria.append({"ka_case": label, "caffeine_ka_per_molar": ka,
                        "caffeine_total_uM": c_um, "competition": case["id"], "host_total_ratio": ratio,
                        "host_total_uM": state["host_total"]*1e6, "host_free_uM": state["host_free"]*1e6,
                        "caffeine_free_fraction": caffeine["free"]/total,
                        "caffeine_bound_fraction": caffeine["bound"]/total,
                        "competing_bound_sites_uM": math.fsum(g["bound"] for g in state["guests"][1:])*1e6,
                        "host_balance_error_M": state["host_balance_error"]})
                for target in plan["capture_fraction_targets"]:
                    req = required_host("caffeine", target, guests)
                    check = equilibrium(req["host_total"], guests)
                    measured = check["guests"][0]["bound"]/total
                    if abs(measured-target) > 1e-12:
                        raise ValueError("Threshold reconstruction failed")
                    requirements.append({"ka_case": label, "caffeine_ka_per_molar": ka,
                        "caffeine_total_uM": c_um, "competition": case["id"], "capture_fraction": target,
                        "host_free_uM": req["host_free"]*1e6, "host_total_uM": req["host_total"]*1e6,
                        "host_total_to_caffeine_ratio": req["host_total"]/total,
                        "occupied_sites_uM": req["bound_sites"]*1e6})
    out = HERE / "derived"
    out.mkdir(exist_ok=True)
    write_tsv(out / "finite_capacity_equilibria.tsv", equilibria)
    write_tsv(out / "target_capture_requirements.tsv", requirements)
    receipt = {"schema_version": 1, "plan_sha256_lf_text": hashlib.sha256(plan_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest(),
        "script_sha256_lf_text": hashlib.sha256(Path(__file__).read_text(encoding="utf-8").encode("utf-8")).hexdigest(),
        "output_sha256_lf_text": {name: hashlib.sha256((out/name).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
                                   for name in ["finite_capacity_equilibria.tsv", "target_capture_requirements.tsv"]},
        "equilibrium_rows": len(equilibria), "requirement_rows": len(requirements),
        "maximum_host_balance_error_M": max_error,
        "caffeine_to_theophylline_affinity_ratio": center/source["theophylline_ka_per_molar"],
        "caffeine_to_theobromine_affinity_ratio": center/source["theobromine_ka_per_molar"],
        "paraxanthine_result": "not_identifiable_missing_affinity",
        "human_oral_sleep_result": "not_identifiable_not_modelled"}
    (out / "analysis_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(receipt))

if __name__ == "__main__":
    main()
