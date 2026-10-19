"""Bound joint endpoint attainment only for an explicitly shared observation set.

Study helper, not a tissue efficacy score. Allele, cell, area and patient
denominators cannot be interchanged. Missing joint measurements stay visible.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def audit(payload):
    population = payload["population"]
    count = population["n_units"]
    if not integer(count) or count <= 0:
        raise ValueError("Population must have a positive integer unit count")
    identifiers = ("population_id", "unit", "timepoint", "sampling_frame")
    if not all(isinstance(population.get(key), str) and population[key].strip() for key in identifiers):
        raise ValueError("Declare population, unit, timepoint and sampling frame")
    endpoints = payload["required_endpoints"]
    if (not isinstance(endpoints, list) or len(endpoints) < 2
            or not all(isinstance(e, str) and e.strip() for e in endpoints) or len(set(endpoints)) != len(endpoints)):
        raise ValueError("Require at least two distinct named endpoints")
    observations = payload["observations"]
    if not isinstance(observations, list):
        raise ValueError("Observations must be a list")
    seen, eligible, problems = set(), [], []
    for row in observations:
        name = row["endpoint"]
        if name not in endpoints or name in seen:
            raise ValueError("Unexpected or duplicate endpoint")
        seen.add(name)
        value = row.get("attaining_count")
        if value is not None and (not integer(value) or not 0 <= value <= count):
            raise ValueError("Endpoint count must be an integer within the shared population")
        mismatch = [key for key in identifiers if row.get(key) != population[key]]
        if row.get("n_units") != count or not integer(row.get("n_units")):
            mismatch.append("n_units")
        if mismatch:
            problems.append({"endpoint": name, "reason": "incompatible_observation_set", "fields": mismatch})
        elif value is None:
            problems.append({"endpoint": name, "reason": "unmeasured_endpoint"})
        else:
            eligible.append(value)
    for name in endpoints:
        if name not in seen:
            problems.append({"endpoint": name, "reason": "missing_endpoint"})
    result = {"population": population, "required_endpoints": endpoints,
        "qualification": "Joint attainment of declared assay criteria; not clinical regeneration or a universal quality score",
        "problems": problems, "joint_attaining_count": None,
        "lower_bound_count": None, "upper_bound_count": None,
        "independence_product_benchmark_fraction": None}
    if problems:
        if payload.get("joint_attaining_count") is not None:
            raise ValueError("Cannot accept a joint count with incomplete or incompatible required endpoints")
        return {**result, "status": "unidentified_incompatible_or_incomplete_endpoints"}
    lower, upper = max(0, sum(eligible) - (len(eligible) - 1) * count), min(eligible)
    product = 1.
    for value in eligible:
        product *= value / count
    joint = payload.get("joint_attaining_count")
    if joint is not None and (not integer(joint) or not lower <= joint <= upper):
        raise ValueError("Observed joint count violates marginal overlap bounds")
    return {**result, "status": "joint_measured" if joint is not None else "joint_bounded_not_measured",
        "lower_bound_count": lower, "upper_bound_count": upper,
        "lower_bound_fraction": lower / count, "upper_bound_fraction": upper / count,
        "joint_attaining_count": joint,
        "independence_product_benchmark_fraction": product,
        "independence_warning": "Benchmark assumes independent endpoints; not an estimated or observed joint outcome"}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE / "joint_endpoint_examples.json")
    parser.add_argument("--out", type=Path, default=HERE / "derived" / "joint_endpoint_audit.json")
    args = parser.parse_args()
    raw = args.input.read_text(encoding="utf-8").encode()
    payload = json.loads(raw, object_pairs_hook=unique_object,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON value")))
    results = [{"example_id": row["example_id"], "input_status": row["input_status"], **audit(row)} for row in payload]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"input_sha256": hashlib.sha256(raw).hexdigest(),
        "text_hash_convention": "canonical UTF-8/LF", "results": results}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps([{key: row.get(key) for key in ("example_id", "status", "lower_bound_count", "upper_bound_count")} for row in results], indent=2))
