# Plan freeze and receipt binding: the GSE160356 endothelial check

This folder holds the ResearchDesk records around one prespecified analysis that lives in
[senescence-module-score](https://github.com/dylanstechmann/senescence-module-score) (its
[plan](https://github.com/dylanstechmann/senescence-module-score/blob/main/validation/GSE160356/PLAN.md) and
[report](https://github.com/dylanstechmann/senescence-module-score/blob/main/validation/GSE160356/REPORT.md)).
It is part of a personal hobby and learning project developed with substantial assistance from AI coding tools.
This is the first use of the frozen-evaluation records (plan freeze, holdout ledger, receipt binding) on a real
run rather than a worked example. It runs no analysis itself and says nothing about biology.

## What happened, in order

| When (UTC, 2026-10-07) | Event | Evidence |
|---|---|---|
| 19:52:36 | Plan, pinned inputs and evaluator pushed in senescence-module-score `caa9eb3` | GitHub Actions run creation time |
| 19:54:19 | ResearchDesk plan freeze recorded (`exploratory`, one listed blocker) | `frozen_utc` in the record (Desk clock, self-reported) |
| 19:54:34 | Freeze snapshot pushed here, regen-workbench `bb0a182` | GitHub Actions run creation time |
| 19:54:38 | Evaluator started from the clean pinned revision; one run | `created_utc` in the receipt |
| afterwards | Ledger event and receipt binding recorded; final dossier exported | `derived/` |

## What the Desk says

- Freeze status **`exploratory`**. The Desk lists its own blocker: the split's grouping unit (a library) is not an
  identified independent-unit level, because the series text mentions three independent clones but deposits no
  sample-level clone or pairing.
- Binding **`bound_prospective`**: inputs pinned, split matches, no sealed library in any fit, no reported overlap,
  method revision equal to the pinned commit, frozen metric and baseline present, receipt created after the freeze.
- Claim state **`exploratory_only`**; the record does **not** support a confirmatory claim.
- Both dossiers pass `verify_dossier.py --strict` with `scientific_lineage` resolved; `scientific_review` stays
  `not_established_by_this_tool` and `reproduction` stays `not_attempted`.

A clean binding means the receipt agrees with the plan on those checks. It does not mean the analysis is correct
or that SenMayo is validated: the analysis outcome, with its limits (three libraries per condition, passage
confounded with condition, CDKN1A not rising, a gene-concentrated late-passage shift), is in the sibling report.

## Files

| Path | Contents |
|---|---|
| `record_freeze.py` | `freeze` creates question, dataset card, plan and freeze and exports the pre-run snapshot; `bind` records the ledger event and binding and exports the final dossier |
| `freeze_state.json` | Revision IDs, content hashes and the freeze time written by `freeze` |
| `inputs/evaluation_receipt.json` | Byte-identical copy of the receipt the evaluator wrote (`PROVENANCE.json` records its hash and source commit) |
| `derived/dossier-before-run.zip`, `verification-before-run.json` | The pre-run snapshot: the freeze exists, no ledger event or binding yet |
| `derived/dossier.zip`, `verification_report.json`, `binding_result.json` | The final dossier, its strict verification, and a summary of the binding |

```bash
python tools/verify_dossier.py studies/senescence-endothelial-challenge/derived/dossier.zip --strict
python -m unittest tests.test_senescence_endothelial_challenge -v
```

## Limits

The freeze clock, the "results inspected before freeze" statement and the ledger actor are self-reported and
unauthenticated; access that was never recorded cannot be detected. The inspection statement discloses that sixteen
count lines of one early-passage library were shown incidentally and that the linked paper (which benchmarks its own
signature against earlier ones in these datasets) was read for design only. Data: GEO GSE160356
(Bertelli, Pedrini, Guduric-Fuchs, Medina), public with no dataset-specific license; no data are redistributed here.
