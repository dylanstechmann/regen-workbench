"""Create descriptive gene-level tables and plots from the exploratory Salmon runs."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
MARKERS = [
    "POSTN", "COL1A1", "COL1A2", "COL3A1", "COL12A1", "COL14A1", "ASPN",
    "SCX", "TNMD", "MKX", "CILP", "DCN", "LUM", "BGN", "THY1", "PDGFRA",
    "ITGA11", "VCAM1", "FAP", "ALPL", "RUNX2", "SP7", "IBSP", "BGLAP",
    "POU5F1", "SOX2", "NANOG", "LIN28A", "AMELX", "ENAM", "AMBN", "DSPP",
    "MMP20",
]
ATTRIBUTE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*) "([^"]+)"')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--gtf", type=Path, required=True)
    parser.add_argument("--quant-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def gene_symbols(gtf: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    opener = gzip.open if gtf.suffix == ".gz" else open
    with opener(gtf, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9 or fields[2] != "gene":
                continue
            attrs = dict(ATTRIBUTE.findall(fields[8]))
            gene_id, symbol = attrs.get("gene_id"), attrs.get("gene_name")
            if gene_id and symbol:
                result[gene_id.split(".", 1)[0]] = symbol
    return result


def read_gene_tpm(path: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"Name", "TPM"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"{path} lacks required columns {sorted(required)}")
        for row in reader:
            fields = row["Name"].split("|")
            if len(fields) < 2 or not fields[1].startswith("ENSG"):
                continue
            gene_id = fields[1].split(".", 1)[0]
            values[gene_id] = values.get(gene_id, 0.0) + float(row["TPM"])
    return values


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with args.manifest.open(encoding="utf-8", newline="") as handle:
        samples = [row for row in csv.DictReader(handle, delimiter="\t")]
    genes_to_symbol = gene_symbols(args.gtf)

    missing: list[str] = []
    quantified: list[dict[str, object]] = []
    mapping_rows: list[dict[str, object]] = []
    for sample in samples:
        quant_dir = args.quant_dir / sample["run"]
        quant = quant_dir / "quant.sf"
        if not quant.is_file():
            missing.append(sample["run"])
            continue
        meta_path = quant_dir / "aux_info" / "meta_info.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        mapping = {
            "num_processed": meta.get("num_processed"),
            "num_mapped": meta.get("num_mapped"),
            "percent_mapped": meta.get("percent_mapped"),
            "detected_library_type": meta.get("detected_library_type"),
        }
        quantified.append({
            "run": sample["run"],
            "sample": sample["sample_name"],
            "group": sample["group"],
            "values": read_gene_tpm(quant),
            "mapping": mapping,
        })
        mapping_rows.append({"run": sample["run"], "sample": sample["sample_name"],
                             "group": sample["group"], **mapping})
    if not quantified:
        raise SystemExit("No quant.sf files found; complete Salmon quantification first.")

    gene_ids = sorted(set().union(*(set(sample["values"]) for sample in quantified)))
    matrix = pd.DataFrame(
        {sample["sample"]: [sample["values"].get(gene_id, 0.0) for gene_id in gene_ids]
         for sample in quantified},
        index=gene_ids,
    )
    matrix.index.name = "gene_id"
    matrix.insert(0, "gene_symbol", [genes_to_symbol.get(gene_id, "") for gene_id in matrix.index])
    matrix.to_csv(args.out_dir / "ipspdl_gene_tpm.tsv", sep="\t")

    symbol_to_ids: dict[str, list[str]] = defaultdict(list)
    for gene_id, symbol in genes_to_symbol.items():
        if symbol:
            symbol_to_ids[symbol].append(gene_id)

    long_rows = []
    for symbol in MARKERS:
        ids = symbol_to_ids.get(symbol, [])
        for sample in quantified:
            tpm = sum(float(sample["values"].get(gene_id, 0.0)) for gene_id in ids)
            long_rows.append({"gene_symbol": symbol, "sample": sample["sample"],
                              "group": sample["group"], "TPM": tpm})
    marker_frame = pd.DataFrame(long_rows)
    marker_frame.to_csv(args.out_dir / "ipspdl_marker_panel.tsv", sep="\t", index=False)
    medians = (marker_frame.groupby(["gene_symbol", "group"], sort=False)["TPM"]
               .agg(median="median", minimum="min", maximum="max", n="count")
               .reset_index())
    medians.to_csv(args.out_dir / "ipspdl_marker_group_summary.tsv", sep="\t", index=False)

    mapping_frame = pd.DataFrame(mapping_rows)
    mapping_frame.to_csv(args.out_dir / "ipspdl_mapping_by_sample.tsv", sep="\t", index=False)
    mapping_summary = []
    if not mapping_frame.empty and mapping_frame["percent_mapped"].notna().any():
        grouped_mapping = (mapping_frame.dropna(subset=["percent_mapped"])
                           .groupby("group", sort=False)["percent_mapped"]
                           .agg(median="median", minimum="min", maximum="max", n="count")
                           .reset_index())
        mapping_summary = [
            {"group": str(row.group), "median": float(row.median),
             "minimum": float(row.minimum), "maximum": float(row.maximum), "n": int(row.n)}
            for row in grouped_mapping.itertuples(index=False)
        ]

    # A descriptive PCA over the 2,000 most variable expressed genes; no group model is fit.
    tpm = matrix.drop(columns="gene_symbol").astype(float)
    logged = np.log2(tpm + 1.0)
    expressed = logged.loc[tpm.max(axis=1) >= 1.0]
    if len(expressed) >= 2 and len(quantified) >= 3:
        variance = expressed.var(axis=1, ddof=0).sort_values(ascending=False)
        selected = expressed.loc[variance.head(min(2000, len(variance))).index]
        centered = selected.subtract(selected.mean(axis=1), axis=0)
        _, singular, vt = np.linalg.svd(centered.to_numpy(), full_matrices=False)
        coords = vt[:2, :].T * singular[:2]
        explained = singular[:2] ** 2 / np.sum(singular ** 2)
        pca_rows = []
        for sample, point in zip(quantified, coords, strict=True):
            pca_rows.append({"run": sample["run"], "sample": sample["sample"],
                             "group": sample["group"], "PC1": point[0], "PC2": point[1]})
        pca_frame = pd.DataFrame(pca_rows)
        pca_frame.to_csv(args.out_dir / "ipspdl_pca.tsv", sep="\t", index=False)
        fig, ax = plt.subplots(figsize=(8, 6))
        for group, points in pca_frame.groupby("group", sort=False):
            ax.scatter(points["PC1"], points["PC2"], s=55, label=group)
            for row in points.itertuples():
                ax.annotate(row.sample, (row.PC1, row.PC2), xytext=(4, 4),
                            textcoords="offset points", fontsize=8)
        ax.set_xlabel(f"PC1 ({explained[0] * 100:.1f}% of selected-gene variance)")
        ax.set_ylabel(f"PC2 ({explained[1] * 100:.1f}% of selected-gene variance)")
        ax.set_title("Exploratory PCA of log2(gene TPM + 1)")
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(args.out_dir / "ipspdl_pca.png", dpi=180)
        plt.close(fig)
    else:
        explained = np.array([])

    receipt = {
        "project": "PRJDB39888",
        "quantified_runs": [sample["run"] for sample in quantified],
        "missing_runs": missing,
        "quantified_sample_count": len(quantified),
        "gene_ids_in_matrix": len(gene_ids),
        "mapping_rate_percent_by_group": mapping_summary,
        "mapping_by_run": mapping_rows,
        "marker_panel_symbols": MARKERS,
        "pca": {
            "method": "centered log2(TPM+1), top 2000 most variable expressed genes, descriptive SVD",
            "explained_variance_pc1_pc2": [float(value) for value in explained],
        } if len(explained) else None,
        "gene_TPM_method": "sum transcript TPM by the GENCODE gene identifier in each FASTA header; descriptive only; no tximport length-offset model",
        "interpretation": "descriptive only; sample-line and differentiation-batch nesting are unresolved",
    }
    (args.out_dir / "summary.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
