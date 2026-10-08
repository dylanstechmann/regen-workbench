# Frozen-evaluation worked example

This folder shows what ResearchDesk's freeze, holdout ledger and receipt
binding do, using one real existing benchmark receipt and one clearly labeled
synthetic fixture. It is part of a personal hobby and learning project developed
with substantial assistance from AI coding tools (see the repository README).

It **runs no model and measures no biology**. Every status below is computed by
the Desk from stored records and one bounded read of each receipt.

## Run it

```bash
python3 studies/frozen-evaluation-example/run_example.py --out <new directory>
```

Python standard library only. The script refuses an existing output directory
and does all of its Desk and receipt writes inside a throwaway directory, so it
never touches your real ResearchDesk workspace. Revision IDs are random and
timestamps differ on every run; the statuses, hashes of the inputs and
conclusions below do not. `tests/test_frozen_evaluation_example.py` re-runs it
and asserts those conclusions.

The committed `derived/` folder is the receipt of one execution
(`workflow_result.json` records the time, Python version and workbench
revision):

| File | Contents |
| --- | --- |
| `REPORT.md` | Short human-readable summary of the results below |
| `workflow_result.json` | Every freeze, binding and check, with statuses and hashes |
| `dossier.zip` | The exported ResearchDesk dossier containing the records |
| `verification_report.json` | `verify_dossier.py --strict` run on that dossier |
| `synthetic_receipt.json` | The made-up receipt used by Part B only |

## Part A — a real development receipt (retrospective)

Input: `inputs/nist_ipsc_regression_metrics.json`, a byte-identical copy of the
metrics receipt that [regen-benchmark-kit](https://github.com/dylanstechmann/regen-benchmark-kit)
committed for its NIST iPSC example (192 tiles from three source wells, one per
seeding density; leave-one-well-out). The receipt carries no timestamp of its
own; its first commit there is dated 2026-09-24. `inputs/PROVENANCE.json`
records the exact commits it was copied from and first added in, and
`SOURCE_NOTICE.md` carries the NIST data terms and the citation to the source
data (Asmar et al. 2023, v1.1.0, doi:10.18434/mds2-2960).

That receipt existed before any plan was written here, so the freeze is
attested as **retrospective** and can never be confirmatory.

| Question | Result |
| --- | --- |
| Does the receipt agree with the plan that describes it (all three wells are development groups)? | `bound_retrospective` |
| If `training_high` had been sealed as a final-test well, could this receipt be its **development** run? | `mismatch` |
| ...could it be the **final-test** evaluation? | `mismatch` |
| Claim state of that what-if freeze | `holdout_compromised` |

Leave-one-well-out uses every well in training, so the receipt cannot be a
confirmatory evaluation of any one of them. regen-benchmark-kit's own report says
so in prose; here the Desk derives it from the receipt's recorded fold
assignments (`final_test_not_in_training` fails: `training_high` appears in
training folds). The negative result is the point: this existing benchmark is a
development benchmark, and the record says so mechanically.

## Part B — SYNTHETIC clean path (not a measurement)

Part B walks the prospective path once with made-up groups (`synthetic-a`,
`synthetic-b` for development; `synthetic-c` sealed) and a made-up receipt
(`synthetic_receipt.json`, producer `synthetic-fixture`). The dataset card,
plan, freeze, ledger events and receipt are all labeled SYNTHETIC in their
titles and citation fields. The expected outcome is a `confirmatory` freeze, a
`bound_prospective` binding and claim state `single_final_evaluation_recorded`.
That demonstrates what a correct procedure looks like in the record. No biology
is implied.

## Part C — can the Part A receipt be reproduced? (separate from verification)

`reproduction` stays `not_attempted` in dossier verification. As a separate step,
`tools/rerun_check.py` runs one allowlisted entry point (`regenbench regress`) from the
producing repository's source **at the pinned commit** (`git archive`, so the checkout is not
touched), on the feature table whose SHA-256 the receipt names, and compares the new
`metrics.json` with the vendored receipt, ignoring the `environment` block.

```bash
python studies/frozen-evaluation-example/rerun_nist.py --kit ../regen-benchmark-kit --out <new report.json>
```

Result recorded on 2026-10-08 in `derived/nist_rerun_report.json`:
**`reproduced_within_tolerance`**. 107 numbers compared; 78 are bit-identical and 29
(all Ridge values) differ in the last digits, at most 2.5e-14 relative, against a tolerance of
1e-9. The receipt was made with Python 3.12.14, numpy 2.3.5 and scikit-learn 1.8.0; the rerun
used Python 3.12.3, numpy 1.26.4 and scikit-learn 1.4.1. Both are recorded in the report.

This shows that the pinned code and the hashed table give these numbers again. It is not
scientific review, not evidence that the method works outside these three wells, and not a
rerun of anything but this one receipt. A spec cannot name another program: unknown entry
points, shell-like arguments and unpinned commits are refused before anything runs.

## What this does not show

- A freeze time is the Desk's clock. It shows when a plan was pinned, not that
  nobody looked at the data earlier. The "results inspected before freeze"
  answer and ledger actors are self-reported and unauthenticated.
- A binding shows that a receipt agrees with a plan. It does not show the
  analysis was correct, that the receipt is genuine, or that any biological
  claim follows. `scientific_review` remains `not_established_by_this_tool` and
  `reproduction` remains `not_attempted` in the dossier verification.
- Three wells cannot support a group interval, and seeding density is fully
  confounded with well.
- The adapter reads only the receipt fields it documents; it does not execute
  anything named in a record.
