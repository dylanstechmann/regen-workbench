"""Quantify fixed-panel co-detection in the two deposited GSE306722 records.

This is a source-scoped descriptive screen. It does not assign cell types,
qualify raw UMI provenance, or treat barcodes as independent donors.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import regen
from summarize_native_pdls_markers import load_labels, load_panel, verified_path

MATRIX_GENES = ("POSTN", "COL1A1", "DCN", "COL12A1")
LIGAMENT_ASSOCIATED_GENES = ("SCX", "TNMD", "MKX", "CILP", "ITGA11")
CONTEXTS = {
    "endothelial_any": ("PECAM1", "CDH5"),
    "perivascular_any": ("RGS5", "KCNJ8"),
    "immune_any": ("CD3D", "CD3E", "LYZ", "CSF1R"),
}
ENTRY_THRESHOLDS = (1, 2)
ANCHOR_MINIMUMS = (2, 3)
SCREENS = ("all_barcodes", "source_rule_sensitivity")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_tsv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("Cannot write an empty coexpression table")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def summarize_sample(sample: dict, features: list[dict], barcodes: list[str], matrix,
                     selection: dict, output_rows: list[dict], pair_rows: list[dict],
                     burden_rows: list[dict]) -> dict:
    import numpy as np

    feature_indices: dict[str, list[int]] = {}
    for index, feature in enumerate(features):
        feature_indices.setdefault(feature["symbol"], []).append(index)
    required = set(MATRIX_GENES + LIGAMENT_ASSOCIATED_GENES)
    for genes in CONTEXTS.values():
        required.update(genes)
    vectors = {}
    for symbol in required:
        indices = feature_indices.get(symbol, [])
        if len(indices) != 1 or features[indices[0]]["type"] != "Gene Expression":
            raise ValueError(f"Required symbol is missing or ambiguous: {symbol}")
        vectors[symbol] = np.asarray(matrix.getrow(indices[0]).toarray()).ravel()

    records = []
    for screen_name in SCREENS:
        selected = np.ones(len(barcodes), dtype=bool) if screen_name == "all_barcodes" else selection
        n = int(selected.sum())
        for entry_threshold in ENTRY_THRESHOLDS:
            positive = {symbol: values >= entry_threshold for symbol, values in vectors.items()}
            matrix_score = np.sum(np.column_stack([positive[g] for g in MATRIX_GENES]), axis=1)
            contexts = {name: np.logical_or.reduce([positive[g] for g in genes])
                        for name, genes in CONTEXTS.items()}
            group_vectors = {"matrix_anchor_ge2_of4": matrix_score >= 2,
                             "matrix_anchor_ge3_of4": matrix_score >= 3,
                             **contexts}
            for anchor_minimum in ANCHOR_MINIMUMS:
                anchor = matrix_score >= anchor_minimum
                ligament_score = np.sum(np.column_stack([positive[g] for g in LIGAMENT_ASSOCIATED_GENES]), axis=1)
                core_triad = np.logical_and.reduce([positive[g] for g in ("SCX", "TNMD", "MKX")])
                all_five = np.logical_and.reduce([positive[g] for g in LIGAMENT_ASSOCIATED_GENES])
                anchor_n = int(np.count_nonzero(selected & anchor))
                burden_rows.append({
                    "geo_sample": sample["geo_sample"],
                    "stage_label_from_source_fields": sample["stage_label_from_source_fields"],
                    "screen": screen_name,
                    "entry_positive_threshold": entry_threshold,
                    "matrix_anchor_rule": f"at_least_{anchor_minimum}_of_4",
                    "n_selected_barcodes": n,
                    "matrix_anchor_barcodes": anchor_n,
                    "anchor_with_at_least_1_of_5_ligament_genes": int(np.count_nonzero(selected & anchor & (ligament_score >= 1))),
                    "anchor_with_at_least_2_of_5_ligament_genes": int(np.count_nonzero(selected & anchor & (ligament_score >= 2))),
                    "anchor_with_at_least_3_of_5_ligament_genes": int(np.count_nonzero(selected & anchor & (ligament_score >= 3))),
                    "anchor_with_SCX_TNMD_MKX_triad": int(np.count_nonzero(selected & anchor & core_triad)),
                    "anchor_with_all_5_ligament_genes": int(np.count_nonzero(selected & anchor & all_five)),
                    "triad_fraction_within_anchor": (int(np.count_nonzero(selected & anchor & core_triad)) / anchor_n
                                                     if anchor_n else None),
                })
                for target in LIGAMENT_ASSOCIATED_GENES:
                    joint = int(np.count_nonzero(selected & anchor & positive[target]))
                    anchor_n = int(np.count_nonzero(selected & anchor))
                    target_n = int(np.count_nonzero(selected & positive[target]))
                    record = {
                        "geo_sample": sample["geo_sample"],
                        "stage_label_from_source_fields": sample["stage_label_from_source_fields"],
                        "screen": screen_name,
                        "entry_positive_threshold": entry_threshold,
                        "matrix_anchor_rule": f"at_least_{anchor_minimum}_of_4",
                        "matrix_anchor_genes": ";".join(MATRIX_GENES),
                        "target_gene": target,
                        "n_selected_barcodes": n,
                        "matrix_anchor_barcodes": anchor_n,
                        "target_positive_barcodes": target_n,
                        "joint_positive_barcodes": joint,
                        "target_fraction_within_anchor": joint / anchor_n if anchor_n else None,
                        "anchor_fraction_within_target": joint / target_n if target_n else None,
                        "joint_fraction_of_selected": joint / n if n else None,
                    }
                    output_rows.append(record)
                    records.append(record)

            for matrix_gene in MATRIX_GENES:
                for target in LIGAMENT_ASSOCIATED_GENES:
                    a = selected & positive[matrix_gene]
                    b = selected & positive[target]
                    both = int(np.count_nonzero(a & b))
                    n_a, n_b = int(a.sum()), int(b.sum())
                    pair_rows.append({
                        "geo_sample": sample["geo_sample"],
                        "stage_label_from_source_fields": sample["stage_label_from_source_fields"],
                        "screen": screen_name,
                        "entry_positive_threshold": entry_threshold,
                        "marker_a": matrix_gene,
                        "marker_b": target,
                        "n_selected_barcodes": n,
                        "marker_a_positive": n_a,
                        "marker_b_positive": n_b,
                        "both_positive": both,
                        "fraction_a_positive_with_b": both / n_b if n_b else None,
                        "fraction_b_positive_with_a": both / n_a if n_a else None,
                        "joint_fraction_of_selected": both / n if n else None,
                    })

            for context_name, context_positive in contexts.items():
                for target in LIGAMENT_ASSOCIATED_GENES:
                    anchor = group_vectors["matrix_anchor_ge2_of4"]
                    joint = int(np.count_nonzero(selected & anchor & positive[target] & context_positive))
                    anchor_target = int(np.count_nonzero(selected & anchor & positive[target]))
                    context_n = int(np.count_nonzero(selected & context_positive))
                    records.append({
                        "geo_sample": sample["geo_sample"],
                        "stage_label_from_source_fields": sample["stage_label_from_source_fields"],
                        "screen": screen_name,
                        "entry_positive_threshold": entry_threshold,
                        "matrix_anchor_rule": "at_least_2_of_4",
                        "matrix_anchor_genes": ";".join(MATRIX_GENES),
                        "target_gene": target,
                        "comparison_context": context_name,
                        "n_selected_barcodes": n,
                        "matrix_anchor_and_target_barcodes": anchor_target,
                        "context_positive_barcodes": context_n,
                        "joint_anchor_target_context_barcodes": joint,
                        "context_fraction_within_anchor_target": joint / anchor_target if anchor_target else None,
                        "joint_fraction_of_selected": joint / n if n else None,
                    })

    return {
        "geo_sample": sample["geo_sample"],
        "stage_label_from_source_fields": sample["stage_label_from_source_fields"],
        "barcodes": len(barcodes),
        "screen_counts": {
            screen: int(np.ones(len(barcodes), dtype=bool).sum()) if screen == "all_barcodes" else int(selection.sum())
            for screen in SCREENS
        },
        "matrix_genes": list(MATRIX_GENES),
        "ligament_associated_genes": list(LIGAMENT_ASSOCIATED_GENES),
        "entry_positive_thresholds": list(ENTRY_THRESHOLDS),
        "anchor_rules": {"at_least_2_of_4": 2, "at_least_3_of_4": 3},
        "context_positive_counts_all_barcodes_threshold_1": {
            name: int(np.count_nonzero(np.logical_or.reduce([vectors[g] >= 1 for g in genes])))
            for name, genes in CONTEXTS.items()
        },
    }


def plot_coexpression(rows: list[dict], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    samples = list(dict.fromkeys(row["geo_sample"] for row in rows))
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True, sharey=True)
    for ax, (sample, screen) in zip(axes.flat,
                                    [(s, sc) for s in samples for sc in SCREENS], strict=True):
        chosen = [r for r in rows if r["geo_sample"] == sample and r["screen"] == screen
                  and r["entry_positive_threshold"] == 1 and r["matrix_anchor_rule"] == "at_least_2_of_4"]
        genes = list(LIGAMENT_ASSOCIATED_GENES)
        values = np.array([[next((r["target_fraction_within_anchor"] for r in chosen
                                  if r["target_gene"] == gene), np.nan)] for gene in genes], dtype=float)
        cmap = plt.colormaps["viridis"].copy()
        cmap.set_bad("#dddddd")
        image = ax.imshow(np.ma.masked_invalid(values), aspect="auto", cmap=cmap, vmin=0, vmax=1)
        ax.set_yticks(range(len(genes)), genes)
        ax.set_xticks([0], ["≥2 matrix markers"])
        ax.set_title(f"{sample} — {screen.replace('_', ' ')}")
        for i, row in enumerate(chosen):
            count = row["joint_positive_barcodes"]
            denom = row["matrix_anchor_barcodes"]
            ax.text(0, i, f"{count}/{denom}" if denom else "0/0", ha="center", va="center",
                    color="white" if denom and count / denom < .55 else "black", fontsize=9)
    fig.colorbar(image, ax=axes.ravel().tolist(), label="Target-positive fraction within matrix-anchor barcodes", shrink=.8)
    fig.suptitle("GSE306722 within-record marker co-detection (entry threshold ≥1)")
    fig.text(.5, .01, "Entry co-detection is descriptive; it does not define cell identity or donor-level replication.", ha="center", fontsize=9)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def write_report(path: Path, outputs: list[dict], burden_rows: list[dict], binding: dict,
                 run_utc: str) -> None:
    lines = [
        "# Native PDL within-record marker co-detection",
        "",
        f"Analysis run (UTC): {run_utc}.",
        "",
        "## Question and fixed rules",
        "",
        "Do PDL-associated low-abundance markers occur in the same deposited barcodes as a multi-marker extracellular-matrix pattern, and how often do competing vascular/perivascular or immune marker contexts co-occur? This is a descriptive follow-up to the fixed 45-symbol native screen, not a cell annotation.",
        "",
        "A matrix-anchor barcode has positive entries for at least two of POSTN, COL1A1, DCN and COL12A1; a stricter three-of-four rule is also reported. Ligament-associated targets are SCX, TNMD, MKX, CILP and ITGA11. A positive entry is evaluated at thresholds of at least 1 and at least 2 deposited units. Vascular, perivascular and immune contexts are positive when any listed fixed-panel marker reaches that same threshold. The two archive records and the all-barcode/source-rule screens remain separate.",
        "",
        "The deposited matrices have integer numeric form, but their raw-UMI lineage and exact preprocessing stage remain unresolved. Barcode-level co-detection can reflect capture depth, ambient signal, multiplets, processing and true biological co-expression. The two GEO records lack a cell-to-library/tooth/donor map; barcodes are descriptive observations, not independent donor replicates. The source labels are developmental root-maturity labels, not chronological aging or rejuvenation.",
        "",
        "## Key results",
        "",
        "The following table uses the all-barcode screen and entry threshold ≥1. Fractions use only barcodes meeting the stated matrix-anchor rule.",
        "",
        "| Record / source label | Anchor rule | Anchor barcodes | Gene | Joint barcodes | Gene positive within anchor |",
        "| --- | --- | ---: | --- | ---: | ---: |",
    ]
    for row in outputs:
        if row["screen"] != "all_barcodes" or row["entry_positive_threshold"] != 1:
            continue
        fraction = "undefined" if row["target_fraction_within_anchor"] is None else f"{row['target_fraction_within_anchor']:.2%}"
        lines.append(f"| {row['geo_sample']} ({row['stage_label_from_source_fields']}) | {row['matrix_anchor_rule']} | {row['matrix_anchor_barcodes']} | {row['target_gene']} | {row['joint_positive_barcodes']} | {fraction} |")
    lines += [
        "",
        "A compact combination check asks how often the same matrix-anchor barcode contains multiple ligament-associated signals. These are raw co-detection counts at threshold ≥1; the second threshold and cell-inclusion screen are retained in the machine-readable table.",
        "",
        "| Record / source label | Screen | Entry threshold | Anchor barcodes | ≥1 of 5 genes | ≥2 of 5 | ≥3 of 5 | SCX+TNMD+MKX |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in burden_rows:
        if row["matrix_anchor_rule"] != "at_least_2_of_4":
            continue
        lines.append(f"| {row['geo_sample']} ({row['stage_label_from_source_fields']}) | {row['screen']} | ≥{row['entry_positive_threshold']} | {row['matrix_anchor_barcodes']} | {row['anchor_with_at_least_1_of_5_ligament_genes']} | {row['anchor_with_at_least_2_of_5_ligament_genes']} | {row['anchor_with_at_least_3_of_5_ligament_genes']} | {row['anchor_with_SCX_TNMD_MKX_triad']} |")
    lines += [
        "",
        "## Competing marker contexts",
        "",
        "Context co-detection tables are retained in `pdls_native_coexpression_contexts.tsv`. A context marker in the same barcode as a matrix anchor is not by itself proof of a distinct cell type or contamination; the deposited processing and cell labels do not support that conclusion.",
        "",
        "## Interpretation and limits",
        "",
        "This calculation answers whether fixed-panel signals are observed together at the barcode level. It cannot establish organized PDL tissue, oriented fibers inserting at cementum and alveolar bone, physiological tooth mobility, load transfer, avoidance of ankylosis, or durable function. It also cannot assign a maturity effect because the archive has one group-level record per source label and no donor-level map. Native deposited-entry cp10k remains distinct from bulk TPM.",
        "",
        "The [co-detection figure](derived/pdls-native-coexpression/pdls_native_coexpression.png), all pairwise matrix/ligament-marker counts, conditional fractions, context summaries and output hashes are committed beside this report. The raw matrix inputs remain local; their SHA-256 bindings are checked against the committed source receipt before analysis.",
        "",
        "Reproduce from the repository root with the running workbench container:",
        "",
        "```powershell",
        "$analysisRevision = git rev-parse HEAD",
        "docker compose exec -T workbench python /lab/workbench/studies/dental-regeneration-2026-10-09/analyze_pdls_native_coexpression.py --code-revision $analysisRevision",
        "```",
        "",
        f"Source script SHA-256: `{binding['analysis_script_sha256']}`.",
        f"Frozen panel SHA-256: `{binding['panel_sha256']}`.",
        f"Matrix-audit receipt SHA-256: `{binding['matrix_audit_sha256']}`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=HERE / "pdls_maturity_matrix_receipt.json")
    parser.add_argument("--panel", type=Path, default=HERE / "native_marker_panel.json")
    parser.add_argument("--data-root", type=Path, default=regen.DATA)
    parser.add_argument("--out-dir", type=Path, default=HERE / "derived" / "pdls-native-coexpression")
    parser.add_argument("--report", type=Path, default=HERE / "PDLSC_NATIVE_COEXPRESSION.md")
    parser.add_argument("--code-revision", default=None)
    args = parser.parse_args()
    import numpy as np
    import scipy
    from scipy.io import mmread

    load_panel(args.panel)
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    if (audit.get("accession") != "GSE306722" or len(audit.get("samples", [])) != 2
            or not audit.get("qualification", {}).get("descriptive_sparse_matrix_loading_eligible")):
        raise ValueError("A qualified two-record GSE306722 matrix audit is required")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    coexpression_rows, pair_rows, context_rows, burden_rows, sample_summaries, bound_inputs = [], [], [], [], [], []

    for sample in audit["samples"]:
        if not sample["matrix"]["structural_quality_passed"] or not sample["matrix"]["nonnegative_integer_numeric_form"]:
            raise ValueError("The audited sparse matrix must retain its checked numeric form")
        paths = {kind: verified_path(args.data_root, sample["files"][kind])
                 for kind in ("features", "barcodes", "matrix")}
        features = load_labels(paths["features"], "features")
        barcodes = load_labels(paths["barcodes"], "barcodes")
        with gzip.open(paths["matrix"], "rb") as handle:
            matrix = mmread(handle).tocsr()
        if sample["matrix"]["orientation_from_label_dimensions"] == "barcodes_by_features":
            matrix = matrix.T.tocsr()
        if matrix.shape != (len(features), len(barcodes)):
            raise ValueError("Matrix dimensions do not match audited feature/barcode labels")
        indices = {i for i, feature in enumerate(features) if feature["type"] == "Gene Expression"}
        gene_matrix = matrix[list(sorted(indices)), :].tocsr()
        totals = np.asarray(gene_matrix.sum(axis=0)).ravel()
        detected = np.asarray(gene_matrix.getnnz(axis=0)).ravel()
        mito_rows = [i for i, feature in enumerate(features)
                     if feature["type"] == "Gene Expression" and feature["symbol"].startswith("MT-")]
        mito = np.asarray(matrix[mito_rows, :].sum(axis=0)).ravel()
        mito_fraction = np.divide(mito, totals, out=np.full(totals.shape, np.nan), where=totals > 0)
        selected = (detected >= 200) & (mito_fraction <= 0.1) & (totals > 0)
        summary = summarize_sample(sample, features, barcodes, matrix, selected,
                                   coexpression_rows, pair_rows, burden_rows)
        sample_summaries.append(summary)

        feature_indices: dict[str, list[int]] = {}
        for index, feature in enumerate(features):
            feature_indices.setdefault(feature["symbol"], []).append(index)
        vectors = {}
        for symbol in set(MATRIX_GENES + LIGAMENT_ASSOCIATED_GENES + tuple(g for group in CONTEXTS.values() for g in group)):
            vectors[symbol] = np.asarray(matrix[feature_indices[symbol][0], :].toarray()).ravel()
        for screen_name in SCREENS:
            use = np.ones(len(barcodes), dtype=bool) if screen_name == "all_barcodes" else selected
            for threshold in ENTRY_THRESHOLDS:
                positives = {g: v >= threshold for g, v in vectors.items()}
                anchor2 = np.sum(np.column_stack([positives[g] for g in MATRIX_GENES]), axis=1) >= 2
                context_flags = {name: np.logical_or.reduce([positives[g] for g in genes])
                                 for name, genes in CONTEXTS.items()}
                for target in LIGAMENT_ASSOCIATED_GENES:
                    anchor_target = use & anchor2 & positives[target]
                    for context_name, context_flag in context_flags.items():
                        joint = int(np.count_nonzero(anchor_target & context_flag))
                        denom = int(anchor_target.sum())
                        context_rows.append({
                            "geo_sample": sample["geo_sample"],
                            "stage_label_from_source_fields": sample["stage_label_from_source_fields"],
                            "screen": screen_name,
                            "entry_positive_threshold": threshold,
                            "matrix_anchor_rule": "at_least_2_of_4",
                            "target_gene": target,
                            "comparison_context": context_name,
                            "n_selected_barcodes": int(use.sum()),
                            "anchor_and_target_barcodes": denom,
                            "context_positive_within_anchor_target": joint,
                            "context_fraction_within_anchor_target": joint / denom if denom else None,
                        })
        bound_inputs.append({"geo_sample": sample["geo_sample"],
                             "files_sha256": {kind: sample["files"][kind]["sha256"] for kind in paths}})
        print(json.dumps(summary), flush=True)
        del matrix, gene_matrix

    coexpression_path = args.out_dir / "pdls_native_coexpression.tsv"
    pair_path = args.out_dir / "pdls_native_pairwise_coexpression.tsv"
    context_path = args.out_dir / "pdls_native_coexpression_contexts.tsv"
    burden_path = args.out_dir / "pdls_native_coexpression_burdens.tsv"
    figure_path = args.out_dir / "pdls_native_coexpression.png"
    write_tsv(coexpression_path, coexpression_rows)
    write_tsv(pair_path, pair_rows)
    write_tsv(context_path, context_rows)
    write_tsv(burden_path, burden_rows)
    plot_coexpression(coexpression_rows, figure_path)
    binding = {
        "matrix_audit_sha256": sha256(args.audit),
        "panel_sha256": sha256(args.panel),
        "source_linkage_audit_sha256": sha256(HERE / "PDLSC_SOURCE_LINKAGE_AUDIT.md"),
        "analysis_script_sha256": sha256(Path(__file__)),
        "code_revision_at_run": args.code_revision,
        "inputs": bound_inputs,
    }
    run_utc = regen.now()
    report_path = args.report
    write_report(report_path, coexpression_rows, burden_rows, binding, run_utc)
    outputs = [coexpression_path, pair_path, context_path, burden_path, figure_path, report_path]
    provenance = regen.record("dental-pdls-native-coexpression", {
        "question": "Which fixed-panel PDL-associated signals co-occur with a multi-marker matrix pattern and competing vascular/perivascular/immune contexts?",
        "binding": binding,
        "normalization": "Binary deposited-entry detection at thresholds >=1 and >=2; no cross-record pooling.",
        "unit": "Barcode within one of two GEO archive records; not an independent donor.",
        "scope": "Descriptive co-detection; raw UMI lineage and cell identity are unresolved.",
    }, outputs)
    receipt = {
        "schema_version": 1,
        "accession": "GSE306722",
        "run_utc": run_utc,
        "software": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "binding": binding,
        "matrix_genes": list(MATRIX_GENES),
        "ligament_associated_genes": list(LIGAMENT_ASSOCIATED_GENES),
        "competing_contexts": {key: list(value) for key, value in CONTEXTS.items()},
        "entry_positive_thresholds": list(ENTRY_THRESHOLDS),
        "screens": list(SCREENS),
        "samples": sample_summaries,
        "claim_limits": {"raw_umi_lineage_qualified": False, "donor_inference_eligible": False,
                          "cell_type_annotations_assigned": False, "functional_attachment_measured": False},
        "local_provenance_receipt": provenance.name,
        "outputs": [{"filename": path.name, "sha256": sha256(path), "bytes": path.stat().st_size}
                    for path in outputs],
    }
    (args.out_dir / "summary.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(args.out_dir), "coexpression_rows": len(coexpression_rows),
                      "pairwise_rows": len(pair_rows), "context_rows": len(context_rows), "burden_rows": len(burden_rows),
                      "summary": str(args.out_dir / "summary.json")}), flush=True)


if __name__ == "__main__":
    main()
