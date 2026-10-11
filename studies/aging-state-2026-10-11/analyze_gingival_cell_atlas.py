"""Donor-aware, fixed-panel analysis of curated GSE164241 gingival cells."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
import sys

import h5py
import numpy as np
from scipy.sparse import csr_matrix

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data" / "literature" / "oral-atlas-GSE164241"
H5AD = DATA / "human-periodontal-meta-atlas-v1.h5ad"
H5AD_RECEIPT = DATA / "human-periodontal-meta-atlas-v1.receipt.json"
CROSSWALK = HERE / "oral_atlas_GSE164241_sample_crosswalk.tsv"
DERIVED = HERE / "derived" / "gingival-cell-atlas-GSE164241"

sys.path.insert(0, str(HERE))
from analyze_gingival_age_reference import PANELS  # frozen before this cell-level challenge

SEED = 164241
BOOTSTRAPS = 2_000
ROW_CHUNK = 4_096
MIN_CELLS_PER_DONOR = 20
MIN_AGE_DONORS = 8
MIN_DISEASE_CASE_DONORS = 4

# CellxGene's annotated-cell-set labels are retained as published. Combined
# groups are used for primary estimates; the listed subgroups are sensitivities.
CELL_GROUP_SETS = {
    "fibroblasts_all": {"Fibroblast 1", "Fibroblast 2"},
    "fibroblast_1": {"Fibroblast 1"},
    "fibroblast_2": {"Fibroblast 2"},
    "epithelium_all": {
        "Lining mucosal keratinocyte", "Masticatory mucosal keratinocyte",
        "Suprabasal keratinocytes", "Sulcus/junction epithelial keratinocytes",
    },
    "epithelium_lining": {"Lining mucosal keratinocyte"},
    "epithelium_masticatory": {"Masticatory mucosal keratinocyte"},
    "epithelium_suprabasal": {"Suprabasal keratinocytes"},
    "epithelium_sulcus_junction": {"Sulcus/junction epithelial keratinocytes"},
    "endothelium_all": {
        "Post-capillary venule VECs", "Capillary VECs", "Arterial VECs",
        "Lymphatic endothelial cell 1", "Lymphatic endothelial cell 2",
    },
    "perivascular_support": {"Pericytes", "Vascular smooth muscle cells"},
    "dendritic_cells_all": {
        "Conventional dendritic cells", "Plasmacytoid dendritic cells", "Langerhans cells",
    },
    "lymphoid_all": {
        "Th cells", "Tc cells", "B.Cells", "Mucosal-associated invariant T cells",
        "Gamma delta-T cells", "NK cells", "NKT cells", "Treg cells", "Th17 cells",
        "Plasma cells",
    },
    "neutrophils": {"Neutrophils"},
    "macrophages_monocytes": {"Macrophages/Monocytes"},
    "mast_cells": {"Mast cells"},
    "t_helper_cells": {"Th cells"},
    "t_cytotoxic_cells": {"Tc cells"},
    "b_cells": {"B.Cells"},
    "plasma_cells": {"Plasma cells"},
}
INTENTIONALLY_EXCLUDED_CELLSETS = {
    "Cells in the cell cycle (mixed cells)": "Mixed-lineage label; excluded from lineage-specific contrasts.",
    "Melanocytes": "Outside the prespecified oral repair panels in this focused analysis.",
    "Schwann cells": "Sparse group (26 cells) and outside the prespecified oral repair panels.",
    "Merkel Cells": "Sparse group (19 cells) and outside the prespecified oral repair panels.",
}
FIBROBLAST_GROUPS = {"fibroblasts_all", "fibroblast_1", "fibroblast_2"}
EPITHELIAL_GROUPS = {name for name in CELL_GROUP_SETS if name.startswith("epithelium_")}
ALL_GROUPS = set(CELL_GROUP_SETS)
PANEL_GROUPS = {
    "matrix_degradation": FIBROBLAST_GROUPS,
    "matrix_inhibitors": FIBROBLAST_GROUPS,
    "structural_ecm": FIBROBLAST_GROUPS,
    "inflammation": ALL_GROUPS,
    "epithelial_barrier_identity": EPITHELIAL_GROUPS,
    "fibroblast_stromal_identity": FIBROBLAST_GROUPS,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_h5_column(group: h5py.Group, name: str) -> np.ndarray:
    node = group[name]
    if isinstance(node, h5py.Group):
        categories = node["categories"].asstr()[()]
        codes = node["codes"][()]
        return np.asarray([categories[code] if code >= 0 else "" for code in codes], dtype=object)
    if h5py.check_string_dtype(node.dtype):
        return np.asarray(node.asstr()[()], dtype=object)
    return node[()]


def sample_root(value: str) -> str:
    match = re.match(r"^([A-Za-z]+\d+)", value.strip())
    return match.group(1).upper() if match else value.strip().upper()


def read_crosswalk() -> tuple[dict[str, dict], dict[str, list[dict]], list[dict]]:
    with CROSSWALK.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    eligible = [row for row in rows if row["category"] in {"healthy_gingiva_candidate", "periodontitis_gingiva"}]
    by_exact: dict[str, dict] = {}
    by_root: dict[str, list[dict]] = defaultdict(list)
    for row in eligible:
        exact = row["sample_title"].strip().upper()
        if exact in by_exact:
            raise ValueError(f"Duplicate exact sample title in GEO crosswalk: {exact}")
        by_exact[exact] = row
        root = sample_root(row["sample_title"])
        by_root[root].append(row)
    return by_exact, by_root, eligible


def match_sample(sample_id: str, by_exact: dict[str, dict], by_root: dict[str, list[dict]]) -> dict:
    exact = sample_id.strip().upper()
    if exact in by_exact:
        return by_exact[exact]
    candidates = by_root.get(sample_root(sample_id), [])
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError(f"Cannot unambiguously match curated sample ID to GEO crosswalk: {sample_id}")


def fit_linear(y: np.ndarray, design: np.ndarray) -> np.ndarray | None:
    if len(y) < design.shape[1] or np.linalg.matrix_rank(design) < design.shape[1]:
        return None
    return np.linalg.lstsq(design, y, rcond=None)[0]


def slope_per_decade(records: list[dict], rng: np.random.Generator) -> dict:
    ages = np.asarray([float(row["age"]) for row in records])
    scores = np.asarray([float(row["score"]) for row in records])
    centered = ages - ages.mean()
    beta = fit_linear(scores, np.column_stack([np.ones(len(scores)), centered]))
    if beta is None:
        return {"slope_per_10y": "", "spearman_rho": "", "bootstrap_low": "",
                "bootstrap_high": "", "leave_one_out_low": "", "leave_one_out_high": ""}
    slopes = []
    for _ in range(BOOTSTRAPS):
        ids = rng.integers(0, len(scores), len(scores))
        x = ages[ids]
        if np.ptp(x) == 0:
            continue
        candidate = fit_linear(scores[ids], np.column_stack([np.ones(len(ids)), x - x.mean()]))
        if candidate is not None:
            slopes.append(float(candidate[1] * 10))
    loo = []
    for omitted in range(len(scores)):
        keep = np.arange(len(scores)) != omitted
        candidate = fit_linear(scores[keep], np.column_stack([np.ones(keep.sum()), ages[keep] - ages[keep].mean()]))
        if candidate is not None:
            loo.append(float(candidate[1] * 10))
    from scipy.stats import spearmanr
    rho = float(spearmanr(ages, scores).statistic)
    return {
        "slope_per_10y": float(beta[1] * 10), "spearman_rho": rho,
        "bootstrap_low": float(np.percentile(slopes, 2.5)) if slopes else "",
        "bootstrap_high": float(np.percentile(slopes, 97.5)) if slopes else "",
        "leave_one_out_low": min(loo) if loo else "",
        "leave_one_out_high": max(loo) if loo else "",
    }


def disease_effect(records: list[dict], rng: np.random.Generator) -> dict:
    controls = [row for row in records if row["condition"] == "healthy"]
    cases = [row for row in records if row["condition"] == "periodontitis"]

    def estimate(sample: list[dict]) -> float | None:
        age = np.asarray([float(row["age"]) for row in sample])
        disease = np.asarray([row["condition"] == "periodontitis" for row in sample], dtype=float)
        score = np.asarray([float(row["score"]) for row in sample])
        design = np.column_stack([np.ones(len(sample)), disease, age - age.mean()])
        beta = fit_linear(score, design)
        return float(beta[1]) if beta is not None else None

    point = estimate(records)
    if point is None:
        return {"age_adjusted_difference": "", "bootstrap_low": "", "bootstrap_high": ""}
    boot = []
    for _ in range(BOOTSTRAPS):
        cidx = rng.integers(0, len(controls), len(controls))
        didx = rng.integers(0, len(cases), len(cases))
        sample = [controls[index] for index in cidx] + [cases[index] for index in didx]
        value = estimate(sample)
        if value is not None:
            boot.append(value)
    return {
        "age_adjusted_difference": point,
        "bootstrap_low": float(np.percentile(boot, 2.5)) if boot else "",
        "bootstrap_high": float(np.percentile(boot, 97.5)) if boot else "",
    }


def write_tsv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write an empty output table: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(dict.fromkeys(key for row in rows for key in row))
        if "interpretation_limit" in fieldnames:
            fieldnames.remove("interpretation_limit")
            fieldnames.append("interpretation_limit")
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not H5AD.is_file() or not H5AD_RECEIPT.is_file():
        raise FileNotFoundError("Run fetch_periodontal_meta_atlas.py first")
    h5ad_receipt = json.loads(H5AD_RECEIPT.read_text(encoding="utf-8"))
    observed_sha = sha256_file(H5AD)
    if observed_sha != h5ad_receipt["sha256"]:
        raise ValueError("Curated H5AD hash differs from its download receipt")
    exact_crosswalk, root_crosswalk, eligible_crosswalk = read_crosswalk()

    with h5py.File(H5AD, "r") as source:
        obs = source["obs"]
        columns = {key: read_h5_column(obs, key) for key in
                   ["GSE", "Sample ID", "tissue", "disease", "cell_type", "Annotated Cell Sets",
                    "development_stage", "sex", "donor_id"]}
        n_obs = len(columns["GSE"])
        x_shape = tuple(int(value) for value in re.findall(r"\d+", str(source["X"].attrs["shape"])))
        if len(x_shape) != 2 or n_obs != x_shape[0]:
            raise ValueError("H5AD observation metadata and X row count disagree")

        sample_rows: dict[str, dict] = {}
        sample_counts: Counter[str] = Counter()
        selected_row_indices: list[int] = []
        row_metadata: list[dict | None] = [None] * n_obs
        observed_cellset_counts: Counter[str] = Counter()
        for row_index in range(n_obs):
            if str(columns["GSE"][row_index]) != "164241":
                continue
            if str(columns["tissue"][row_index]) != "gingiva":
                continue
            sample_id = str(columns["Sample ID"][row_index])
            metadata = match_sample(sample_id, exact_crosswalk, root_crosswalk)
            disease = str(columns["disease"][row_index])
            expected_disease = "normal" if metadata["category"] == "healthy_gingiva_candidate" else "periodontitis"
            if disease != expected_disease:
                raise ValueError(f"CZI disease label {disease!r} disagrees with GEO/Table S1 for {sample_id}")
            stage = str(columns["development_stage"][row_index])
            stage_age = re.search(r"(\d+)-year-old stage", stage)
            if not stage_age or int(stage_age.group(1)) != int(metadata["age"]):
                raise ValueError(f"CZI age stage disagrees with GEO/Table S1 for {sample_id}: {stage!r}")
            czi_sex = str(columns["sex"][row_index])
            expected_sex = {"F": "female", "M": "male"}.get(metadata["sex"])
            if expected_sex and czi_sex != expected_sex:
                raise ValueError(f"CZI sex label disagrees with GEO/Table S1 for {sample_id}")
            donor = metadata["inferred_donor_group"]
            condition = "healthy" if expected_disease == "normal" else "periodontitis"
            sample_rows.setdefault(sample_id, {
                "sample_id": sample_id, "GSM": metadata["GSM"], "condition": condition,
                "inferred_donor_group": donor, "age": int(metadata["age"]), "sex": czi_sex,
                "cellranger_version": metadata["cellranger_version"], "sample_title": metadata["sample_title"],
            })
            sample_counts[sample_id] += 1
            row_metadata[row_index] = {"donor": donor, "condition": condition, "age": int(metadata["age"]),
                                       "sex": czi_sex, "cellset": str(columns["Annotated Cell Sets"][row_index])}
            observed_cellset_counts[str(columns["Annotated Cell Sets"][row_index])] += 1
            selected_row_indices.append(row_index)

        mapped_cellsets = {cellset for cellsets in CELL_GROUP_SETS.values() for cellset in cellsets}
        unexplained_cellsets = set(observed_cellset_counts) - mapped_cellsets - set(INTENTIONALLY_EXCLUDED_CELLSETS)
        stale_exclusions = set(INTENTIONALLY_EXCLUDED_CELLSETS) - set(observed_cellset_counts)
        if unexplained_cellsets or stale_exclusions:
            raise ValueError(f"Cell-set coverage audit failed: unexplained={sorted(unexplained_cellsets)}, stale_exclusions={sorted(stale_exclusions)}")

        observed_gsms = {info["GSM"] for info in sample_rows.values()}
        expected_gsms = {row["GSM"] for row in eligible_crosswalk}
        if expected_gsms != observed_gsms:
            raise ValueError(f"CZI/GEO gingiva sample crosswalk mismatch: missing={sorted(expected_gsms-observed_gsms)}, extra={sorted(observed_gsms-expected_gsms)}")
        if len(eligible_crosswalk) != 21 or len(sample_rows) != 21:
            raise ValueError("Expected 21 original GEO gingival libraries (13 healthy and 8 periodontitis)")

        donor_metadata: dict[str, dict] = {}
        for sample in sample_rows.values():
            donor = sample["inferred_donor_group"]
            value = donor_metadata.setdefault(donor, {"condition": sample["condition"], "age": sample["age"],
                                                       "sex": sample["sex"], "samples": set(), "versions": set()})
            if (value["condition"], value["age"], value["sex"]) != (sample["condition"], sample["age"], sample["sex"]):
                raise ValueError(f"GEO/Table S1 metadata differ within inferred donor group {donor}")
            value["samples"].add(sample["sample_id"])
            value["versions"].add(sample["cellranger_version"])
        expected_donors = {"healthy": 13, "periodontitis": 5}
        actual_donors = Counter(value["condition"] for value in donor_metadata.values())
        if dict(actual_donors) != expected_donors:
            raise ValueError(f"Unexpected donor counts after aggregating repeated biopsies: {dict(actual_donors)}")

        # The CZI file stores integer raw counts in AnnData .raw and log-normalized
        # values in X. Use .raw only; retain gene symbols and feature IDs in receipt.
        matrix = source["raw"]["X"]
        matrix_shape = matrix.attrs["shape"]
        if isinstance(matrix_shape, bytes):
            matrix_shape = matrix_shape.decode("ascii")
        n_rows, n_features = map(int, re.findall(r"\d+", str(matrix_shape)))
        indptr = matrix["indptr"][()]
        if n_rows != n_obs or len(indptr) != n_obs + 1:
            raise ValueError("Raw-count CSR dimensions do not match observation metadata")
        feature_names = read_h5_column(source["raw"]["var"], "feature_name")
        target_symbols = sorted({gene.upper() for genes in PANELS.values() for gene in genes})
        target_set = set(target_symbols)
        symbol_to_col = {symbol: i for i, symbol in enumerate(target_symbols)}
        chosen_features, chosen_symbol_columns = [], []
        feature_symbol_counts: Counter[str] = Counter()
        for feature_index, feature_name in enumerate(feature_names):
            symbol = str(feature_name).upper()
            if symbol in target_set:
                chosen_features.append(feature_index)
                chosen_symbol_columns.append(symbol_to_col[symbol])
                feature_symbol_counts[symbol] += 1
        present_symbols = {symbol for symbol, count in feature_symbol_counts.items() if count > 0}
        missing_symbols = sorted(target_set - present_symbols)
        if len(present_symbols) < 30:
            raise ValueError(f"Unexpectedly low frozen-panel gene coverage: {len(present_symbols)} of {len(target_set)}")
        collapse = csr_matrix((np.ones(len(chosen_features), dtype=np.int8),
                               (np.arange(len(chosen_features)), np.asarray(chosen_symbol_columns))),
                              shape=(len(chosen_features), len(target_symbols)))

        cellset_to_groups: dict[str, list[str]] = defaultdict(list)
        for group_name, cellsets in CELL_GROUP_SETS.items():
            for cellset in cellsets:
                cellset_to_groups[cellset].append(group_name)
        group_key_to_id: dict[tuple[str, str], int] = {}
        group_info: list[dict] = []
        row_memberships: list[tuple[int, ...]] = [()] * n_obs
        for row_index in selected_row_indices:
            metadata = row_metadata[row_index]
            group_ids = []
            for group_name in cellset_to_groups.get(metadata["cellset"], []):
                key = (metadata["donor"], group_name)
                if key not in group_key_to_id:
                    group_key_to_id[key] = len(group_info)
                    donor = donor_metadata[metadata["donor"]]
                    group_info.append({"donor": metadata["donor"], "condition": donor["condition"],
                                       "age": donor["age"], "sex": donor["sex"], "cell_group": group_name,
                                       "samples": ";".join(sorted(donor["samples"])),
                                       "cellranger_versions": ";".join(sorted(donor["versions"]))})
                group_ids.append(group_key_to_id[key])
            row_memberships[row_index] = tuple(group_ids)

        pseudobulk_counts = np.zeros((len(group_info), len(target_symbols)), dtype=np.int64)
        pseudobulk_cells = np.zeros(len(group_info), dtype=np.int64)
        pseudobulk_umis = np.zeros(len(group_info), dtype=np.int64)
        raw_data = matrix["data"]
        raw_indices = matrix["indices"]
        if len(raw_data) != len(raw_indices):
            raise ValueError("Raw-count CSR data and index arrays differ in length")

        for start in range(0, n_obs, ROW_CHUNK):
            end = min(start + ROW_CHUNK, n_obs)
            first_nnz, last_nnz = int(indptr[start]), int(indptr[end])
            data = raw_data[first_nnz:last_nnz]
            if np.any(np.abs(data - np.rint(data)) > 1e-5):
                raise ValueError("AnnData .raw matrix contains non-integer values; refusing count pseudobulk")
            counts = np.rint(data).astype(np.int64)
            indices = raw_indices[first_nnz:last_nnz].astype(np.int32, copy=False)
            local_indptr = (indptr[start:end + 1] - first_nnz).astype(np.int64, copy=False)
            block = csr_matrix((counts, indices, local_indptr), shape=(end - start, n_features))
            library_sizes = np.asarray(block.sum(axis=1)).ravel().astype(np.int64)
            panel_counts = block[:, chosen_features] @ collapse
            rows_by_group: dict[int, list[int]] = defaultdict(list)
            for local_row, group_ids in enumerate(row_memberships[start:end]):
                for group_id in group_ids:
                    rows_by_group[group_id].append(local_row)
            for group_id, local_rows in rows_by_group.items():
                selected = np.asarray(local_rows, dtype=np.int32)
                pseudobulk_counts[group_id] += np.asarray(panel_counts[selected].sum(axis=0)).ravel().astype(np.int64)
                pseudobulk_cells[group_id] += len(local_rows)
                pseudobulk_umis[group_id] += int(library_sizes[selected].sum())

    # Keep sparse-table rows even when the cell count falls below analysis gates.
    cell_count_rows = []
    pseudobulk_rows = []
    panel_score_by_group: dict[tuple[int, str], float] = {}
    panel_coverage_rows = []
    for panel, genes in PANELS.items():
        present = [gene for gene in genes if gene in present_symbols]
        panel_coverage_rows.append({
            "panel": panel, "specified_genes": len(genes), "present_gene_symbols": len(present),
            "missing_gene_symbols": ";".join(gene for gene in genes if gene not in present_symbols),
            "symbols_with_multiple_feature_rows": ";".join(gene for gene in genes if feature_symbol_counts.get(gene, 0) > 1),
            "included_gene_symbols": ";".join(present),
            "cell_groups": ";".join(sorted(PANEL_GROUPS[panel])),
        })

    for group_id, info in enumerate(group_info):
        cells = int(pseudobulk_cells[group_id])
        total_umis = int(pseudobulk_umis[group_id])
        cell_count_rows.append({**info, "n_cells": cells, "total_raw_umis": total_umis,
                                "meets_min_cell_gate": cells >= MIN_CELLS_PER_DONOR})
        symbol_counts = pseudobulk_counts[group_id]
        for gene_index, gene in enumerate(target_symbols):
            if gene in present_symbols:
                pseudobulk_rows.append({**info, "n_cells": cells, "total_raw_umis": total_umis,
                                        "gene_symbol": gene, "raw_count": int(symbol_counts[gene_index])})

    score_rows = []
    by_group_panel: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for group_id, info in enumerate(group_info):
        if pseudobulk_cells[group_id] < MIN_CELLS_PER_DONOR or pseudobulk_umis[group_id] <= 0:
            continue
        for panel, genes in PANELS.items():
            if info["cell_group"] not in PANEL_GROUPS[panel]:
                continue
            present = [gene for gene in genes if gene in present_symbols]
            if not present:
                continue
            values = []
            for gene in present:
                count = int(pseudobulk_counts[group_id, symbol_to_col[gene]])
                values.append(float(np.log1p(count / pseudobulk_umis[group_id] * 1_000_000)))
            score = float(np.mean(values))
            row = {**info, "n_cells": int(pseudobulk_cells[group_id]), "total_raw_umis": int(pseudobulk_umis[group_id]),
                   "panel": panel, "n_genes_observed": len(present), "score_mean_log1p_cpm": score,
                   "age_analysis_eligible": info["condition"] == "healthy",
                   "cell_minimum_pass": True}
            score_rows.append(row)
            by_group_panel[(info["cell_group"], panel)].append({**row, "score": score})

    rng = np.random.default_rng(SEED)
    age_rows, disease_rows, challenge_rows = [], [], []
    for (cell_group, panel), records in sorted(by_group_panel.items()):
        healthy = [row for row in records if row["condition"] == "healthy"]
        cases = [row for row in records if row["condition"] == "periodontitis"]
        age_ok = len(healthy) >= MIN_AGE_DONORS
        age_result = slope_per_decade(healthy, rng) if age_ok else {}
        age_rows.append({
            "cell_group": cell_group, "panel": panel, "n_healthy_donors": len(healthy),
            "n_periodontitis_donors": len(cases), "min_cells_per_donor": MIN_CELLS_PER_DONOR,
            "eligible": age_ok, "age_min": min((int(row["age"]) for row in healthy), default=""),
            "age_max": max((int(row["age"]) for row in healthy), default=""), **age_result,
            "interpretation_limit": "Exploratory donor-level age association in 13 healthy gingival donors; not an age clock or rejuvenation measure.",
        })
        disease_ok = len(healthy) >= MIN_AGE_DONORS and len(cases) >= MIN_DISEASE_CASE_DONORS
        if disease_ok:
            full = disease_effect(healthy + cases, rng)
            v3 = [row for row in records if row["cellranger_versions"] == "3.0.1"]
            v3_healthy = [row for row in v3 if row["condition"] == "healthy"]
            v3_cases = [row for row in v3 if row["condition"] == "periodontitis"]
            v3_result = disease_effect(v3_healthy + v3_cases, rng) if len(v3_healthy) >= MIN_AGE_DONORS and len(v3_cases) >= MIN_DISEASE_CASE_DONORS else {}
            disease_rows.append({
                "cell_group": cell_group, "panel": panel, "n_healthy_donors": len(healthy),
                "n_periodontitis_donors": len(cases), "healthy_age_range": f"{min(int(r['age']) for r in healthy)}-{max(int(r['age']) for r in healthy)}",
                "periodontitis_age_range": f"{min(int(r['age']) for r in cases)}-{max(int(r['age']) for r in cases)}",
                "age_adjusted_difference": full["age_adjusted_difference"],
                "bootstrap_low": full["bootstrap_low"], "bootstrap_high": full["bootstrap_high"],
                "cellranger3_healthy_donors": len(v3_healthy), "cellranger3_periodontitis_donors": len(v3_cases),
                "cellranger3_age_adjusted_difference": v3_result.get("age_adjusted_difference", ""),
                "cellranger3_bootstrap_low": v3_result.get("bootstrap_low", ""),
                "cellranger3_bootstrap_high": v3_result.get("bootstrap_high", ""),
                "interpretation_limit": "Age-adjusted cross-sectional contrast; donor group is inferred from GEO sample-code roots and matching Table S1 demographics; do not treat bootstrap ranges as confirmatory inference.",
            })
        else:
            disease_rows.append({"cell_group": cell_group, "panel": panel, "n_healthy_donors": len(healthy),
                                 "n_periodontitis_donors": len(cases), "eligible": False,
                                 "interpretation_limit": "Insufficient donor-level cell coverage for the prespecified descriptive contrast."})
        age_sign = np.sign(float(age_result["slope_per_10y"])) if age_result.get("slope_per_10y") not in (None, "") else 0
        disease_sign = np.sign(float(disease_rows[-1].get("age_adjusted_difference", 0) or 0))
        direction = "same_direction" if age_sign and disease_sign and age_sign == disease_sign else (
            "opposite_direction" if age_sign and disease_sign and age_sign != disease_sign else "not_comparable")
        challenge_rows.append({
            "cell_group": cell_group, "panel": panel, "healthy_age_slope_per_10y": age_result.get("slope_per_10y", ""),
            "age_adjusted_periodontitis_difference": disease_rows[-1].get("age_adjusted_difference", ""),
            "direction_relation": direction,
            "interpretation_limit": "Direction comparison only; age and disease are distinct cross-sectional contrasts with small donor counts.",
        })

    sample_output = []
    for sample_id, info in sorted(sample_rows.items()):
        sample_output.append({**info, "n_cells_in_h5ad": int(sample_counts[sample_id])})

    DERIVED.mkdir(parents=True, exist_ok=True)
    output_map = {
        "oral_atlas_sample_crosswalk.tsv": sample_output,
        "gingival_cellset_donor_counts.tsv": cell_count_rows,
        "gingival_cellset_pseudobulk_fixed_genes.tsv": pseudobulk_rows,
        "gingival_fixed_panel_coverage.tsv": panel_coverage_rows,
        "gingival_fixed_panel_donor_scores.tsv": score_rows,
        "gingival_healthy_age_slopes.tsv": age_rows,
        "gingival_periodontitis_challenge.tsv": disease_rows,
        "gingival_age_disease_direction_challenge.tsv": challenge_rows,
    }
    for name, rows in output_map.items():
        write_tsv(DERIVED / name, rows)

    version_counts = Counter(row["cellranger_version"] for row in sample_rows.values())
    donor_versions = Counter("mixed" if len(value["versions"]) > 1 else next(iter(value["versions"]))
                             for value in donor_metadata.values())
    cell_group_counts: Counter[str] = Counter()
    for row in cell_count_rows:
        cell_group_counts[row["cell_group"]] += int(row["n_cells"])
    summary = {
        "accession": "GSE164241",
        "curated_source": "CZ CELLxGENE integrated Human Periodontal Atlas v1",
        "curated_source_url": "https://cellxgene.cziscience.com/collections/71f4bccf-53d4-4c12-9e80-e73bfb89e398",
        "original_study": "Williams et al., 2021, PMID 34129837",
        "h5ad_sha256": observed_sha,
        "h5ad_bytes": H5AD.stat().st_size,
        "h5ad_cell_count_all_studies": n_obs,
        "gse164241_gingiva_cells": len(selected_row_indices),
        "libraries": len(sample_rows),
        "library_counts_by_condition": dict(Counter(row["condition"] for row in sample_rows.values())),
        "inferred_donor_counts": dict(actual_donors),
        "source_cellranger_version_libraries": dict(version_counts),
        "source_cellranger_version_donors": dict(donor_versions),
        "cell_group_counts": dict(sorted(cell_group_counts.items())),
        "annotated_cellset_coverage": {
            label: {
                "n_cells": int(count),
                "mapped_to_groups": sorted(group for group, labels in CELL_GROUP_SETS.items() if label in labels),
                "exclusion_reason": INTENTIONALLY_EXCLUDED_CELLSETS.get(label, ""),
            }
            for label, count in sorted(observed_cellset_counts.items())
        },
        "raw_count_matrix": "AnnData .raw/X; integer-valued counts verified in streamed chunks",
        "fixed_panels": PANELS,
        "unit_of_analysis": "Inferred donor group for age and disease contrasts; sample biopsies and cells are nested observations. Donor groups are inferred from shared sample-code roots and matching Table S1 age/sex/race, not an explicit donor identifier.",
        "analysis_limits": [
            "Only the 13 healthy gingival and 8 periodontitis gingival libraries from the original series are analyzed; buccal samples and later ID080UST are excluded.",
            "Repeated PD161 and PD164 biopsies are summed within their inferred donors; no biopsy is counted as an independent person.",
            "Healthy-age analyses are exploratory with 13 donors spanning 21–61 years, not an adult age clock and not a claim about rejuvenation.",
            "Disease contrasts include five inferred periodontitis donors; they are used to challenge age-associated axes as inflammatory alternatives, not to estimate treatment effects.",
            "Cellranger version sensitivity is descriptive; processing and clinical groups are not fully randomized across versions.",
            "CellxGene integrated cell annotations are used as supplied; they are not a blinded reannotation of the source data.",
            "The percentile ranges are exploratory bootstrap summaries and do not substitute for independent validation or confirmatory p-values.",
        ],
        "outputs": list(output_map),
    }
    summary_path = DERIVED / "gingival_cell_atlas_analysis_summary.json"
    with summary_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"accession": "GSE164241", "cells": len(selected_row_indices),
                      "samples": len(sample_rows), "donors": dict(actual_donors),
                      "source_cellranger_version_libraries": dict(version_counts),
                      "output_dir": str(DERIVED), "panel_scores": len(score_rows)}, indent=2))


if __name__ == "__main__":
    main()
