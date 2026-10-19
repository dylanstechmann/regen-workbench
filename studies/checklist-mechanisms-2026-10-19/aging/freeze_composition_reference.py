"""Audit source-label coverage and freeze common RNA fractions without genes."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha_text(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def audit_labels(coverage: dict, compartments: list[str], captured_cells: int) -> dict:
    if len(compartments) != len(set(compartments)):
        raise ValueError("Duplicate compartment")
    included, omitted, included_cells = {}, {}, 0
    for label, info in coverage.items():
        overlap = sorted(set(info["mapped_to_groups"]) & set(compartments))
        if len(overlap) > 1:
            raise ValueError(f"Overlapping parent/child compartments double-count {label}")
        if overlap:
            included[label] = {"compartment": overlap[0], "n_cells": info["n_cells"]}
            included_cells += info["n_cells"]
        else:
            omitted[label] = {"n_cells": info["n_cells"], "source_exclusion": info["exclusion_reason"]}
    if included_cells + sum(info["n_cells"] for info in omitted.values()) != captured_cells:
        raise ValueError("Source-label counts do not sum to captured cohort")
    return {"status": "partial_captured_cell_mixture" if omitted else "exhaustive_for_supplied_capture_labels",
            "included_cells": included_cells, "captured_cells": captured_cells,
            "captured_cell_fraction": included_cells / captured_cells,
            "omitted_cell_UMIs": None, "included_labels": included, "omitted_labels": omitted,
            "whole_tissue_reconstruction": False}


def freeze_reference(rows: list[dict], compartments: list[str]) -> tuple[list[dict], dict, list[dict]]:
    keys = [(row["donor"], row["cell_group"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate donor-compartment metadata")
    groups = defaultdict(dict)
    for row in rows:
        if row["cell_group"] in compartments:
            groups[row["donor"]][row["cell_group"]] = row
    output, donor_audit = [], []
    for donor, current in sorted(groups.items()):
        if set(current) != set(compartments):
            raise ValueError("Missing captured compartment; do not impute it as zero")
        metadata = {(row["condition"], row["age"], row["sex"], row["samples"], row["cellranger_versions"]) for row in current.values()}
        if len(metadata) != 1:
            raise ValueError("Donor metadata differs across compartments")
        cells = {group: int(current[group]["n_cells"]) for group in compartments}
        umis = {group: int(current[group]["total_raw_umis"]) for group in compartments}
        if min(cells.values()) <= 0 or min(umis.values()) <= 0:
            raise ValueError("Positive cells/UMIs required for common-composition support")
        total_umis, total_cells = sum(umis.values()), sum(cells.values())
        base = next(iter(current.values()))
        donor_audit.append({"donor": donor, "condition": base["condition"], "age": base["age"], "sex": base["sex"],
                            "included_cells": total_cells, "included_total_raw_umis": total_umis,
                            "minimum_compartment_cells": min(cells.values()), "strict20_eligible": min(cells.values()) >= 20})
        for group in compartments:
            output.append({**current[group], "donor_included_cells": total_cells,
                           "donor_included_raw_umis": total_umis,
                           "observed_RNA_fraction": umis[group] / total_umis,
                           "observed_cell_fraction": cells[group] / total_cells,
                           "strict20_eligible": min(cells.values()) >= 20})
    healthy = sorted({row["donor"] for row in output if row["condition"] == "healthy"})
    if len(healthy) != 13:
        raise ValueError("Expected the same 13 qualified healthy inferred donors")
    weights = {group: math.fsum(float(row["observed_RNA_fraction"]) for row in output
                                if row["donor"] in healthy and row["cell_group"] == group) / len(healthy) for group in compartments}
    if not math.isclose(math.fsum(weights.values()), 1, abs_tol=1e-12, rel_tol=0):
        raise ValueError("Common reference weights do not sum to one")
    frozen = {"status": "Frozen from metadata before panel outcomes; exploratory, not preregistered",
              "rule": "Equal-donor arithmetic mean of each healthy donor's included-compartment RNA fractions",
              "reference_donors": healthy, "n_reference_donors": len(healthy), "weights": weights,
              "selected_gene_values_used": False, "age_labels_used_to_optimize_weights": False,
              "disease_donors_used": False, "pooled_donor_counts_used": False,
              "cell_fraction_substituted_for_RNA": False}
    return output, frozen, donor_audit


def main() -> None:
    plan_path = HERE / "analysis_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    source = ROOT / plan["input_directory"]
    # This step intentionally does not open the selected-gene count file.
    for name in ["gingival_cellset_donor_counts.tsv", "gingival_cell_atlas_analysis_summary.json", "oral_atlas_sample_crosswalk.tsv"]:
        if sha_text(source / name) != plan["input_sha256_lf_text"][name]:
            raise ValueError("Metadata input differs from plan")
    summary = json.loads((source / "gingival_cell_atlas_analysis_summary.json").read_text(encoding="utf-8"))
    coverage = audit_labels(summary["annotated_cellset_coverage"], plan["compartments"], summary["gse164241_gingiva_cells"])
    rows, frozen, donors = freeze_reference(read_tsv(source / "gingival_cellset_donor_counts.tsv"), plan["compartments"])
    if sum(row["included_cells"] for row in donors) != coverage["included_cells"]:
        raise ValueError("Donor-compartment cell counts differ from label coverage")
    totals = Counter()
    for sample in read_tsv(source / "oral_atlas_sample_crosswalk.tsv"):
        totals[sample["inferred_donor_group"]] += int(sample["n_cells_in_h5ad"])
    if set(totals) != {row["donor"] for row in donors} or sum(totals.values()) != coverage["captured_cells"]:
        raise ValueError("Original library/donor cell count mismatch")
    for donor in donors:
        donor["all_source_captured_cells"] = totals[donor["donor"]]
        donor["omitted_captured_cells"] = totals[donor["donor"]] - donor["included_cells"]
        if donor["omitted_captured_cells"] < 0:
            raise ValueError("Included counts exceed donor capture; possible overlap")
    coverage["donor_coverage"] = donors
    frozen.update(plan_sha256_lf_text=sha_text(plan_path), metadata_script_sha256_lf_text=sha_text(Path(__file__)))
    (HERE / "frozen_RNA_weights.json").write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8", newline="\n")
    out = HERE / "derived"
    out.mkdir(parents=True, exist_ok=True)
    (out / "capture_coverage_audit.json").write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8", newline="\n")
    write_tsv(out / "donor_compartment_metadata.tsv", rows)
    print(json.dumps({"status": coverage["status"], "included_cells": coverage["included_cells"],
                      "captured_cells": coverage["captured_cells"], "healthy_reference_donors": len(frozen["reference_donors"]),
                      "strict20_healthy_donors": sum(row["condition"] == "healthy" and row["strict20_eligible"] for row in donors),
                      "weights": frozen["weights"]}, indent=2))


if __name__ == "__main__":
    main()
