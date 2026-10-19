"""Freeze demographic sensitivities before reading gene-expression outcomes."""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def text_sha(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def populations(cell: list[dict], bulk: list[dict]) -> dict:
    cohorts = {"GSE164241": cell, "GSE173078": bulk}
    for rows in cohorts.values():
        if not rows or len({row["donor"] for row in rows}) != len(rows):
            raise ValueError("Expected unique healthy donor metadata")
    low = max(min(row["age"] for row in rows) for rows in cohorts.values())
    high = min(max(row["age"] for row in rows) for rows in cohorts.values())
    if low > high:
        raise ValueError("No common observed age span")
    bins = sorted(set(int(row["age"] // 10)*10 for row in cell) & set(int(row["age"] // 10)*10 for row in bulk))
    output = {"rules": {"shared_age_span": [low, high], "shared_decade_starts": bins}, "populations": {}}
    for name in ["all_healthy", "shared_observed_age_span", "shared_nonempty_decade_bins"]:
        current = {}
        for cohort, rows in cohorts.items():
            selected = [row for row in rows if name == "all_healthy" or
                        (name == "shared_observed_age_span" and low <= row["age"] <= high) or
                        (name == "shared_nonempty_decade_bins" and int(row["age"] // 10)*10 in bins)]
            current[cohort] = {"donors": selected, "n_donors": len(selected),
                               "ages_sorted": sorted(row["age"] for row in selected),
                               "sex_counts": dict(Counter(row["sex"] for row in selected)),
                               "processing_counts": dict(Counter(row["processing_label"] for row in selected)),
                               "decade_counts": dict(sorted(Counter(int(row["age"] // 10)*10 for row in selected).items()))}
        output["populations"][name] = current
    return output


def main() -> None:
    plan_path = HERE / "analysis_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for name in ["cell_metadata", "bulk_metadata"]:
        spec = plan["inputs"][name]
        if text_sha(ROOT / spec["path"]) != spec["sha256_lf_text"]:
            raise ValueError("Metadata source differs from plan")
    cell = [{"donor": row["donor"], "cohort": "GSE164241", "age": float(row["age"]), "sex": row["sex"],
             "processing": int(row["cellranger_versions"] == "3.0.1"), "processing_label": row["cellranger_versions"]}
            for row in read_tsv(ROOT / plan["inputs"]["cell_metadata"]["path"])
            if row["cell_group"] == "fibroblasts_all" and row["condition"] == "healthy"]
    bulk = [{"donor": row["donor_code"], "cohort": "GSE173078", "age": float(row["age_years"]), "sex": row["sex"],
             "processing": int(row["batch"] == "B"), "processing_label": row["batch"]}
            for row in read_tsv(ROOT / plan["inputs"]["bulk_metadata"]["path"]) if row["phenotype"] == "Healthy"]
    if len(cell) != 13 or len(bulk) != 12:
        raise ValueError("Expected the previously qualified 13/12 healthy donor cohorts")
    result = populations(cell, bulk)
    result.update(status="Metadata-only rules frozen before per-gene outcomes; exploratory, not preregistered",
                  plan_sha256_lf_text=text_sha(plan_path), metadata_script_sha256_lf_text=text_sha(Path(__file__)),
                  gene_expression_used=False, clinical_age_matching=False)
    (HERE / "frozen_populations.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"rules": result["rules"], "n_by_population": {name: {cohort: info["n_donors"] for cohort, info in value.items()}
                                                                   for name, value in result["populations"].items()}}, indent=2))


if __name__ == "__main__":
    main()
