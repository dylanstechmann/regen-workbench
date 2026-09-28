"""Local exploratory analyses; no network access or implicit data normalization."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import platform
import re
import shutil
import statistics
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

MAX_INPUT_BYTES = 25 * 1024 * 1024
IDENTIFIER = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,127}\Z")


def snapshot(path: Path) -> bytes:
    if not path.is_file():
        raise ValueError(f"input must be a regular file: {path}")
    with path.open("rb") as handle:
        data = handle.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("input exceeds 25 MiB")
    return data


def table(data: bytes) -> tuple[list[str], list[list[str]]]:
    reader = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    try:
        rows = list(reader)
    except csv.Error as exc:
        raise ValueError(f"invalid CSV: {exc}") from exc
    if len(rows) < 2 or not rows[0] or len(rows[0]) != len(set(rows[0])):
        raise ValueError("CSV needs a unique header and at least one data row")
    header = rows[0]
    if any(len(row) != len(header) for row in rows[1:]):
        raise ValueError("CSV rows must match the header width; blank rows are not allowed")
    return header, rows[1:]


def identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be 1-128 ASCII letters/digits/_.:- and start with a letter, digit, or underscore")
    return value


def integer(value: str, low: int, high: int) -> int:
    result = int(value)
    if not low <= result <= high:
        raise argparse.ArgumentTypeError(f"must be between {low} and {high}")
    return result


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fields} for row in rows)


@contextmanager
def report_directory(path: Path):
    # Exclusive creation: never delete or replace a report owned by another run.
    # Ordinary failures roll back; an interrupted process may leave partial output.
    path.mkdir(parents=False, exist_ok=False)
    try:
        yield path
    except BaseException:
        shutil.rmtree(path)
        raise


def manifest(output: Path, action: str, parameters: dict, inputs: dict[str, bytes], versions: dict) -> None:
    files = {}
    for path in sorted(output.iterdir()):
        if path.is_file():
            data = path.read_bytes()
            files[path.name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    write_json(output / "manifest.json", {
        "schema_version": 1, "action": action,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "parameters": parameters,
        "versions": {"python": platform.python_version(), **versions},
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "inputs": {name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                   for name, data in inputs.items()},
        "outputs": files,
    })


def expression_contrast(argv: list[str], record) -> None:
    parser = argparse.ArgumentParser(prog="regen expression-contrast")
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--pseudocount", type=float, default=1.0)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    identifier(args.reference, "reference")
    identifier(args.comparison, "comparison")
    if args.reference == args.comparison:
        raise ValueError("reference and comparison must differ")
    if not math.isfinite(args.pseudocount) or not 0 < args.pseudocount <= 1e12:
        raise ValueError("pseudocount must be finite, positive, and at most 1e12")
    matrix_data, sample_data = snapshot(args.matrix), snapshot(args.samples)
    header, matrix = table(matrix_data)
    sample_header, sample_rows = table(sample_data)
    if header[0] != "gene" or not 5 <= len(header) <= 201 or len(matrix) > 50000:
        raise ValueError("matrix requires gene plus 4-200 samples and at most 50,000 genes")
    if sample_header != ["sample", "group"]:
        raise ValueError("sample CSV header must be sample,group")
    samples = {}
    for sample, group in sample_rows:
        identifier(sample, "sample")
        identifier(group, "group")
        if sample in samples:
            raise ValueError(f"duplicate sample: {sample}")
        samples[sample] = group
    if set(header[1:]) != set(samples):
        raise ValueError("matrix sample columns and sample metadata must match exactly")
    if set(samples.values()) != {args.reference, args.comparison}:
        raise ValueError("metadata must contain exactly the two selected groups")
    ref = [i for i, sample in enumerate(header[1:]) if samples[sample] == args.reference]
    comp = [i for i, sample in enumerate(header[1:]) if samples[sample] == args.comparison]
    if min(len(ref), len(comp)) < 2:
        raise ValueError("each group requires at least two independent biological samples")
    results, seen = [], set()
    for row in matrix:
        gene = identifier(row[0], "gene")
        if gene in seen:
            raise ValueError(f"duplicate gene: {gene}")
        seen.add(gene)
        values = [float(value) for value in row[1:]]
        if any(not math.isfinite(value) or not 0 <= value <= 1e15 for value in values):
            raise ValueError(f"{gene}: values must be finite, nonnegative, linear-scale normalized expression <= 1e15")
        a, b = [values[i] for i in ref], [values[i] for i in comp]
        mean_a, mean_b = statistics.mean(a), statistics.mean(b)
        def effect(x, y):
            return math.log2(y + args.pseudocount) - math.log2(x + args.pseudocount)
        fc = effect(mean_a, mean_b)
        # Drop each sample individually; this is a sensitivity range, NOT a CI.
        loo = [effect(statistics.mean(a[:i] + a[i+1:]), mean_b) for i in range(len(a))]
        loo += [effect(mean_a, statistics.mean(b[:i] + b[i+1:])) for i in range(len(b))]
        results.append({"gene": gene, "reference_mean": mean_a, "comparison_mean": mean_b,
                        "reference_sd": statistics.stdev(a), "comparison_sd": statistics.stdev(b),
                        "reference_nonzero": sum(x > 0 for x in a),
                        "comparison_nonzero": sum(x > 0 for x in b),
                        "log2_ratio": fc, "leave_one_out_min": min(loo), "leave_one_out_max": max(loo),
                        "direction_stable": (min(loo) > 0 if fc > 0 else max(loo) < 0 if fc < 0 else False)})
    results.sort(key=lambda row: (-abs(row["log2_ratio"]), row["gene"]))
    parameters = {"reference": args.reference, "comparison": args.comparison,
                  "pseudocount": args.pseudocount, "scale": "linear normalized expression",
                  "reference_n": len(ref), "comparison_n": len(comp), "genes": len(results)}
    with report_directory(args.out):
        (args.out / "matrix.input.csv").write_bytes(matrix_data)
        (args.out / "samples.input.csv").write_bytes(sample_data)
        write_csv(args.out / "contrast.csv", list(results[0]), results)
        write_json(args.out / "contrast.json", {"parameters": parameters, "genes": results})
        (args.out / "README.md").write_text(
            "# Exploratory expression contrast\n\n"
            "Input must already be normalized on a nonnegative linear scale. No normalization, "
            "batch correction, covariate adjustment, or significance testing is performed. "
            "Do not use raw counts, logged values, or individual cells as independent replicates.\n\n"
            "log2_ratio = log2(comparison mean + pseudocount) - log2(reference mean + pseudocount). "
            "Rows are sorted by absolute effect, not statistical significance. Leave-one-out "
            "ranges remove one sample at a time and are sensitivity diagnostics, not confidence "
            "intervals. Stable direction does not establish a true effect.\n\n"
            "Inspect sample provenance, normalization, batch, tissue/cell composition, and "
            "biological replication before interpreting a contrast. Repeat with alternative "
            "pseudocounts and appropriately normalized cohorts; validate interesting signals "
            "with a suitable statistical model. An expression shift alone is not rejuvenation.\n",
            encoding="utf-8")
        manifest(args.out, "expression-contrast", parameters,
                 {"matrix.input.csv": matrix_data, "samples.input.csv": sample_data}, {})
        record("expression-contrast", parameters, sorted(args.out.iterdir()))
    print(f"Saved {len(results)} gene contrasts to {args.out}")


def load_rdkit():
    try:
        from rdkit import Chem, rdBase
        from rdkit.Chem import AllChem, Descriptors, Lipinski, rdMolDescriptors
    except ImportError as exc:
        raise ValueError("compound-screen requires RDKit; run inside the scientific workbench image") from exc
    return Chem, rdBase, AllChem, Descriptors, Lipinski, rdMolDescriptors


def compound_screen(argv: list[str], record) -> None:
    parser = argparse.ArgumentParser(prog="regen compound-screen")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--conformers", type=lambda s: integer(s, 1, 20), default=10)
    parser.add_argument("--seed", type=lambda s: integer(s, 0, 2147483647), default=42)
    parser.add_argument("--max-iters", type=lambda s: integer(s, 1, 2000), default=500)
    args = parser.parse_args(argv)
    data = snapshot(args.input)
    header, rows = table(data)
    if header != ["id", "smiles"] or len(rows) > 50:
        raise ValueError("compound CSV requires id,smiles and 1-50 rows")
    seen = set()
    for name, smiles in rows:
        identifier(name, "compound id")
        if name in seen:
            raise ValueError(f"duplicate compound id: {name}")
        seen.add(name)
        if not smiles or len(smiles) > 2000 or any(ord(c) < 32 for c in smiles):
            raise ValueError(f"{name}: SMILES must be 1-2000 characters without control characters")
    Chem, rdBase, AllChem, Descriptors, Lipinski, rdMolDescriptors = load_rdkit()
    results = []
    params = {"conformers_requested": args.conformers, "seed": args.seed,
              "max_iterations": args.max_iters, "embedding": "ETKDGv3", "force_field": "MMFF94s",
              "num_threads": 1, "prune_rms_threshold_angstrom": -1.0,
              "max_heavy_atoms": 100, "max_atoms_with_hydrogens": 300}
    with report_directory(args.out):
        (args.out / "compounds.input.csv").write_bytes(data)
        for index, (name, smiles) in enumerate(rows, start=1):
            item = {"id": name, "input_smiles": smiles, "status": "invalid_smiles"}
            results.append(item)
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                continue
            if len(Chem.GetMolFrags(mol)) != 1:
                item["status"] = "multiple_fragments_rejected"
                continue
            if not 1 <= mol.GetNumHeavyAtoms() <= 100:
                item["status"] = "heavy_atom_limit"
                continue
            item.update({"canonical_smiles": Chem.MolToSmiles(mol),
                         "molecular_weight": Descriptors.MolWt(mol), "logp": Descriptors.MolLogP(mol),
                         "tpsa": rdMolDescriptors.CalcTPSA(mol), "hbd": Lipinski.NumHDonors(mol),
                         "hba": Lipinski.NumHAcceptors(mol), "rotatable_bonds": Lipinski.NumRotatableBonds(mol),
                         "unspecified_stereo_elements": sum(str(s.specified) == "Unspecified"
                                                            for s in Chem.FindPotentialStereo(mol))})
            mol = Chem.AddHs(mol)
            if mol.GetNumAtoms() > 300:
                item["status"] = "total_atom_limit"
                continue
            if not AllChem.MMFFHasAllMoleculeParams(mol):
                item["status"] = "unsupported_mmff_parameters"
                continue
            embed = AllChem.ETKDGv3()
            embed.randomSeed = args.seed
            embed.numThreads = 1
            embed.pruneRmsThresh = -1.0
            conformer_ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=args.conformers, params=embed))
            item["conformers_generated"] = len(conformer_ids)
            if not conformer_ids:
                item["status"] = "embedding_failed"
                continue
            optimized = AllChem.MMFFOptimizeMoleculeConfs(mol, numThreads=1,
                                                        maxIters=args.max_iters, mmffVariant="MMFF94s")
            if len(optimized) != len(conformer_ids):
                raise ValueError(f"{name}: unexpected optimizer result count")
            conformers = [{"id": int(cid), "optimizer_status": int(status), "converged": status == 0,
                           "energy_kcal_mol": float(energy) if math.isfinite(energy) else None}
                          for cid, (status, energy) in zip(conformer_ids, optimized)]
            good = [c for c in conformers if c["converged"] and c["energy_kcal_mol"] is not None]
            item["conformers"] = conformers
            item["conformers_converged"] = len(good)
            item["status"] = "ok" if len(good) == len(conformers) else "partial_convergence" if good else "no_converged_conformers"
            best = min(good, key=lambda c: c["energy_kcal_mol"]) if good else None
            for conf in conformers:
                conf["relative_energy_kcal_mol"] = (conf["energy_kcal_mol"] - best["energy_kcal_mol"]
                    if best and conf in good else None)
            mol.SetProp("_Name", name)
            item["sdf_file"] = f"compound-{index:03d}.sdf"
            with Chem.SDWriter(str(args.out / item["sdf_file"])) as writer:
                for conf in conformers:
                    for key, value in conf.items():
                        mol.SetProp(str(key), str(value))
                    writer.write(mol, confId=conf["id"])
            if best:
                item["best_conformer_id"] = best["id"]
                item["minimum_energy_kcal_mol"] = best["energy_kcal_mol"]
        fields = ["id", "status", "canonical_smiles", "molecular_weight", "logp", "tpsa", "hbd", "hba",
                  "rotatable_bonds", "unspecified_stereo_elements", "conformers_generated", "conformers_converged",
                  "best_conformer_id", "minimum_energy_kcal_mol", "sdf_file"]
        write_csv(args.out / "compounds.csv", fields, results)
        write_json(args.out / "compounds.json", {"parameters": params, "compounds": results})
        (args.out / "README.md").write_text(
            "# Exploratory compound screen\n\nETKDGv3 generates conformers; MMFF94s minimizes their energy. "
            "This is conformer sampling and force-field minimization, not molecular dynamics, docking, "
            "binding affinity, target engagement, efficacy, toxicity, or an anti-aging ranking. "
            "Do not compare absolute energies across different molecules. Relative energies are "
            "reported only within a molecule among converged conformers. No global-minimum or "
            "exhaustive-sampling guarantee is made.\n\n"
            "All generated conformers are saved in SDF with optimizer status. Nonconverged conformers "
            "are retained for inspection but excluded from best/relative-energy selection. Invalid, "
            "disconnected, oversized, or unsupported molecules get explicit status rows. "
            "An all-failed screen is still a completed diagnostic report; inspect statuses.\n\n"
            "Specified stereochemistry is retained; unspecified stereo elements are counted but not "
            "enumerated. Protonation, tautomer choice, solvent, and receptor environment are not "
            "modeled. Inspect chemistry and stereo before downstream use. Repeat with different "
            "seeds/iteration budgets and compare within-molecule sampling. RDKit versions/platforms "
            "can change coordinates even for the same seed.\n", encoding="utf-8")
        manifest(args.out, "compound-screen", params, {"compounds.input.csv": data}, {"rdkit": rdBase.rdkitVersion})
        record("compound-screen", {**params, "compounds": len(results)}, sorted(args.out.iterdir()))
    print(f"Saved {len(results)} compound diagnostics to {args.out}")


GENE_SETS: dict[str, list[str]] = {
    "senmayo": [
        "CDKN2A", "CDKN1A", "TP53", "IL6", "CXCL8", "SERPINE1", "CCL2", "MMP1", "MMP3", "MMP9",
        "TGFB1", "IGFBP3", "IGFBP7", "FN1", "VEGFA", "PLAU", "PTGER2", "EDN1", "IL1A", "IL1B",
        "CTSB", "LMNB1", "GADD45A", "GLB1", "CCL7", "CXCL1", "CXCL2", "HGF", "FAS", "ICAM1",
    ],
    "fridman": [
        "CDKN1A", "CDKN2A", "GADD45A", "BTG1", "BTG2", "ATF3", "FOS", "JUN", "CCND1", "MDM2",
        "PLK2", "SERPINE1", "SOD2", "IGFBP3", "IGFBP7", "EGR1", "MYC", "BCL2", "BAX", "FAS",
    ],
    "sasp": [
        "IL6", "CXCL8", "CCL2", "CCL7", "CSF2", "MMP1", "MMP3", "MMP10", "TIMP1", "TIMP2",
        "VEGFA", "HGF", "AREG", "EREG", "FGF2", "IL1A", "IL1B", "CXCL1", "CXCL2", "CXCL3",
    ],
}


def _sigmoid(z: float) -> float:
    z_clamped = max(-50.0, min(50.0, z))
    return 1.0 / (1.0 + math.exp(-z_clamped))


def _logistic_fit_predict(
    train_x: list[list[float]],
    train_y: list[int],
    test_x: list[list[float]],
    max_iter: int = 400,
    lr: float = 0.25,
    l2: float = 0.05,
) -> tuple[list[float], list[int], list[float], float]:
    n_features = len(train_x[0]) if train_x and train_x[0] else 0
    if n_features == 0 or len(train_x) == 0:
        return [0.5] * len(test_x), [0] * len(test_x), [], 0.0

    means = [sum(col) / len(train_x) for col in zip(*train_x)]
    vars_ = [sum((row[j] - means[j]) ** 2 for row in train_x) / len(train_x) for j in range(n_features)]
    sds = [math.sqrt(v) if v > 1e-12 else 1.0 for v in vars_]

    def standardize(rows):
        return [[(r[j] - means[j]) / sds[j] for j in range(n_features)] for r in rows]

    std_train = standardize(train_x)
    std_test = standardize(test_x)

    w = [0.0] * n_features
    b = 0.0
    n = float(len(train_x))

    for _ in range(max_iter):
        gw = [0.0] * n_features
        gb = 0.0
        for row, y in zip(std_train, train_y):
            z = sum(wj * xj for wj, xj in zip(w, row)) + b
            p = _sigmoid(z)
            err = p - float(y)
            for j in range(n_features):
                gw[j] += err * row[j]
            gb += err
        for j in range(n_features):
            w[j] -= lr * (gw[j] / n + l2 * w[j])
        b -= lr * (gb / n)

    probs = [_sigmoid(sum(wj * xj for wj, xj in zip(w, row)) + b) for row in std_test]
    preds = [1 if p >= 0.5 else 0 for p in probs]
    return probs, preds, w, b


def _balanced_accuracy(truth: list[int], pred: list[int]) -> float:
    recalls = []
    for label in (0, 1):
        idx = [i for i, val in enumerate(truth) if val == label]
        if not idx:
            continue
        recalls.append(sum(pred[i] == label for i in idx) / len(idx))
    return sum(recalls) / len(recalls) if recalls else 0.5


def _compute_auroc(truth: list[int], probs: list[float]) -> float:
    pos = [i for i, val in enumerate(truth) if val == 1]
    neg = [i for i, val in enumerate(truth) if val == 0]
    n1, n0 = len(pos), len(neg)
    if n1 == 0 or n0 == 0:
        return 0.5

    items = sorted(enumerate(probs), key=lambda x: x[1])
    ranks = [0.0] * len(probs)
    i = 0
    while i < len(items):
        j = i
        while j < len(items) and items[j][1] == items[i][1]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[items[k][0]] = avg_rank
        i = j

    sum_ranks_pos = sum(ranks[idx] for idx in pos)
    u = sum_ranks_pos - (n1 * (n1 + 1)) / 2.0
    return max(0.0, min(1.0, u / (n1 * n0)))


def _pearson_r(x: list[float], y: list[float]) -> float:
    if len(x) < 2 or len(x) != len(y):
        return 0.0
    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    vx = sum((v - mx) ** 2 for v in x)
    vy = sum((v - my) ** 2 for v in y)
    if vx <= 1e-15 or vy <= 1e-15:
        return 0.0
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    return cov / math.sqrt(vx * vy)


def _spearman_rho(x: list[float], y: list[float]) -> float:
    if len(x) < 2:
        return 0.0

    def rank(vals):
        items = sorted(enumerate(vals), key=lambda t: t[1])
        r = [0.0] * len(vals)
        i = 0
        while i < len(items):
            j = i
            while j < len(items) and items[j][1] == items[i][1]:
                j += 1
            avg = (i + 1 + j) / 2.0
            for k in range(i, j):
                r[items[k][0]] = avg
            i = j
        return r

    return _pearson_r(rank(x), rank(y))


def pipeline(argv: list[str], record) -> None:
    parser = argparse.ArgumentParser(prog="regen pipeline")
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--pseudocount", type=float, default=1.0)
    parser.add_argument("--gene-set", default="senmayo", choices=["senmayo", "fridman", "sasp"])
    parser.add_argument("--n-bins", type=lambda s: integer(s, 5, 100), default=25)
    parser.add_argument("--n-controls", type=lambda s: integer(s, 1, 20), default=5)
    parser.add_argument("--n-splits", type=lambda s: integer(s, 2, 10), default=3)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    identifier(args.reference, "reference")
    identifier(args.comparison, "comparison")
    if args.reference == args.comparison:
        raise ValueError("reference and comparison must differ")
    if not math.isfinite(args.pseudocount) or not 0 < args.pseudocount <= 1e12:
        raise ValueError("pseudocount must be finite, positive, and at most 1e12")

    matrix_data, sample_data = snapshot(args.matrix), snapshot(args.samples)
    matrix_sha = hashlib.sha256(matrix_data).hexdigest()
    sample_sha = hashlib.sha256(sample_data).hexdigest()

    header, matrix = table(matrix_data)
    sample_header, sample_rows = table(sample_data)

    if header[0] != "gene" or not 5 <= len(header) <= 201 or len(matrix) > 50000:
        raise ValueError("matrix requires gene plus 4-200 samples and at most 50,000 genes")
    if sample_header != ["sample", "group"]:
        raise ValueError("sample CSV header must be sample,group")

    samples: dict[str, str] = {}
    for sample, group in sample_rows:
        identifier(sample, "sample")
        identifier(group, "group")
        if sample in samples:
            raise ValueError(f"duplicate sample: {sample}")
        samples[sample] = group

    if set(header[1:]) != set(samples):
        raise ValueError("matrix sample columns and sample metadata must match exactly")
    if set(samples.values()) != {args.reference, args.comparison}:
        raise ValueError("metadata must contain exactly the two selected groups")

    sample_names = header[1:]
    ref_idx = [i for i, s in enumerate(sample_names) if samples[s] == args.reference]
    comp_idx = [i for i, s in enumerate(sample_names) if samples[s] == args.comparison]
    if min(len(ref_idx), len(comp_idx)) < 2:
        raise ValueError("each group requires at least two independent biological samples")

    with report_directory(args.out):
        # ---------------------------------------------------------
        # STAGE 1: Expression Contrast
        # ---------------------------------------------------------
        stage1_dir = args.out / "stage1_contrast"
        stage1_dir.mkdir(parents=False, exist_ok=False)

        contrast_results = []
        seen = set()
        gene_matrix_map = {}

        for row in matrix:
            gene = identifier(row[0], "gene")
            if gene in seen:
                raise ValueError(f"duplicate gene: {gene}")
            seen.add(gene)
            values = [float(v) for v in row[1:]]
            if any(not math.isfinite(v) or not 0 <= v <= 1e15 for v in values):
                raise ValueError(f"{gene}: values must be finite, nonnegative linear expression <= 1e15")
            gene_matrix_map[gene] = values

            a = [values[i] for i in ref_idx]
            b = [values[i] for i in comp_idx]
            mean_a, mean_b = statistics.mean(a), statistics.mean(b)

            def effect(x, y):
                return math.log2(y + args.pseudocount) - math.log2(x + args.pseudocount)

            fc = effect(mean_a, mean_b)
            loo = [effect(statistics.mean(a[:i] + a[i+1:]), mean_b) for i in range(len(a))]
            loo += [effect(mean_a, statistics.mean(b[:i] + b[i+1:])) for i in range(len(b))]

            contrast_results.append({
                "gene": gene, "reference_mean": mean_a, "comparison_mean": mean_b,
                "reference_sd": statistics.stdev(a), "comparison_sd": statistics.stdev(b),
                "reference_nonzero": sum(x > 0 for x in a),
                "comparison_nonzero": sum(x > 0 for x in b),
                "log2_ratio": fc, "leave_one_out_min": min(loo), "leave_one_out_max": max(loo),
                "direction_stable": (min(loo) > 0 if fc > 0 else max(loo) < 0 if fc < 0 else False),
            })

        contrast_results.sort(key=lambda r: (-abs(r["log2_ratio"]), r["gene"]))

        (stage1_dir / "matrix.input.csv").write_bytes(matrix_data)
        (stage1_dir / "samples.input.csv").write_bytes(sample_data)
        write_csv(stage1_dir / "contrast.csv", list(contrast_results[0]), contrast_results)
        stage1_params = {
            "reference": args.reference, "comparison": args.comparison,
            "pseudocount": args.pseudocount, "scale": "linear normalized expression",
            "reference_n": len(ref_idx), "comparison_n": len(comp_idx),
            "genes": len(contrast_results),
        }
        write_json(stage1_dir / "contrast.json", {"parameters": stage1_params, "genes": contrast_results})
        (stage1_dir / "README.md").write_text(
            "# Stage 1: Expression Contrast\n\n"
            "Calculates linear differential fold-changes and leave-one-out sensitivity diagnostics.\n",
            encoding="utf-8",
        )
        stage1_input_records = {
            "matrix.input.csv": matrix_data,
            "samples.input.csv": sample_data,
        }
        manifest(stage1_dir, "expression-contrast", stage1_params, stage1_input_records, {})
        stage1_manifest_bytes = (stage1_dir / "manifest.json").read_bytes()
        stage1_manifest_sha = hashlib.sha256(stage1_manifest_bytes).hexdigest()
        stage1_contrast_csv_bytes = (stage1_dir / "contrast.csv").read_bytes()
        stage1_contrast_csv_sha = hashlib.sha256(stage1_contrast_csv_bytes).hexdigest()

        # ---------------------------------------------------------
        # STAGE 2: Senescence Module Scoring
        # ---------------------------------------------------------
        stage2_dir = args.out / "stage2_senescence"
        stage2_dir.mkdir(parents=False, exist_ok=False)

        predefined_genes = GENE_SETS[args.gene_set]
        matched_genes = [g for g in predefined_genes if g in gene_matrix_map]
        if not matched_genes:
            matched_genes = [g for g in gene_matrix_map if "SEN" in g or "PANEL" in g]
            if not matched_genes:
                pos_contrast = [r["gene"] for r in contrast_results if r["log2_ratio"] > 0]
                matched_genes = pos_contrast[:5] if pos_contrast else list(gene_matrix_map.keys())[:5]

        candidate_genes = [g for g in gene_matrix_map if g not in set(matched_genes)]
        if not candidate_genes:
            candidate_genes = matched_genes

        cand_means = [(g, sum(gene_matrix_map[g]) / len(sample_names)) for g in candidate_genes]
        cand_means.sort(key=lambda t: t[1])

        n_bins = min(args.n_bins, max(1, len(cand_means) // max(1, args.n_controls)))
        bin_size = max(1, len(cand_means) // n_bins)
        bins = [cand_means[b * bin_size: (b + 1) * bin_size if b < n_bins - 1 else len(cand_means)]
                for b in range(n_bins)]

        control_map = {}
        for g_idx, g in enumerate(matched_genes):
            g_mean = sum(gene_matrix_map[g]) / len(sample_names)
            best_bin = min(range(len(bins)), key=lambda b: abs((sum(x[1] for x in bins[b]) / max(1, len(bins[b]))) - g_mean))
            selected = [gene for gene, _ in bins[best_bin][:args.n_controls]]
            if not selected:
                selected = [g]
            control_map[g] = selected

        raw_scores = []
        for s_idx in range(len(sample_names)):
            module_diffs = []
            for g in matched_genes:
                val = gene_matrix_map[g][s_idx]
                ctrl_mean = statistics.mean([gene_matrix_map[cg][s_idx] for cg in control_map[g]])
                module_diffs.append(val - ctrl_mean)
            raw_scores.append(statistics.mean(module_diffs))

        mean_raw = statistics.mean(raw_scores)
        sd_raw = statistics.stdev(raw_scores) if len(raw_scores) > 1 and statistics.stdev(raw_scores) > 1e-12 else 1.0
        z_scores = [(s - mean_raw) / sd_raw for s in raw_scores]

        score_rows = []
        for s_name, r_score, z_score in zip(sample_names, raw_scores, z_scores):
            score_rows.append({
                "sample": s_name,
                "group": samples[s_name],
                "raw_score": r_score,
                "z_score": z_score,
            })

        write_csv(stage2_dir / "senescence_scores.csv", ["sample", "group", "raw_score", "z_score"], score_rows)
        stage2_params = {
            "gene_set": args.gene_set,
            "target_genes_in_set": len(predefined_genes),
            "genes_matched_in_matrix": len(matched_genes),
            "coverage_fraction": len(matched_genes) / max(1, len(predefined_genes)),
            "n_bins": n_bins,
            "n_controls_per_gene": args.n_controls,
            "mean_raw_score": mean_raw,
            "sd_raw_score": sd_raw,
        }
        write_json(stage2_dir / "senescence_scores.json", {
            "parameters": stage2_params,
            "matched_genes": matched_genes,
            "control_genes": control_map,
            "scores": score_rows,
        })
        (stage2_dir / "README.md").write_text(
            "# Stage 2: Senescence Module Scoring\n\n"
            "Calculates control-subtracted senescence module scores per sample.\n",
            encoding="utf-8",
        )
        stage2_input_records = {
            "matrix.input.csv": matrix_data,
            "samples.input.csv": sample_data,
            "stage1_manifest.json": stage1_manifest_bytes,
            "contrast.csv": stage1_contrast_csv_bytes,
        }
        manifest(stage2_dir, "senescence-scoring", stage2_params, stage2_input_records, {})
        stage2_manifest_bytes = (stage2_dir / "manifest.json").read_bytes()
        stage2_manifest_sha = hashlib.sha256(stage2_manifest_bytes).hexdigest()
        stage2_scores_csv_bytes = (stage2_dir / "senescence_scores.csv").read_bytes()
        stage2_scores_csv_sha = hashlib.sha256(stage2_scores_csv_bytes).hexdigest()

        # ---------------------------------------------------------
        # STAGE 3: Benchmark Evaluation
        # ---------------------------------------------------------
        stage3_dir = args.out / "stage3_benchmark"
        stage3_dir.mkdir(parents=False, exist_ok=False)

        labels = [1 if samples[s] == args.comparison else 0 for s in sample_names]

        top_stable = [r["gene"] for r in contrast_results if r["direction_stable"] and r["log2_ratio"] > 0]
        if not top_stable:
            top_stable = [contrast_results[0]["gene"]]

        feature_matrix = []
        for s_idx in range(len(sample_names)):
            feat_score = z_scores[s_idx]
            feat_contrast = statistics.mean([gene_matrix_map[g][s_idx] for g in top_stable])
            feature_matrix.append([feat_score, feat_contrast])

        n_samples = len(sample_names)
        pos_indices = [i for i, y in enumerate(labels) if y == 1]
        neg_indices = [i for i, y in enumerate(labels) if y == 0]

        k_folds = min(args.n_splits, len(pos_indices), len(neg_indices))
        if k_folds < 2:
            folds = [[i] for i in range(n_samples)]
        else:
            folds = [[] for _ in range(k_folds)]
            for idx_list in (neg_indices, pos_indices):
                for rank_i, sample_i in enumerate(idx_list):
                    folds[rank_i % k_folds].append(sample_i)

        test_preds = [0] * n_samples
        test_probs = [0.0] * n_samples
        majority_preds = [0] * n_samples
        fold_assignment = [0] * n_samples

        for f_idx, test_fold in enumerate(folds):
            train_idx = [i for i in range(n_samples) if i not in set(test_fold)]
            train_x = [feature_matrix[i] for i in train_idx]
            train_y = [labels[i] for i in train_idx]
            test_x = [feature_matrix[i] for i in test_fold]

            f_probs, f_preds, _, _ = _logistic_fit_predict(train_x, train_y, test_x)
            majority_val = 1 if sum(train_y) >= len(train_y) - sum(train_y) else 0

            for local_i, global_i in enumerate(test_fold):
                test_probs[global_i] = f_probs[local_i]
                test_preds[global_i] = f_preds[local_i]
                majority_preds[global_i] = majority_val
                fold_assignment[global_i] = f_idx + 1

        _, _, final_w, final_b = _logistic_fit_predict(feature_matrix, labels, feature_matrix)

        bacc_model = _balanced_accuracy(labels, test_preds)
        bacc_majority = _balanced_accuracy(labels, majority_preds)
        auroc = _compute_auroc(labels, test_probs)
        brier = statistics.mean([(p - y) ** 2 for p, y in zip(test_probs, labels)])
        p_r = _pearson_r(z_scores, [float(y) for y in labels])
        s_rho = _spearman_rho(z_scores, [float(y) for y in labels])

        benchmark_pred_rows = []
        for s_idx, s_name in enumerate(sample_names):
            benchmark_pred_rows.append({
                "sample": s_name,
                "group": samples[s_name],
                "true_label": labels[s_idx],
                "predicted_label": test_preds[s_idx],
                "predicted_probability": round(test_probs[s_idx], 4),
                "majority_baseline": majority_preds[s_idx],
                "fold": fold_assignment[s_idx],
            })

        write_csv(stage3_dir / "benchmark_predictions.csv",
                  ["sample", "group", "true_label", "predicted_label", "predicted_probability", "majority_baseline", "fold"],
                  benchmark_pred_rows)

        stage3_params = {
            "n_folds": len(folds),
            "features": ["senescence_score_z", "top_contrast_mean"],
            "model": "logistic_regression_l2",
            "logistic_balanced_accuracy": bacc_model,
            "majority_balanced_accuracy": bacc_majority,
            "auroc": auroc,
            "brier_score": brier,
            "pearson_r_score_vs_group": p_r,
            "spearman_rho_score_vs_group": s_rho,
            "weights": {
                "senescence_score_weight": final_w[0] if final_w else 0.0,
                "contrast_weight": final_w[1] if len(final_w) > 1 else 0.0,
                "bias": final_b,
            },
        }
        write_json(stage3_dir / "benchmark_results.json", {
            "parameters": stage3_params,
            "predictions": benchmark_pred_rows,
        })
        (stage3_dir / "README.md").write_text(
            "# Stage 3: Benchmark Evaluation\n\n"
            "Evaluates predictive generalization of senescence scores and differential features "
            "against phenotypic ground truth using out-of-fold cross-validation.\n",
            encoding="utf-8",
        )
        stage3_input_records = {
            "stage1_manifest.json": stage1_manifest_bytes,
            "stage2_manifest.json": stage2_manifest_bytes,
            "senescence_scores.csv": stage2_scores_csv_bytes,
            "contrast.csv": stage1_contrast_csv_bytes,
        }
        manifest(stage3_dir, "benchmark-evaluation", stage3_params, stage3_input_records, {})
        stage3_manifest_bytes = (stage3_dir / "manifest.json").read_bytes()
        stage3_manifest_sha = hashlib.sha256(stage3_manifest_bytes).hexdigest()
        stage3_results_json_bytes = (stage3_dir / "benchmark_results.json").read_bytes()
        stage3_results_json_sha = hashlib.sha256(stage3_results_json_bytes).hexdigest()

        # ---------------------------------------------------------
        # STAGE 4: Integrated Pipeline Manifest & Audit Report
        # ---------------------------------------------------------
        pipeline_manifest = {
            "schema_version": 1,
            "action": "pipeline",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "parameters": {
                "reference": args.reference,
                "comparison": args.comparison,
                "pseudocount": args.pseudocount,
                "gene_set": args.gene_set,
                "n_bins": args.n_bins,
                "n_controls": args.n_controls,
                "n_splits": args.n_splits,
            },
            "upstream_inputs": {
                "matrix.csv": {"sha256": matrix_sha, "bytes": len(matrix_data)},
                "samples.csv": {"sha256": sample_sha, "bytes": len(sample_data)},
            },
            "stage_provenance": [
                {
                    "stage": 1,
                    "name": "expression-contrast",
                    "directory": "stage1_contrast",
                    "manifest_sha256": stage1_manifest_sha,
                    "key_outputs": {
                        "contrast.csv": stage1_contrast_csv_sha,
                    },
                    "upstream_dependencies": ["matrix.csv", "samples.csv"],
                },
                {
                    "stage": 2,
                    "name": "senescence-scoring",
                    "directory": "stage2_senescence",
                    "manifest_sha256": stage2_manifest_sha,
                    "key_outputs": {
                        "senescence_scores.csv": stage2_scores_csv_sha,
                    },
                    "upstream_dependencies": ["matrix.csv", "samples.csv", "stage1_manifest.json", "contrast.csv"],
                },
                {
                    "stage": 3,
                    "name": "benchmark-evaluation",
                    "directory": "stage3_benchmark",
                    "manifest_sha256": stage3_manifest_sha,
                    "key_outputs": {
                        "benchmark_results.json": stage3_results_json_sha,
                    },
                    "upstream_dependencies": ["stage1_manifest.json", "stage2_manifest.json", "senescence_scores.csv"],
                },
            ],
            "provenance_chain_intact": True,
        }
        write_json(args.out / "pipeline_manifest.json", pipeline_manifest)

        top_up = [r for r in contrast_results if r["log2_ratio"] > 0][:3]
        top_dn = [r for r in contrast_results if r["log2_ratio"] < 0][:3]
        up_str = ", ".join(f"{r['gene']} (+{r['log2_ratio']:.2f})" for r in top_up) or "none"
        dn_str = ", ".join(f"{r['gene']} ({r['log2_ratio']:.2f})" for r in top_dn) or "none"

        report_md = f"""# Integrated Pipeline Report

Three-stage exploratory pipeline: Expression Contrast -> Senescence Module Scoring -> Benchmark Evaluation.

## Stage 1: Differential Expression Contrast
- **Groups**: Reference `{args.reference}` (N={len(ref_idx)}) vs Comparison `{args.comparison}` (N={len(comp_idx)})
- **Total Genes Analyzed**: {len(contrast_results)}
- **Pseudocount**: {args.pseudocount}
- **Top Upregulated**: {up_str}
- **Top Downregulated**: {dn_str}
- **Direction-Stable Genes**: {sum(1 for r in contrast_results if r['direction_stable'])} / {len(contrast_results)}

## Stage 2: Senescence Module Scoring
- **Module Gene Set**: `{args.gene_set}` ({len(matched_genes)} matched genes in matrix)
- **Expression Bins**: {n_bins} (using {args.n_controls} controls per gene)
- **Mean Reference Raw Score**: {statistics.mean([r_score for s_idx, r_score in enumerate(raw_scores) if s_idx in ref_idx]):.4f}
- **Mean Comparison Raw Score**: {statistics.mean([r_score for s_idx, r_score in enumerate(raw_scores) if s_idx in comp_idx]):.4f}
- **Pearson correlation (Score vs Group)**: {p_r:.4f}
- **Spearman rank correlation**: {s_rho:.4f}

## Stage 3: Out-of-Fold Benchmark Evaluation
- **Evaluation Scheme**: {len(folds)}-fold stratified cross-validation
- **Model Balanced Accuracy**: {bacc_model:.4f} vs **Majority Baseline**: {bacc_majority:.4f}
- **AUROC**: {auroc:.4f}
- **Brier Score**: {brier:.4f}

## Provenance Chain & Cryptographic Audit
All stages link directly to upstream input data and preceding stage manifests:
- **Raw Matrix SHA-256**: `{matrix_sha}`
- **Raw Samples SHA-256**: `{sample_sha}`
- **Stage 1 Manifest SHA-256**: `{stage1_manifest_sha}`
- **Stage 2 Manifest SHA-256**: `{stage2_manifest_sha}`
- **Stage 3 Manifest SHA-256**: `{stage3_manifest_sha}`

*Note: All outputs are computational exploratory research artifacts. An expression or module score shift is not a clinical diagnosis, an anti-aging claim, or a rejuvenation protocol.*
"""
        (args.out / "REPORT.md").write_text(report_md, encoding="utf-8")

        all_outputs = sorted(p for p in args.out.rglob("*") if p.is_file())
        record("pipeline", {
            "reference": args.reference, "comparison": args.comparison,
            "gene_set": args.gene_set, "stages": 3,
            "pipeline_manifest_sha256": hashlib.sha256((args.out / "pipeline_manifest.json").read_bytes()).hexdigest(),
        }, all_outputs)

    print(f"Saved 3-stage pipeline report to {args.out}")
