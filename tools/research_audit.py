"""Summarize saved research runs and verify their artifact hashes, without fetching."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import regen
from regen_compute import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=regen.DATA / "research-desk")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    runs = [json.loads(p.read_text()) for p in (args.root / "runs").glob("*/run.json")]
    failures, verified, conformers = [], 0, 0
    providers = {}
    for run in runs:
        path = args.root / "runs" / run["id"]
        if (path / "manifest.json").exists():
            manifest = json.loads((path / "manifest.json").read_text())
            for file, meta in manifest["outputs"].items():
                artifact = path / file
                if not artifact.is_file() or hashlib.sha256(artifact.read_bytes()).hexdigest() != meta["sha256"]:
                    failures.append(f"{run['id']}/{file}")
                else:
                    verified += 1
        for provider in run.get("result", {}).get("providers", []):
            item = providers.setdefault(provider["provider"], {"successful_calls": 0, "failed_calls": 0, "records": 0})
            item["successful_calls" if provider["status"] == "ok" else "failed_calls"] += 1
            item["records"] += provider.get("count", 0)
        conformers += sum(c.get("conformers_converged", 0) for c in run.get("result", {}).get("compounds", []))
    summary = {"audited_utc": regen.now(), "run_count": len(runs), "statuses": dict(Counter(r["status"] for r in runs)),
               "providers": providers, "source_records_before_deduplication": sum(p["records"] for p in providers.values()),
               "converged_conformers": conformers, "verified_artifact_hashes": verified, "hash_failures": failures,
               "interpretation": "Run/record counts are not efficacy evidence or independent replications"}
    if args.out:
        write_json(args.out, summary)
    print(json.dumps(summary, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
