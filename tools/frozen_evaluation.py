"""Frozen evaluation plans for ResearchDesk: pin, bind and audit.

An analysis plan says what a study intends to test. It does not, by itself, stop
anyone (a person or a coding agent) from choosing a split after seeing results,
re-tuning against a held-out group, or describing an exploratory result as a
confirmation. This module is the method-neutral core behind three append-only
record types that make those procedural facts inspectable:

* ``plan_freeze``       pins one exact plan revision, the question and dataset-card
                        revisions it links, the method revision, and the
                        development / final-test split before a run exists.
* ``holdout_access``    a hash-chained ledger of every recorded touch of the
                        development or final-test groups.
* ``evaluation_binding`` checks one sibling-repository receipt against a freeze
                        (inputs, split, leakage, method revision, timing).

What a clean record does and does not mean
------------------------------------------
Everything here is procedural. A freeze time is the Desk's clock: it shows when the
plan was pinned, not that nobody looked at data earlier. ``results_inspected_before_
freeze`` and the ledger ``actor`` are self-reported and unauthenticated. A binding
shows that a receipt agrees with a plan; it does not show that the analysis was
correct, that the receipt is genuine, or that any biological claim follows. "The record
supports a confirmatory claim" means only that the recorded procedure was followed.

The module reads and hashes bytes it is handed. It never opens a path, runs a
command, or imports a sibling package, so nothing named in a record is executed.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

SHA256_HEX = re.compile(r"[0-9a-f]{64}")
GIT_COMMIT = re.compile(r"[0-9a-f]{40}")
REVISION_ID = re.compile(r"[0-9a-f]{32}")

FROZEN_RECORD_TYPES = ("plan_freeze", "holdout_access", "evaluation_binding")
FREEZE_STATUSES = ("exploratory", "confirmatory", "retrospective")
ACCESS_SCOPES = ("development", "final_test")
ACCESS_ACTIONS = ("evaluate", "tune", "inspect_labels", "export_predictions")
BINDING_STAGES = ("development", "final_test")
BINDING_STATUSES = ("bound_prospective", "bound_retrospective", "bound_timing_unverified",
                    "mismatch", "unverifiable")
MAX_GROUP_IDS = 500
MAX_RECEIPT_BYTES = 4 * 1024 * 1024

FREEZE_LIMITS = (
    "The freeze time is the ResearchDesk clock. It shows when this plan was pinned, not that no "
    "one inspected the data earlier; 'results_inspected_before_freeze' is a self-report.",
    "Pinning a plan does not make it a good plan, and a frozen split is only as independent as the "
    "grouping unit it names.",
    "A freeze records intent and inputs. It does not run, verify or review any analysis.",
)
CLAIM_LIMITS = (
    "'The record supports a confirmatory claim' means the recorded procedure was followed. It does "
    "not establish that the analysis was correct, that a receipt is genuine, or that a biological "
    "effect exists.",
    "Ledger actors and the 'results inspected' attestation are self-reported and unauthenticated; "
    "access that was never recorded cannot be detected, except where a bound receipt reveals it.",
    "A held-out group that has been evaluated more than once, or tuned against, is development "
    "data from that point on. The record keeps that fact visible rather than resetting it.",
)


class FrozenEvaluationError(ValueError):
    """A freeze, ledger event, receipt or binding failed its contract."""


def record_hash(record_type, title, content):
    """Content hash shared with ResearchDesk research revisions."""
    canonical = json.dumps({"record_type": record_type, "title": title, "content": content},
                           ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical_sha256(value):
    return sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                                   allow_nan=False).encode("utf-8"))


# --------------------------------------------------------------------------- validators

def _text(value, label, maximum, *, empty=False):
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise FrozenEvaluationError(
            f"{label} must be {'text' if empty else 'nonempty text'} of at most {maximum} characters")
    return value.strip()


def _object(value, required, optional, label):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise FrozenEvaluationError(f"{label} must contain exactly its documented fields")
    return value


def _choice(value, choices, label):
    if not isinstance(value, str) or value not in choices:
        raise FrozenEvaluationError(f"Unknown {label}")
    return value


def _id_list(value, label, *, minimum):
    if (not isinstance(value, list) or not minimum <= len(value) <= MAX_GROUP_IDS
            or not all(isinstance(item, str) and 1 <= len(item.strip()) <= 200 for item in value)):
        raise FrozenEvaluationError(
            f"{label} must contain {minimum}-{MAX_GROUP_IDS} group identifiers of at most 200 characters")
    cleaned = [item.strip() for item in value]
    if len(set(cleaned)) != len(cleaned):
        raise FrozenEvaluationError(f"{label} must not repeat an identifier")
    return sorted(cleaned)


def _utc(value):
    """Timezone-aware UTC datetime from an ISO-8601 string, or None when unusable."""
    if not isinstance(value, str) or not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment.astimezone(timezone.utc) if moment.tzinfo is not None else None


# --------------------------------------------------------------------------- freeze

def validate_freeze_request(content):
    """Validate what a person supplies; the server adds pins, status and clocks."""
    value = _object(content, {"plan_revision_id", "method", "split", "primary_metric",
                              "results_inspected_before_freeze", "inspection_statement"}, set(),
                    "Freeze request")
    plan_id = _text(value["plan_revision_id"], "Plan revision ID", 64)
    method = _object(value["method"], {"owner_repository", "revision", "version", "entry_point",
                                       "preprocessing", "parameters"}, set(), "Method")
    revision = _text(method["revision"], "Method revision", 64, empty=True)
    if revision and not GIT_COMMIT.fullmatch(revision):
        raise FrozenEvaluationError("Method revision must be a 40-character lower-case git commit or empty")
    method = {
        "owner_repository": _text(method["owner_repository"], "Method owner repository", 200),
        "revision": revision,
        "version": _text(method["version"], "Method version", 100, empty=True),
        "entry_point": _text(method["entry_point"], "Method entry point", 1000),
        "preprocessing": _text(method["preprocessing"], "Preprocessing", 2000),
        "parameters": _text(method["parameters"], "Fixed parameters and seeds", 2000),
    }
    split = _object(value["split"], {"grouping_unit", "development_group_ids", "final_test_group_ids"},
                    set(), "Split")
    development = _id_list(split["development_group_ids"], "development_group_ids", minimum=1)
    final = _id_list(split["final_test_group_ids"], "final_test_group_ids", minimum=0)
    overlap = sorted(set(development) & set(final))
    if overlap:
        raise FrozenEvaluationError(
            "A group cannot be both development and final-test: " + ", ".join(overlap[:10]))
    split = {"grouping_unit": _text(split["grouping_unit"], "Split grouping unit", 300),
             "development_group_ids": development, "final_test_group_ids": final}
    metric = _object(value["primary_metric"], {"name", "direction", "baseline"}, set(), "Primary metric")
    metric = {"name": _text(metric["name"], "Primary metric name", 200),
              "direction": _choice(metric["direction"], {"lower_is_better", "higher_is_better"},
                                   "metric direction"),
              "baseline": _text(metric["baseline"], "Baseline name", 200)}
    inspected = value["results_inspected_before_freeze"]
    if not isinstance(inspected, bool):
        raise FrozenEvaluationError("results_inspected_before_freeze must be true or false")
    statement = _text(value["inspection_statement"], "Inspection statement", 2000, empty=not inspected)
    return {"plan_revision_id": plan_id, "method": method, "split": split, "primary_metric": metric,
            "results_inspected_before_freeze": inspected, "inspection_statement": statement}


def _checked(record, label):
    try:
        recomputed = record_hash(record["record_type"], record["title"], record["content"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FrozenEvaluationError(f"The {label} revision could not be hashed") from exc
    if recomputed != record.get("content_sha256"):
        raise FrozenEvaluationError(f"The {label} revision failed its content hash check")
    return record


def build_freeze_content(request, *, plan, question, datasets, frozen_utc):
    """Expand a validated request into the stored freeze content.

    ``plan``, ``question`` and ``datasets`` are stored research records (with
    ``is_current_revision`` and ``stale_dependency_revision_ids`` on the plan). The
    server, not the client, supplies every pin and the derived status.
    """
    plan = _checked(plan, "plan")
    if plan.get("record_type") != "analysis_plan":
        raise FrozenEvaluationError("Only an analysis-plan revision can be frozen")
    if not plan.get("is_current_revision"):
        raise FrozenEvaluationError(
            "Freeze the current plan revision; this one has been superseded by a newer revision")
    if plan.get("stale_dependency_revision_ids"):
        raise FrozenEvaluationError(
            "This plan links question or dataset-card revisions that were superseded; create a new plan "
            "revision against the current inputs before freezing")
    question = _checked(question, "question")
    expected_datasets = set(plan["content"]["dataset_revision_ids"])
    if {item["revision_id"] for item in datasets} != expected_datasets:
        raise FrozenEvaluationError("Every dataset-card revision linked by the plan must be pinned")
    pins_datasets = []
    for card in sorted((_checked(item, "dataset-card") for item in datasets),
                       key=lambda item: item["revision_id"]):
        body = card["content"]
        pins_datasets.append({
            "revision_id": card["revision_id"], "content_sha256": card["content_sha256"],
            "independent_unit_level": body["independent_unit_level"],
            "unit_levels_reported": sorted(level["level"] for level in body["unit_hierarchy"]
                                           if level["identity_status"] == "reported"),
            "files": [{"path": item["path"], "sha256": item["sha256"], "rows": item["rows"]}
                      for item in body["files"]],
        })
    pins = {"plan": {"revision_id": plan["revision_id"], "content_sha256": plan["content_sha256"],
                     "analysis_status": plan["content"]["analysis_status"]},
            "question": {"revision_id": question["revision_id"], "content_sha256": question["content_sha256"]},
            "datasets": pins_datasets}
    split = dict(request["split"])
    split["split_sha256"] = _canonical_sha256({key: split[key] for key in
                                               ("grouping_unit", "development_group_ids",
                                                "final_test_group_ids")})

    blockers = []
    if request["results_inspected_before_freeze"]:
        blockers.append("Results were inspected before the freeze, so this plan cannot be confirmatory.")
    if not split["final_test_group_ids"]:
        blockers.append("No final-test groups are sealed.")
    if any(item["sha256"] is None for card in pins_datasets for item in card["files"]):
        blockers.append("At least one pinned dataset file has no SHA-256.")
    if not request["method"]["revision"]:
        blockers.append("The method revision is not pinned to a 40-character git commit.")
    unit = split["grouping_unit"]
    if not any(unit == card["independent_unit_level"] and unit in card["unit_levels_reported"]
               for card in pins_datasets):
        blockers.append("The split grouping unit is not an identified independent-unit level of any "
                        "pinned dataset card.")

    if request["results_inspected_before_freeze"]:
        status = "retrospective"
    elif pins["plan"]["analysis_status"] == "proposed_confirmatory" and not blockers:
        status = "confirmatory"
    else:
        status = "exploratory"
    return {
        "plan_revision_id": plan["revision_id"], "pins": pins, "method": request["method"],
        "split": split, "primary_metric": request["primary_metric"],
        "results_inspected_before_freeze": request["results_inspected_before_freeze"],
        "inspection_statement": request["inspection_statement"],
        "freeze_status": status,
        "confirmatory_blockers": blockers,
        "frozen_utc": frozen_utc, "limitations": list(FREEZE_LIMITS),
    }


def validate_freeze_content(content):
    """Structural check of a stored freeze; used before a record is appended."""
    value = _object(content, {"plan_revision_id", "pins", "method", "split", "primary_metric",
                              "results_inspected_before_freeze", "inspection_statement",
                              "freeze_status", "confirmatory_blockers", "frozen_utc", "limitations"},
                    set(), "Freeze content")
    _choice(value["freeze_status"], FREEZE_STATUSES, "freeze status")
    if not REVISION_ID.fullmatch(value["plan_revision_id"]):
        raise FrozenEvaluationError("Freeze plan_revision_id must be a 32-character revision identifier")
    if not SHA256_HEX.fullmatch(value["split"].get("split_sha256", "")):
        raise FrozenEvaluationError("Freeze split must carry its SHA-256")
    if _utc(value["frozen_utc"]) is None:
        raise FrozenEvaluationError("Freeze frozen_utc must be a timezone-aware ISO-8601 time")
    return value


# --------------------------------------------------------------------------- access ledger

def validate_access_request(content):
    value = _object(content, {"freeze_revision_id", "scope", "action", "actor", "reference", "note"},
                    {"expected_previous_event_sha256"}, "Access event")
    expected = value.get("expected_previous_event_sha256")
    if expected is not None and (not isinstance(expected, str) or not SHA256_HEX.fullmatch(expected)):
        raise FrozenEvaluationError("expected_previous_event_sha256 must be a SHA-256 or null")
    return {
        "freeze_revision_id": _text(value["freeze_revision_id"], "Freeze revision ID", 64),
        "scope": _choice(value["scope"], ACCESS_SCOPES, "access scope"),
        "action": _choice(value["action"], ACCESS_ACTIONS, "access action"),
        "actor": _text(value["actor"], "Actor", 200),
        "reference": _text(value["reference"], "Reference", 1000, empty=True),
        "note": _text(value["note"], "Note", 2000, empty=True),
        "expected_previous_event_sha256": expected,
    }


def ledger_problems(freeze, events):
    """Chain defects for one freeze's events; empty when the ledger is intact."""
    problems, previous = [], None
    ordered = sorted(events, key=lambda item: item["content"].get("sequence", 0))
    for expected_sequence, event in enumerate(ordered, start=1):
        body = event["content"]
        if event.get("content_integrity_valid") is False:
            problems.append(f"event {expected_sequence} failed its content hash check")
        if body.get("sequence") != expected_sequence:
            problems.append(f"event sequence {body.get('sequence')} found where {expected_sequence} was expected")
        if body.get("previous_event_sha256") != previous:
            problems.append(f"event {expected_sequence} does not follow the previous event's hash")
        if body.get("freeze_content_sha256") != freeze["content_sha256"]:
            problems.append(f"event {expected_sequence} is bound to a different freeze content")
        previous = event.get("content_sha256")
    return problems


def build_access_content(request, *, freeze, events, recorded_utc):
    if freeze.get("record_type") != "plan_freeze":
        raise FrozenEvaluationError("Access events attach to a plan freeze")
    _checked(freeze, "freeze")
    problems = ledger_problems(freeze, events)
    if problems:
        raise FrozenEvaluationError(
            "The access ledger failed its integrity check, so no event was appended: " + "; ".join(problems[:3]))
    if request["scope"] == "final_test" and not freeze["content"]["split"]["final_test_group_ids"]:
        raise FrozenEvaluationError(
            "This freeze seals no final-test groups, so a final-test access cannot be recorded against it")
    ordered = sorted(events, key=lambda item: item["content"]["sequence"])
    head = ordered[-1]["content_sha256"] if ordered else None
    if request["expected_previous_event_sha256"] is not None and request["expected_previous_event_sha256"] != head:
        raise FrozenEvaluationError("The ledger head changed since it was read; reload and try again")
    return {
        "freeze_revision_id": freeze["revision_id"], "freeze_content_sha256": freeze["content_sha256"],
        "sequence": len(ordered) + 1, "previous_event_sha256": head,
        "scope": request["scope"], "action": request["action"], "actor": request["actor"],
        "reference": request["reference"], "note": request["note"], "recorded_utc": recorded_utc,
    }


# --------------------------------------------------------------------------- receipts

def parse_receipt_json(raw):
    """Parse bounded receipt bytes, rejecting duplicate keys and non-finite numbers."""
    if not isinstance(raw, (bytes, bytearray)) or not raw or len(raw) > MAX_RECEIPT_BYTES:
        raise FrozenEvaluationError(f"A receipt must be 1 byte to {MAX_RECEIPT_BYTES} bytes")

    def unique(pairs):
        keys = [key for key, _ in pairs]
        if len(set(keys)) != len(keys):
            raise FrozenEvaluationError("Receipt JSON must not repeat an object key")
        return dict(pairs)

    def reject(constant):
        raise FrozenEvaluationError(f"Receipt JSON must not contain {constant}")

    try:
        value = json.loads(bytes(raw).decode("utf-8-sig"), object_pairs_hook=unique, parse_constant=reject)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FrozenEvaluationError("The receipt is not UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise FrozenEvaluationError("A receipt must be a JSON object")
    return value


def _group_label(metadata, columns):
    """Readable group name from a regenbench group_metadata entry."""
    parts = []
    for column in columns:
        values = metadata.get(column)
        if not isinstance(values, list) or not values or not all(isinstance(v, str) for v in values):
            raise FrozenEvaluationError("A group is missing a recorded value for its grouping column")
        parts.append(",".join(values))
    return parts[0] if len(columns) == 1 else ";".join(f"{c}={p}" for c, p in zip(columns, parts))


def adapt_regenbench_metrics(receipt):
    """Normalize a ``regenbench`` run/regress ``metrics.json`` receipt.

    Group names are the source-column values recorded in ``group_metadata`` (for one
    grouping column, the plain value), so a frozen group identifier can be written
    from the original data rather than from the report's pseudonyms.
    """
    required = ("task", "dataset_sha256", "group_metadata", "configuration", "folds", "models", "environment")
    if any(key not in receipt for key in required):
        raise FrozenEvaluationError("Not a regenbench metrics report: required fields are missing")
    columns = receipt["configuration"].get("group_by")
    if (not isinstance(columns, list) or not columns
            or not all(isinstance(column, str) for column in columns)):
        raise FrozenEvaluationError("The report does not record its grouping columns")
    if not SHA256_HEX.fullmatch(str(receipt["dataset_sha256"])):
        raise FrozenEvaluationError("The report's dataset_sha256 is not a SHA-256")
    labels = {pseudonym: _group_label(meta, columns) for pseudonym, meta in receipt["group_metadata"].items()}

    def mapped(names):
        try:
            return sorted(labels[name] for name in names)
        except KeyError as exc:
            raise FrozenEvaluationError("A fold names a group missing from group_metadata") from exc

    folds = [{"train_groups": mapped(fold["train_groups"]), "test_groups": mapped(fold["test_groups"])}
             for fold in receipt["folds"]]
    metric_names = sorted({key for model in receipt["models"].values() for key in model
                           if not isinstance(model[key], (dict, list))})
    leakage = []
    overlaps = receipt.get("unblocked_overlap_counts", {})
    if isinstance(overlaps, dict):
        for column, counts in sorted(overlaps.items()):
            total = sum(counts) if isinstance(counts, list) else counts
            leakage.append({"id": f"unblocked_overlap:{column}", "count": int(total)})
    environment = receipt["environment"] if isinstance(receipt["environment"], dict) else {}
    return {
        "adapter": "regenbench-metrics/1",
        "producer": {"tool": "regenbench", "version": environment.get("regenbench"), "code_revision": None},
        "created_utc": None, "input_sha256": [receipt["dataset_sha256"]],
        "folds": folds, "baseline_names": sorted(receipt["models"]), "metric_names": metric_names,
        "model_names": sorted(receipt["models"]), "reported_leakage": leakage,
        "seed": receipt["configuration"].get("seed"),
    }


def adapt_evaluation_receipt(receipt):
    """Normalize the generic ``regen-workbench/evaluation-receipt/1`` contract.

    A sibling repository can emit this small document without a bespoke adapter::

        {"schema": "regen-workbench/evaluation-receipt/1",
         "producer": {"tool": "...", "version": "...", "code_revision": "<40-hex>|null"},
         "created_utc": "<ISO-8601 with timezone>", "input_sha256": ["<64-hex>", ...],
         "folds": [{"train_groups": [...], "test_groups": [...]}],
         "model_names": ["..."], "metric_names": ["..."],
         "reported_leakage": [{"id": "...", "count": 0}]}
    """
    if receipt.get("schema") != "regen-workbench/evaluation-receipt/1":
        raise FrozenEvaluationError("Not a regen-workbench/evaluation-receipt/1 document")
    producer = _object(receipt.get("producer"), {"tool", "version", "code_revision"}, set(), "Receipt producer")
    revision = producer["code_revision"]
    if revision is not None and (not isinstance(revision, str) or not GIT_COMMIT.fullmatch(revision)):
        raise FrozenEvaluationError("Receipt code_revision must be a 40-character git commit or null")
    hashes = receipt.get("input_sha256")
    if (not isinstance(hashes, list) or not hashes or not all(isinstance(h, str) and SHA256_HEX.fullmatch(h)
                                                              for h in hashes)):
        raise FrozenEvaluationError("Receipt input_sha256 must list SHA-256 digests")
    folds = receipt.get("folds")
    if not isinstance(folds, list) or not folds or len(folds) > 1000:
        raise FrozenEvaluationError("Receipt folds must list 1-1000 train/test group sets")
    cleaned = []
    for fold in folds:
        fold = _object(fold, {"train_groups", "test_groups"}, set(), "Receipt fold")
        cleaned.append({"train_groups": _id_list(fold["train_groups"], "train_groups", minimum=0),
                        "test_groups": _id_list(fold["test_groups"], "test_groups", minimum=1)})
    models = receipt.get("model_names")
    metrics = receipt.get("metric_names")
    for label, value in (("model_names", models), ("metric_names", metrics)):
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise FrozenEvaluationError(f"Receipt {label} must be a list of names")
    leakage = receipt.get("reported_leakage", [])
    if not isinstance(leakage, list):
        raise FrozenEvaluationError("Receipt reported_leakage must be a list")
    cleaned_leakage = []
    for item in leakage:
        item = _object(item, {"id", "count"}, set(), "Reported leakage entry")
        if isinstance(item["count"], bool) or not isinstance(item["count"], int) or item["count"] < 0:
            raise FrozenEvaluationError("Reported leakage counts must be nonnegative integers")
        cleaned_leakage.append({"id": _text(item["id"], "Leakage id", 200), "count": item["count"]})
    created = receipt.get("created_utc")
    if created is not None and _utc(created) is None:
        raise FrozenEvaluationError("Receipt created_utc must be a timezone-aware ISO-8601 time or null")
    return {
        "adapter": "evaluation-receipt/1",
        "producer": {"tool": _text(producer["tool"], "Producer tool", 200),
                     "version": _text(producer["version"], "Producer version", 100, empty=True),
                     "code_revision": revision},
        "created_utc": created, "input_sha256": sorted(set(hashes)), "folds": cleaned,
        "baseline_names": sorted(models), "metric_names": sorted(metrics), "model_names": sorted(models),
        "reported_leakage": cleaned_leakage, "seed": receipt.get("seed"),
    }


ADAPTERS = {"regenbench-metrics/1": adapt_regenbench_metrics,
            "evaluation-receipt/1": adapt_evaluation_receipt}


# --------------------------------------------------------------------------- binding

def _check(identifier, status, detail):
    return {"id": identifier, "status": status, "detail": detail}


def evaluate_binding(freeze, normalized, stage):
    """Compare a normalized receipt with a freeze under the declared stage.

    ``stage='development'``: every train and test group must be a development
    group; touching a final-test group is a failure. ``stage='final_test'``: every
    training group must be a development group and every test group a final-test
    group, with at least one final-test group evaluated.
    """
    _choice(stage, BINDING_STAGES, "binding stage")
    body = freeze["content"]
    development = set(body["split"]["development_group_ids"])
    final = set(body["split"]["final_test_group_ids"])
    pinned = {item["sha256"] for card in body["pins"]["datasets"] for item in card["files"] if item["sha256"]}
    checks = []

    unpinned = [value for value in normalized["input_sha256"] if value not in pinned]
    if not normalized["input_sha256"]:
        checks.append(_check("inputs_pinned", "unavailable", "The receipt names no input hash."))
    elif unpinned:
        checks.append(_check("inputs_pinned", "fail", "The receipt consumed input(s) not pinned by the "
                             "freeze's dataset cards: " + ", ".join(value[:12] for value in unpinned)))
    else:
        checks.append(_check("inputs_pinned", "pass", "Every input hash is a file pinned by a dataset card."))

    folds = normalized["folds"]
    train_union = sorted({group for fold in folds for group in fold["train_groups"]})
    test_union = sorted({group for fold in folds for group in fold["test_groups"]})
    unknown = sorted((set(train_union) | set(test_union)) - development - final)
    final_in_training = sorted(final & set(train_union))
    final_evaluated = sorted(final & set(test_union))
    if not folds:
        checks.append(_check("split_matches_freeze", "unavailable", "The receipt exposes no group assignment."))
    else:
        problems = []
        if unknown:
            problems.append("groups outside the frozen split: " + ", ".join(unknown[:10]))
        if stage == "development":
            touched = sorted(final & (set(train_union) | set(test_union)))
            if touched:
                problems.append("final-test group(s) used in a development run: " + ", ".join(touched))
        else:
            bad_training = sorted(set(train_union) - development)
            bad_testing = sorted(set(test_union) - final)
            if bad_training:
                problems.append("non-development group(s) used for training: " + ", ".join(bad_training[:10]))
            if bad_testing:
                problems.append("non-final-test group(s) used as the test set: " + ", ".join(bad_testing[:10]))
            if not final_evaluated:
                problems.append("no final-test group was evaluated")
        checks.append(_check("split_matches_freeze", "fail" if problems else "pass",
                             "; ".join(problems) if problems else
                             f"All groups agree with the frozen split for the {stage} stage."))
        checks.append(_check(
            "final_test_not_in_training", "fail" if final_in_training else "pass",
            ("Final-test group(s) appear in training folds: " + ", ".join(final_in_training))
            if final_in_training else "No final-test group appears in any training fold."))

    leaked = [item for item in normalized["reported_leakage"] if item["count"] > 0]
    if not normalized["reported_leakage"]:
        checks.append(_check("producer_reported_overlap", "unavailable",
                             "The producer reported no overlap diagnostic."))
    elif leaked:
        checks.append(_check("producer_reported_overlap", "fail", "The producer reported overlap: " + ", ".join(
            f"{item['id']}={item['count']}" for item in leaked)))
    else:
        checks.append(_check("producer_reported_overlap", "pass", "The producer reported zero overlap."))

    method = body["method"]
    producer = normalized["producer"]
    if method["revision"] and producer.get("code_revision"):
        same = method["revision"] == producer["code_revision"]
        checks.append(_check("method_revision_matches", "pass" if same else "fail",
                             "Receipt code revision " + ("equals" if same else "differs from") +
                             " the pinned method commit."))
    elif method["version"] and producer.get("version"):
        same = method["version"] == producer["version"]
        checks.append(_check("method_revision_matches", "pass" if same else "fail",
                             "Producer version " + ("equals" if same else "differs from") +
                             " the pinned version; a version is weaker evidence than a commit."))
    else:
        checks.append(_check("method_revision_matches", "unavailable",
                             "The receipt or the freeze carries no comparable revision or version."))

    metric = body["primary_metric"]
    if not normalized["metric_names"]:
        checks.append(_check("primary_metric_present", "unavailable", "The receipt lists no metric names."))
    else:
        missing = []
        if metric["name"] not in normalized["metric_names"]:
            missing.append(f"metric {metric['name']!r}")
        if metric["baseline"] not in normalized["baseline_names"]:
            missing.append(f"baseline {metric['baseline']!r}")
        checks.append(_check("primary_metric_present", "fail" if missing else "pass",
                             ("The receipt lacks " + " and ".join(missing)) if missing else
                             "The frozen primary metric and baseline are both reported."))

    produced, frozen = _utc(normalized["created_utc"]), _utc(body["frozen_utc"])
    if produced is None:
        checks.append(_check("result_postdates_freeze", "unavailable",
                             "The receipt carries no creation time, so it cannot be shown to postdate the freeze."))
    elif produced >= frozen:
        checks.append(_check("result_postdates_freeze", "pass", "The receipt was created after the freeze."))
    else:
        checks.append(_check("result_postdates_freeze", "fail", "The receipt was created before the freeze."))

    substantive = [item for item in checks if item["id"] in {
        "inputs_pinned", "split_matches_freeze", "final_test_not_in_training", "method_revision_matches",
        "primary_metric_present", "producer_reported_overlap"}]
    # A metric name matching proves nothing about which data or code produced the number, so a
    # binding needs at least one identity check (inputs, split or method) to pass.
    identity = [item for item in checks if item["id"] in {
        "inputs_pinned", "split_matches_freeze", "method_revision_matches"}]
    timing = next(item for item in checks if item["id"] == "result_postdates_freeze")
    if any(item["status"] == "fail" for item in substantive):
        status = "mismatch"
    elif not any(item["status"] == "pass" for item in identity):
        status = "unverifiable"
    elif body["freeze_status"] == "retrospective" or timing["status"] == "fail":
        status = "bound_retrospective"
    elif timing["status"] == "unavailable":
        status = "bound_timing_unverified"
    else:
        status = "bound_prospective"
    return {"checks": checks, "binding_status": status,
            "final_test_groups_evaluated": final_evaluated if folds else None,
            "final_test_groups_in_training": final_in_training if folds else None}


def validate_binding_request(content):
    value = _object(content, {"freeze_revision_id", "adapter", "stage", "receipt_path"}, set(),
                    "Binding request")
    return {"freeze_revision_id": _text(value["freeze_revision_id"], "Freeze revision ID", 64),
            "adapter": _choice(value["adapter"], set(ADAPTERS), "receipt adapter"),
            "stage": _choice(value["stage"], BINDING_STAGES, "binding stage"),
            "receipt_path": _text(value["receipt_path"], "Receipt path", 1000)}


def build_binding_content(request, *, freeze, receipt_bytes, receipt_name, bound_utc):
    _checked(freeze, "freeze")
    if freeze.get("record_type") != "plan_freeze":
        raise FrozenEvaluationError("Receipts bind to a plan freeze")
    receipt = parse_receipt_json(receipt_bytes)
    normalized = ADAPTERS[request["adapter"]](receipt)
    evaluation = evaluate_binding(freeze, normalized, request["stage"])
    return {
        "freeze_revision_id": freeze["revision_id"], "freeze_content_sha256": freeze["content_sha256"],
        "adapter": request["adapter"], "stage": request["stage"],
        "receipt": {"filename": receipt_name, "sha256": sha256_bytes(receipt_bytes),
                    "bytes": len(receipt_bytes)},
        "normalized": normalized, "checks": evaluation["checks"],
        "binding_status": evaluation["binding_status"],
        "final_test_groups_evaluated": evaluation["final_test_groups_evaluated"],
        "final_test_groups_in_training": evaluation["final_test_groups_in_training"],
        "bound_utc": bound_utc,
        "limitations": [
            "A binding shows that a receipt agrees with a plan on the listed checks. It does not show "
            "that the analysis was correct or that the receipt is genuine.",
            "Only the fields the adapter exposes were compared; 'unavailable' means a check could not be "
            "made, not that it passed.",
        ],
    }


# --------------------------------------------------------------------------- assessment

HOLDOUT_VIOLATIONS = ("tuned_on_final_test", "tuned_after_final_test_opened",
                      "final_test_data_used_in_development_run", "unrecorded_final_test_evaluation")


def assess_freeze(freeze, events, bindings):
    """Derive the holdout and claim state of one freeze from its immutable records."""
    body = freeze["content"]
    ordered = sorted(events, key=lambda item: item["content"].get("sequence", 0))
    problems = ledger_problems(freeze, events)
    final_events = [item for item in ordered if item["content"].get("scope") == "final_test"]
    first_final = final_events[0]["content"].get("sequence") if final_events else None
    violations = []
    if any(item["content"].get("action") == "tune" for item in final_events):
        violations.append({"id": "tuned_on_final_test",
                           "detail": "A tuning action was recorded against the final-test groups."})
    if first_final is not None and any(
            item["content"].get("scope") == "development" and item["content"].get("action") == "tune"
            and item["content"].get("sequence", 0) > first_final for item in ordered):
        violations.append({"id": "tuned_after_final_test_opened",
                           "detail": "Development tuning was recorded after the final-test groups were "
                                     "first accessed."})
    usable = [item for item in bindings if item.get("content_integrity_valid") is not False]
    if any(item["content"].get("final_test_groups_in_training") for item in usable) or any(
            item["content"].get("stage") == "development" and item["content"].get("final_test_groups_evaluated")
            for item in usable):
        violations.append({"id": "final_test_data_used_in_development_run",
                           "detail": "A bound receipt used final-test group(s) in a development run or in "
                                     "training."})
    if not final_events and any(item["content"].get("final_test_groups_evaluated") and
                                item["content"].get("stage") == "final_test" for item in usable):
        violations.append({"id": "unrecorded_final_test_evaluation",
                           "detail": "A bound receipt evaluated final-test group(s) but the ledger records "
                                     "no final-test access."})
    if len(final_events) > 1:
        violations.append({"id": "final_test_reused",
                           "detail": f"The final-test groups were accessed {len(final_events)} times."})

    status = body["freeze_status"]
    ids = {item["id"] for item in violations}
    if problems:
        claim = "ledger_integrity_failed"
    elif ids & set(HOLDOUT_VIOLATIONS):
        claim = "holdout_compromised"
    elif status == "retrospective":
        claim = "retrospective_not_confirmatory"
    elif status == "exploratory":
        claim = "exploratory_only"
    elif len(final_events) == 0:
        claim = "holdout_sealed"
    elif len(final_events) == 1:
        claim = "single_final_evaluation_recorded"
    else:
        claim = "holdout_reused_not_independent"
    supported = claim == "single_final_evaluation_recorded" and any(
        item["content"].get("binding_status") == "bound_prospective"
        and item["content"].get("stage") == "final_test" for item in usable)
    ordered_head = ordered[-1]["content_sha256"] if ordered else None
    return {
        "ledger": {"n_events": len(ordered), "head_sha256": ordered_head, "chain_valid": not problems,
                   "chain_problems": problems, "n_final_test_events": len(final_events),
                   "first_final_test_sequence": first_final},
        "bindings": [{"revision_id": item["revision_id"], "stage": item["content"].get("stage"),
                      "binding_status": item["content"].get("binding_status"),
                      "receipt_sha256": (item["content"].get("receipt") or {}).get("sha256")}
                     for item in usable],
        "violations": violations, "claim_status": claim,
        "record_supports_confirmatory_claim": supported,
        "claim_limits": list(CLAIM_LIMITS),
    }
