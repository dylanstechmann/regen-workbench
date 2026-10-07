#!/usr/bin/env python3
"""Worked example: freeze, ledger and receipt binding on a real development receipt.

Part A uses the committed NIST iPSC regression receipt from regen-benchmark-kit
(real data, an existing *development* benchmark). Its results existed before any
plan was written here, so the freeze is attested as retrospective and can never be
confirmatory. The script asks two questions of that receipt:

1. Does it agree with the plan that describes it?  (it does, retrospectively)
2. Could it serve as a final-test evaluation if one well were sealed?  (no: leave-one-
   well-out trains on every well, so any sealed well was used in development)

Part B is a SYNTHETIC fixture, not a measurement. It walks the clean prospective path
with a made-up receipt so the "record supports a confirmatory claim" state can be seen
once. No biology is implied by anything in Part B.

Nothing here runs a model. Every status is computed by ResearchDesk from stored
records and one bounded read of each receipt.

Usage:  python run_example.py --out <new directory>
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import frozen_evaluation as fe  # noqa: E402
import regen  # noqa: E402
import regen_desk  # noqa: E402
import verify_dossier  # noqa: E402

AREA = "tissues"
NIST_RECEIPT = HERE / "inputs" / "nist_ipsc_regression_metrics.json"
FEATURE_TABLE_SHA256 = "e055bf31bc6d08594b9010625a779d027821c2333cb369e7247c011c81158645"
KIT_COMMIT = "b0087c78ac3474aecdb6e5cc276d6ba79921df5d"


def question():
    return {
        "question": "Can nine fixed phase-image descriptors predict nuclear-mask area fraction when a "
                    "whole source well is withheld?",
        "scope": "Three NIST iPSC source wells (one per seeding density); 64 non-overlapping 512x512 tiles each.",
        "claim_boundary": "Associations within these three wells only. Density and well are confounded; "
                          "there is one well per condition; no interval is estimable from three groups.",
        "hypotheses": [
            {"id": "h1", "prediction": "Fixed Ridge has lower equal-well MAE than the training-fold mean.",
             "falsifier": "Ridge does not beat the mean baseline in a withheld well."},
            {"id": "h2", "prediction": "Apparent skill is specific to density and degrades at the extreme-density well.",
             "falsifier": "Error does not rise for the extreme-density well."}],
        "source_refs": [{"label": "NIST mds2-2960 (Asmar et al.)", "url": "https://doi.org/10.18434/mds2-2960"},
                        {"label": "Asmar et al. 2024, PLOS ONE", "url": "https://doi.org/10.1371/journal.pone.0298446"}]}


def dataset_card():
    return {
        "citation": "Derived feature table from NIST mds2-2960 (Asmar et al., v1.1.0), built in "
                    "regen-benchmark-kit/examples/nist_ipsc.",
        "source_url": "https://doi.org/10.18434/mds2-2960", "access_status": "public_open",
        "license": "NIST non-SRD data terms (https://www.nist.gov/open/license); see SOURCE_NOTICE.md",
        "scope": "Nine fixed descriptors and a fluorescence-derived nuclear-area target for 192 tiles.",
        "species_or_model": "human iPSC colonies, phase-contrast imaging",
        "stage_or_interval": "Three seeding-density conditions; one well each.",
        "data_granularity": "individual_level",
        "files": [{"path": "regen-benchmark-kit/examples/nist_ipsc/data/features.csv", "format": "csv",
                   "sha256": FEATURE_TABLE_SHA256, "rows": 192}],
        "unit_hierarchy": [
            {"level": "source well", "kind": "well; one per seeding-density condition",
             "source_field": "source_well", "identity_status": "reported"},
            {"level": "tile", "kind": "512x512 pixel tile", "source_field": "sample_id",
             "identity_status": "reported"}],
        "independent_unit_level": "source well",
        "observed_quantities": [{"endpoint": "nuclear mask area fraction", "unit": "fraction of tile area",
                                 "measurement_role": "target; reference mask from automated fluorescence processing",
                                 "calibration_status": "not_applicable"}],
        "groups": [{"label": "source well", "source_fields": ["source_well"], "role": "holdout grouping"}],
        "missingness": "No missing feature values. Some tiles have empty nuclear masks (4 of 64 in "
                       "training_low, 2 in training_medium, 0 in training_high) and are retained.",
        "exclusions": "Right and bottom 256 pixels excluded by the tile grid; 64 tiles per well chosen by "
                      "seeded random selection."}


def plan(question_id, card_id):
    return {
        "question_revision_id": question_id, "dataset_revision_ids": [card_id],
        "estimand": "Equal-well MAE (percentage points of tile area) of fixed Ridge against the "
                    "training-fold mean when each source well is withheld in turn.",
        "primary_outcome": {"endpoint": "nuclear mask area fraction", "unit": "fraction of tile area",
                            "timepoint": "single acquisition", "comparator": "training-fold mean baseline",
                            "independent_unit": "source well"},
        "alternatives": [{"hypothesis_id": "h1", "prediction": "Ridge MAE below the baseline in every withheld well."},
                         {"hypothesis_id": "h2", "prediction": "Error is largest for the extreme-density well."}],
        "baseline": "Training-fold mean, fit independently in each fold.",
        "split": "Leave one source well out; three folds.",
        "uncertainty": "None estimated: three groups cannot support a group interval.",
        "missingness_rule": "Retain empty-mask tiles; report them.",
        "confounding": "Seeding density and source well are fully confounded.",
        "falsification_rule": "Ridge fails to beat the baseline in at least one withheld well.",
        "ambiguity_rule": "If only the extreme-density well disagrees, report density-specific skill, not a failure.",
        "analysis_status": "exploratory"}


def method(version="0.2.0", revision=KIT_COMMIT):
    return {"owner_repository": "regen-benchmark-kit", "revision": revision, "version": version,
            "entry_point": "regenbench regress examples/nist_ipsc/data/features.csv "
                           "--target reference_nuclear_fraction --group-by source_well --seed 0",
            "preprocessing": "Fold-local standardization inside the pipeline; no feature selection.",
            "parameters": "seed 0; Ridge alpha 1.0; fixed histogram-gradient-boosting settings; no search."}


def summarize(desk, freeze):
    record = next(item for item in desk.research_record_state(AREA) if item["revision_id"] == freeze["revision_id"])
    assessment = record["freeze_assessment"]
    return {
        "freeze_revision_id": record["revision_id"],
        "freeze_status": record["content"]["freeze_status"],
        "confirmatory_blockers": record["content"]["confirmatory_blockers"],
        "split_sha256": record["content"]["split"]["split_sha256"],
        "pins_resolve": record["pins_resolve"]["all_resolve"],
        "claim_status": assessment["claim_status"],
        "record_supports_confirmatory_claim": assessment["record_supports_confirmatory_claim"],
        "violations": [item["id"] for item in assessment["violations"]],
        "ledger_events": assessment["ledger"]["n_events"],
        "bindings": assessment["bindings"]}


def checks(binding):
    return {item["id"]: item["status"] for item in binding["content"]["checks"]}


def save(desk, record_type, title, content):
    return desk.research_record({"record_type": record_type, "blueprint_id": AREA, "title": title,
                                 "content": content})


def part_a(desk):
    """The real, retrospective NIST development receipt."""
    q = save(desk, "question", "NIST well-holdout question", question())
    card = save(desk, "dataset_card", "NIST derived feature table", dataset_card())
    p = save(desk, "analysis_plan", "Retrospective description of the NIST benchmark",
             plan(q["revision_id"], card["revision_id"]))
    statement = ("The NIST regression receipt (regen-benchmark-kit, first committed 2026-09-24) existed "
                 "before this plan was written. This freeze documents an existing development benchmark "
                 "and is retrospective by construction.")

    # A1: the plan as it was actually run: all three wells are development groups.
    as_run = save(desk, "plan_freeze", "As run: three development wells", {
        "plan_revision_id": p["revision_id"], "method": method(),
        "split": {"grouping_unit": "source well",
                  "development_group_ids": ["training_low", "training_medium", "training_high"],
                  "final_test_group_ids": []},
        "primary_metric": {"name": "equal_group_mae", "direction": "lower_is_better", "baseline": "mean_baseline"},
        "results_inspected_before_freeze": True, "inspection_statement": statement})
    bound = save(desk, "evaluation_binding", "NIST receipt, development stage", {
        "freeze_revision_id": as_run["revision_id"], "adapter": "regenbench-metrics/1", "stage": "development",
        "receipt_path": str(NIST_RECEIPT)})

    # A2: what-if. Seal the high-density well, then ask whether this receipt could be its evaluation.
    sealed = save(desk, "plan_freeze", "What-if: seal training_high", {
        "plan_revision_id": p["revision_id"], "method": method(),
        "split": {"grouping_unit": "source well",
                  "development_group_ids": ["training_low", "training_medium"],
                  "final_test_group_ids": ["training_high"]},
        "primary_metric": {"name": "equal_group_mae", "direction": "lower_is_better", "baseline": "mean_baseline"},
        "results_inspected_before_freeze": True,
        "inspection_statement": statement + " This split was written afterwards, as a what-if."})
    as_development = save(desk, "evaluation_binding", "NIST receipt as a development run", {
        "freeze_revision_id": sealed["revision_id"], "adapter": "regenbench-metrics/1", "stage": "development",
        "receipt_path": str(NIST_RECEIPT)})
    as_final = save(desk, "evaluation_binding", "NIST receipt as the final-test evaluation", {
        "freeze_revision_id": sealed["revision_id"], "adapter": "regenbench-metrics/1", "stage": "final_test",
        "receipt_path": str(NIST_RECEIPT)})
    return {
        "receipt": {"sha256": bound["content"]["receipt"]["sha256"], "bytes": bound["content"]["receipt"]["bytes"],
                    "feature_table_sha256": FEATURE_TABLE_SHA256},
        "as_run": {"freeze": summarize(desk, as_run), "binding_status": bound["content"]["binding_status"],
                   "checks": checks(bound)},
        "what_if_sealed_training_high": {
            "freeze": summarize(desk, sealed),
            "bound_as_development_run": {"binding_status": as_development["content"]["binding_status"],
                                         "checks": checks(as_development),
                                         "final_test_groups_in_training": as_development["content"]["final_test_groups_in_training"],
                                         "final_test_groups_evaluated": as_development["content"]["final_test_groups_evaluated"]},
            "bound_as_final_test_run": {"binding_status": as_final["content"]["binding_status"],
                                        "checks": checks(as_final),
                                        "detail": [item["detail"] for item in as_final["content"]["checks"]
                                                   if item["status"] == "fail"]}}}


def synthetic_receipt(freeze, *, created_utc):
    return {"schema": "regen-workbench/evaluation-receipt/1",
            "producer": {"tool": "synthetic-fixture", "version": "0.0", "code_revision": "0" * 40},
            "created_utc": created_utc, "input_sha256": ["1" * 64],
            "folds": [{"train_groups": ["synthetic-a", "synthetic-b"], "test_groups": ["synthetic-c"]}],
            "model_names": ["mean_baseline", "synthetic_model"], "metric_names": ["equal_group_mae"],
            "reported_leakage": [{"id": "unblocked_overlap:batch", "count": 0}]}


def part_b(desk, scratch):
    """SYNTHETIC fixture: the clean prospective path, shown once. Not a measurement."""
    card_content = dataset_card()
    card_content.update(citation="SYNTHETIC FIXTURE - not a measurement.", source_url="",
                        access_status="synthetic_example", license="not applicable",
                        scope="Made-up groups for the procedure demonstration only.",
                        files=[{"path": "synthetic-table.csv", "format": "csv", "sha256": "1" * 64, "rows": 3}])
    q = save(desk, "question", "SYNTHETIC procedure question", question())
    card = save(desk, "dataset_card", "SYNTHETIC table", card_content)
    p = save(desk, "analysis_plan", "SYNTHETIC confirmatory plan",
             {**plan(q["revision_id"], card["revision_id"]), "analysis_status": "proposed_confirmatory"})
    frozen = save(desk, "plan_freeze", "SYNTHETIC prospective freeze", {
        "plan_revision_id": p["revision_id"], "method": method("0.0", "0" * 40),
        "split": {"grouping_unit": "source well", "development_group_ids": ["synthetic-a", "synthetic-b"],
                  "final_test_group_ids": ["synthetic-c"]},
        "primary_metric": {"name": "equal_group_mae", "direction": "lower_is_better", "baseline": "mean_baseline"},
        "results_inspected_before_freeze": False, "inspection_statement": ""})
    for scope, action, note in (("development", "tune", "synthetic development tuning"),
                                ("final_test", "evaluate", "single synthetic final evaluation")):
        save(desk, "holdout_access", "Synthetic access", {
            "freeze_revision_id": frozen["revision_id"], "scope": scope, "action": action,
            "actor": "synthetic example script", "reference": "", "note": note})
    receipt_dir = regen.DATA / "receipts"  # receipts must live under data/, studies/ or projects/
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / "synthetic_receipt.json"
    receipt_path.write_text(json.dumps(synthetic_receipt(frozen, created_utc="2999-01-01T00:00:00+00:00")),
                            encoding="utf-8")
    binding = save(desk, "evaluation_binding", "SYNTHETIC final-test receipt", {
        "freeze_revision_id": frozen["revision_id"], "adapter": "evaluation-receipt/1", "stage": "final_test",
        "receipt_path": str(receipt_path)})
    return {"label": "SYNTHETIC FIXTURE - made-up groups and receipt; demonstrates the procedure, not a result",
            "freeze": summarize(desk, frozen), "binding_status": binding["content"]["binding_status"],
            "checks": checks(binding)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="new output directory")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        parser.error(f"output already exists: {out}")
    out.mkdir(parents=True)
    # Isolate every write in a throwaway directory: the example never touches the user's real Desk
    # workspace or data directory, and only the inspectable artifacts are kept in --out.
    saved_paths = (regen.DATA, regen.CACHE, regen.PROV)
    with tempfile.TemporaryDirectory(prefix="frozen-example-") as temporary:
        scratch = Path(temporary)
        regen.DATA, regen.CACHE, regen.PROV = scratch / "data", scratch / "cache", scratch / "provenance"
        regen.DATA.mkdir()
        desk = regen_desk.Desk(scratch / "desk")
        try:
            result = {"schema_version": 1, "generated_utc": regen.now(), "python": sys.version.split()[0],
                      "workbench": regen_desk.workbench_revision(),
                      "part_a_real_nist_development_receipt": part_a(desk),
                      "part_b_synthetic_clean_path": part_b(desk, scratch)}
            archive = out / "dossier.zip"
            archive.write_bytes(desk.export_archive(AREA))
            shutil.copyfile(regen.DATA / "receipts" / "synthetic_receipt.json", out / "synthetic_receipt.json")
        finally:
            desk.executor.shutdown(wait=True)
            regen.DATA, regen.CACHE, regen.PROV = saved_paths

    report = verify_dossier.verify_dossier(archive, strict=True)
    result["dossier_verification"] = {key: report[key] for key in (
        "bytes_verified", "verified", "ancestry_resolved", "scientific_lineage", "scientific_review",
        "reproduction")}
    result["dossier_verification"]["lineage_freezes"] = report["lineage"]["freezes"]
    with zipfile.ZipFile(archive) as bundle:
        result["dossier_members"] = len(bundle.namelist())
    (out / "verification_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "workflow_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    a, b = result["part_a_real_nist_development_receipt"], result["part_b_synthetic_clean_path"]
    what_if = a["what_if_sealed_training_high"]
    lines = [
        "# Frozen-evaluation worked example", "",
        f"Generated {result['generated_utc']} by `run_example.py` with Python {result['python']} at workbench "
        f"revision `{result['workbench']['revision'][:12]}`"
        f"{' (uncommitted changes were present)' if result['workbench'].get('uncommitted_changes') else ''}.", "",
        "## Part A - the committed NIST development receipt (real data, retrospective)", "",
        f"Receipt SHA-256 `{a['receipt']['sha256']}` ({a['receipt']['bytes']} bytes); feature table "
        f"`{FEATURE_TABLE_SHA256}`.", "",
        "| Question | Result |", "|---|---|",
        f"| Does the receipt agree with the plan that describes it? | {a['as_run']['binding_status']} "
        f"(freeze `{a['as_run']['freeze']['freeze_status']}`, claim state `{a['as_run']['freeze']['claim_status']}`) |",
        f"| Could it be the evaluation of a sealed `training_high` well, as a development run? | "
        f"{what_if['bound_as_development_run']['binding_status']} |",
        f"| ...or as the final-test evaluation? | {what_if['bound_as_final_test_run']['binding_status']} |",
        f"| Claim state of the what-if freeze | `{what_if['freeze']['claim_status']}` "
        f"({', '.join(what_if['freeze']['violations']) or 'no violations'}) |", "",
        "Leave-one-well-out trains on every well, so the receipt cannot be a confirmatory evaluation of any one "
        "of them. The regen-benchmark-kit report says the same in prose (\"Repeated tuning against these folds "
        "turns them into development data\"); here the Desk derives it from the receipt's fold assignments.", "",
        "## Part B - SYNTHETIC clean path (not a measurement)", "",
        f"{b['label']}. Freeze `{b['freeze']['freeze_status']}`, binding `{b['binding_status']}`, claim state "
        f"`{b['freeze']['claim_status']}`; the record supports a confirmatory claim: "
        f"{b['freeze']['record_supports_confirmatory_claim']}. That sentence is about the recorded procedure only.", "",
        "## Dossier verification", "",
        f"`verify_dossier.py --strict` on `dossier.zip`: bytes verified {report['bytes_verified']}, "
        f"scientific lineage `{report['scientific_lineage']}`, scientific review "
        f"`{report['scientific_review']}`, reproduction `{report['reproduction']}`.", "",
        "## What this does not show", "",
        "- It runs no model and measures no biology. Part A re-reads a receipt that already existed.",
        "- The freeze clock, the `results inspected` answer and ledger actors are self-reported.",
        "- Three wells cannot support a group interval, and density is confounded with well.", ""]
    (out / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"part_a": {"as_run": a["as_run"]["binding_status"],
                                 "sealed_as_development": what_if["bound_as_development_run"]["binding_status"],
                                 "sealed_as_final_test": what_if["bound_as_final_test_run"]["binding_status"],
                                 "what_if_claim": what_if["freeze"]["claim_status"]},
                      "part_b": {"binding": b["binding_status"], "claim": b["freeze"]["claim_status"],
                                 "supported": b["freeze"]["record_supports_confirmatory_claim"]},
                      "dossier": result["dossier_verification"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
