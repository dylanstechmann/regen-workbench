"""Post-thermal-cycle OCT interface evidence with source hierarchy preserved.

Worksheet blocks are locations, not invented tooth IDs. Calculations are
descriptive and never join the unlinked OCT and tensile assay records.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = ROOT / "data/literature/checklist-integration-2026-10-19/materials"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
BLOCK_STARTS = (2, 13, 24, 35, 46)
GROUPS = (("A", "ER"), ("B", "ER/CHX"), ("C", "SE"), ("D", "SE/CHX"))


def load(path):
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


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_sha(path):
    return hashlib.sha256(Path(path).read_text(encoding="utf-8").encode()).hexdigest()


def percent(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError("OCT percentage must be finite and within 0-100")
    return float(value)


def extract_oct():
    manifest = load(HERE / "source_manifest.json")
    entry = next(e for e in manifest["retained_files"] if e["role"] == "oct_numeric_workbook")
    path = ROOT / entry["cache_path"]
    if sha(path) != entry["sha256"]:
        raise ValueError("Workbook byte hash mismatch")
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = workbook.findall("s:sheets/s:sheet", NS)
        if len(sheets) != 1 or sheets[0].get("name") != "OCT data":
            raise ValueError("Unexpected source worksheet")
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(si.itertext()) for si in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        member = "xl/worksheets/sheet1.xml"
        raw = archive.read(member)
        cells, formulas = {}, []
        for c in ET.fromstring(raw).findall("s:sheetData/s:row/s:c", NS):
            if c.find("s:f", NS) is not None:
                formulas.append(c.get("r"))
            v = c.find("s:v", NS)
            if c.get("t") == "inlineStr":
                cells[c.get("r")] = "".join(c.find("s:is", NS).itertext())
            elif v is not None:
                cells[c.get("r")] = strings[int(v.text)] if c.get("t") == "s" else float(v.text)
        groups = []
        for col, group in GROUPS:
            if cells[f"{col}1"] != group:
                raise ValueError("Source group headers changed")
            blocks = []
            for start in BLOCK_STARTS:
                blocks.append({"source_row_range": [start, start + 9], "source_cells": [f"{col}{r}" for r in range(start, start + 10)],
                               "values_percent": [percent(cells[f"{col}{r}"]) for r in range(start, start + 10)],
                               "tooth_id": None, "donor_id": None})
            groups.append({"group": group, "source_column": col, "worksheet_blocks": blocks})
        expected = {f"{c}1" for c, _ in GROUPS} | {f"{c}{r}" for c, _ in GROUPS for start in BLOCK_STARTS for r in range(start, start + 10)}
        unexpected = {a: v for a, v in cells.items() if a not in expected and v not in (None, "")}
        if unexpected or formulas:
            raise ValueError("Unexpected populated cells or formulas; source needs requalification")
    return {"source_sheet": "OCT data", "source_member": member, "source_member_sha256": hashlib.sha256(raw).hexdigest(),
            "source_formula_addresses": formulas, "source_numeric_observations": 200, "groups": groups}


def longest_equal_run(left, right):
    """Record exact equality, without deduplication or a claim about its cause."""
    best = (0, None, None)
    for i in range(len(left)):
        for j in range(len(right)):
            n = 0
            while i + n < len(left) and j + n < len(right) and left[i + n] == right[j + n]:
                n += 1
            if n > best[0]:
                best = (n, i, j)
    return best


def summarize_group(group):
    blocks = group["worksheet_blocks"]
    if len(blocks) != 5:
        raise ValueError("Five source row blocks required")
    for start, block in zip(BLOCK_STARTS, blocks):
        if block["source_row_range"] != [start, start + 9] or len(block["values_percent"]) != 10:
            raise ValueError("Incomplete source block")
        expected_cells = [f"{group['source_column']}{r}" for r in range(start, start + 10)]
        if block["source_cells"] != expected_cells:
            raise ValueError("Source coordinates do not match block values")
        for value in block["values_percent"]:
            percent(value)
    raw = [v for b in blocks for v in b["values_percent"]]
    means = [statistics.mean(b["values_percent"]) for b in blocks]
    leave_one_block = [statistics.mean([v for j, b in enumerate(blocks) if i != j for v in b["values_percent"]]) for i in range(5)]
    repeats = []
    for i, left in enumerate(blocks):
        for right in blocks[i + 1:]:
            n, a, b = longest_equal_run(left["values_percent"], right["values_percent"])
            if n >= 3:
                repeats.append({"length": n, "left_source_cells": left["source_cells"][a:a + n],
                                "right_source_cells": right["source_cells"][b:b + n],
                                "interpretation": "Exact repeated values retained. Could reflect measurement coincidence, reuse or transcription; source identity records are needed, and no cause is assigned."})
    return {"group": group["group"], "n_source_scan_rows": len(raw),
            "source_row_mean_percent": statistics.mean(raw), "source_row_median_percent": statistics.median(raw),
            "source_row_sample_sd_percent_not_independent_tooth_sd": statistics.stdev(raw),
            "source_row_range_percent": [min(raw), max(raw)],
            "conditional_block_as_tooth_summary": {"n_worksheet_blocks": 5, "block_means_percent": means,
                "mean_percent": statistics.mean(means), "sample_sd_of_block_means_percent": statistics.stdev(means),
                "qualification": "Conditional worksheet-block nesting sensitivity; paper reports five teeth and ten scans per tooth, but no individual identity crosswalk is present. No donor count or independent replication is inferred from row blocks."},
            "leave_one_source_block_out_means_percent": leave_one_block,
            "leave_one_block_out_range_percent": [min(leave_one_block), max(leave_one_block)],
            "repeated_runs_at_least_three_values": repeats}


def calculate(data):
    if data["data_kind"] != "observed_source_numeric_extract_not_synthetic":
        raise ValueError("Observed source inputs required")
    groups = data["oct_source"]["groups"]
    if Counter(g["group"] for g in groups) != Counter(dict((name, 1) for _, name in GROUPS)):
        raise ValueError("Expected the four original source groups")
    for g in groups:
        if (g["source_column"], g["group"]) not in GROUPS:
            raise ValueError("Source column/group mapping changed")
    summaries = [summarize_group(g) for g in groups]
    by_group = {g["group"]: g for g in summaries}
    contrasts = []
    for mode in ("ER", "SE"):
        control, treated = by_group[mode], by_group[mode + "/CHX"]
        control_low, control_high = control["leave_one_block_out_range_percent"]
        treated_low, treated_high = treated["leave_one_block_out_range_percent"]
        contrasts.append({"etch_mode": mode, "contrast": f"{mode}/CHX minus {mode}",
                          "difference_of_source_means_percentage_points": treated["source_row_mean_percent"] - control["source_row_mean_percent"],
                          "independent_block_deletion_contrast_range_percentage_points": [treated_low - control_high, treated_high - control_low],
                          "deletion_combinations": 25,
                          "qualification": "Delete one ten-row source block from each group, independently. This is a conditional record-sensitivity range, not a CI, matched-pair effect, actual tooth loss model or population effect."})
    reconciliation = []
    for published in data["published_OCT_table2"]:
        calculated = by_group[published["group"]]
        block = calculated["conditional_block_as_tooth_summary"]
        reconciliation.append({"group": published["group"], "published_mean_percent": published["mean_percent"],
                               "published_sd_percent": published["sd_percent"],
                               "rounded_block_mean_matches": round(block["mean_percent"], 1) == published["mean_percent"],
                               "rounded_block_sd_matches": round(block["sample_sd_of_block_means_percent"], 1) == published["sd_percent"],
                               "qualification": "Numerical agreement supports this worksheet segmentation; it does not recover physical specimen or donor IDs."})
    return {"scope": "Post-thermal-cycle established-restorative dentin-interface benchmark, not enamel regrowth",
            "group_summaries": summaries, "source_table2_reconciliation": reconciliation,
            "etch_specific_CHX_descriptive_contrasts": contrasts,
            "SE_minus_ER_contrast_of_mean_differences_percentage_points": contrasts[1]["difference_of_source_means_percentage_points"] - contrasts[0]["difference_of_source_means_percentage_points"],
            "new_p_value_or_confidence_interval": None, "equivalence_established": False,
            "source_reported_nominal_cavity_depth_mm": 2, "actual_specimen_repair_depth_um": None,
            "thermal_cycles_before_OCT": 10000, "mechanical_fatigue_cycle_history": None,
            "baseline_OCT_before_aging": None, "depth_response_or_within_specimen_change": None,
            "source_reported_OCT_teeth_per_group": 5, "independent_donor_count": None,
            "cross_endpoint_specimen_pairing": None, "OCT_to_microtensile_correlation": None,
            "published_unlinked_tensile_table3_not_pooled": data["published_unlinked_tensile_table3"],
            "pretest_failures_or_unreported_losses": None,
            "full_native_restoration_and_finite_support_withdrawal_qualified": False,
            "assay_qualification": data["assay_qualification"]}


def check_cache(data):
    manifest = load(HERE / "source_manifest.json")
    for source in manifest["retained_files"]:
        p = ROOT / source["cache_path"]
        if not p.exists() or p.stat().st_size != source["bytes"] or sha(p) != source["sha256"]:
            raise ValueError(f"Cached source mismatch: {source['cache_path']}")
    if extract_oct() != data["oct_source"]:
        raise ValueError("Original XLSX extraction does not exactly match observed inputs")
    return {"retained_byte_hashes_checked": len(manifest["retained_files"]), "OCT_numeric_cells_checked": 200,
            "exact_source_extract_match": True, "images_read_or_digitized": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-cache", action="store_true")
    args = parser.parse_args()
    data = load(HERE / "inputs.json")
    result = calculate(data)
    result["inputs_text_sha256"] = text_sha(HERE / "inputs.json")
    dump(HERE / "results.json", result)
    if args.check_cache:
        print(json.dumps(check_cache(data)))
    print(json.dumps({"OCT_scan_rows": 200, "source_groups": 4, "joint_depth_interface_eligibility": False}))


if __name__ == "__main__":
    main()
