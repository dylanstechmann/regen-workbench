"""Fixed ECM gene contributions and demographic support sensitivities."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import platform
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from freeze_populations import read_tsv, text_sha, populations

COHORT = {"fibroblast_only": "GSE164241", "observed_partial_capture": "GSE164241",
          "common_RNA_partial_capture": "GSE164241", "bulk_gingiva": "GSE173078"}


def write_tsv(path: Path, rows: list[dict]) -> None:
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, keys, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fit_genes(metadata: list[dict], outcomes: np.ndarray, model: str) -> dict:
    if outcomes.ndim != 2 or outcomes.shape[0] != len(metadata) or not np.isfinite(outcomes).all():
        raise ValueError("Require finite donor x gene outcomes")
    if len({row["donor"] for row in metadata}) != len(metadata):
        raise ValueError("One row per donor is required")
    if model not in {"age_only", "age_sex_processing"}:
        raise ValueError("Unknown frozen model")
    if any(row["sex"] not in {"male", "female"} or row["processing"] not in {0, 1} for row in metadata):
        raise ValueError("Unknown source covariate category")
    result = {"status": "unfitted", "n_donors": len(metadata), "rank": "", "residual_df": "",
              "maximum_leverage": "", "maximum_leverage_donor": "", "gene_slopes": None, "panel_slope": None,
              "age_min": min((row["age"] for row in metadata), default=""),
              "age_max": max((row["age"] for row in metadata), default="")}
    if not metadata:
        return {**result, "status": "empty_population"}
    age = np.asarray([row["age"] for row in metadata], dtype=float)
    if not np.isfinite(age).all():
        raise ValueError("Non-finite donor age")
    columns = [np.ones(len(metadata)), (age - age.mean()) / 10]
    if model == "age_sex_processing":
        columns.extend([np.asarray([row["sex"] == "male" for row in metadata], dtype=float),
                        np.asarray([row["processing"] for row in metadata], dtype=float)])
    design = np.column_stack(columns)
    rank, df = int(np.linalg.matrix_rank(design)), len(metadata) - design.shape[1]
    result.update(rank=rank, residual_df=df)
    if rank < design.shape[1]:
        return {**result, "status": "rank_deficient"}
    if df < 2:
        return {**result, "status": "insufficient_residual_df"}
    gene_slopes = np.linalg.lstsq(design, outcomes, rcond=None)[0][1]
    direct_panel = float(np.linalg.lstsq(design, outcomes.mean(axis=1), rcond=None)[0][1])
    if not np.isclose(direct_panel, gene_slopes.mean(), atol=1e-12, rtol=0):
        raise ValueError("Gene contributions no longer reconstruct the fixed panel")
    leverage = np.sum(design * np.linalg.pinv(design).T, axis=1)
    which = int(np.argmax(leverage))
    return {**result, "status": "descriptive_only", "maximum_leverage": float(leverage[which]),
            "maximum_leverage_donor": metadata[which]["donor"], "gene_slopes": gene_slopes.tolist(),
            "panel_slope": direct_panel}


def omission_slopes(gene_slopes: list[float]) -> list[float]:
    if len(gene_slopes) < 2:
        raise ValueError("Gene-omission diagnostic requires multiple fixed genes")
    values = np.asarray(gene_slopes, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Non-finite gene coefficients")
    return [float(np.delete(values, index).mean()) for index in range(len(values))]


def collect_values(plan: dict, frozen: dict) -> dict:
    genes = plan["genes"]
    full = frozen["populations"]["all_healthy"]
    cell_donors = {row["donor"] for row in full["GSE164241"]["donors"]}
    bulk_donors = {row["donor"] for row in full["GSE173078"]["donors"]}
    collected = {mode: {} for mode in COHORT}

    def put(mode: str, donor: str, gene: str, value: float) -> None:
        key = (donor, gene)
        if key in collected[mode] or not np.isfinite(value):
            raise ValueError("Duplicate/non-finite donor-gene value")
        collected[mode][key] = value

    for row in read_tsv(ROOT / plan["inputs"]["cell_raw_fixed_genes"]["path"]):
        if row["cell_group"] == "fibroblasts_all" and row["donor"] in cell_donors and row["gene_symbol"] in genes:
            count, denominator = int(row["raw_count"]), int(row["total_raw_umis"])
            if count < 0 or denominator <= 0 or count > denominator:
                raise ValueError("Invalid raw fibroblast count/UMI total")
            put("fibroblast_only", row["donor"], row["gene_symbol"], float(np.log1p(count / denominator * 1e6)))
    for row in read_tsv(ROOT / plan["inputs"]["partial_mixture_genes"]["path"]):
        if row["donor"] in cell_donors and row["gene"] in genes:
            for mode, column in [("observed_partial_capture", "observed_partial_CPM"),
                                 ("common_RNA_partial_capture", "common_RNA_weight_partial_CPM")]:
                value = float(row[column])
                if value < 0:
                    raise ValueError("Negative partial-mixture CPM")
                put(mode, row["donor"], row["gene"], float(np.log1p(value)))
    for row in read_tsv(ROOT / plan["inputs"]["bulk_gene_values"]["path"]):
        if row["donor_code"] in bulk_donors and row["gene"] in genes:
            put("bulk_gingiva", row["donor_code"], row["gene"], float(row["log1p_cpm"]))
    for mode, values in collected.items():
        donors = cell_donors if COHORT[mode] == "GSE164241" else bulk_donors
        if set(values) != {(donor, gene) for donor in donors for gene in genes}:
            raise ValueError("Not every frozen gene is available for every eligible healthy donor")
    return collected


def main() -> None:
    plan_path = HERE / "analysis_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    frozen_path = HERE / "frozen_populations.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    if frozen["plan_sha256_lf_text"] != text_sha(plan_path) or frozen["metadata_script_sha256_lf_text"] != text_sha(HERE / "freeze_populations.py"):
        raise ValueError("Population definitions differ from the frozen metadata rule")
    for name, specification in plan["inputs"].items():
        if text_sha(ROOT / specification["path"]) != specification["sha256_lf_text"]:
            raise ValueError(f"Input differs from plan: {name}")
    expected_cell = [{"donor": row["donor"], "cohort": "GSE164241", "age": float(row["age"]), "sex": row["sex"],
                      "processing": int(row["cellranger_versions"] == "3.0.1"), "processing_label": row["cellranger_versions"]}
                     for row in read_tsv(ROOT / plan["inputs"]["cell_metadata"]["path"])
                     if row["cell_group"] == "fibroblasts_all" and row["condition"] == "healthy"]
    expected_bulk = [{"donor": row["donor_code"], "cohort": "GSE173078", "age": float(row["age_years"]), "sex": row["sex"],
                      "processing": int(row["batch"] == "B"), "processing_label": row["batch"]}
                     for row in read_tsv(ROOT / plan["inputs"]["bulk_metadata"]["path"]) if row["phenotype"] == "Healthy"]
    expected_populations = json.loads(json.dumps(populations(expected_cell, expected_bulk)))
    if expected_populations != {key: frozen[key] for key in ["rules", "populations"]}:
        raise ValueError("Frozen populations differ from healthy-only source metadata rules")
    values = collect_values(plan, frozen)
    genes = plan["genes"]
    gene_rows, panel_rows, gene_omissions, donor_omissions, values_rows = [], [], [], [], []
    for mode, data in values.items():
        for (donor, gene), value in sorted(data.items()):
            values_rows.append({"cohort": COHORT[mode], "score_mode": mode, "donor": donor, "gene": gene,
                                "log1p_cpm": value, "interpretation": "Relative expression; lineage/partial capture/bulk are separate estimands."})
    for population, cohorts in frozen["populations"].items():
        for mode in plan["score_modes"]:
            cohort = COHORT[mode]
            metadata = cohorts[cohort]["donors"]
            matrix = np.asarray([[values[mode][(row["donor"], gene)] for gene in genes] for row in metadata])
            for model in plan["models"]:
                fit = fit_genes(metadata, matrix, model)
                base = {"population": population, "cohort": cohort, "score_mode": mode, "model": model}
                scalar = {key: value for key, value in fit.items() if key != "gene_slopes"}
                drop = omission_slopes(fit["gene_slopes"]) if fit["gene_slopes"] is not None else []
                omitted_donor_values = []
                for index, omitted in enumerate(metadata):
                    keep = np.arange(len(metadata)) != index
                    changed = fit_genes([row for j, row in enumerate(metadata) if j != index], matrix[keep], model)
                    donor_omissions.append({**base, "omitted_donor": omitted["donor"],
                                            **{key: value for key, value in changed.items() if key != "gene_slopes"}})
                    if changed["panel_slope"] is not None:
                        omitted_donor_values.append(changed["panel_slope"])
                panel_rows.append({**base, **scalar, "n_positive_gene_slopes": sum(value > 0 for value in (fit["gene_slopes"] or [])),
                                   "n_negative_gene_slopes": sum(value < 0 for value in (fit["gene_slopes"] or [])),
                                   "gene_omission_min": min(drop) if drop else "", "gene_omission_max": max(drop) if drop else "",
                                   "gene_omission_sign_changes": sum(np.sign(value) != np.sign(fit["panel_slope"]) for value in drop) if drop else "",
                                   "donor_omission_min": min(omitted_donor_values) if omitted_donor_values else "",
                                   "donor_omission_max": max(omitted_donor_values) if omitted_donor_values else "",
                                   "donor_omission_fits": len(omitted_donor_values),
                                   "donor_omission_sign_changes": sum(np.sign(value) != np.sign(fit["panel_slope"]) for value in omitted_donor_values)
                                   if fit["panel_slope"] is not None else "",
                                   "donor_omission_failed_fits": len(metadata)-len(omitted_donor_values)})
                total_abs = sum(abs(value) for value in (fit["gene_slopes"] or []))
                for index, gene in enumerate(genes):
                    coefficient = fit["gene_slopes"][index] if fit["gene_slopes"] is not None else None
                    gene_rows.append({**base, "gene": gene, "status": fit["status"], "n_donors": fit["n_donors"],
                                      "gene_slope_per_decade": coefficient,
                                      "equal_weight_panel_contribution": coefficient / len(genes) if coefficient is not None else None,
                                      "absolute_contribution_share": abs(coefficient)/total_abs if total_abs else None,
                                      "qualification": "Algebraic contribution, not causal attribution or variance explained."})
                    gene_omissions.append({**base, "omitted_gene": gene, "n_genes_remaining": len(genes)-1,
                                           "diagnostic_panel_slope": drop[index] if drop else None,
                                           "status": fit["status"], "qualification": "All gene omissions shown; no replacement panel selected."})
    concordance = []
    for population in frozen["populations"]:
        for model in plan["models"]:
            for gene in genes:
                row = {"population": population, "model": model, "gene": gene}
                for mode in plan["score_modes"]:
                    item = next(value for value in gene_rows if value["population"] == population and value["model"] == model
                                and value["score_mode"] == mode and value["gene"] == gene)
                    row[mode + "_slope"] = item["gene_slope_per_decade"]
                a, b = row["fibroblast_only_slope"], row["bulk_gingiva_slope"]
                row["fibroblast_vs_bulk_direction"] = "unavailable" if a is None or b is None else (
                    "opposite_signs" if a*b < 0 else "zero_or_same_sign")
                concordance.append(row)
    out = HERE / "derived"
    out.mkdir(parents=True, exist_ok=True)
    outputs = {"healthy_gene_values.tsv": values_rows, "gene_contributions.tsv": gene_rows,
               "fixed_panel_age_effects.tsv": panel_rows, "all_gene_omissions.tsv": gene_omissions,
               "donor_omissions.tsv": donor_omissions, "cross_cohort_gene_directions.tsv": concordance}
    for name, rows in outputs.items():
        write_tsv(out / name, rows)
    summary = {"status": "fixed_ECM_gene_and_demographic_support_challenge", "n_fixed_genes": len(genes),
               "panel_fits": len(panel_rows), "gene_effect_rows": len(gene_rows), "gene_omission_rows": len(gene_omissions),
               "donor_omission_rows": len(donor_omissions), "new_source_fetches": 0,
               "plan_sha256_lf_text": text_sha(plan_path), "frozen_populations_sha256_lf_text": text_sha(frozen_path),
               "script_sha256_lf_text": text_sha(Path(__file__)), "software": {"python": platform.python_version(), "numpy": np.__version__},
               "output_sha256_lf_text": {name: text_sha(out / name) for name in outputs}, "limits": plan["limits"]}
    (out / "analysis_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: summary[key] for key in ["panel_fits", "gene_effect_rows", "gene_omission_rows", "donor_omission_rows"]}, indent=2))


if __name__ == "__main__":
    main()
