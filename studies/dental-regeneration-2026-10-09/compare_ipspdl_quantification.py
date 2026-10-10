"""Compare two completed Salmon estimates of the same iPS-PDL libraries.

This is a descriptive reference sensitivity analysis, not differential expression.
Inputs and both reference receipts are hash-linked; raw reads and outputs stay local.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.metadata
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path


MARKERS = [
    "POSTN", "COL1A1", "COL1A2", "COL3A1", "COL12A1", "COL14A1", "ASPN",
    "SCX", "TNMD", "MKX", "CILP", "DCN", "LUM", "BGN", "THY1", "PDGFRA",
    "ITGA11", "VCAM1", "FAP", "ALPL", "RUNX2", "SP7", "IBSP", "BGLAP",
    "POU5F1", "SOX2", "NANOG", "LIN28A", "AMELX", "ENAM", "AMBN", "DSPP",
    "MMP20",
]
ATTRIBUTE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*) "([^"]+)"')
METADATA_SETTINGS = (
    "salmon_version", "opt_type", "mapping_type", "seq_bias_correct",
    "gc_bias_correct", "pos_bias_correct", "keep_duplicates", "num_bootstraps",
    "inference_path", "range_factorization_bins", "seq_bias_context_length", "gc_bias_bins",
)
INDEX_HASHES = (
    "index_seq_hash", "index_name_hash", "index_seq_hash512", "index_name_hash512",
    "index_decoy_seq_hash", "index_decoy_name_hash",
)
MAPPING_FIELDS = (
    "num_processed", "num_mapped", "percent_mapped", "num_decoy_fragments",
    "num_orphan", "num_fragments_filtered_vm", "num_valid_targets", "num_decoy_targets",
    "detected_library_type", "em_converged", "num_em_iterations",
)
LIBRARY_FIELDS = (
    "expected_format", "compatible_fragment_ratio", "num_incompatible_fragments",
    "num_assigned_fragments", "strand_mapping_bias",
)
LIMITATIONS = [
    "Descriptive sensitivity of the same libraries to quantification references; no significance tests or independent validation.",
    "Gene TPM is a direct sum of transcript TPM by version-stripped GENCODE gene ID, without a tximport length-offset model.",
    "TPM is compositional: a reference-induced reassignment can alter other TPM values without a biological change.",
    "iPS-PDL products share one parental iPSC background; differentiation-source nesting and the run-to-conditioned-medium donor crosswalk remain unresolved.",
    "No assigned donor pairing between iPS-PDL and primary PDL. Pairing here only means the same run quantified twice.",
    "The paired-only sensitivity excludes DRR913336 when its layout is single/unspecified: primary PDL n becomes 2 versus 3 in each other label group. It removes a donor together with a layout, so it cannot isolate the layout effect.",
    "Expression profiles cannot establish native ligament identity, oriented insertion, force transfer, clinical benefit, or safety.",
    "Bulk counts/TPM are not pooled with native PDL single-cell expression matrices.",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path) -> dict:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def validate_reference_files(inputs: dict, receipts: dict) -> list[dict]:
    """Check explicit filename/hash entries without assuming a new receipt's schema."""
    checks = []
    for version, receipt in receipts.items():
        files = receipt["receipt"].get("files", [])
        for kind in ("transcripts", "gtf"):
            filename = Path(inputs[kind]["path"]).name
            matches = [item for item in files if isinstance(item, dict) and item.get("filename") == filename]
            if kind == "transcripts" and "transcript_sha256" in receipt["receipt"]:
                matches.append({"sha256": receipt["receipt"]["transcript_sha256"]})
            for item in matches:
                if item.get("sha256") != inputs[kind]["sha256"]:
                    raise ValueError(f"{version} reference receipt hash mismatch for {filename}")
                if "bytes" in item and item["bytes"] != inputs[kind]["bytes"]:
                    raise ValueError(f"{version} reference receipt size mismatch for {filename}")
            checks.append({"version": version, "input": kind, "explicit_filename_hash_entries_checked": len(matches)})
    return checks


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"run", "sample_name", "group", "layout"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Manifest lacks {sorted(required)}")
        samples = list(reader)
    if not samples:
        raise ValueError("Empty manifest")
    for key in ("run", "sample_name"):
        values = [sample[key] for sample in samples]
        if any(not value for value in values) or len(values) != len(set(values)):
            raise ValueError(f"Manifest has empty or duplicate {key}")
    if any(not sample["group"] or not sample["layout"] for sample in samples):
        raise ValueError("Manifest has empty group or layout")
    return samples


def validate_sample_directories(samples: list[dict], *roots: Path) -> None:
    expected = {sample["run"] for sample in samples}
    for root in roots:
        observed = {path.parent.name for path in root.glob("*/quant.sf")}
        if observed != expected:
            raise ValueError(f"Sample mismatch in {root}: missing={sorted(expected-observed)}, extra={sorted(observed-expected)}")


def target_hash(targets: dict[str, int]) -> str:
    digest = hashlib.sha256()
    for name in sorted(targets):
        digest.update(f"{name}\t{targets[name]}\n".encode("utf-8"))
    return digest.hexdigest()


def read_quant(path: Path, expected_targets: dict[str, int] | None = None) -> tuple[dict[str, float], dict[str, int]]:
    """Reject incomplete, duplicate, changed-length or changed-target quantifications."""
    values: dict[str, float] = defaultdict(float)
    targets: dict[str, int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not {"Name", "Length", "TPM"}.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing quantification columns in {path}")
        for row in reader:
            name = row["Name"]
            if name in targets:
                raise ValueError(f"Duplicate target in {path}: {name}")
            length, tpm = int(row["Length"]), float(row["TPM"])
            if length <= 0 or not math.isfinite(tpm) or tpm < 0:
                raise ValueError(f"Invalid length/TPM in {path}: {name}")
            if expected_targets is not None and expected_targets.get(name) != length:
                raise ValueError(f"Target name/length mismatch in {path}: {name}")
            targets[name] = length
            fields = name.split("|")
            if len(fields) < 2 or not fields[1].startswith("ENSG"):
                raise ValueError(f"Target lacks GENCODE gene ID in {path}: {name}")
            values[fields[1].split(".", 1)[0]] += tpm
    if not targets:
        raise ValueError(f"No targets in {path}")
    if expected_targets is not None and len(targets) != len(expected_targets):
        raise ValueError(f"Target count mismatch in {path}: {len(targets)} versus {len(expected_targets)}")
    return dict(values), targets


def gene_symbols(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9 or fields[2] != "gene":
                continue
            attrs = dict(ATTRIBUTE.findall(fields[8]))
            if attrs.get("gene_id") and attrs.get("gene_name"):
                result[attrs["gene_id"].split(".", 1)[0]] = attrs["gene_name"]
    return result


def read_metadata(quant_dir: Path) -> dict:
    files = {"command": quant_dir / "cmd_info.json", "metadata": quant_dir / "aux_info/meta_info.json",
             "library": quant_dir / "lib_format_counts.json"}
    result = {key: json.loads(path.read_text(encoding="utf-8")) for key, path in files.items()}
    meta = result["metadata"]
    if meta.get("meta_info_complete") is not True or meta.get("em_converged") is not True or meta.get("quant_errors") != []:
        raise ValueError(f"Incomplete/failed estimate in {quant_dir}")
    result["files"] = {key: file_record(path) for key, path in files.items()}
    result["quant_file"] = file_record(quant_dir / "quant.sf")
    return result


def read_identities(command: dict) -> dict[str, list[str]]:
    # Command paths may be mounted under different prefixes. Basenames plus processed
    # fragment counts are checked; input FASTQ identity still depends on the fetch receipt.
    return {key: [str(path).replace("\\", "/").rsplit("/", 1)[-1] for path in command.get(key, [])]
            for key in ("mates1", "mates2", "unmatedReads")}


def validate_run_pair(sample: dict, baseline: dict, candidate: dict) -> None:
    if baseline["metadata"].get("num_processed") != candidate["metadata"].get("num_processed"):
        raise ValueError(f"Processed-fragment mismatch for {sample['run']}")
    left, right = read_identities(baseline["command"]), read_identities(candidate["command"])
    if left != right:
        raise ValueError(f"Input-read mismatch for {sample['run']}: {left} versus {right}")
    paired = bool(left["mates1"] or left["mates2"])
    if paired != (sample["layout"] == "paired") or (paired and (not left["mates1"] or not left["mates2"])):
        raise ValueError(f"Command library layout disagrees with manifest for {sample['run']}")
    if not paired and not left["unmatedReads"]:
        raise ValueError(f"No input reads recorded for {sample['run']}")


def settings(metadata: dict) -> dict:
    command = {key: value for key, value in metadata["command"].items()
               if key not in {"index", "output", "mates1", "mates2", "unmatedReads", "threads"}}
    return {**{f"metadata.{key}": metadata["metadata"].get(key) for key in METADATA_SETTINGS},
            **{f"command.{key}": value for key, value in command.items()}}


def setting_changes(baseline: dict, candidate: dict) -> list[dict]:
    left, right = settings(baseline), settings(candidate)
    return [{"setting": key, "baseline": left.get(key), "candidate": right.get(key)}
            for key in sorted(set(left) | set(right)) if left.get(key) != right.get(key)]


def validate_index_consistency(metadata: dict) -> None:
    for version in ("baseline", "candidate"):
        keys = (*INDEX_HASHES, "num_decoy_targets")
        signatures = {tuple(pair[version]["metadata"].get(key) for key in keys) for pair in metadata.values()}
        if len(signatures) != 1:
            raise ValueError(f"Inconsistent {version} index hashes/decoy counts across runs")


def correlation(left, right, method: str = "pearson") -> float | None:
    import numpy as np
    import pandas as pd
    x, y = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if len(x) < 2 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    if method == "spearman":
        x, y = pd.Series(x).rank().to_numpy(), pd.Series(y).rank().to_numpy()
    return float(np.corrcoef(x, y)[0, 1])


def expression_agreement(left: dict[str, float], right: dict[str, float], minimum_tpm: float) -> dict:
    import numpy as np
    genes = sorted(set(left) | set(right))
    a = np.array([left.get(gene, 0.0) for gene in genes])
    b = np.array([right.get(gene, 0.0) for gene in genes])
    selected = np.maximum(a, b) >= minimum_tpm
    logged_a, logged_b = np.log2(a[selected] + 1.0), np.log2(b[selected] + 1.0)
    return {
        "all_gene_count": len(genes), "expressed_either_gene_count": int(selected.sum()),
        "excluded_below_threshold_gene_count": int((~selected).sum()), "minimum_gene_tpm": minimum_tpm,
        "expressed_both_gene_count": int(((a >= minimum_tpm) & (b >= minimum_tpm)).sum()),
        "baseline_only_expressed_gene_count": int(((a >= minimum_tpm) & (b < minimum_tpm)).sum()),
        "candidate_only_expressed_gene_count": int(((a < minimum_tpm) & (b >= minimum_tpm)).sum()),
        "pearson_log2_tpm_plus_1": correlation(logged_a, logged_b),
        "spearman_expressed_tpm": correlation(a[selected], b[selected], "spearman"),
        "median_absolute_log2_tpm_plus_1_change": float(np.median(np.abs(logged_b-logged_a))) if selected.any() else None,
        "maximum_absolute_log2_tpm_plus_1_change": float(np.max(np.abs(logged_b-logged_a))) if selected.any() else None,
    }


def largest_gene_changes(left: dict[str, float], right: dict[str, float], minimum_tpm: float, maximum_genes: int = 50) -> list[dict]:
    """Expose reference-sensitive outliers; this ranking is not a significance test."""
    rows = []
    for gene in sorted(set(left) | set(right)):
        baseline, candidate = left.get(gene, 0.0), right.get(gene, 0.0)
        if max(baseline, candidate) < minimum_tpm:
            continue
        change = math.log2((candidate+1.0)/(baseline+1.0))
        rows.append({"gene_id": gene, "baseline_TPM": baseline, "candidate_TPM": candidate,
                     "TPM_change": candidate-baseline, "log2_TPM_plus_1_change": change,
                     "absolute_log2_TPM_plus_1_change": abs(change)})
    return sorted(rows, key=lambda row: (-row["absolute_log2_TPM_plus_1_change"], row["gene_id"]))[:maximum_genes]


def marker_tables(samples: list[dict], matrices: dict, symbols: dict, markers: list[str]) -> tuple:
    import numpy as np
    by_symbol: dict[str, list[str]] = defaultdict(list)
    for gene, symbol in symbols.items():
        by_symbol[symbol].append(gene)
    rows, groups, patterns = [], [], []
    for marker in markers:
        ids = by_symbol.get(marker, [])
        for sample in samples:
            run = sample["run"]
            values = [sum(matrices[version][run].get(gene, 0.0) for gene in ids) for version in ("baseline", "candidate")]
            rows.append({"gene_symbol": marker, "gene_ids": ";".join(ids), "annotation_present": bool(ids),
                         "run": run, "sample": sample["sample_name"], "group": sample["group"], "layout": sample["layout"],
                         "baseline_TPM": values[0], "candidate_TPM": values[1], "TPM_change": values[1]-values[0],
                         "log2_TPM_plus_1_change": math.log2((values[1]+1)/(values[0]+1))})
        for scope, scoped_samples in (("all", samples), ("paired_only", [sample for sample in samples if sample["layout"] == "paired"])):
            scoped_runs = {sample["run"] for sample in scoped_samples}
            for group in dict.fromkeys(sample["group"] for sample in scoped_samples):
                subset = [row for row in rows if row["gene_symbol"] == marker and row["group"] == group and row["run"] in scoped_runs]
                result = {"scope": scope, "gene_symbol": marker, "group": group, "n": len(subset), "annotation_present": bool(ids)}
                for version in ("baseline", "candidate"):
                    values = [row[f"{version}_TPM"] for row in subset]
                    result.update({f"{version}_median_TPM": float(np.median(values)),
                                   f"{version}_minimum_TPM": min(values), f"{version}_maximum_TPM": max(values)})
                result["median_TPM_change"] = result["candidate_median_TPM"]-result["baseline_median_TPM"]
                result["median_log2_TPM_plus_1_change"] = math.log2((result["candidate_median_TPM"]+1)/(result["baseline_median_TPM"]+1))
                groups.append(result)
            summaries = [row for row in groups if row["scope"] == scope and row["gene_symbol"] == marker]
            for i, left in enumerate(summaries):
                for right in summaries[i+1:]:
                    baseline_delta = left["baseline_median_TPM"]-right["baseline_median_TPM"]
                    candidate_delta = left["candidate_median_TPM"]-right["candidate_median_TPM"]
                    sign = lambda value: 0 if abs(value) < 1e-9 else (1 if value > 0 else -1)
                    patterns.append({"scope": scope, "gene_symbol": marker, "group_left": left["group"], "group_right": right["group"],
                                     "n_left": left["n"], "n_right": right["n"], "baseline_median_delta_TPM": baseline_delta,
                                     "candidate_median_delta_TPM": candidate_delta, "median_order_retained": sign(baseline_delta) == sign(candidate_delta),
                                     "baseline_order": sign(baseline_delta), "candidate_order": sign(candidate_delta)})
    return rows, groups, patterns


def pca_fit(matrix, selected: list[str] | None = None, minimum_tpm: float = 1.0, maximum_genes: int = 2000) -> dict:
    import numpy as np
    if selected is None:
        expressed = matrix.loc[matrix.max(axis=1) >= minimum_tpm]
        variance = np.log2(expressed+1).var(axis=1, ddof=0)
        # The matrix index is sorted by gene ID; stable sorting makes ties reproducible.
        selected = list(variance[variance > 0].sort_values(ascending=False, kind="stable").head(maximum_genes).index)
    if len(selected) < 2 or matrix.shape[1] < 3:
        raise ValueError("PCA requires >=2 variable expressed genes and >=3 runs")
    logged = np.log2(matrix.loc[selected]+1)
    centered = logged.subtract(logged.mean(axis=1), axis=0)
    _, singular, vt = np.linalg.svd(centered.to_numpy(), full_matrices=False)
    if not np.sum(singular**2):
        raise ValueError("No selected-gene variance for PCA")
    coords = vt[:2].T*singular[:2]
    return {"genes": selected, "coordinates": coords, "explained": singular[:2]**2/np.sum(singular**2)}


def pca_agreement(baseline: dict, candidate: dict) -> tuple[dict, object]:
    import numpy as np
    a, b = baseline["coordinates"], candidate["coordinates"]
    # Orthogonal alignment accommodates arbitrary PCA signs/axis rotation, without rescaling.
    u, _, vt = np.linalg.svd(b.T@a)
    aligned = b@(u@vt)
    distances = lambda points: np.array([np.linalg.norm(points[i]-points[j]) for i in range(len(points)) for j in range(i+1, len(points))])
    left, right = distances(a), distances(b)
    shared = set(baseline["genes"]) & set(candidate["genes"])
    union = set(baseline["genes"]) | set(candidate["genes"])
    return {"baseline_selected_genes": len(baseline["genes"]), "candidate_selected_genes": len(candidate["genes"]),
            "selected_gene_overlap": len(shared), "selected_gene_jaccard": len(shared)/len(union),
            "orthogonal_alignment_relative_residual": float(np.linalg.norm(aligned-a)/np.linalg.norm(a)),
            "pairwise_distance_pearson": correlation(left, right), "pairwise_distance_spearman": correlation(left, right, "spearman"),
            "baseline_explained_variance_pc1_pc2": baseline["explained"].tolist(),
            "candidate_explained_variance_pc1_pc2": candidate["explained"].tolist()}, aligned


def write_tsv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def compute_pca(samples: list[dict], matrices: dict, out: Path, minimum_tpm: float, maximum_genes: int) -> dict:
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    genes = sorted(set().union(*(set(values) for version in matrices.values() for values in version.values())))
    summary = {}
    figure, axes = plt.subplots(2, 3, figsize=(16, 10))
    for row_index, (scope, subset) in enumerate((("all", samples), ("paired_only", [row for row in samples if row["layout"] == "paired"]))):
        runs = [row["run"] for row in subset]
        frames = {version: pd.DataFrame({run: [values[run].get(gene, 0.0) for gene in genes] for run in runs}, index=genes)
                  for version, values in matrices.items()}
        baseline = pca_fit(frames["baseline"], minimum_tpm=minimum_tpm, maximum_genes=maximum_genes)
        fixed = pca_fit(frames["candidate"], baseline["genes"])
        reselected = pca_fit(frames["candidate"], minimum_tpm=minimum_tpm, maximum_genes=maximum_genes)
        comparison_fixed, aligned_fixed = pca_agreement(baseline, fixed)
        comparison_reselected, aligned_reselected = pca_agreement(baseline, reselected)
        summary[scope] = {"runs": runs, "group_n": {group: sum(sample["group"] == group for sample in subset) for group in dict.fromkeys(sample["group"] for sample in subset)},
                          "fixed_baseline_genes": comparison_fixed, "independently_reselected_genes": comparison_reselected}
        for column_index, (name, result, aligned) in enumerate((("baseline", baseline, baseline["coordinates"]), ("candidate_fixed", fixed, aligned_fixed),
                                                               ("candidate_reselected", reselected, aligned_reselected))):
            write_tsv(out / f"pca_{scope}_{name}.tsv", [{"run": sample["run"], "sample": sample["sample_name"], "group": sample["group"],
                      "PC1": float(point[0]), "PC2": float(point[1]), "aligned_to_baseline_PC1": float(alignment[0]), "aligned_to_baseline_PC2": float(alignment[1])}
                      for sample, point, alignment in zip(subset, result["coordinates"], aligned, strict=True)])
            (out / f"pca_{scope}_{name}_genes.txt").write_text("\n".join(result["genes"])+"\n", encoding="utf-8")
            # PC signs are arbitrary. Match the display to the baseline within each
            # scope while preserving raw and orthogonally aligned exported coordinates.
            plot_coordinates = result["coordinates"].copy()
            for component in range(2):
                if np.dot(plot_coordinates[:, component], baseline["coordinates"][:, component]) < 0:
                    plot_coordinates[:, component] *= -1
            ax = axes[row_index, column_index]
            for group in dict.fromkeys(sample["group"] for sample in subset):
                indices = [i for i, sample in enumerate(subset) if sample["group"] == group]
                points = plot_coordinates[indices]
                ax.scatter(points[:, 0], points[:, 1], s=45, label=group)
                ordered = sorted(indices, key=lambda index: plot_coordinates[index, 1])
                for rank, index in enumerate(ordered):
                    point = plot_coordinates[index]
                    offset = 4+10*(rank-(len(ordered)-1)/2)
                    ax.annotate(subset[index]["sample_name"], point, xytext=(5, offset),
                                textcoords="offset points", fontsize=7,
                                arrowprops={"arrowstyle": "-", "lw": .4, "color": "0.6"})
            ax.margins(x=.15, y=.15)
            ax.set_title(f"{scope}: {name.replace('_', ' ')}")
            ax.set_xlabel(f"PC1 ({result['explained'][0]*100:.1f}% selected-gene variance)")
            ax.set_ylabel(f"PC2 ({result['explained'][1]*100:.1f}% selected-gene variance)")
            ax.legend(frameon=False, fontsize=8)
    figure.suptitle("Descriptive reference sensitivity: log2(gene TPM + 1)\nDisplayed PC signs matched to baseline within each sample scope")
    figure.tight_layout()
    figure.savefig(out / "pca_reference_sensitivity.png", dpi=180)
    plt.close(figure)
    return summary


def compare(args: argparse.Namespace) -> dict:
    script_record = file_record(Path(__file__).resolve())
    samples = load_manifest(args.manifest)
    validate_sample_directories(samples, args.baseline_dir, args.candidate_dir)
    matrices = {"baseline": {}, "candidate": {}}
    inputs = {"manifest": file_record(args.manifest), "gtf": file_record(args.gtf), "transcripts": file_record(args.transcripts)}
    receipts = {}
    for version in matrices:
        receipt_path = getattr(args, f"{version}_reference_manifest")
        receipts[version] = {"file": file_record(receipt_path), "receipt": json.loads(receipt_path.read_text(encoding="utf-8"))}
    receipt_checks = validate_reference_files(inputs, receipts)
    metadata, mapping_rows, changes, agreements = {}, [], [], []
    targets = None
    expected_target_hash = None
    for sample in samples:
        run = sample["run"]
        pair = {}
        for version in matrices:
            root = getattr(args, f"{version}_dir")/run
            values, observed = read_quant(root/"quant.sf", targets)
            if targets is None:
                targets = observed
                expected_target_hash = target_hash(targets)
            pair[version] = read_metadata(root)
            if pair[version]["metadata"].get("num_valid_targets") != len(observed):
                raise ValueError(f"Metadata target count disagrees with quant.sf in {root}")
            matrices[version][run] = values
        validate_run_pair(sample, pair["baseline"], pair["candidate"])
        metadata[run] = pair
        for change in setting_changes(pair["baseline"], pair["candidate"]):
            changes.append({"run": run, **change})
        mapping = {"run": run, "sample": sample["sample_name"], "group": sample["group"], "layout": sample["layout"]}
        for version, record in pair.items():
            mapping.update({f"{version}_{key}": record["metadata"].get(key) for key in MAPPING_FIELDS})
            mapping.update({f"{version}_{key}": record["library"].get(key) for key in LIBRARY_FIELDS})
            mapping[f"{version}_diagnostic_codes"] = ";".join(item.get("code", "") for item in record["metadata"].get("diagnostics", []))
        mapping["mapping_rate_change_percentage_points"] = mapping["candidate_percent_mapped"]-mapping["baseline_percent_mapped"]
        mapping["detected_library_type_changed"] = mapping["candidate_detected_library_type"] != mapping["baseline_detected_library_type"]
        mapping_rows.append(mapping)
        agreements.append({"run": run, "sample": sample["sample_name"], "group": sample["group"],
                           **expression_agreement(matrices["baseline"][run], matrices["candidate"][run], args.minimum_tpm)})
    # Validate every input before writing results; a partial run must not look complete.
    validate_index_consistency(metadata)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    symbols = gene_symbols(args.gtf)
    import pandas as pd
    gene_ids = sorted(set().union(*(set(values) for version in matrices.values() for values in version.values())))
    for version, values in matrices.items():
        table = pd.DataFrame({sample["run"]: [values[sample["run"]].get(gene, 0.0) for gene in gene_ids] for sample in samples}, index=gene_ids)
        table.index.name = "gene_id"
        table.insert(0, "gene_symbol", [symbols.get(gene, "") for gene in gene_ids])
        table.to_csv(args.out_dir/f"gene_TPM_{version}.tsv", sep="\t")
    change_rows = [{"run": sample["run"], "sample": sample["sample_name"], "group": sample["group"],
                    "gene_symbol": symbols.get(row["gene_id"], ""), **row}
                   for sample in samples for row in largest_gene_changes(matrices["baseline"][sample["run"]], matrices["candidate"][sample["run"]], args.minimum_tpm)]
    write_tsv(args.out_dir/"largest_gene_tpm_changes.tsv", change_rows)
    markers, groups, patterns = marker_tables(samples, matrices, symbols, MARKERS)
    write_tsv(args.out_dir/"marker_by_sample.tsv", markers)
    write_tsv(args.out_dir/"marker_group_summary.tsv", groups)
    write_tsv(args.out_dir/"marker_group_order_sensitivity.tsv", patterns)
    write_tsv(args.out_dir/"mapping_sensitivity.tsv", mapping_rows)
    import numpy as np
    mapping_groups = []
    for scope, subset in (("all", samples), ("paired_only", [sample for sample in samples if sample["layout"] == "paired"])):
        scoped_runs = {sample["run"] for sample in subset}
        for group in dict.fromkeys(sample["group"] for sample in subset):
            rows = [row for row in mapping_rows if row["run"] in scoped_runs and row["group"] == group]
            item = {"scope": scope, "group": group, "n": len(rows)}
            for version in ("baseline", "candidate"):
                rates = [row[f"{version}_percent_mapped"] for row in rows]
                item.update({f"{version}_median_percent_mapped": float(np.median(rates)),
                             f"{version}_minimum_percent_mapped": min(rates), f"{version}_maximum_percent_mapped": max(rates)})
            item["median_mapping_rate_change_percentage_points"] = item["candidate_median_percent_mapped"]-item["baseline_median_percent_mapped"]
            mapping_groups.append(item)
    write_tsv(args.out_dir/"mapping_group_summary.tsv", mapping_groups)
    write_tsv(args.out_dir/"expression_agreement.tsv", agreements)
    pca = compute_pca(samples, matrices, args.out_dir, args.minimum_tpm, args.pca_maximum_genes)
    for version, receipt in receipts.items():
        (args.out_dir/f"{version}_reference_manifest.json").write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    (args.out_dir/"quantification_inputs.json").write_text(json.dumps(metadata, indent=2)+"\n", encoding="utf-8")
    result = {
        "project": "PRJDB39888", "analysis": "descriptive within-run reference sensitivity", "inputs": inputs,
        "reference_manifests": {version: receipt["file"] for version, receipt in receipts.items()},
        "reference_receipt_file_checks": receipt_checks,
        "target_validation": {"identical_names_and_lengths_in_every_quant_sf": True, "target_count": len(targets),
                              "canonical_name_length_sha256": expected_target_hash},
        "runs": [sample["run"] for sample in samples], "mapping_by_run": mapping_rows,
        "mapping_by_group_and_scope": mapping_groups,
        "quantification_setting_changes": changes,
        "index_hashes_by_run": {run: {version: {key: item["metadata"].get(key) for key in INDEX_HASHES} for version, item in pair.items()} for run, pair in metadata.items()},
        "index_hash_changes_by_run": {run: [key for key in INDEX_HASHES if pair["baseline"]["metadata"].get(key) != pair["candidate"]["metadata"].get(key)] for run, pair in metadata.items()},
        "expression_agreement": agreements,
        "largest_gene_change_table": {"filename": "largest_gene_tpm_changes.tsv", "maximum_genes_per_run": 50,
                                      "ranking": "absolute log2(TPM+1) change among genes expressed in either estimate; descriptive, not significance", "rows": len(change_rows)},
        "correlation_method": f"Per-run genes with TPM >= {args.minimum_tpm:g} in either estimate; Pearson on log2(TPM+1), Spearman on TPM. Common low/zero genes are excluded.",
        "markers_missing_from_annotation": [marker for marker in MARKERS if marker not in set(symbols.values())],
        "marker_group_order_changes": [row for row in patterns if not row["median_order_retained"]],
        "pca": pca, "pca_method": f"Centered log2(TPM+1); <= {args.pca_maximum_genes} variable genes with maximum TPM >= {args.minimum_tpm:g}; baseline-selected fixed features and independently reselected features; PC signs/rotation aligned without scaling for residuals.",
        "limitations": LIMITATIONS,
        "additional_provenance_limit": "Read basenames and processed-fragment totals match between runs. This checks the command record, not FASTQ bytes; retain the existing raw-read hash receipt.",
        "generated_with": {"script": script_record, "python": sys.version,
                           "packages": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "matplotlib")}},
    }
    (args.out_dir/"summary.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    report = ["# iPS-PDL quantification reference sensitivity", "", "Agent-run, descriptive comparison of the same archived libraries. Refer to the hash-linked summary and tables for settings and run-level values.", "",
              f"All {len(samples)} runs passed sample, target name/length, input-read basename, processed-fragment, completed-estimate and convergence checks. Each quant.sf contains {len(targets):,} targets.", "",
              f"Other quantification-setting changes: {len(changes)} run-setting entries. Detected library-type changes: {sum(row['detected_library_type_changed'] for row in mapping_rows)} runs.", "",
              "| Scope | Fixed-gene PCA distance Pearson | Reselected-gene overlap | Reselected PCA distance Pearson |", "|---|---:|---:|---:|"]
    fmt = lambda value: "undefined" if value is None else f"{value:.6f}"
    for scope, values in pca.items():
        report.append(f"| {scope} | {fmt(values['fixed_baseline_genes']['pairwise_distance_pearson'])} | {values['independently_reselected_genes']['selected_gene_overlap']} | {fmt(values['independently_reselected_genes']['pairwise_distance_pearson'])} |")
    report.extend(["", f"Marker group median orders changed in {len(result['marker_group_order_changes'])} of {len(patterns)} marker/group-pair/scope comparisons. Low-expression order changes are retained in the table and do not imply biological reversal.", "", "## Limits", ""])
    report.extend(f"- {limitation}" for limitation in LIMITATIONS)
    (args.out_dir/"SENSITIVITY_REPORT.md").write_text("\n".join(report)+"\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("manifest", "gtf", "transcripts", "baseline-dir", "candidate-dir", "baseline-reference-manifest", "candidate-reference-manifest", "out-dir"):
        parser.add_argument(f"--{flag}", type=Path, required=True)
    parser.add_argument("--minimum-tpm", type=float, default=1.0)
    parser.add_argument("--pca-maximum-genes", type=int, default=2000)
    args = parser.parse_args()
    if not math.isfinite(args.minimum_tpm) or args.minimum_tpm <= 0 or args.pca_maximum_genes < 2:
        parser.error("minimum TPM must be finite and >0; PCA maximum genes must be >=2")
    return args


if __name__ == "__main__":
    output = compare(parse_args())
    print(json.dumps({"runs": len(output["runs"]), "targets": output["target_validation"]["target_count"],
                      "setting_change_entries": len(output["quantification_setting_changes"]),
                      "marker_order_changes": len(output["marker_group_order_changes"]), "pca": output["pca"]}, indent=2))
