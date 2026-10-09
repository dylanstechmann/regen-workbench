"""One deposited dental table: validate, scale to CPM, reuse exploratory contrasts.

Study-specific analysis, not a new expression method. No statistical inference.
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).parent
sys.path.insert(0, str(ROOT / "tools"))
import regen
from regen_compute import (
    expression_contrast,
    identifier,
    report_directory,
    write_csv,
    write_json,
)

URL = "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE307nnn/GSE307437/suppl/GSE307437_gene_raw_counts_matrix.csv.gz"
RAW = ROOT / "data/literature/GSE307437-gene-raw-counts-2026-10-09.csv.gz"
LIMIT = 16 * 1024 * 1024
# Correspondence is a declared interpretation of source labels, not genotyping.
LABELS = (
    ("WT_isAM_1", "GSM9224208", "WT_untreated", "WT isAM organoids, untreated, biol rep 1"),
    ("WT_isAM_2", "GSM9224209", "WT_untreated", "WT isAM organoids, untreated, biol rep 2"),
    ("WT_C3DLL4_isAM_1", "GSM9224210", "WT_treated", "WT isAM organoids, C3-DLL4 treated, biol rep 1"),
    ("WT_C3DLL4_isAM_2", "GSM9224211", "WT_treated", "WT isAM organoids, C3-DLL4 treated, biol rep 2"),
    ("DLX3KO_C3DLL4_isAM_1", "GSM9224212", "KO_treated", "DLX3-KO isAM organoids, C3-DLL4 treated, biol rep 1"),
    ("DLX3KO_C3DLL4_isAM_2", "GSM9224213", "KO_treated", "DLX3-KO isAM organoids, C3-DLL4 treated, biol rep 2"),
)
# Declared before running: enamel-associated genes, transcription factors and
# epithelial/context markers. Not an exhaustive gene set or a maturity score.
PANEL = ("AMELX", "AMBN", "ENAM", "MMP20", "KLK4", "DLX3", "SP6", "ALPL", "KRT14", "KRT19", "SOX2")


def qualify_counts(raw, metadata):
    if len(raw) > LIMIT:
        raise ValueError("Compressed count table exceeds limit")
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as handle:
        expanded = handle.read(LIMIT + 1)
    if len(expanded) > LIMIT:
        raise ValueError("Expanded count table exceeds limit")
    reader = csv.reader(io.StringIO(expanded.decode("utf-8-sig")), strict=True)
    header = next(reader, [])
    if header != ["", *[entry[0] for entry in LABELS]]:
        raise ValueError("Count header differs from the six declared source labels")
    if metadata["series"]["accession"] != "GSE307437":
        raise ValueError("Wrong metadata series")
    samples = {s["accession"]: s for s in metadata["samples"]}
    if len(samples) != len(metadata["samples"]) or set(samples) != {s[1] for s in LABELS}:
        raise ValueError("Metadata sample set differs from the declared mapping")
    for _, accession, _, title in LABELS:
        if samples[accession]["fields"]["Sample_title"] != [title]:
            raise ValueError("Source title does not support declared column correspondence")
    rows, seen = [], set()
    for row in reader:
        if len(row) != len(header):
            raise ValueError("Ragged count row")
        gene = identifier(row[0], "gene")
        if gene in seen:
            raise ValueError("Duplicate gene identifier")
        seen.add(gene)
        if any(not value.isascii() or not value.isdigit() for value in row[1:]):
            raise ValueError("Raw counts must be nonnegative decimal integers")
        counts = [int(value) for value in row[1:]]
        if any(value > 10**12 for value in counts):
            raise ValueError("Count exceeds study intake bound")
        rows.append((gene, counts))
    if not 1 <= len(rows) <= 50000:
        raise ValueError("Expected 1-50,000 gene rows")
    totals = [sum(counts[i] for _, counts in rows) for i in range(6)]
    if any(total == 0 for total in totals):
        raise ValueError("Zero-total library cannot be scaled to CPM")
    normalized = [(gene, [value * 1e6 / totals[i] for i, value in enumerate(counts)]) for gene, counts in rows]
    qc = [{"column": entry[0], "sample_accession": entry[1], "group": entry[2],
           "source_title": entry[3], "assigned_count_total": totals[i],
           "nonzero_gene_rows": sum(counts[i] > 0 for _, counts in rows),
           "independent_donor_id": None, "clone_id": None, "culture_batch_id": None}
          for i, entry in enumerate(LABELS)]
    return normalized, qc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Acquire the exact advertised file and new provenance")
    parser.add_argument("--out", required=True, type=Path, help="New private output directory")
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Analysis output already exists")
    receipt_path = STUDY / "count_receipt.json"
    if args.fetch:
        raw = regen.http_bytes(URL, timeout=45)
        if len(raw) > LIMIT:
            raise ValueError("Count response exceeds limit")
        RAW.write_bytes(raw)
        provenance = regen.record("dental-organoid-count-intake", {"url": URL, "accession": "GSE307437"}, [RAW])
        write_json(receipt_path, {"accession": "GSE307437", "url": URL, "retrieved_utc": regen.now(),
                                 "response_sha256": regen.sha256_file(RAW), "local_provenance_receipt": provenance.name})
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    raw = RAW.read_bytes()
    if hashlib.sha256(raw).hexdigest() != receipt["response_sha256"] or receipt["url"] != URL:
        raise ValueError("Cached counts do not match exact-source retrieval receipt")
    metadata_receipt = json.loads((STUDY / "geo_metadata_receipt.json").read_text(encoding="utf-8"))
    expected = next(r for r in metadata_receipt["records"] if r["accession"] == "GSE307437")
    metadata_path = ROOT / "data/literature/GSE307437-metadata-2026-10-09.soft.metadata.json"
    if regen.sha256_file(metadata_path) != expected["parsed_metadata_sha256"]:
        raise ValueError("Cached metadata does not match receipt")
    rows, qc = qualify_counts(raw, json.loads(metadata_path.read_text(encoding="utf-8")))
    summary = {"origin": "retrieved_source_counts_descriptive_analysis", "assisted_by": "AI",
               "count_response_sha256": receipt["response_sha256"],
               "metadata_sha256": expected["parsed_metadata_sha256"], "source_url": URL,
               "gene_rows": len(rows), "libraries": qc, "panel_declared_before_analysis": list(PANEL),
               "normalization": "CPM = count / sum of all deposited gene counts in that library * 1,000,000",
               "independent_biological_units_qualified": False, "reuse_license_qualified": False,
               "p_values_calculated": False, "differential_expression_inferred": False,
               "functional_maturation_inferred": False, "comparisons": []}
    with report_directory(args.out):
        for name, reference, comparison in (("treatment_in_WT", "WT_untreated", "WT_treated"),
                                             ("genotype_under_treatment", "WT_treated", "KO_treated")):
            indices = [i for i, label in enumerate(LABELS) if label[2] in (reference, comparison)]
            matrix, samples = args.out / f"{name}.cpm.csv", args.out / f"{name}.samples.csv"
            fields = ["gene", *[LABELS[i][0] for i in indices]]
            write_csv(matrix, fields, [{"gene": gene, **{LABELS[i][0]: values[i] for i in indices}} for gene, values in rows])
            write_csv(samples, ["sample", "group"], [{"sample": LABELS[i][0], "group": LABELS[i][2]} for i in indices])
            for pseudocount in (0.1, 1.0):
                output = args.out / f"{name}-pc{pseudocount}"
                expression_contrast(["--matrix", str(matrix), "--samples", str(samples),
                                     "--reference", reference, "--comparison", comparison,
                                     "--pseudocount", str(pseudocount), "--out", str(output)], regen.record)
                result = json.loads((output / "contrast.json").read_text(encoding="utf-8"))
                by_gene = {row["gene"]: row for row in result["genes"]}
                summary["comparisons"].append({"name": name, "reference": reference, "comparison": comparison,
                                               "pseudocount_cpm": pseudocount,
                                               "missing_panel_identifiers": [g for g in PANEL if g not in by_gene],
                                               "panel": [by_gene[g] for g in PANEL if g in by_gene],
                                               "method_manifest_sha256": regen.sha256_file(output / "manifest.json")})
        summary["implementation_sha256"] = regen.sha256_file(Path(__file__))
        summary["python_version"] = platform.python_version()
        write_json(args.out / "summary.json", summary)
        regen.record("dental-organoid-descriptive-cpm", {"count_sha256": receipt["response_sha256"],
                     "pseudocounts_cpm": [0.1, 1.0]}, [args.out / "summary.json"])
    write_json(STUDY / "ameloblast_expression_summary.json", summary)
    print(json.dumps({"gene_rows": len(rows), "libraries": len(qc), "comparisons_with_sensitivity": len(summary["comparisons"])}))


if __name__ == "__main__":
    main()
