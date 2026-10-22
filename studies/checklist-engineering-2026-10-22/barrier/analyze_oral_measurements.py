"""Describe frozen noninfectious oral-epithelial source summaries, offline."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return value


def compare(facts):
    if facts["schema_version"] != 1 or facts["evidence_unit"] != "published_aggregate_summary":
        raise ValueError("Expected published aggregate summaries")
    rows = facts["physical_properties"]
    if len(rows) != 4 or len({r["model"] for r in rows}) != 4:
        raise ValueError("Expected four distinct model summaries")
    by_model = {r["model"]: r for r in rows}
    for row in rows:
        if row["teer_unit"] != "ohm_cm2" or row["thickness_unit"] != "um":
            raise ValueError("Incompatible physical-property units")
        if row["dispersion"] != "SEM" or row["replicates_per_group"] != 3:
            raise ValueError("Preserve source SEM and reported replicate count")
        for field in ["teer_mean", "teer_sem", "thickness_mean", "thickness_sem"]:
            positive(row[field], field)
    tracer = facts["fd20_transport"]
    if tracer["tracer"] != "FITC_dextran_20_kDa" or tracer["unit"] != "cm_per_s":
        raise ValueError("Only frozen FD20 transport is eligible")
    if tracer["crosswalk_to_physical_properties"] is not None:
        raise ValueError("No source insert crosswalk is available")
    papp = tracer["reported_coefficients"]
    positive(papp["Submerged"], "Submerged Papp")
    positive(papp["ALI"], "ALI Papp")

    def ratio(numerator, denominator):
        left, right = by_model[numerator], by_model[denominator]
        return {"numerator": numerator, "denominator": denominator,
                "thickness_ratio_of_reported_means": left["thickness_mean"] / right["thickness_mean"],
                "teer_ratio_of_reported_means": left["teer_mean"] / right["teer_mean"],
                "paired_insert_effect": None, "confidence_interval": None}

    ali = ratio("ALI", "Submerged")
    fd_ratio = papp["ALI"] / papp["Submerged"]
    ali["fd20_papp_ratio_of_reported_coefficients"] = fd_ratio
    ali["fd20_papp_relative_difference_percent"] = (fd_ratio - 1) * 100
    return {
        "schema_version": 1,
        "evidence_kind": "descriptive_source_summary_comparison",
        "source_doi": facts["source"]["doi"],
        "model_summary_count": len(rows),
        "independent_donor_count": None,
        "comparison_ali_over_submerged": ali,
        "comparison_full_thickness_over_microtissue": ratio("Hu-FT", "Hu-Mic"),
        "teer_blank_subtraction": "source states R_cells minus R_blank, multiplied by insert growth area",
        "tr146_insert_area_cm2": facts["measurement_qualifiers"]["tr146_insert_area_cm2"],
        "direct_permeability_evidence": "reported FD20 apparent permeability only; not inferred from TEER or thickness",
        "clinical_equivalence": None,
        "joint_thickness_teer_transport_per_insert": None,
        "gingival_restoration_outcome": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", type=Path, default=HERE / "source_facts.json")
    parser.add_argument("--output", type=Path, default=HERE / "results.json")
    args = parser.parse_args()
    raw = args.facts.read_bytes()
    results = compare(json.loads(raw))
    results["source_facts_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.write_text(json.dumps(results, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(results, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
