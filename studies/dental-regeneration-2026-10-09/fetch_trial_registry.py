"""Retrieve the official jRCT record for the 2026 ASC/PRP periodontal trial."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import regen


def main():
    regen.ensure_dirs()
    registry_id = "jRCTb030190173"
    url = f"https://jrct.mhlw.go.jp/latest-detail/{registry_id}"
    raw = regen.http_bytes(url)
    if registry_id.encode("ascii") not in raw:
        raise ValueError("Registry response does not identify the requested trial")
    target = regen.DATA / "literature" / f"{registry_id}-2026-10-09.html"
    target.write_bytes(raw)
    receipt = regen.record("dental-trial-registry", {"registry_id": registry_id, "url": url}, [target])
    public = {
        "registry_id": registry_id,
        "url": url,
        "retrieved_utc": regen.now(),
        "response_sha256": regen.sha256_file(target),
        "local_provenance_receipt": receipt.name,
        "scope": "Official registry result and participant-flow summary; this receipt authenticates retrieved bytes, not interpretation.",
    }
    (Path(__file__).parent / "trial_registry_receipt.json").write_text(
        json.dumps(public, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"registry_id": registry_id}))


if __name__ == "__main__":
    main()
