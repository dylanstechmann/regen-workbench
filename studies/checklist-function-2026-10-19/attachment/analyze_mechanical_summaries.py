"""Bounded arithmetic on observed printed summaries, never independent people."""
from __future__ import annotations
import argparse
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from extract_numeric_summaries import load_json, save_json, text_sha, verified_sources

def positive(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError("Expected a finite positive observed quantity")
    return value

def tissue_modulus_gate(post_stiffness, tissue_gauge_length=None, tissue_cross_section=None, passive_tissue_slope=None):
    """A post/sensor stiffness is not the construct's passive force slope."""
    positive(post_stiffness)
    missing = [name for name, value in (("tissue_gauge_length", tissue_gauge_length),
        ("tissue_cross_section", tissue_cross_section), ("passive_tissue_force_displacement_slope", passive_tissue_slope)) if value is None]
    if missing:
        return {"status": "unavailable", "missing": missing, "native_equivalence": "not_tested"}
    raise ValueError("This source-summary audit does not accept invented or externally supplied tissue geometry")

def analyze(extract):
    if extract["data_kind"] != "observed_primary_summary_numbers_no_synthetic_people_or_constructs":
        raise ValueError("Unexpected evidence kind")
    m, native = extract["magnetic"], extract["native"]
    stiffness = positive(m["calculated_post_stiffness_uN_per_um"])
    reference = positive(m["acellular_reference_length_um"])
    length = positive(m["PTC_length_mean_um"])
    if length >= reference:
        raise ValueError("Source baseline contraction does not shorten the reference")
    deflection = reference - length
    predicted_force = stiffness * deflection
    reported_force = positive(m["PTC_active_force_mean_uN"])
    calibration = {"evidence_kind": "recomputed_source_summary_arithmetic",
        "post_stiffness_N_per_m": stiffness,
        "post_stiffness_N_per_mm": stiffness / 1000,
        "bare_post_force_recomputed_uN": stiffness * positive(m["bare_post_deflection_um"]),
        "bare_post_force_source_uN": positive(m["source_bare_post_force_uN"]),
        "baseline_mean_shortening_um": deflection,
        "baseline_mean_shortening_fraction": deflection / reference,
        "force_from_reported_mean_length_and_post_stiffness_uN": predicted_force,
        "source_active_force_mean_uN": reported_force,
        "source_active_force_mean_N": reported_force * 1e-6,
        "force_mean_absolute_difference_uN": abs(predicted_force - reported_force),
        "force_mean_relative_difference_percent": 100 * abs(predicted_force - reported_force) / reported_force,
        "uncertainty_interval": None,
        "interpretation": "Force and length are algebraically linked through modeled post stiffness; numerical agreement is not independent validation. No stiffness uncertainty, raw repeated lengths, n/covariance or recovery distribution is invented.",
        "tissue_modulus": tissue_modulus_gate(stiffness)}
    rows = native["table2_rows"]
    expected = {(t, p) for t in ("Central incisors", "Lateral incisors") for p in (1., 3., 5.)}
    keys = [(r["tooth_class"], r["peak_load_N"]) for r in rows]
    if len(rows) != 6 or set(keys) != expected or len(set(keys)) != len(keys):
        raise ValueError("Missing or duplicate native tooth/regime summary")
    regimes = {r["peak_load_N"]: r for r in native["regimes"]}
    if set(regimes) != {1., 3., 5.} or len(native["regimes"]) != 3:
        raise ValueError("Missing or duplicate native mechanical regime")
    comparisons = []
    for r in rows:
        e1, e2 = positive(r["E1_mean_MPa"]), positive(r["E2_mean_MPa"])
        for name in ("E1_SD_MPa", "E2_SD_MPa", "source_mean_ultimate_strain"):
            positive(r[name])
        if e2 <= e1:
            raise ValueError("Source high-strain branch must exceed its low-strain branch")
        regime = regimes[r["peak_load_N"]]
        comparisons.append({"tooth_class": r["tooth_class"], "peak_load_N": r["peak_load_N"],
            "loading_rate_N_per_min": regime["loading_rate_N_per_min"], "E2_to_E1_ratio_of_source_means": e2 / e1,
            "source_bilinear_transition_strain": r["source_mean_ultimate_strain"]})
    changes = []
    for tooth in ("Central incisors", "Lateral incisors"):
        low, high = [next(r for r in rows if r["tooth_class"] == tooth and r["peak_load_N"] == p) for p in (1, 5)]
        changes.append({"tooth_class": tooth, "E1_5N_regime_to_1N_regime_ratio_of_means": high["E1_mean_MPa"] / low["E1_mean_MPa"],
            "E2_5N_regime_to_1N_regime_ratio_of_means": high["E2_mean_MPa"] / low["E2_mean_MPa"]})
    means = [r[name] for r in rows for name in ("E1_mean_MPa", "E2_mean_MPa")]
    max_row = max(rows, key=lambda r: r["E2_mean_MPa"])
    summary = {"evidence_kind": "separate_native_passive_aggregate_reference",
        "source_summary_rows": len(rows), "independent_human_donors_reported": 3, "teeth_reported": 6, "slices_reported": 18,
        "individual_donor_ages_or_crosswalk_available": False,
        "all_branch_summary_mean_min_MPa": min(means), "all_branch_summary_mean_max_MPa": max(means),
        "ratio_of_largest_to_smallest_summary_mean": max(means) / min(means),
        "upper_discussion_value_MPa": native["source_discussion_upper_value_MPa"],
        "largest_E2_mean_plus_its_SD_MPa": max_row["E2_mean_MPa"] + max_row["E2_SD_MPa"],
        "individual_extreme_range": None,
        "regime_effects": changes, "per_regime_branch_ratios": comparisons,
        "loading_rate_and_peak_load_identically_coupled": all(r["peak_load_N"] == r["loading_rate_N_per_min"] for r in native["regimes"]),
        "interpretation": "Ratios of aggregate means only; no donor-paired effect, independent rate effect, confidence interval, distribution of individual ratios or physiological acceptance band. Source epsilon is a bilinear transition, not rupture strain."}
    return {"magnetic_construct": calibration, "native_passive_reference": summary,
        "joint_age_niche_or_attachment_function_result": "unavailable",
        "native_construct_modulus_equivalence": "not_tested_different_quantities_and_missing_geometry",
        "individual_construct_recovery_fraction": None,
        "donor_age_effect": None, "rejuvenation_claim": False,
        "boundary": "Active cell contraction, passive tissue modulus, bilateral inserted attachment and stable original tooth pose are separate outcomes; no source is upgraded into regenerated attachment or durable human repair."}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-cache", action="store_true")
    args = parser.parse_args()
    if args.verify_cache:
        verified_sources()
    extract = load_json(HERE / "source_summary_extract.json")
    if extract["cache_receipts_text_sha256"] != text_sha(HERE / "source_receipts.json"):
        raise ValueError("Source receipts changed after extraction")
    if extract["extractor_text_sha256"] != text_sha(HERE / "extract_numeric_summaries.py"):
        raise ValueError("Extractor changed after extraction")
    out = HERE / "derived"
    result = analyze(extract)
    save_json(out / "mechanical_summary_results.json", result)
    save_json(out / "analysis_receipt.json", {"analysis_text_sha256": text_sha(Path(__file__)),
        "plan_text_sha256": text_sha(HERE / "analysis_plan.json"), "extract_text_sha256": text_sha(HERE / "source_summary_extract.json"),
        "qualification_text_sha256": text_sha(HERE / "source_qualification.json"),
        "source_receipts_text_sha256": text_sha(HERE / "source_receipts.json"),
        "results_text_sha256": text_sha(out / "mechanical_summary_results.json"),
        "evidence_kind": "observed_printed_aggregate_summary_reanalysis_not_individual_construct_data",
        "raw_cache_required_for_default_analysis": False, "new_data_acquired_by_analysis": False,
        "software": {"python": sys.version.split()[0], "third_party_analysis_packages": []}})
    print("Recomputed aggregate force/contraction audit and all six native mechanical summaries; no age or individual recovery fit")

if __name__ == "__main__":
    main()
