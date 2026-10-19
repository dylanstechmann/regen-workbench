"""Challenge existing public gingival scores at their inferred-donor unit.

No original H5AD is reread and no features are selected or trained here. Input
text hashes use UTF-8 with LF newlines so checkout line endings do not change
the scientific receipt. Existing subtype raw counts support an independently
specified, equal-RNA-mixture sensitivity, not a counterfactual tissue model.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import platform

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def text_sha(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"No output records: {path}")
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, keys, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def validate_scores(rows: list[dict], crosswalk: list[dict], min_cells: int) -> None:
    """Reject duplicate donor outcomes and inconsistent repeated-biopsy metadata."""
    sample_meta = {}
    donor_meta = {}
    for row in crosswalk:
        sample = row["sample_id"]
        if sample in sample_meta:
            raise ValueError("Duplicate source library")
        sample_meta[sample] = row
        donor = row["inferred_donor_group"]
        metadata = (row["condition"], row["age"], row["sex"])
        if donor in donor_meta and donor_meta[donor] != metadata:
            raise ValueError("Inconsistent inferred-donor metadata")
        donor_meta[donor] = metadata
    if Counter(value[0] for value in donor_meta.values()) != {"healthy": 13, "periodontitis": 5}:
        raise ValueError("Source no longer has the qualified 13/5 donor groups")
    seen = set()
    for row in rows:
        key = (row["donor"], row["cell_group"], row["panel"])
        if key in seen:
            raise ValueError("Duplicate donor/cell-group/panel outcome")
        seen.add(key)
        if (row["condition"], row["age"], row["sex"]) != donor_meta[row["donor"]]:
            raise ValueError("Score/source donor metadata mismatch")
        versions = set()
        for sample in row["samples"].split(";"):
            source = sample_meta[sample]
            if source["inferred_donor_group"] != row["donor"]:
                raise ValueError("Biopsy counted under a different donor")
            versions.add(source["cellranger_version"])
        if ";".join(sorted(versions)) != row["cellranger_versions"]:
            raise ValueError("Processing metadata mismatch")
        if row["sex"] not in {"female", "male"} or row["condition"] not in {"healthy", "periodontitis"}:
            raise ValueError("Unexpected condition or sex category")
        if row["cellranger_versions"] not in {"2.0.0", "3.0.1"}:
            raise ValueError("Mixed or unknown processing version")
        values = [float(row["age"]), float(row["score_mean_log1p_cpm"])]
        if not np.isfinite(values).all() or int(row["n_cells"]) < min_cells:
            raise ValueError("Invalid score or source cell gate")


def overlap_bounds(records: list[dict]) -> tuple[float, float] | None:
    healthy = [float(row["age"]) for row in records if row["condition"] == "healthy"]
    cases = [float(row["age"]) for row in records if row["condition"] == "periodontitis"]
    if not healthy or not cases:
        return None
    lower, upper = max(min(healthy), min(cases)), min(max(healthy), max(cases))
    return (lower, upper) if lower <= upper else None


def restrict_records(records: list[dict], model: str, bounds: tuple | None) -> list[dict]:
    if model not in {"age_overlap", "female_age_overlap"}:
        return records
    if bounds is None:
        return []
    return [row for row in records if bounds[0] <= float(row["age"]) <= bounds[1]
            and (model != "female_age_overlap" or row["sex"] == "female")]


def fit_effect(records: list[dict], model: str, target: str = "disease", min_df: int = 2) -> dict:
    """Return retained failure states; never drop covariates to rescue a fit."""
    if target not in {"disease", "age"}:
        raise ValueError("Unknown target")
    allowed = {"unadjusted", "age", "age_sex", "age_version", "age_sex_version",
               "age_overlap", "female_age_overlap"}
    if model not in allowed or (target == "age" and model == "unadjusted"):
        raise ValueError("Unknown model")
    counts = Counter(row["condition"] for row in records)
    result = {"n_donors": len(records), "n_healthy": counts["healthy"],
              "n_periodontitis": counts["periodontitis"], "status": "unfitted",
              "coefficient": "", "residual_df": "", "design_rank": "",
              "design_columns": "", "design_condition_number": "",
              "maximum_leverage": "", "max_leverage_donor": ""}
    if not records or (target == "disease" and (not counts["healthy"] or not counts["periodontitis"])):
        return {**result, "status": "missing_condition_or_empty"}
    if len({row["donor"] for row in records}) != len(records):
        raise ValueError("Fit requires one row per donor")
    ages = np.asarray([float(row["age"]) for row in records])
    y = np.asarray([float(row["score_mean_log1p_cpm"]) for row in records])
    if not np.isfinite(ages).all() or not np.isfinite(y).all():
        raise ValueError("Non-finite donor age or score")
    if target == "age" and counts["periodontitis"]:
        raise ValueError("Healthy age fits must not pool disease donors")
    columns = [np.ones(len(records))]
    names = ["intercept"]
    if target == "disease":
        columns.append(np.asarray([row["condition"] == "periodontitis" for row in records], dtype=float))
        names.append("disease")
    if model != "unadjusted":
        columns.append((ages - ages.mean()) / 10)
        names.append("age_decades")
    if "sex" in model:
        columns.append(np.asarray([row["sex"] == "male" for row in records], dtype=float))
        names.append("male")
    if "version" in model:
        columns.append(np.asarray([row["cellranger_versions"] == "3.0.1" for row in records], dtype=float))
        names.append("cellranger_3")
    design = np.column_stack(columns)
    rank = int(np.linalg.matrix_rank(design))
    df = len(records) - design.shape[1]
    result.update(residual_df=df, design_rank=rank, design_columns=design.shape[1])
    if rank != design.shape[1]:
        return {**result, "status": "rank_deficient"}
    if df < min_df:
        return {**result, "status": "insufficient_residual_df"}
    beta = np.linalg.lstsq(design, y, rcond=None)[0]
    leverage = np.sum(design * np.linalg.pinv(design).T, axis=1)
    max_id = int(np.argmax(leverage))
    result.update(status="descriptive_only", coefficient=float(beta[names.index("disease" if target == "disease" else "age_decades")]),
                  design_condition_number=float(np.linalg.cond(design)), maximum_leverage=float(leverage[max_id]),
                  max_leverage_donor=records[max_id]["donor"])
    return result


def build_fixed_mixture(raw: list[dict], scores: list[dict], coverage: list[dict], plan: dict) -> tuple[list[dict], list[dict]]:
    """Audit exact count nesting, then average subtype CPM before log1p."""
    selected_groups = {"fibroblasts_all", "fibroblast_1", "fibroblast_2"}
    grouped = defaultdict(dict)
    metadata = {}
    for row in raw:
        if row["cell_group"] not in selected_groups:
            continue
        key = (row["donor"], row["cell_group"])
        gene = row["gene_symbol"]
        if gene in grouped[key]:
            raise ValueError("Duplicate pseudobulk gene")
        grouped[key][gene] = int(row["raw_count"])
        current = (int(row["total_raw_umis"]), int(row["n_cells"]))
        if grouped[key][gene] < 0 or grouped[key][gene] > current[0]:
            raise ValueError("Invalid pseudobulk gene count")
        if key in metadata and metadata[key] != current:
            raise ValueError("Gene rows have inconsistent library metadata")
        metadata[key] = current
    panels = {row["panel"]: row["included_gene_symbols"].split(";") for row in coverage}
    score_keys = {(row["donor"], row["panel"]): row for row in scores if row["cell_group"] == "fibroblasts_all"}
    output, audit = [], []
    weights = np.asarray(plan["fixed_subgroup_rna_weights"], dtype=float)
    if weights.shape != (2,) or not np.allclose(weights, [.5, .5], rtol=0, atol=0):
        raise ValueError("This challenge requires the frozen equal-RNA mixture")
    for donor in sorted({key[0] for key in score_keys}):
        all_key, first, second = [(donor, group) for group in ["fibroblasts_all", "fibroblast_1", "fibroblast_2"]]
        if any(key not in grouped for key in [all_key, first, second]):
            raise ValueError("Missing fibroblast subgroup")
        if not (grouped[all_key].keys() == grouped[first].keys() == grouped[second].keys()):
            raise ValueError("Subgroup gene coverage differs")
        if any(metadata[all_key][index] != metadata[first][index] + metadata[second][index] for index in [0, 1]):
            raise ValueError("Subgroup UMIs/cells do not sum to combined values")
        if any(grouped[all_key][gene] != grouped[first][gene] + grouped[second][gene] for gene in grouped[all_key]):
            raise ValueError("Subgroup counts do not sum to combined values")
        if min(metadata[first][1], metadata[second][1]) < plan["minimum_cells_each_subgroup"]:
            audit.append({"donor": donor, "status": "excluded_subgroup_cell_gate"})
            continue
        if min(metadata[first][0], metadata[second][0]) <= 0:
            raise ValueError("Empty subtype RNA library")
        w1 = metadata[first][0] / metadata[all_key][0]
        for (candidate, panel), original in sorted(score_keys.items()):
            if candidate != donor:
                continue
            genes = panels[panel]
            cpm = np.asarray([[grouped[key][gene] / metadata[key][0] * 1e6 for gene in genes]
                              for key in [first, second]])
            observed = float(np.log1p(w1 * cpm[0] + (1 - w1) * cpm[1]).mean())
            discrepancy = observed - float(original["score_mean_log1p_cpm"])
            if abs(discrepancy) > 1e-10:
                raise ValueError("Reconstructed score differs from original combined panel")
            fixed = float(np.log1p(weights @ cpm).mean())
            output.append({**original, "score_mean_log1p_cpm": fixed, "score_type": "fixed_50_50_subtype_RNA"})
            audit.append({"donor": donor, "condition": original["condition"], "age": original["age"], "panel": panel,
                          "status": "included", "fibroblast1_rna_fraction": w1,
                          "fibroblast1_cell_fraction": metadata[first][1] / metadata[all_key][1],
                          "fibroblast1_cells": metadata[first][1], "fibroblast2_cells": metadata[second][1],
                          "observed_score": observed, "reconstruction_error": discrepancy,
                          "fixed_mixture_score": fixed, "fixed_minus_observed": fixed - observed})
    return output, audit


def support_rows(crosswalk: list[dict]) -> list[dict]:
    donors = {row["inferred_donor_group"]: row for row in crosswalk}
    result = []
    for sex in ["all", "female", "male"]:
        current = [row for row in donors.values() if sex == "all" or row["sex"] == sex]
        for version in ["all", "2.0.0", "3.0.1"]:
            subset = [row for row in current if version == "all" or row["cellranger_version"] == version]
            records = [{**row, "donor": row["inferred_donor_group"]} for row in subset]
            bounds = overlap_bounds(records)
            overlap = [] if bounds is None else [row for row in records if bounds[0] <= float(row["age"]) <= bounds[1]]
            healthy = [int(row["age"]) for row in records if row["condition"] == "healthy"]
            cases = [int(row["age"]) for row in records if row["condition"] == "periodontitis"]
            result.append({"sex": sex, "version": version, "n_healthy": len(healthy), "n_disease": len(cases),
                           "healthy_ages": ";".join(map(str, sorted(healthy))), "disease_ages": ";".join(map(str, sorted(cases))),
                           "age_overlap_min": "" if bounds is None else bounds[0],
                           "age_overlap_max": "" if bounds is None else bounds[1],
                           "n_healthy_in_age_overlap": sum(row["condition"] == "healthy" for row in overlap),
                           "n_disease_in_age_overlap": sum(row["condition"] == "periodontitis" for row in overlap),
                           "interpretation": "Age-range intersection only; overlap is not matched sampling or causal exchangeability."})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=HERE / "analysis_plan.json")
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--out", type=Path, default=HERE / "derived")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    source = args.input_dir or ROOT / plan["input_directory"]
    for filename, expected in plan["input_sha256_lf_text"].items():
        if text_sha(source / filename) != expected:
            raise ValueError(f"Input text checksum mismatch: {filename}")
    scores = read_tsv(source / "gingival_fixed_panel_donor_scores.tsv")
    crosswalk = read_tsv(source / "oral_atlas_sample_crosswalk.tsv")
    coverage = read_tsv(source / "gingival_fixed_panel_coverage.tsv")
    raw = read_tsv(source / "gingival_cellset_pseudobulk_fixed_genes.tsv")
    validate_scores(scores, crosswalk, plan["minimum_cells_per_donor"])
    grouped = defaultdict(list)
    for row in scores:
        if row["cell_group"] in plan["primary_cell_groups"]:
            grouped[(row["cell_group"], row["panel"])].append(row)
    disease_rows, age_rows, omissions, robustness = [], [], [], []
    min_df = plan["minimum_residual_degrees_of_freedom"]
    for (cell_group, panel), records in sorted(grouped.items()):
        records.sort(key=lambda row: row["donor"])
        counts = Counter(row["condition"] for row in records)
        if counts["healthy"] < plan["minimum_original_healthy_donors"] or counts["periodontitis"] < plan["minimum_original_disease_donors"]:
            disease_rows.append({"cell_group": cell_group, "panel": panel, "status": "source_coverage_ineligible"})
            continue
        bounds = overlap_bounds(records)
        for model in plan["disease_models"]:
            current = restrict_records(records, model, bounds)
            fitted = fit_effect(current, model, min_df=min_df)
            disease_rows.append({"cell_group": cell_group, "panel": panel, "model": model,
                                 "age_overlap_min": "" if bounds is None else bounds[0],
                                 "age_overlap_max": "" if bounds is None else bounds[1], **fitted})
        healthy = [row for row in records if row["condition"] == "healthy"]
        for model in plan["healthy_age_models"]:
            age_rows.append({"cell_group": cell_group, "panel": panel, "model": model,
                             **fit_effect(healthy, model, "age", min_df)})
        for model in plan["influence_models"]:
            baseline = fit_effect(records, model, min_df=min_df)
            fitted_omissions = []
            for omitted in records:
                current = [row for row in records if row["donor"] != omitted["donor"]]
                fitted = fit_effect(current, model, min_df=min_df)
                fitted_omissions.append({"omitted_condition": omitted["condition"], **fitted})
                omissions.append({"cell_group": cell_group, "panel": panel, "model": model,
                                  "omitted_donor": omitted["donor"], "omitted_condition": omitted["condition"], **fitted})
            values = [row["coefficient"] for row in fitted_omissions if row["status"] == "descriptive_only"]
            case_values = [row["coefficient"] for row in fitted_omissions
                           if row["status"] == "descriptive_only" and row["omitted_condition"] == "periodontitis"]
            robustness.append({"cell_group": cell_group, "panel": panel, "model": model,
                               "full_coefficient": baseline["coefficient"], "n_omissions": len(records),
                               "n_fit_failures": len(records) - len(values),
                               "omission_min": min(values) if values else "", "omission_max": max(values) if values else "",
                               "case_omission_min": min(case_values) if case_values else "",
                               "case_omission_max": max(case_values) if case_values else "",
                               "n_sign_changes": sum(np.sign(value) != np.sign(baseline["coefficient"]) for value in values)
                               if baseline["coefficient"] != "" else ""})
    fixed, mixture_audit = build_fixed_mixture(raw, scores, coverage, plan["fibroblast_mixture_challenge"])
    mixture_effects = []
    for panel in sorted({row["panel"] for row in fixed}):
        adjusted = [row for row in fixed if row["panel"] == panel]
        included = {row["donor"] for row in adjusted}
        observed = [row for row in scores if row["cell_group"] == "fibroblasts_all" and row["panel"] == panel and row["donor"] in included]
        for target in ["disease", "age"]:
            for model in plan["healthy_age_models"]:
                for label, records in [("observed_mixture", observed), ("fixed_50_50_subtype_RNA", adjusted)]:
                    current = records if target == "disease" else [row for row in records if row["condition"] == "healthy"]
                    mixture_effects.append({"panel": panel, "target": target, "model": model, "score_type": label,
                                           **fit_effect(current, model, target, min_df)})
    args.out.mkdir(parents=True, exist_ok=True)
    outputs = {"donor_common_support.tsv": support_rows(crosswalk), "disease_adjustment_challenge.tsv": disease_rows,
               "healthy_age_adjustment_challenge.tsv": age_rows, "donor_omission_effects.tsv": omissions,
               "donor_omission_summary.tsv": robustness, "fibroblast_mixture_audit.tsv": mixture_audit,
               "fibroblast_mixture_effects.tsv": mixture_effects}
    for filename, rows in outputs.items():
        write_tsv(args.out / filename, rows)
    summary = {
        "source_accession": "GSE164241", "source_commit": plan["source_commit"],
        "source_h5ad_sha256_from_prior_receipt": "7dc13de46fd2702dbfaf8d69bec933b79b05196ebce7d516e59cea471aa83c4e",
        "source_h5ad_reread": False, "new_network_fetch": False,
        "plan_sha256_lf_text": text_sha(args.plan), "script_sha256_lf_text": text_sha(Path(__file__)),
        "input_sha256_lf_text": plan["input_sha256_lf_text"],
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "unit": "inferred donor; repeated biopsies already aggregated; cell groups and panels share donors",
        "disease_model_rows": len(disease_rows), "healthy_age_model_rows": len(age_rows),
        "omission_rows": len(omissions), "mixture_model_rows": len(mixture_effects),
        "disease_coefficient_units": "mean log1p(CPM) difference; not fold change, activity, tissue function or years of age",
        "age_coefficient_units": "mean log1p(CPM) per 10 chronological years; cross-sectional association",
        "mixture_reconstruction_max_abs_error": max(abs(row["reconstruction_error"]) for row in mixture_audit if row["status"] == "included"),
        "output_sha256_lf_text": {name: text_sha(args.out / name) for name in outputs},
        "limits": plan["interpretation"] + [
            "Original donor IDs are inferred, not formally supplied independent-person identifiers.",
            "Equal subtype RNA weights may remove relevant biology and do not separate individual cell states within each annotated subgroup.",
            "All adjustments are observational, panel/cell-group dependent and based on a single cohort; no patient intervention, clock training or functional repair was tested."
        ],
    }
    (args.out / "analysis_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: summary[key] for key in ["disease_model_rows", "healthy_age_model_rows", "omission_rows", "mixture_model_rows", "mixture_reconstruction_max_abs_error"]}, indent=2))


if __name__ == "__main__":
    main()
