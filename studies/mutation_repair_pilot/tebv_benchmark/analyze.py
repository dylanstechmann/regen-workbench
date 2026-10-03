#!/usr/bin/env python3
"""Reproduce descriptive vasodilation summaries from the public Figure 8 workbook."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "inputs" / "Figure_8.zip"
DEFAULT_OUTPUT = HERE / "derived"
MODEL_SPEC_PATH = HERE / "model_spec.json"
EXPERIMENT_MANIFEST_PATH = HERE / "experiment.json"
EXPECTED_ARCHIVE_SHA256 = "27c87f55dec8f2f82fcbe89ec8af6ac5dcc9ce582d47b14fa85a2d221058a41c"
EXPECTED_ARCHIVE_BYTES = 324302
WORKBOOK_MEMBER = "Figure 8/Fig 8.xlsx"
ANOVA_MEMBER = "Figure 8/ANOVA_Fig8.pdf"
SHEET_NAME = "Fig 8A. Vasodilation"
NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}

GROUPS = {
    "Healthy": {"role": "healthy_control", "edited_fraction": None, "donor_group": "healthy donor 168"},
    "HGPS": {"role": "disease_control", "edited_fraction": 0.0, "donor_group": "HGPS donor 003"},
    "25:75": {"role": "intervention", "edited_fraction": 0.25, "donor_group": "HGPS donor 003"},
    "50:50": {"role": "intervention", "edited_fraction": 0.5, "donor_group": "HGPS donor 003"},
    "75:25": {"role": "intervention", "edited_fraction": 0.75, "donor_group": "HGPS donor 003"},
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_record(path: Path, repo_root: Path) -> dict:
    data = path.read_bytes()
    try:
        stored_path = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        stored_path = str(path.resolve())
    return {
        "path": stored_path,
        "sha256": sha256_bytes(data),
        "size_bytes": len(data),
    }


def _shared_strings(book: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in book.namelist():
        return []
    root = ET.fromstring(book.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.findall(".//main:t", NS))
            for si in root.findall("main:si", NS)]


def _cell_value(cell: ET.Element, shared: list[str]) -> str | None:
    if cell.attrib.get("t") == "inlineStr":
        return "".join(t.text or "" for t in cell.findall(".//main:t", NS))
    value = cell.find("main:v", NS)
    if value is None or value.text is None:
        return None
    if cell.attrib.get("t") == "s":
        return shared[int(value.text)]
    return value.text


def _column_number(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    result = 0
    for char in letters.upper():
        result = result * 26 + ord(char) - ord("A") + 1
    return result


def _workbook_sheet(book_bytes: bytes, expected_name: str) -> tuple[dict[int, dict[int, tuple[str, str]]], str]:
    with zipfile.ZipFile(__import__("io").BytesIO(book_bytes)) as book:
        shared = _shared_strings(book)
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("pkg:Relationship", NS)}
        for sheet in workbook.findall("main:sheets/main:sheet", NS):
            if sheet.attrib.get("name") != expected_name:
                continue
            target = targets[sheet.attrib[f"{{{NS['rel']}}}id"]]
            sheet_path = target.lstrip("/")
            if not sheet_path.startswith("xl/"):
                sheet_path = "xl/" + sheet_path
            root = ET.fromstring(book.read(sheet_path))
            rows: dict[int, dict[int, tuple[str, str]]] = {}
            for row in root.findall(".//main:sheetData/main:row", NS):
                row_num = int(row.attrib["r"])
                rows[row_num] = {}
                for cell in row.findall("main:c", NS):
                    text = _cell_value(cell, shared)
                    if text is not None:
                        col_num = _column_number(cell.attrib["r"])
                        rows[row_num][col_num] = (cell.attrib["r"], text)
            return rows, sheet_path
    raise ValueError(f"required source worksheet not found: {expected_name}")


def extract_observations(archive_path: Path) -> tuple[list[dict], dict]:
    archive_bytes = archive_path.read_bytes()
    if len(archive_bytes) != EXPECTED_ARCHIVE_BYTES or sha256_bytes(archive_bytes) != EXPECTED_ARCHIVE_SHA256:
        raise ValueError("public Figure 8 source archive failed its pinned byte-count/SHA-256 check")
    with zipfile.ZipFile(archive_path) as source:
        members = {name: source.read(name) for name in (WORKBOOK_MEMBER, ANOVA_MEMBER)}
    rows, sheet_path = _workbook_sheet(members[WORKBOOK_MEMBER], SHEET_NAME)

    header_row = rows.get(1, {})
    if header_row.get(2, (None, None))[1].replace("\xa0", " ").strip() != "3 weeks":
        raise ValueError("unexpected 3-week header in the pinned vasodilation worksheet")
    if header_row.get(6, (None, None))[1].replace("\xa0", " ").strip() != "5 weeks":
        raise ValueError("unexpected 5-week header in the pinned vasodilation worksheet")

    observations: list[dict] = []
    for row_num in sorted(rows):
        if row_num == 1:
            continue
        row = rows[row_num]
        group = row.get(1, (None, None))[1].strip()
        if not group:
            continue
        if group not in GROUPS:
            raise ValueError(f"unknown source group label at row {row_num}: {group!r}")
        for col_num, (cell_ref, raw_value) in sorted(row.items()):
            if col_num == 1:
                continue
            if col_num not in range(2, 10):
                raise ValueError(f"unexpected data column in source workbook: {cell_ref}")
            try:
                value = float(raw_value)
            except ValueError as exc:
                raise ValueError(f"non-numeric source measurement in {cell_ref}: {raw_value!r}") from exc
            week = 3 if col_num <= 5 else 5
            group_info = GROUPS[group]
            observations.append({
                "group": group,
                "group_role": group_info["role"],
                "edited_fraction": group_info["edited_fraction"],
                "week": week,
                "vasodilation_percent_diameter_change": value,
                "source_cell": cell_ref,
                "source_position": cell_ref[0],
                "donor_group": group_info["donor_group"],
                "donor_id_at_observation_level": "",
                "tebv_id_at_observation_level": "",
            })

    if len(observations) != 35:
        raise ValueError(f"expected 35 source observations, found {len(observations)}")
    provenance = {
        "archive": {
            "member": archive_path.name,
            "sha256": sha256_bytes(archive_bytes),
            "size_bytes": len(archive_bytes),
        },
        "members": {
            name: {"sha256": sha256_bytes(data), "size_bytes": len(data)}
            for name, data in members.items()
        },
        "worksheet": {"name": SHEET_NAME, "member": WORKBOOK_MEMBER, "xml_path": sheet_path},
    }
    return observations, provenance


def _summaries(observations: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, int], list[float]] = defaultdict(list)
    for observation in observations:
        grouped[(observation["group"], observation["week"])].append(
            observation["vasodilation_percent_diameter_change"]
        )
    summary = []
    for (group, week), values in sorted(grouped.items(), key=lambda key: (key[0][1], key[0][0])):
        summary.append({
            "group": group,
            "week": week,
            "n_source_values": len(values),
            "mean": round(statistics.mean(values), 8),
            "sd": round(statistics.stdev(values), 8) if len(values) > 1 else None,
            "median": round(statistics.median(values), 8),
            "minimum": round(min(values), 8),
            "maximum": round(max(values), 8),
        })
    return summary


def _monotonicity(summary: list[dict]) -> list[dict]:
    by_key = {(row["group"], row["week"]): row for row in summary}
    result = []
    for week in (3, 5):
        dose_rows = [(fraction, by_key[(label, week)]["mean"])
                     for label, fraction in (("25:75", 0.25), ("50:50", 0.5), ("75:25", 0.75))]
        violations = []
        for left, right in zip(dose_rows, dose_rows[1:]):
            if right[1] < left[1]:
                violations.append({
                    "from_fraction": left[0],
                    "from_mean": round(left[1], 8),
                    "to_fraction": right[0],
                    "to_mean": round(right[1], 8),
                })
        result.append({"week": week, "dose_means": dose_rows, "nondecreasing": not violations,
                       "violations": violations})
    return result


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "group", "group_role", "edited_fraction", "week",
        "vasodilation_percent_diameter_change", "source_cell", "source_position",
        "donor_group", "donor_id_at_observation_level", "tebv_id_at_observation_level",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _refresh_manifest_artifacts(repo_root: Path) -> None:
    if not EXPERIMENT_MANIFEST_PATH.is_file():
        return
    document = json.loads(EXPERIMENT_MANIFEST_PATH.read_text(encoding="utf-8"))
    refresh_kinds = {"analysis_code", "analysis_specification", "analysis_output"}
    for artifact in document.get("artifacts", []):
        if artifact.get("repository") != document.get("repository_id") or artifact.get("kind") not in refresh_kinds:
            continue
        rel = PurePosixPath(artifact["path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"manifest artifact path escapes repository: {artifact['path']}")
        path = (repo_root / Path(*rel.parts)).resolve()
        path.relative_to(repo_root.resolve())
        payload = path.read_bytes()
        if artifact.get("member_path"):
            with zipfile.ZipFile(path) as archive:
                payload = archive.read(artifact["member_path"])
        artifact["sha256"] = sha256_bytes(payload)
        artifact["size_bytes"] = len(payload)
    EXPERIMENT_MANIFEST_PATH.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def run_analysis(archive_path: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT) -> dict:
    archive_path = archive_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    model_spec = json.loads(MODEL_SPEC_PATH.read_text(encoding="utf-8"))
    observations, source_provenance = extract_observations(archive_path)
    summary = _summaries(observations)
    monotonicity = _monotonicity(summary)
    grouped_n = {(row["group"], row["week"]): row["n_source_values"] for row in summary}
    if grouped_n.get(("50:50", 3)) != 3:
        raise ValueError("source-table missing-value check changed: expected n=3 for 50:50 at week 3")

    repo_root = HERE.parents[2]
    output_csv = output_dir / "vasodilation_observations.csv"
    _write_csv(output_csv, observations)
    result = {
        "experiment_id": "hgps003-lmna-abe-tebv-vasodilation",
        "model_specification": {
            "research_question": model_spec["research_question"],
            "falsifier": model_spec["planned_falsifier"]["decision_rule"],
        },
        "primary_endpoint": "Percent change in TEBV diameter from after phenylephrine to after acetylcholine.",
        "unit": "% diameter change",
        "experimental_unit": "TEBV",
        "source_observation_count": len(observations),
        "summaries": summary,
        "monotone_dose_response_check": monotonicity,
        "monotone_dose_response_supported_descriptively": all(item["nondecreasing"] for item in monotonicity),
        "donor_generalization": {
            "status": "not_testable",
            "split": "leave-one-HGPS-donor-out",
            "independent_hgps_donors": 1,
            "independent_healthy_donors": 1,
            "minimum_disease_donors_for_benchmark": model_spec["donor_held_out_validation"]["minimum_independent_hgps_donors"],
            "reason": "All HGPS lines in the study derive from donor 003; the public Figure 8 workbook has no donor or TEBV identifiers per value.",
        },
        "author_reported_model": {
            "method": model_spec["source_analysis"]["method"],
            "ratio_p_value": model_spec["source_analysis"]["author_reported_results"]["ratio_p_value"],
            "week_p_value": model_spec["source_analysis"]["author_reported_results"]["week_p_value"],
            "reported_pairwise_comparison": model_spec["source_analysis"]["author_reported_results"]["pairwise_comparison"],
            "source_member": model_spec["source_analysis"]["source_output"],
            "locally_refit": model_spec["source_analysis"]["locally_refit"],
        },
        "calibration": {
            "status": model_spec["calibration"]["status"],
            "reported_flow_ml_min_per_tebv": model_spec["calibration"]["reported_operating_conditions"]["flow_rate_ml_min_per_tebv"],
            "reported_nominal_wall_shear_dyn_cm2": model_spec["calibration"]["reported_operating_conditions"]["nominal_wall_shear_dyn_cm2"],
            "raw_flow_or_calibration_record_available": False,
        },
        "interpretation": (
            "The observed group means do not rise monotonically with edited fraction at either timepoint. "
            "This descriptive falsifier and the source-reported ratio effect apply to one HGPS donor in an in-vitro TEBV model; they do not establish a donor-general threshold or rejuvenation."
        ),
        "source_provenance": source_provenance,
    }
    output_json = output_dir / "summary.json"
    output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = _report(result)
    report_path = output_dir / "REPORT.md"
    report_path.write_text(report, encoding="utf-8")

    script_record = file_record(Path(__file__), repo_root)
    outputs = [file_record(path, repo_root) for path in (output_csv, output_json, report_path)]
    provenance = {
        "schema_version": 1,
        "experiment_id": result["experiment_id"],
        "source": source_provenance,
        "analysis_code": script_record,
        "analysis_specification": file_record(MODEL_SPEC_PATH, repo_root),
        "outputs": outputs,
        "reproduction_command": "python studies/mutation_repair_pilot/tebv_benchmark/analyze.py",
    }
    provenance_path = output_dir / "provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if output_dir == DEFAULT_OUTPUT.resolve():
        _refresh_manifest_artifacts(repo_root)
    return result


def _report(result: dict) -> str:
    rows = result["summaries"]
    lines = [
        "# HGPS LMNA correction: TEBV vasodilation benchmark",
        "",
        "> This is a descriptive reanalysis of one published in-vitro HGPS donor model. It is not evidence of ordinary human aging reversal, treatment efficacy, or a clinical intervention.",
        "",
        "## Question and falsifier",
        "",
        f"{result['model_specification']['research_question']} {result['model_specification']['falsifier']}",
        "",
        "## Reproduced values",
        "",
        "Values are reported percent diameter change from after phenylephrine to after acetylcholine. Summary statistics are recomputed from the public workbook; author-reported ANOVA values below are transcribed from the archive's `ANOVA_Fig8.pdf` and were not refit.",
        "",
        "| Group | Week | n in workbook | Mean | SD |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        sd = "n/a" if row["sd"] is None else f"{row['sd']:.4f}"
        lines.append(f"| {row['group']} | {row['week']} | {row['n_source_values']} | {row['mean']:.4f} | {sd} |")
    lines += [
        "",
        "The published Figure 8 caption says N=4 TEBVs per vasoactivity group, while the public workbook and its ANOVA summary contain 35 values: the 50:50 group at week 3 has three values. The workbook has no TEBV identifiers, so the missing value and longitudinal pairing cannot be resolved here.",
        "",
        "## Benchmark result",
        "",
        f"The edited-fraction means are not monotone at either week. At week 3, the 50:50 mean is above the 75:25 mean; at week 5, the 25:75 mean is highest. The author's ordinary two-way ANOVA reports a ratio effect (p={result['author_reported_model']['ratio_p_value']:.4f}), no overall week effect (p={result['author_reported_model']['week_p_value']:.4f}), and a week-5 25% edited versus HGPS comparison (adjusted p={result['author_reported_model']['reported_pairwise_comparison']['adjusted_p_value']:.4f}). These source-level results do not support a simple monotone dose rule.",
        "",
        "## Donor and calibration gates",
        "",
        "Donor-held-out validation is **not testable**: the HGPS cell lines used in the study come from one person (donor 003), and the Figure 8 workbook has no donor or vessel ID on individual values. The paper itself identifies testing the correction and mixing experiment in the second HGPS donor (HGADFN167) as future work. The public data therefore support within-study description, not donor-general model performance.",
        "",
        "The paper reports a perfusion setting of 0.5 mL/min per TEBV and nominal wall shear of 6.8 dyn/cm². No original flow trace, pump calibration record, or uncertainty budget is included in the Figure 8 archive. The related `perfusion-calibration-lab` repository is linked as a candidate analysis tool only; it was not applied to this experiment.",
        "",
        "## Reproduction",
        "",
        "```powershell",
        "docker compose exec workbench python /lab/workbench/studies/mutation_repair_pilot/tebv_benchmark/analyze.py",
        "docker compose exec workbench python /lab/workbench/tools/validate_experiment_manifest.py /lab/workbench/studies/mutation_repair_pilot/tebv_benchmark/experiment.json",
        "```",
        "",
        "Source: Abutaleb et al., APL Bioengineering (2025), doi:10.1063/5.0244026; Duke Research Data Repository, doi:10.7924/r4pg1xv1b (CC0).",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="pinned Figure 8 source archive")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="output directory")
    args = parser.parse_args(argv)
    result = run_analysis(args.input, args.out)
    print(f"Wrote {args.out.resolve()} ({result['source_observation_count']} raw workbook values)")
    print(f"Donor-held-out benchmark: {result['donor_generalization']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
