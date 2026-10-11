"""Descriptive, group-level analysis of the qualified GSE83382 gingiva matrix."""

from __future__ import annotations

import csv
import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import regen

ACCESSION = "GSE83382"
CACHE = regen.DATA / "literature" / "gingival-age-reference-GSE83382"
INTAKE = HERE / "gingival_age_intake_receipt.json"
DERIVED = HERE / "derived" / "gingival-age-reference-GSE83382"

# Panels are deliberately compact, fixed, and reported with coverage. They are
# exploratory axes rather than a validated biological age clock or cell atlas.
PANELS = {
    "matrix_degradation": ["MMP1", "MMP2", "MMP3", "MMP8", "MMP9", "MMP12", "MMP13", "MMP27"],
    "matrix_inhibitors": ["TIMP1", "TIMP2", "TIMP3"],
    "structural_ecm": ["COL1A1", "COL1A2", "COL3A1", "COL5A1", "COL6A1", "FN1", "DCN", "LUM"],
    "inflammation": ["IL1A", "IL1B", "IL6", "TNF", "CXCL8", "CCL2", "PTGS2", "NFKBIA", "ICAM1"],
    "epithelial_barrier_identity": ["KRT5", "KRT14", "KRT13", "KRT19", "EPCAM", "CDH1", "CLDN1", "SFN", "IVL"],
    "fibroblast_stromal_identity": ["COL1A1", "COL1A2", "COL3A1", "DCN", "LUM", "PDGFRA", "PDGFRB", "THY1", "COL6A1"],
}


def read_matrix(path: Path, group_map: dict[str, str]) -> tuple[dict, dict, dict]:
    samples: dict[str, dict[str, list[tuple[str, float]]]] = {
        sample: defaultdict(list) for sample in group_map
    }
    features: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    rows = 0
    empty_symbols = 0
    duplicate_symbol_rows: Counter[str] = Counter()
    feature_ids: set[str] = set()
    with gzip.open(path, "rt", encoding="utf-8", errors="strict", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        if header[:2] != ["RefSeq", "Symbol"] or set(header[2:]) != set(group_map):
            raise ValueError(f"Unexpected GSE83382 processed matrix header: {header!r}")
        for line_no, row in enumerate(reader, start=2):
            rows += 1
            if len(row) != len(header):
                raise ValueError(f"Malformed expression row {line_no}: {len(row)} fields, expected {len(header)}")
            refseq, raw_symbol = row[0].strip(), row[1].strip()
            if refseq in feature_ids:
                raise ValueError(f"Duplicated RefSeq feature identifier: {refseq}")
            feature_ids.add(refseq)
            symbol = raw_symbol.upper()
            if not symbol or symbol in {"-", "NA", "N/A", "NULL"}:
                empty_symbols += 1
                continue
            duplicate_symbol_rows[symbol] += 1
            for sample, value in zip(header[2:], row[2:], strict=True):
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError(f"Non-finite expression value for {sample}/{symbol}")
                samples[sample][symbol].append((refseq, number))
                features[symbol][refseq][sample] = number
    stats = {
        "matrix_header": header,
        "feature_row_count": rows,
        "unique_refseq_features": len(feature_ids),
        "empty_or_placeholder_symbol_rows": empty_symbols,
        "unique_nonplaceholder_gene_symbols": len(duplicate_symbol_rows),
        "symbols_with_multiple_refseq_rows": sum(count > 1 for count in duplicate_symbol_rows.values()),
        "maximum_refseq_rows_per_symbol": max(duplicate_symbol_rows.values(), default=0),
        "duplicate_symbol_handling": "No collapse: fixed-panel summaries include a gene only when its symbol maps to exactly one RefSeq row. Multi-row symbols remain unresolved and are shown per RefSeq feature.",
    }
    return samples, features, stats


def write_tsv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty table: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    intake = json.loads(INTAKE.read_text(encoding="utf-8"))
    if intake["accession"] != ACCESSION or not intake["sample_mapping_check"]["group_counts_match"]:
        raise ValueError("GSE83382 intake qualification failed")
    expression_map = intake["expression_header_group_map"]
    group_map = {row["expression_header"]: row["group"] for row in expression_map}
    matrix_path = CACHE / "GSE83382_Processed_data_file_FPKM.txt.gz"
    if not matrix_path.is_file():
        raise FileNotFoundError("Run fetch_gingival_age_reference.py before this analysis")
    samples, features, matrix_stats = read_matrix(matrix_path, group_map)
    sample_names = list(group_map)
    group_names = ["young", "old"]

    gene_rows, feature_rows, coverage_rows, axis_rows = [], [], [], []
    panel_scores: dict[str, dict[str, float]] = {name: {} for name in PANELS}
    for panel, symbols in PANELS.items():
        unique_features = [symbol for symbol in symbols if len(features.get(symbol, {})) == 1]
        ambiguous = [symbol for symbol in symbols if len(features.get(symbol, {})) > 1]
        missing = [symbol for symbol in symbols if len(features.get(symbol, {})) == 0]
        coverage_rows.append({"panel": panel, "specified_genes": len(symbols),
                              "unique_single_refseq_genes": len(unique_features),
                              "ambiguous_multi_refseq_genes": ",".join(ambiguous),
                              "missing_genes": ",".join(missing),
                              "included_symbols": ",".join(unique_features)})
        for symbol in symbols:
            symbol_features = features.get(symbol, {})
            count = len(symbol_features)
            if count == 0:
                gene_rows.append({"panel": panel, "symbol": symbol, "status": "not_found",
                                  "refseq_feature_count": 0, "refseq_ids": "NA",
                                  "young_values": "NA", "old_values": "NA", "young_mean": "NA",
                                  "old_mean": "NA", "old_minus_young": "NA"})
            elif count > 1:
                gene_rows.append({"panel": panel, "symbol": symbol, "status": "ambiguous_multiple_refseq_features",
                                  "refseq_feature_count": count, "refseq_ids": ";".join(sorted(symbol_features)),
                                  "young_values": "NA", "old_values": "NA", "young_mean": "NA",
                                  "old_mean": "NA", "old_minus_young": "NA"})
                for refseq, values in sorted(symbol_features.items()):
                    young_values = [values[sample] for sample in sample_names if group_map[sample] == "young"]
                    old_values = [values[sample] for sample in sample_names if group_map[sample] == "old"]
                    young_mean, old_mean = sum(young_values) / len(young_values), sum(old_values) / len(old_values)
                    feature_rows.append({"panel": panel, "symbol": symbol, "RefSeq": refseq,
                                         "young_values": ";".join(f"{v:.6f}" for v in young_values),
                                         "old_values": ";".join(f"{v:.6f}" for v in old_values),
                                         "old_minus_young": f"{old_mean - young_mean:.6f}"})
            else:
                refseq, values = next(iter(symbol_features.items()))
                young_values = [values[sample] for sample in sample_names if group_map[sample] == "young"]
                old_values = [values[sample] for sample in sample_names if group_map[sample] == "old"]
                young_mean, old_mean = sum(young_values) / len(young_values), sum(old_values) / len(old_values)
                gene_rows.append({"panel": panel, "symbol": symbol, "status": "unique_refseq_feature",
                                  "refseq_feature_count": 1, "refseq_ids": refseq,
                                  "young_values": ";".join(f"{v:.6f}" for v in young_values),
                                  "old_values": ";".join(f"{v:.6f}" for v in old_values),
                                  "young_mean": f"{young_mean:.6f}", "old_mean": f"{old_mean:.6f}",
                                  "old_minus_young": f"{old_mean - young_mean:.6f}"})
        if not unique_features:
            continue
        for sample in sample_names:
            panel_scores[panel][sample] = sum(samples[sample][gene][0][1] for gene in unique_features) / len(unique_features)
        young_values = [panel_scores[panel][sample] for sample in sample_names if group_map[sample] == "young"]
        old_values = [panel_scores[panel][sample] for sample in sample_names if group_map[sample] == "old"]
        axis_rows.append({"panel": panel, "n_genes_observed": len(unique_features),
                          "young_sample_values": ";".join(f"{v:.6f}" for v in young_values),
                          "old_sample_values": ";".join(f"{v:.6f}" for v in old_values),
                          "young_mean": f"{sum(young_values) / len(young_values):.6f}",
                          "old_mean": f"{sum(old_values) / len(old_values):.6f}",
                          "old_minus_young": f"{sum(old_values) / len(old_values) - sum(young_values) / len(young_values):.6f}",
                          "interpretation_limit": "Descriptive group contrast in processed expression units; bulk tissue, n=3/group, no inferential test."})

    sample_rows = []
    for sample in sample_names:
        sample_rows.append({"expression_header": sample, "group": group_map[sample],
                            "n_unique_gene_features": sum(len(values) == 1 for values in samples[sample].values()),
                            **{panel: f"{panel_scores[panel][sample]:.6f}" if sample in panel_scores[panel] else ""
                               for panel in PANELS}})
    DERIVED.mkdir(parents=True, exist_ok=True)
    write_tsv(DERIVED / "gingival_age_gene_contrasts.tsv", gene_rows)
    if feature_rows:
        write_tsv(DERIVED / "gingival_age_feature_contrasts.tsv", feature_rows)
    write_tsv(DERIVED / "gingival_age_panel_coverage.tsv", coverage_rows)
    write_tsv(DERIVED / "gingival_age_axis_summary.tsv", axis_rows)
    write_tsv(DERIVED / "gingival_age_sample_scores.tsv", sample_rows)

    summary = {
        "accession": ACCESSION,
        "primary_publication": intake["primary_publication"],
        "eligibility": "Eligible for small, exploratory group-level descriptive analyses only; individual processed-matrix aliases cannot be matched to GEO's sample titles/ages.",
        "groups": {group: {"n": sum(value == group for value in group_map.values()),
                            "expression_headers": [sample for sample in sample_names if group_map[sample] == group]}
                   for group in group_names},
        "age_metadata_by_group": {group: sorted(row["age_years"] for row in intake["geo_sample_records"]
                                                   if row["group"] == group)
                                   for group in group_names},
        "sex_metadata": sorted({row["sex"] for row in intake["geo_sample_records"]}),
        "matrix_stats": matrix_stats,
        "processed_scale": intake["sample_mapping_check"]["expression_scale"],
        "analysis": {"fixed_panels": PANELS,
                     "panel_score": "Unweighted mean across observed fixed genes for each expression sample, then descriptive mean by age group.",
                     "gene_summary": "A gene is included in a panel score only when its symbol maps to one RefSeq feature; multi-feature symbols are listed separately without averaging or summation.",
                     "uncertainty": "No significance tests, confidence intervals or age-clock training. Three expression samples per group; expression aliases are not matched to individual GEO ages."},
        "outputs": ["gingival_age_gene_contrasts.tsv", "gingival_age_panel_coverage.tsv",
                    "gingival_age_axis_summary.tsv", "gingival_age_sample_scores.tsv",
                    "gingival_age_feature_contrasts.tsv"],
    }
    summary_path = DERIVED / "gingival_age_analysis_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    regen.record("gingival-gse83382-descriptive-analysis", {
        "accession": ACCESSION,
        "source_matrix_sha256": regen.sha256_file(matrix_path),
        "intake_receipt_sha256": regen.sha256_file(INTAKE),
        "panel_count": len(PANELS),
        "gene_contrast_rows": len(gene_rows),
    }, [DERIVED / name for name in summary["outputs"]] + [summary_path])
    print(json.dumps({"accession": ACCESSION, "groups": summary["groups"],
                      "matrix_stats": matrix_stats, "panel_summary": axis_rows,
                      "outputs": summary["outputs"] + [summary_path.name]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
