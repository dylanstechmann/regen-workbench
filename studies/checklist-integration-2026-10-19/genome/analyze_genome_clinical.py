"""Reproduce descriptive clinical-summary contrasts; never infer editing coverage."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def canonical_hash(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def whole(value, name, positive=False):
    number(value, name, positive)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def calculate(data):
    n = whole(data["study"]["independent_patients"], "independent_patients", True)
    if n != 1:
        raise ValueError("This source-specific reconstruction is restricted to one patient")
    timeline = data["timeline"]
    for key, value in timeline.items():
        if key != "time_unit":
            whole(value, key)
    first = timeline["first_intervention_day"]
    interval = timeline["second_intervention_interval_days_reported"]
    if interval <= 0:
        raise ValueError("second intervention interval must be positive")
    second = first + interval
    end = timeline["followup_end_day"]
    reduction = second + 7 * timeline["relative_medication_reduction_after_second_weeks_reported"]
    if not first < second <= reduction <= end:
        raise ValueError("Chronology is inconsistent")
    contrasts = []
    summaries = []
    endpoint_ids = set()
    for endpoint in data["endpoints"]:
        name = endpoint["endpoint"]
        if name in endpoint_ids:
            raise ValueError("Duplicate endpoint")
        endpoint_ids.add(name)
        groups = endpoint["groups"]
        if len(groups) != 3 or groups[0]["id"] != "baseline":
            raise ValueError("Expected baseline and two reported follow-up summaries")
        if len({group["id"] for group in groups}) != len(groups):
            raise ValueError("Duplicate group")
        for group in groups:
            for key in ["q1", "median", "q3"]:
                number(group[key], f"{name}.{key}", positive=True)
            if not group["q1"] <= group["median"] <= group["q3"]:
                raise ValueError("Quartile order must be q1 <= median <= q3")
            if group["n_measurements"] is not None:
                whole(group["n_measurements"], "n_measurements", positive=True)
            summaries.append({
                "endpoint": name, "unit": endpoint["unit"], "group": group["id"],
                "median": group["median"], "q1": group["q1"], "q3": group["q3"],
                "IQR_width": group["q3"] - group["q1"],
                "n_measurements": group["n_measurements"], "independent_patients": n,
            })
        baseline = groups[0]["median"]
        for group in groups[1:]:
            contrasts.append({
                "endpoint": name, "unit": endpoint["unit"],
                "comparison": group["id"] + "_vs_baseline",
                "difference_of_reported_medians": group["median"] - baseline,
                "ratio_of_reported_medians": group["median"] / baseline,
                "relative_difference_of_reported_medians_percent": 100 * (group["median"] / baseline - 1),
                "independent_patients": n,
                "interpretation": "Descriptive contrast of group summaries; not a paired-specimen ratio or causal effect",
            })
    weight = data["weight"]
    for key in ["start", "end"]:
        number(weight[key], "weight." + key, positive=True)
    for key in ["start_day", "end_day"]:
        whole(weight[key], "weight." + key)
    if weight["end_day"] <= weight["start_day"]:
        raise ValueError("Weight measurement order invalid")
    med_fraction = number(data["care_and_outcomes"]["relative_medication_fraction_of_start_reported"], "relative medication fraction", True)
    if med_fraction > 1:
        raise ValueError("Reported relative reduction must be within (0,1]")
    return {
        "analysis_type": "Single-patient descriptive contrasts of published summaries; no raw-series reconstruction or inference",
        "independent_patients": n,
        "summary_rows": summaries,
        "contrasts": contrasts,
        "timeline": {
            "time_unit": timeline["time_unit"],
            "second_intervention_day_derived": second,
            "first_to_followup_end_elapsed_days": end - first,
            "first_to_followup_end_inclusive_day_count": end - first + 1,
            "second_to_followup_end_elapsed_days": end - second,
            "nominal_relative_medication_reduction_day_derived_from_weeks": reduction,
            "nominal_relative_medication_reduction_to_followup_end_days": end - reduction,
            "medication_timing_precision": "Week-based source description converted arithmetically; not a reported exact clinical day",
            "reported_followup_after_first_weeks": timeline["reported_followup_after_first_weeks"],
            "reported_illness_window_after_second_weeks": timeline["reported_illness_window_after_second_weeks"],
            "rounding_note": "Rounded source week descriptions and calendar conventions are retained, not substituted for timestamp differences",
        },
        "weight_contrast": {
            "unit": weight["unit"], "difference": weight["end"] - weight["start"],
            "relative_difference_percent": 100 * (weight["end"] / weight["start"] - 1),
            "elapsed_days": weight["end_day"] - weight["start_day"],
            "reported_percentile_point_difference": weight["end_reported_percentile"] - weight["start_reported_percentile"],
            "interpretation": "Descriptive growth in an infant; not an editing-attributable effect or percentile-to-weight conversion",
        },
        "reported_relative_medication_fraction_of_start": med_fraction,
        "unavailable_inferences": {
            "raw_clinical_trajectory": "No numeric specimen series or complete specimen counts acquired",
            "protein_intake_percent_change": "No numeric intake series reconstructed; age-specific feeding target changes",
            "paired_ammonia_orotic_association": "Specimen correspondence and identical sampling windows unavailable",
            "clinical_causal_effect": "One uncontrolled case with concurrent care, illness, growth and unequal observation windows",
            "patient_corrected_allele_fraction": "No patient liver biopsy; unknown",
            "patient_corrected_hepatocyte_fraction": "No patient liver biopsy; allele-to-cell mapping also unavailable",
            "joint_corrected_viable_functional_cell_fraction": "No common patient molecular/cellular/function sampling frame",
            "ordinary_aging_coverage_fraction": "Inherited-lesion correction does not supply a natural-aging causal target or coverage threshold",
            "long_term_safety_or_durability": "Original short follow-up; no inference from absence of reported serious events",
        },
    }


def tables(result):
    out = io.StringIO(newline="")
    fields = ["endpoint", "unit", "comparison", "difference_of_reported_medians", "ratio_of_reported_medians", "relative_difference_of_reported_medians_percent", "independent_patients", "interpretation"]
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["contrasts"])
    return out.getvalue()


def verify_sources():
    manifest = json.loads((HERE / "source_manifest.json").read_text(encoding="utf-8"))
    verified = 0
    for source in manifest["sources"]:
        path = ROOT / source["cache_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("Source hash mismatch: " + source["id"])
        if path.stat().st_size != source["bytes"]:
            raise ValueError("Source size mismatch: " + source["id"])
        receipt = ROOT / source["receipt_path"]
        if not receipt.is_file():
            raise ValueError("Missing genuine source receipt")
        verified += 1
    return verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--verify-sources", action="store_true")
    args = parser.parse_args()
    data_path = HERE / "inputs.json"
    result = calculate(json.loads(data_path.read_text(encoding="utf-8")))
    result["inputs_sha256_canonical_utf8_lf"] = canonical_hash(data_path)
    result_text = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    csv_text = tables(result)
    for filename, content in [("results.json", result_text), ("clinical_summary_contrasts.csv", csv_text)]:
        path = HERE / filename
        if args.check:
            if path.read_text(encoding="utf-8") != content:
                raise SystemExit("Derived output differs: " + filename)
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
    if args.verify_sources:
        print(f"Verified {verify_sources()} cached primary source and receipt presence")
    print(f"Verified {len(result['summary_rows'])} published summary groups, {len(result['contrasts'])} descriptive contrasts; independent patients=1")


if __name__ == "__main__":
    main()
