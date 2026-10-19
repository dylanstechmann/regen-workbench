"""Observed HEA bulk mechanics: source traces are not independent specimens.

Default calculations use a small factual numeric extract. Optional source
extraction/hash verification reads selected XLSX XML only, never images.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
WORKBOOK = ROOT / "data/literature/checklist-function-2026-10-19/dental/HEA2024_source_data.xlsx"
SOURCE_SHA = "242fcb42e123669a80c891f74036c979de7be78c1e78d7cac4d0eb31a0f717b8"


def load(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("Duplicate JSON key")
            out[key] = value
        return out
    def invalid(value):
        raise ValueError(f"Non-finite JSON constant: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=invalid)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def byte_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def text_sha(path):
    return hashlib.sha256(Path(path).read_text(encoding="utf-8").encode()).hexdigest()


def numeric(value, nonnegative=True):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("Finite numeric source observation required")
    if nonnegative and value < 0:
        raise ValueError("Negative source observation")
    return float(value)


def worksheet(archive, index, strings):
    """Cell values and formula presence; no chart, drawing or image access."""
    member = f"xl/worksheets/sheet{index}.xml"
    raw = archive.read(member)
    root = ET.fromstring(raw)
    cells, formulas = {}, []
    for cell in root.findall("s:sheetData/s:row/s:c", NS):
        if cell.find("s:f", NS) is not None:
            formulas.append(cell.get("r"))
        value = cell.find("s:v", NS)
        if value is not None:
            cells[cell.get("r")] = strings[int(value.text)] if cell.get("t") == "s" else float(value.text)
    return cells, {"member": member, "member_sha256": hashlib.sha256(raw).hexdigest(),
                   "populated_value_cells": len(cells), "formula_cell_addresses": formulas}


def extract_source(path=WORKBOOK):
    if byte_sha(path) != SOURCE_SHA:
        raise ValueError("Workbook hash mismatch")
    fatigue, curves, roughness, source_summary, audit, interfaces = [], [], [], [], [], []
    with zipfile.ZipFile(path) as archive:
        strings = ["".join(si.itertext()) for si in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        sheet_info = ET.fromstring(archive.read("xl/workbook.xml")).findall("s:sheets/s:sheet", NS)
        relationship_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        relationships = {r.get("Id"): r.get("Target") for r in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels")).findall(f"{{{relationship_ns}}}Relationship")}
        expected_names = {6: "Fig.4c", 10: "Fig.5e", 12: "Fig.6b", 18: "Supplementary Fig. 8", 46: "Supplementary Fig. 41",
                          49: "Supplementary Fig. 43c", 51: "Supplementary Fig. 43f", 53: "Supplementary Fig. 48"}
        source = {}
        for index, name in expected_names.items():
            sheet = sheet_info[index - 1]
            rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            if sheet.get("name") != name or relationships[rid] != f"worksheets/sheet{index}.xml":
                raise ValueError("Worksheet name/relationship mapping changed")
            cells, detail = worksheet(archive, index, strings)
            source[index] = cells
            audit.append({"sheet": name, **detail})
        c = source[6]
        if c["D1"] != "absolute displacement (mm)" or c["B3"] != "cycle number":
            raise ValueError("Fatigue source units changed")
        for material, col in (("enamel", "D"), ("HEA", "E"), ("EA", "F")):
            if c[f"{col}2"] != material:
                raise ValueError("Fatigue material header changed")
            fatigue.append({"material": material, "source_sheet": "Fig.4c", "x_cells": "B4:B162", "y_cells": f"{col}4:{col}162",
                            "trace_identity": f"Fig.4c:{col}", "points": [[c[f"B{r}"], c[f"{col}{r}"]] for r in range(4, 163)],
                            "physical_specimen_id": None, "donor_id": None})
        for index, group, spec in ((12, "main_perpendicular", [("HEA", "C", "D"), ("HEA", "E", "F"), ("enamel", "G", "H"), ("enamel", "I", "J"), ("EA", "K", "L"), ("EA", "M", "N")]),
                                   (49, "source_LD", [("HEA", "E", "F"), ("HEA", "H", "I"), ("enamel", "K", "L"), ("enamel", "N", "O")]),
                                   (51, "source_TD", [("HEA", "E", "F"), ("HEA", "H", "I"), ("enamel", "K", "L"), ("enamel", "N", "O")])):
            c = source[index]
            name = expected_names[index]
            for material, xcol, ycol in spec:
                if "crack" not in c[f"{xcol}2"] or not ("toughness" in c[f"{ycol}2"] or "KJC" in c[f"{ycol}2"]):
                    raise ValueError("R-curve source unit/endpoint changed")
                curves.append({"material": material, "architecture_context": group, "source_sheet": name,
                               "trace_identity": f"{name}:{xcol}:{ycol}",
                               "source_trace_label": c.get(f"{xcol}1") if index != 12 else None,
                               "x_cells": f"{xcol}3:{xcol}13", "y_cells": f"{ycol}3:{ycol}13",
                               "points": [[c[f"{xcol}{r}"], c[f"{ycol}{r}"]] for r in range(3, 14)],
                               "physical_specimen_id": None, "donor_id": None,
                               "individual_thickness_mm": None})
        c = source[10]
        if c["C1"] != "roughness (nm)" or (c["B4"], c["B5"]) != (0, 15000):
            raise ValueError("Roughness endpoint or cycle labels changed")
        for material, col, sdcol in (("HEA", "C", "D"), ("enamel", "E", "F"), ("EA", "G", "H")):
            if c[f"{col}2"] != material:
                raise ValueError("Roughness material mapping changed")
            roughness.append({"material": material, "source_sheet": "Fig.5e",
                              "before": {"cycles": c["B4"], "mean_nm": c[f"{col}4"], "source_sd_nm": c[f"{sdcol}4"], "cells": [f"{col}4", f"{sdcol}4"]},
                              "after": {"cycles": c["B5"], "mean_nm": c[f"{col}5"], "source_sd_nm": c[f"{sdcol}5"], "cells": [f"{col}5", f"{sdcol}5"]},
                              "individual_specimen_pairing": None, "n_independent_specimens_from_table": None})
        c = source[46]
        for material, cols in (("HEA", "EFGH"), ("enamel", "IJKL"), ("EA", "MNOP")):
            source_summary.append({"material": material, "source_sheet": "Supplementary Fig. 41",
                                   "KIC_mean": c[f"{cols[0]}4"], "KIC_source_sd": c[f"{cols[1]}4"],
                                   "KJC_mean": c[f"{cols[2]}4"], "KJC_source_sd": c[f"{cols[3]}4"],
                                   "cells": [f"{col}4" for col in cols], "raw_specimen_crosswalk": None})
        c = source[18]
        for material, xcol, ycol, last in (("HEA", "C", "D", 300), ("ZrO2", "E", "F", 195)):
            if c[f"{xcol}1"] != material or c[f"{xcol}2"] != "displacement" or c[f"{ycol}2"] != "stress":
                raise ValueError("Delamination material or shared ordinate definition changed")
            interfaces.append({"material": material, "source_sheet": "Supplementary Fig. 8",
                               "trace_identity": f"Supplementary Fig. 8:{xcol}:{ycol}",
                               "x_cells": f"{xcol}3:{xcol}{last}", "y_cells": f"{ycol}3:{ycol}{last}",
                               "source_x_header": c[f"{xcol}2"], "source_y_header": c[f"{ycol}2"],
                               "source_header_absolute_units": None,
                               "points": [[c[f"{xcol}{r}"], c[f"{ycol}{r}"]] for r in range(3, last + 1)],
                               "physical_specimen_id": None, "donor_id": None, "contact_area_mm2": None,
                               "measured_repair_thickness_um": None, "fatigue_crosswalk": None})
        interface_audit = {"sheet": expected_names[53], "header_F1": source[53]["F1"], "header_G1": source[53]["G1"],
                           "source_context": "Primary methods explicitly link Supplementary Fig.48 to corroboration of compliance and crack length in SENB calculations",
                           "is_host_enamel_shear_bond_dataset": False, "numeric_force_curve_not_used_as_interface_data": True,
                           "identified_host_bond_numeric_table": "Supplementary Fig. 8",
                           "actual_interface_context": "Primary results explicitly associate Supplementary Fig.8 with delamination of HEA or ZrO2 from enamel",
                           "absolute_ordinate_unit_and_area_validated": False}
    return {"data_kind": "observed_source_numeric_extract_not_synthetic", "article_doi": "10.1038/s41467-024-54576-5",
            "raw_workbook_sha256": SOURCE_SHA, "source_sheet_count": len(sheet_info), "selected_xml_audit": audit,
            "fatigue_displacement_traces": fatigue, "bulk_R_curves": curves, "toothbrushing_roughness_summaries": roughness,
            "interface_delamination_traces": interfaces,
            "published_bulk_toughness_summaries": source_summary, "interface_assay_audit": interface_audit,
            "rights_scope": "Factual numerical observations and source-cell locations only; no article text, images, molecular depictions or adapted figures. Article metadata identifies CC-BY-NC-ND-4.0; raw workbook remains ignored."}


def validate_trace(points, nonnegative_y=True):
    if not isinstance(points, list) or len(points) < 2:
        raise ValueError("At least two observed points required")
    out = []
    for pair in points:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("Each observed point needs x and y")
        out.append([numeric(pair[0]), numeric(pair[1], nonnegative=nonnegative_y)])
    if any(out[i][0] <= out[i - 1][0] for i in range(1, len(out))):
        raise ValueError("Source x values must increase strictly; do not silently sort, deduplicate or extrapolate")
    return out


def interpolate(points, x):
    points = validate_trace(points)
    x = numeric(x)
    if x < points[0][0] or x > points[-1][0]:
        raise ValueError("No extrapolation beyond observed support")
    for (left, a), (right, b) in zip(points, points[1:]):
        if left <= x <= right:
            return a + (b - a) * (x - left) / (right - left)
    raise ValueError("Point outside interpolation support")


def clipped_integral(points, low, high):
    points = validate_trace(points)
    if high <= low:
        raise ValueError("Positive integration width required")
    clipped = [[low, interpolate(points, low)]]
    clipped += [p for p in points if low < p[0] < high]
    clipped.append([high, interpolate(points, high)])
    return sum((right - left) * (a + b) / 2 for (left, a), (right, b) in zip(clipped, clipped[1:]))


def R_comparison(curves):
    points = [validate_trace(c["points"]) for c in curves]
    low, high = max(p[0][0] for p in points), min(p[-1][0] for p in points)
    if high <= low:
        raise ValueError("No common observed crack-extension interval")
    rows = []
    for c, p in zip(curves, points):
        rows.append({"trace_identity": c["trace_identity"], "material": c["material"],
                     "architecture_context": c["architecture_context"], "n_serial_points": len(p),
                     "initial_source_K": p[0][1], "last_source_crack_extension_mm": p[-1][0], "last_source_K": p[-1][1],
                     "K_at_common_upper_MPa_sqrt_m": interpolate(p, high),
                     "mean_K_over_common_interval_MPa_sqrt_m": clipped_integral(p, low, high) / (high - low),
                     "decreasing_K_steps_retained": sum(b[1] < a[1] for a, b in zip(p, p[1:]))})
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["material"], row["architecture_context"])].append(row)
    summaries = []
    for (material, context), values in grouped.items():
        at_end = [v["K_at_common_upper_MPa_sqrt_m"] for v in values]
        integrated = [v["mean_K_over_common_interval_MPa_sqrt_m"] for v in values]
        summaries.append({"material": material, "architecture_context": context, "n_listed_traces": len(values),
                          "trace_mean_K_at_common_upper": statistics.mean(at_end), "trace_range_K_at_common_upper": [min(at_end), max(at_end)],
                          "trace_mean_of_interval_mean_K": statistics.mean(integrated),
                          "independent_specimen_or_donor_n": None, "new_sem_or_confidence_interval": None})
    return {"common_observed_crack_extension_mm": [low, high], "interpolation": "piecewise linear within observed coordinates only",
            "traces": rows, "trace_summaries": summaries}


def calculate(data):
    if data["data_kind"] != "observed_source_numeric_extract_not_synthetic" or data["raw_workbook_sha256"] != SOURCE_SHA:
        raise ValueError("Unqualified numerical source")
    fatigue = data["fatigue_displacement_traces"]
    curves = data["bulk_R_curves"]
    if Counter(c["material"] for c in fatigue) != Counter({"enamel": 1, "HEA": 1, "EA": 1}) or len(curves) != 14:
        raise ValueError("Expected complete source trace set")
    if len({c["trace_identity"] for c in fatigue + curves}) != 17:
        raise ValueError("Duplicate source trace identity")
    fatigue_results = []
    for row in fatigue:
        p = validate_trace(row["points"])
        if len(p) != 159 or p[0][0] != 100 or p[-1][0] != 150000:
            raise ValueError("Incomplete source fatigue trace")
        fatigue_results.append({"material": row["material"], "trace_identity": row["trace_identity"],
                                "n_serial_points": len(p), "n_listed_traces": 1, "independent_specimen_or_donor_n": None,
                                "observed_cycle_window": [p[0][0], p[-1][0]],
                                "first_source_displacement_mm": p[0][1], "last_source_displacement_mm": p[-1][1],
                                "change_over_observed_window_mm": p[-1][1] - p[0][1],
                                "cycle_weighted_mean_displacement_mm": clipped_integral(p, p[0][0], p[-1][0]) / (p[-1][0] - p[0][0]),
                                "decreasing_displacement_steps_retained": sum(b[1] < a[1] for a, b in zip(p, p[1:])),
                                "failure_time_or_survival_probability": None})
    main = [c for c in curves if c["architecture_context"] == "main_perpendicular"]
    direction = [c for c in curves if c["architecture_context"] in ("source_LD", "source_TD")]
    if len(main) != 6 or len(direction) != 8 or any(len(c["points"]) != 11 for c in curves):
        raise ValueError("Incomplete source R-curve set")
    main_result, direction_result = R_comparison(main), R_comparison(direction)
    roughness = []
    for row in data["toothbrushing_roughness_summaries"]:
        before, after = row["before"], row["after"]
        b, a = numeric(before["mean_nm"]), numeric(after["mean_nm"])
        if b == 0 or (before["cycles"], after["cycles"]) != (0, 15000):
            raise ValueError("Invalid roughness baseline or source cycles")
        roughness.append({"material": row["material"], "before_mean_nm": b, "after_mean_nm": a,
                          "source_before_sd_nm": numeric(before["source_sd_nm"]), "source_after_sd_nm": numeric(after["source_sd_nm"]),
                          "difference_of_reported_means_nm": a - b, "relative_change_of_reported_means_percent": 100 * (a / b - 1),
                          "paired_individual_change_variance_or_CI": None,
                          "interpretation": "Unfavorable roughness direction retained; a difference of published means is not a paired specimen-level estimate or equivalence test"})
    if Counter(r["material"] for r in roughness) != Counter({"enamel": 1, "HEA": 1, "EA": 1}):
        raise ValueError("Incomplete roughness material set")
    interfaces = data["interface_delamination_traces"]
    if Counter(r["material"] for r in interfaces) != Counter({"HEA": 1, "ZrO2": 1}) or any(r["source_sheet"] != "Supplementary Fig. 8" or r["source_y_header"] != "stress" for r in interfaces):
        raise ValueError("Both delamination traces must share the source stress definition in Supplementary Fig.8")
    interface_results = []
    for row in interfaces:
        p = validate_trace(row["points"])
        peak = max(p, key=lambda xy: xy[1])
        interface_results.append({"material": row["material"], "trace_identity": row["trace_identity"],
                                  "n_serial_points": len(p), "peak_source_stress_ordinate": peak[1],
                                  "source_displacement_at_peak": peak[0], "absolute_stress_unit_validated": None,
                                  "independent_specimen_or_donor_n": None})
    peak_by_material = {r["material"]: r["peak_source_stress_ordinate"] for r in interface_results}
    if peak_by_material["ZrO2"] <= 0:
        raise ValueError("Positive source comparator peak needed")
    return {"data_kind": "descriptive_observed_bulk_material_comparator",
            "full_repair_depth_interface_durability_eligible": False,
            "fatigue_trace_summaries": fatigue_results,
            "main_bulk_R_curve_comparison": main_result,
            "source_label_directional_R_curve_comparison": direction_result,
            "roughness_summary_changes": roughness,
            "published_toughness_summaries_kept_separate": data["published_bulk_toughness_summaries"],
            "host_enamel_delamination_source_ordinate_comparison": {"traces": interface_results,
                "peak_ordinate_ratio_HEA_to_ZrO2": peak_by_material["HEA"] / peak_by_material["ZrO2"],
                "ratio_qualification": "Conditional on the common stress ordinate scale used for the two traces in the same source figure. Identical stress headers and primary delamination-comparison text support that reading; absolute units, actual bond areas and per-specimen geometry are not validated. This is a ratio of two listed trace peaks, not a cohort mean or validated absolute bond strength.",
                "host_interface_fatigue_or_repair_depth_linkage": None},
            "source_summary_reconstruction_from_two_curves_attempted": False,
            "interface_assay_audit": data["interface_assay_audit"],
            "hierarchy_and_missingness": {"serial_R_curve_points": 154, "serial_fatigue_points": 477,
                                          "listed_R_curves": 14, "listed_fatigue_traces": 3,
                                          "listed_interface_traces": 2, "serial_interface_points": 491,
                                          "donor_count": None, "independent_specimen_count_from_deposited_vectors": None,
                                          "per_specimen_measured_repair_thickness": None,
                                          "per_specimen_geometry_to_curve_crosswalk": None,
                                          "joint_host_interface_fatigue_or_leakage": None,
                                          "native_PDL_gum_pulp_and_pose_after_finite_support": None},
            "calendar_life_or_growth_forecast": None,
            "uncertainty_qualification": "Trace ranges and missing source linkage are not confidence intervals. Processed source R-curves are not revalidated toughness measurements. Geometry/orientation, source summary SD hierarchy and absent donor/specimen identifiers limit transfer to repaired teeth."}


def check_cache(data):
    actual = extract_source()
    if actual != data:
        raise ValueError("Selected source XML extraction differs from tracked numeric inputs")
    return {"raw_workbook_bytes": WORKBOOK.stat().st_size, "raw_workbook_sha256": SOURCE_SHA,
            "selected_xml_members_checked": len(actual["selected_xml_audit"]), "source_numeric_extract_exact_match": True,
            "embedded_images_read": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract-source", action="store_true")
    parser.add_argument("--check-cache", action="store_true")
    args = parser.parse_args()
    if args.extract_source:
        dump(HERE / "inputs.json", extract_source())
    data = load(HERE / "inputs.json")
    results = calculate(data)
    results["inputs_text_sha256"] = text_sha(HERE / "inputs.json")
    dump(HERE / "results.json", results)
    if args.check_cache:
        print(json.dumps(check_cache(data)))
    print(json.dumps({"R_curves": 14, "fatigue_traces": 3, "roughness_material_summaries": 3,
                      "full_depth_interface_eligibility": False, "output": str(HERE / "results.json")}))


if __name__ == "__main__":
    main()
