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
