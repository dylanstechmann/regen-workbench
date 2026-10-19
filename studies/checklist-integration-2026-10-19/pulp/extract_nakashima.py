"""Hash-verified primary-table extraction retaining source IDs and ambiguities."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def load_json(path):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out: raise ValueError("Duplicate JSON field")
            out[k] = v
        return out
    def bad(value): raise ValueError("Nonfinite JSON constant")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=bad)

def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")

def text_sha(path):
    return hashlib.sha256(Path(path).read_text(encoding="utf-8").encode()).hexdigest()

def flatten(e, footnotes=True):
    if e.tag == "sup" and not footnotes: return ""
    if e.tag == "break": return " "
    return (e.text or "") + "".join(flatten(c, footnotes) + (c.tail or "") for c in e)

def clean(text): return " ".join(text.split())

def source_root():
    rows = load_json(HERE / "source_receipts.json")["actual_fetches"]
    if len(rows) != 1: raise ValueError("Expected one frozen primary-source document")
    row = rows[0]
    raw = (ROOT / row["cache_path"]).read_bytes()
    if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ValueError("Primary source differs from its actual-fetch receipt")
    return ET.fromstring(raw)

def table_rows(root, ident):
    table = root.find(f'.//table-wrap[@id="{ident}"]')
    if table is None: raise ValueError("Missing source table")
    heads = [clean(flatten(c)) for c in table.findall(".//thead/tr/th")]
    target_heads = [f"Patient {i}" for i in range(1,6)]
    if heads[1:] != target_heads + (["Average"] if ident == "Tab2" else []): raise ValueError("Patient-column identities changed")
    rows = {}
    for tr in table.findall(".//tbody/tr"):
        cells = tr.findall("td")
        if len(cells) == 1: continue
        if len(cells) != (7 if ident == "Tab2" else 6): raise ValueError("Unexpected patient row width")
        label = clean(flatten(cells[0]))
        if label in rows: raise ValueError("Duplicate source endpoint row")
        rows[label] = [{"source_text": clean(flatten(c)), "core_text": clean(flatten(c, False)),
                        "footnote_markers": [clean(flatten(s)) for s in c.findall(".//sup")]} for c in cells[1:6]]
    return rows

def parse_ept(cell):
    text = cell["core_text"]
    if text.startswith("+"): status = True
    elif text == "–": status = False
    else: raise ValueError("Unrecognized source EPT status")
    m = re.search(r"\(([\d+, ]+)\)", text)
    readings = []
    if m:
        for token in m[1].split(","):
            token = token.strip()
            if not re.fullmatch(r"\d+\+?", token): raise ValueError("Unrecognized EPT device token")
            readings.append({"source_token": token, "value_or_lower_limit": int(token.rstrip("+")),
                             "censoring": "right_censored" if token.endswith("+") else "exact_device_reading"})
    if status and len(readings) != 3: raise ValueError("Expected three dentist device readings")
    control = re.search(r"\(control (.+) (\d+)\)", text)
    day = re.search(r"Day (\d+)", text)
    return {**cell, "source_positive": status, "first_positive_day_if_reported": int(day[1]) if day else None,
        "readings_nested_in_patient_visit": readings,
        "control_tooth_literal": control[1] if control else None,
        "control_device_reading": int(control[2]) if control else None,
        "late_positive_note": "Positive reaction detected after36weeks; exact day not given" if "a" in cell["footnote_markers"] else None}

def extract(root):
    base, outcomes = table_rows(root, "Tab1"), table_rows(root, "Tab4")
    mri_key = "MRI (relative signal intensity of apical part of root canal at 24 weeks)"
    xr_key = "X-ray (periapical radiolucency at 24 weeks)"
    cbct_key = "Cone beam computed tomography (lateral dentin formation)"
    records = []
    for i in range(5):
        xr = outcomes[xr_key][i]
        absence = {"–": True, "+": False, "–/+": None}[xr["core_text"]]
        records.append({"patient_id": str(i+1), "affected_tooth": base["Affected tooth"][i]["core_text"],
            "age_years_table1": int(base["Age (years)"][i]["core_text"]), "sex_table1": base["Gender"][i]["core_text"],
            "enrollment_EPT_table1": base["Electric pulp test"][i],
            "pre_transplant_EPT_negative_narrative": True,
            "onset_EPT_table4": parse_ept(outcomes["Day positive reaction started"][i]),
            "EPT_12wk_table4": parse_ept(outcomes["12 weeks"][i]),
            "EPT_24wk_table4": parse_ept(outcomes["24 weeks"][i]),
            "MRI_24wk_apical_relative_signal": float(outcomes[mri_key][i]["core_text"]),
            "XR_24wk_source": xr, "XR_24wk_radiolucency_absent": absence,
            "CBCT_lateral_mineralization_source": outcomes[cbct_key][i],
            "CBCT_lateral_mineralization_reported": {"+": True, "–": False}[outcomes[cbct_key][i]["core_text"]],
            "CBCT_table4_time_weeks": None,
            "blood_urine_ECG_local_examination_abnormality_source": {k: outcomes[k][i]["core_text"] for k in
                ("Blood test", "Urine test", "Cardiogram", "Local clinical examination")},
            "blood_flow_direct_measurement": None, "human_pulp_histological_identity": None})
    paragraphs = [clean(flatten(p)) for p in root.findall(".//p")]
    volume = next(t for t in paragraphs if "from 0.0143 cm3" in t)
    volumes = []
    for m in re.finditer(r"from ([\d.]+) (c?m3) to ([\d.]+) (c?m3) in patient ([14])", volume):
        volumes.append({"patient_id": m[5], "before_value": float(m[1]), "before_unit_literal": m[2],
            "after_value": float(m[3]), "after_unit_literal": m[4],
            "results_narrative_times_weeks": [16,28],
            "timing_qualification": "Figure3b labels16 and28/32weeks; patient4 Discussion instead mentions12/24weeks" if m[5]=="4" else "Results narrative16/28weeks; no individual acquisition dates given",
            "endpoint": "CBCT threshold-defined low-density pulp-space volume, not direct tissue mass, perfusion or histological dentin volume"})
    if len(volumes) != 2: raise ValueError("Expected both source narrative volume pairs")
    karyotypes = table_rows(root, "Tab2")["Karyotype"]
    return {"source_doi": "10.1186/s13287-017-0506-5", "source_attribution": "Nakashima et al.2017, Stem Cell Research & Therapy8:61, CC BY4.0",
        "data_kind": "observed_public_patient_table_transcription_with_explicit_narrative_annotations",
        "n_enrolled_reported": 5, "n_screened_or_approached": None,
        "patient_records": records, "source_volume_pairs": volumes,
        "source_cell_karyotype_literals_not_clinical_adverse_adjudication": [{"patient_id": str(i+1), **r} for i,r in enumerate(karyotypes)],
        "MRI_ratio_definition": "Ratio of root-canal tissue signal to surrounding dentin, compared with normal pulp/dentin in the opposite site; apical Table4 values only. No healthy threshold adopted.",
        "followup": {"Table4_EPT_MRI_XR_named_week": 24, "CBCT_Table4_named_week": None,
            "patient2_late_EPT_footnote": "after36weeks; not assigned to24weeks or an exact36-week visit",
            "patient5_CBCT_initial_volume": None, "patient5_missing_baseline_reason": "Source states initial CBCT was not obtained",
            "formal_screening_or_dropout_flow": None},
        "source_narrative_annotations": {"EPT_pre_transplant": "Source states all5 had negative EPT before transplantation; Table1 enrollment precedes intervening pulpectomy and has positive EPT",
            "patient2": "Pre-transplant lesion subsequently shrank; minor PDL-space widening and minus/plus radiolucency at24weeks retained",
            "patient4": "PDL-space widening at12weeks and periapical radiolucency at24weeks; no significant radiolucency increase reported at32weeks; infection mechanism discussed, not causally established",
            "systemic_clinical_events": "No cell-transplantation-attributed events or postoperative pain reported through24weeks; this does not remove radiographic findings or establish long-term safety",
            "apical_obliteration_patient_ids": ["1","3","5"],
            "CBCT_lateral_mineralization_patient_ids": ["1","4","5"],
            "apical_obliteration_visit_label": "24/28weeks; separate X-ray endpoint, not added to24-week joint pattern"},
        "source_receipts_text_sha256": text_sha(HERE / "source_receipts.json"),
        "extractor_text_sha256": text_sha(Path(__file__))}

def main():
    data = extract(source_root())
    save_json(HERE / "patient_records.json", data)
    print("Extracted all5 linked patient/tooth records, censored EPT tokens and two literal-unit volume pairs")

if __name__ == "__main__": main()
