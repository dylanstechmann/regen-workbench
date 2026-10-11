"""Check collagen-marker age directions in the independent GSE113957 cohort.

This is a small, preselected marker analysis, not reconstruction or application
of the published transcriptomic age clock.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import re
import statistics
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import regen

ACCESSION = "GSE113957"
CACHE = regen.DATA / "literature" / "aging-reference-GSE113957"
INTAKE_RECEIPT = HERE / "aging_reference_intake_receipt.json"
GENES = ("COL1A1", "COL1A2", "COL4A1", "COL4A2")


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


def characteristics(sample: dict) -> dict[str, str]:
    result = {}
    for item in sample["fields"].get("Sample_characteristics_ch1", []):
        if ":" in item:
            key, value = item.split(":", 1)
            result[key.strip().casefold()] = value.strip()
    return result


def age_years(value: str) -> float:
    text = value.strip().casefold()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:yr|year|years)?(?:\s*(\d+)\s*mos?)?", text)
    if not match:
        raise ValueError(f"Could not parse GEO donor age: {value!r}")
    years = float(match.group(1))
    months = float(match.group(2) or 0)
    return years + months / 12


def rankdata(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = ((start + 1) + end) / 2
        for index in order[start:end]:
            ranks[index] = rank
        start = end
    return ranks


def correlation(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 3:
        return None
    rx, ry = rankdata(x), rankdata(y)
    mean_x, mean_y = statistics.mean(rx), statistics.mean(ry)
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry, strict=True))
    norm_x = math.sqrt(sum((a - mean_x) ** 2 for a in rx))
    norm_y = math.sqrt(sum((b - mean_y) ** 2 for b in ry))
    if norm_x == 0 or norm_y == 0:
        return None
    return cov / (norm_x * norm_y)


def slope_per_decade(age: list[float], expression: list[float]) -> float | None:
    if len(age) < 2:
        return None
    mean_age, mean_expression = statistics.mean(age), statistics.mean(expression)
    denominator = sum((value - mean_age) ** 2 for value in age)
    if denominator == 0:
        return None
    slope = sum((a - mean_age) * (y - mean_expression) for a, y in zip(age, expression, strict=True)) / denominator
    return slope * 10


def plot_age_reference(samples: list[dict], expression: dict, path: Path) -> bool:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    adults = [sample for sample in samples if sample["age_years"] >= 18]
    colors = {"female": "#CC79A7", "male": "#0072B2"}
    fig, axes = plt.subplots(2, 2, figsize=(9, 7), constrained_layout=True, sharex=True)
    for ax, gene in zip(axes.flat, GENES, strict=True):
        ages = [sample["age_years"] for sample in adults]
        values = [math.log2(expression[gene][sample["GSM"]] + 0.1) for sample in adults]
        rho = correlation(ages, values)
        for sex in ("female", "male"):
            chosen = [sample for sample in adults if sample["sex"] == sex]
            ax.scatter([s["age_years"] for s in chosen],
                       [math.log2(expression[gene][s["GSM"]] + 0.1) for s in chosen],
                       s=20, alpha=0.72, color=colors[sex], label=sex.title())
        ax.set_title(f"{gene} (adult Spearman ρ={rho:.2f})" if rho is not None else gene)
        ax.set_xlabel("Donor age (years)")
        ax.set_ylabel("log₂(sum transcript FPKM + 0.1)")
        ax.grid(alpha=0.2)
    axes[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle("Preselected collagen markers in independent healthy fibroblast reference")
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return True


def main() -> None:
    receipt = json.loads(INTAKE_RECEIPT.read_text(encoding="utf-8"))
    metadata = json.loads((CACHE / f"{ACCESSION}_sample_metadata.json").read_text(encoding="utf-8"))
    matrix_record = receipt["files"]["fpkm_matrix"]
    matrix_path = CACHE / matrix_record["filename"]
    if sha256_file(matrix_path) != matrix_record["sha256"]:
        raise ValueError("FPKM source hash does not match the GEO intake receipt")

    by_gsm = {}
    for sample in metadata["samples"]:
        chars = characteristics(sample)
        title = sample["fields"].get("Sample_title", [""])[0]
        disease = chars.get("disease", "").casefold()
        if disease not in {"normal", "hgps"}:
            raise ValueError(f"Unexpected disease status in GEO sample {sample['accession']}: {disease!r}")
        by_gsm[sample["accession"]] = {
            "GSM": sample["accession"], "sample_title": title,
            "cell_id": chars.get("cell id", ""), "disease": disease,
            "age_years": age_years(chars["age"]), "sex": chars.get("sex", "").casefold(),
            "ethnicity": chars.get("ethnicity", ""),
            "skin_source": sample["fields"].get("Sample_source_name_ch1", [""])[0],
        }
    mapping = receipt["sample_mapping_check"]["expression_header_to_GSM"]
    header_to_gsm = {entry["expression_header"]: entry["GSM"] for entry in mapping}
    sample_headers = matrix_record["header"][8:]
    if len(sample_headers) != 143 or set(sample_headers) != set(header_to_gsm):
        raise ValueError("FPKM sample headers no longer match the qualified GEO crosswalk")

    transcript_sums = {gene: defaultdict(float) for gene in GENES}
    transcript_counts = Counter()
    annotation_fields = 8
    with gzip.open(matrix_path, "rt", encoding="utf-8", errors="strict", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        if header != matrix_record["header"]:
            raise ValueError("FPKM matrix header differs from the intake receipt")
        for row in reader:
            if len(row) != len(header):
                raise ValueError("Malformed ragged row in FPKM table")
            annotation = row[7]
            symbol = annotation.split("|", 1)[0].strip()
            if symbol not in GENES:
                continue
            for header_label, raw in zip(sample_headers, row[annotation_fields:], strict=True):
                value = float(raw)
                if not math.isfinite(value) or value < 0:
                    raise ValueError(f"Invalid FPKM value for {symbol}/{header_label}: {raw!r}")
                gsm = header_to_gsm[header_label]
                transcript_sums[symbol][gsm] += value
            transcript_counts[symbol] += 1
    if set(transcript_counts) != set(GENES):
        raise ValueError(f"Missing selected genes from FPKM annotations: {set(GENES)-set(transcript_counts)}")

    value_rows = []
    for gene in GENES:
        for gsm, sample in by_gsm.items():
            value_rows.append({**sample, "gene": gene, "transcript_rows_summed": transcript_counts[gene],
                               "sum_transcript_FPKM": f"{transcript_sums[gene][gsm]:.8f}"})
    write_tsv(HERE / "derived" / "reprogramming-paired-analysis" / "aging_reference_gene_values.tsv", value_rows)

    adult_samples = [s for s in by_gsm.values() if s["disease"] == "normal" and s["age_years"] >= 18]
    cohorts = {
        "healthy_all_ages": [s for s in by_gsm.values() if s["disease"] == "normal"],
        "healthy_adult_18_plus": adult_samples,
        "healthy_age_35_to_60": [s for s in by_gsm.values() if s["disease"] == "normal" and 35 <= s["age_years"] <= 60],
        "healthy_adult_male_18_plus": [s for s in adult_samples if s["sex"] == "male"],
        "healthy_adult_female_18_plus": [s for s in adult_samples if s["sex"] == "female"],
        "healthy_adult_arm_site_18_plus": [s for s in adult_samples if "arm" in s["skin_source"].casefold()],
    }
    trends = []
    for cohort_name, samples in cohorts.items():
        for gene in GENES:
            ages = [s["age_years"] for s in samples]
            values = [transcript_sums[gene][s["GSM"]] for s in samples]
            transformed = [math.log2(value + 0.1) for value in values]
            rho = correlation(ages, values)
            slope = slope_per_decade(ages, transformed)
            trends.append({"cohort": cohort_name, "gene": gene, "n_people": len(samples),
                           "min_age_years": f"{min(ages):.3f}" if ages else "",
                           "max_age_years": f"{max(ages):.3f}" if ages else "",
                           "spearman_age_vs_sum_transcript_FPKM": f"{rho:.6f}" if rho is not None else "",
                           "descriptive_log2_FPKM_plus_0_1_slope_per_decade": f"{slope:.6f}" if slope is not None else "",
                           "median_sum_transcript_FPKM": f"{statistics.median(values):.6f}" if values else ""})
    write_tsv(HERE / "derived" / "reprogramming-paired-analysis" / "aging_reference_gene_trends.tsv", trends)
    figure_path = HERE / "derived" / "reprogramming-paired-analysis" / "aging_reference_marker_age_trends.png"
    figure_created = plot_age_reference(cohorts["healthy_all_ages"], transcript_sums, figure_path)

    # Direction-only comparison: separate independent age reference from MPTR contrasts.
    mptr_path = HERE / "derived" / "reprogramming-paired-analysis" / "gene_effect_summary.tsv"
    with mptr_path.open("r", encoding="utf-8", newline="") as handle:
        mptr_rows = list(csv.DictReader(handle, delimiter="\t"))
    day13 = {row["gene"]: row for row in mptr_rows
             if row["phase"] == "endpoint_after_withdrawal" and row["induction_days"] == "13"
             and row["comparison"] == "successful_endpoint_vs_negative_endpoint"}
    age_rows = {row["gene"]: row for row in trends
                if row["cohort"] == "healthy_adult_18_plus"}
    direction_rows = []
    for gene in GENES:
        rho = float(age_rows[gene]["spearman_age_vs_sum_transcript_FPKM"])
        effect = float(day13[gene]["median_donor_delta_log2_RPM"])
        opposition = "opposite" if rho * effect < 0 else "same" if rho * effect > 0 else "unclear"
        direction_rows.append({"gene": gene, "age_reference_cohort": "healthy_adult_18_plus",
                               "age_reference_n_people": age_rows[gene]["n_people"],
                               "age_reference_spearman_rho": f"{rho:.6f}",
                               "MPTR_contrast": "13-day successful post-withdrawal vs matched negative control",
                               "MPTR_n_donor_lines": day13[gene]["n_donor_lines"],
                               "MPTR_median_donor_delta_log2_RPM": day13[gene]["median_donor_delta_log2_RPM"],
                               "direction_vs_age_association": opposition,
                               "interpretation_limit": "Direction only; cohorts, assays and expression scales differ; not an age-clock estimate."})
    write_tsv(HERE / "derived" / "reprogramming-paired-analysis" / "age_vs_MPTR_direction_comparison.tsv", direction_rows)

    healthy = cohorts["healthy_all_ages"]
    healthy_cell_ids = {sample["cell_id"] for sample in healthy}
    if len(healthy_cell_ids) != len(healthy) or "" in healthy_cell_ids:
        raise ValueError("Healthy GEO records do not have unique, populated cell IDs")
    skin_sources = Counter(sample["skin_source"] for sample in healthy)
    summary = {
        "schema_version": 1, "accession": ACCESSION,
        "source": "NCBI GEO processed FPKM matrix and sample metadata",
        "healthy_sample_count": len(healthy), "hgps_sample_count": sum(s["disease"] == "hgps" for s in by_gsm.values()),
        "healthy_unique_cell_id_count": len(healthy_cell_ids),
        "healthy_age_range_years": [min(s["age_years"] for s in healthy), max(s["age_years"] for s in healthy)],
        "age_range_metadata_note": {
            "geo_metadata_range_years": [min(s["age_years"] for s in healthy), max(s["age_years"] for s in healthy)],
            "article_text_range_years": [1, 94],
            "record_above_article_text_maximum": {"GSM": "GSM3124624", "cell_id": "AG04059", "GEO_age_years": 96},
            "handling": "retain GEO sample-level age; record the article-versus-GEO discrepancy"
        },
        "healthy_sex_counts": dict(Counter(s["sex"] for s in healthy)),
        "healthy_sample_source_counts": dict(skin_sources),
        "selected_genes": list(GENES),
        "transcript_rows_summed_by_gene": {gene: transcript_counts[gene] for gene in GENES},
        "figure_created": figure_created,
        "aggregation": "sum transcript-row FPKM values sharing the exact first annotation symbol; record transcript row counts",
        "age_cohorts": {name: {"n": len(samples), "min_age_years": min(s["age_years"] for s in samples),
                               "max_age_years": max(s["age_years"] for s in samples)}
                        for name, samples in cohorts.items()},
        "limitations": [
            "Four collagen genes were selected from the MPTR paper before this age-reference analysis; this is not genome-wide replication.",
            "Spearman correlations and expression slopes are descriptive and unadjusted for sex, ethnicity, skin sampling site, culture or batch.",
            "FPKM transcript rows are summed by gene symbol; this is a transcript-level aggregation, not read-count re-quantification.",
            "This analysis does not train or apply the published age clock and does not convert molecular expression into years of rejuvenation.",
            "The age-reference and reprogramming cohorts use different datasets and expression units; only direction is compared."
        ],
        "inputs_sha256": {record["filename"]: record["sha256"] for record in receipt["files"].values()},
        "generated_utc": regen.now(),
    }
    output = HERE / "derived" / "reprogramming-paired-analysis" / "aging_reference_summary.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths = [HERE / "derived" / "reprogramming-paired-analysis" / name for name in (
        "aging_reference_gene_values.tsv", "aging_reference_gene_trends.tsv",
        "age_vs_MPTR_direction_comparison.tsv", "aging_reference_summary.json")]
    if figure_created:
        paths.append(figure_path)
    provenance = regen.record("aging-gse113957-collagen-marker-age-trend", {
        "accession": ACCESSION, "inputs_sha256": summary["inputs_sha256"],
        "method": "descriptive Spearman correlations in GEO disease=Normal samples; no age clock"
    }, paths)
    print(json.dumps({"healthy_people": len(healthy), "hgps_people": summary["hgps_sample_count"],
                      "gene_trends": len(trends), "direction_rows": len(direction_rows),
                      "summary": str(output), "provenance": provenance.name if provenance else None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
