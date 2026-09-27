"""Run the pre-registered synthetic cohort check.

Usage:
  PYTHONPATH=tools python3 studies/frozen_cohort/run_study.py --out DIR

DIR must not already exist. The parent must exist. This script does not
download data and does not claim a biological effect.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from regen_compute import expression_contrast  # noqa: E402

PANEL = ("PANEL_A", "PANEL_B", "PANEL_C", "PANEL_D")
NULL = ("NULL_A", "NULL_B", "STABLE_A")
SAMPLES = ("Y1", "Y2", "Y3", "Y4", "O1", "O2", "O3", "O4")
GROUPS = {
    "Y1": "young", "Y2": "young", "Y3": "young", "Y4": "young",
    "O1": "older", "O2": "older", "O3": "older", "O4": "older",
}
DONORS = {
    "Y1": "D1", "Y2": "D1", "Y3": "D2", "Y4": "D2",
    "O1": "D3", "O2": "D3", "O3": "D4", "O4": "D4",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def expression_tables() -> tuple[list[list], list[list]]:
    """Deterministic fixtures. See PROTOCOL.md. Values are linear-scale, not counts."""
    young = [4.0, 4.0, 4.0, 4.0]
    older = [16.0, 16.0, 16.0, 16.0]
    flat = [10.0, 10.0, 10.0, 10.0]
    genes = {
        "PANEL_A": young + older,
        "PANEL_B": young + older,
        "PANEL_C": [4.0, 5.0, 4.0, 5.0, 15.0, 16.0, 15.0, 16.0],
        "PANEL_D": [3.0, 4.0, 5.0, 4.0, 14.0, 18.0, 16.0, 15.0],
        "NULL_A": flat + flat,
        "NULL_B": [9.0, 11.0, 10.0, 10.0, 10.0, 9.0, 11.0, 10.0],
        "STABLE_A": flat + flat,
        # Mean leans older-lower, but dropping the young outlier reverses it.
        "FLIP_A": [5.0, 5.0, 5.0, 40.0, 8.0, 8.0, 8.0, 8.0],
        "CTRL_A": [2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0],
        "CTRL_B": [30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0],
    }
    matrix = [[gene, *values] for gene, values in genes.items()]
    meta = [[sample, GROUPS[sample]] for sample in SAMPLES]
    return matrix, meta


def _betacf(a: float, b: float, x: float) -> float:
    """Lentz continued fraction for the incomplete beta function."""
    max_iter = 200
    eps = 3e-14
    fpmin = 1e-30
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    raise ValueError("incomplete beta did not converge")


def _regularized_beta(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1.0 - x) - ln_beta)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def welch(a: list[float], b: list[float]) -> dict:
    n1, n2 = len(a), len(b)
    m1, m2 = sum(a) / n1, sum(b) / n2
    v1 = sum((v - m1) ** 2 for v in a) / (n1 - 1)
    v2 = sum((v - m2) ** 2 for v in b) / (n2 - 1)
    se2 = v1 / n1 + v2 / n2
    if se2 == 0.0:
        p = 1.0 if m1 == m2 else 0.0
        t = 0.0 if m1 == m2 else math.inf
        df = float(n1 + n2 - 2)
    else:
        t = (m2 - m1) / math.sqrt(se2)
        df = se2 ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
        if abs(t) > 40.0:
            p = 0.0
        else:
            x = df / (df + t * t)
            p = min(1.0, _regularized_beta(df / 2.0, 0.5, x))
    return {"t": t, "df": df, "p": p}


def benjamini_hochberg(pvals: list[float]) -> list[float]:
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    q = [1.0] * len(pvals)
    running = 1.0
    m = len(pvals)
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, pvals[i] * m / rank)
        q[i] = running
    return q


def _group_values(row: list, groups: dict, samples: tuple[str, ...], label: str) -> list[float]:
    return [float(row[1 + i]) for i, sample in enumerate(samples) if groups[sample] == label]


def contrast_rows(matrix: list[list], groups: dict) -> list[dict]:
    rows = []
    for row in matrix:
        a = _group_values(row, groups, SAMPLES, "young")
        b = _group_values(row, groups, SAMPLES, "older")
        mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
        rows.append({
            "gene": row[0],
            "log2_ratio": math.log2(mean_b + 1.0) - math.log2(mean_a + 1.0),
            "welch": welch(a, b),
        })
    qvals = benjamini_hochberg([row["welch"]["p"] for row in rows])
    for row, q in zip(rows, qvals):
        row["q"] = q
    return rows


def estimand(rows: list[dict]) -> float:
    by = {row["gene"]: row["log2_ratio"] for row in rows}
    panel = sum(by[gene] for gene in PANEL) / len(PANEL)
    null = sum(by[gene] for gene in NULL) / len(NULL)
    return panel - null


def swapped_groups() -> dict:
    return {sample: ("older" if group == "young" else "young") for sample, group in GROUPS.items()}


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _components(rows: list[dict]) -> list[int]:
    parent = list(range(len(rows)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    buckets: dict[tuple, list[int]] = {}
    for i, row in enumerate(rows):
        for key in ("donor_id", "batch_id"):
            buckets.setdefault((key, row[key]), []).append(i)
    for members in buckets.values():
        for other in members[1:]:
            union(members[0], other)
    return [find(i) for i in range(len(rows))]


def _logistic_predict(train: list[dict], test: list[dict]) -> list[int]:
    features = ("f_area", "f_texture", "f_roundness")
    ys = [1 if row["label"] == "compact" else 0 for row in train]
    xt = [[row[name] for name in features] for row in train]
    xs = [[row[name] for name in features] for row in test]
    mu = [sum(col) / len(xt) for col in zip(*xt)]
    var = [sum((row[j] - mu[j]) ** 2 for row in xt) / len(xt) for j in range(3)]
    sd = [math.sqrt(v) if v > 1e-12 else 1.0 for v in var]

    def norm(rows):
        return [[(row[j] - mu[j]) / sd[j] for j in range(3)] for row in rows]

    xt, xs = norm(xt), norm(xs)
    w = [0.0, 0.0, 0.0]
    b = 0.0
    for _ in range(500):
        gw, gb = [0.0, 0.0, 0.0], 0.0
        for row, y in zip(xt, ys):
            p = _sigmoid(sum(wj * xj for wj, xj in zip(w, row)) + b)
            err = p - y
            for j in range(3):
                gw[j] += err * row[j]
            gb += err
        scale = 1.0 / len(xt)
        w = [(wj - 0.35 * (gw[j] * scale + 0.1 * wj)) for j, wj in enumerate(w)]
        b -= 0.35 * gb * scale
    return [1 if _sigmoid(sum(wj * xj for wj, xj in zip(w, row)) + b) >= 0.5 else 0 for row in xs]


def _balanced_accuracy(truth: list[int], pred: list[int]) -> float:
    recalls = []
    for label in (0, 1):
        idx = [i for i, value in enumerate(truth) if value == label]
        if not idx:
            continue
        recalls.append(sum(pred[i] == label for i in idx) / len(idx))
    return sum(recalls) / len(recalls)


def morphology_rows(shared_batch: bool) -> list[dict]:
    rows = []
    for sample in SAMPLES:
        donor = DONORS[sample]
        compact = donor in {"D1", "D2"}
        # Small donor-level noise. The signal is the label, not a microscopy claim.
        jitter = {"D1": 0.02, "D2": -0.01, "D3": 0.03, "D4": -0.02}[donor]
        replicate = 0.01 if sample.endswith("1") or sample.endswith("3") else -0.01
        rows.append({
            "sample_id": sample,
            "label": "compact" if compact else "irregular",
            "donor_id": donor,
            "batch_id": "B_SHARED" if shared_batch else f"B_{donor}",
            "f_area": (0.72 if compact else 0.28) + jitter,
            "f_texture": (0.22 if compact else 0.68) + jitter,
            "f_roundness": (0.80 if compact else 0.35) + replicate,
        })
    return rows


def evaluate_morphology(rows: list[dict]) -> dict:
    comps = _components(rows)
    groups = {}
    for i, comp in enumerate(comps):
        groups.setdefault(comp, []).append(i)
    if len(groups) < 2:
        return {
            "status": "refused",
            "reason": "donor-or-batch grouping collapsed to one component; joint holdout is impossible",
            "n_components": 1,
        }
    truth, pred_model, pred_majority = [], [], []
    for members in groups.values():
        train = [row for i, row in enumerate(rows) if i not in members]
        test = [rows[i] for i in members]
        labels = [1 if row["label"] == "compact" else 0 for row in train]
        if len(set(labels)) < 2:
            return {"status": "refused", "reason": "a training fold lost a class", "n_components": len(groups)}
        majority = 1 if sum(labels) >= len(labels) - sum(labels) else 0
        truth.extend(1 if row["label"] == "compact" else 0 for row in test)
        pred_model.extend(_logistic_predict(train, test))
        pred_majority.extend([majority] * len(test))
    return {
        "status": "scored",
        "n_components": len(groups),
        "logistic_balanced_accuracy": _balanced_accuracy(truth, pred_model),
        "majority_balanced_accuracy": _balanced_accuracy(truth, pred_majority),
    }


def protocol_fixture() -> dict:
    """Encoded GiWi window check. Not a license to run the protocol."""
    return {
        "id": "giwi_cardiac",
        "source": "10.1038/nprot.2012.150",
        "chir_uM": 6.0,
        "chir_window": [2.0, 12.0],
        "endpoint_count": 1,
        "steps_after_endpoint": 0,
        "qc_gates": ["troponin fraction recorded"],
    }


def validate_protocol(protocol: dict) -> list[str]:
    errors = []
    low, high = protocol["chir_window"]
    if not low <= protocol["chir_uM"] <= high:
        errors.append(f"CHIR {protocol['chir_uM']} is outside {low}-{high}")
    if protocol["endpoint_count"] != 1 or protocol["steps_after_endpoint"] != 0:
        errors.append("endpoint must be unique and last")
    gates = [gate.strip() for gate in protocol["qc_gates"] if str(gate).strip()]
    if not gates:
        errors.append("explicit QC gate required")
    return errors


def run(out: Path) -> dict:
    if out.exists():
        raise ValueError(f"refusing to overwrite {out}")
    out.mkdir(parents=False, exist_ok=False)
    matrix, meta = expression_tables()
    _write_csv(out / "expression.csv", ["gene", *SAMPLES], matrix)
    _write_csv(out / "samples.csv", ["sample", "group"], meta)
    expression_contrast(
        ["--matrix", str(out / "expression.csv"), "--samples", str(out / "samples.csv"),
         "--reference", "young", "--comparison", "older", "--pseudocount", "1",
         "--out", str(out / "expression-contrast")],
        lambda *_args: None,
    )
    registered = contrast_rows(matrix, GROUPS)
    flipped = contrast_rows(matrix, swapped_groups())
    by_gene = {row["gene"]: row for row in registered}
    nested = evaluate_morphology(morphology_rows(False))
    shared = evaluate_morphology(morphology_rows(True))
    protocol = protocol_fixture()
    protocol_errors = validate_protocol(protocol)
    (out / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    summary = {
        "estimand": estimand(registered),
        "estimand_swapped_labels": estimand(flipped),
        "flip_direction_stable": _direction_stable(matrix, "FLIP_A"),
        "panel_q": {gene: by_gene[gene]["q"] for gene in PANEL},
        "null_q": {gene: by_gene[gene]["q"] for gene in NULL},
        "morphology_nested": nested,
        "morphology_shared_batch": shared,
        "protocol_errors": protocol_errors,
        "aliasing": "age is perfectly nested in donor on this fixture",
        "not": "Not a biological age effect, not a media recipe, and not a senescence call.",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    phenotype = {
        "expression_csv_sha256": _sha(out / "expression.csv"),
        "samples_csv_sha256": _sha(out / "samples.csv"),
        "expression_contrast_manifest_sha256": _sha(out / "expression-contrast" / "manifest.json"),
        "summary_sha256": _sha(out / "summary.json"),
        "protocol_sha256": _sha(out / "protocol.json"),
    }
    (out / "phenotype_manifest.json").write_text(json.dumps(phenotype, indent=2) + "\n", encoding="utf-8")
    link = {
        "phenotype_manifest_sha256": _sha(out / "phenotype_manifest.json"),
        "cite_in": "geroscience-compound-atlas",
        "instruction": (
            "Record phenotype_manifest_sha256 next to any atlas export that cites this table. "
            "The hash identifies bytes. It is not a pChEMBL value or an evidence grade."
        ),
    }
    (out / "atlas_link.json").write_text(json.dumps(link, indent=2) + "\n", encoding="utf-8")
    checks = {
        "estimand_passes": summary["estimand"] > 0.5,
        "swapped_label_negative_control_passes": summary["estimand_swapped_labels"] < -0.5,
        "flip_gene_is_unstable": summary["flip_direction_stable"] is False,
        "nested_logistic_beats_majority": (
            nested["status"] == "scored"
            and nested["logistic_balanced_accuracy"] > nested["majority_balanced_accuracy"]
        ),
        "shared_batch_refused": shared["status"] == "refused",
        "protocol_fixture_accepted": protocol_errors == [],
    }
    (out / "checks.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    (out / "REPORT.md").write_text(_report(summary, checks, link), encoding="utf-8")
    return {"summary": summary, "checks": checks, "atlas_link": link}


def _direction_stable(matrix: list[list], gene: str) -> bool:
    row = next(item for item in matrix if item[0] == gene)
    young = [float(v) for v, sample in zip(row[1:], SAMPLES) if GROUPS[sample] == "young"]
    older = [float(v) for v, sample in zip(row[1:], SAMPLES) if GROUPS[sample] == "older"]

    def effect(a, b):
        return math.log2(sum(b) / len(b) + 1) - math.log2(sum(a) / len(a) + 1)

    full = effect(young, older)
    loo = []
    for i in range(len(young)):
        loo.append(effect(young[:i] + young[i + 1:], older))
    for i in range(len(older)):
        loo.append(effect(young, older[:i] + older[i + 1:]))
    if full > 0:
        return min(loo) > 0
    if full < 0:
        return max(loo) < 0
    return False


def _report(summary: dict, checks: dict, link: dict) -> str:
    lines = [
        "# Frozen cohort report",
        "",
        "Synthetic software check defined in PROTOCOL.md. Age is aliased with donor.",
        "Do not read a log2 ratio as rejuvenation.",
        "",
        f"- Estimand (panel minus null): {summary['estimand']:.4f}",
        f"- Estimand with swapped labels: {summary['estimand_swapped_labels']:.4f}",
        f"- FLIP_A direction stable: {summary['flip_direction_stable']}",
        f"- Nested morphology: {json.dumps(summary['morphology_nested'])}",
        f"- Shared-batch morphology: {json.dumps(summary['morphology_shared_batch'])}",
        f"- Protocol fixture errors: {summary['protocol_errors'] or 'none'}",
        "",
        "## Checks",
        "",
    ]
    for name, ok in checks.items():
        lines.append(f"- {'pass' if ok else 'fail'}: {name}")
    lines += [
        "",
        "## Atlas link",
        "",
        f"Phenotype manifest SHA-256: `{link['phenotype_manifest_sha256']}`",
        "",
        link["instruction"],
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the frozen synthetic cohort check")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args.out)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    failed = [name for name, ok in result["checks"].items() if not ok]
    if failed:
        raise SystemExit(f"pre-registered checks failed: {', '.join(failed)}")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
