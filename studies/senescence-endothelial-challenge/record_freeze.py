#!/usr/bin/env python3
"""Record a ResearchDesk plan freeze for the GSE160356 endothelial check, then bind its receipt.

The analysis itself lives in the senescence-module-score repository
(``python -m senescore.hrmec_validation``). This script only creates the procedural records
around it, so that the plan, split and method revision are pinned *before* the evaluator runs
and the receipt it writes can be checked against them afterwards.

    python record_freeze.py freeze --workspace <new dir> --senescence-repo <checkout>
    ... run the evaluator from that clean checkout ...
    python record_freeze.py bind   --workspace <same dir> --senescence-repo <checkout>

Nothing here scores anything. The freeze clock, the "results inspected" statement and the
ledger actor are self-reported; the commit time on GitHub is the independent timestamp.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))

import regen  # noqa: E402
import regen_desk  # noqa: E402
import verify_dossier  # noqa: E402

AREA = "tissues"
STATE = HERE / "freeze_state.json"
PRIMARY_METRIC = "directional_auroc_vs_early_passage"
RANDOM_BASELINE = "random_uniform_panels_100"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_head(repo: Path) -> tuple[str, bool]:
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"],
                            capture_output=True, text=True, check=True)
    return head.stdout.strip(), bool(status.stdout.strip())


def load_sources(repo: Path) -> dict:
    snapshot = repo / "validation" / "GSE160356"
    sources = json.loads((snapshot / "sources.json").read_text(encoding="utf-8"))
    if sha256_file(snapshot / "PLAN.md") != sources["snapshots"]["PLAN.md"]:
        raise SystemExit("PLAN.md does not match the hash pinned in sources.json")
    samples = json.loads((snapshot / "samples.json").read_text(encoding="utf-8"))["samples"]
    return {"sources": sources, "samples": samples}


def groups(samples: list[dict]) -> tuple[list[str], list[str]]:
    baseline = sorted(s["accession"] for s in samples if s["condition"] == "early_passage")
    held_out = sorted(s["accession"] for s in samples if s["condition"] != "early_passage")
    return baseline, held_out


def question() -> dict:
    return {
        "question": "Do this repository's fixed gene panels, scored with controls fitted only on early-passage "
                    "libraries, rank late-passage and etoposide-treated HRMEC libraries above early-passage "
                    "libraries, and is any separation by SenMayo distinguishable from random 125-gene panels?",
        "scope": "Nine HRMEC RNA-seq libraries of GEO GSE160356: three early passage, three late passage, three "
                 "etoposide-treated. One retinal endothelial culture system.",
        "claim_boundary": "A descriptive 3-vs-3 ranking only. Passage is confounded with condition; no clone or "
                          "pairing identifier is deposited and none is inferred; no per-library functional assay; "
                          "not tissue performance, not independence, not senescence validation.",
        "hypotheses": [
            {"id": "h1", "prediction": "SenMayo ranks both induced conditions above early passage (directional AUROC "
                                       "1.0 for both) and separates from random panels (empirical rank <= 0.05).",
             "falsifier": "Any primary directional AUROC is below 1.0 (verdict: fail)."},
            {"id": "h2", "prediction": "Any ranking is a generic transcriptome shift: random 125-gene panels separate "
                                       "the same libraries about as well.",
             "falsifier": "SenMayo's absolute mean difference ranks at or below 0.05 against 100 random panels for "
                          "both contrasts."}],
        "source_refs": [
            {"label": "GEO GSE160356", "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE160356"},
            {"label": "Guduric-Fuchs et al. 2024, Aging Cell (design read before freeze; no result read)",
             "url": "https://doi.org/10.1111/acel.14240"},
            {"label": "Saul et al. 2022, SenMayo", "url": "https://doi.org/10.1038/s41467-022-32552-1"}]}


def dataset_card(bundle: dict) -> dict:
    sources, samples = bundle["sources"], bundle["samples"]
    files = [{"path": f"GSE160356/{name}", "format": "htseq-count tsv.gz", "sha256": info["sha256"], "rows": 58889}
             for name, info in sorted(sources["members"].items())]
    files.append({"path": "GSE160356/GSE160356_RAW.tar", "format": "tar", "sha256": sources["raw_archive"]["sha256"],
                  "rows": None})
    files.append({"path": "senescence-module-score/validation/GSE268487/hgnc_mapping.tsv.gz",
                  "format": "tsv.gz", "sha256": sources["hgnc"]["sha256"], "rows": 42497})
    return {
        "citation": "GEO GSE160356 (Bertelli, Pedrini, Guduric-Fuchs, Medina; submitted 2020-10-28, public "
                    "2023-10-27); HGNC mapping snapshot of senescence-module-score.",
        "source_url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE160356",
        "access_status": "public_open",
        "license": "No dataset-specific license stated by GEO",
        "scope": "Nine per-library HTSeq count tables (Ensembl identifiers, GRCh38 release 96) and the pinned "
                 "HGNC Ensembl-to-symbol mapping.",
        "species_or_model": "human retinal microvascular endothelial cells (HRMEC), cultured",
        "stage_or_interval": "Early passage P3-P8; late passage P15-P20; 1 uM etoposide 4 days then 4 days growth (P6-P8).",
        "data_granularity": "individual_level",
        "files": files,
        "unit_hierarchy": [
            {"level": "library", "kind": "RNA-seq library, one per GSM accession",
             "source_field": "Sample_geo_accession", "identity_status": "reported"},
            {"level": "clone", "kind": "independent clone (series text); sample-level mapping not deposited",
             "source_field": "", "identity_status": "not_reported"}],
        "independent_unit_level": "not_reported",
        "observed_quantities": [
            {"endpoint": "gene counts per Ensembl gene", "unit": "reads (HTSeq counts)",
             "measurement_role": "expression input to a control-bin module score",
             "calibration_status": "not_applicable"}],
        "groups": [{"label": "culture condition", "source_fields": ["Sample_characteristics_ch1: treatment"],
                    "role": "early passage = baseline; late passage and etoposide = held out"}],
        "missingness": "None filtered; measured zeros retained; unmapped Ensembl rows stay in the CPM denominator.",
        "exclusions": "HTSeq summary rows (__no_feature, __ambiguous, __too_low_aQual, __not_aligned, "
                      "__alignment_not_unique) are excluded from the denominator and reported."}


def plan(question_id: str, card_id: str, plan_sha256: str) -> dict:
    return {
        "question_revision_id": question_id, "dataset_revision_ids": [card_id],
        "estimand": "Directional AUROC of the SenMayo control-bin score for late-passage vs early-passage and "
                    "etoposide vs early-passage libraries (3 vs 3), under the leave-one-out baseline protocol, "
                    "compared with 100 uniform random 125-gene panels.",
        "primary_outcome": {"endpoint": "directional AUROC of SenMayo score vs early-passage libraries",
                            "unit": "AUROC (0-1)", "timepoint": "single acquisition per library",
                            "comparator": "100 uniform random 125-gene panels (seeds 1000-1099), same protocol",
                            "independent_unit": "library (clone independence not reported)"},
        "alternatives": [
            {"hypothesis_id": "h1", "prediction": "AUROC 1.0 for both contrasts and rank <= 0.05 against random panels."},
            {"hypothesis_id": "h2", "prediction": "Random panels separate the libraries about as well; the rank exceeds 0.05."}],
        "baseline": "100 uniformly random 125-gene panels excluding all registered panels and CDKN1A/CDKN2A, "
                    "scored under the primary protocol.",
        "split": "Development: the three early-passage libraries (the only libraries that may select controls; each "
                 "is scored by a fit from the other two). Sealed: three late-passage and three etoposide libraries.",
        "uncertainty": "None estimated: three libraries per condition cannot support a group interval. Exact "
                       "permutation p over 20 assignments is descriptive (smallest possible 0.1).",
        "missingness_rule": "No expression or condition filter; measured zeros retained; unmapped genes stay in the denominator.",
        "confounding": "Passage is confounded with condition; clone and pairing are not deposited; processing batch unknown.",
        "falsification_rule": "SenMayo fails if either primary directional AUROC is below 1.0.",
        "ambiguity_rule": "If both AUROCs are 1.0 but a rank exceeds 0.05, report ranking only, not distinguishable "
                          "from random panels. PLAN.md sha256 " + plan_sha256 + " governs.",
        "analysis_status": "exploratory"}


def freeze_request(plan_id: str, revision: str, plan_sha256: str, baseline: list[str], held_out: list[str]) -> dict:
    return {
        "plan_revision_id": plan_id,
        "method": {"owner_repository": "senescence-module-score", "revision": revision,
                   "version": "hrmec_validation evaluator 1",
                   "entry_point": "python -m senescore.hrmec_validation --download (clean checkout of the pinned revision)",
                   "preprocessing": "Pinned GEO HTSeq counts; approved unambiguous Ensembl-to-HGNC mapping; HTSeq summary "
                                    "rows excluded from the CPM denominator; log2(CPM+1); no filtering.",
                   "parameters": "seed 0; 20 bins; 5 controls; CDKN1A/CDKN2A blocked from controls; random panels seeds "
                                 "1000-1099; verdict rule and thresholds as in PLAN.md sha256 " + plan_sha256},
        "split": {"grouping_unit": "library", "development_group_ids": baseline, "final_test_group_ids": held_out},
        "primary_metric": {"name": PRIMARY_METRIC, "direction": "higher_is_better", "baseline": RANDOM_BASELINE},
        "results_inspected_before_freeze": False,
        "inspection_statement": "Before this freeze I inspected GEO metadata, file names/sizes/hashes and the "
                                "identifier column of the nine count files. Sixteen count lines of one early-passage "
                                "library (GSM4872128) were displayed incidentally. No score, contrast or "
                                "differential-expression statistic was calculated or viewed. The linked paper was read "
                                "for design only; it benchmarks its own signature against earlier ones in these "
                                "datasets and I did not read those results."}


def save(desk, record_type, title, content):
    return desk.research_record({"record_type": record_type, "blueprint_id": AREA, "title": title, "content": content})


def open_desk(workspace: Path):
    return regen_desk.Desk(workspace)


def do_freeze(args) -> int:
    repo = Path(args.senescence_repo)
    head, dirty = git_head(repo)
    if dirty:
        raise SystemExit("tracked files in the senescence checkout differ from HEAD; commit first")
    if args.method_revision and head != args.method_revision:
        raise SystemExit(f"checkout HEAD {head} is not the declared method revision {args.method_revision}")
    bundle = load_sources(repo)
    plan_sha256 = bundle["sources"]["snapshots"]["PLAN.md"]
    baseline, held_out = groups(bundle["samples"])
    workspace = Path(args.workspace)
    if workspace.exists():
        raise SystemExit(f"workspace already exists: {workspace}")
    desk = open_desk(workspace)
    try:
        q = save(desk, "question", "GSE160356 endothelial passage and etoposide question", question())
        card = save(desk, "dataset_card", "GSE160356 HRMEC count tables", dataset_card(bundle))
        p = save(desk, "analysis_plan", "GSE160356 prespecified control-bin check",
                 plan(q["revision_id"], card["revision_id"], plan_sha256))
        freeze = save(desk, "plan_freeze", "GSE160356 freeze before scoring",
                      freeze_request(p["revision_id"], head, plan_sha256, baseline, held_out))
        dossier = desk.export_archive(AREA)
    finally:
        desk.executor.shutdown(wait=True)
    state = {"schema_version": 1, "workspace_hint": workspace.name,
             "method_revision": head, "plan_sha256": plan_sha256,
             "question_revision_id": q["revision_id"], "dataset_card_revision_id": card["revision_id"],
             "plan_revision_id": p["revision_id"], "freeze_revision_id": freeze["revision_id"],
             "freeze_content_sha256": freeze["content_sha256"], "freeze_status": freeze["content"]["freeze_status"],
             "confirmatory_blockers": freeze["content"]["confirmatory_blockers"],
             "frozen_utc": freeze["content"]["frozen_utc"], "split_sha256": freeze["content"]["split"]["split_sha256"]}
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out = HERE / "derived"
    out.mkdir(exist_ok=True)
    (out / "dossier-before-run.zip").write_bytes(dossier)
    report = verify_dossier.verify_dossier(out / "dossier-before-run.zip", strict=True)
    (out / "verification-before-run.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({**state, "pre_run_dossier_verified": report["verified"], "lineage": report["scientific_lineage"]}, indent=2))
    return 0


def do_bind(args) -> int:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    repo = Path(args.senescence_repo)
    receipt_source = repo / "validation" / "GSE160356" / "evaluation_receipt.json"
    raw = receipt_source.read_bytes()
    receipt = json.loads(raw)
    head, dirty = git_head(repo)
    inputs = HERE / "inputs"
    inputs.mkdir(exist_ok=True)
    target = inputs / "evaluation_receipt.json"
    target.write_bytes(raw)
    (inputs / "PROVENANCE.json").write_text(json.dumps({
        "schema_version": 1,
        "description": "Byte-identical copy of the receipt written by senescore.hrmec_validation, vendored so the binding "
                       "can be re-checked from this repository alone.",
        "source_repository": "https://github.com/dylanstechmann/senescence-module-score",
        "source_path": "validation/GSE160356/evaluation_receipt.json",
        "receipt_code_revision": receipt["producer"]["code_revision"],
        "checkout_head_when_copied": head, "tracked_changes_when_copied": dirty,
        "receipt_sha256": hashlib.sha256(raw).hexdigest(), "receipt_bytes": len(raw)}, indent=2) + "\n", encoding="utf-8")
    workspace = Path(args.workspace)
    if not workspace.exists():
        raise SystemExit("workspace not found; the freeze must be bound in the Desk workspace that recorded it")
    desk = open_desk(workspace)
    try:
        freeze_id = state["freeze_revision_id"]
        event = desk.research_record({
            "record_type": "holdout_access", "blueprint_id": AREA, "title": "Single final evaluation of the sealed libraries",
            "content": {"freeze_revision_id": freeze_id, "scope": "final_test", "action": "evaluate",
                        "actor": "Claude (AI coding assistant), at the user's request",
                        "reference": f"senescence-module-score {receipt['producer']['code_revision']}",
                        "note": "One run of python -m senescore.hrmec_validation --download from a clean checkout of "
                                "the pinned revision; no re-run, no tuning.",
                        "expected_previous_event_sha256": None}})
        binding = desk.research_record({
            "record_type": "evaluation_binding", "blueprint_id": AREA, "title": "Receipt of the single final evaluation",
            "content": {"freeze_revision_id": freeze_id, "adapter": "evaluation-receipt/1", "stage": "final_test",
                        "receipt_path": str(target)}})
        record = next(item for item in desk.research_record_state(AREA) if item["revision_id"] == freeze_id)
        assessment = record["freeze_assessment"]
        dossier = desk.export_archive(AREA)
    finally:
        desk.executor.shutdown(wait=True)
    out = HERE / "derived"
    out.mkdir(exist_ok=True)
    (out / "dossier.zip").write_bytes(dossier)
    report = verify_dossier.verify_dossier(out / "dossier.zip", strict=True)
    (out / "verification_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = {
        "freeze_revision_id": freeze_id, "freeze_status": record["content"]["freeze_status"],
        "confirmatory_blockers": record["content"]["confirmatory_blockers"],
        "binding_status": binding["content"]["binding_status"],
        "binding_checks": {item["id"]: item["status"] for item in binding["content"]["checks"]},
        "claim_status": assessment["claim_status"],
        "record_supports_confirmatory_claim": assessment["record_supports_confirmatory_claim"],
        "violations": [item["id"] for item in assessment["violations"]],
        "receipt_sha256": binding["content"]["receipt"]["sha256"], "ledger_events": assessment["ledger"]["n_events"],
        "dossier_verification": {key: report[key] for key in ("bytes_verified", "verified", "scientific_lineage",
                                                              "scientific_review", "reproduction")}}
    (out / "binding_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("freeze", "bind"):
        command = sub.add_parser(name)
        command.add_argument("--workspace", required=True, help="Desk workspace directory (new for freeze)")
        command.add_argument("--senescence-repo", required=True, help="checkout of senescence-module-score")
    sub.choices["freeze"].add_argument("--method-revision", default="", help="expected 40-hex HEAD of the checkout")
    args = parser.parse_args(argv)
    return do_freeze(args) if args.command == "freeze" else do_bind(args)


if __name__ == "__main__":
    raise SystemExit(main())
