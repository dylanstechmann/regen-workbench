"""Descriptively compare matched GSE165177 fibroblast states by donor and day.

Input values are GEO's processed log2 RPM tables. This is a targeted, paired
re-analysis of four collagen genes highlighted in the source paper; it is not
an age-clock reconstruction or an estimate of organismal rejuvenation.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
import re
import statistics
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import regen

ACCESSION = "GSE165177"
CACHE = regen.DATA / "literature" / "aging-reprogramming-GSE165177"
INTAKE_RECEIPT = HERE / "geo_intake_receipt.json"
GENES = ("COL1A1", "COL1A2", "COL4A1", "COL4A2")
GROUP_COMPARISONS = (
    ("endpoint_after_withdrawal", "successful_endpoint", "negative_endpoint"),
    ("endpoint_after_withdrawal", "failed_endpoint", "negative_endpoint"),
    ("endpoint_after_withdrawal", "successful_endpoint", "failed_endpoint"),
    ("during_induction_intermediate", "successful_intermediate", "negative_intermediate"),
    ("during_induction_intermediate", "failing_intermediate", "negative_intermediate"),
    ("during_induction_intermediate", "successful_intermediate", "failing_intermediate"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_tsv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty output: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sample_state(sample: dict, filename: str) -> dict:
    fields = sample["fields"]
    title = fields["Sample_title"][0]
    donor_match = re.match(r"^(O[123])_", title)
    donor = donor_match.group(1) if donor_match else ""
    age_match = re.search(r"donor age \(years\):\s*(\d+)", " ".join(fields.get("Sample_characteristics_ch1", [])))
    age = int(age_match.group(1)) if age_match else None
    day_match = re.search(r"_(\d+)days_", title)
    day = int(day_match.group(1)) if day_match else 0
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
    elif title.endswith("_Fib"):
        group = "starting_fibroblast"
    elif title.startswith("iPSC_"):
        group = "iPSC_reference"
    else:
        group = "other"
    exp_match = re.search(r"_exp(\d+)$", title)
    experiment = f"exp{exp_match.group(1)}" if exp_match else "reference"
    return {"GSM": sample["accession"], "sample_title": title, "donor_code": donor,
            "donor_age_years": age, "induction_days": day, "experiment": experiment,
            "group": group, "source_file": filename}


def load_input_manifest(receipt: dict) -> tuple[list[dict], dict[str, dict]]:
    metadata = json.loads((CACHE / f"{ACCESSION}_series_metadata.json").read_text(encoding="utf-8"))
    gsm_to_state = {}
    for sample in metadata["sample_metadata"]:
        filename = ""
        state = sample_state(sample, filename)
        if state["GSM"] in gsm_to_state:
            raise ValueError(f"Duplicate GSM in source metadata: {state['GSM']}")
        gsm_to_state[state["GSM"]] = state

    manifest = []
    crosswalk = receipt["sample_mapping_check"]["expression_header_to_GSM"]
    for table_key, file_record in receipt["files"].items():
        if not table_key.startswith("expression_"):
            continue
        path = CACHE / file_record["filename"]
        if not path.is_file() or sha256_file(path) != file_record["sha256"]:
            raise ValueError(f"Source hash mismatch or missing file: {file_record['filename']}")
        mappings = crosswalk[file_record["filename"]]
        mapping_by_header = {item["expression_header"]: item["GSM"] for item in mappings}
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            header = next(csv.reader(handle, delimiter="\t"))
        sample_headers = header[12:]
        if set(sample_headers) != set(mapping_by_header) or len(sample_headers) != len(mapping_by_header):
            raise ValueError(f"Expression headers no longer match intake receipt: {file_record['filename']}")
        for title in sample_headers:
            gsm = mapping_by_header[title]
            if gsm not in gsm_to_state:
                raise ValueError(f"Sample crosswalk references absent metadata GSM: {gsm}")
            gsm_to_state[gsm]["source_file"] = file_record["filename"]
            gsm_to_state[gsm]["expression_header"] = title
            manifest.append(gsm_to_state[gsm].copy())
    if len(manifest) != 95 or len({row["GSM"] for row in manifest}) != 95:
        raise ValueError(f"Expected one expression column per GEO sample; got {len(manifest)}")
    return manifest, gsm_to_state


def load_marker_expression(receipt: dict, gsm_to_state: dict[str, dict]) -> tuple[dict, dict]:
    expression = {gene: {} for gene in GENES}
    marker_presence = {}
    crosswalk = receipt["sample_mapping_check"]["expression_header_to_GSM"]
    for file_record in receipt["files"].values():
        if not file_record["filename"].endswith(".txt.gz"):
            continue
        path = CACHE / file_record["filename"]
        headers = file_record["header"]
        sample_headers = headers[12:]
        header_to_gsm = {item["expression_header"]: item["GSM"]
                         for item in crosswalk[file_record["filename"]]}
        sums = {gene: {header: 0.0 for header in sample_headers} for gene in GENES}
        counts = {gene: {header: 0 for header in sample_headers} for gene in GENES}
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for row in reader:
                symbol = row["Feature"]
                if symbol not in sums or row["Type"].casefold() != "gene":
                    continue
                for header in sample_headers:
                    value = float(row[header])
                    if not math.isfinite(value):
                        raise ValueError(f"Non-finite processed expression value: {symbol}/{header}")
                    sums[symbol][header] += value
                    counts[symbol][header] += 1
        for gene in GENES:
            for header in sample_headers:
                n = counts[gene][header]
                if n == 0:
                    raise ValueError(f"Gene symbol not found in source matrix: {gene}")
                gsm = header_to_gsm[header]
                expression[gene][gsm] = sums[gene][header] / n
                marker_presence[(file_record["filename"], gene)] = n
    return expression, marker_presence


def build_pairs(manifest: list[dict], expression: dict) -> tuple[list[dict], list[dict]]:
    by_key: dict[tuple, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for sample in manifest:
        if sample["group"] in {"successful_endpoint", "failed_endpoint", "negative_endpoint",
                               "successful_intermediate", "failing_intermediate", "negative_intermediate"}:
            key = (sample["experiment"], sample["donor_code"], sample["induction_days"])
            by_key[key][sample["group"]].append(sample)

    rows = []
    pair_panel_rows = []
    for phase, contrast, reference in GROUP_COMPARISONS:
        for (experiment, donor, day), groups in sorted(by_key.items()):
            if len(groups.get(contrast, [])) != 1 or len(groups.get(reference, [])) != 1:
                continue
            treatment = groups[contrast][0]
            control = groups[reference][0]
            pair_id = f"{phase}:{experiment}:{donor}:{day}:{contrast}-vs-{reference}"
            deltas = []
            for gene in GENES:
                ref_value = expression[gene][control["GSM"]]
                test_value = expression[gene][treatment["GSM"]]
                delta = test_value - ref_value
                deltas.append(delta)
                rows.append({"pair_id": pair_id, "phase": phase, "experiment": experiment,
                             "induction_days": day, "donor_code": donor,
                             "donor_age_years": treatment["donor_age_years"],
                             "comparison": f"{contrast}_vs_{reference}", "gene": gene,
                             "reference_GSM": control["GSM"], "reference_title": control["sample_title"],
                             "contrast_GSM": treatment["GSM"], "contrast_title": treatment["sample_title"],
                             "reference_log2_RPM": f"{ref_value:.8f}",
                             "contrast_log2_RPM": f"{test_value:.8f}",
                             "delta_log2_RPM": f"{delta:.8f}"})
            pair_panel_rows.append({"pair_id": pair_id, "phase": phase, "experiment": experiment,
                                    "induction_days": day, "donor_code": donor,
                                    "donor_age_years": treatment["donor_age_years"],
                                    "comparison": f"{contrast}_vs_{reference}",
                                    "n_collagen_genes": len(deltas),
                                    "mean_delta_log2_RPM_four_collagen_genes": f"{statistics.mean(deltas):.8f}",
                                    "reference_GSM": control["GSM"], "contrast_GSM": treatment["GSM"]})
    if not rows:
        raise ValueError("No paired samples found for the predeclared comparisons")
    return rows, pair_panel_rows


def summarize_donor_effects(pair_panel_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    donor_blocks: dict[tuple, list[dict]] = defaultdict(list)
    for row in pair_panel_rows:
        key = (row["phase"], row["induction_days"], row["comparison"], row["donor_code"])
        donor_blocks[key].append(row)
    donor_rows = []
    for key, blocks in sorted(donor_blocks.items()):
        phase, day, comparison, donor = key
        values = [float(row["mean_delta_log2_RPM_four_collagen_genes"]) for row in blocks]
        donor_rows.append({"phase": phase, "induction_days": day, "comparison": comparison,
                           "donor_code": donor, "donor_age_years": blocks[0]["donor_age_years"],
                           "n_experiment_blocks": len(blocks),
                           "experiment_blocks": ";".join(row["experiment"] for row in blocks),
                           "donor_mean_delta_log2_RPM_four_collagen_genes": f"{statistics.mean(values):.8f}"})

    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in donor_rows:
        grouped[(row["phase"], row["induction_days"], row["comparison"])].append(row)
    summaries = []
    for key, rows in sorted(grouped.items()):
        values = [float(row["donor_mean_delta_log2_RPM_four_collagen_genes"]) for row in rows]
        summaries.append({"phase": key[0], "induction_days": key[1], "comparison": key[2],
                          "n_donor_lines": len(values), "median_donor_mean_delta_log2_RPM": f"{statistics.median(values):.8f}",
                          "min_donor_effect": f"{min(values):.8f}", "max_donor_effect": f"{max(values):.8f}",
                          "donors_positive": sum(value > 0 for value in values),
                          "donors_negative": sum(value < 0 for value in values),
                          "donor_effects": ";".join(f"{row['donor_code']}:{float(row['donor_mean_delta_log2_RPM_four_collagen_genes']):.4f}" for row in rows)})
    return donor_rows, summaries


def summarize_gene_effects(pair_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    blocks: dict[tuple, list[dict]] = defaultdict(list)
    for row in pair_rows:
        key = (row["phase"], row["induction_days"], row["comparison"], row["donor_code"], row["gene"])
        blocks[key].append(row)
    donor_rows = []
    for key, rows in sorted(blocks.items()):
        values = [float(row["delta_log2_RPM"]) for row in rows]
        donor_rows.append({"phase": key[0], "induction_days": key[1], "comparison": key[2],
                           "donor_code": key[3], "gene": key[4], "n_experiment_blocks": len(rows),
                           "experiment_blocks": ";".join(row["experiment"] for row in rows),
                           "donor_mean_delta_log2_RPM": f"{statistics.mean(values):.8f}"})
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in donor_rows:
        grouped[(row["phase"], row["induction_days"], row["comparison"], row["gene"])].append(row)
    summaries = []
    for key, rows in sorted(grouped.items()):
        values = [float(row["donor_mean_delta_log2_RPM"]) for row in rows]
        summaries.append({"phase": key[0], "induction_days": key[1], "comparison": key[2], "gene": key[3],
                          "n_donor_lines": len(values), "median_donor_delta_log2_RPM": f"{statistics.median(values):.8f}",
                          "min_donor_effect": f"{min(values):.8f}", "max_donor_effect": f"{max(values):.8f}",
                          "donors_positive": sum(value > 0 for value in values),
                          "donors_negative": sum(value < 0 for value in values),
                          "donor_effects": ";".join(f"{row['donor_code']}:{float(row['donor_mean_delta_log2_RPM']):.4f}" for row in rows)})
    return donor_rows, summaries


def plot_panel(donor_rows: list[dict], path: Path) -> bool:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    selected = [row for row in donor_rows
                if row["comparison"] in {"successful_endpoint_vs_negative_endpoint",
                                          "successful_intermediate_vs_negative_intermediate"}
                and row["induction_days"] in {10, 13}]
    categories = []
    for phase, day in (("endpoint_after_withdrawal", 10), ("endpoint_after_withdrawal", 13),
                       ("during_induction_intermediate", 10), ("during_induction_intermediate", 13)):
        title = ("post-withdrawal" if phase == "endpoint_after_withdrawal" else "during induction") + f", {day} d"
        records = [row for row in selected if row["phase"] == phase and row["induction_days"] == day]
        if records:
            categories.append((title, records))
    if not categories:
        return False
    fig, ax = plt.subplots(figsize=(8.6, 4.8), constrained_layout=True)
    colors = {"O1": "#0072B2", "O2": "#D55E00", "O3": "#009E73"}
    x_offsets = {"O1": -0.08, "O2": 0.0, "O3": 0.08}
    for x, (label, records) in enumerate(categories):
        for row in records:
            value = float(row["donor_mean_delta_log2_RPM_four_collagen_genes"])
            donor = row["donor_code"]
            ax.scatter(x + x_offsets[donor], value, s=52, color=colors[donor], zorder=3)
            ax.annotate(donor, (x + x_offsets[donor], value), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.axhline(0, color="#555555", linewidth=1, linestyle="--")
    ax.set_xticks(range(len(categories)), [label for label, _ in categories])
    ax.set_ylabel("Paired mean Δ log₂ RPM\n(COL1A1, COL1A2, COL4A1, COL4A2)")
    ax.set_title("Matched collagen-transcript shift by donor-coded line")
    ax.text(0.01, -0.21, "Each point is one donor line; duplicate experiment blocks are averaged within line. Descriptive only.",
            transform=ax.transAxes, fontsize=8)
    ax.legend(handles=[plt.Line2D([0], [0], marker="o", color="w", label=donor,
                                 markerfacecolor=colors[donor], markersize=7)
                       for donor in ("O1", "O2", "O3")], title="Donor line", frameon=False)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return True


def main() -> None:
    receipt = json.loads(INTAKE_RECEIPT.read_text(encoding="utf-8"))
    manifest, gsm_to_state = load_input_manifest(receipt)
    expression, marker_presence = load_marker_expression(receipt, gsm_to_state)
    pair_rows, pair_panel_rows = build_pairs(manifest, expression)
    donor_rows, summaries = summarize_donor_effects(pair_panel_rows)
    gene_donor_rows, gene_summaries = summarize_gene_effects(pair_rows)

    output = HERE / "derived" / "reprogramming-paired-analysis"
    output.mkdir(parents=True, exist_ok=True)
    write_tsv(output / "sample_manifest.tsv", manifest)
    write_tsv(output / "paired_marker_deltas.tsv", pair_rows)
    write_tsv(output / "paired_collagen_panel_by_experiment.tsv", pair_panel_rows)
    write_tsv(output / "donor_level_collagen_panel_effects.tsv", donor_rows)
    write_tsv(output / "collagen_panel_effect_summary.tsv", summaries)
    write_tsv(output / "donor_level_gene_effects.tsv", gene_donor_rows)
    write_tsv(output / "gene_effect_summary.tsv", gene_summaries)
    figure_created = plot_panel(donor_rows, output / "paired_collagen_effects.png")

    input_hashes = {record["filename"]: record["sha256"] for record in receipt["files"].values()}
    summary = {
        "schema_version": 1,
        "accession": ACCESSION,
        "processed_expression_scale": "GEO log2 RPM; no raw counts or re-normalization",
        "source_paper_donor_lines": {"O1": 53, "O2": 53, "O3": 38},
        "target_panel": list(GENES),
        "panel_rationale": "Four collagen genes plotted in the source paper's transcript results and linked to its separate collagen protein assay.",
        "matching_feature_rows_by_input_file_and_gene": {
            f"{filename}:{gene}": n for (filename, gene), n in sorted(marker_presence.items())
        },
        "unit_of_summary": "donor-coded line; experiment blocks for the same line are averaged before group summaries",
        "pair_count_by_phase_comparison_day": [
            {"phase": phase, "comparison": comparison, "induction_days": day,
             "n_sample_pairs": sum(1 for row in pair_panel_rows if row["phase"] == phase and row["comparison"] == comparison and row["induction_days"] == day),
             "donor_lines": sorted({row["donor_code"] for row in pair_panel_rows if row["phase"] == phase and row["comparison"] == comparison and row["induction_days"] == day})}
            for phase, day, comparison in sorted({(r["phase"], r["induction_days"], r["comparison"]) for r in pair_panel_rows})
        ],
        "conclusions_limits": [
            "Differences are descriptive matched log2-RPM contrasts, not inferential tests.",
            "Experiment repeats from the same donor-coded line are not counted as independent donors.",
            "The four-gene collagen panel is not a validated biological-age clock.",
            "In-vitro fibroblast expression cannot establish organism-level age reversal, lasting health benefit, or safe human treatment.",
            "The source paper measured collagen proteins and migration separately; this re-analysis only evaluates deposited transcript values."
        ],
        "inputs_sha256": input_hashes,
        "generated_utc": regen.now(),
        "figure_created": figure_created,
    }
    summary_path = output / "analysis_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    output_paths = [path for path in output.iterdir() if path.is_file()]
    provenance = regen.record("aging-gse165177-paired-collagen-analysis", {
        "accession": ACCESSION, "input_hashes": input_hashes,
        "donor_line_unit": True, "summary": "descriptive paired log2-RPM differences; no age clock"
    }, output_paths)
    print(json.dumps({"sample_columns": len(manifest), "paired_marker_rows": len(pair_rows),
                      "paired_panel_rows": len(pair_panel_rows), "donor_line_summaries": len(donor_rows),
                      "summary": str(summary_path), "figure_created": figure_created,
                      "provenance": provenance.name if provenance else None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
