#!/usr/bin/env python3
"""Create a reproducible, donor-crossed allocation manifest from a roster TSV."""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path


REQUIRED = {"donor_id", "role", "age_years", "age_stratum"}
FIELDS = [
    "allocation_id",
    "target_donor_id",
    "target_age_years",
    "target_age_stratum",
    "niche_donor_id",
    "niche_lot_id",
    "niche_age_years",
    "niche_age_stratum",
    "exposure_condition",
    "construct_rep",
    "condition_key",
    "batch_id",
    "randomized_order",
    "blinded_code",
    "seed",
]


def load_roster(path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Roster is missing required columns: {', '.join(sorted(missing))}")
        rows = [row for row in reader if any((value or "").strip() for value in row.values())]

    targets: list[dict[str, str]] = []
    niches: list[dict[str, str]] = []
    seen: dict[str, str] = {}
    for row in rows:
        donor_id = (row.get("donor_id") or "").strip()
        role = (row.get("role") or "").strip().lower()
        if not donor_id:
            raise ValueError("Every nonblank roster row needs a pseudonymous donor_id")
        if role not in {"target", "niche"}:
            raise ValueError(f"Donor {donor_id} has invalid role {role!r}; use target or niche")
        if donor_id in seen:
            if seen[donor_id] != role:
                raise ValueError("Target and niche roles must use independent donors")
            raise ValueError(f"Duplicate donor_id: {donor_id}")
        seen[donor_id] = role
        try:
            age = float(row["age_years"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Donor {donor_id} needs numeric age_years") from exc
        if not math.isfinite(age) or age < 0:
            raise ValueError(f"Donor {donor_id} has invalid age_years {age!r}")
        stratum = (row.get("age_stratum") or "").strip()
        if not stratum:
            raise ValueError(f"Donor {donor_id} needs an age_stratum")
        item = {"donor_id": donor_id, "age_years": f"{age:g}", "age_stratum": stratum}
        (targets if role == "target" else niches).append(item)

    if not targets or not niches:
        raise ValueError("Roster must include both target and niche donors")
    overlap = {row["donor_id"] for row in targets} & {row["donor_id"] for row in niches}
    if overlap:
        raise ValueError(f"Target and niche roles must use independent donors: {sorted(overlap)}")
    target_strata = {row["age_stratum"] for row in targets}
    niche_strata = {row["age_stratum"] for row in niches}
    if len(target_strata) != 2 or target_strata != niche_strata:
        raise ValueError("Target and niche donors must share exactly two prospective age_stratum labels")
    return targets, niches


def build_rows(
    targets: list[dict[str, str]],
    niches: list[dict[str, str]],
    constructs_per_pair: int,
    controls_per_target: int,
    seed: int,
    batch_capacity: int,
) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    for target in targets:
        for rep in range(1, controls_per_target + 1):
            rows.append(make_row(target, None, "unconditioned", rep, seed))
        for niche in niches:
            for rep in range(1, constructs_per_pair + 1):
                rows.append(make_row(target, niche, "conditioned", rep, seed))

    if not rows:
        raise ValueError("The roster produced no allocations")
    batch_count = math.ceil(len(rows) / batch_capacity)
    batches: list[list[dict[str, str]]] = [[] for _ in range(batch_count)]
    group_counts: list[Counter[tuple[str, str, str]]] = [Counter() for _ in batches]
    by_group: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (row["target_age_stratum"], row["exposure_condition"], row["niche_age_stratum"])
        by_group[key].append(row)

    # Balance every target-age × exposure × niche-age group across assay batches.
    for key in sorted(by_group):
        rng.shuffle(by_group[key])
        for row in by_group[key]:
            available = [i for i, batch in enumerate(batches) if len(batch) < batch_capacity]
            if not available:
                batches.append([])
                group_counts.append(Counter())
                available = [len(batches) - 1]
            least_group = min(group_counts[i][key] for i in available)
            candidates = [i for i in available if group_counts[i][key] == least_group]
            least_full = min(len(batches[i]) for i in candidates)
            candidates = [i for i in candidates if len(batches[i]) == least_full]
            batch_index = rng.choice(candidates)
            batches[batch_index].append(row)
            group_counts[batch_index][key] += 1

    allocation_index = 0
    blinded_codes: set[str] = set()
    for batch_index, batch in enumerate(batches, start=1):
        rng.shuffle(batch)
        for order, row in enumerate(batch, start=1):
            allocation_index += 1
            row["allocation_id"] = f"A{allocation_index:05d}"
            row["batch_id"] = f"B{batch_index:03d}"
            row["randomized_order"] = str(order)
            code = f"S{rng.getrandbits(32):08X}"
            while code in blinded_codes:
                code = f"S{rng.getrandbits(32):08X}"
            blinded_codes.add(code)
            row["blinded_code"] = code
    return sorted(rows, key=lambda row: (row["batch_id"], int(row["randomized_order"])))


def make_row(
    target: dict[str, str],
    niche: dict[str, str] | None,
    exposure: str,
    rep: int,
    seed: int,
) -> dict[str, str]:
    niche_id = niche["donor_id"] if niche else ""
    niche_age = niche["age_years"] if niche else ""
    niche_stratum = niche["age_stratum"] if niche else "none"
    condition_key = "|".join((target["age_stratum"], exposure, niche_stratum))
    return {
        "allocation_id": "",
        "target_donor_id": target["donor_id"],
        "target_age_years": target["age_years"],
        "target_age_stratum": target["age_stratum"],
        "niche_donor_id": niche_id,
        "niche_lot_id": f"L-{niche_id}" if niche else "",
        "niche_age_years": niche_age,
        "niche_age_stratum": niche_stratum,
        "exposure_condition": exposure,
        "construct_rep": str(rep),
        "condition_key": condition_key,
        "batch_id": "",
        "randomized_order": "",
        "blinded_code": "",
        "seed": str(seed),
    }


def write_manifest(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roster", type=Path, required=True, help="Pseudonymized donor roster TSV")
    parser.add_argument("--out", type=Path, required=True, help="Randomized allocation manifest TSV")
    parser.add_argument("--seed", type=int, required=True, help="Record this seed in the protocol")
    parser.add_argument("--batch-capacity", type=int, required=True, help="Maximum constructs per processing batch")
    parser.add_argument("--constructs-per-pair", type=int, default=1)
    parser.add_argument("--controls-per-target", type=int, default=1)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output manifest")
    args = parser.parse_args()
    if args.out.resolve() == args.roster.resolve():
        parser.error("output path must not overwrite the donor roster")
    if args.out.exists() and not args.force:
        parser.error(f"output already exists: {args.out}; choose a new path or pass --force")
    if args.batch_capacity < 1 or args.constructs_per_pair < 1 or args.controls_per_target < 1:
        parser.error("batch capacity and replicate counts must be positive integers")
    try:
        targets, niches = load_roster(args.roster)
        rows = build_rows(
            targets, niches, args.constructs_per_pair, args.controls_per_target,
            args.seed, args.batch_capacity,
        )
        write_manifest(rows, args.out)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"Wrote {len(rows)} allocations for {len(targets)} target donors and "
        f"{len(niches)} niche donors to {args.out}; technical constructs remain nested."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
