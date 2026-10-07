# Frozen-evaluation worked example

Generated 2026-10-07T19:13:07.348498+00:00 by `run_example.py` with Python 3.12.3 at workbench revision `455ecb685c89`.

## Part A - the committed NIST development receipt (real data, retrospective)

Receipt SHA-256 `7cd440e0ff4c66975966712015c974a6d866e574fba0859506a404f158391f7c` (7035 bytes); feature table `e055bf31bc6d08594b9010625a779d027821c2333cb369e7247c011c81158645`.

| Question | Result |
|---|---|
| Does the receipt agree with the plan that describes it? | bound_retrospective (freeze `retrospective`, claim state `retrospective_not_confirmatory`) |
| Could it be the evaluation of a sealed `training_high` well, as a development run? | mismatch |
| ...or as the final-test evaluation? | mismatch |
| Claim state of the what-if freeze | `holdout_compromised` (final_test_data_used_in_development_run, unrecorded_final_test_evaluation) |

Leave-one-well-out trains on every well, so the receipt cannot be a confirmatory evaluation of any one of them. The regen-benchmark-kit report says the same in prose ("Repeated tuning against these folds turns them into development data"); here the Desk derives it from the receipt's fold assignments.

## Part B - SYNTHETIC clean path (not a measurement)

SYNTHETIC FIXTURE - made-up groups and receipt; demonstrates the procedure, not a result. Freeze `confirmatory`, binding `bound_prospective`, claim state `single_final_evaluation_recorded`; the record supports a confirmatory claim: True. That sentence is about the recorded procedure only.

## Dossier verification

`verify_dossier.py --strict` on `dossier.zip`: bytes verified True, scientific lineage `resolved`, scientific review `not_established_by_this_tool`, reproduction `not_attempted`.

## What this does not show

- It runs no model and measures no biology. Part A re-reads a receipt that already existed.
- The freeze clock, the `results inspected` answer and ledger actors are self-reported.
- Three wells cannot support a group interval, and density is confounded with well.
