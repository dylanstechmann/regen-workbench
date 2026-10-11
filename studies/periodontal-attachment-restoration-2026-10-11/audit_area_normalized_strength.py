"""Reconcile the PDGF-BB paper's area-normalized strength arithmetic."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen

HERE = Path(__file__).resolve().parent
INPUT = HERE / "mechanics_benchmark_inputs.json"
SUPPLEMENT = ROOT / "data" / "literature" / "dental-attachment-mechanics" / "41598_2022_6865_MOESM1_ESM.pdf"
EXPECTED_SUPPLEMENT_MD5 = "1c3c2d21a96406cdef8fe243d5fa1924"
OUTPUT = HERE / "derived" / "area_normalized_strength_audit.json"


def decimal(value: int | float) -> Decimal:
    return Decimal(str(value))


def main() -> None:
    source = json.loads(INPUT.read_text(encoding="utf-8"))["sources"][0]
    supplement = source["supplementary_table_s3_reconstruction"]
    if not SUPPLEMENT.is_file():
        raise FileNotFoundError(
            "Official supplementary PDF is missing; run "
            "studies/dental-attachment-mechanics-2026-10-11/fetch_mechanics_sources.py first."
        )
    source_md5 = hashlib.md5(SUPPLEMENT.read_bytes()).hexdigest()
    if source_md5 != EXPECTED_SUPPLEMENT_MD5:
        raise ValueError(f"Official supplementary PDF checksum mismatch: {source_md5}")

    group_results = {}
    for name in ("NC", "PDGF_BB"):
        row = supplement[name]
        area_sum = sum((decimal(value) for value in row["root_surface_areas_mm2"]), Decimal(0))
        total_area = decimal(row["total_root_surface_area_mm2"])
        if area_sum != total_area:
            raise ValueError(f"Root surface areas do not sum to the Table S3 total for {name}")
        stress_from_mean_load = decimal(row["group_mean_maximum_load_N"]) / total_area
        table_stress = decimal(row["table_mechanical_strength_N_per_mm2"])
        if abs(stress_from_mean_load - table_stress) >= Decimal("0.005"):
            raise ValueError(f"Reconstructed strength does not round to Table S3 for {name}")
        group_results[name] = {
            "representative_tooth_id": row["representative_tooth_id"],
            "root_surface_areas_mm2": row["root_surface_areas_mm2"],
            "total_root_surface_area_mm2": str(total_area),
            "root_surface_area_sum_check": str(area_sum),
            "group_mean_maximum_load_N": str(decimal(row["group_mean_maximum_load_N"])),
            "reconstructed_strength_N_per_mm2": f"{stress_from_mean_load:.8f}",
            "table_strength_N_per_mm2": str(table_stress),
        }

    treated = supplement["PDGF_BB"]
    control = supplement["NC"]
    treatment_table_strength = decimal(treated["table_mechanical_strength_N_per_mm2"])
    control_table_strength = decimal(control["table_mechanical_strength_N_per_mm2"])
    table_strength_ratio = treatment_table_strength / control_table_strength
    reconstructed_treatment = decimal(group_results["PDGF_BB"]["reconstructed_strength_N_per_mm2"])
    reconstructed_control = decimal(group_results["NC"]["reconstructed_strength_N_per_mm2"])
    reconstructed_ratio = reconstructed_treatment / reconstructed_control

    lower_rounding_bound = (treatment_table_strength - Decimal("0.005")) / (control_table_strength + Decimal("0.005"))
    upper_rounding_bound = (treatment_table_strength + Decimal("0.005")) / (control_table_strength - Decimal("0.005"))
    published_claim = Decimal("0.76")
    needed_treatment_strength = published_claim * control_table_strength
    needed_control_strength = treatment_table_strength / published_claim

    audit = {
        "schema_version": 1,
        "purpose": "Source-level arithmetic audit; not a reanalysis of animal-level data.",
        "primary_article_doi": source["doi"],
        "supplement_url": supplement["source_url"],
        "supplement_sha256": regen.sha256_file(SUPPLEMENT),
        "supplement_md5": source_md5,
        "source_table": supplement["source_table"],
        "table_reconstruction": group_results,
        "ratio_comparisons": {
            "published_text_fraction": str(published_claim),
            "published_table_strength_quotient": f"{table_strength_ratio:.10f}",
            "published_table_strength_quotient_percent": f"{table_strength_ratio * 100:.4f}",
            "ratio_reconstructed_from_group_mean_load_and_representative_area": f"{reconstructed_ratio:.10f}",
            "ratio_reconstructed_percent": f"{reconstructed_ratio * 100:.4f}",
            "rounded_table_strength_quotient_range_percent": {
                "lower": f"{lower_rounding_bound * 100:.4f}",
                "upper": f"{upper_rounding_bound * 100:.4f}",
                "assumption": "Each printed strength is rounded to the nearest 0.01 N/mm^2.",
            },
            "treatment_strength_needed_for_76_percent_at_reported_control": f"{needed_treatment_strength:.6f} N/mm^2",
            "control_strength_needed_for_76_percent_at_reported_treatment": f"{needed_control_strength:.6f} N/mm^2",
            "gap_between_published_claim_and_rounded_quotient_percentage_points": f"{(published_claim - table_strength_ratio) * 100:.4f}",
        },
        "finding": "The official supplement reproduces the displayed 2.45 and 3.39 N/mm^2 values, but their quotient is 72.27%; using the Table S3 loads and representative-tooth areas gives 72.39%. Rounding the displayed strengths cannot produce 76%. The discrepancy remains unresolved without the underlying records or calculation worksheet.",
        "unit_of_analysis_limit": "Table S3 combines group mean maximum load from Figure 2d with root surface area measured on one representative tooth per group. This is a source-level ratio audit, not a per-animal area-normalized effect estimate; the paper says supporting data are available on reasonable request.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    regen.record(
        "periodontal-area-normalized-strength-source-audit",
        {
            "article_doi": source["doi"],
            "supplement_sha256": audit["supplement_sha256"],
            "supplement_md5": source_md5,
            "table": supplement["source_table"],
            "ratio_from_displayed_strengths": audit["ratio_comparisons"]["published_table_strength_quotient"],
        },
        [OUTPUT],
    )
    print(json.dumps(audit["ratio_comparisons"], ensure_ascii=False))


if __name__ == "__main__":
    main()
