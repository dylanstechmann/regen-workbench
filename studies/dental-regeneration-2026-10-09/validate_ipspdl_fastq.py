"""Validate bzip2 integrity and four-line FASTQ structure for the audited runs."""

from __future__ import annotations

import argparse
import bz2
import json
from pathlib import Path


def validate(path: Path) -> dict[str, object]:
    records = 0
    bad: dict[str, object] | None = None
    with bz2.open(path, "rt", encoding="ascii", errors="replace", newline="") as handle:
        while True:
            header = handle.readline()
            if not header:
                break
            sequence = handle.readline()
            plus = handle.readline()
            quality = handle.readline()
            records += 1
            if not sequence or not plus or not quality:
                bad = {"record": records, "reason": "incomplete four-line record"}
                break
            seq = sequence.rstrip("\r\n")
            qual = quality.rstrip("\r\n")
            if not header.startswith("@"):
                bad = {"record": records, "reason": "header does not begin with @"}
                break
            if not plus.startswith("+"):
                bad = {"record": records, "reason": "separator line does not begin with +"}
                break
            if len(seq) != len(qual):
                bad = {"record": records, "reason": "sequence and quality lengths differ",
                       "sequence_length": len(seq), "quality_length": len(qual)}
                break
    return {"file": path.name, "records_read": records, "status": "passed" if bad is None else "failed",
            "failure": bad}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    results = [validate(path) for path in args.files]
    print(json.dumps(results, indent=2))
    if any(result["status"] != "passed" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
