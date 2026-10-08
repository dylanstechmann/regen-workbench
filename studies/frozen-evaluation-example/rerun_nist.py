#!/usr/bin/env python3
"""Try to reproduce the vendored NIST regression receipt with tools/rerun_check.py.

Needs a local regen-benchmark-kit checkout that contains commit b0087c78... and its
examples/nist_ipsc/data/features.csv (not copied into this repository), plus numpy and
scikit-learn. Writes a new report; nothing in this repository is modified.

Usage:  python rerun_nist.py --kit <path to regen-benchmark-kit> --out <new report.json>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))

import rerun_check  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kit", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    provenance = json.loads((HERE / "inputs" / "PROVENANCE.json").read_text(encoding="utf-8"))
    kit = Path(args.kit).resolve()
    spec = {
        "schema_version": 1, "entry_point": rerun_check.ENTRY_POINT,
        "producer": {"repository": str(kit), "commit": provenance["source_commit_that_added_the_receipt"]},
        "input": {"path": str(kit / "examples" / "nist_ipsc" / "data" / "features.csv"),
                  "sha256": provenance["feature_table_sha256"]},
        "receipt": {"path": str(HERE / "inputs" / "nist_ipsc_regression_metrics.json"),
                    "sha256": provenance["receipt_sha256"]},
        "arguments": {"group_by": "source_well", "target": "reference_nuclear_fraction", "seed": 0},
    }
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "spec.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        return rerun_check.main([str(path), "--out", args.out])


if __name__ == "__main__":
    raise SystemExit(main())
