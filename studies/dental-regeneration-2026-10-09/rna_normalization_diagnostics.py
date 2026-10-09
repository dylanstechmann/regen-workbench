"""Study-specific normalization and library diagnostics; no differential testing."""

import argparse
import csv
import gzip
import importlib.metadata
import io
import json
import sys
from pathlib import Path

import analyze_ameloblast_counts as intake
import numpy as np
import pandas as pd
from pydeseq2.dds import DeseqDataSet

sys.path.insert(0, str(intake.ROOT / "tools"))
import regen
from regen_compute import report_directory, write_json


def validate_factors(factors, n):
    values = np.asarray(factors, dtype=float)
    if values.shape != (n,) or not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Normalization factors must be finite, positive and sample-aligned")
    return values


def normalize(counts):
    # Fit only library size factors: do not fit dispersions/LFCs or perform tests.
    if not (counts > 0).all(axis=0).any():
        raise ValueError("No genes positive in all libraries for ratio normalization; iterative fallback is excluded")
    samples = [row[0] for row in intake.LABELS]
    metadata = pd.DataFrame({"condition": [row[2] for row in intake.LABELS]}, index=samples)
    dds = DeseqDataSet(counts=counts, metadata=metadata, design="~condition", n_cpus=1, quiet=True)
    dds.fit_size_factors(fit_type="ratio")
    ratio = validate_factors(dds.obs["size_factors"].to_numpy(), len(samples))
    totals = counts.sum(axis=1).to_numpy(dtype=float)
    # Put both normalizations on a common typical-library scale so the same
    # pseudocount has comparable units. Keep the absolute factors in the report.
    cpm_factor = validate_factors(totals / np.exp(np.mean(np.log(totals))), len(samples))
    ratio = ratio / np.exp(np.mean(np.log(ratio)))
    return {"total_count": counts.to_numpy(dtype=float) / cpm_factor[:, None],
            "median_ratio": counts.to_numpy(dtype=float) / ratio[:, None]}, cpm_factor, ratio


def describe(normalized, genes):
    panel = []
    for gene in intake.PANEL:
        i = genes.index(gene)
        values = normalized[:, i]
        means = [float(np.mean(values[start:start + 2])) for start in (0, 2, 4)]
        effects = []
        for reference, comparison in ((0, 2), (2, 4)):
            a, b = values[reference:reference + 2], values[comparison:comparison + 2]
            # Same formula as the existing exploratory contrast, normalized-count
            # units, pseudocount=1. This is not a fitted negative-binomial LFC.
            effect = float(np.log2(np.mean(b) + 1) - np.log2(np.mean(a) + 1))
            loo = [float(np.log2(np.mean(b) + 1) - np.log2(v + 1)) for v in a]
            loo += [float(np.log2(v + 1) - np.log2(np.mean(a) + 1)) for v in b]
            effects.append({"log2_mean_ratio_pc1": effect, "leave_one_library_out_min": min(loo),
                            "leave_one_library_out_max": max(loo)})
        panel.append({"gene": gene, "library_normalized_counts": values.tolist(),
                      "group_means": means, "treatment_in_WT": effects[0], "genotype_under_treatment": effects[1]})
    # Predefined unsupervised feature rule, applied identically across methods.
    keep = (normalized > 0).all(axis=0)
    if not keep.any():
        raise ValueError("No genes positive in all libraries for the predefined PCA rule")
    logged = np.log2(normalized[:, keep] + 1)
    centered = logged - logged.mean(axis=0)
    u, singular, _ = np.linalg.svd(centered, full_matrices=False)
    variance = singular**2
    fraction = variance / variance.sum() if variance.sum() > 0 else np.zeros_like(variance)
    scores = u[:, :2] * singular[:2]
    distance = np.linalg.norm(logged[:, None, :] - logged[None, :, :], axis=2) / np.sqrt(logged.shape[1])
    return {"panel": panel, "pca": {"feature_rule": "Gene count >0 in every library; log2(normalized count+1), gene-centered, not variance-scaled",
                                      "genes": int(keep.sum()), "scores": scores.tolist(), "variance_fraction": fraction[:2].tolist()},
            "pairwise_log_rms_distance": distance.tolist()}


def plots(report, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [row[0] for row in intake.LABELS]
    short_names = ["WT untreated 1", "WT untreated 2", "WT treated 1", "WT treated 2", "KO treated 1", "KO treated 2"]
    colors = ["#4477aa", "#4477aa", "#228833", "#228833", "#cc6677", "#cc6677"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), constrained_layout=True)
    for ax, (method, result) in zip(axes, report["methods"].items()):
        scores = np.asarray(result["pca"]["scores"])
        for i, name in enumerate(short_names):
            ax.scatter(*scores[i], c=colors[i], s=60, marker="o" if i % 2 == 0 else "^")
            right = scores[i, 0] > 0
            ax.annotate(name, scores[i], fontsize=8, xytext=(-7 if right else 7, 12 if i % 2 == 0 else -15),
                        ha="right" if right else "left", textcoords="offset points")
        ax.margins(0.16)
        variance = result["pca"]["variance_fraction"]
        ax.set(xlabel=f"PC1 ({variance[0]:.1%})", ylabel=f"PC2 ({variance[1]:.1%})", title=method.replace("_", " "))
        ax.grid(alpha=0.15)
    fig.suptitle("Deposited dental libraries: descriptive PCA\nSource-labeled replicates; clone/batch independence unresolved", fontsize=11)
    fig.savefig(out / "library_pca.svg")
    fig.savefig(out / "library_pca.png", dpi=140)
    plt.close(fig)
    panel = report["methods"]["median_ratio"]["panel"]
    values = np.log2(np.array([row["library_normalized_counts"] for row in panel]) + 1)
    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    im = ax.imshow(values, aspect="auto", cmap="viridis", vmin=0)
    ax.set_xticks(range(6), names, rotation=30, ha="right", fontsize=8)
    ax.set_yticks(range(len(panel)), [row["gene"] for row in panel])
    ax.set_title("Declared panel: log2(median-ratio normalized count + 1)\nAcross genes: counts also depend on transcript properties; no maturity score", fontsize=10)
    fig.colorbar(im, ax=ax, label="log2(normalized count + 1)")
    fig.savefig(out / "marker_panel.svg")
    fig.savefig(out / "marker_panel.png", dpi=140)
    plt.close(fig)
    for svg in out.glob("*.svg"):
        # Matplotlib path attributes span lines; retain line separators while
        # removing export whitespace before hashing and copying public figures.
        svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    raw = intake.RAW.read_bytes()
    receipt = json.loads((intake.STUDY / "count_receipt.json").read_text())
    if regen.sha256_file(intake.RAW) != receipt["response_sha256"]:
        raise ValueError("Count receipt mismatch")
    mpath = intake.ROOT / "data/literature/GSE307437-metadata-2026-10-09.soft.metadata.json"
    records = json.loads((intake.STUDY / "geo_metadata_receipt.json").read_text())["records"]
    expected = next(r for r in records if r["accession"] == "GSE307437")
    if regen.sha256_file(mpath) != expected["parsed_metadata_sha256"]:
        raise ValueError("Metadata receipt mismatch")
    intake.qualify_counts(raw, json.loads(mpath.read_text()))
    table = list(csv.reader(io.StringIO(gzip.decompress(raw).decode("utf-8-sig"))))
    genes = [row[0] for row in table[1:]]
    counts = pd.DataFrame(np.array([[int(v) for v in row[1:]] for row in table[1:]]).T,
                          index=[row[0] for row in intake.LABELS], columns=genes)
    normalized, total, ratio = normalize(counts)
    report = {"origin": "retrieved_source_library_diagnostics", "assisted_by": "AI",
              "count_sha256": receipt["response_sha256"], "metadata_sha256": expected["parsed_metadata_sha256"],
              "implementation_sha256": regen.sha256_file(Path(__file__)),
              "versions": {p: importlib.metadata.version(p) for p in ("pydeseq2", "numpy", "pandas", "matplotlib")},
              "samples": [row[0] for row in intake.LABELS], "groups": [row[2] for row in intake.LABELS],
              "normalization_factor_scale": "Each factor vector has geometric mean 1; factors use all six libraries",
              "total_count_factors": total.tolist(), "median_ratio_factors": ratio.tolist(),
              "normalization_only": True, "wald_tests_performed": False, "dispersion_model_fitted": False,
              "independent_biological_units_qualified": False,
              "methods": {method: describe(values, genes) for method, values in normalized.items()}}
    with report_directory(args.out):
        write_json(args.out / "normalization_diagnostics.json", report)
        plots(report, args.out)
        regen.record("dental-rna-normalization-diagnostics", {"count_sha256": receipt["response_sha256"],
                     "pydeseq2": report["versions"]["pydeseq2"], "normalization_only": True}, list(args.out.iterdir()))
    write_json(intake.STUDY / "normalization_diagnostics.json", report)
    for name in ("library_pca.svg", "marker_panel.svg"):
        (intake.STUDY / name).write_bytes((args.out / name).read_bytes())
    print(json.dumps({"diagnostic_libraries": 6, "methods": list(normalized), "wald_tests_performed": False}))


if __name__ == "__main__":
    main()
