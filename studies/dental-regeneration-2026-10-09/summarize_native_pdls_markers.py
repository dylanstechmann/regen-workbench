"""Describe the fixed marker panel in hash-audited GSE306722 matrices.

All-barcode and source-rule sensitivity summaries use separate denominators.
No cell-type assignment, independent-cell testing or age/maturity model is fit.
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import regen

ACCESSION = "GSE306722"
SCREENS = ("all_barcodes", "source_rule_sensitivity")
EXPECTED_SYMBOLS = tuple("""POSTN COL1A1 COL1A2 COL3A1 COL12A1 COL14A1 ASPN
SCX TNMD MKX CILP DCN LUM BGN THY1 PDGFRA ITGA11 VCAM1 FAP
ALPL RUNX2 SP7 IBSP BGLAP POU5F1 SOX2 NANOG LIN28A AMELX ENAM AMBN DSPP MMP20
CD3D CD3E LYZ CSF1R PECAM1 CDH5 KRT14 ODAM PLP1 SOX10 RGS5 KCNJ8""".split())


def digest(path: Path) -> str:
    return regen.sha256_file(path)


def load_panel(path: Path) -> tuple[dict, list[str], dict[str, str]]:
    panel = json.loads(path.read_text(encoding="utf-8"))
    controls = panel["control_contexts"]
    symbols = panel["bulk_existing"] + [gene for item in controls for gene in item["symbols"]]
    if (panel["schema_version"] != 1 or panel["panel_id"] != "native-pdl-descriptive-45-v1"
            or len(panel["bulk_existing"]) != 33 or len(symbols) != 45
            or tuple(symbols) != EXPECTED_SYMBOLS or len(set(symbols)) != len(symbols)):
        raise ValueError("Expected the frozen 45-symbol descriptive panel")
    rule = panel["sensitivity_screen"]
    if (rule["minimum_detected_gene_expression_features"] != 200
            or rule["maximum_mitochondrial_entry_fraction"] != 0.1
            or rule["mitochondrial_gene_symbol_prefix"] != "MT-"):
        raise ValueError("Frozen source-rule sensitivity screen has changed")
    contexts = {gene: "existing_bulk_panel" for gene in panel["bulk_existing"]}
    contexts.update({gene: item["context"] for item in controls for gene in item["symbols"]})
    return panel, symbols, contexts


def verified_path(data_root: Path, file_record: dict) -> Path:
    relative = Path(file_record["local_path_relative_to_data"])
    if relative.is_absolute():
        raise ValueError("Audit file path must be relative to data")
    resolved_root = data_root.resolve()
    path = (resolved_root / relative).resolve()
    if not path.is_relative_to(resolved_root):
        raise ValueError("Audit file path leaves data directory")
    if not path.is_file() or digest(path) != file_record["sha256"]:
        raise ValueError(f"Input hash differs from matrix audit: {relative}")
    return path


def load_labels(path: Path, kind: str) -> list:
    result = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            fields = line.rstrip("\r\n").split("\t")
            if any(not field or field != field.strip() for field in fields):
                raise ValueError("Empty/padded feature or barcode label")
            if kind == "features":
                if len(fields) != 3:
                    raise ValueError("Feature type is required for normalization and screening")
                result.append({"id": fields[0], "symbol": fields[1], "type": fields[2]})
            elif kind == "barcodes" and len(fields) == 1:
                result.append(fields[0])
            else:
                raise ValueError("Unexpected label-file columns")
    identities = [item["id"] for item in result] if kind == "features" else result
    if not identities or len(set(identities)) != len(identities):
        raise ValueError("Empty or duplicated feature/barcode identifiers")
    return result


def cell_metrics(matrix, features: list[dict], minimum_features: int = 200,
                 maximum_mitochondrial_fraction: float = 0.1) -> dict:
    import numpy as np

    matrix = matrix.tocsr(copy=False)
    if matrix.shape[0] != len(features):
        raise ValueError("Feature dimension does not match labels")
    if (not np.isfinite(matrix.data).all() or np.any(matrix.data < 0)
            or np.any(matrix.data != np.floor(matrix.data))):
        raise ValueError("Expected finite, nonnegative integer-like deposited entries")
    gene_rows = np.array([item["type"] == "Gene Expression" for item in features])
    mitochondrial_rows = np.array([item["type"] == "Gene Expression"
                                   and item["symbol"].startswith("MT-") for item in features])
    if not gene_rows.any() or not mitochondrial_rows.any():
        raise ValueError("Gene Expression and MT- feature context required for the sensitivity screen")
    genes = matrix[gene_rows].copy()
    genes.eliminate_zeros()
    totals = np.asarray(genes.sum(axis=0)).ravel().astype(float)
    detected = np.asarray(genes.getnnz(axis=0)).ravel()
    mitochondrial_totals = np.asarray(matrix[mitochondrial_rows].sum(axis=0)).ravel().astype(float)
    fractions = np.divide(mitochondrial_totals, totals, out=np.full(totals.shape, np.nan), where=totals > 0)
    low_features = detected < minimum_features
    high_mito = fractions > maximum_mitochondrial_fraction
    zero_total = totals <= 0
    passes = (~low_features) & (~high_mito) & (~zero_total)
    return {"total": totals, "detected_features": detected, "mitochondrial_total": mitochondrial_totals,
            "mitochondrial_fraction": fractions, "low_features": low_features,
            "high_mitochondrial_fraction": high_mito, "zero_total": zero_total,
            "passes_sensitivity_screen": passes, "gene_expression_features": int(gene_rows.sum()),
            "mitochondrial_feature_count": int(mitochondrial_rows.sum())}


def marker_metrics(matrix, features: list[dict], symbols: list[str], contexts: dict[str, str],
                   metrics: dict, geo_sample: str, stage_label: str) -> list[dict]:
    import numpy as np

    matrix = matrix.tocsr(copy=False)
    candidates = {}
    for index, item in enumerate(features):
        candidates.setdefault(item["symbol"], []).append(index)
    rows = []
    for symbol in symbols:
        indices = candidates.get(symbol, [])
        if not indices:
            status = "missing_feature"
        elif len(indices) > 1:
            status = "ambiguous_symbol"
        elif features[indices[0]]["type"] != "Gene Expression":
            status = "non_gene_expression_feature"
        else:
            status = "unique_gene_expression_feature"
        entry_values = matrix.getrow(indices[0]).toarray().ravel().astype(float) if status.startswith("unique_") else None
        for screen in SCREENS:
            selection = np.ones(matrix.shape[1], dtype=bool) if screen == "all_barcodes" else metrics["passes_sensitivity_screen"]
            n = int(selection.sum())
            defined = selection & (metrics["total"] > 0)
            record = {"geo_sample": geo_sample, "stage_label": stage_label, "screen": screen,
                      "gene_symbol": symbol, "expression_context": contexts[symbol],
                      "feature_status": status, "feature_ids": [features[index]["id"] for index in indices],
                      "feature_types": [features[index]["type"] for index in indices],
                      "n_barcodes": n, "n_abundance_defined": int(defined.sum()),
                      "detected_barcodes": None, "detection_fraction": None,
                      "mean_log1p_entry_cp10k": None}
            if entry_values is not None:
                detected = int(np.count_nonzero(entry_values[selection] > 0))
                record["detected_barcodes"] = detected
                record["detection_fraction"] = detected / n if n else None
                if defined.any():
                    logged = np.log1p(entry_values[defined] * 10000.0 / metrics["total"][defined])
                    record["mean_log1p_entry_cp10k"] = float(logged.mean())
            rows.append(record)
    return rows


def summarize_screen(metrics: dict) -> dict:
    import numpy as np

    return {"all_barcodes": int(metrics["total"].size),
            "source_rule_sensitivity_retained": int(metrics["passes_sensitivity_screen"].sum()),
            "excluded_union": int(np.count_nonzero(~metrics["passes_sensitivity_screen"])),
            "fewer_than_200_detected_features": int(metrics["low_features"].sum()),
            "mitochondrial_fraction_above_10_percent": int(metrics["high_mitochondrial_fraction"].sum()),
            "both_low_features_and_high_mito": int(np.count_nonzero(metrics["low_features"] & metrics["high_mitochondrial_fraction"])),
            "zero_gene_expression_total": int(metrics["zero_total"].sum()),
            "gene_expression_feature_count": metrics["gene_expression_features"],
            "mitochondrial_feature_count": metrics["mitochondrial_feature_count"]}


def write_tsv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: json.dumps(value) if isinstance(value, list) else value for key, value in row.items()} for row in rows)


def plot_markers(rows: list[dict], symbols: list[str], destination: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    samples = list(dict.fromkeys(row["geo_sample"] for row in rows))
    columns = [(sample, screen) for sample in samples for screen in SCREENS]
    lookup = {(row["geo_sample"], row["screen"], row["gene_symbol"]): row for row in rows}
    values = []
    for key in ("detection_fraction", "mean_log1p_entry_cp10k"):
        values.append(np.array([[lookup[sample, screen, symbol][key] if lookup[sample, screen, symbol][key] is not None else np.nan
                                 for sample, screen in columns] for symbol in symbols], dtype=float))
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 15), sharey=True)
    for ax, array, title in zip(axes, values, ("Detection fraction", "Mean ln(1 + deposited-entry cp10k)"), strict=True):
        cmap = plt.colormaps["viridis"].copy()
        cmap.set_bad("#dddddd")
        img = ax.imshow(np.ma.masked_invalid(array), aspect="auto", cmap=cmap, vmin=0,
                        vmax=1 if title == "Detection fraction" else None)
        ax.set_xticks(range(len(columns)), [sample + "\n" + ("all" if screen == "all_barcodes" else "sensitivity") for sample, screen in columns], fontsize=8)
        ax.set_yticks(range(len(symbols)), symbols, fontsize=8)
        ax.set_title(title, fontsize=11)
        fig.colorbar(img, ax=ax, fraction=.03, pad=.03)
    fig.suptitle("GSE306722 fixed marker contexts — descriptive within archive records", fontsize=12)
    fig.text(.5, .008, "No cell identities or independent-donor contrasts. Gray = undefined/missing/ambiguous; zero remains numeric zero.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .02, 1, .97))
    fig.savefig(destination, dpi=150)
    plt.close(fig)


def write_report(path: Path, rows: list[dict], sample_summaries: list[dict], binding: dict,
                 panel: dict, run_utc: str) -> None:
    lines = ["# Native PDL fixed-marker descriptive screen", "",
             f"Run date/time (UTC): {run_utc}.", "",
             "The two deposited GSE306722 records contain matrix-associated expression and several competing control contexts. "
             "SCX and TNMD are detectable in a small fraction of archived barcodes. These summaries describe the deposited mixtures; "
             "they do not establish cell identities, maturation, rejuvenation or functional periodontal regeneration.", "",
             "## Frozen inputs and eligibility", "",
             "The analysis uses the exact 45 symbols in [native_marker_panel.json](native_marker_panel.json), frozen before expression inspection: "
             "the existing 33 bulk markers plus 12 source-backed control-context markers. The source selection and publication-linkage limits are in "
             "[PDLSC_SOURCE_LINKAGE_AUDIT.md](PDLSC_SOURCE_LINKAGE_AUDIT.md). All 45 symbols map uniquely to Gene Expression features in each deposited record. "
             "Ten duplicated symbols elsewhere in the feature file are not silently summed. All 36,601 features in each record have the Gene Expression type.", "",
             "[pdls_maturity_matrix_receipt.json](pdls_maturity_matrix_receipt.json) qualifies file integrity and positive integer numeric form. "
             "It does not establish raw UMI lineage or the exact processing stage. There is one GEO record per developmental source label, "
             "with no cell-to-donor map; barcodes are not independent biological replicates. The 59 barcode strings shared between records "
             "are kept distinct by prefixing each with its GEO sample accession.", "",
             "## Measures and implemented sensitivity screen", "",
             "Detection is the fraction of selected barcodes with a positive deposited entry for the uniquely mapped feature. "
             "The abundance measure is the average, over selected barcodes, of the natural logarithm ln(1 + 10,000 × feature entry / "
             "total Gene Expression entries in that barcode). Each barcode is normalized before logging and averaging. "
             "These are deposited-entry cp10k units, not verified raw UMI units and not bulk RNA-seq TPM.", "",
             "The all-barcode analysis includes every deposited barcode. The implemented sensitivity screen retains barcodes with "
             "at least 200 positive Gene Expression features and a mitochondrial entry fraction no greater than 10%, based on the "
             "source-described cutoffs. Mitochondrial features are the 13 Gene Expression rows whose symbols begin MT-. "
             "This screen does not reproduce source regression, clustering, tissue pooling or doublet removal.", "",
             "Missing features, ambiguous symbols and non-Gene Expression matches have undefined marker metrics. "
             "A uniquely mapped feature with zero entries remains measured zero. Zero-total barcodes have undefined normalized abundance "
             "and are excluded from the sensitivity screen; none occur in this run. An empty selected subset stays undefined rather than becoming zero.", "",
             "| GEO record / source label | All barcodes | Retained sensitivity | Excluded union | <200 features | >10% MT | Both exclusions |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for sample in sample_summaries:
        screen = sample["screen_accounting"]
        lines.append(f"| {sample['geo_sample']} / {sample['stage_label_from_source_fields']} | "
                     f"{screen['all_barcodes']:,} | {screen['source_rule_sensitivity_retained']:,} | {screen['excluded_union']:,} | "
                     f"{screen['fewer_than_200_detected_features']:,} | {screen['mitochondrial_fraction_above_10_percent']:,} | "
                     f"{screen['both_low_features_and_high_mito']:,} |")
    lines += ["", "The low-feature and high-mitochondrial counts overlap; adding them would overstate exclusions. "
              "The source labels identify archive records. No stage-effect significance test, donor contrast or cell-type proportion estimate is performed.", "",
              "## Complete fixed-panel results", "",
              "Each table describes one archive record. Detection cells are detected barcode counts followed by their percentage of that table's "
              "screen denominator. Abundance columns are mean ln(1 + deposited-entry cp10k). The screen results are a sensitivity check on "
              "these supplied values, not proof that retained barcodes are validated cells. Table order follows the frozen panel."]
    lookup = {(row["geo_sample"], row["screen"], row["gene_symbol"]): row for row in rows}
    symbols = panel["bulk_existing"] + [gene for item in panel["control_contexts"] for gene in item["symbols"]]
    for sample in sample_summaries:
        accession = sample["geo_sample"]
        counts = sample["screen_accounting"]
        lines += ["", f"### {accession} — source label {sample['stage_label_from_source_fields']}", "",
                  f"Denominators: all {counts['all_barcodes']:,}; sensitivity {counts['source_rule_sensitivity_retained']:,}.", "",
                  "| Symbol | Detected all | Detected sensitivity | Mean ln all | Mean ln sensitivity |",
                  "| --- | ---: | ---: | ---: | ---: |"]
        for symbol in symbols:
            all_row, screened_row = [lookup[accession, screen, symbol] for screen in SCREENS]
            def detection(row):
                return (f"{row['detected_barcodes']:,} ({row['detection_fraction'] * 100:.2f}%)"
                        if row["detection_fraction"] is not None else row["feature_status"])
            def abundance(row):
                return f"{row['mean_log1p_entry_cp10k']:.4f}" if row["mean_log1p_entry_cp10k"] is not None else "undefined"
            lines.append(f"| {symbol} | {detection(all_row)} | {detection(screened_row)} | {abundance(all_row)} | {abundance(screened_row)} |")
    lines += ["", "## Interpretation and reproducibility", "",
              "POSTN, collagen and proteoglycan expression supports inspecting matrix-associated patterns in the native tissue mixtures. "
              "The endothelial-, immune- and perivascular-associated control genes also have detectable expression. Detection of a control gene "
              "does not identify a cell type or establish whether different markers occur in the same cells. The full tables preserve the low and zero markers.", "",
              "Sparse SCX/TNMD detection in these tissue mixtures means that a universal identity or maturity cutoff cannot be inferred from their low "
              "bulk expression alone. Cell-state mixture, capture sensitivity, assay differences and unresolved preprocessing must be considered "
              "before comparison with cultured iPS-PDL. No single-cell cp10k value is treated as equivalent to bulk gene-summed TPM, "
              "and this analysis generates no cross-assay identity score.", "",
              "The next useful test is a separately frozen within-record coexpression exploration that checks which matrix-associated markers occur "
              "together and which control contexts accompany them, retaining ambiguous/dropout cases. It would remain descriptive until sample "
              "construction and donor mapping are resolved.", "",
              "Run from the repository root with Docker:", "", "```powershell",
              "$nativeAnalysisRevision = git rev-parse HEAD",
              "docker compose exec workbench python /lab/workbench/studies/dental-regeneration-2026-10-09/summarize_native_pdls_markers.py --code-revision $nativeAnalysisRevision",
              "```", "",
              "Local generated artifacts remain ignored under `data/structures/pdls-maturity/summary/`: "
              "`native_marker_summary.tsv` (180 rows), `native_barcode_screen.tsv` (25,762 rows), "
              "`native_marker_contexts.png`, the exact panel copy and `summary.json`. "
              "The figure uses separate color scales for detection and abundance, with missing/ambiguous values shown as gray. "
              "The computational receipt binds the script, frozen panel, source audit, upstream matrix audit, six input hashes and output hashes; "
              "its `regen.record` provenance receipt remains in ignored `data/provenance/`.", "",
              f"- Panel SHA-256: `{binding['panel_sha256']}`.",
              f"- Analysis script SHA-256: `{binding['analysis_script_sha256']}`.",
              f"- Matrix audit SHA-256: `{binding['matrix_audit_sha256']}`.",
              f"- Source linkage audit SHA-256: `{binding['source_linkage_audit_sha256']}`.",
              f"- Checkout revision at run: `{binding['code_revision_at_run']}`; the script hash binds the analysis code pending commit.", "",
              "Focused numerical and input-integrity tests cover threshold boundaries, overlapping exclusions, protein-count denominators, "
              "missing/ambiguous/zero distinctions, empty subsets and changed input/panel rejection. These are software checks rather than biological validation.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=HERE / "pdls_maturity_matrix_receipt.json")
    parser.add_argument("--panel", type=Path, default=HERE / "native_marker_panel.json")
    parser.add_argument("--data-root", type=Path, default=regen.DATA)
    parser.add_argument("--out-dir", type=Path, default=regen.DATA / "structures" / "pdls-maturity" / "summary")
    parser.add_argument("--report", type=Path, default=HERE / "PDLSC_NATIVE_MARKER_SCREEN.md")
    parser.add_argument("--code-revision", default=None, help="Source checkout revision at execution; script hash binds uncommitted analysis code")
    args = parser.parse_args()
    import numpy as np
    import scipy
    from scipy.io import mmread

    panel, symbols, contexts = load_panel(args.panel)
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    if (audit["schema_version"] != 1 or audit["accession"] != ACCESSION or len(audit["samples"]) != 2
            or not audit["qualification"]["descriptive_sparse_matrix_loading_eligible"]):
        raise ValueError("A passed two-record GSE306722 matrix audit is required")
    if len({item["geo_sample"] for item in audit["samples"]}) != 2:
        raise ValueError("Distinct GEO record identifiers required")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    marker_rows, cell_rows, sample_summaries = [], [], []
    bound_inputs = []
    for sample in audit["samples"]:
        if not sample["matrix"]["structural_quality_passed"] or not sample["matrix"]["nonnegative_integer_numeric_form"]:
            raise ValueError("Count-compatible numeric form is required; raw UMI lineage is still unresolved")
        paths = {kind: verified_path(args.data_root, sample["files"][kind]) for kind in ("features", "barcodes", "matrix")}
        features = load_labels(paths["features"], "features")
        barcodes = load_labels(paths["barcodes"], "barcodes")
        with gzip.open(paths["matrix"], "rb") as handle:
            matrix = mmread(handle).tocsr()
        if sample["matrix"]["orientation_from_label_dimensions"] == "barcodes_by_features":
            matrix = matrix.T.tocsr()
        if matrix.shape != (len(features), len(barcodes)):
            raise ValueError("Audited matrix does not match label dimensions")
        metrics = cell_metrics(matrix, features)
        marker_rows.extend(marker_metrics(matrix, features, symbols, contexts, metrics,
                                          sample["geo_sample"], sample["stage_label_from_source_fields"]))
        for index, barcode in enumerate(barcodes):
            cell_rows.append({"archive_barcode_id": sample["geo_sample"] + ":" + barcode,
                              "geo_sample": sample["geo_sample"], "barcode": barcode,
                              "gene_expression_entry_total": float(metrics["total"][index]),
                              "detected_gene_expression_features": int(metrics["detected_features"][index]),
                              "mitochondrial_entry_fraction": float(metrics["mitochondrial_fraction"][index]) if np.isfinite(metrics["mitochondrial_fraction"][index]) else None,
                              "passes_source_rule_sensitivity": bool(metrics["passes_sensitivity_screen"][index])})
        summary = {"geo_sample": sample["geo_sample"], "stage_label_from_source_fields": sample["stage_label_from_source_fields"],
                   "feature_type_distribution": dict(Counter(item["type"] for item in features)),
                   "screen_accounting": summarize_screen(metrics),
                   "marker_feature_status": dict(Counter(row["feature_status"] for row in marker_rows
                                                         if row["geo_sample"] == sample["geo_sample"] and row["screen"] == "all_barcodes"))}
        sample_summaries.append(summary)
        bound_inputs.append({"geo_sample": sample["geo_sample"], "files_sha256": {kind: sample["files"][kind]["sha256"] for kind in paths}})
        print(json.dumps(summary), flush=True)
        del matrix, metrics

    marker_path, cell_path = args.out_dir / "native_marker_summary.tsv", args.out_dir / "native_barcode_screen.tsv"
    figure_path, panel_path = args.out_dir / "native_marker_contexts.png", args.out_dir / "native_marker_panel.json"
    write_tsv(marker_path, marker_rows)
    write_tsv(cell_path, cell_rows)
    panel_path.write_bytes(args.panel.read_bytes())
    plot_markers(marker_rows, symbols, figure_path)
    source_doc = HERE / "PDLSC_SOURCE_LINKAGE_AUDIT.md"
    binding = {"matrix_audit_sha256": digest(args.audit), "panel_sha256": digest(args.panel),
               "analysis_script_sha256": digest(Path(__file__)), "source_linkage_audit_sha256": digest(source_doc),
               "code_revision_at_run": args.code_revision, "inputs": bound_inputs}
    run_utc = regen.now()
    write_report(args.report, marker_rows, sample_summaries, binding, panel, run_utc)
    outputs = [marker_path, cell_path, figure_path, panel_path, args.report]
    provenance = regen.record("dental-pdls-native-marker-summary", {
        "accession": ACCESSION, "binding": binding,
        "normalization": "ln(1 + 10000 * feature deposited entry / barcode total Gene Expression entries)",
        "scope": "Descriptive within archive records; no raw UMI lineage qualification, independent-donor contrast or cell-type annotation.",
    }, outputs)
    receipt = {"schema_version": 1, "accession": ACCESSION, "run_utc": run_utc,
               "binding": binding, "software": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
               "panel_id": panel["panel_id"], "panel_symbols_in_order": symbols,
               "samples": sample_summaries, "screens": list(SCREENS),
               "local_provenance_receipt": provenance.name,
               "normalization": {"base": "natural logarithm", "formula": "ln(1 + 10000 * feature entry / barcode Gene Expression entry sum)",
                                 "detected": "deposited entry > 0", "prevalence_denominator": "all selected barcodes",
                                 "abundance_denominator": "selected barcodes with positive Gene Expression entry total",
                                 "zero_total_abundance": "undefined; not converted to zero",
                                 "missing_or_ambiguous_feature_abundance": "undefined; not converted to zero",
                                 "numeric_zero": "present uniquely mapped feature with zero entries remains measured zero"},
               "raw_umi_preprocessing_lineage_qualified": False,
               "independent_donor_inference_eligible": False, "cell_type_annotations_assigned": False,
               "source_rule_screen_is_doublet_detection": False,
               "outputs": [{"filename": path.name, "sha256": digest(path), "bytes": path.stat().st_size} for path in outputs]}
    (args.out_dir / "summary.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(args.out_dir), "panel_symbols": len(symbols), "marker_rows": len(marker_rows), "barcode_rows": len(cell_rows)}), flush=True)


if __name__ == "__main__":
    main()
