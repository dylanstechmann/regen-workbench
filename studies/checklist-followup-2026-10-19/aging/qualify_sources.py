"""Extract official GEO metadata without promoting libraries to people."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MAX_EXPANDED = 32 * 1024 * 1024


def read_soft(path: Path) -> tuple[dict, list[dict]]:
    series, samples, current = {}, [], None
    expanded = 0
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for raw in handle:
            expanded += len(raw.encode("utf-8"))
            if expanded > MAX_EXPANDED:
                raise ValueError("Expanded metadata exceeds qualification bound")
            line = raw.rstrip("\r\n")
            if line.startswith("^SERIES = "):
                current = series
                current["accession"] = line.split(" = ", 1)[1]
            elif line.startswith("^SAMPLE = "):
                current = {"accession": line.split(" = ", 1)[1]}
                samples.append(current)
            elif line.startswith("^"):
                current = None
            elif current is not None and line.startswith("!") and " = " in line:
                key, value = line[1:].split(" = ", 1)
                current.setdefault(key, []).append(value)
    expected = set(series.get("Series_sample_id", []))
    actual = {sample["accession"] for sample in samples}
    if not samples or len(actual) != len(samples) or expected != actual:
        raise ValueError("Declared GEO samples do not match unique parsed records")
    return series, samples


def characteristics(sample: dict) -> dict[str, str]:
    result = {}
    for item in sample.get("Sample_characteristics_ch1", []):
        if ":" in item:
            key, value = item.split(":", 1)
            key = key.strip().casefold()
            if key in result and result[key] != value.strip():
                raise ValueError("Conflicting within-sample characteristic")
            result[key] = value.strip()
    return result


def sample_rows(series: dict, samples: list[dict]) -> list[dict]:
    result = []
    for sample in samples:
        char = characteristics(sample)
        title = sample["Sample_title"][0]
        accession = series["accession"]
        donor = ""
        donor_status = "not_resolved_from_GEO"
        if accession == "GSE173078":
            match = re.fullmatch(r"(AC\d+)_(Healthy|Gingivitis|Periodontitis) \(RNA-seq\)", title)
            if not match or match.group(2) != char["phenotype"]:
                raise ValueError("GSE173078 participant-code/phenotype crosswalk mismatch")
            donor = match.group(1)
            donor_status = "participant_code_one_library_each_per_series_design"
        elif accession == "GSE111523":
            match = re.fullmatch(r"\d+_(\d+)(con|pw) \[RNA-Seq\]", title)
            if not match:
                raise ValueError("Unexpected healing-study title")
            donor = "volunteer_" + match.group(1)
            donor_status = "paired_sides_inferred_from_title_and_sample_description"
        elif accession == "GSE133603" and sample.get("Sample_organism_ch1") == ["Homo sapiens"]:
            donor = title
            donor_status = "one_human_biopsy_per_donor_as_series_design_no_repeat_donor_key"
        age = char.get("age", "")
        if re.fullmatch(r"\d+(?:\.\d+)?(?: years old)?", age):
            age_years = float(age.split()[0])
        else:
            age_years = ""
        sex = char.get("sex", "").casefold()
        sex = {"m": "male", "f": "female"}.get(sex, sex)
        result.append({"series": accession, "GSM": sample["accession"], "title": title,
                       "organism": ";".join(sample.get("Sample_organism_ch1", [])),
                       "tissue": char.get("tissue", char.get("cell source", "")),
                       "donor_code": donor, "donor_resolution": donor_status,
                       "age_as_supplied": age, "age_years": age_years, "sex": sex,
                       "phenotype": char.get("phenotype", char.get("disease state", char.get("disease", char.get("genotype", "")))),
                       "sampling_group": char.get("group", ""), "batch": char.get("batch", ""),
                       "platform": ";".join(sample.get("Sample_platform_id", [])),
                       "source_url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=" + sample["accession"]})
    return result


def main() -> None:
    receipts = json.loads((HERE / "source_receipts.json").read_text(encoding="utf-8"))
    records = []
    for source in receipts["sources"]:
        if not source["filename"].endswith(".soft.gz"):
            continue
        path = ROOT / source["local_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("Source bytes differ from actual-fetch receipt")
        series, samples = read_soft(path)
        records.extend(sample_rows(series, samples))
    out = HERE / "derived"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "candidate_geo_samples.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, list(records[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    dispositions = [
        {"series": "GSE173078", "rank": 1, "healthy_library_count": 12, "healthy_donor_count": 12,
         "status": "bounded_healthy_bulk_challenge", "tissue": "human fresh gingiva, bulk",
         "age_sex": "Exact numeric ages and sex per AC participant code; healthy 28-75y, 10F/2M",
         "nesting": "36 unique AC codes, one RNA-seq library each; paired methylation series is not extra people",
         "raw_or_processed": "Public 1.20MB gzip integer gene counts and SRA; hg19/STAR/featureCounts, HiSeq4000",
         "gap": "Only two healthy men, both batch A and ages 32/39; health is provider-labelled, no independent clinical adjudication",
         "next_action": "Analyze frozen panels in healthy women with batch adjustment; retain full-cohort sensitivities"},
        {"series": "GSE111523", "rank": 2, "healthy_library_count": 18, "healthy_donor_count": 9,
         "status": "defer_individual_demographic_crosswalk", "tissue": "human palatal gingiva; control versus previously wounded side",
         "age_sex": "No individual ages or sex in retrieved GEO SOFT",
         "nesting": "Nine volunteer title codes each repeated as con/pw; 18 libraries are not 18 donors",
         "raw_or_processed": "Public processed count/quantile-normalized workbook and SRA; Ion Proton",
         "gap": "Demographics and wound-stage crosswalk required; healed/wounded side is not untouched healthy baseline",
         "next_action": "Recover donor-linked author demographics and exact control-side stage before any age fit"},
        {"series": "GSE133603", "rank": 3, "healthy_library_count": 4, "healthy_donor_count": 4,
         "status": "too_small_for_this_reference", "tissue": "human gingival biopsies plus separate mouse tongue libraries",
         "age_sex": "Healthy ages 23,25,27,43; 3F/1M",
         "nesting": "Four healthy human biopsy titles, one library each; do not count two SRA relations as two donors",
         "raw_or_processed": "Public human-specific raw-count and TMM-CPM tables, SRA; NextSeq500",
         "gap": "Too few healthy donors/limited age range; APECED and mouse samples cannot extend healthy human age coverage",
         "next_action": "Retain as separate immune-disease challenge, not an adult age validation cohort"},
        {"series": "GSE224044", "rank": 4, "healthy_library_count": 3, "healthy_donor_count": "unresolved",
         "status": "defer_missing_age_sex_and_nesting", "tissue": "human gingiva versus peri-implantitis",
         "age_sex": "No numeric age or sex in retrieved GEO SOFT",
         "nesting": "Three healthy sample labels; no formal participant key recovered",
         "raw_or_processed": "Public per-sample processed TXT and SRA; HiSeq2500",
         "gap": "Small sample count, demographics missing, donor mapping unverified",
         "next_action": "Require donor-linked author metadata; do not invent ages from another analysis"},
        {"series": "GSE312885", "rank": 5, "healthy_library_count": 0, "healthy_donor_count": "unresolved",
         "status": "wrong_deposited_experiment_and_pooled_single_cells", "tissue": "six cultured human knockdown/control bulk libraries in cited accession",
         "age_sex": "No numeric age, sex or donor mapping in retrieved accession",
         "nesting": "Primary paper methods 4.3 pool gingiva from similar donors for each single-cell sample (2 young/3 aged libraries)",
         "raw_or_processed": "Accession supplies FPKM workbook and SRA for shIFT88/control bulk samples, not identified donor-resolved age libraries",
         "gap": "Age-library donor pooling prevents treating five pools as five people; cited deposit does not supply that aging series",
         "next_action": "Obtain correct single-cell deposit and constituent donor/pool metadata before considering a cell-resolved challenge"},
    ]
    with (out / "candidate_qualification.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, list(dispositions[0]) + ["source_url"], delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows({**row, "source_url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=" + row["series"]} for row in dispositions)
    for accession in sorted({row["series"] for row in records}):
        current = [row for row in records if row["series"] == accession]
        print(json.dumps({"series": accession, "libraries": len(current), "numeric_ages": sum(row["age_years"] != "" for row in current),
                          "sex_recorded": sum(row["sex"] in {"female", "male"} for row in current),
                          "phenotypes": dict(Counter(row["phenotype"] for row in current))}))
    print("GSE173078 HEALTHY DEMOGRAPHICS")
    print(json.dumps([{key: row[key] for key in ["donor_code", "age_years", "sex", "batch"]}
                      for row in records if row["series"] == "GSE173078" and row["phenotype"] == "Healthy"], indent=2))


if __name__ == "__main__":
    main()
