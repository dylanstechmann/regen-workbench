"""Parent/metabolite bookkeeping for hypothetical caffeine-reversal mechanisms.

Normalized, post-absorption, one-compartment thought experiment. No molecule,
oral exposure, receptor displacement, sleep response or human dose is predicted.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def finite_nonnegative(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def advance(parent, metabolite, hours, parent_rate, metabolite_rate, formation_rate):
    """Exact P'=-kp P, M'=q P-km M; q<=kp conserves molecular equivalents."""
    if (not all(finite_nonnegative(x) for x in (parent, metabolite, hours, parent_rate, metabolite_rate, formation_rate))
            or parent_rate <= 0 or metabolite_rate <= 0 or formation_rate > parent_rate):
        raise ValueError("Require finite nonnegative states/time, positive rates and formation <= parent clearance")
    ep, em = math.exp(-parent_rate * hours), math.exp(-metabolite_rate * hours)
    difference = metabolite_rate - parent_rate
    generated = (parent * formation_rate * hours * ep if abs(difference) < 1e-12
                 else parent * formation_rate * (ep - em) / difference)
    p, m = parent * ep, metabolite * em + generated
    lost = parent + metabolite - p - m
    if min(p, m, lost) < -1e-11:
        raise ArithmeticError("Negative state or failed balance")
    return p, m, max(0., lost)


def state_at(hours, scenario, parent_half_life, metabolite_half_life, natural_formation_fraction=1.):
    if (not finite_nonnegative(hours) or not finite_nonnegative(parent_half_life) or parent_half_life <= 0
            or not finite_nonnegative(metabolite_half_life) or metabolite_half_life <= 0
            or not finite_nonnegative(natural_formation_fraction) or natural_formation_fraction > 1):
        raise ValueError("Invalid time, half-life or formation fraction")
    event = scenario["event_hours"]
    extra = scenario["extra_parent_clearance_per_hour"]
    yield_fraction = scenario["extra_clearance_active_product_fraction"]
    capture_p, capture_m = scenario["capture_parent_fraction"], scenario["capture_metabolite_fraction"]
    if (not all(finite_nonnegative(x) for x in (event, extra, yield_fraction, capture_p, capture_m))
            or max(yield_fraction, capture_p, capture_m) > 1):
        raise ValueError("Invalid hypothetical intervention")
    kp, km = math.log(2) / parent_half_life, math.log(2) / metabolite_half_life
    p, m, eliminated = advance(1., 0., min(hours, event), kp, km, natural_formation_fraction * kp)
    bound = 0.
    if hours >= event:
        bound = p * capture_p + m * capture_m
        p, m = p * (1 - capture_p), m * (1 - capture_m)
        p, m, loss = advance(p, m, hours - event, kp + extra, km,
                             natural_formation_fraction * kp + yield_fraction * extra)
        eliminated += loss
    if abs(p + m + eliminated + bound - 1) > 1e-10:
        raise ArithmeticError("Molecular-equivalent balance failed")
    return {"parent_fraction": p, "modeled_active_metabolite_fraction": m,
            "eliminated_equivalent_fraction": eliminated, "ideally_captured_fraction": bound}


def run(plan, output):
    rows = []
    for half_life in plan["parent_half_life_hours"]:
        for formation in plan["natural_active_product_fractions"]:
            for scenario in plan["scenarios"]:
                for hours in plan["evaluation_hours"]:
                    state = state_at(hours, scenario, half_life, plan["metabolite_half_life_hours"], formation)
                    for relative_weight in plan["metabolite_proxy_weights"]:
                        rows.append({"scenario": scenario["name"], "parent_half_life_hours": half_life,
                            "natural_active_product_fraction": formation, "hours": hours,
                            "metabolite_proxy_weight": relative_weight, **state,
                            "weighted_active_equivalent_proxy": state["parent_fraction"]
                                + relative_weight * state["modeled_active_metabolite_fraction"]})
    output.mkdir(parents=True, exist_ok=True)
    with (output / "mechanism_comparison.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=HERE / "mechanism_plan.json")
    parser.add_argument("--out", type=Path, default=HERE / "derived")
    args = parser.parse_args()
    raw = args.plan.read_text(encoding="utf-8").encode()
    plan = json.loads(raw)
    rows = run(plan, args.out)
    summary = {"plan_sha256": hashlib.sha256(raw).hexdigest(), "rows": len(rows),
        "status": "hypothetical mechanism comparison; not a validated PK/PD or sleep model",
        "maximum_molecular_balance_error": max(abs(sum(row[k] for k in
            ("parent_fraction", "modeled_active_metabolite_fraction", "eliminated_equivalent_fraction", "ideally_captured_fraction")) - 1) for row in rows),
        "half_life_source": "https://pubmed.ncbi.nlm.nih.gov/3756065/",
        "new_molecule_designed": False, "clinical_success_threshold": None}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))
