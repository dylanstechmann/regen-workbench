"""Fit a deliberately limited interpolation to published rat tooth displacement means."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen

HERE = Path(__file__).resolve().parent
INPUT = HERE / "mechanics_benchmark_inputs.json"
OUTPUT = HERE / "derived"


def write_tsv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty output: {path}")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    source = data["sources"][1]
    points = {row["load_N"]: row for row in source["reported_functional_displacement"]}
    required = {10, 15}
    if not required.issubset(points):
        raise ValueError("Source does not contain both 10 N and 15 N displacement summaries")
    outputs = []
    groups = {
        "WT_control": ("WT_mean_um", "WT_SD_um"),
        "progenitor_replant": ("progenitor_replant_mean_um", "progenitor_replant_SD_um"),
    }
    segments = {}
    for group, (mean_key, sd_key) in groups.items():
        low, high = points[10], points[15]
        low_mean, high_mean = float(low[mean_key]), float(high[mean_key])
        low_sd, high_sd = float(low[sd_key]), float(high[sd_key])
        slope = (high_mean - low_mean) / 5.0
        segments[group] = {"at_10N_mean_um": low_mean, "at_10N_SD_um": low_sd,
                           "at_15N_mean_um": high_mean, "at_15N_SD_um": high_sd,
                           "mean_segment_compliance_um_per_N": slope,
                           "one_SD_edge_sensitivity_min_um_per_N": ((high_mean-high_sd)-(low_mean+low_sd))/5.0,
                           "one_SD_edge_sensitivity_max_um_per_N": ((high_mean+high_sd)-(low_mean-low_sd))/5.0}
        for force in range(10, 16):
            mean = low_mean + (force - 10) * slope
            outputs.append({"group": group, "load_N": force,
                            "mean_displacement_um": f"{mean:.4f}",
                            "model_status": "linear interpolation of source group means; only 10–15 N interval is supported",
                            "observed_source_point": force in required,
                            "source_SD_at_endpoint_um": f"{low_sd if force == 10 else high_sd:.4f}" if force in required else "not_reported_at_interpolated_forces"})
    write_tsv(OUTPUT / "displacement_model_10_to_15N.tsv", outputs)

    endpoint_rows = []
    for force in (10, 15):
        point = points[force]
        control = float(point["WT_mean_um"])
        treated = float(point["progenitor_replant_mean_um"])
        endpoint_rows.append({"load_N": force, "WT_mean_um": control, "WT_SD_um": point["WT_SD_um"],
                              "progenitor_replant_mean_um": treated,
                              "progenitor_replant_SD_um": point["progenitor_replant_SD_um"],
                              "treated_minus_WT_um": treated-control,
                              "treated_to_WT_mean_ratio": f"{treated/control:.8f}",
                              "meaning": "descriptive difference of published group means; no inferential test reconstructed"})
    write_tsv(OUTPUT / "displacement_model_endpoint_comparison.tsv", endpoint_rows)

    control_slope = segments["WT_control"]["mean_segment_compliance_um_per_N"]
    treated_slope = segments["progenitor_replant"]["mean_segment_compliance_um_per_N"]
    summary = {
        "schema_version": 1,
        "source_doi": source["doi"],
        "model": "straight-line interpolation between the published mean displacement at 10 N and 15 N; no extrapolation",
        "units": {"load": "N", "displacement": "μm", "segment_compliance": "μm/N"},
        "segments": segments,
        "treated_vs_control_mean_segment_compliance_difference_percent": (treated_slope/control_slope-1)*100,
        "limits": [
            "Only two group means anchor the modeled interval; values at 11–14 N are interpolations, not observed measurements.",
            "Reported SDs are displayed at the measured endpoints. Combining endpoint means ±1 SD to form edge-sensitivity ranges ignores within-tooth covariance and is not a confidence interval.",
            "The paper page reviewed here does not expose the per-tooth dataset or enough information to recover the covariance of repeated force steps; no p-value is recomputed.",
            "This is a rat crown-displacement response slice, not a tooth–PDL material law, chewing model, human in-situ tooth-repositioning model or lifetime stability prediction.",
            "The 626±31 μm loose-untreated observation at 1 N is retained as a separate comparator and is not connected to the 10–15 N fitted segments."
        ],
        "generated_utc": regen.now()
    }
    summary_path = OUTPUT / "displacement_model_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    figure_created = False
    try:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7.4, 4.8), constrained_layout=True)
        styles = {"WT_control": ("#0072B2", "Wild-type control"),
                  "progenitor_replant": ("#D55E00", "Progenitor-treated replant")}
        for group, (color, label) in styles.items():
            values = segments[group]
            x = [10, 15]
            y = [values["at_10N_mean_um"], values["at_15N_mean_um"]]
            yerr = [values["at_10N_SD_um"], values["at_15N_SD_um"]]
            ax.errorbar(x, y, yerr=yerr, marker="o", capsize=4, color=color, label=label)
            ax.plot([10, 15], y, color=color, alpha=.5, linestyle="--")
        ax.set_xticks([10, 11, 12, 13, 14, 15])
        ax.set_xlabel("Applied load (N)")
        ax.set_ylabel("Mean tooth displacement (μm; bars are reported SD)")
        ax.set_title("Published two-point displacement response\ninterpolated segment; no extrapolation")
        ax.legend(frameon=False)
        svg = OUTPUT / "displacement_model.svg"
        fig.savefig(svg)
        svg.write_text("\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n",
                       encoding="utf-8")
        fig.savefig(OUTPUT / "displacement_model.png", dpi=180)
        plt.close(fig)
        figure_created = True
    except ImportError:
        pass
    summary["figure_created"] = figure_created
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths = [p for p in OUTPUT.iterdir() if p.is_file()]
    receipt = regen.record("periodontal-published-displacement-interpolation", {
        "source_doi": source["doi"], "observed_force_points_N": [10, 15],
        "interpolation_only": True, "extrapolation": False
    }, paths)
    print(json.dumps({"model": summary["model"],
                      "WT_segment_compliance_um_per_N": control_slope,
                      "progenitor_segment_compliance_um_per_N": treated_slope,
                      "relative_difference_percent": summary["treated_vs_control_mean_segment_compliance_difference_percent"],
                      "figure_created": figure_created, "provenance": receipt.name}))


if __name__ == "__main__":
    main()
