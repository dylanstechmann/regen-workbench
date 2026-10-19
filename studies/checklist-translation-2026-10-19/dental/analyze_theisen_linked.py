"""Observed restoration comparator: retain contradictory identities and loads.

Default analysis is offline/stdlib. Optional extraction needs pdfplumber and
the two hash-pinned public PDF deposits in the ignored source cache.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = ROOT / "data/literature/checklist-translation-2026-10-19/dental"
MARGINAL_COLUMNS = ["code", "group", "specimen_number", "side", "interface", "measurement",
                    "material", "loading_rounds", "full_um", "not_assessable_um",
                    "assessable_um", "noncontinuous_um", "continuous_percent"]
FACES = ("buccal", "oral", "mesial", "distal")
FRACTURE_COLUMNS = ["group_label", "specimen_label"] + [f"{s}_type_{i}" for s in FACES for i in (1, 2, 3)] + ["load_N"]
CODE = re.compile(r"^(G[1-4])_(T(?:[1-9]|1[0-2]))_([DM])_(B|R1|R2)_(CmT|InCm|InT)$")


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f"Non-finite JSON constant: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=invalid)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def text_sha(path):
    return hashlib.sha256(Path(path).read_text(encoding="utf-8").encode()).hexdigest()


def number(value, missing=False):
    if value in (None, "") and missing:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid source number: {value!r}") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError("Source number must be finite and nonnegative")
    return result


def verify_cache(manifest):
    results = []
    for entry in manifest["retained_fetches"]:
        path = ROOT / entry["cache_path"]
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            raise ValueError(f"Source hash/size mismatch: {path.name}")
        results.append({"cache_path": entry["cache_path"], "sha256": actual, "verified": True})
    return results


def extract_from_cache():
    import pdfplumber  # Optional, read-only source PDF extraction.
    manifest = read_json(HERE / "source_manifest.json")
    verify_cache(manifest)
    marginal, fracture = [], []
    with pdfplumber.open(CACHE / "theisen_marginal.pdf") as doc:
        for page_index, page in enumerate(doc.pages, 1):
            tables = page.extract_tables()
            if len(tables) != 1:
                raise ValueError("Expected one marginal table on each PDF page")
            for row_index, row in enumerate(tables[0][1:], 2):
                marginal.append({"source_page": page_index, "source_table_row": row_index, "cells": row})
    with pdfplumber.open(CACHE / "theisen_fracture.pdf") as doc:
        tables = doc.pages[0].extract_tables()
        if len(tables) != 1:
            raise ValueError("Expected one fracture table")
        group_label = None
        for row_index, row in enumerate(tables[0][3:51], 4):
            if row[0]:
                group_label = row[0]
            fracture.append({"source_page": 1, "source_table_row": row_index,
                             "group_label_carried_from_merged_cell": group_label, "cells": row})
    return {"data_kind": "observed_public_numeric_tables_not_synthetic", "source_doi": "10.5281/zenodo.7412385",
            "license": "CC-BY-4.0", "attribution": "Theisen, Amato, Krastl, Attin, Blatz, Weiger and Eggmann, dataset version 3 (2022)",
            "extraction": "pdfplumber table extraction; all seven original PDF pages rendered and visually inspected; no numeric corrections",
            "marginal_columns": MARGINAL_COLUMNS, "fracture_columns": FRACTURE_COLUMNS,
            "marginal_rows": marginal, "fracture_rows": fracture}


def parse_data(data):
    if data["marginal_columns"] != MARGINAL_COLUMNS or data["fracture_columns"] != FRACTURE_COLUMNS:
        raise ValueError("Unexpected source column mapping")
    if len(data["marginal_rows"]) != 384 or len(data["fracture_rows"]) != 48:
        raise ValueError("Expected the complete 384 marginal rows and 48 fracture rows")
    fractures = {}
    for raw in data["fracture_rows"]:
        cells = raw["cells"]
        if len(cells) != 15:
            raise ValueError("Unexpected fracture column count")
        group = re.match(r"G[1-4]", raw["group_label_carried_from_merged_cell"] or "")
        if not group or not re.fullmatch(r"T(?:[1-9]|1[0-2])", cells[1] or ""):
            raise ValueError("Invalid fracture specimen label")
        key = f"{group[0]}_{cells[1]}"
        if key in fractures:
            raise ValueError("Duplicate fracture specimen")
        if any(v not in ("", None, "1") for v in cells[2:14]):
            raise ValueError("Unrecognized fracture face indicator")
        face_types = {face: [i for i in (1, 2, 3) if cells[2 + j * 3 + i - 1] == "1"]
                      for j, face in enumerate(FACES)}
        fractures[key] = {"key": key, "group": group[0], "load_N": number(cells[14]),
                          "face_types": face_types,
                          "any_below_bone_fracture": any(3 in types for types in face_types.values()),
                          "source_page": raw["source_page"], "source_table_row": raw["source_table_row"]}
    expected = {f"G{g}_T{t}" for g in range(1, 5) for t in range(1, 13)}
    if set(fractures) != expected:
        raise ValueError("Incomplete fracture registry")
    margins, codes, ambiguous = [], set(), set()
    for raw in data["marginal_rows"]:
        c = raw["cells"]
        if len(c) != 13:
            raise ValueError("Unexpected marginal column count")
        match = CODE.fullmatch(c[0] or "")
        if not match or c[0] in codes:
            raise ValueError("Invalid or duplicate marginal row code")
        codes.add(c[0])
        group, tooth, side, state, interface = match.groups()
        key = f"{group}_{tooth}"
        declared_key = f"G{c[1]}_T{c[2]}"
        if declared_key not in fractures:
            raise ValueError("Declared marginal identity outside fracture registry")
        identity_conflict = key != declared_key
        if identity_conflict:
            # Both ends of a conflicting identity are ambiguous. A destination
            # tooth is not considered safe merely because its own rows agree.
            ambiguous.update((key, declared_key))
        if c[3] != {"D": "distal", "M": "mesial"}[side]:
            raise ValueError("Source side conflicts with row code")
        if c[4] != {"CmT": "Composit-Tooth", "InCm": "Inlay-Composit", "InT": "Inlay-Tooth"}[interface]:
            raise ValueError("Source interface conflicts with row code")
        expected_state = ("baseline_Filling" if interface == "CmT" else "baseline_Inlay") if state == "B" else {"R1": "1. thermomechanical cycle", "R2": "2. thermomechanical cycle"}[state]
        if c[5] != expected_state:
            raise ValueError("Source measurement state conflicts with row code")
        full, unassess = number(c[8]), number(c[9], missing=True)
        assess, gap = number(c[10].split()[0]), number(c[11])
        continuous = number(c[12].rstrip("%"))
        if full <= 0 or assess <= 0 or assess > full + 0.011 or gap > assess or continuous > 100:
            raise ValueError("Impossible marginal length or proportion")
        if unassess is not None and (unassess > full or abs(full - unassess - assess) > 0.011):
            raise ValueError("Source lengths do not reconcile within printed rounding")
        if abs(100 * (1 - gap / assess) - continuous) > 0.011:
            raise ValueError("Source continuous percentage does not reconcile")
        margins.append({"code": c[0], "key": key, "declared_key": declared_key, "group": group,
                        "side": side, "state": state, "interface": interface,
                        "identity_conflict": identity_conflict, "full_um": full,
                        "not_assessable_um": unassess, "assessable_um": assess,
                        "noncontinuous_um": gap, "source_continuous_percent": continuous,
                        "noncontinuous_assessable_percent": 100 * gap / assess,
                        "source_page": raw["source_page"], "source_table_row": raw["source_table_row"]})
    return margins, fractures, ambiguous


def full_margin_bounds(row):
    """Printed-value identification bounds; unknown scan regions may all gap.

    A blank non-assessable field remains unknown, despite nearly equal printed
    full/assessable lengths. These bounds are deliberately conservative and are
    not measurement-error confidence intervals.
    """
    low = row["noncontinuous_um"] / row["full_um"]
    missing = row["not_assessable_um"]
    high = 1.0 if missing is None else min(1.0, (row["noncontinuous_um"] + missing) / row["full_um"])
    return 100 * low, 100 * high


def summarize_pairs(margins, ambiguous, strict):
    index = {(r["key"], r["side"], r["state"], r["interface"]): r for r in margins}
    summaries = []
    for group in ("G1", "G2", "G3", "G4"):
        for interface, side in (("InCm", "D"), ("InT", "M")):
            pairs = []
            for t in range(1, 13):
                key = f"{group}_T{t}"
                if strict and key in ambiguous:
                    continue
                before = index.get((key, side, "B", interface))
                after = index.get((key, side, "R2", interface))
                if before is None or after is None:
                    raise ValueError("Missing registered inlay-interface state")
                b0, b1 = full_margin_bounds(before)
                a0, a1 = full_margin_bounds(after)
                pairs.append((before, after, a0 - b1, a1 - b0))
            if not pairs:
                continue
            summaries.append({"group": group, "interface": interface, "n_teeth": len(pairs),
                              "baseline_mean_noncontinuous_assessable_percent": statistics.mean(b["noncontinuous_assessable_percent"] for b, _, _, _ in pairs),
                              "postload_mean_noncontinuous_assessable_percent": statistics.mean(a["noncontinuous_assessable_percent"] for _, a, _, _ in pairs),
                              "mean_paired_change_percentage_points": statistics.mean(a["noncontinuous_assessable_percent"] - b["noncontinuous_assessable_percent"] for b, a, _, _ in pairs),
                              "mean_paired_change_full_scanned_bounds_percentage_points": [statistics.mean(lo for _, _, lo, _ in pairs), statistics.mean(hi for _, _, _, hi in pairs)],
                              "postload_recorded_positive_gap_teeth": sum(a["noncontinuous_um"] > 0 for _, a, _, _ in pairs),
                              "postload_missing_unassessable_field_teeth": sum(a["not_assessable_um"] is None for _, a, _, _ in pairs)})
    return summaries


def bridge_availability():
    path = ROOT / "studies/checklist-mechanisms-2026-10-19/dental/analyze_linked_material_outcomes.py"
    spec = importlib.util.spec_from_file_location("previous_dental_bridge", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Reuse the prior bridge's missing-outcome handling, not an invented adapter
    # that equates optical margin lengths with tracer leakage or peak loads
    # with fatigue event times.
    return {"prior_bridge_text_sha256": text_sha(path), "registered_teeth": 48,
            "depth_example_result": module.depth_result(None, None),
            "leakage_example_result": list(module.leakage_bounds(None)),
            "fatigue_example_result": list(module.fatigue_state(None, 1200000)),
            "measured_repair_depth_n": 0, "tracer_leakage_n": 0, "fatigue_event_time_n": 0,
            "paired_intended_depth_interface_analysis": "unavailable",
            "donor_balanced_analysis": "unavailable_unknown_donor_crosswalk",
            "host_substrate_resolution": "tooth substance in optical margin labels; no row-specific enamel/dentin segmentation",
            "failure_of_full_contract": "No regenerated enamel/dentin, native living PDL, gum, pulp or pose after finite support withdrawal is measured"}


def analyze(data):
    margins, fractures, ambiguous = parse_data(data)
    rows_by_key = defaultdict(list)
    for row in margins:
        rows_by_key[row["key"]].append(row)
    specimen_rows, known_joint, unknown_joint, conditional_joint = [], 0, 0, 0
    for key, fracture in fractures.items():
        final = [r for r in rows_by_key[key] if r["state"] == "R2" and r["interface"] in ("InCm", "InT")]
        if len(final) != 2:
            raise ValueError("Each source-code tooth must have two final inlay interfaces")
        detected = any(r["noncontinuous_um"] > 0 for r in final)
        root_fracture = fracture["any_below_bone_fracture"]
        conditional_joint += int(detected and root_fracture)
        unresolved = key in ambiguous
        if root_fracture and unresolved:
            joint = "unknown_identity"
            unknown_joint += 1
        elif root_fracture and detected:
            joint = "recorded_joint_positive"
            known_joint += 1
        else:
            joint = "recorded_joint_negative"
        specimen_rows.append({"source_code_key": key, "identity_status": "unresolved_conflict_component" if unresolved else "internally_consistent",
                              "donor_id": None, "measured_repair_depth_um": None,
                              "fracture_load_N_literal": fracture["load_N"],
                              "source_code_conditional_detected_gap": detected,
                              "terminal_any_below_bone_fracture": root_fracture,
                              "joint_status_with_identity_uncertainty": joint})
    load_summary = []
    for group in ("G1", "G2", "G3", "G4"):
        rows = [v for v in fractures.values() if v["group"] == group]
        loads = [r["load_N"] for r in rows]
        load_summary.append({"group": group, "n_literal_loads": len(loads),
                             "literal_mean_N": statistics.mean(loads), "literal_sample_sd_N": statistics.stdev(loads),
                             "face_category_counts": {str(i): sum(i in types for r in rows for types in r["face_types"].values()) for i in (1, 2, 3)},
                             "tooth_any_category_counts": {str(i): sum(any(i in types for types in r["face_types"].values()) for r in rows) for i in (1, 2, 3)}})
    without = [v["load_N"] for key, v in fractures.items() if v["group"] == "G1" and key != "G1_T11"]
    result = {"data_kind": "observed_restoration_comparator_with_unresolved_source_errors",
              "n_registered_teeth": len(fractures), "n_marginal_rows": len(margins),
              "identity_audit": {"n_conflicting_rows": sum(r["identity_conflict"] for r in margins),
                                 "conflicting_rows": [{k: r[k] for k in ("code", "key", "declared_key", "source_page", "source_table_row")} for r in margins if r["identity_conflict"]],
                                 "ambiguous_tooth_keys_both_ends": sorted(ambiguous),
                                 "n_ambiguous_teeth": len(ambiguous), "n_internally_consistent_teeth": len(fractures) - len(ambiguous)},
              "blank_nonassessable_fields": [r["code"] for r in margins if r["not_assessable_um"] is None],
              "strict_internal_identity_paired_margin_summaries": summarize_pairs(margins, ambiguous, True),
              "conditional_trust_row_codes_paired_margin_summaries": summarize_pairs(margins, ambiguous, False),
              "literal_fracture_summaries": load_summary,
              "g1_load_ambiguity_diagnostic": {"literal_G1_T11_N": fractures["G1_T11"]["load_N"],
                                               "published_mean_N": 1953.2, "published_sample_sd_N": 483.4,
                                               "omit_G1_T11_n": len(without), "omit_G1_T11_mean_N": statistics.mean(without),
                                               "omit_G1_T11_sample_sd_N": statistics.stdev(without),
                                               "interpretation": "Omission numerically reproduces publication rounding; no evidence resolves whether source value or exclusion was intended. Literal value is retained."},
              "joint_recorded_gap_and_terminal_below_bone_fracture": {"denominator_teeth": 48, "known_joint_positive": known_joint,
                                                                     "unknown_from_identity": unknown_joint,
                                                                     "finite_cohort_proportion_bounds": [known_joint / 48, (known_joint + unknown_joint) / 48],
                                                                     "conditional_trust_row_codes_joint_positive": conditional_joint,
                                                                     "interpretation": "Detected noncontinuous optical margin at postload inspection and later terminal fracture below simulated bone, not simultaneous events, biological repair, causal coupling, true gap-free classification, or failure incidence during cycling"},
              "prior_bridge": bridge_availability(),
              "specimen_links": specimen_rows}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-cache", action="store_true")
    parser.add_argument("--extract-from-cache", action="store_true")
    args = parser.parse_args()
    if args.extract_from_cache:
        write_json(HERE / "source_extract.json", extract_from_cache())
    result = analyze(read_json(HERE / "source_extract.json"))
    result["source_extract_text_sha256"] = text_sha(HERE / "source_extract.json")
    if args.verify_cache:
        result["cache_verification"] = verify_cache(read_json(HERE / "source_manifest.json"))
    out = HERE / "derived"
    write_json(out / "theisen_linked_results.json", result)
    with (out / "theisen_specimen_links.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(result["specimen_links"][0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in result["specimen_links"]:
            writer.writerow({k: "unknown" if v is None else v for k, v in row.items()})
    print(json.dumps({"registered_teeth": result["n_registered_teeth"], "internally_consistent_teeth": result["identity_audit"]["n_internally_consistent_teeth"],
                      "joint": result["joint_recorded_gap_and_terminal_below_bone_fracture"], "outputs": [str(out / "theisen_linked_results.json"), str(out / "theisen_specimen_links.tsv")]}, indent=2))


if __name__ == "__main__":
    main()
