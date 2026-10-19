"""Extract printed summaries from hash-pinned primary XML/HTML; no graph reading."""
from __future__ import annotations
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def load_json(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("Duplicate JSON key")
            out[key] = value
        return out
    def bad(value):
        raise ValueError("Non-finite JSON constant")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=bad)

def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")

def text_sha(path):
    return hashlib.sha256(Path(path).read_text(encoding="utf-8").encode("utf-8")).hexdigest()

def verified_sources():
    rows = load_json(HERE / "source_receipts.json")["actual_fetches"]
    found = {}
    for row in rows:
        path = ROOT / row["cache_path"]
        raw = path.read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Primary source bytes differ from actual-fetch receipt")
        valid = not path.name.endswith(".docx") or raw.startswith(b"PK\x03\x04")
        if valid != row["expected_document_received"]:
            raise ValueError("Source document type differs from receipt qualification")
        if valid:
            found[path.name] = raw
    return found

def clean(text):
    return " ".join(text.split())

class Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = None
        self.rows = []
    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.parts = []
    def handle_endtag(self, tag):
        if tag == "p" and self.parts is not None:
            self.rows.append(clean("".join(self.parts)))
            self.parts = None
    def handle_data(self, text):
        if self.parts is not None:
            self.parts.append(text)

def magnetic_summary(raw):
    parser = Paragraphs()
    parser.feed(raw.decode("utf-8"))
    paragraphs = parser.rows
    def find(token):
        selected = [(i, p) for i, p in enumerate(paragraphs) if token in p]
        if len(selected) != 1:
            raise ValueError("Magnetic source paragraph is missing or ambiguous")
        return selected[0]
    i, calibration = find("the bending stiffness (Kpost)")
    j, bare = find("deflection of the posts was measured")
    k, contraction = find("PTCs reduced in length to")
    a = re.search(r"elasticity of ([\d.]+) MPa.*?calculated to be ([\d.]+) µN/µm", calibration)
    b = re.search(r"measured to be ([\d,]+) ± ([\d.]+) µm.*?equates to ([\d.]+) µN", bare)
    c = re.search(r"length to ([\d,]+) ± ([\d.]+) µm.*?without cells were ([\d,]+) µm.*?force of ([\d.]+) ± ([\d.]+) µN", contraction)
    if not all((a, b, c)):
        raise ValueError("Magnetic numerical text format differs")
    n = lambda s: float(s.replace(",", ""))
    return {"source_id": "magnetic2024", "doi": "10.1177/00220345241264792",
        "data_kind": "printed_aggregate_summaries_not_individual_construct_records",
        "assumed_PDMS_elastic_modulus_MPa": n(a[1]), "calculated_post_stiffness_uN_per_um": n(a[2]),
        "bare_post_deflection_um": n(b[1]), "bare_post_deflection_reported_spread_um": n(b[2]),
        "bare_post_spread_definition": "Not specified in the accessed main-text paragraph; not assigned SD or SEM",
        "source_bare_post_force_uN": n(b[3]), "PTC_length_mean_um": n(c[1]), "PTC_length_SEM_um": n(c[2]),
        "acellular_reference_length_um": n(c[3]), "PTC_active_force_mean_uN": n(c[4]), "PTC_active_force_SEM_uN": n(c[5]),
        "PTC_spread_definition": "mean+/-SEM in Figure2 caption; inferential baseline n not assigned from unrelated panels",
        "source_paragraph_indices_zero_based": {"post_stiffness": i, "bare_deflection": j, "contraction": k},
        "source_paragraph_sha256": {name: hashlib.sha256(text.encode()).hexdigest() for name, text in
            (("post_stiffness", calibration), ("bare_deflection", bare), ("contraction", contraction))},
        "recovery_measurement_context": {"4h_constructs": 5, "24h_constructs": 6, "1week_constructs": 6,
            "numeric_individual_before_during_after_lengths": None, "same_construct_timecourse_crosswalk": None,
            "context_locator": "Figure3D-F caption; n are constructs, not independent donors"},
        "qualitative_outcomes_only": {"4h": "Partial elastic recovery with residual deformation",
            "24h": "Little elastic recovery and permanent deformation", "1week": "Creep elongation and reduced calculated contractile force"}}

def native_summaries(raw):
    root = ET.fromstring(raw)
    tables = {t.attrib["id"]: t for t in root.findall(".//table-wrap")}
    if set(tables) != {"Tab1", "Tab2"}:
        raise ValueError("Native table identity differs")
    regimes = []
    for tr in tables["Tab1"].findall(".//tbody/tr"):
        cells = [clean("".join(c.itertext())) for c in tr.findall("td")][-5:]
        rate, load, hold, unload, cycles = map(float, cells)
        regimes.append({"peak_load_N": load, "loading_rate_N_per_min": rate, "hold_s": hold,
                        "unloading_rate_N_per_min": unload, "repeated_cycles": int(cycles)})
    rows, load = [], None
    for tr in tables["Tab2"].findall(".//tbody/tr"):
        cells = [clean("".join(c.itertext())) for c in tr.findall("td")]
        if len(cells) == 5:
            label = cells.pop(0)
            load = float(re.fullmatch(r"0–([135]) N", label)[1])
        if len(cells) != 4 or load is None:
            raise ValueError("Native table row/rowspan differs")
        tooth, e1, e2, strain = cells
        def mean_sd(value):
            a, b = value.split("±")
            return float(a), float(b)
        e1, e1_sd = mean_sd(e1)
        e2, e2_sd = mean_sd(e2)
        rows.append({"peak_load_N": load, "tooth_class": tooth, "E1_mean_MPa": e1, "E1_SD_MPa": e1_sd,
            "E2_mean_MPa": e2, "E2_SD_MPa": e2_sd, "source_mean_ultimate_strain": float(strain),
            "strain_definition": "Bilinear transition epsilon12 in main text; not a measured rupture/failure strain",
            "unit": "Aggregate source tooth-class/regime summary; not an individual donor"})
    if len(rows) != 6 or len(regimes) != 3:
        raise ValueError("Expected all six native summary rows and three regimes")
    return {"source_id": "native_tension2018", "doi": "10.1186/s12938-018-0607-0",
        "data_kind": "printed_aggregate_means_and_SDs_not_individual_donor_data",
        "regimes": regimes, "table2_rows": rows,
        "source_discussion_upper_value_MPa": 6.82,
        "context": "Three male cadavers ages31-52;18 slices from6 incisors; individual ages and crosswalk absent; repeated cycles within specimens"}

def main():
    sources = verified_sources()
    extract = {"data_kind": "observed_primary_summary_numbers_no_synthetic_people_or_constructs",
        "magnetic": magnetic_summary(sources["magnetic2024.html"]),
        "native": native_summaries(sources["native_tension2018.xml"]),
        "cache_receipts_text_sha256": text_sha(HERE / "source_receipts.json"),
        "extractor_text_sha256": text_sha(Path(__file__)),
        "rights": {"native": "Wu et al.2018, CC BY4.0; numerical table transcription and original calculations",
            "magnetic": "Mulimani et al.2024; factual numerical summaries only, raw article/response bytes ignored; no text or figures redistributed"}}
    save_json(HERE / "source_summary_extract.json", extract)
    print("Extracted magnetic aggregate summaries and all six native Table2 rows; four cached response hashes verified")

if __name__ == "__main__":
    main()
