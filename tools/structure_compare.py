#!/usr/bin/env python3
"""Compare protein chains in local PDB/mmCIF files with hash-linked evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


MAX_STRUCTURE_BYTES = 50 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_CHAIN_RESIDUES = 3000
MAX_CONTACT_PAIRS = 2_000_000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _input_file(path: Path, suffixes: set[str], max_bytes: int) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or resolved.suffix.lower() not in suffixes:
        raise ValueError(f"expected a regular {', '.join(sorted(suffixes))} file: {path}")
    size = resolved.stat().st_size
    if size == 0 or size > max_bytes:
        raise ValueError(f"input must be between 1 and {max_bytes} bytes: {path}")
    return resolved


def verify_manifest(manifest_path: Path, candidate: Path) -> dict[str, Any]:
    """Check every declared output, confined to the manifest's run directory."""
    manifest = _input_file(manifest_path, {".json"}, MAX_MANIFEST_BYTES)
    run_dir = manifest.parent.resolve(strict=True)
    candidate = candidate.resolve(strict=True)
    if not candidate.is_relative_to(run_dir):
        raise ValueError("candidate must be inside the manifest's run directory")
    contents = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(contents, dict):
        raise ValueError("manifest must be a JSON object")
    fields = [name for name in ("output_files", "files", "outputs") if name in contents]
    if len(fields) != 1:
        raise ValueError("manifest must declare exactly one output hash list")
    files = contents[fields[0]]
    if not isinstance(files, list) or not files:
        raise ValueError("manifest output hash list must be non-empty")
    checked: set[Path] = set()
    for entry in files:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("each manifest output entry needs a relative path")
        relative = entry["path"]
        if not relative or "\\" in relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("manifest output path must be relative to the run directory")
        output = (run_dir / relative).resolve(strict=True)
        if not output.is_relative_to(run_dir) or not output.is_file():
            raise ValueError("manifest output must resolve to a file inside the run directory")
        if output in checked:
            raise ValueError("manifest contains a duplicate output path")
        checked.add(output)
        digest = entry.get("sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError(f"manifest output lacks a SHA-256 digest: {relative}")
        if output.stat().st_size > MAX_STRUCTURE_BYTES:
            raise ValueError(f"manifest output exceeds the 50 MiB limit: {relative}")
        if "bytes" in entry and (type(entry["bytes"]) is not int or entry["bytes"] != output.stat().st_size):
            raise ValueError(f"manifest output byte count differs: {relative}")
        if sha256_file(output) != digest:
            raise ValueError(f"manifest output SHA-256 differs: {relative}")
    if candidate not in checked:
        raise ValueError("candidate is not listed among the manifest outputs")
    return {"sha256": sha256_file(manifest), "output_field": fields[0], "outputs_verified": len(checked)}


def _protein_chain(path: Path, chain_id: str | None, model_index: int):
    from Bio.PDB import MMCIFParser, PDBParser, is_aa
    from Bio.SeqUtils import seq1

    parser = MMCIFParser(QUIET=True) if path.suffix.lower() in {".cif", ".mmcif"} else PDBParser(QUIET=True)
    structure = parser.get_structure(path.stem, str(path))
    models = list(structure.get_models())
    if model_index < 0 or model_index >= len(models):
        raise ValueError(f"model index {model_index} is outside the {len(models)} available models")
    model = models[model_index]
    candidates = []
    for chain in model.get_chains():
        residues = [residue for residue in chain.get_residues() if is_aa(residue, standard=False)]
        if residues:
            candidates.append((chain, residues))
    if chain_id is None:
        if len(candidates) != 1:
            ids = ", ".join(chain.id for chain, _ in candidates)
            raise ValueError(f"expected one protein chain; choose a chain explicitly from: {ids}")
        chain, residues = candidates[0]
    else:
        selected = [(chain, residues) for chain, residues in candidates if chain.id == chain_id]
        if len(selected) != 1:
            raise ValueError(f"protein chain {chain_id!r} was not found")
        chain, residues = selected[0]
    sequence = "".join(seq1(residue.resname, custom_map={"MSE": "M"}, undef_code="X") for residue in residues)
    if "X" in sequence:
        raise ValueError(f"chain {chain.id!r} contains an unrecognized amino acid")
    if len(sequence) > MAX_CHAIN_RESIDUES:
        raise ValueError(f"chain {chain.id!r} exceeds the {MAX_CHAIN_RESIDUES}-residue alignment limit")
    return chain.id, sequence, residues, len(models)


def _align_chains(ref_seq, pred_seq, ref_residues, pred_residues, min_identity, min_coverage):
    from Bio.Align import PairwiseAligner
    import numpy as np

    aligner = PairwiseAligner()
    aligner.mode = "global"
    aligner.match_score = 2
    aligner.mismatch_score = -1
    aligner.open_gap_score = -5
    aligner.extend_gap_score = -0.5
    alignment = aligner.align(ref_seq, pred_seq)[0]
    pairs = [(int(i), int(j)) for i, j in alignment.indices.T if i >= 0 and j >= 0]
    matches = sum(ref_seq[i] == pred_seq[j] for i, j in pairs)
    identity = matches / len(pairs) if pairs else 0.0
    ref_coverage = len(pairs) / len(ref_seq)
    pred_coverage = len(pairs) / len(pred_seq)
    if identity < min_identity or min(ref_coverage, pred_coverage) < min_coverage:
        raise ValueError(
            f"sequence comparison failed: identity={identity:.4f}, "
            f"reference coverage={ref_coverage:.4f}, candidate coverage={pred_coverage:.4f}"
        )
    ca_pairs = [(i, j, ref_residues[i]["CA"], pred_residues[j]["CA"])
                for i, j in pairs if "CA" in ref_residues[i] and "CA" in pred_residues[j]]
    if any(not np.isfinite(atom.get_coord()).all() for pair in ca_pairs for atom in pair[2:]):
        raise ValueError("matched C-alpha coordinates must be finite")
    if len(ca_pairs) < 3 or len(ca_pairs) / len(ref_residues) < min_coverage or len(ca_pairs) / len(pred_residues) < min_coverage:
        raise ValueError(f"insufficient matched C-alpha coverage: {len(ca_pairs)} atoms")
    metrics = {"paired_residues": len(pairs), "identical_residues": matches,
               "sequence_identity": identity, "reference_coverage": ref_coverage,
               "candidate_coverage": pred_coverage, "matched_ca_atoms": len(ca_pairs)}
    return metrics, ca_pairs


def _ca_contacts(receptor_pairs, partner_pairs, cutoff, side):
    from numpy.linalg import norm

    atom_index = 2 if side == "reference" else 3
    return {(receptor[0], partner[0]) for receptor in receptor_pairs for partner in partner_pairs
            if norm(receptor[atom_index].get_coord() - partner[atom_index].get_coord()) <= cutoff}


def compare(
    reference_path: Path,
    candidate_path: Path,
    *,
    reference_chain: str | None = None,
    candidate_chain: str | None = None,
    reference_partner_chain: str | None = None,
    candidate_partner_chain: str | None = None,
    reference_model: int = 0,
    candidate_model: int = 0,
    min_identity: float = 1.0,
    min_coverage: float = 0.9,
    contact_cutoff_angstrom: float = 8.0,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    from Bio import __version__ as biopython_version
    from Bio.PDB import Superimposer
    import numpy as np

    if not 0 <= min_identity <= 1 or not 0 <= min_coverage <= 1:
        raise ValueError("minimum identity and coverage must be between 0 and 1")
    if not math.isfinite(contact_cutoff_angstrom) or not 0 < contact_cutoff_angstrom <= 20:
        raise ValueError("contact cutoff must be greater than 0 and at most 20 angstrom")
    if (reference_partner_chain is None) != (candidate_partner_chain is None):
        raise ValueError("both partner chain IDs are required for a complex comparison")
    if reference_partner_chain is not None and reference_partner_chain == reference_chain:
        raise ValueError("reference partner chain must differ from the receptor chain")
    if candidate_partner_chain is not None and candidate_partner_chain == candidate_chain:
        raise ValueError("candidate partner chain must differ from the receptor chain")
    reference = _input_file(reference_path, {".cif", ".mmcif", ".pdb"}, MAX_STRUCTURE_BYTES)
    candidate = _input_file(candidate_path, {".cif", ".mmcif", ".pdb"}, MAX_STRUCTURE_BYTES)
    manifest = verify_manifest(manifest_path, candidate) if manifest_path is not None else None
    ref_chain, ref_seq, ref_residues, ref_models = _protein_chain(reference, reference_chain, reference_model)
    pred_chain, pred_seq, pred_residues, pred_models = _protein_chain(candidate, candidate_chain, candidate_model)

    metrics, ca_pairs = _align_chains(ref_seq, pred_seq, ref_residues, pred_residues, min_identity, min_coverage)
    superimposer = Superimposer()
    superimposer.set_atoms([pair[2] for pair in ca_pairs], [pair[3] for pair in ca_pairs])
    if not math.isfinite(superimposer.rms):
        raise ValueError("C-alpha RMSD is not finite")
    report = {
        "schema_version": 1,
        "method": "Biopython global sequence alignment and all-matched-C-alpha rigid superposition",
        "biopython_version": biopython_version,
        "reference": {"path": str(reference), "sha256": sha256_file(reference), "chain": ref_chain,
                      "model_index": reference_model, "model_count": ref_models, "residues": len(ref_seq)},
        "candidate": {"path": str(candidate), "sha256": sha256_file(candidate), "chain": pred_chain,
                      "model_index": candidate_model, "model_count": pred_models, "residues": len(pred_seq)},
        "alignment": {**metrics, "ca_rmsd_angstrom": round(float(superimposer.rms), 4)},
        "thresholds": {"min_identity": min_identity, "min_coverage": min_coverage},
        "interpretation": ("Self-comparison checks parsing and metric behavior only."
                           if reference == candidate else
                           "Geometric agreement for these selected chains; no binding, function, or efficacy inference."),
    }
    if manifest is not None:
        report["manifest"] = {"path": str(manifest_path.resolve(strict=True)), **manifest}
    if reference_partner_chain is not None:
        ref_partner_id, ref_partner_seq, ref_partner_residues, _ = _protein_chain(reference, reference_partner_chain, reference_model)
        pred_partner_id, pred_partner_seq, pred_partner_residues, _ = _protein_chain(candidate, candidate_partner_chain, candidate_model)
        partner_metrics, partner_pairs = _align_chains(ref_partner_seq, pred_partner_seq, ref_partner_residues,
                                                       pred_partner_residues, min_identity, min_coverage)
        if len(ca_pairs) * len(partner_pairs) > MAX_CONTACT_PAIRS:
            raise ValueError("receptor/partner C-alpha contact matrix exceeds the size limit")
        rotation, translation = superimposer.rotran
        squared_distances = [np.sum((ref_atom.get_coord() - (pred_atom.get_coord() @ rotation + translation)) ** 2)
                             for _, _, ref_atom, pred_atom in partner_pairs]
        pose_rmsd = math.sqrt(float(np.mean(squared_distances)))
        partner_superimposer = Superimposer()
        partner_superimposer.set_atoms([pair[2] for pair in partner_pairs], [pair[3] for pair in partner_pairs])
        reference_contacts = _ca_contacts(ca_pairs, partner_pairs, contact_cutoff_angstrom, "reference")
        candidate_contacts = _ca_contacts(ca_pairs, partner_pairs, contact_cutoff_angstrom, "candidate")
        recovered = len(reference_contacts & candidate_contacts)
        report["partner"] = {
            "reference_chain": ref_partner_id,
            "candidate_chain": pred_partner_id,
            "alignment": partner_metrics,
            "pose_ca_rmsd_angstrom": round(pose_rmsd, 4),
            "intrinsic_ca_rmsd_angstrom": round(float(partner_superimposer.rms), 4),
            "ca_contacts": {"cutoff_angstrom": contact_cutoff_angstrom,
                            "reference_count": len(reference_contacts),
                            "candidate_count": len(candidate_contacts),
                            "recovered_count": recovered,
                            "recall": recovered / len(reference_contacts) if reference_contacts else None,
                            "precision": recovered / len(candidate_contacts) if candidate_contacts else None},
        }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--reference-chain")
    parser.add_argument("--candidate-chain")
    parser.add_argument("--reference-partner-chain")
    parser.add_argument("--candidate-partner-chain")
    parser.add_argument("--reference-model", type=int, default=0)
    parser.add_argument("--candidate-model", type=int, default=0)
    parser.add_argument("--min-identity", type=float, default=1.0)
    parser.add_argument("--min-coverage", type=float, default=0.9)
    parser.add_argument("--contact-cutoff-angstrom", type=float, default=8.0)
    parser.add_argument("--manifest", type=Path, help="verify declared output hashes within this run directory")
    parser.add_argument("--out", type=Path, help="new JSON report file; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        report = compare(args.reference, args.candidate, reference_chain=args.reference_chain,
                         candidate_chain=args.candidate_chain, reference_partner_chain=args.reference_partner_chain,
                         candidate_partner_chain=args.candidate_partner_chain, reference_model=args.reference_model,
                         candidate_model=args.candidate_model, min_identity=args.min_identity,
                         min_coverage=args.min_coverage, contact_cutoff_angstrom=args.contact_cutoff_angstrom,
                         manifest_path=args.manifest)
        result = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.out is None:
            sys.stdout.write(result)
        else:
            with args.out.open("x", encoding="utf-8") as handle:
                handle.write(result)
            print(args.out)
    except (OSError, ValueError, KeyError, ImportError) as exc:
        parser.exit(2, f"structure comparison failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
