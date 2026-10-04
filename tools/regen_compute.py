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
    samples = _parse_sample_metadata(sample_header, sample_rows)
    if set(header[1:]) != set(samples):
        raise ValueError("matrix sample columns and sample metadata must match exactly")
    if {info["group"] for info in samples.values()} != {args.reference, args.comparison}:
        raise ValueError("metadata must contain exactly the two selected groups")
    ref = [i for i, sample in enumerate(header[1:]) if samples[sample]["group"] == args.reference]
    comp = [i for i, sample in enumerate(header[1:]) if samples[sample]["group"] == args.comparison]
    if min(len(ref), len(comp)) < 2:
        raise ValueError("each group requires at least two sample rows")
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
    "fridman": [
        "CDKN1A", "CDKN2A", "GADD45A", "BTG1", "BTG2", "ATF3", "FOS", "JUN", "CCND1", "MDM2",
        "PLK2", "SERPINE1", "SOD2", "IGFBP3", "IGFBP7", "EGR1", "MYC", "BCL2", "BAX", "FAS",
    ],
    "sasp": [
        "IL6", "CXCL8", "CCL2", "CCL7", "CSF2", "MMP1", "MMP3", "MMP10", "TIMP1", "TIMP2",
        "VEGFA", "HGF", "AREG", "EREG", "FGF2", "IL1A", "IL1B", "CXCL1", "CXCL2", "CXCL3",
    ],
}

SENESCORE_ASSET_ROOT = Path(__file__).resolve().parent / "data" / "gene-sets"


def _gene_set_metadata(name: str) -> tuple[list[str], dict, bytes | None]:
    if name == "senmayo":
        path = SENESCORE_ASSET_ROOT / "senmayo-human.json"
        data = path.read_bytes()
        try:
            entry = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("the vendored SenMayo gene-set file is invalid") from exc
        genes = entry.get("symbols")
        if (entry.get("set_id") != "senmayo" or entry.get("source_status") != "published_gene_set"
                or not isinstance(genes, list) or len(genes) != 125 or len(set(genes)) != 125
                or set(genes) & set(entry.get("orthogonal_not_members", []))):
            raise ValueError("the vendored SenMayo gene set failed its integrity checks")
        return genes, {**{k: v for k, v in entry.items() if k != "symbols"},
                       "sha256": hashlib.sha256(data).hexdigest()}, data
    if name in {"fridman_up", "fridman_down"}:
        filename = "fridman-senescence-up.json" if name == "fridman_up" else "fridman-senescence-down.json"
        path = SENESCORE_ASSET_ROOT / filename
        data = path.read_bytes()
        entry = json.loads(data)
        expected_id, count, direction = (
            ("FRIDMAN_SENESCENCE_UP", 77, "up")
            if name == "fridman_up" else ("FRIDMAN_SENESCENCE_DN", 13, "down")
        )
        genes = entry.get("symbols")
        source_snapshot = (SENESCORE_ASSET_ROOT / "msigdb-c2-v2025.1.Hs-fridman-senescence.gmt").read_bytes()
        source_lines = [line for line in source_snapshot.splitlines(keepends=True)
                        if line.startswith((expected_id + "\t").encode("ascii"))]
        if (hashlib.sha256(source_snapshot).hexdigest() !=
                "4cb3926f5e4898e1c30225baf44152c03fe4d1b815c17406422c3537c053ef33"
                or entry.get("set_id") != expected_id or entry.get("direction") != direction
                or entry.get("source", {}).get("release") != "2025.1.Hs"
                or not isinstance(genes, list) or len(genes) != count or len(set(genes)) != count
                or len(source_lines) != 1
                or hashlib.sha256(source_lines[0]).hexdigest() != entry.get("source", {}).get("raw_line_sha256")
                or source_lines[0].decode("utf-8").rstrip("\n").split("\t")[2:] != genes):
            raise ValueError(f"vendored MSigDB gene set failed integrity checks: {filename}")
        return genes, {
            "set_id": expected_id,
            "name": f"MSigDB {expected_id}",
            "source_status": "published_gene_set",
            "citation": "Fridman AL, Tainsky MA. Oncogene. 2008;27:5975-5987. DOI:10.1038/onc.2008.213; MSigDB C2 2025.1.Hs Table 2S.",
            "description": f"Source-pinned {count}-gene direction-specific signature.",
            "direction": direction,
            "systematic_id": entry.get("systematic_id"),
            "source": entry.get("source"),
            "sha256": hashlib.sha256(data).hexdigest(),
        }, data
    if name == "fridman_signed":
        up_genes, up_info, up_data = _gene_set_metadata("fridman_up")
        down_genes, down_info, down_data = _gene_set_metadata("fridman_down")
        genes = list(dict.fromkeys(up_genes + down_genes))
        data = json.dumps(
            {"up": json.loads(up_data), "down": json.loads(down_data)},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        return genes, {
            "set_id": "fridman_signed",
            "name": "MSigDB FRIDMAN_SENESCENCE_UP minus FRIDMAN_SENESCENCE_DN",
            "source_status": "published_gene_set",
            "citation": up_info["citation"],
            "description": "Direction-aware signed contrast using separately scored MSigDB up/down sets.",
            "direction": "up_minus_down",
            "components": {"up": up_info, "down": down_info},
            "sha256": hashlib.sha256(data).hexdigest(),
        }, data
    if name not in GENE_SETS:
        raise ValueError(f"unknown gene set: {name}")
    return GENE_SETS[name], {
        "set_id": name,
        "name": {"fridman": "Custom Fridman-inspired panel", "sasp": "Custom SASP-oriented panel"}[name],
        "source_status": "custom_unverified",
        "citation": "Project-curated panel; membership is not verified against a source gene list.",
        "description": "Exploratory custom panel only; not a source-transcribed published signature.",
        "sha256": hashlib.sha256(json.dumps(GENE_SETS[name], separators=(",", ":")).encode()).hexdigest(),
    }, None


def _parse_sample_metadata(sample_header: list[str], sample_rows: list[list[str]]) -> dict[str, dict[str, str]]:
    allowed = {"sample", "group", "donor_id", "batch_id"}
    if not {"sample", "group"}.issubset(sample_header) or set(sample_header) - allowed:
        raise ValueError("sample CSV header must contain sample,group and optional donor_id,batch_id")
    if sample_header[:2] != ["sample", "group"]:
        raise ValueError("sample CSV columns must begin with sample,group")
    samples: dict[str, dict[str, str]] = {}
    for row in sample_rows:
        values = dict(zip(sample_header, row))
        sample = identifier(values["sample"], "sample")
        group = identifier(values["group"], "group")
        if sample in samples:
            raise ValueError(f"duplicate sample: {sample}")
        samples[sample] = {"group": group, "donor_id": "", "batch_id": ""}
        for field in ("donor_id", "batch_id"):
            value = values.get(field, "")
            if value:
                identifier(value, field)
                samples[sample][field] = value
    return samples


def _grouped_stratified_folds(sample_names: list[str], labels: list[int],
                              sample_info: dict[str, dict[str, str]], requested: int) -> tuple[list[list[int]], list[str]]:
    """Keep samples joined by donor or batch in one test fold."""
    parents = list(range(len(sample_names)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        root_l, root_r = find(left), find(right)
        if root_l != root_r:
            parents[root_r] = root_l

    seen_ids: dict[tuple[str, str], int] = {}
    used_fields = [field for field in ("donor_id", "batch_id")
                   if any(sample_info[s].get(field) for s in sample_names)]
    for field in used_fields:
        if any(not sample_info[s].get(field) for s in sample_names):
            raise ValueError(f"{field} must be present for every sample when used for grouped cross-validation")
    for index, sample in enumerate(sample_names):
        for field in used_fields:
            value = sample_info[sample].get(field, "")
            key = (field, value)
            if key in seen_ids:
                union(index, seen_ids[key])
            else:
                seen_ids[key] = index

    components: dict[int, list[int]] = {}
    for index in range(len(sample_names)):
        components.setdefault(find(index), []).append(index)
    component_rows = []
    for indexes in components.values():
        counts = [sum(labels[i] == label for i in indexes) for label in (0, 1)]
        component_rows.append((indexes, counts))
    n_components_by_label = [sum(counts[label] > 0 for _, counts in component_rows) for label in (0, 1)]
    k_folds = min(requested, *n_components_by_label)
    if k_folds < 2:
        raise ValueError("grouped cross-validation needs at least two independent donor/batch components per class")

    total_by_label = [sum(labels[i] == label for i in range(len(labels))) for label in (0, 1)]
    target = [count / k_folds for count in total_by_label]
    fold_counts = [[0, 0] for _ in range(k_folds)]
    folds: list[list[int]] = [[] for _ in range(k_folds)]
    # Place larger and label-balanced components first; deterministic ties keep runs reproducible.
    component_rows.sort(key=lambda row: (-len(row[0]), -sum(n > 0 for n in row[1]), min(row[0])))
    for indexes, counts in component_rows:
        choices = []
        for fold_index in range(k_folds):
            missing_present_labels = sum(counts[label] > 0 and fold_counts[fold_index][label] == 0
                                         for label in (0, 1))
            imbalance = sum(((fold_counts[fold_index][label] + counts[label] - target[label])
                             / max(1.0, target[label])) ** 2 for label in (0, 1))
            choices.append((-missing_present_labels, imbalance, len(folds[fold_index]), fold_index))
        fold_index = min(choices)[-1]
        folds[fold_index].extend(indexes)
        for label in (0, 1):
            fold_counts[fold_index][label] += counts[label]

    for fold in folds:
        fold.sort()
    if any(not fold or not any(labels[i] == 0 for i in fold) or not any(labels[i] == 1 for i in fold)
           for fold in folds):
        raise ValueError("donor/batch components cannot form stratified folds containing both classes")
    return folds, used_fields or ["sample_id"]


def _training_fold_features(gene_matrix_map: dict[str, list[float]], train_idx: list[int],
                            test_idx: list[int], train_y: list[int],
                            signature_genes: list[str], n_controls: int,
                            signed_down_genes: list[str] | None = None,
                            n_bins: int = 25, pseudocount: float = 1.0,
                            ) -> tuple[list[list[float]], list[list[float]], list[str]]:
    """Fit control selection, score normalization, and marker selection on training rows only."""
    up_genes = [gene for gene in signature_genes if gene in gene_matrix_map]
    down_genes = [gene for gene in (signed_down_genes or []) if gene in gene_matrix_map]
    matched = list(dict.fromkeys(up_genes + down_genes))
    signature_union = set(signature_genes) | set(signed_down_genes or [])
    candidates = [gene for gene in sorted(gene_matrix_map) if gene not in signature_union]
    if not matched or len(candidates) < n_controls:
        raise ValueError("not enough non-signature genes to fit training-fold controls")
    candidate_means = [(gene, statistics.mean(gene_matrix_map[gene][i] for i in train_idx))
                       for gene in candidates]
    candidate_means.sort(key=lambda item: (item[1], item[0]))
    n_bins = min(n_bins, max(1, len(candidate_means) // n_controls))
    bins = [candidate_means[b * len(candidate_means) // n_bins:
                            (b + 1) * len(candidate_means) // n_bins] for b in range(n_bins)]
    control_map = {}
    for gene in matched:
        mean_value = statistics.mean(gene_matrix_map[gene][i] for i in train_idx)
        best_bin = min(range(len(bins)), key=lambda b: (
            abs(statistics.mean(value for _, value in bins[b]) - mean_value), b))
        control_map[gene] = [candidate for candidate, _ in bins[best_bin][:n_controls]]
        if not control_map[gene]:
            raise ValueError("training-fold control selection produced an empty control set")

    def score(index: int) -> float:
        return statistics.mean(gene_matrix_map[gene][index] -
                               statistics.mean(gene_matrix_map[control][index] for control in control_map[gene])
                               for gene in matched)

    if signed_down_genes is not None:
        def direction_score(index: int, genes: list[str]) -> float:
            return statistics.mean(
                gene_matrix_map[gene][index] - statistics.mean(
                    gene_matrix_map[control][index] for control in control_map[gene]
                ) for gene in genes
            )

        def combined_score(index):
            return direction_score(index, up_genes) - direction_score(index, down_genes)
    else:
        combined_score = score

    train_scores = [combined_score(i) for i in train_idx]
    mean_score = statistics.mean(train_scores)
    sd_score = statistics.stdev(train_scores) if len(train_scores) > 1 else 1.0
    if sd_score <= 1e-12:
        sd_score = 1.0
    score_z = {i: (combined_score(i) - mean_score) / sd_score for i in train_idx + test_idx}

    class_means = []
    for label in (0, 1):
        indexes = [index for index, y in zip(train_idx, train_y) if y == label]
        if not indexes:
            raise ValueError("each training fold must contain both classes")
        class_means.append(indexes)
    contrast_rows = []
    for gene in gene_matrix_map:
        means = [statistics.mean(gene_matrix_map[gene][i] for i in indexes) for indexes in class_means]
        effect = math.log2(means[1] + pseudocount) - math.log2(means[0] + pseudocount)
        # Rank only on training data. Stability uses the training rows' leave-one-out effects.
        leave_one_out = []
        for label, indexes in enumerate(class_means):
            if len(indexes) < 2:
                continue
            other_mean = means[1 - label]
            for removed in indexes:
                retained = [i for i in indexes if i != removed]
                retained_mean = statistics.mean(gene_matrix_map[gene][i] for i in retained)
                a, b = (retained_mean, other_mean) if label == 0 else (other_mean, retained_mean)
                leave_one_out.append(math.log2(b + pseudocount) - math.log2(a + pseudocount))
        stable_up = effect > 0 and bool(leave_one_out) and min(leave_one_out) > 0
        contrast_rows.append((gene, stable_up, effect))
    stable_up = sorted((row for row in contrast_rows if row[1]), key=lambda row: (-row[2], row[0]))
    ranked = stable_up or sorted(contrast_rows, key=lambda row: (-abs(row[2]), row[0]))
    selected_markers = [row[0] for row in ranked[:5]]
    if not selected_markers:
        raise ValueError("training-fold marker selection produced no genes")

    def features(index: int) -> list[float]:
        return [score_z[index], statistics.mean(gene_matrix_map[gene][index] for gene in selected_markers)]

    return [features(i) for i in train_idx], [features(i) for i in test_idx], selected_markers


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


def _pearson_r(x: list[float], y: list[float]) -> float | None:
    if len(x) < 2 or len(x) != len(y):
        return None
    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    vx = sum((v - mx) ** 2 for v in x)
    vy = sum((v - my) ** 2 for v in y)
    if vx <= 1e-15 or vy <= 1e-15:
        return None
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    return cov / math.sqrt(vx * vy)


def _spearman_rho(x: list[float], y: list[float]) -> float | None:
    if len(x) < 2:
        return None

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


def _format_correlation(value: float | None) -> str:
    return "undefined (constant or insufficient data)" if value is None else f"{value:.4f}"


def pipeline(argv: list[str], record) -> None:
    parser = argparse.ArgumentParser(prog="regen pipeline")
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--pseudocount", type=float, default=1.0)
    parser.add_argument("--gene-set", default="senmayo", choices=["senmayo", "fridman", "fridman_up", "fridman_down", "fridman_signed", "sasp"],
                        help="senmayo and Fridman sets are source-pinned; fridman and sasp are custom panels")
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
    samples = _parse_sample_metadata(sample_header, sample_rows)

    if set(header[1:]) != set(samples):
        raise ValueError("matrix sample columns and sample metadata must match exactly")
    if {info["group"] for info in samples.values()} != {args.reference, args.comparison}:
        raise ValueError("metadata must contain exactly the two selected groups")

    sample_names = header[1:]
    ref_idx = [i for i, s in enumerate(sample_names) if samples[s]["group"] == args.reference]
    comp_idx = [i for i, s in enumerate(sample_names) if samples[s]["group"] == args.comparison]
    if min(len(ref_idx), len(comp_idx)) < 2:
        raise ValueError("each group requires at least two sample rows")

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

        predefined_genes, gene_set_info, gene_set_data = _gene_set_metadata(args.gene_set)
        matched_genes = [g for g in predefined_genes if g in gene_matrix_map]
        coverage_fraction = len(matched_genes) / len(predefined_genes)
        if coverage_fraction < 0.60:
            raise ValueError(f"gene-set coverage is {coverage_fraction:.1%}; at least 60% is required; "
                             "no contrast-derived or name-based fallback is used")

        candidate_genes = [g for g in gene_matrix_map if g not in set(predefined_genes)]
        if len(candidate_genes) < args.n_controls:
            raise ValueError("at least n-controls non-signature genes are required for control matching")

        cand_means = [(g, sum(gene_matrix_map[g]) / len(sample_names)) for g in candidate_genes]
        cand_means.sort(key=lambda t: t[1])

        n_bins = min(args.n_bins, max(1, len(cand_means) // max(1, args.n_controls)))
        bin_size = max(1, len(cand_means) // n_bins)
        bins = [cand_means[b * bin_size: (b + 1) * bin_size if b < n_bins - 1 else len(cand_means)]
                for b in range(n_bins)]

        control_map = {}
        signed_sets = None
        if args.gene_set == "fridman_signed":
            up_genes, _, _ = _gene_set_metadata("fridman_up")
            down_genes, _, _ = _gene_set_metadata("fridman_down")
            up_matched = [gene for gene in up_genes if gene in gene_matrix_map]
            down_matched = [gene for gene in down_genes if gene in gene_matrix_map]
            if (len(up_matched) / len(up_genes) < 0.60 or len(down_matched) / len(down_genes) < 0.60):
                raise ValueError("signed Fridman scoring requires at least 60% coverage of both UP and DOWN sets")
            signed_sets = {"up": up_matched, "down": down_matched}
            for direction, signature in signed_sets.items():
                for g in signature:
                    g_mean = sum(gene_matrix_map[g]) / len(sample_names)
                    best_bin = min(range(len(bins)), key=lambda b: abs((sum(x[1] for x in bins[b]) / max(1, len(bins[b]))) - g_mean))
                    control_map[f"{direction}:{g}"] = [gene for gene, _ in bins[best_bin][:args.n_controls]]
        else:
            for g in matched_genes:
                g_mean = sum(gene_matrix_map[g]) / len(sample_names)
                best_bin = min(range(len(bins)), key=lambda b: abs((sum(x[1] for x in bins[b]) / max(1, len(bins[b]))) - g_mean))
                selected = [gene for gene, _ in bins[best_bin][:args.n_controls]]
                control_map[g] = selected

        raw_scores = []
        component_scores = {"up": [], "down": []} if signed_sets else None
        for s_idx in range(len(sample_names)):
            if signed_sets:
                for direction, signature in signed_sets.items():
                    diffs = [gene_matrix_map[g][s_idx] - statistics.mean(
                        gene_matrix_map[cg][s_idx] for cg in control_map[f"{direction}:{g}"]
                    ) for g in signature]
                    component_scores[direction].append(statistics.mean(diffs))
                raw_scores.append(component_scores["up"][s_idx] - component_scores["down"][s_idx])
            else:
                module_diffs = []
                for g in matched_genes:
                    val = gene_matrix_map[g][s_idx]
                    ctrl_mean = statistics.mean([gene_matrix_map[cg][s_idx] for cg in control_map[g]])
                    module_diffs.append(val - ctrl_mean)
                raw_scores.append(statistics.mean(module_diffs))

        mean_raw = statistics.mean(raw_scores)
        sd_raw = statistics.stdev(raw_scores) if len(raw_scores) > 1 and statistics.stdev(raw_scores) > 1e-12 else 1.0
        z_scores = [(s - mean_raw) / sd_raw for s in raw_scores]
        group_labels = [
            0.0 if samples[sample_name]["group"] == args.reference else 1.0
            for sample_name in sample_names
        ]
        score_p_r = _pearson_r(raw_scores, group_labels)
        score_s_rho = _spearman_rho(raw_scores, group_labels)

        score_rows = []
        for s_name, r_score, z_score in zip(sample_names, raw_scores, z_scores):
            score_rows.append({
                "sample": s_name,
                "group": samples[s_name]["group"],
                "donor_id": samples[s_name]["donor_id"],
                "batch_id": samples[s_name]["batch_id"],
                "raw_score": r_score,
                "z_score": z_score,
            })

        write_csv(stage2_dir / "senescence_scores.csv",
                  ["sample", "group", "donor_id", "batch_id", "raw_score", "z_score"], score_rows)
        stage2_params = {
            "gene_set": args.gene_set,
            "gene_set_name": gene_set_info["name"],
            "gene_set_source_status": gene_set_info["source_status"],
            "gene_set_citation": gene_set_info["citation"],
            "gene_set_sha256": gene_set_info["sha256"],
            "target_genes_in_set": len(predefined_genes),
            "genes_matched_in_matrix": len(matched_genes),
            "coverage_fraction": coverage_fraction,
            "minimum_coverage_fraction": 0.60,
            "n_bins": n_bins,
            "n_controls_per_gene": args.n_controls,
            "score_method": "control-subtracted mean; not the source paper's GSEA procedure",
            "mean_raw_score": mean_raw,
            "sd_raw_score": sd_raw,
        }
        if signed_sets:
            stage2_params["genes_matched_in_matrix"] = len(signed_sets["up"]) + len(signed_sets["down"])
            stage2_params["coverage_fraction"] = min(
                len(signed_sets["up"]) / 77, len(signed_sets["down"]) / 13
            )
            stage2_params["directional_coverage"] = {
                direction: len(genes) / (77 if direction == "up" else 13)
                for direction, genes in signed_sets.items()
            }
            stage2_params["direction"] = "up_minus_down"
            stage2_params["signed_scoring"] = "independently control-subtracted UP score minus independently control-subtracted DOWN score"
        write_json(stage2_dir / "senescence_scores.json", {
            "parameters": stage2_params,
            "matched_genes": matched_genes,
            "control_genes": control_map,
            "directional_raw_scores": component_scores,
            "scores": score_rows,
        })
        (stage2_dir / "README.md").write_text(
            "# Stage 2: Senescence Module Scoring\n\n"
            f"Calculates a control-subtracted module score from `{gene_set_info['name']}` "
            f"({gene_set_info['source_status']}). This is not the source paper's GSEA procedure. "
            "The stage 2 score uses the full dataset and is descriptive; Stage 3 refits all score "
            "controls and normalization within each training fold.\n",
            encoding="utf-8",
        )
        stage2_input_records = {
            "matrix.input.csv": matrix_data,
            "samples.input.csv": sample_data,
            "stage1_manifest.json": stage1_manifest_bytes,
            "contrast.csv": stage1_contrast_csv_bytes,
        }
        if gene_set_data is not None:
            stage2_input_records[f"{args.gene_set}.json"] = gene_set_data
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

        labels = [1 if samples[s]["group"] == args.comparison else 0 for s in sample_names]
        folds, split_fields = _grouped_stratified_folds(sample_names, labels, samples, args.n_splits)
        if split_fields == ["sample_id"]:
            independence_note = "no donor or batch identifiers were supplied; sample independence is unverified"
        else:
            independence_note = (
                f"folds grouped by {', '.join(split_fields)}; "
                "independence beyond these identifiers is unverified"
            )
        n_samples = len(sample_names)

        test_preds = [0] * n_samples
        test_probs = [0.0] * n_samples
        majority_preds = [0] * n_samples
        fold_assignment = [0] * n_samples
        fold_details = []

        for f_idx, test_fold in enumerate(folds):
            test_set = set(test_fold)
            train_idx = [i for i in range(n_samples) if i not in test_set]
            train_y = [labels[i] for i in train_idx]
            train_x, test_x, selected_markers = _training_fold_features(
                gene_matrix_map, train_idx, test_fold, train_y,
                (
                    _gene_set_metadata("fridman_up")[0]
                    if args.gene_set == "fridman_signed" else predefined_genes
                ),
                args.n_controls,
                signed_down_genes=(
                    _gene_set_metadata("fridman_down")[0]
                    if args.gene_set == "fridman_signed" else None
                ),
                n_bins=args.n_bins, pseudocount=args.pseudocount,
            )

            f_probs, f_preds, _, _ = _logistic_fit_predict(train_x, train_y, test_x)
            majority_val = 1 if sum(train_y) >= len(train_y) - sum(train_y) else 0

            for local_i, global_i in enumerate(test_fold):
                test_probs[global_i] = f_probs[local_i]
                test_preds[global_i] = f_preds[local_i]
                majority_preds[global_i] = majority_val
                fold_assignment[global_i] = f_idx + 1
            fold_details.append({
                "fold": f_idx + 1,
                "train_samples": len(train_idx),
                "test_samples": len(test_fold),
                "selected_marker_genes": selected_markers,
                "training_only_transformations": [
                    "expression-bin control selection", "control-subtracted score normalization",
                    "differential marker selection", "logistic feature scaling",
                ],
            })

        bacc_model = _balanced_accuracy(labels, test_preds)
        bacc_majority = _balanced_accuracy(labels, majority_preds)
        auroc = _compute_auroc(labels, test_probs)
        brier = statistics.mean([(p - y) ** 2 for p, y in zip(test_probs, labels)])
        p_r = _pearson_r(test_probs, [float(y) for y in labels])
        s_rho = _spearman_rho(test_probs, [float(y) for y in labels])

        benchmark_pred_rows = []
        for s_idx, s_name in enumerate(sample_names):
            benchmark_pred_rows.append({
                "sample": s_name,
                "group": samples[s_name]["group"],
                "donor_id": samples[s_name]["donor_id"],
                "batch_id": samples[s_name]["batch_id"],
                "true_label": labels[s_idx],
                "predicted_label": test_preds[s_idx],
                "predicted_probability": round(test_probs[s_idx], 4),
                "majority_baseline": majority_preds[s_idx],
                "fold": fold_assignment[s_idx],
            })

        write_csv(stage3_dir / "benchmark_predictions.csv",
                  ["sample", "group", "donor_id", "batch_id", "true_label", "predicted_label",
                   "predicted_probability", "majority_baseline", "fold"],
                  benchmark_pred_rows)

        stage3_params = {
            "n_folds": len(folds),
            "requested_n_folds": args.n_splits,
            "split_strategy": "stratified connected components; samples sharing donor_id or batch_id are held together",
            "split_fields": split_fields,
            "feature_selection_scope": "training fold only",
            "scoring_and_control_fit_scope": "training fold only",
            "features": ["training-fold control-subtracted module score z", "training-fold selected marker mean"],
            "requested_expression_bins": args.n_bins,
            "n_controls_per_gene": args.n_controls,
            "marker_pseudocount": args.pseudocount,
            "module_score_definition": (
                "raw control-subtracted UP minus raw control-subtracted DOWN, then training-fold z"
                if signed_sets else "raw control-subtracted mean, then training-fold z"
            ),
            "model": "logistic_regression_l2",
            "logistic_balanced_accuracy": bacc_model,
            "majority_balanced_accuracy": bacc_majority,
            "auroc": auroc,
            "brier_score": brier,
            "pearson_r_oof_probability_vs_group": p_r,
            "spearman_rho_oof_probability_vs_group": s_rho,
            "fold_details": fold_details,
        }
        write_json(stage3_dir / "benchmark_results.json", {
            "parameters": stage3_params,
            "predictions": benchmark_pred_rows,
        })
        (stage3_dir / "README.md").write_text(
            "# Stage 3: Benchmark Evaluation\n\n"
            "Evaluates exploratory out-of-fold predictions. Donor/batch-connected samples stay "
            "together; control selection, score normalization, differential marker selection, and "
            "model scaling are fitted within each training fold. Without donor/batch IDs, the "
            "split is sample-level and biological independence is unverified. Few groups make "
            "metrics unstable; these are not evidence of external generalization or rejuvenation.\n",
            encoding="utf-8",
        )
        stage3_input_records = {
            "matrix.input.csv": matrix_data,
            "samples.input.csv": sample_data,
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
                    "upstream_dependencies": ["matrix.csv", "samples.csv", f"{args.gene_set}.json",
                                              "stage1_manifest.json", "contrast.csv"]
                    if gene_set_data is not None else
                    ["matrix.csv", "samples.csv", "stage1_manifest.json", "contrast.csv"],
                },
                {
                    "stage": 3,
                    "name": "benchmark-evaluation",
                    "directory": "stage3_benchmark",
                    "manifest_sha256": stage3_manifest_sha,
                    "key_outputs": {
                        "benchmark_results.json": stage3_results_json_sha,
                    },
                    "upstream_dependencies": ["matrix.csv", "samples.csv", "stage1_manifest.json",
                                              "stage2_manifest.json", "senescence_scores.csv"],
                },
            ],
            "provenance_chain_intact": True,
        }
        if gene_set_data is not None:
            pipeline_manifest["upstream_inputs"][f"{args.gene_set}.json"] = {
                "sha256": gene_set_info["sha256"], "bytes": len(gene_set_data),
            }
        write_json(args.out / "pipeline_manifest.json", pipeline_manifest)

        top_up = [r for r in contrast_results if r["log2_ratio"] > 0][:3]
        top_dn = [r for r in contrast_results if r["log2_ratio"] < 0][:3]
        up_str = ", ".join(f"{r['gene']} (+{r['log2_ratio']:.2f})" for r in top_up) or "none"
        dn_str = ", ".join(f"{r['gene']} ({r['log2_ratio']:.2f})" for r in top_dn) or "none"

        report_md = f"""# Integrated Pipeline Report

Three-stage exploratory pipeline: Expression Contrast -> Senescence Module Scoring -> Grouped Out-of-Fold Benchmark.

## Stage 1: Differential Expression Contrast
- **Groups**: Reference `{args.reference}` (N={len(ref_idx)}) vs Comparison `{args.comparison}` (N={len(comp_idx)})
- **Total Genes Analyzed**: {len(contrast_results)}
- **Pseudocount**: {args.pseudocount}
- **Top Upregulated**: {up_str}
- **Top Downregulated**: {dn_str}
- **Direction-Stable Genes**: {sum(1 for r in contrast_results if r['direction_stable'])} / {len(contrast_results)}

## Stage 2: Senescence Module Scoring
- **Module Gene Set**: {gene_set_info['name']} (`{args.gene_set}`, {gene_set_info['source_status']}; {len(matched_genes)} / {len(predefined_genes)} matched)
- **Gene Set Source**: {gene_set_info['citation']}
- **Expression Bins**: {n_bins} (using {args.n_controls} controls per gene)
- This whole-dataset score is descriptive only; cross-validation refits controls and score scaling within each training fold.
- **Mean Reference Raw Score**: {statistics.mean([r_score for s_idx, r_score in enumerate(raw_scores) if s_idx in ref_idx]):.4f}
- **Mean Comparison Raw Score**: {statistics.mean([r_score for s_idx, r_score in enumerate(raw_scores) if s_idx in comp_idx]):.4f}
- **Pearson correlation (Score vs Group)**: {_format_correlation(score_p_r)}
- **Spearman rank correlation (Score vs Group)**: {_format_correlation(score_s_rho)}

## Stage 3: Out-of-Fold Benchmark Evaluation
- **Evaluation Scheme**: {len(folds)}-fold stratified connected-component cross-validation; samples sharing a donor or batch stay in one fold.
- **Split Fields**: {", ".join(split_fields)}
- **Fold-local steps**: control matching, module-score scaling, marker selection, and logistic feature scaling are fit on training samples only.
- **Independence note**: {independence_note}
- **Model Balanced Accuracy**: {bacc_model:.4f} vs **Majority Baseline**: {bacc_majority:.4f}
- **AUROC**: {auroc:.4f}
- **Brier Score**: {brier:.4f}
- **OOF probability correlations**: Pearson r {_format_correlation(p_r)}; Spearman rho {_format_correlation(s_rho)}

## Provenance Chain & Cryptographic Audit
All stages link directly to upstream input data and preceding stage manifests:
- **Raw Matrix SHA-256**: `{matrix_sha}`
- **Raw Samples SHA-256**: `{sample_sha}`
- **Stage 1 Manifest SHA-256**: `{stage1_manifest_sha}`
- **Stage 2 Manifest SHA-256**: `{stage2_manifest_sha}`
- **Stage 3 Manifest SHA-256**: `{stage3_manifest_sha}`

*Note: Cross-validation metrics and uncalibrated model probabilities are exploratory and can be unstable with few independent components. They do not establish external generalization, a senescence diagnosis, rejuvenation, or clinical benefit. The SenMayo paper used GSEA; this software uses a distinct control-subtracted score.*
"""
        (args.out / "REPORT.md").write_text(report_md, encoding="utf-8")

        all_outputs = sorted(p for p in args.out.rglob("*") if p.is_file())
        record("pipeline", {
            "reference": args.reference, "comparison": args.comparison,
            "gene_set": args.gene_set, "stages": 3,
            "pipeline_manifest_sha256": hashlib.sha256((args.out / "pipeline_manifest.json").read_bytes()).hexdigest(),
        }, all_outputs)

    print(f"Saved 3-stage pipeline report to {args.out}")
