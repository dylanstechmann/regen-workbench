"""Train an exploratory age-direction signature and challenge MPTR state shifts.

The GSE113957 age labels are held out during repeated signature selection.
The resulting direction-only panel is then transferred to matched GSE165177
log2-RPM contrasts. This is not an age clock, and the intervention lines are
too few for a claim of organismal rejuvenation.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path
import re
import sys

import numpy as np
from scipy.stats import rankdata, spearmanr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen

HERE = Path(__file__).resolve().parent
OUT = HERE / "derived" / "broad-age-state-challenge"
AGE_ACCESSION = "GSE113957"
TARGET_ACCESSION = "GSE165177"
AGE_CACHE = regen.DATA / "literature" / "aging-reference-GSE113957"
TARGET_CACHE = regen.DATA / "literature" / "aging-reprogramming-GSE165177"
AGE_RECEIPT = HERE / "aging_reference_intake_receipt.json"
TARGET_RECEIPT = HERE / "geo_intake_receipt.json"
SEED = 20261011
FOLDS = 5
REPEATS = 20
FEATURES_PER_DIRECTION = 100

# Prespecified monitoring axes. They are compact expression panels, not
# validated biological-age, identity, senescence, or safety scores.
AXES = {
    "collagen_core": ("COL1A1", "COL1A2", "COL4A1", "COL4A2"),
    "fibroblast_lineage_matrix": ("COL1A1", "COL1A2", "COL3A1", "DCN", "LUM", "PDGFRA", "THY1", "COL6A1"),
    "pluripotency_dedifferentiation": ("POU5F1", "NANOG", "SOX2", "LIN28A", "DPPA4", "TDGF1", "SALL4", "ZFP42"),
    "cell_cycle": ("MKI67", "TOP2A", "PCNA", "CCNB1", "MCM2", "MCM5", "CDK1", "CDC20"),
    "p53_DNA_damage_response": ("CDKN1A", "GADD45A", "GADD45B", "DDB2", "MDM2", "BBC3", "BAX", "CDKN2A"),
    "acute_stress_response": ("FOS", "JUN", "JUNB", "EGR1", "ATF3", "HMOX1", "NQO1", "HSPA1A", "DDIT3", "XBP1"),
    "inflammatory_response": ("IL6", "CXCL8", "CCL2", "NFKBIA", "PTGS2", "ISG15", "IFIT1", "OAS1", "STAT1"),
}
ECM_EXCLUDE = {"COL1A1", "COL1A2", "COL3A1", "COL4A1", "COL4A2", "COL6A1", "COL6A2",
               "COL6A3", "DCN", "LUM", "FN1", "VCAN", "FBN1", "ELN", "POSTN",
               "LOX", "LOXL1", "MMP2", "MMP3", "MMP14", "TIMP1", "TIMP2"}
COMPARISONS = (
    ("endpoint_after_withdrawal", "successful_endpoint", "negative_endpoint"),
    ("endpoint_after_withdrawal", "failed_endpoint", "negative_endpoint"),
    ("endpoint_after_withdrawal", "successful_endpoint", "failed_endpoint"),
    ("during_induction_intermediate", "successful_intermediate", "negative_intermediate"),
    ("during_induction_intermediate", "failing_intermediate", "negative_intermediate"),
    ("during_induction_intermediate", "successful_intermediate", "failing_intermediate"),
)


def write_tsv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty output: {path}")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return regen.sha256_file(path)


def characteristics(sample: dict) -> dict[str, str]:
    out = {}
    for value in sample["fields"].get("Sample_characteristics_ch1", []):
        if ":" in value:
            key, val = value.split(":", 1)
            out[key.strip().casefold()] = val.strip()
    return out


def parse_age(value: str) -> float:
    text = value.strip().casefold()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:yr|year|years)?(?:\s*(\d+)\s*mos?)?", text)
    if not match:
        raise ValueError(f"Could not parse GEO donor age: {value!r}")
    return float(match.group(1)) + float(match.group(2) or 0) / 12


def load_age_reference() -> tuple[list[dict], np.ndarray, list[str], dict]:
    receipt = json.loads(AGE_RECEIPT.read_text(encoding="utf-8"))
    metadata = json.loads((AGE_CACHE / f"{AGE_ACCESSION}_sample_metadata.json").read_text(encoding="utf-8"))
    matrix_record = receipt["files"]["fpkm_matrix"]
    matrix_path = AGE_CACHE / matrix_record["filename"]
    if sha256(matrix_path) != matrix_record["sha256"]:
        raise ValueError("GSE113957 input hash differs from the intake receipt")
    by_gsm = {}
    for sample in metadata["samples"]:
        chars = characteristics(sample)
        by_gsm[sample["accession"]] = {
            "GSM": sample["accession"],
            "cell_id": chars.get("cell id", ""),
            "disease": chars.get("disease", "").casefold(),
            "age_years": parse_age(chars["age"]),
            "sex": chars.get("sex", "").casefold(),
            "skin_source": sample["fields"].get("Sample_source_name_ch1", [""])[0],
        }
    header_to_gsm = {x["expression_header"]: x["GSM"]
                     for x in receipt["sample_mapping_check"]["expression_header_to_GSM"]}
    headers = matrix_record["header"][8:]
    if set(headers) != set(header_to_gsm) or len(headers) != len(header_to_gsm):
        raise ValueError("GSE113957 expression columns no longer map one-to-one to GEO samples")
    samples = [by_gsm[header_to_gsm[h]] for h in headers]
    age_indices = [i for i, s in enumerate(samples) if s["disease"] == "normal" and s["age_years"] >= 18]
    age_samples = [samples[i] for i in age_indices]
    if len(age_samples) != 111 or len({s["cell_id"] for s in age_samples}) != len(age_samples):
        raise ValueError(f"Expected 111 unique healthy adult cells from prior qualification; got {len(age_samples)}")
    sums: dict[str, np.ndarray] = {}
    annotation_counts = Counter()
    with gzip.open(matrix_path, "rt", encoding="utf-8", errors="strict", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        if header != matrix_record["header"]:
            raise ValueError("GSE113957 matrix header differs from receipt")
        for row in reader:
            if len(row) != len(header):
                raise ValueError("Malformed GSE113957 FPKM row")
            symbol = row[7].split("|", 1)[0].strip().upper()
            if not symbol or symbol in {"NA", "N/A", "-"}:
                continue
            values = np.asarray(row[8:], dtype=np.float64)
            if not np.isfinite(values).all() or (values < 0).any():
                raise ValueError(f"Invalid FPKM values for {symbol}")
            if symbol not in sums:
                sums[symbol] = values
            else:
                sums[symbol] += values
            annotation_counts[symbol] += 1
    selected = sorted(sums)
    X = np.vstack([np.log2(sums[g][age_indices] + 0.1) for g in selected]).T
    if not np.isfinite(X).all():
        raise ValueError("Non-finite log2 FPKM value in age reference")
    metadata_out = {"source_sha256": matrix_record["sha256"], "input_filename": matrix_record["filename"],
                    "adult_n": len(age_samples), "unique_cell_ids": len({s["cell_id"] for s in age_samples}),
                    "age_min": min(s["age_years"] for s in age_samples),
                    "age_max": max(s["age_years"] for s in age_samples),
                    "gene_count_after_exact_annotation_aggregation": len(selected),
                    "aggregation": "sum transcript-row FPKM sharing the first exact annotation symbol; log2(sum+0.1)"}
    return age_samples, X, selected, metadata_out


def selected_signature(X: np.ndarray, ages: np.ndarray, genes: list[str], candidates: np.ndarray | None = None) -> tuple[list[int], list[int], np.ndarray]:
    if candidates is None:
        candidates = np.arange(X.shape[1])
    variance = X[:, candidates].std(axis=0, ddof=1)
    expressed = np.mean(X[:, candidates] > math.log2(0.1), axis=0) >= 0.5
    valid = candidates[(variance > 1e-8) & expressed]
    if len(valid) < 2 * FEATURES_PER_DIRECTION:
        raise ValueError(f"Too few variable expressed genes for cross-validation: {len(valid)}")
    age_rank = rankdata(ages, method="average")
    ranks = rankdata(X[:, valid], axis=0, method="average")
    centered_age = age_rank - age_rank.mean()
    centered_genes = ranks - ranks.mean(axis=0)
    denom = np.sqrt(np.sum(centered_age**2) * np.sum(centered_genes**2, axis=0))
    rho = np.divide(centered_age @ centered_genes, denom, out=np.zeros_like(denom), where=denom > 0)
    positive = valid[np.argsort(rho)[-FEATURES_PER_DIRECTION:][::-1]].tolist()
    negative = valid[np.argsort(rho)[:FEATURES_PER_DIRECTION]].tolist()
    full_rho = np.full(X.shape[1], np.nan)
    full_rho[valid] = rho
    return positive, negative, full_rho


def score_direction(X_train: np.ndarray, X_test: np.ndarray, pos: list[int], neg: list[int]) -> np.ndarray:
    selected = np.asarray(pos + neg, dtype=int)
    mu = X_train[:, selected].mean(axis=0)
    sd = X_train[:, selected].std(axis=0, ddof=1)
    sd[sd < 1e-8] = 1.0
    z = (X_test[:, selected] - mu) / sd
    npos = len(pos)
    return z[:, :npos].mean(axis=1) - z[:, npos:].mean(axis=1)


def cross_validate_age_direction(X: np.ndarray, samples: list[dict], genes: list[str]) -> tuple[list[dict], dict[int, int], dict[int, int]]:
    ages = np.asarray([s["age_years"] for s in samples], dtype=np.float64)
    rng = np.random.default_rng(SEED)
    # Assign folds within five age-rank strata so each held-out fold spans the adult range.
    age_order = np.argsort(ages, kind="stable")
    strata = np.empty(len(ages), dtype=int)
    strata[age_order] = np.floor(np.arange(len(ages)) * FOLDS / len(ages)).astype(int)
    records = []
    selected_count = Counter()
    selected_sign = Counter()
    for repeat in range(REPEATS):
        fold_indices = [[] for _ in range(FOLDS)]
        for stratum in range(FOLDS):
            ids = np.where(strata == stratum)[0]
            rng.shuffle(ids)
            for j, idx in enumerate(ids):
                fold_indices[j % FOLDS].append(int(idx))
        age_score = np.full(len(ages), np.nan)
        random_score = np.full(len(ages), np.nan)
        for fold, test_ids_list in enumerate(fold_indices):
            test_ids = np.asarray(sorted(test_ids_list), dtype=int)
            train_ids = np.asarray([i for i in range(len(ages)) if i not in set(test_ids.tolist())], dtype=int)
            pos, neg, _ = selected_signature(X[train_ids], ages[train_ids], genes)
            age_score[test_ids] = score_direction(X[train_ids], X[test_ids], pos, neg)
            for i in pos:
                selected_count[i] += 1
                selected_sign[(i, 1)] += 1
            for i in neg:
                selected_count[i] += 1
                selected_sign[(i, -1)] += 1
            # Random panels retain the same size and fold-specific train scaling.
            variance = X[train_ids].std(axis=0, ddof=1)
            expressed = np.mean(X[train_ids] > math.log2(0.1), axis=0) >= 0.5
            universe = np.where((variance > 1e-8) & expressed)[0]
            random_ids = rng.choice(universe, size=2*FEATURES_PER_DIRECTION, replace=False)
            random_score[test_ids] = score_direction(X[train_ids], X[test_ids],
                                                      random_ids[:FEATURES_PER_DIRECTION].tolist(),
                                                      random_ids[FEATURES_PER_DIRECTION:].tolist())
        age_rho = float(spearmanr(ages, age_score).statistic)
        random_rho = float(spearmanr(ages, random_score).statistic)
        middle = (ages >= 35) & (ages <= 60)
        records.append({"repeat": repeat + 1, "out_of_fold_spearman_age_score": age_rho,
                        "out_of_fold_random_panel_spearman": random_rho,
                        "oof_35_to_60_spearman_age_score": float(spearmanr(ages[middle], age_score[middle]).statistic),
                        "oof_score_missing": int(np.isnan(age_score).sum())})
    return records, selected_count, selected_sign


def sample_state(sample: dict) -> dict:
    fields = sample["fields"]
    title = fields["Sample_title"][0]
    donor_match = re.match(r"^(O[123])_", title)
    day_match = re.search(r"_(\d+)days_", title)
    experiment_match = re.search(r"_exp(\d+)$", title)
    if "transient_reprogramming_intermediate" in title:
        group = "successful_intermediate"
    elif "failing_to_transiently_reprogram_intermediate" in title:
        group = "failing_intermediate"
    elif "negative_control_intermediate" in title:
        group = "negative_intermediate"
    elif "failed_to_transiently_reprogram_" in title:
        group = "failed_endpoint"
    elif "transiently_reprogrammed_" in title:
        group = "successful_endpoint"
    elif "negative_control_" in title:
        group = "negative_endpoint"
    else:
        group = "other"
    return {"GSM": sample["accession"], "title": title,
            "donor": donor_match.group(1) if donor_match else "",
            "day": int(day_match.group(1)) if day_match else 0,
            "experiment": f"exp{experiment_match.group(1)}" if experiment_match else "reference",
            "group": group}


def load_target_expression(receipt: dict) -> tuple[list[dict], dict[str, dict[str, float]], dict]:
    metadata = json.loads((TARGET_CACHE / f"{TARGET_ACCESSION}_series_metadata.json").read_text(encoding="utf-8"))
    state_by_gsm = {s["accession"]: sample_state(s) for s in metadata["sample_metadata"]}
    expr: dict[str, dict[str, float]] = defaultdict(dict)
    row_counts = Counter()
    crosswalk = receipt["sample_mapping_check"]["expression_header_to_GSM"]
    target_hashes = {}
    for file_record in receipt["files"].values():
        filename = file_record["filename"]
        if not filename.endswith(".txt.gz"):
            continue
        path = TARGET_CACHE / filename
        if sha256(path) != file_record["sha256"]:
            raise ValueError(f"GSE165177 source hash mismatch for {filename}")
        target_hashes[filename] = file_record["sha256"]
        header_to_gsm = {x["expression_header"]: x["GSM"] for x in crosswalk[filename]}
        headers = file_record["header"][12:]
        if set(headers) != set(header_to_gsm):
            raise ValueError(f"GSE165177 sample columns no longer match receipt for {filename}")
        sums: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        with gzip.open(path, "rt", encoding="utf-8", errors="strict", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if reader.fieldnames != file_record["header"]:
                raise ValueError(f"GSE165177 matrix header differs from receipt: {filename}")
            for row in reader:
                if row["Type"].casefold() != "gene":
                    continue
                symbol = row["Feature"].strip().upper()
                if not symbol or symbol in {"NA", "N/A", "-"}:
                    continue
                for header in headers:
                    value = float(row[header])
                    if not math.isfinite(value):
                        raise ValueError(f"Invalid GSE165177 log2-RPM value: {symbol}/{header}")
                    sums[symbol][header].append(value)
        for symbol, values_by_header in sums.items():
            for header, vals in values_by_header.items():
                gsm = header_to_gsm[header]
                if gsm in expr[symbol]:
                    raise ValueError(f"Duplicate target matrix column for {symbol}/{gsm}")
                expr[symbol][gsm] = float(np.mean(vals))
                row_counts[symbol] += len(vals)
    manifest = [state_by_gsm[item] for item in sorted(state_by_gsm)]
    return manifest, expr, {"source_hashes": target_hashes, "gene_symbol_rows": len(expr),
                           "metadata_samples": len(manifest), "aggregation": "mean processed log2-RPM among exact Type=gene rows sharing exact symbol"}


def build_pairs(manifest: list[dict]) -> list[dict]:
    blocks: dict[tuple, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for row in manifest:
        if row["group"] in {"successful_endpoint", "failed_endpoint", "negative_endpoint",
                            "successful_intermediate", "failing_intermediate", "negative_intermediate"}:
            blocks[(row["experiment"], row["donor"], row["day"])][row["group"]].append(row)
    pairs = []
    for phase, case, control in COMPARISONS:
        for (experiment, donor, day), groups in sorted(blocks.items()):
            if donor == "" or len(groups.get(case, [])) != 1 or len(groups.get(control, [])) != 1:
                continue
            treatment, reference = groups[case][0], groups[control][0]
            pairs.append({"pair_id": f"{phase}:{experiment}:{donor}:{day}:{case}-vs-{control}",
                          "phase": phase, "experiment": experiment, "donor": donor, "day": day,
                          "comparison": f"{case}_vs_{control}",
                          "treatment_GSM": treatment["GSM"], "control_GSM": reference["GSM"],
                          "treatment_title": treatment["title"], "control_title": reference["title"]})
    if not pairs:
        raise ValueError("No matched expression pairs found")
    return pairs


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    age_samples, X, genes, age_meta = load_age_reference()
    ages = np.asarray([s["age_years"] for s in age_samples], dtype=np.float64)
    cv, stable_count, stable_sign = cross_validate_age_direction(X, age_samples, genes)
    pos, neg, full_rho = selected_signature(X, ages, genes)
    ecm_candidates = np.asarray([i for i, gene in enumerate(genes) if gene not in ECM_EXCLUDE], dtype=int)
    pos_no_ecm, neg_no_ecm, rho_no_ecm = selected_signature(X, ages, genes, ecm_candidates)
    age_receipt = json.loads(AGE_RECEIPT.read_text(encoding="utf-8"))
    target_receipt = json.loads(TARGET_RECEIPT.read_text(encoding="utf-8"))
    manifest, expression, target_meta = load_target_expression(target_receipt)
    target_genes = set(expression)

    signature_rows = []
    panels = {"age_direction_full": (pos, neg, full_rho),
              "age_direction_excluding_matrix_markers": (pos_no_ecm, neg_no_ecm, rho_no_ecm)}
    for panel_name, (panel_pos, panel_neg, panel_rho) in panels.items():
        for direction, ids in (("age_associated_higher", panel_pos), ("age_associated_lower", panel_neg)):
            for idx in ids:
                gene = genes[idx]
                signature_rows.append({"panel": panel_name, "gene": gene, "age_direction": direction,
                                       "reference_spearman_rho": f"{panel_rho[idx]:.8f}",
                                       "selected_in_oof_training_folds": stable_count[idx],
                                       "oof_fold_selection_fraction": f"{stable_count[idx]/(REPEATS*FOLDS):.6f}",
                                       "sign_selected_in_oof_folds": stable_sign[(idx, 1 if direction == "age_associated_higher" else -1)],
                                       "present_in_GSE165177": gene in target_genes,
                                       "ECM_exclusion_set_member": gene in ECM_EXCLUDE})
    write_tsv(OUT / "age_direction_signature.tsv", signature_rows)
    write_tsv(OUT / "age_direction_cross_validation.tsv", cv)

    pair_rows = []
    axis_gene_rows = []
    pairs = build_pairs(manifest)
    for pair in pairs:
        tg, cg = pair["treatment_GSM"], pair["control_GSM"]
        feature_deltas = {}
        for gene in target_genes:
            if tg in expression[gene] and cg in expression[gene]:
                feature_deltas[gene] = expression[gene][tg] - expression[gene][cg]
        row = dict(pair)
        for panel_name, (panel_pos, panel_neg, panel_rho) in panels.items():
            ids = panel_pos + panel_neg
            selected_genes = [genes[i] for i in ids if genes[i] in feature_deltas and np.isfinite(panel_rho[i])]
            reversal_values = [-float(np.sign(panel_rho[genes.index(g)])) * feature_deltas[g]
                               for g in selected_genes]
            row[f"{panel_name}_n_genes"] = len(reversal_values)
            row[f"{panel_name}_mean_younger_direction_delta_log2_RPM"] = (
                f"{float(np.mean(reversal_values)):.8f}" if reversal_values else "")
            row[f"{panel_name}_fraction_genes_moving_opposite_age_direction"] = (
                f"{float(np.mean(np.asarray(reversal_values) > 0)):.8f}" if reversal_values else "")
        for axis_name, axis_genes in AXES.items():
            values = [feature_deltas[g] for g in axis_genes if g in feature_deltas]
            row[f"{axis_name}_n_genes"] = len(values)
            row[f"{axis_name}_mean_delta_log2_RPM"] = f"{float(np.mean(values)):.8f}" if values else ""
            for gene in axis_genes:
                if gene in feature_deltas:
                    axis_gene_rows.append({**{k: pair[k] for k in ("pair_id", "phase", "experiment", "donor", "day", "comparison", "treatment_GSM", "control_GSM")},
                                           "axis": axis_name, "gene": gene,
                                           "control_log2_RPM": f"{expression[gene][cg]:.8f}",
                                           "treatment_log2_RPM": f"{expression[gene][tg]:.8f}",
                                           "delta_log2_RPM": f"{feature_deltas[gene]:.8f}"})
        pair_rows.append(row)
    write_tsv(OUT / "matched_pair_age_and_state_scores.tsv", pair_rows)
    axis_table = OUT / "alternative_axis_gene_deltas.tsv"
    write_tsv(axis_table, axis_gene_rows)
    # The full gene-level audit is highly repetitive. Keep it losslessly
    # compressed so the public derivative remains small and reproducible.
    axis_archive = OUT / "alternative_axis_gene_deltas.tsv.gz"
    with axis_table.open("rb") as source, axis_archive.open("wb") as raw_archive:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_archive, compresslevel=9, mtime=0) as archive:
            shutil.copyfileobj(source, archive)
    axis_table.unlink()

    donor_blocks: dict[tuple, list[dict]] = defaultdict(list)
    for row in pair_rows:
        donor_blocks[(row["phase"], row["day"], row["comparison"], row["donor"])].append(row)
    donor_rows = []
    score_fields = [key for key in pair_rows[0] if key.endswith("_mean_younger_direction_delta_log2_RPM") or key.endswith("_fraction_genes_moving_opposite_age_direction") or key.endswith("_mean_delta_log2_RPM")]
    for (phase, day, comparison, donor), rows in sorted(donor_blocks.items()):
        result = {"phase": phase, "day": day, "comparison": comparison, "donor": donor,
                  "n_experiment_blocks": len(rows), "experiment_blocks": ";".join(r["experiment"] for r in rows)}
        for field in score_fields:
            vals = [float(r[field]) for r in rows if r.get(field, "") != ""]
            result[field] = f"{float(np.mean(vals)):.8f}" if vals else ""
        donor_rows.append(result)
    write_tsv(OUT / "donor_line_age_and_state_scores.tsv", donor_rows)

    cohort_groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in donor_rows:
        cohort_groups[(row["phase"], row["day"], row["comparison"])].append(row)
    cohort_rows = []
    for key, rows in sorted(cohort_groups.items()):
        item = {"phase": key[0], "day": key[1], "comparison": key[2], "n_donor_lines": len(rows),
                "donor_lines": ";".join(r["donor"] for r in rows)}
        for field in score_fields:
            vals = [float(r[field]) for r in rows if r.get(field, "") != ""]
            item[f"median_{field}"] = f"{float(np.median(vals)):.8f}" if vals else ""
            item[f"min_{field}"] = f"{min(vals):.8f}" if vals else ""
            item[f"max_{field}"] = f"{max(vals):.8f}" if vals else ""
            item[f"donor_values_{field}"] = ";".join(f"{r['donor']}:{float(r[field]):.4f}" for r in rows if r.get(field, "") != "")
        cohort_rows.append(item)
    write_tsv(OUT / "donor_level_age_state_summary.tsv", cohort_rows)

    cv_scores = np.asarray([float(row["out_of_fold_spearman_age_score"]) for row in cv])
    random_scores = np.asarray([float(row["out_of_fold_random_panel_spearman"]) for row in cv])
    adult_mid = [i for i, sample in enumerate(age_samples) if 35 <= sample["age_years"] <= 60]
    score_summary = {
        "schema_version": 1,
        "reference": {"accession": AGE_ACCESSION, **age_meta},
        "target": {"accession": TARGET_ACCESSION, **target_meta},
        "age_signature_training": {
            "method": "Repeated 5-fold cross-validation stratified across chronological-age rank; within each training fold select top 100 positive and top 100 negative Spearman genes and score held-out samples from training-standardized expression.",
            "repeats": REPEATS,
            "folds": FOLDS,
            "features_each_direction": FEATURES_PER_DIRECTION,
            "oof_age_score_spearman_median": float(np.median(cv_scores)),
            "oof_age_score_spearman_10th_percentile": float(np.quantile(cv_scores, .10)),
            "oof_age_score_spearman_90th_percentile": float(np.quantile(cv_scores, .90)),
            "oof_35_to_60_spearman_median": float(np.median([float(r["oof_35_to_60_spearman_age_score"]) for r in cv])),
            "oof_35_to_60_spearman_10th_percentile": float(np.quantile([float(r["oof_35_to_60_spearman_age_score"]) for r in cv], .10)),
            "oof_35_to_60_spearman_90th_percentile": float(np.quantile([float(r["oof_35_to_60_spearman_age_score"]) for r in cv], .90)),
            "random_panel_oof_spearman_median": float(np.median(random_scores)),
            "random_panel_oof_spearman_10th_percentile": float(np.quantile(random_scores, .10)),
            "random_panel_oof_spearman_90th_percentile": float(np.quantile(random_scores, .90)),
            "adult_35_to_60_n": len(adult_mid),
            "limitation": "This is a direction-score benchmark within one processed skin-fibroblast cohort; it is not an externally validated clock, and the age training data come from a different study/platform than target intervention data."
        },
        "target_contrast_scoring": {
            "matching_unit": "donor-coded line × day × experiment block; experiment blocks averaged within donor before cohort summary",
            "age_direction_score": "negative(reference Spearman age direction) × paired treatment-minus-control log2-RPM change, averaged equally across mapped signature genes; positive means change opposite the adult reference age association.",
            "ecm_exclusion": sorted(ECM_EXCLUDE),
            "alternative_axes": AXES,
            "alternative_axes_limit": "Prespecified compact marker panels; transcript changes do not independently prove identity, senescence, stress, safety, or rejuvenation.",
            "no_years_younger_estimate": True,
            "small_target_n_warning": "Day-13 successful post-withdrawal endpoint has only two donor-coded lines; cell lines and repeated experiments do not replace donor replication."
        },
        "generated_utc": regen.now(),
        "inputs_sha256": {**{AGE_RECEIPT.name: sha256(AGE_RECEIPT), TARGET_RECEIPT.name: sha256(TARGET_RECEIPT)},
                           **{age_meta["input_filename"]: age_meta["source_sha256"]}, **target_meta["source_hashes"]},
    }
    (OUT / "broad_age_state_summary.json").write_text(json.dumps(score_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    try:
        import matplotlib.pyplot as plt
        chosen = [r for r in donor_rows if r["comparison"] in {
            "successful_endpoint_vs_negative_endpoint", "failed_endpoint_vs_negative_endpoint"}]
        days = sorted({r["day"] for r in chosen})
        fig, ax = plt.subplots(figsize=(9.2, 5.2), constrained_layout=True)
        colors = {"successful_endpoint_vs_negative_endpoint": "#0072B2",
                  "failed_endpoint_vs_negative_endpoint": "#D55E00"}
        labels = {"successful_endpoint_vs_negative_endpoint": "successful endpoint",
                  "failed_endpoint_vs_negative_endpoint": "failed endpoint"}
        labelled = set()
        for x, day in enumerate(days):
            for comparison, dx in (("successful_endpoint_vs_negative_endpoint", -0.08),
                                   ("failed_endpoint_vs_negative_endpoint", 0.08)):
                values = [float(r["age_direction_full_mean_younger_direction_delta_log2_RPM"])
                          for r in chosen if r["day"] == day and r["comparison"] == comparison
                          and r["age_direction_full_mean_younger_direction_delta_log2_RPM"]]
                for j, value in enumerate(values):
                    label = labels[comparison] if comparison not in labelled else None
                    ax.scatter(x+dx+(j-len(values)/2)*.012, value, color=colors[comparison], s=55,
                               label=label)
                    labelled.add(comparison)
        ax.axhline(0, color="#444444", lw=1, ls="--")
        ax.set_xticks(range(len(days)), [str(d) for d in days])
        ax.set_xlabel("Induction days at endpoint collection")
        ax.set_ylabel("Mean age-opposing Δ log₂ RPM (donor line)")
        ax.set_title("Transferred age-direction score, paired within donor line")
        ax.legend(frameon=False)
        ax.text(.01, .01, "Positive means movement opposite an adult skin-fibroblast age association; not years younger.",
                transform=ax.transAxes, fontsize=8)
        fig.savefig(OUT / "broad_age_direction_transfer.png", dpi=180)
        svg_path = OUT / "broad_age_direction_transfer.svg"
        fig.savefig(svg_path)
        svg_path.write_text("\n".join(line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()) + "\n",
                            encoding="utf-8")
        plt.close(fig)
        score_summary["figure_created"] = True
    except ImportError:
        score_summary["figure_created"] = False
    (OUT / "broad_age_state_summary.json").write_text(json.dumps(score_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    paths = [p for p in OUT.iterdir() if p.is_file()]
    provenance = regen.record("broad-age-direction-state-challenge", {
        "reference_accession": AGE_ACCESSION, "target_accession": TARGET_ACCESSION,
        "reference_cv_repeats": REPEATS, "folds": FOLDS,
        "feature_selection_within_train_fold": True,
        "target_unit": "matched donor line × phase × day",
        "not_an_age_clock": True
    }, paths)
    print(json.dumps({"age_reference_genes": age_meta["gene_count_after_exact_annotation_aggregation"],
                      "target_genes": target_meta["gene_symbol_rows"], "age_samples": len(age_samples),
                      "matched_pairs": len(pair_rows), "donor_line_rows": len(donor_rows),
                      "cv_median_rho": float(np.median(cv_scores)),
                      "random_median_rho": float(np.median(random_scores)),
                      "day13_success": next((row for row in cohort_rows if row["day"] == 13 and row["comparison"] == "successful_endpoint_vs_negative_endpoint"), None),
                      "output": str(OUT), "provenance": provenance.name}, ensure_ascii=False))


if __name__ == "__main__":
    main()
