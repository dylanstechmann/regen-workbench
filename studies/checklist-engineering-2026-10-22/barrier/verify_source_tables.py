"""Verify only the two frozen benign table sections against retained primary HTML."""
from __future__ import annotations
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


class TableReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_cell = False
        self.cells = []
        self.row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.row = []
        elif self.in_table and tag in ["td", "th"]:
            self.cells = []
            self.in_cell = True

    def handle_data(self, text):
        if self.in_cell:
            self.cells.append(text)

    def handle_endtag(self, tag):
        if self.in_table and tag in ["td", "th"]:
            self.row.append(" ".join("".join(self.cells).split()))
            self.in_cell = False
        elif self.in_table and tag == "tr":
            self.rows.append(self.row)
        elif tag == "table":
            self.in_table = False


def selected_section(html, identifier):
    if identifier not in {"tbl2", "tbl7"}:
        raise ValueError("Only frozen noninfectious table sections are eligible")
    match = re.search(r'<section\b[^>]*\bid="' + identifier + r'"[^>]*>', html)
    if match is None:
        raise ValueError("Source table missing")
    end = html.find("</section>", match.end())
    if end < 0:
        raise ValueError("Unclosed source section")
    return html[match.start():end + len("</section>")]


def rows_in(section):
    reader = TableReader()
    reader.feed(section)
    return reader.rows


def mean_sem(text):
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*±\s*(\d+(?:\.\d+)?)", text)
    if match is None:
        raise ValueError("Expected explicit mean plus/minus dispersion")
    return tuple(float(x) for x in match.groups())


def scientific_number(text):
    match = re.fullmatch(r"([\d.]+)\s*×\s*10[−–-](\d+)", text)
    if match is None:
        raise ValueError("Expected reported positive scientific notation")
    return float(match.group(1)) * 10 ** (-int(match.group(2)))


def verify(html, facts):
    physical = rows_in(selected_section(html, "tbl2"))
    expected = {r["model"]: r for r in facts["physical_properties"]}
    if len(physical) != 5:
        raise ValueError("Unexpected physical-property table shape")
    if {row[0] for row in physical[1:]} != set(expected):
        raise ValueError("Each frozen model must appear exactly once")
    for row in physical[1:]:
        if len(row) != 3 or row[0] not in expected:
            raise ValueError("Unexpected physical-property model")
        fact = expected[row[0]]
        if mean_sem(row[1]) != (fact["teer_mean"], fact["teer_sem"]):
            raise ValueError("TEER summary differs from frozen extract")
        if mean_sem(row[2]) != (fact["thickness_mean"], fact["thickness_sem"]):
            raise ValueError("Thickness summary differs from frozen extract")
    fd_rows = [r for r in rows_in(selected_section(html, "tbl7")) if r and r[0] == "FD20"]
    if len(fd_rows) != 1 or len(fd_rows[0]) != 4:
        raise ValueError("Expected exactly one standard FD20 row")
    values = facts["fd20_transport"]["reported_coefficients"]
    # The fourth cell is an external literature comparator and is deliberately unused.
    for index, model in [(1, "Submerged"), (2, "ALI")]:
        if abs(scientific_number(fd_rows[0][index]) - values[model]) > 1e-20:
            raise ValueError("FD20 coefficient differs from frozen extract")
    return {"physical_summary_rows_verified": 4, "fd20_coefficients_verified": 2,
            "individual_insert_records_extracted": 0, "other_table_content_used": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    facts = json.loads((HERE / "source_facts.json").read_text(encoding="utf-8"))
    path = args.source or ROOT / facts["source"]["retained_html_path"]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != facts["source"]["retained_html_sha256"]:
        raise ValueError("Retained HTML differs from actual fetch hash")
    print(json.dumps(verify(raw.decode("utf-8"), facts), indent=2))


if __name__ == "__main__":
    main()
