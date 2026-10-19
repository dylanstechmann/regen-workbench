"""Fixed-panel transport to source-labelled healthy GSE173078 bulk gingiva.

No age clock, learned gene panel, pooled-cohort regression or treatment model.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from qualify_sources import read_soft, sample_rows


def sha_text(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("No output rows")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, list(dict.fromkeys(key for row in rows for key in row)), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_counts(path: Path, participant_ids: set[str], selected_genes: set[str]) -> tuple[list[str], np.ndarray, dict, int]:
    totals, selected, seen = [], {}, set()
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        if len(header) != len(set(header)) or set(header) != participant_ids:
            raise ValueError("Count columns do not uniquely match qualified participants")
        totals = [0] * len(header)
        for row in reader:
            if len(row) != len(header) + 1 or not row[0] or row[0] in seen:
                raise ValueError("Malformed or duplicate gene-count row")
            gene = row[0]
            seen.add(gene)
            try:
                counts = [int(value) for value in row[1:]]
            except ValueError as exc:
                raise ValueError("Counts are not integer values") from exc
            if min(counts) < 0:
                raise ValueError("Negative gene count")
            totals = [total + value for total, value in zip(totals, counts)]
            if gene in selected_genes:
                selected[gene] = np.asarray(counts, dtype=float)
    if not seen or min(totals) <= 0:
        raise ValueError("Empty count matrix or library")
    return header, np.asarray(totals, dtype=float), selected, len(seen)


def fit_age(rows: list[dict], model: str, min_df: int = 2) -> dict:
    if len({row["donor_code"] for row in rows}) != len(rows):
        raise ValueError("Each age fit needs one independent participant-code row")
    if any(row["phenotype"] != "Healthy" for row in rows):
        raise ValueError("Disease/gingivitis rows cannot enter a healthy age model")
    if model not in {"all_healthy_age", "all_healthy_age_sex_batch", "female_age", "female_age_batch"}:
        raise ValueError("Unknown frozen model")
    if model.startswith("female") and any(row["sex"] != "female" for row in rows):
        raise ValueError("Female model received another sex")
    if any(row["sex"] not in {"female", "male"} or row["batch"] not in {"A", "B"} for row in rows):
        raise ValueError("Unknown sex or batch cannot be coded as the reference category")
    result = {"n_donors": len(rows), "n_female": sum(row["sex"] == "female" for row in rows),
              "n_male": sum(row["sex"] == "male" for row in rows), "status": "unfitted",
              "slope_per_decade": "", "rank": "", "residual_df": "", "max_leverage": ""}
    if not rows:
        return {**result, "status": "empty_subset"}
    ages = np.asarray([float(row["age_years"]) for row in rows])
    scores = np.asarray([float(row["score_mean_log1p_cpm"]) for row in rows])
    if not np.isfinite(ages).all() or not np.isfinite(scores).all():
        raise ValueError("Non-finite age or score")
    columns = [np.ones(len(rows)), (ages - ages.mean()) / 10]
    if "sex" in model:
        columns.append(np.asarray([row["sex"] == "male" for row in rows], dtype=float))
    if "batch" in model:
        columns.append(np.asarray([row["batch"] == "B" for row in rows], dtype=float))
    design = np.column_stack(columns)
    rank, df = int(np.linalg.matrix_rank(design)), len(rows) - design.shape[1]
    result.update(rank=rank, residual_df=df)
    if rank != design.shape[1]:
        return {**result, "status": "rank_deficient"}
    if df < min_df:
        return {**result, "status": "insufficient_residual_df"}
    beta = np.linalg.lstsq(design, scores, rcond=None)[0]
    leverages = np.sum(design * np.linalg.pinv(design).T, axis=1)
    return {**result, "status": "descriptive_only", "slope_per_decade": float(beta[1]),
            "max_leverage": float(max(leverages))}


def common_support(metadata: list[dict]) -> list[dict]:
    result = []
    for phenotype in ["Periodontitis", "Gingivitis"]:
        for sex in ["all", "female", "male"]:
            healthy = [row for row in metadata if row["phenotype"] == "Healthy" and (sex == "all" or row["sex"] == sex)]
            challenge = [row for row in metadata if row["phenotype"] == phenotype and (sex == "all" or row["sex"] == sex)]
            ha, ca = [float(row["age_years"]) for row in healthy], [float(row["age_years"]) for row in challenge]
            low, high = max(min(ha), min(ca)), min(max(ha), max(ca))
            overlap = low <= high
            result.append({"challenge": phenotype, "sex": sex, "n_healthy": len(ha), "n_challenge": len(ca),
                           "healthy_ages": ";".join(map(str, sorted(ha))), "challenge_ages": ";".join(map(str, sorted(ca))),
                           "age_overlap_min": low if overlap else "", "age_overlap_max": high if overlap else "",
                           "n_healthy_in_range_intersection": sum(low <= age <= high for age in ha) if overlap else 0,
                           "n_challenge_in_range_intersection": sum(low <= age <= high for age in ca) if overlap else 0,
                           "interpretation": "Range intersection is not matched sampling or a guarantee of common covariate support."})
    return result


def alias_sensitivity(cache: Path, metadata: list[dict], panels: dict, models: list[str]) -> tuple[list[dict], list[dict], list[dict]]:
    annotation = json.loads((HERE / "annotation_sensitivity_plan.json").read_text(encoding="utf-8"))
    docs = json.loads((cache / "HGNC_CXCL8.json").read_text(encoding="utf-8"))["response"]["docs"]
    if len(docs) != 1 or docs[0]["hgnc_id"] != annotation["official_record"] or docs[0]["symbol"] != "CXCL8" or "IL8" not in docs[0]["prev_symbol"]:
        raise ValueError("Official previous-symbol mapping no longer matches sensitivity plan")
    header, totals, counts, _ = read_counts(cache / "GSE173078_rnaseq_raw_counts.txt.gz",
                                          {row["donor_code"] for row in metadata}, set(panels["inflammation"]) | {"IL8"})
    if "CXCL8" in counts or "IL8" not in counts:
        raise ValueError("Alias sensitivity requires absent current symbol and one unique previous-symbol row")
    genes = [gene if gene != "CXCL8" else "IL8" for gene in panels["inflammation"]]
    if any(gene not in counts for gene in genes):
        raise ValueError("Alias-corrected frozen inflammation panel is incomplete")
    values = np.log1p(np.asarray([counts[gene] for gene in genes]) / totals * 1e6).mean(axis=0)
    metadata_by_donor = {row["donor_code"]: row for row in metadata}
    scores = [{**metadata_by_donor[donor], "analysis_status": "posthoc_annotation_sensitivity",
               "panel": "inflammation_9_genes_CXCL8_via_IL8", "n_genes": 9,
               "score_mean_log1p_cpm": float(values[index]), "IL8_supplied_count": int(counts["IL8"][index])}
              for index, donor in enumerate(header)]
    effects, omissions = [], []
    for model in models:
        current = [row for row in scores if row["phenotype"] == "Healthy" and (not model.startswith("female") or row["sex"] == "female")]
        fitted = fit_age(current, model)
        omitted_values = []
        if model == "female_age_batch":
            for omitted in current:
                result = fit_age([row for row in current if row["donor_code"] != omitted["donor_code"]], model)
                omissions.append({"model": model, "omitted_donor": omitted["donor_code"], **result})
                if result["status"] == "descriptive_only":
                    omitted_values.append(result["slope_per_decade"])
        effects.append({"model": model, "analysis_status": "posthoc_annotation_sensitivity", "n_genes": 9, **fitted,
                        "omission_min": min(omitted_values) if omitted_values else "",
                        "omission_max": max(omitted_values) if omitted_values else ""})
    return scores, effects, omissions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / "data/literature/checklist-aging-followup-2026-10-19")
    parser.add_argument("--out", type=Path, default=HERE / "derived")
    args = parser.parse_args()
    plan_path = HERE / "analysis_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    receipt_path = HERE / "source_receipts.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    for source in receipt["sources"]:
        if hashlib.sha256((args.cache / source["filename"]).read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("Cached primary source differs from fetch receipt")
    for name in ["frozen_panel_coverage", "previous_bulk_table", "previous_cell_table"]:
        digest_name = {"frozen_panel_coverage": "frozen_panel_coverage_sha256_lf_text", "previous_bulk_table": "previous_bulk_sha256_lf_text",
                       "previous_cell_table": "previous_cell_sha256_lf_text"}[name]
        if sha_text(ROOT / plan[name]) != plan[digest_name]:
            raise ValueError("Historical comparison table differs from frozen plan")
    series, samples = read_soft(args.cache / "GSE173078_family.soft.gz")
    metadata = sample_rows(series, samples)
    if len(metadata) != 36 or len({row["donor_code"] for row in metadata}) != 36:
        raise ValueError("Expected one RNA library for each of 36 unique AC participant codes")
    if Counter(row["phenotype"] for row in metadata) != {"Healthy": 12, "Gingivitis": 12, "Periodontitis": 12}:
        raise ValueError("Unexpected clinical-group counts")
    coverage = read_tsv(ROOT / plan["frozen_panel_coverage"])
    panels = {row["panel"]: row["included_gene_symbols"].split(";") for row in coverage}
    genes = set(gene for panel in panels.values() for gene in panel)
    count_path = args.cache / "GSE173078_rnaseq_raw_counts.txt.gz"
    if hashlib.sha256(count_path.read_bytes()).hexdigest() != plan["counts_sha256"]:
        raise ValueError("Count data differ from the pre-outcome analysis plan")
    header, totals, selected, n_features = read_counts(count_path, {row["donor_code"] for row in metadata}, genes)
    by_donor = {row["donor_code"]: row for row in metadata}
    manifest = [{**by_donor[donor], "total_supplied_gene_counts": int(totals[index]),
                 "age_model_eligible": by_donor[donor]["phenotype"] == "Healthy",
                 "primary_female_age_model_eligible": by_donor[donor]["phenotype"] == "Healthy" and by_donor[donor]["sex"] == "female"}
                for index, donor in enumerate(header)]
    score_rows, gene_rows, panel_rows = [], [], []
    for gene in sorted(selected):
        for index, donor in enumerate(header):
            gene_rows.append({"donor_code": donor, "GSM": by_donor[donor]["GSM"], "gene": gene,
                              "supplied_integer_count": int(selected[gene][index]),
                              "log1p_cpm": float(np.log1p(selected[gene][index] / totals[index] * 1e6))})
    for panel, specified in panels.items():
        included = [gene for gene in specified if gene in selected]
        panel_rows.append({"panel": panel, "n_specified": len(specified), "n_present": len(included),
                           "included_genes": ";".join(included), "missing_genes": ";".join(gene for gene in specified if gene not in selected),
                           "outcome_based_filter": False})
        if not included:
            raise ValueError("Panel has no mapped genes; do not silently skip it")
        values = np.log1p(np.asarray([selected[gene] for gene in included]) / totals * 1e6).mean(axis=0)
        for index, donor in enumerate(header):
            score_rows.append({**by_donor[donor], "panel": panel, "n_genes": len(included),
                               "score_mean_log1p_cpm": float(values[index])})
    effect_rows, omissions = [], []
    for panel in panels:
        healthy = [row for row in score_rows if row["panel"] == panel and row["phenotype"] == "Healthy"]
        for model in plan["models"]:
            current = [row for row in healthy if row["sex"] == "female"] if model.startswith("female") else healthy
            result = fit_age(current, model)
            values = []
            if model in plan["donor_omissions"]:
                for omitted in current:
                    fitted = fit_age([row for row in current if row["donor_code"] != omitted["donor_code"]], model)
                    omissions.append({"panel": panel, "model": model, "omitted_donor": omitted["donor_code"], **fitted})
                    if fitted["status"] == "descriptive_only":
                        values.append(fitted["slope_per_decade"])
            effect_rows.append({"panel": panel, "model": model, **result,
                                "omission_min": min(values) if values else "", "omission_max": max(values) if values else "",
                                "omission_fits": len(values), "omission_sign_changes": sum(np.sign(value) != np.sign(result["slope_per_decade"]) for value in values)
                                if result["status"] == "descriptive_only" and values else ""})
    bulk = {row["panel"]: row for row in read_tsv(ROOT / plan["previous_bulk_table"])}
    cell = {(row["cell_group"], row["panel"]): row for row in read_tsv(ROOT / plan["previous_cell_table"])}
    direction_rows = []
    for panel in panels:
        fitted = next(row for row in effect_rows if row["panel"] == panel and row["model"] == plan["primary_model"])
        previous_cell = cell[(plan["cell_comparator_by_panel"][panel], panel)]
        new = fitted["slope_per_decade"]
        direction_rows.append({"panel": panel, "new_bulk_primary_slope_per_decade": new,
                               "new_omission_min": fitted["omission_min"], "new_omission_max": fitted["omission_max"],
                               "old_bulk_GSE83382_old_minus_young": bulk[panel]["old_minus_young"],
                               "old_cell_GSE164241_group": previous_cell["cell_group"],
                               "old_cell_age_slope_per_decade": previous_cell["slope_per_10y"],
                               "sign_agrees_previous_bulk": bool(np.sign(new) == np.sign(float(bulk[panel]["old_minus_young"]))),
                               "sign_agrees_previous_cell": bool(np.sign(new) == np.sign(float(previous_cell["slope_per_10y"]))),
                               "interpretation": "Signs only; cohorts, assay scales, gene coverage, age ranges and bulk versus selected-cell estimands differ. No magnitudes pooled."})
    args.out.mkdir(parents=True, exist_ok=True)
    outputs = {"GSE173078_sample_manifest.tsv": manifest, "cohort_common_support.tsv": common_support(metadata),
               "fixed_panel_coverage.tsv": panel_rows, "fixed_panel_gene_values.tsv": gene_rows,
               "fixed_panel_donor_scores.tsv": score_rows, "healthy_age_effects.tsv": effect_rows,
               "healthy_age_donor_omissions.tsv": omissions, "direction_transport.tsv": direction_rows}
    alias_scores, alias_effects, alias_omissions = alias_sensitivity(args.cache, metadata, panels, plan["models"])
    outputs.update({"annotation_sensitivity_donor_scores.tsv": alias_scores,
                    "annotation_sensitivity_age_effects.tsv": alias_effects,
                    "annotation_sensitivity_donor_omissions.tsv": alias_omissions})
    for name, rows in outputs.items():
        write_tsv(args.out / name, rows)
    summary = {"accession": "GSE173078", "analysis_type": "fixed_panel_bulk_age_direction_challenge",
               "clinical_health": "provider-labelled Healthy, not independently adjudicated",
               "source_h5ad_used": False, "count_features": n_features, "count_libraries": len(header),
               "participants_by_phenotype": dict(Counter(row["phenotype"] for row in metadata)),
               "healthy_sex_counts": dict(Counter(row["sex"] for row in metadata if row["phenotype"] == "Healthy")),
               "primary_healthy_female_donors": 10, "primary_age_range": [28, 75], "age_effect_rows": len(effect_rows),
               "donor_omission_rows": len(omissions), "primary_model": plan["primary_model"],
               "source_receipts_sha256_lf_text": sha_text(receipt_path), "plan_sha256_lf_text": sha_text(plan_path),
               "script_sha256_lf_text": sha_text(Path(__file__)), "software": {"python": platform.python_version(), "numpy": np.__version__},
               "annotation_sensitivity_plan_sha256_lf_text": sha_text(HERE / "annotation_sensitivity_plan.json"),
               "annotation_sensitivity_status": "Post-hoc official-symbol mapping; primary exact-symbol analysis preserved separately",
               "output_sha256_lf_text": {name: sha_text(args.out / name) for name in outputs}, "limits": plan["limits"]}
    (args.out / "analysis_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"features": n_features, "libraries": len(header), "primary_model": plan["primary_model"],
                      "age_fits": len(effect_rows), "omissions": len(omissions)}, indent=2))


if __name__ == "__main__":
    main()
