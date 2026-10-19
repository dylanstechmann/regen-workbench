"""Source-data summaries and missing-evidence gates, not a fertility-risk model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def positive_number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a finite positive numeric observation")
    return float(value)


def mean_sd_sem(values: list[float]) -> dict:
    if len(values) < 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError("At least two finite numeric observations are required")
    sd = statistics.stdev(values)
    return {"n": len(values), "mean": statistics.mean(values), "sample_sd": sd, "sem": sd / math.sqrt(len(values))}


def selectivity_summaries(rows: list[dict]) -> dict:
    summaries = {}
    for compound in ["rapamycin", "DL001"]:
        group = [r for r in rows if r["compound"] == compound]
        if not group or len({r["biological_replicate"] for r in group}) != len(group):
            raise ValueError("Unique biological replicate pairs are required")
        c1 = [positive_number(r["c1_ic50_source_fM"], "C1 IC50") / 1000 for r in group]
        c2 = [positive_number(r["c2_ic50_source_fM"], "C2 IC50") / 1000 for r in group]
        ratios = [b / a for a, b in zip(c1, c2)]
        for ratio, source in zip(ratios, group):
            if not math.isclose(ratio, source["source_ratio_c2_c1"], rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("Replicate pairing does not reproduce source Figure1f ratios")
        summaries[compound] = {"C1_ic50_pM": mean_sd_sem(c1), "C2_ic50_pM": mean_sd_sem(c2), "paired_replicate_C2_C1_selectivity": ratios, "mean_of_paired_ratios": mean_sd_sem(ratios), "ratio_of_mean_ic50s": statistics.mean(c2) / statistics.mean(c1)}
    summaries["relative_DL001_vs_rapamycin"] = {
        "ratio_of_compound_mean_paired_selectivities": summaries["DL001"]["mean_of_paired_ratios"]["mean"] / summaries["rapamycin"]["mean_of_paired_ratios"]["mean"],
        "ratio_of_compound_ratios_of_mean_ic50s": summaries["DL001"]["ratio_of_mean_ic50s"] / summaries["rapamycin"]["ratio_of_mean_ic50s"],
        "cross_compound_replicate_pairing_assumed": False,
        "new_p_value": None,
        "interpretation": "Different descriptive estimands, not conflicting experiments. No reproductive or tissue selectivity follows from PC3 ratios."
    }
    return summaries


def reproductive_gate(evidence: dict) -> dict:
    required = ["testis_cell_native_parent_exposure", "testis_cell_C1_C2_time_context", "direct_reproductive_endpoints", "matched_specified_intended_function", "same_relevant_population_for_joint_comparison", "human_reproductive_candidate_comparison"]
    missing = [key for key in required if evidence.get(key) is not True]
    return {"joint_human_reproductive_protection_comparison_eligible": not missing, "missing": missing, "human_reproductive_risk_reduction_estimate": None}


def source_cells(workbook: Path, sheet_index: int) -> dict:
    """Read only worksheet/shared-string XML; no embedded images/structures."""
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(workbook) as archive:
        strings = ["".join(t.itertext()) for t in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("x:si", ns)]
        cells = {}
        for cell in ET.fromstring(archive.read(f"xl/worksheets/sheet{sheet_index}.xml")).findall("x:sheetData/x:row/x:c", ns):
            value = cell.find("x:v", ns)
            if value is not None:
                cells[cell.get("r")] = strings[int(value.text)] if cell.get("t") == "s" else float(value.text)
    return cells


def verify_cached_sources(inputs: dict, manifest: dict) -> dict:
    checked = []
    for source in manifest["source_files"]:
        path = REPO / source["relative_cached_path"]
        if not path.exists():
            raise ValueError(f"Source is not cached: {source['source_id']}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != source["sha256"]:
            raise ValueError(f"Source hash mismatch: {source['source_id']}")
        checked.append(source["source_id"])
    workbook = REPO / next(s["relative_cached_path"] for s in manifest["source_files"] if s["source_id"] == "dl001_source_data")
    ic, tissue, blood = [source_cells(workbook, index) for index in [4, 15, 44]]
    values_checked = 0
    for row in inputs["dl001_ic50"]["replicates"]:
        expected = [row["c1_ic50_source_fM"], row["c2_ic50_source_fM"], row["source_ratio_c2_c1"]]
        for address, value in zip(row["source_cells"], expected):
            if ic[address.split("!")[1]] != value:
                raise ValueError(f"Source extraction mismatch: {address}")
            values_checked += 1
    for row in inputs["dl001_tissue_pathway"]["series"]:
        address = row["source_cells"].split("!")[1]
        first, last = address.split(":")
        num = "".join(c for c in first if c.isdigit())
        for index, col in enumerate(range(ord(first[0]), ord(last[0]) + 1)):
            if tissue[f"{chr(col)}{num}"] != row["values"][index]:
                raise ValueError(f"Source extraction mismatch: {address}")
            values_checked += 1
    for row in inputs["dl001_blood_parent"]["series"]:
        col = row["source_cells"].split("!")[1][0]
        for index, value in enumerate(row["values_ng_per_mL_whole_blood"], 3):
            if blood[f"{col}{index}"] != value:
                raise ValueError(f"Source extraction mismatch: {col}{index}")
            values_checked += 1
    return {"source_hashes_checked": len(checked), "worksheet_numeric_values_checked": values_checked, "all_match": True, "excluded_partial_file": "dl001_partial_prefix is hashed for provenance, never used as a workbook"}


def calculate(inputs: dict) -> tuple[dict, list[dict]]:
    selection = selectivity_summaries(inputs["dl001_ic50"]["replicates"])
    tissue_rows = []
    for row in inputs["dl001_tissue_pathway"]["series"]:
        tissue_rows.append({"tissue": row["tissue"], "pathway_readout": row["pathway"], "compound": row["compound"], **mean_sd_sem(row["values"]), "source_cells": row["source_cells"], "unit": "source-normalized phosphorylation, not drug concentration or all-complex function"})
    blood_summary = {}
    for row in inputs["dl001_blood_parent"]["series"]:
        summary = mean_sd_sem(row["values_ng_per_mL_whole_blood"])
        for key, expected in [("mean", row["source_mean"]), ("sem", row["source_sem"])]:
            if not math.isclose(summary[key], expected, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("Blood source mean/SEM mismatch")
        blood_summary[row["compound"]] = summary
    mass = inputs["mouse_reproductive"]["testis_mass"]
    human = inputs["human_reproductive"]
    results = {
        "inputs_sha256": hashlib.sha256((HERE / "inputs.json").read_text(encoding="utf-8").encode("utf-8")).hexdigest(),
        "hash_convention": "UTF-8 text after universal-newline normalization to LF",
        "analysis_status": "Descriptive source reanalysis, no new significance/equivalence tests or reproductive-risk model",
        "PC3_cell_selectivity": selection,
        "tissue_pathway_series": len(tissue_rows),
        "tissue_pathway_interpretation": "Different tissues and source sex/context; zeros retained as normalized readouts, not proof of absent kinase activity. No parent tissue exposure is measured by these values.",
        "reported_whole_blood_compound_concentration_ng_per_mL": blood_summary,
        "whole_blood_DL001_to_rapamycin_mean_ratio": blood_summary["DL001"]["mean"] / blood_summary["rapamycin"]["mean"],
        "blood_parent_exposure_qualification": "Single reported post-administration whole-blood time point, not AUC, oral F, unbound or testis concentration. Assay validation/specificity not established from the retrieved main-text methods. Cannot match to female Figure3d animals or infer cause of pathway selectivity.",
        "adult_mouse_testis_mass": {
            "rapamycin_to_control_reported_mean_ratio": mass["rapamycin_mean"] / mass["control_mean"],
            "reported_mean_difference_mg_per_pair": mass["rapamycin_mean"] - mass["control_mean"],
            "control_n_animals": mass["control_n_animals"], "rapamycin_n_animals": mass["rapamycin_n_animals"],
            "individual_observations_or_new_confidence_interval": None,
            "human_testicular_volume_inference": None,
            "mechanistic_attribution_to_C2_alone": None
        },
        "human_transplant_descriptive_contrasts": {
            "total_sperm_count_mean_difference_million": human["sperm_count_total_million"]["sirolimus"] - human["sperm_count_total_million"]["no_sirolimus"],
            "motile_sperm_mean_difference_percentage_points": human["motile_sperm_percent"]["sirolimus"] - human["motile_sperm_percent"]["no_sirolimus"],
            "n_semen_by_regimen": None,
            "adjusted_causal_effect": None,
            "probability_of_infertility_or_recovery": None,
            "comparison_to_DL001": None,
            "interpretation": "Unadjusted differences of reported abstract means in transplant recipients. Respondents are not the established semen sample size; no healthy-person effect or testicular-volume estimate follows."
        },
        "candidate_joint_evidence_gates": {compound: reproductive_gate(evidence) for compound, evidence in inputs["reproductive_comparison_gate_inputs"].items()},
        "human_safe_analogue_or_equivalent_benefit_identified": False,
        "recovery_qualification": inputs["mouse_reproductive"]["recovery"]
    }
    return results, tissue_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-cache", action="store_true")
    args = parser.parse_args()
    inputs = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
    manifest = json.loads((HERE / "source_manifest.json").read_text(encoding="utf-8"))
    results, rows = calculate(inputs)
    if args.check_cache:
        print(json.dumps(verify_cached_sources(inputs, manifest)))
    (HERE / "results.json").write_text(json.dumps(results, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (HERE / "tissue_pathway_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"selectivity_biological_pairs": len(inputs["dl001_ic50"]["replicates"]), "tissue_series": len(rows), "reproductive_candidate_rank": None}))


if __name__ == "__main__":
    main()
