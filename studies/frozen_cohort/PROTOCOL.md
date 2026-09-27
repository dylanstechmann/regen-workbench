# Frozen cohort — pre-registered software check

This file is the estimand. The runner does not tune it. Nothing here is a
biological result, a protocol for a person, or evidence of rejuvenation.

## Cohort

Eight synthetic samples. `Y1`–`Y4` are labeled `young`. `O1`–`O4` are labeled
`older`. Donors `D1` and `D2` are young; `D3` and `D4` are older. Age is
perfectly nested in donor, so a donor holdout cannot estimate an age effect.
The expression contrast is descriptive on this table only.

Expression values are nonnegative linear-scale fixtures. They are not counts
and they are not a public RNA-seq matrix.

## Estimand

Pseudocount `1`. Comparison `older` versus reference `young`.

Predeclared panel: `PANEL_A`, `PANEL_B`, `PANEL_C`, `PANEL_D`.

Predeclared null set: `NULL_A`, `NULL_B`, `STABLE_A`.

Estimand = mean log2 ratio of the panel minus mean log2 ratio of the null set.

Software-check success, all required:

1. Estimand > 0.5 on the registered labels.
2. The same estimand after swapping `young` and `older` is < −0.5.
3. `FLIP_A` is not direction-stable under leave-one-out. That gene is the
   declared failure case.
4. Nested morphology (each donor has its own batch): leave-one-donor-out
   L2 logistic balanced accuracy is greater than the training-fold majority
   baseline. Features are only `f_*` columns.
5. Shared-batch morphology (one batch id on every donor): joint donor-or-batch
   holdout has a single connected component and the runner refuses to score it.

Welch t-tests and Benjamini–Hochberg q-values are reported as a second view.
They are not the estimand. They are not DESeq2, and they do not adjust for the
donor/age aliasing.

## What this does not authorize

A concentration, a media recipe, a senescence call, or a compound rank.
`atlas_link.json` only carries the phenotype manifest hash so a later
compound-atlas export can cite the same bytes. The hash is not an activity label.
