"""Compare two curated ResearchDesk source catalogs by entry and artifact ID."""

import argparse
import json
from pathlib import Path

import research_progress as progress


ENTRY_FIELDS = ("title", "topic", "updated_on", "evidence_kind", "result", "boundary", "next_step")
ARTIFACT_FIELDS = ("label", "path", "sha256_lf_text", "bytes_utf8_lf")


def changes(before, after, fields):
    return {
        key: {"before": before[key], "after": after[key]}
        for key in fields if before[key] != after[key]
    }


def by_id(rows):
    return {row["id"]: row for row in rows}


def compare(before_path, after_path, *, verify_after_root=None):
    before = by_id(progress._document(before_path.parent, before_path))
    after = by_id(progress._document(after_path.parent, after_path))
    changed = []
    for ident in sorted(before.keys() & after.keys()):
        fields = changes(before[ident], after[ident], ENTRY_FIELDS)
        old = by_id(before[ident]["artifacts"])
        new = by_id(after[ident]["artifacts"])
        artifacts = {}
        for aid in sorted(old.keys() | new.keys()):
            if aid not in old or aid not in new:
                artifacts[aid] = {"before": old.get(aid), "after": new.get(aid)}
            else:
                delta = changes(old[aid], new[aid], ARTIFACT_FIELDS)
                if delta:
                    artifacts[aid] = {"changed_fields": delta}
        if fields or artifacts:
            changed.append({"id": ident, "changed_fields": fields, "artifacts": artifacts})
    report = {
        "schema_version": 1,
        "added_entries": sorted(after.keys() - before.keys()),
        "removed_entries": sorted(before.keys() - after.keys()),
        "changed_entries": changed,
    }
    if verify_after_root is not None:
        checked = 0
        unavailable = []
        for ident in sorted(after):
            for artifact in sorted(after[ident]["artifacts"], key=lambda a: a["id"]):
                checked += 1
                try:
                    progress._artifact_bytes(verify_after_root, artifact)
                except (OSError, ValueError):
                    unavailable.append({"entry_id": ident, "artifact_id": artifact["id"]})
        report["after_artifact_check"] = {"checked": checked, "unavailable": unavailable}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--verify-after-root", type=Path, metavar="CHECKOUT",
                        help="Check the after catalog’s pinned study files under this checkout")
    args = parser.parse_args()
    try:
        report = compare(args.before, args.after, verify_after_root=args.verify_after_root)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("after_artifact_check", {}).get("unavailable"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
