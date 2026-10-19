"""Between-compartment RNA-mixture challenge using tracked raw pseudobulk.

The retained data are a partial captured-cell mixture, never full-tissue bulk.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import platform
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from freeze_composition_reference import read_tsv, write_tsv, sha_text, freeze_reference


def mix_gene_cpm(counts: np.ndarray, total_umis: np.ndarray, common: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """One donor, compartment x gene; RNA mixing happens before log transform."""
    if counts.ndim != 2 or total_umis.shape != (counts.shape[0],) or common.shape != total_umis.shape:
        raise ValueError("Compartment/gene matrix dimensions do not agree")
    if not np.isfinite(counts).all() or not np.isfinite(total_umis).all() or not np.isfinite(common).all():
        raise ValueError("Non-finite mixture input")
    if np.any(counts < 0) or np.any(total_umis <= 0) or np.any(common <= 0) or not np.isclose(common.sum(), 1, atol=1e-12, rtol=0):
        raise ValueError("Invalid count, UMI total or common RNA weight")
    if np.any(np.abs(counts - np.rint(counts)) > 1e-9) or np.any(counts > total_umis[:, None]) or np.any(counts.sum(axis=1) > total_umis):
        raise ValueError("Input is not nonnegative raw counts within each compartment library")
    cpm = counts / total_umis[:, None] * 1e6
    observed = (total_umis / total_umis.sum()) @ cpm
    direct = counts.sum(axis=0) / total_umis.sum() * 1e6
    error = float(np.max(np.abs(observed - direct)))
    if error > 1e-8:
        raise ValueError("RNA-weight reconstruction does not match summed-count pseudobulk")
    return observed, common @ cpm, error


def model_subset(rows: list[dict], model: str) -> list[dict]:
    if model not in {"all_healthy_age", "all_healthy_age_sex_version", "female_healthy_age_version",
                     "strict20_healthy_age", "strict20_healthy_age_sex_version"}:
        raise ValueError("Unknown frozen model")
    return [row for row in rows if row["condition"] == "healthy"
            and (not model.startswith("female") or row["sex"] == "female")
            and (not model.startswith("strict20") or row["strict20_eligible"])]


def fit_age(rows: list[dict], model: str) -> dict:
    if any(row["condition"] != "healthy" for row in rows) or len({row["donor"] for row in rows}) != len(rows):
        raise ValueError("Healthy age fit requires one row per inferred healthy donor")
    if any(row["sex"] not in {"male", "female"} or row["version"] not in {"2.0.0", "3.0.1"} for row in rows):
        raise ValueError("Unqualified sex/version category")
    result = {"n_donors": len(rows), "n_female": sum(row["sex"] == "female" for row in rows),
              "n_male": sum(row["sex"] == "male" for row in rows), "status": "unfitted",
              "slope_per_decade": "", "rank": "", "residual_df": "", "max_leverage": ""}
    if not rows:
        return {**result, "status": "empty_subset"}
    age = np.asarray([float(row["age"]) for row in rows])
    score = np.asarray([float(row["score"]) for row in rows])
    if not np.isfinite(age).all() or not np.isfinite(score).all():
        raise ValueError("Non-finite donor age/score")
    columns = [np.ones(len(rows)), (age - age.mean()) / 10]
    if "sex" in model:
        columns.append(np.asarray([row["sex"] == "male" for row in rows], dtype=float))
    if "version" in model:
        columns.append(np.asarray([row["version"] == "3.0.1" for row in rows], dtype=float))
    design = np.column_stack(columns)
    rank, df = int(np.linalg.matrix_rank(design)), len(rows) - design.shape[1]
    result.update(rank=rank, residual_df=df)
    if rank != design.shape[1]:
        return {**result, "status": "rank_deficient"}
    if df < 2:
        return {**result, "status": "insufficient_residual_df"}
    beta = np.linalg.lstsq(design, score, rcond=None)[0]
    leverage = np.sum(design * np.linalg.pinv(design).T, axis=1)
    return {**result, "status": "descriptive_only", "slope_per_decade": float(beta[1]), "max_leverage": float(max(leverage))}


def main() -> None:
    plan_path = HERE / "analysis_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    source = ROOT / plan["input_directory"]
    for name, expected in plan["input_sha256_lf_text"].items():
        if sha_text(source / name) != expected:
            raise ValueError(f"Tracked input differs from plan: {name}")
    frozen_path = HERE / "frozen_RNA_weights.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    if frozen["plan_sha256_lf_text"] != sha_text(plan_path) or frozen["metadata_script_sha256_lf_text"] != sha_text(HERE / "freeze_composition_reference.py"):
        raise ValueError("Frozen composition does not belong to the current pre-outcome metadata rule")
    compartments = plan["compartments"]
    metadata, reconstructed_frozen, donor_audit = freeze_reference(read_tsv(source / "gingival_cellset_donor_counts.tsv"), compartments)
    if frozen["weights"] != reconstructed_frozen["weights"] or frozen["reference_donors"] != reconstructed_frozen["reference_donors"]:
        raise ValueError("Frozen weights were altered or derived from a different donor set")
    weights = np.asarray([frozen["weights"][group] for group in compartments])
    metadata_by_key = {(row["donor"], row["cell_group"]): row for row in metadata}
    counts = {}
    for row in read_tsv(source / "gingival_cellset_pseudobulk_fixed_genes.tsv"):
        if row["cell_group"] not in compartments:
            continue
        key = (row["donor"], row["cell_group"], row["gene_symbol"])
        if key in counts:
            raise ValueError("Duplicate donor/compartment/gene raw value")
        meta = metadata_by_key[(row["donor"], row["cell_group"])]
        for field in ["n_cells", "total_raw_umis", "condition", "age", "sex", "samples", "cellranger_versions"]:
            if row[field] != meta[field]:
                raise ValueError("Raw gene row and donor-compartment metadata differ")
        counts[key] = int(row["raw_count"])
    coverage = read_tsv(source / "gingival_fixed_panel_coverage.tsv")
    panels = {row["panel"]: row["included_gene_symbols"].split(";") for row in coverage}
    genes = sorted({gene for panel in panels.values() for gene in panel})
    score_rows, gene_rows = [], []
    reconstruction_errors = []
    for donor in sorted({row["donor"] for row in metadata}):
        current = [metadata_by_key[(donor, group)] for group in compartments]
        matrix = np.asarray([[counts[(donor, group, gene)] for gene in genes] for group in compartments], dtype=float)
        totals = np.asarray([int(row["total_raw_umis"]) for row in current], dtype=float)
        observed, common, error = mix_gene_cpm(matrix, totals, weights)
        reconstruction_errors.append(error)
        base = current[0]
        cpm = matrix / totals[:, None] * 1e6
        for index, gene in enumerate(genes):
            gene_rows.append({"donor": donor, "condition": base["condition"], "gene": gene,
                              "included_gene_count": int(matrix[:, index].sum()), "included_total_UMIs": int(totals.sum()),
                              "observed_partial_CPM": float(observed[index]), "common_RNA_weight_partial_CPM": float(common[index])})
        for panel, symbols in panels.items():
            indices = [genes.index(gene) for gene in symbols]
            reference_group = plan["lineage_reference_by_panel"][panel]
            values = [observed, common, cpm[compartments.index(reference_group)]]
            for score_type, value in zip(plan["score_types"], values):
                score_rows.append({"donor": donor, "condition": base["condition"], "age": base["age"], "sex": base["sex"],
                                   "version": base["cellranger_versions"], "strict20_eligible": base["strict20_eligible"],
                                   "panel": panel, "n_genes": len(symbols), "score_type": score_type,
                                   "reference_cell_group": reference_group if score_type == "lineage_reference_same_donors" else "nine_disjoint_compartments_partial_capture",
                                   "score": float(np.log1p(value[indices]).mean())})
    effects, omissions = [], []
    for panel in panels:
        for score_type in plan["score_types"]:
            rows = [row for row in score_rows if row["panel"] == panel and row["score_type"] == score_type]
            for model in plan["models"]:
                selected = model_subset(rows, model)
                fitted = fit_age(selected, model)
                values = []
                if model in plan["donor_omissions"]:
                    for omitted in selected:
                        result = fit_age([row for row in selected if row["donor"] != omitted["donor"]], model)
                        omissions.append({"panel": panel, "score_type": score_type, "model": model,
                                          "omitted_donor": omitted["donor"], **result})
                        if result["status"] == "descriptive_only":
                            values.append(result["slope_per_decade"])
                effects.append({"panel": panel, "score_type": score_type, "model": model, **fitted,
                                "omission_min": min(values) if values else "", "omission_max": max(values) if values else "",
                                "omission_fits": len(values), "omission_sign_changes": sum(np.sign(value) != np.sign(fitted["slope_per_decade"]) for value in values)
                                if values and fitted["status"] == "descriptive_only" else ""})
    old_cell = {(row["cell_group"], row["panel"]): row for row in read_tsv(source / "gingival_healthy_age_slopes.tsv")}
    old_bulk = {}
    for name, table in plan["previous_bulk_tables"].items():
        if sha_text(ROOT / table["path"]) != table["sha256_lf_text"]:
            raise ValueError("Historical bulk table differs from frozen context")
        old_bulk[name] = read_tsv(ROOT / table["path"])
    direction = []
    for panel in panels:
        original = old_cell[(plan["lineage_reference_by_panel"][panel], panel)]
        lineage = next(row for row in effects if row["panel"] == panel and row["score_type"] == "lineage_reference_same_donors" and row["model"] == "all_healthy_age")
        if abs(float(original["slope_per_10y"]) - lineage["slope_per_decade"]) > 1e-10:
            raise ValueError("Lineage-only reconstruction did not reproduce old same-donor score slope")
        row = {"panel": panel}
        for kind in plan["score_types"]:
            row[kind + "_slope_per_decade"] = next(effect["slope_per_decade"] for effect in effects
                                                   if effect["panel"] == panel and effect["score_type"] == kind and effect["model"] == "all_healthy_age")
        row["GSE173078_female_batch_bulk_slope"] = next(item["slope_per_decade"] for item in old_bulk["GSE173078"] if item["panel"] == panel and item["model"] == "female_age_batch")
        row["GSE83382_bulk_old_minus_young"] = next(item["old_minus_young"] for item in old_bulk["GSE83382"] if item["panel"] == panel)
        row["interpretation"] = "Signs only across studies/scales; this source's nine-compartment reconstruction is a partial captured-cell mixture, not observed intact tissue."
        direction.append(row)
    out = HERE / "derived"
    outputs = {"partial_mixture_gene_values.tsv": gene_rows, "partial_mixture_donor_scores.tsv": score_rows,
               "healthy_age_effects.tsv": effects, "healthy_age_donor_omissions.tsv": omissions,
               "direction_challenge.tsv": direction}
    for filename, rows in outputs.items():
        write_tsv(out / filename, rows)
    summary = {"status": "partial_captured_cell_RNA_mixture_challenge", "whole_tissue_reconstruction": False,
               "new_source_fetches": 0, "donor_counts": dict(Counter(row["condition"] for row in donor_audit)),
               "n_disjoint_compartments": len(compartments), "n_panels": len(panels),
               "unique_panel_genes_shared_by_all_donor_compartment_keys": len(genes),
               "panel_gene_counts": {panel: len(symbols) for panel, symbols in panels.items()},
               "age_model_rows": len(effects),
               "donor_omission_rows": len(omissions), "max_gene_reconstruction_absolute_CPM_error": max(reconstruction_errors),
               "plan_sha256_lf_text": sha_text(plan_path), "frozen_RNA_weights_sha256_lf_text": sha_text(frozen_path),
               "script_sha256_lf_text": sha_text(Path(__file__)), "software": {"python": platform.python_version(), "numpy": np.__version__},
               "output_sha256_lf_text": {name: sha_text(out / name) for name in outputs},
               "metadata_output_sha256_lf_text": {name: sha_text(out / name) for name in ["capture_coverage_audit.json", "donor_compartment_metadata.tsv"]},
               "limits": plan["limits"]}
    (out / "analysis_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: summary[key] for key in ["status", "age_model_rows", "donor_omission_rows", "max_gene_reconstruction_absolute_CPM_error"]}, indent=2))


if __name__ == "__main__":
    main()
