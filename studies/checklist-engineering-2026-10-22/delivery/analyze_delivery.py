"""Compare source-printed association summaries, without inventing paired data."""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXPECTED_PANELS = {
    "2d": ("Liver SORT", "liver", 1), "2e": ("Liver SORT", "liver", 24),
    "2i": ("Lung SORT", "lung", 1), "2j": ("Lung SORT", "lung", 24),
    "2n": ("Spleen SORT", "spleen", 1), "2o": ("Spleen SORT", "spleen", 24),
}

def decimal_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("Expected a finite numeric value")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Expected a finite numeric value")
    return result

def compare(inputs: dict) -> dict:
    places = inputs["rounding_assumption"]["decimal_places"]
    if not isinstance(places, int) or isinstance(places, bool) or not 0 <= places <= 6:
        raise ValueError("Unsupported display precision")
    half_unit = Decimal(10) ** -places / 2
    groups = {}
    panels = set()
    for row in inputs["reported_associations"]:
        value = decimal_number(row["reported_r_squared"])
        if not 0 <= value <= 1:
            raise ValueError("R-squared must lie in [0,1]")
        key = (row["formulation_label"], row["target_organ"])
        time = row["qpcr_time_h"]
        if isinstance(time, bool) or isinstance(row["reporter_time_h"], bool) or time not in (1, 24) or row["reporter_time_h"] != 24:
            raise ValueError("Unexpected time scope")
        if EXPECTED_PANELS.get(row["panel"]) != (*key, time):
            raise ValueError("Panel does not match frozen source formulation-organ-time mapping")
        if row["panel"] in panels or time in groups.setdefault(key, {}):
            raise ValueError("Duplicate panel or formulation-organ-time key")
        panels.add(row["panel"])
        groups[key][time] = (value, row["panel"])
    if panels != set(EXPECTED_PANELS):
        raise ValueError("All six expected source panels are required")
    rows = []
    for (formulation, organ), times in groups.items():
        if set(times) != {1, 24}:
            raise ValueError("Both time summaries required within formulation and organ")
        early, early_panel = times[1]
        late, late_panel = times[24]
        lower = max(Decimal(0), early-half_unit) - min(Decimal(1), late+half_unit)
        upper = min(Decimal(1), early+half_unit) - max(Decimal(0), late-half_unit)
        rows.append({"formulation_label": formulation, "target_organ": organ,
                     "early_panel": early_panel, "late_panel": late_panel,
                     "reported_r_squared_1h": float(early), "reported_r_squared_24h": float(late),
                     "early_association_time_pair_h": {"qpcr": 1, "reporter": 24},
                     "late_association_time_pair_h": {"qpcr": 24, "reporter": 24},
                     "reported_difference_1h_minus_24h": float(early-late),
                     "display_rounding_difference_enclosure": [float(lower), float(upper)],
                     "earlier_association_higher_under_rounding_assumption": lower > 0,
                     "unit": "Difference of dimensionless reported R-squared summaries",
                     "individual_pairing": "Unavailable; not inferred from matched group labels"})
    return {
        "evidence_kind": "source_summary_analysis",
        "source_doi": inputs["study"]["doi"],
        "source_figure": inputs["study"]["source_figure"],
        "annotation_count": len(panels),
        "within_formulation_organ_comparisons": rows,
        "comparison_count": len(rows),
        "earlier_higher_count_under_rounding_assumption": sum(r["earlier_association_higher_under_rounding_assumption"] for r in rows),
        "rounding_enclosure_meaning": "Display precision only. Neither statistical uncertainty nor a confidence interval.",
        "new_correlation_fit": False,
        "association_difference_significance": None,
        "out_of_sample_prediction_error": None,
        "independent_animal_n_from_image_fields": None,
        "source_reported_discordance": inputs["source_reported_discordance"],
        "unavailable_endpoints": {key: None for key in inputs["unavailable_endpoints"]},
    }

def verify_sources(manifest: dict, root: Path = ROOT) -> list:
    checked = []
    for row in manifest["retained_sources"]:
        raw = (root / row["cache_path"]).read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError(f"Source byte/hash mismatch: {row['source_id']}")
        receipt = json.loads((root / row["actual_fetch_receipt"]).read_text(encoding="utf-8"))
        if receipt.get("sha256") != row["sha256"] or receipt.get("bytes") != row["bytes"] or receipt.get("requested_url") != row["url"] or receipt.get("output_relative_path") != row["cache_path"]:
            raise ValueError(f"Actual fetch receipt mismatch: {row['source_id']}")
        checked.append(row["source_id"])
    return checked

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-sources", action="store_true", help="Verify retained source bytes/actual receipts offline")
    args = parser.parse_args()
    inputs = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
    results = compare(inputs)
    (HERE / "results.json").write_text(json.dumps(results, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if args.verify_sources:
        checked = verify_sources(json.loads((HERE / "source_manifest.json").read_text(encoding="utf-8")))
        print(json.dumps({"verified_actual_sources": checked}))
    print(json.dumps({"comparisons": results["comparison_count"], "earlier_higher": results["earlier_higher_count_under_rounding_assumption"]}))

if __name__ == "__main__":
    main()
