#!/usr/bin/env python3
"""Reproducible, control-aware ranking and redocking validation reports."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import statistics
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

MAX_ROWS = 1000
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_TOTAL_INPUT_BYTES = 200 * 1024 * 1024
ROLES = {"active_control", "inactive_control", "decoy", "candidate"}
REQUIRED_COLUMNS = {"compound_id", "role", "score", "method"}
OPTIONAL_COLUMNS = {"assay_id", "label_source", "pose_sdf", "reference_sdf", "pose_index", "reference_index"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_input(
    value: str,
    label: str,
    roots: list[Path],
    suffixes: set[str],
    *,
    max_bytes=MAX_FILE_BYTES,
    relative_to: Path | None = None,
) -> Path:
    raw = Path(value)
    root = roots[0].parent
    candidates = [raw] if raw.is_absolute() else [root / raw]
    if relative_to is not None and not raw.is_absolute():
        candidates.append(relative_to / raw)
    path = None
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if any(resolved == base or base in resolved.parents for base in roots):
            path = resolved
            break
    if path is None:
        raise ValueError(f"{label} must resolve to a file under the workbench data/ or projects/ directory")
    if not path.is_file() or path.suffix.lower() not in suffixes:
        raise ValueError(f"{label} must be a regular file with extension {', '.join(sorted(suffixes))}")
    size = path.stat().st_size
    if size == 0 or size > max_bytes:
        raise ValueError(f"{label} must be non-empty and no larger than {max_bytes // (1024 * 1024)} MiB")
    return path


def _output_path(value: str, data_root: Path, workbench_root: Path) -> Path:
    raw = Path(value)
    if not raw.is_absolute():
        raw = workbench_root / raw
    try:
        parent = raw.parent.resolve(strict=True)
        allowed = data_root.resolve(strict=False)
    except OSError as exc:
        raise ValueError("output parent must already exist") from exc
    if parent != allowed and allowed not in parent.parents:
        raise ValueError(f"output directory must be under {allowed}")
    dest = parent / raw.name
    if dest.exists() or dest.is_symlink() or not raw.name or raw.name in {".", ".."}:
        raise ValueError("output must be a new directory; existing reports are never overwritten")
    return dest


def _read_rows(manifest: Path, workbench_root: Path, roots: list[Path]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        if not REQUIRED_COLUMNS <= columns:
            raise ValueError(f"input CSV must include columns: {', '.join(sorted(REQUIRED_COLUMNS))}")
        extra = columns - REQUIRED_COLUMNS - OPTIONAL_COLUMNS
        if extra:
            raise ValueError(f"unsupported input CSV column(s): {', '.join(sorted(extra))}")
        rows = []
        inputs: dict[str, dict[str, Any]] = {}
        ids = set()
        methods = set()
        total_bytes = manifest.stat().st_size
        inputs[str(manifest)] = {"path": manifest, "sha256": sha256_file(manifest), "bytes": total_bytes, "role": "manifest"}
        for line_number, raw in enumerate(reader, start=2):
            if line_number > MAX_ROWS + 1:
                raise ValueError(f"input CSV exceeds the {MAX_ROWS}-row limit")
            compound_id = (raw.get("compound_id") or "").strip()
            role = (raw.get("role") or "").strip()
            if not compound_id or len(compound_id) > 128 or any(ord(c) < 32 for c in compound_id):
                raise ValueError(f"row {line_number}: compound_id must be a non-empty identifier up to 128 characters")
            if compound_id in ids:
                raise ValueError(f"row {line_number}: duplicate compound_id {compound_id!r}")
            ids.add(compound_id)
            if role not in ROLES:
                raise ValueError(f"row {line_number}: role must be one of {', '.join(sorted(ROLES))}")
            method = (raw.get("method") or "").strip()
            if not method or len(method) > 128:
                raise ValueError(f"row {line_number}: method must name the scoring method")
            methods.add(method)
            try:
                score = float(raw["score"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"row {line_number}: score must be numeric") from exc
            if not math.isfinite(score):
                raise ValueError(f"row {line_number}: score must be finite")
            row: dict[str, Any] = {
                "compound_id": compound_id,
                "role": role,
                "score": score,
                "method": method,
                "assay_id": (raw.get("assay_id") or "").strip(),
                "label_source": (raw.get("label_source") or "").strip(),
                "pose_sdf": "",
                "reference_sdf": "",
                "pose_index": 0,
                "reference_index": 0,
                "pose_rmsd_angstrom": None,
                "pose_rmsd_status": "not requested",
            }
            pose_value = (raw.get("pose_sdf") or "").strip()
            reference_value = (raw.get("reference_sdf") or "").strip()
            if bool(pose_value) != bool(reference_value):
                raise ValueError(f"row {line_number}: pose_sdf and reference_sdf must be supplied together")
            if pose_value:
                if Path(pose_value).is_absolute() or Path(reference_value).is_absolute():
                    raise ValueError(f"row {line_number}: SDF paths must be relative workbench paths, not absolute paths")
                pose = _resolve_input(pose_value, f"row {line_number} pose_sdf", roots, {".sdf"}, relative_to=manifest.parent)
                reference = _resolve_input(reference_value, f"row {line_number} reference_sdf", roots, {".sdf"}, relative_to=manifest.parent)
                pose_hash, reference_hash = sha256_file(pose), sha256_file(reference)
                for path, digest, role_name in ((pose, pose_hash, "pose"), (reference, reference_hash, "reference")):
                    key = str(path)
                    if key not in inputs:
                        total_bytes += path.stat().st_size
                        if total_bytes > MAX_TOTAL_INPUT_BYTES:
                            raise ValueError("total CSV and SDF inputs exceed the 200 MiB report limit")
                        inputs[key] = {"path": path, "sha256": digest, "bytes": path.stat().st_size, "role": role_name}
                row["pose_sdf"] = str(pose)
                row["reference_sdf"] = str(reference)
                for column, target in (("pose_index", "pose_index"), ("reference_index", "reference_index")):
                    raw_index = (raw.get(column) or "0").strip()
                    if not raw_index.isdecimal() or int(raw_index) > 999:
                        raise ValueError(f"row {line_number}: {column} must be an integer from 0 to 999")
                    row[target] = int(raw_index)
                row["pose_rmsd_status"] = "pending"
            rows.append(row)
    if not rows:
        raise ValueError("input CSV contains no compounds")
    if not any(row["role"] == "active_control" for row in rows):
        raise ValueError("input CSV needs at least one active_control")
    if not any(row["role"] == "inactive_control" for row in rows):
        raise ValueError("input CSV needs at least one inactive_control")
    if len(methods) != 1:
        raise ValueError("each report must contain scores from exactly one method; run separate reports to compare methods")
    for row in rows:
        if row["role"] in {"active_control", "inactive_control"} and not row["label_source"]:
            raise ValueError(f"{row['role']} {row['compound_id']!r} needs a label_source reference")
    return rows, inputs


def _ranking_metrics(rows: list[dict[str, Any]], direction: str) -> dict[str, Any]:
    active = [row for row in rows if row["role"] == "active_control"]
    inactive = [row for row in rows if row["role"] == "inactive_control"]
    oriented = lambda row: row["score"] if direction == "higher" else -row["score"]
    wins = 0.0
    for positive in active:
        for negative in inactive:
            p_score, n_score = oriented(positive), oriented(negative)
            wins += 1.0 if p_score > n_score else (0.5 if p_score == n_score else 0.0)
    ordered = sorted(active + inactive, key=lambda row: (-oriented(row), row["compound_id"]))
    baseline = len(active) / len(ordered)
    enrichment = {}
    for fraction in (0.01, 0.05, 0.10):
        selected = max(1, math.ceil(fraction * len(ordered)))
        cutoff = oriented(ordered[selected - 1])
        above = [row for row in ordered if oriented(row) > cutoff]
        tied = [row for row in ordered if oriented(row) == cutoff]
        slots = selected - len(above)
        hits = sum(row["role"] == "active_control" for row in above)
        hits += slots * sum(row["role"] == "active_control" for row in tied) / len(tied)
        enrichment[f"{fraction:.0%}"] = {
            "selected_controls": selected,
            "active_hits": hits,
            "fraction_of_actives_recovered": hits / len(active),
            "enrichment_factor": (hits / selected) / baseline,
            "cutoff_tie_count": len(tied),
        }
    return {
        "status": "computed_descriptive_only",
        "n_active_controls": len(active),
        "n_inactive_controls": len(inactive),
        "roc_auc": wins / (len(active) * len(inactive)),
        "enrichment": enrichment,
        "small_control_set_warning": len(active) < 10 or len(inactive) < 10,
        "decoys_excluded_from_primary_metrics": sum(row["role"] == "decoy" for row in rows),
        "candidates_excluded_from_control_metrics": sum(row["role"] == "candidate" for row in rows),
        "interpretation": "Ranking performance on the supplied labels only; not binding affinity, target engagement, efficacy, safety, or anti-aging benefit.",
    }


def _symmetry_aware_pose_rmsd(rows: list[dict[str, Any]], snapshots: dict[str, Path]) -> dict[str, Any]:
    posed = [row for row in rows if row["pose_sdf"]]
    if not posed:
        return {"status": "not_requested", "n_compared": 0, "method": None}
    try:
        from rdkit import Chem, rdBase
        from rdkit.Chem import rdMolAlign
    except ImportError as exc:
        raise ValueError("RDKit is required when pose_sdf/reference_sdf columns are used") from exc

    def load(path: Path, index: int):
        supplier = Chem.SDMolSupplier(str(path), removeHs=True, sanitize=True, strictParsing=True)
        if index >= len(supplier):
            raise IndexError("requested SDF record index is outside the file")
        molecule = supplier[index]
        if molecule is None or molecule.GetNumConformers() == 0:
            raise ValueError("SDF record is invalid or has no 3D coordinates")
        for atom in molecule.GetAtoms():
            atom.SetAtomMapNum(0)
        return molecule

    errors = 0
    compared = 0
    rmsds = []
    for row in posed:
        probe_path = snapshots[row["pose_sdf"]]
        reference_path = snapshots[row["reference_sdf"]]
        try:
            probe = load(probe_path, row["pose_index"])
            reference = load(reference_path, row["reference_index"])
            probe_smiles = Chem.MolToSmiles(probe, canonical=True, isomericSmiles=True)
            reference_smiles = Chem.MolToSmiles(reference, canonical=True, isomericSmiles=True)
            if probe_smiles != reference_smiles:
                row["pose_rmsd_status"] = "chemical identity or stereochemistry differs"
                errors += 1
                continue
            row["pose_rmsd_angstrom"] = float(rdMolAlign.CalcRMS(probe, reference, maxMatches=10000))
            rmsds.append(row["pose_rmsd_angstrom"])
            row["pose_rmsd_status"] = "computed"
            compared += 1
        except (OSError, ValueError, IndexError, RuntimeError) as exc:
            row["pose_rmsd_status"] = f"unavailable: {type(exc).__name__}"
            errors += 1
    return {
        "status": "computed_with_row_errors" if errors else "computed",
        "n_compared": compared,
        "n_unavailable": errors,
        "mean_rmsd_angstrom": statistics.mean(rmsds) if rmsds else None,
        "median_rmsd_angstrom": statistics.median(rmsds) if rmsds else None,
        "method": "RDKit rdMolAlign.CalcRMS, heavy atoms, symmetry-aware atom mapping, in-place coordinates (no ligand alignment)",
        "interpretation": "Pose RMSD is meaningful only when pose and reference use a common receptor coordinate frame and chemically identical ligand states.",
    }


def create_report(
    input_arg: str,
    output_arg: str,
    direction: str,
    *,
    workbench_root: Path,
    data_root: Path,
    record: Callable[[str, dict[str, Any], list[Path]], Any],
) -> dict[str, Any]:
    if direction not in {"lower", "higher"}:
        raise ValueError("direction must be lower or higher")
    roots = [data_root.resolve(strict=False), (workbench_root / "projects").resolve(strict=False)]
    manifest = _resolve_input(input_arg, "input CSV", roots, {".csv"}, max_bytes=10 * 1024 * 1024)
    destination = _output_path(output_arg, data_root, workbench_root)
    rows, source_inputs = _read_rows(manifest, workbench_root, roots)

    with tempfile.TemporaryDirectory(prefix=".regen-docking-benchmark-", dir=destination.parent) as temp_name:
        temp = Path(temp_name)
        (temp / "inputs").mkdir()
        snapshots: dict[str, Path] = {}
        input_records = []
        for source_key, info in source_inputs.items():
            source = info["path"]
            digest = info["sha256"]
            try:
                relative = source.relative_to(workbench_root.resolve()).as_posix()
            except ValueError:
                relative = "external-input"
            if info["role"] == "manifest":
                snapshot = temp / "source-manifest.csv"
            else:
                snapshot = temp / "inputs" / f"{digest}.sdf"
                snapshots[source_key] = snapshot
            if not snapshot.exists():
                shutil.copyfile(source, snapshot)
            input_records.append({"path": relative, "role": info["role"], "sha256": digest,
                                  "bytes": info["bytes"], "snapshot": snapshot.relative_to(temp).as_posix()})

        with manifest.open("r", encoding="utf-8-sig", newline="") as source_handle:
            reader = csv.DictReader(source_handle)
            rerun_rows = list(reader)
            fieldnames = reader.fieldnames or []
        with (temp / "input.csv").open("w", encoding="utf-8", newline="") as output_handle:
            writer = csv.DictWriter(output_handle, fieldnames=fieldnames)
            writer.writeheader()
            for raw in rerun_rows:
                for field in ("pose_sdf", "reference_sdf"):
                    value = (raw.get(field) or "").strip()
                    if value:
                        source = _resolve_input(value, field, roots, {".sdf"}, relative_to=manifest.parent)
                        raw[field] = f"inputs/{sha256_file(source)}.sdf"
                writer.writerow(raw)

        for row in rows:
            if row["pose_sdf"]:
                row["pose_sdf"] = str(_resolve_input(row["pose_sdf"], "pose_sdf", roots, {".sdf"}, relative_to=manifest.parent))
                row["reference_sdf"] = str(_resolve_input(row["reference_sdf"], "reference_sdf", roots, {".sdf"}, relative_to=manifest.parent))
        pose_snapshots = {path: snapshot for path, snapshot in snapshots.items()}
        pose_metrics = _symmetry_aware_pose_rmsd(rows, pose_snapshots)
        metrics = _ranking_metrics(rows, direction)
        ranked = sorted(rows, key=lambda row: ((-row["score"] if direction == "higher" else row["score"]), row["compound_id"]))
        snapshot_by_hash = {entry["sha256"]: entry["snapshot"] for entry in input_records if entry["role"] != "manifest"}
        for rank, row in enumerate(ranked, start=1):
            row["rank"] = rank
            row["pose_sdf"] = snapshot_by_hash.get(sha256_file(Path(row["pose_sdf"])), "") if row["pose_sdf"] else ""
            row["reference_sdf"] = snapshot_by_hash.get(sha256_file(Path(row["reference_sdf"])), "") if row["reference_sdf"] else ""

        metrics_doc = {
            "schema_version": 1,
            "score_direction": direction,
            "method": rows[0]["method"],
            "score_semantics": "User-supplied docking score or model output; values are not calibrated experimental affinities.",
            "ranking": metrics,
            "pose_validation": pose_metrics,
            "input_rows": len(rows),
            "decoy_count": sum(row["role"] == "decoy" for row in rows),
            "candidate_count": sum(row["role"] == "candidate" for row in rows),
        }
        (temp / "metrics.json").write_text(json.dumps(metrics_doc, ensure_ascii=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        fieldnames = ["rank", "compound_id", "role", "score", "method", "assay_id", "label_source", "pose_sdf", "pose_index", "reference_sdf", "reference_index", "pose_rmsd_angstrom", "pose_rmsd_status"]
        with (temp / "ranked-results.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows({key: row.get(key) for key in fieldnames} for row in ranked)
        readme = [
            "# Docking validation report", "",
            f"Input rows: {len(rows)}. Method: {rows[0]['method']}. Score direction: {direction} is better.",
            f"ROC AUC (measured active vs measured inactive controls): {metrics['roc_auc']:.4f} ({metrics['n_active_controls']} active, {metrics['n_inactive_controls']} inactive).",
            "Decoys and candidates are excluded from primary control metrics. Small control sets make ranking estimates unstable.",
            "Pose RMSD is symmetry-aware and computed without ligand alignment; it requires a shared receptor frame.",
            "These are retrospective computational validation metrics, not measured binding affinity, target engagement, efficacy, safety, or anti-aging benefit.",
            "The original input table is preserved as source-manifest.csv. The normalized input.csv can be rerun because all referenced SDF files are snapshotted under inputs/.", "",
        ]
        (temp / "README.md").write_text("\n".join(readme), encoding="utf-8")
        outputs = [path for path in temp.rglob("*") if path.is_file()]
        report_manifest = {
            "schema_version": 1,
            "tool": "regen docking-benchmark",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "score_direction": direction,
            "method": rows[0]["method"],
            "inputs": input_records,
            "rdkit_version": None,
            "outputs": {path.relative_to(temp).as_posix(): {"sha256": sha256_file(path), "bytes": path.stat().st_size}
                        for path in sorted(outputs)},
        }
        try:
            from rdkit import rdBase
            report_manifest["rdkit_version"] = rdBase.rdkitVersion
        except ImportError:
            report_manifest["rdkit_version"] = "not installed; pose comparison not requested"
        (temp / "manifest.json").write_text(json.dumps(report_manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        os.rename(temp, destination)

    manifest_path = destination / "manifest.json"
    metrics_path = destination / "metrics.json"
    record("docking-benchmark", {
        "source_manifest_sha256": sha256_file(destination / "source-manifest.csv"),
        "rerun_manifest_sha256": sha256_file(destination / "input.csv"),
        "score_direction": direction,
        "input_rows": len(rows),
        "report_directory": str(destination),
    }, [manifest_path, metrics_path])
    return {"output": str(destination), "metrics": metrics_doc, "manifest": str(manifest_path)}
