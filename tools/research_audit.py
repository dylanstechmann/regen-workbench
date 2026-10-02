"""Audit saved research runs and artifact hashes without fetching or modifying data."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import regen
from regen_compute import write_json


def audit(root: Path, allow_empty: bool = False) -> dict:
    root = root.resolve()
    run_root = root / "runs"
    if not root.is_dir() or not run_root.is_dir():
        raise ValueError(f"research run directory is missing: {run_root}")

    run_records = []
    malformed_runs = []
    orphan_run_directories = []
    for directory in sorted(run_root.iterdir()):
        if not directory.is_dir():
            continue
        run_file = directory / "run.json"
        if not run_file.is_file():
            orphan_run_directories.append(directory.name)
            continue
        try:
            run = json.loads(run_file.read_text(encoding="utf-8"))
            if not isinstance(run, dict) or not isinstance(run.get("id"), str):
                raise ValueError("run record must be a JSON object with an id")
            run_records.append((directory, run))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            malformed_runs.append({"directory": directory.name, "error": type(exc).__name__})

    missing_manifests = []
    malformed_manifests = []
    hash_failures = []
    unlisted_artifacts = []
    verified = 0
    providers = {}
    conformers = 0
    for directory, run in run_records:
        manifest_path = directory / "manifest.json"
        if not manifest_path.is_file():
            missing_manifests.append({"run_id": run["id"], "status": run.get("status")})
            for path in directory.rglob("*"):
                if path.is_file() and path.name not in {"run.json", "manifest.json"}:
                    unlisted_artifacts.append(f"{run['id']}/{path.relative_to(directory).as_posix()}")
        else:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                outputs = manifest.get("outputs")
                if not isinstance(outputs, dict):
                    raise ValueError("manifest outputs must be an object")
                declared = set()
                for relative, metadata in outputs.items():
                    artifact = (directory / relative).resolve()
                    if directory.resolve() not in artifact.parents or not isinstance(metadata, dict):
                        hash_failures.append(f"{run['id']}/{relative} (invalid manifest path)")
                        continue
                    declared.add(artifact)
                    if not artifact.is_file() or regen.sha256_file(artifact) != metadata.get("sha256"):
                        hash_failures.append(f"{run['id']}/{relative}")
                    else:
                        verified += 1
                for artifact in directory.rglob("*"):
                    if artifact.is_file() and artifact.name not in {"run.json", "manifest.json"} and artifact.resolve() not in declared:
                        unlisted_artifacts.append(f"{run['id']}/{artifact.relative_to(directory).as_posix()}")
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                malformed_manifests.append({"run_id": run["id"], "error": type(exc).__name__})

        for provider in run.get("result", {}).get("providers", []):
            item = providers.setdefault(provider.get("provider", "unknown"), {"successful_calls": 0, "failed_calls": 0, "records": 0})
            item["successful_calls" if provider.get("status") == "ok" else "failed_calls"] += 1
            item["records"] += provider.get("count", 0)
        conformers += sum(c.get("conformers_converged", 0) for c in run.get("result", {}).get("compounds", []))

    empty = not run_records and not orphan_run_directories and not malformed_runs
    issues = bool(malformed_runs or orphan_run_directories or missing_manifests or malformed_manifests or hash_failures or unlisted_artifacts)
    audit_ok = not issues and (not empty or allow_empty)
    return {
        "audited_utc": regen.now(),
        "root": str(root),
        "run_count": len(run_records),
        "statuses": dict(Counter(run.get("status", "unknown") for _, run in run_records)),
        "providers": providers,
        "source_records_before_deduplication": sum(item["records"] for item in providers.values()),
        "converged_conformers": conformers,
        "verified_artifact_hashes": verified,
        "hash_failures": hash_failures,
        "missing_manifests": missing_manifests,
        "malformed_manifests": malformed_manifests,
        "malformed_runs": malformed_runs,
        "orphan_run_directories": orphan_run_directories,
        "unlisted_artifacts": unlisted_artifacts,
        "empty_root_allowed": bool(empty and allow_empty),
        "audit_ok": audit_ok,
        "interpretation": "Run/record counts are not efficacy evidence or independent replications",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=regen.DATA / "research-desk")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--allow-empty", action="store_true", help="accept an existing but empty runs directory")
    args = parser.parse_args()
    try:
        summary = audit(args.root, allow_empty=args.allow_empty)
    except ValueError as exc:
        parser.error(str(exc))
    if args.out:
        write_json(args.out, summary)
    print(json.dumps(summary, indent=2))
    if not summary["audit_ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
