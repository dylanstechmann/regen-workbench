"""Build a transparent, source-traced periodontal attachment benchmark."""

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
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    paper = data["sources"][0]
    metrics = paper["reported_day21_mechanics"]
    rows = []
    for item in metrics:
        value = item["value"]
        rows.append({
            "source_doi": paper["doi"],
            "metric": item["metric"],
            "normalized_value": "" if value is None else f"{value:.8f}",
            "unit": item["unit"],
            "restoration_gap_fraction": "" if value is None else f"{1-value:.8f}",
            "source_wording": item["source_wording"],
            "data_type": "reported group mean ratio or direct arithmetic from rounded reported values; not specimen-level data",
        })
    write_tsv(OUTPUT / "day21_mechanical_endpoints.tsv", rows)

    fracture_rows = []
    for day, groups in {
        "0": {"NC": (1, 10)},
        "7": {"NC": (0, 10), "PBS": (0, 9), "AC": (0, 9), "PDGF-BB": (0, 8)},
        "14": {"NC": (1, 10), "PBS": (3, 9), "AC": (7, 9), "PDGF-BB": (1, 9)},
        "21": {"NC": (0, 10), "PBS": (8, 9), "AC": (10, 10), "PDGF-BB": (3, 10)},
    }.items():
        for group, (fractures, n) in groups.items():
            fracture_rows.append({"day_after_replantation": day, "group": group,
                                  "fractures_during_extraction_test": fractures,
                                  "rats_or_teeth_reported": n,
                                  "fracture_fraction": f"{fractures/n:.8f}",
                                  "source_doi": paper["doi"]})
    write_tsv(OUTPUT / "fractures_during_mechanical_testing.tsv", fracture_rows)

    displacement = data["sources"][1]["reported_functional_displacement"]
    displacement_rows = []
    for row in displacement:
        for group, mean_key, sd_key in (
            ("WT_control", "WT_mean_um", "WT_SD_um"),
            ("progenitor_replant", "progenitor_replant_mean_um", "progenitor_replant_SD_um"),
            ("loose_untreated_replant", "loose_untreated_replant_mean_um", "loose_untreated_replant_SD_um"),
        ):
            if mean_key in row:
                displacement_rows.append({"source_doi": data["sources"][1]["doi"],
                                          "load_N": row["load_N"], "group": group,
                                          "mean_displacement_um": row[mean_key], "SD_um": row[sd_key],
                                          "interpretation": "reported mean ± SD; rat tooth displacement test, not human in-situ repositioning"})
    write_tsv(OUTPUT / "physiologic_displacement_benchmarks.tsv", displacement_rows)

    # A stiffness-only measurement is not identifiable as native attachment.
    # Sweep two hypothetical parallel load paths while holding their sum fixed.
    aliases = []
    for index in range(11):
        bridge = index / 10
        pdl = 1.0 - bridge
        aliases.append({"hypothetical_functional_PDL_stiffness_fraction": f"{pdl:.1f}",
                        "hypothetical_bone_bridge_stiffness_fraction": f"{bridge:.1f}",
                        "apparent_stiffness_fraction": f"{pdl+bridge:.1f}",
                        "source_measurement": "none; algebraic illustration only"})
    write_tsv(OUTPUT / "stiffness_nonidentifiability_sweep.tsv", aliases)

    summary = {
        "schema_version": 1,
        "primary_quantitative_study": paper["doi"],
        "additional_functional_attachment_study": data["sources"][1]["doi"],
        "source_retrieval_receipt": "../dental-attachment-mechanics-2026-10-11/source_extraction_receipt.json",
        "key_findings": {
            "day21_PDGF_BB_failure_load_fraction": 0.54,
            "day21_PDGF_BB_extension_fraction": 0.68,
            "day21_PDGF_BB_toughness_fraction": 0.44,
            "day21_PDGF_BB_stiffness": "qualitatively almost control; exact ratio is not stated in the text",
            "area_standardized_strength_conflict": "The paper calls 2.45/3.39 N/mm^2 approximately 76%; direct division of the rounded values is 72.27%. Keep both statements visible pending source-data clarification.",
            "day21_fractures": {"NC": "0/10", "PBS": "8/9", "AC": "10/10", "PDGF-BB": "3/10"},
            "progenitor_replant_displacement": "At 10 N, 156±19 μm in treated replants vs 141±23 μm WT; at 15 N, 300±26 μm vs 297±34 μm, in one rat replantation study."
        },
        "interpretation": [
            "Strength, extensibility, toughness, physiologic mobility, fiber insertion and absence of ankylosis are separate restoration outcomes.",
            "An apparent stiffness match is insufficient: parallel PDL and bone-bridge load paths can produce the same initial stiffness while differing in mobility, dissipation and tissue identity.",
            "The evidence demonstrates animal proof-of-concept for complete progenitor-driven periodontal reattachment after replantation, not a therapy for crooked in-situ human teeth after blunt trauma.",
            "An in-situ tooth displaced by trauma may heal in a shifted position; restoration research must measure position, socket/cementum/PDL insertion, occlusion, mobility, toughness and relapse after temporary stabilization is removed."
        ],
        "model_scope": data["reduced_model"],
        "generated_utc": regen.now()
    }
    summary_path = OUTPUT / "mechanics_benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    figure_created = False
    try:
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
        labels = ["Failure\nload", "Extension", "Toughness", "Strength\n(paper: ~76%)", "Strength\n(quotient: 72.3%)"]
        values = [0.54, 0.68, 0.44, 0.76, 2.45/3.39]
        colors = ["#0072B2", "#56B4E9", "#D55E00", "#009E73", "#CC79A7"]
        axes[0].bar(range(len(values)), values, color=colors)
        axes[0].axhline(1, color="#333333", lw=1, ls="--")
        axes[0].set_ylim(0, 1.08)
        axes[0].set_ylabel("Fraction of uninjured-control mean")
        axes[0].set_xticks(range(len(values)), labels, fontsize=8)
        axes[0].set_title("Day-21 rat outcomes\nPaper: 76%; rounded values: 72.3%")

        pdl = [float(row["hypothetical_functional_PDL_stiffness_fraction"]) for row in aliases]
        bridge = [float(row["hypothetical_bone_bridge_stiffness_fraction"]) for row in aliases]
        apparent = [float(row["apparent_stiffness_fraction"]) for row in aliases]
        axes[1].plot(pdl, apparent, "o-", label="Same apparent stiffness")
        axes[1].plot(pdl, bridge, "s--", label="Bridge contribution")
        axes[1].set_xlabel("Functional PDL contribution (illustrative fraction)")
        axes[1].set_ylabel("Normalized stiffness contribution")
        axes[1].set_title("Stiffness-only ambiguity\nAlgebraic toy; no tissue fit")
        axes[1].legend(frameon=False, fontsize=8)
        figure = OUTPUT / "mechanics_benchmark.png"
        fig.savefig(figure, dpi=180)
        svg_path = OUTPUT / "mechanics_benchmark.svg"
        fig.savefig(svg_path)
        svg_path.write_text("\n".join(line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()) + "\n",
                            encoding="utf-8")
        plt.close(fig)
        figure_created = True
    except ImportError:
        pass

    summary["figure_created"] = figure_created
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths = [p for p in OUTPUT.iterdir() if p.is_file()]
    receipt = regen.record("periodontal-attachment-benchmark", {
        "sources": [item["doi"] for item in data["sources"]],
        "model": data["reduced_model"]["name"],
        "interpretation": "dimensionless source-traced outcomes plus a stiffness identifiability demonstration"
    }, paths)
    print(json.dumps({"output": str(OUTPUT), "mechanical_rows": len(rows),
                      "fracture_rows": len(fracture_rows), "figure_created": figure_created,
                      "provenance": receipt.name}))


if __name__ == "__main__":
    main()
