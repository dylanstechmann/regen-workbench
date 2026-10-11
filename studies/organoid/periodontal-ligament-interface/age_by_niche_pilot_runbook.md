# Age-by-niche pilot runbook

## What this pilot is for

Convert the age-by-niche comparison into a reproducible assay and estimate
measurement and donor-level variance for a later confirmatory study. It is not
powered to establish rejuvenation, and it should not begin until the static
two-interface architecture passes the attachment gate in the assay dossier.
Use the six conditions in `age_by_niche_test.tsv`; do not add pathway
perturbations to this pilot.

## Before enrollment or sample processing

1. Freeze eligibility criteria, age-stratum labels, periodontal-health
   assessment, tooth classes, root-maturity assessment and extraction
   indications. Keep exact age in the data; strata provide recruitment coverage
   only. Seek overlap in source characteristics across ages. If the cohort
   cannot separate age from tooth class or extraction indication, narrow the
   target population and label the age contrast non-identifiable.
2. Create one pseudonymous roster using the separate `target` and `niche` role
   labels in `age_niche_donor_roster_template.tsv`. No person serves both roles
   in this pilot. Keep the re-identification key outside the research dataset
   and repository. Complete all source fields where available and record
   unavailable values with the data dictionary's missing-value labels.
3. Use one independent conditioned-medium preparation lot per niche donor for
   this pilot. Do not pool donors. Each target donor receives matched
   unconditioned controls and conditioned-medium exposure conditions from
   every qualified niche donor. Freeze handling, base medium,
   collection, storage, passage, exposure and washout definitions in the
   protocol before labels are released.
4. Lock the post-washout endpoint definitions, healthy-reference comparison,
   blinded scoring instructions, exclusion rules and analysis hierarchy. Use
   the data dictionary `age_by_niche_data_dictionary.tsv`; retain raw values,
   units, failures, and all predeclared timepoints.

## Measurement qualification

First establish repeatability for the measurements that determine progression:
cell identity and survival, root- and bone-facing fiber insertion, ligament
space, localized mineralization, and recoverable mechanics. Use coded specimens
so imaging and mechanical scoring are blinded to donor age and condition.
Include acellular, no-guidance, and fusion/mineral-bridge controls from the
assay dossier. Estimate scorer agreement, instrument repeatability, and
manufacturing failure rate before interpreting a niche effect. Freeze margins
from matched healthy references and measurement error; do not invent a numeric
pass threshold from the pilot outcome.

## Crossed allocation and blocking

Generate the complete target-donor × niche-donor crossing plus an unconditioned
control for every target donor with `make_age_niche_allocation.py`. The script
balances target-age × exposure × niche-age groups across batch-capacity blocks,
then randomizes processing order within each block. Technical constructs stay
nested under their donor pair and do not add biological replicates.

Example using synthetic roster values only:

```powershell
python make_age_niche_allocation.py `
  --roster age_niche_donor_roster.tsv `
  --out allocation_manifest.tsv `
  --seed 20261011 `
  --batch-capacity 24 `
  --constructs-per-pair 1 `
  --controls-per-target 1
```

The roster used in the example must be pseudonymized and stored under the
approved local data controls; do not commit participant-level records. The
manifest contains donor ages for the allocation custodian. Provide scorers
only the separate `blinded_code`, timepoint and material needed to score the
endpoint. Record the seed and preserve the original manifest before running
the assay. If a batch fails, preserve its records and use the preregistered
failure rule; do not rerandomize around observed outcomes.

Before execution, verify each target donor has every niche-donor lot, an
unconditioned control, and the planned construct count; verify every batch
contains the intended age and exposure mix. The generator checks donor ID
uniqueness, role separation, exact age parsing and the two shared recruitment
strata. A statistician should review the final manifest if source counts are
unequal, a donor lot is missing, or any condition is aliased with batch.

## Variance pilot and confirmatory sizing

Use the pilot to estimate the donor-specific niche-age response-slope SD, the
niche-lot contribution to the age-by-niche interaction SD, and the residual SD
of the construct-level post-washout endpoint. Estimate repeatability and
failure rates separately. Choose the smallest relevant interaction in endpoint
units before unblinding, anchored to healthy-reference separation and assay
repeatability. Run low, central and conservative variance scenarios with
`simulate_age_niche_interaction.py`; do not call the illustrative example a
sample-size recommendation.

The simulator assumes equal numbers of target and niche donors in each of two
age strata, a fully crossed balanced design, one continuous post-washout
interaction endpoint, and no missingness or batch imbalance. It uses a
small-sample t approximation and Monte Carlo uncertainty guard. It does not fit
the final mixed model, handle multiple co-primary outcomes, or estimate
uncertainty in pilot variance components. Confirm the selected design with the
preregistered crossed-effects model and a sensitivity analysis before the
confirmatory study.

Example with invented values, solely to verify the command:

```powershell
python simulate_age_niche_interaction.py `
  --effect 0.5 `
  --target-donor-slope-sd 0.4 `
  --niche-lot-interaction-sd 0.3 `
  --construct-residual-sd 0.7 `
  --constructs-per-pair 2 `
  --seed 20261011
```

Replace every example number with pilot-derived variance estimates and a
prospectively justified smallest relevant interaction. Adding nested
constructs reduces only the residual term; it cannot replace independent
target or niche donors.

## Decision after the pilot

Proceed to a confirmatory donor-crossed study only if (a) measurement scoring
is repeatable, (b) the roster provides age and source overlap, (c) batches are
not aliased with age or condition, (d) both primary outcome families can be
measured after washout, and (e) the interaction and functional effect margins
are fixed before confirmatory outcomes are examined. Otherwise repair the assay
or cohort design first. A persistent marker shift without viable PDL identity,
bilateral insertion and recoverable mechanics is not an attachment-restoration
signal.
