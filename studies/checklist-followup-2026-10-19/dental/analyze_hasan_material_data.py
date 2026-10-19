"""Read pinned publisher XLSX cells without modifying the source workbook.

Study-level descriptive reanalysis only. Source positions are not specimen IDs;
unlabeled extra values never become independent specimens or inference inputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import statistics
import sys
from urllib.request import Request, urlopen
from zipfile import ZipFile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_CACHE = ROOT / "data/literature/checklist-followup-2026-10-19"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def text_sha(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def verify_file(path: Path, specification: dict) -> None:
    if path.stat().st_size != specification["bytes"] or sha256(path) != specification["sha256"]:
        raise ValueError(f"Pinned source size/SHA-256 mismatch: {path.name}")


def fetch_missing(path: Path, specification: dict) -> None:
    if path.exists():
        verify_file(path, specification)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    request = Request(specification["url"], headers={"User-Agent": "RegenWorkbench public-source audit"})
    with urlopen(request, timeout=45) as response, path.open("wb") as output:
        resolved, status = response.url, response.status
        while True:
            block = response.read(4_000_000)
            if not block:
                break
            count += len(block)
            if count > specification["maximum_fetch_bytes"]:
                raise ValueError("Source exceeded declared fetch bound")
            output.write(block)
    sys.path.insert(0, str(ROOT))
    from tools import regen
    regen.record("hasan-material-source-fetch", {"source_url": specification["url"],
                 "resolved_url": resolved, "status": status, "bytes_read": count,
                 "purpose": "Reproduce pinned published material-source analysis"}, [path])
    verify_file(path, specification)


def parse_sheet(raw: bytes, strings: list[str]) -> dict[str, dict]:
    tree = ET.fromstring(raw)
    result = {}
    for element in tree.findall(".//s:sheetData/s:row/s:c", NS):
        address = element.attrib["r"]
        if address in result:
            raise ValueError("Duplicate worksheet cell")
        stored = element.find("s:v", NS)
        inline = element.find("s:is", NS)
        formula = element.find("s:f", NS)
        kind = element.attrib.get("t", "n")
        text = None if stored is None else stored.text
        value = text
        if kind == "s" and text is not None:
            value = strings[int(text)]
        elif kind == "inlineStr" and inline is not None:
            value = "".join(t.text or "" for t in inline.findall(".//s:t", NS))
        result[address] = {"value": value, "stored_text": text, "type": kind,
                           "style": element.attrib.get("s"),
                           "formula": None if formula is None else formula.text}
    return result


def read_workbook(path: Path, names: list[str]) -> tuple[dict, dict]:
    with ZipFile(path) as archive:
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in relationships}
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = {s.attrib["name"]: targets[s.attrib[REL]] for s in book.findall("s:sheets/s:sheet", NS)}
        shared = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        strings = ["".join(t.text or "" for t in item.findall(".//s:t", NS)) for item in shared.findall("s:si", NS)]
        selected, inventory = {}, {}
        for name in names:
            target = sheets[name]
            member = target.lstrip("/") if target.startswith("/") else str(PurePosixPath("xl") / target)
            if archive.getinfo(member).file_size > 10_000_000:
                raise ValueError("Selected worksheet exceeds fixed 10 MB XML bound")
            raw = archive.read(member)
            selected[name] = parse_sheet(raw, strings)
            inventory[name] = {"worksheet_member": member, "uncompressed_xml_bytes": len(raw),
                               "nonempty_value_cells": sum(c["value"] is not None for c in selected[name].values())}
        return selected, {"worksheet_count": len(sheets), "selected_sheets": inventory,
                          "reader": "Python standard-library OOXML reader; source workbook unchanged"}


def addresses(reference: str) -> list[str]:
    match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*):([A-Z]+)([1-9][0-9]*)", reference)
    if match is None or match[1] != match[3] or int(match[2]) > int(match[4]):
        raise ValueError("Require an ordered, single-column A1 range")
    return [f"{match[1]}{i}" for i in range(int(match[2]), int(match[4]) + 1)]


def numeric_cell(cells: dict, address: str) -> float:
    cell = cells[address]
    if cell["formula"] is not None or cell["type"] != "n" or cell["value"] is None:
        raise ValueError(f"Selected measurement must be a stored numeric value: {address}")
    value = float(cell["value"])
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"Invalid material observation at {address}")
    return value


def describe(values: list[float]) -> dict:
    if len(values) < 2 or not all(math.isfinite(x) for x in values):
        raise ValueError("Need at least two finite descriptive values")
    return {"n_numeric_values": len(values), "mean": statistics.mean(values),
            "sample_sd_n_minus_1": statistics.stdev(values),
            "population_divisor_sd_n": statistics.pstdev(values),
            "median": statistics.median(values), "minimum": min(values), "maximum": max(values)}


def trailing_audit(cells: dict, primary: list[float], address: str) -> dict:
    value = numeric_cell(cells, address)
    row = int(re.search(r"[0-9]+", address)[0])
    nearby = {a: c for a, c in cells.items()
              if int(re.search(r"[0-9]+", a)[0]) in (row - 1, row, row + 1)
              and re.match(r"[A-Z]+", a)[0] in {"AB", "AC", "AD", "AE", "AF", "AG"}}
    labels = {a: c["value"] for a, c in nearby.items() if c["type"] in {"s", "inlineStr"} and c["value"]}
    return {"trailing_cell": address, "stored_value": cells[address]["stored_text"],
            "value": value, "formula": cells[address]["formula"], "style": cells[address]["style"],
            "nearby_labels": labels, "nearby_cells": nearby,
            "first8_mean": statistics.mean(primary), "first8_median": statistics.median(primary),
            "trailing_minus_first8_mean": value - statistics.mean(primary),
            "trailing_minus_first8_median": value - statistics.median(primary),
            "identity": "unresolved: neither specimen nor summary label supplied",
            "same_row_height_values": {a: cells.get(a, {}).get("value") for a in [f"AE{row}", f"AF{row}"]}}


def analyze_series(cells: dict, plan: dict) -> tuple[list, list, dict, list]:
    for address, expected in plan["header_checks"].items():
        if cells[address]["value"] != expected:
            raise ValueError(f"Source header changed: {address}")
    points, summaries, values_by_id, extras = [], [], {}, []
    for series in plan["series"]:
        source_addresses = addresses(series["range"])
        if len(source_addresses) != series["caption_n_samples"]:
            raise ValueError("Selected primary block does not match the source caption count")
        values = [numeric_cell(cells, a) for a in source_addresses]
        values_by_id[series["id"]] = values
        qualified = "conditional_caption_aligned_first8" if "trailing_ambiguous_cell" in series else "caption_aligned_values"
        for index, (address, value) in enumerate(zip(source_addresses, values), start=1):
            points.append({"series": series["id"], "endpoint": series["endpoint"], "substrate": series["substrate"],
                           "condition": series["condition"], "sheet": plan["workbook_sheet"], "cell": address,
                           "source_numeric_text": cells[address]["stored_text"], "value": value, "unit": series["unit"],
                           "source_position_not_specimen_id": index, "observation_status": qualified,
                           "specimen_id": "", "donor_id": "", "formula": cells[address]["formula"] or "none"})
        summaries.append({"series": series["id"], "endpoint": series["endpoint"], "unit": series["unit"],
                          "range": series["range"], "qualification": qualified, "caption_n_samples": series["caption_n_samples"],
                          **describe(values), "inference": "descriptive_values_only; no confidence interval or equivalence inference"})
        if "trailing_ambiguous_cell" in series:
            address = series["trailing_ambiguous_cell"]
            audit = {"series": series["id"], **trailing_audit(cells, values, address)}
            extras.append(audit)
            value = numeric_cell(cells, address)
            points.append({**points[-1], "cell": address, "source_numeric_text": cells[address]["stored_text"],
                           "value": value, "source_position_not_specimen_id": "", "observation_status": "ambiguous_trailing_cell_not_a_specimen"})
            summaries.append({**summaries[-1], "series": series["id"] + "_all_numeric_values_sensitivity",
                              "range": series["range"] + ";" + address, "qualification": "intake_sensitivity_not_9_specimens",
                              **describe(values + [value])})
    return points, summaries, values_by_id, extras


def contrasts(values: dict, plan: dict) -> list[dict]:
    rows = []
    for specification in plan["contrasts"]:
        reference = statistics.mean(values[specification["reference"]])
        candidate = statistics.mean(values[specification["candidate"]])
        if reference <= 0:
            raise ValueError("A mean ratio requires a positive reference mean")
        difference = candidate - reference
        favorable = difference > 0 if specification["favorable_direction"] == "higher" else difference < 0
        rows.append({**specification, "reference_mean": reference, "candidate_mean": candidate,
                     "mean_difference": difference, "candidate_over_reference_mean": candidate / reference,
                     "mean_change_percent": 100 * difference / reference,
                     "observed_direction": "equal_means" if difference == 0 else ("favorable_mean_direction" if favorable else "unfavorable_mean_direction"),
                     "inference": "descriptive_unpaired_group_means; not significance, equivalence or a clinical effect"})
    return rows


def write_tsv(path: Path, rows: list[dict]) -> None:
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def source_context(xml_path: Path) -> dict:
    article = ET.fromstring(xml_path.read_bytes())
    doi = article.find(".//article-id[@pub-id-type='doi']")
    if doi is None or doi.text != "10.1038/s41467-025-64982-y":
        raise ValueError("Wrong primary article")
    wanted = {"Apparent fracture toughness analysis", "Chewing & grinding abrasion test", "Statistical analysis"}
    sections = {s.findtext("title"): " ".join("".join(s.itertext()).split())
                for s in article.findall(".//sec") if s.findtext("title") in wanted}
    if set(sections) != wanted:
        raise ValueError("Assay-linkage sections missing")
    return {"doi": doi.text, "assay_sections_verified": sorted(sections),
            "wear_source_hierarchy": "32 extracted human molars; 8 per substrate/condition, donor identities unknown",
            "fracture_source_hierarchy": "Caption3 samples/group; methods at least5 indents/sample; selected cells have no specimen or indentation crosswalk",
            "source_error_bar_definition": "Methods say mean +/- SD; denominator not specified",
            "units_verified_in_methods": {"wear_volume_loss": "mm^3", "wear_height_loss": "micrometre"},
            "interface_scope": "No quantitative host-repair interface toughness, depth/property pairing or living attachment endpoint in selected numerical blocks"}


def indentation_inventory(sheets: dict) -> list[dict]:
    inventory = []
    for sheet, group_ranges in {"Fig. 3": {"native": "AG5:AG102", "acid_etched": "AI5:AI102", "remineralized": "AK5:AK73"},
                                "Fig. 5": {"native": "AB5:AB97", "acid_etched": "AC5:AC102", "mineralized": "AD5:AD101"}}.items():
        for condition, reference in group_ranges.items():
            values = [numeric_cell(sheets[sheet], a) for a in addresses(reference)]
            inventory.append({"sheet": sheet, "figure": "3f" if sheet == "Fig. 3" else "5f", "condition": condition,
                              "modulus_range": reference, "listed_indentation_values": len(values),
                              "caption_independent_experiments": 3, "indent_to_experiment_crosswalk": None,
                              "independent_donor_count": None, "reanalysis_state": "inventory_only_not_independent_replicates"})
    return inventory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=HERE / "analysis_plan.json")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--out", type=Path, default=HERE / "derived")
    parser.add_argument("--fetch", action="store_true", help="Fetch only missing, pinned public source files; record actual downloads with regen.record")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    paths = {name: args.cache / spec["filename"] for name, spec in plan["source_files"].items()}
    for name, path in paths.items():
        if args.fetch:
            fetch_missing(path, plan["source_files"][name])
        verify_file(path, plan["source_files"][name])
    sheets, inventory = read_workbook(paths["workbook"], ["Fig. 3", "Fig. 5", "Fig. 6"])
    points, summaries, values, extras = analyze_series(sheets[plan["workbook_sheet"]], plan)
    contrasts_rows = contrasts(values, plan)
    fracture_native, fracture_acid, fracture_repaired = [statistics.mean(values[name]) for name in ["K_native", "K_acid", "K_remineralized"]]
    args.out.mkdir(parents=True, exist_ok=True)
    tables = {"material_observations.tsv": points, "material_summary.tsv": summaries, "material_contrasts.tsv": contrasts_rows}
    for filename, rows in tables.items():
        write_tsv(args.out / filename, rows)
    audit = {"status": "actual_published_material_values_reanalyzed; no new biological experiment",
             "source_citation": plan["source_citation"], "source_license": plan["source_license"],
             "source_workbook_or_article_files_redistributed": False, "attributed_numeric_extracts_redistributed": True,
             "source_files": {name: {"sha256": sha256(path), "bytes": path.stat().st_size}
                                                                   for name, path in paths.items()},
             "plan_sha256_lf_text": text_sha(args.plan), "script_sha256_lf_text": text_sha(Path(__file__)),
             "workbook_inventory": inventory, "assay_linkage": source_context(paths["article_xml"]),
             "selected_numeric_observations": len(points), "series_summaries": len(summaries),
             "contrasts": len(contrasts_rows), "ambiguous_trailing_values": extras,
             "indentation_inventory_not_replication": indentation_inventory(sheets),
             "fracture_deficit_recovery_between_group_means_fraction": (fracture_repaired - fracture_acid) / (fracture_native - fracture_acid),
             "fracture_recovery_qualification": "Descriptive interpolation between reference group means; not percent tooth restored or donor-level recovery",
             "output_sha256_lf_text": {name: text_sha(args.out / name) for name in tables},
             "limits": plan["limits"]}
    (args.out / "intake_and_hierarchy_audit.json").write_text(json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"selected_numeric_values": len(points), "summaries": len(summaries),
                      "contrasts": len(contrasts_rows), "unresolved_trailing_cells": [e["trailing_cell"] for e in extras]}))


if __name__ == "__main__":
    main()
