# Age-by-niche donor-level analysis contract

## Purpose

This plan turns the six-condition age-by-niche matrix into donor-level
inference. It asks whether niche-source age changes an attachment-relevant
response, whether older cell sources respond differently, and whether any
response persists after conditioned medium is removed. It does not treat an
age-associated marker shift as rejuvenation.

## Estimands

1. **Cell-source age association:** estimate the age slope in qualified target
   cell donors under matched unconditioned medium. Model exact age
   continuously; use recruitment strata only to ensure coverage, not as the
   analysis scale. Interpret the slope only within the range where tooth class,
   root maturity, extraction indication, health and other source variables
   overlap. If those variables are separated by age, report the age contrast
   as non-identifiable in that cohort.
2. **Niche-source age association:** compare target-cell responses across
   independently prepared niche-donor media while the same target donor is
   represented in each condition. Preserve niche donor as an independent
   biological unit; a pooled “young” or “old” medium cannot estimate donor
   variation.
3. **Age-by-niche interaction (primary mechanism test):** estimate whether
   niche-source age changes the response more in older target-cell donors than
   in younger target-cell donors. This interaction, rather than a within-group
   p-value or a young-versus-old conditioned-medium comparison alone, is the
   key test of age-selective niche rescue.
4. **Persistence after washout:** measure baseline, exposure-end and
   post-washout outcomes in the same target-cell donor and qualified construct.
   Estimate time-by-cell-age and time-by-niche-age terms; a transient exposure
   response that vanishes after washout is reported as transient.
5. **Attachment-function transfer:** test the selected condition in the
   two-interface construct only after cell-identity and survival gates pass.
   The advancement outcome is a vector: fiber insertion at both root- and
   bone-facing interfaces, preserved ligament space, localized mineralization,
   and recoverable mechanics. A marker or proliferation improvement cannot
   compensate for failure of a required interface; stable tooth position
   remains a separate gate for a later orthotopic injury model.

## Model and units

For conditioned-medium arms, the starting model for continuous outcomes is

`outcome ~ cell_age * niche_age * time + prespecified_source_covariates + (1 | target_donor) + (1 | niche_donor) + (1 | batch) + (1 | construct)`

Analyze the unconditioned controls separately with `exposure_condition` as a
categorical factor (unconditioned, younger-donor conditioned medium,
older-donor conditioned medium) and prespecified contrasts against the
unconditioned condition. Do not assign a fictitious age to the unconditioned
control. Use an outcome-appropriate generalized mixed model for non-continuous
measures. If the data do not support the three-way interaction, simplify only
according to a preregistered hierarchy; do not select the model that gives the
most favorable result. Keep target and niche donor crossed where the
experimental matrix permits. Constructs, sections, images and repeated
mechanical cycles are nested observations. They do not increase the number of
donor replicates. Treat batch as a random effect only when enough independent
batches exist; otherwise block or adjust for it as a fixed effect. Include a
donor random slope for repeated time only if donor count and diagnostics
support it.

Prespecify a small number of co-primary outcomes from the endpoint contract:
post-washout viability/PDL identity and the bilateral insertion/mechanics
gate. Report estimates and uncertainty for every primary endpoint, including
null and adverse outcomes. Control multiplicity across the co-primary family
with a hierarchical gate or a stated family-wise procedure; keep exploratory
gene panels secondary and label them exploratory.

## Source qualification and confounding

Record exact donor age, sex, tooth class, root maturity, periodontal diagnosis,
sampling region, extraction indication, smoking/metabolic status where
available, relevant medication, isolation lot, passage, expansion time and
manufacturing batch. Eligibility must be fixed before outcomes are examined.
Recruitment should seek overlap in tooth class and extraction indication
across ages. Third-molar-only young sources and disease-selected older sources
cannot identify a general adult-aging effect. If healthy mature-tooth sources
are unavailable in one age range, narrow the target population and state the
resulting limit instead of extrapolating.

Draw and freeze a causal diagram before choosing adjustment variables. Use
eligibility and source matching to address major design differences first;
report a minimally adjusted age association and a prespecified covariate-
adjusted sensitivity estimate. Do not automatically adjust for every recorded
variable: periodontal health and extraction indication may partly reflect
age-related disease or selection, so conditioning on them can change the
estimand or introduce selection bias.

Conditioned-medium donor lots remain separate and are crossed with target-cell
donors. Match base medium, collection handling, storage and exposure conditions;
measure basic lot attributes needed to detect gross composition or handling
differences. Do not pool lots before the donor-level effect is estimated. The
historical conditioned-medium result is a positive assay benchmark only, not a
product specification or a therapeutic preparation.

## Sample-size and advancement rules

Do not choose a donor count from the published studies' technical triplicates.
First use an assay-qualification pilot to estimate donor, niche-donor, batch
and construct variance, failure rates, and score repeatability. Then set the
confirmatory donor count from the smallest interaction and functional effect
considered meaningful, with power or interval precision specified before
unblinding. Require independent target and niche donors and preserve the
crossing; adding wells to a small donor set is not a substitute.

Freeze numeric margins only after matched healthy-reference tissue and
measurement repeatability are available. Advance a niche condition only if
post-washout identity and viability remain acceptable and all prespecified
attachment-function gates pass without fusion or ectopic mineral bridging.
Position stability is assessed only at the later orthotopic transfer gate.
Otherwise retain it as a transient cell-state effect or reject it for
attachment restoration.

## Evidence constraint

Li et al. (2020) provide a group-level supplementary differential-expression
workbook, not a donor-level matrix; the paper's methods report `p < 0.05` or
fold change `> 2`, and its text notes discordant qRT-PCR directions for three
selected genes. Those candidates should not define the primary panel. The
cell-source × niche interaction and functional attachment outcomes are the
prespecified focus.

Pilot preparation is operationalized in the
[`runbook`](age_by_niche_pilot_runbook.md), with a blank pseudonymous roster
[`template`](age_niche_donor_roster_template.tsv),
[`data dictionary`](age_by_niche_data_dictionary.tsv), reproducible
[`allocation generator`](make_age_niche_allocation.py), and variance-input
[`power simulator`](simulate_age_niche_interaction.py). These tools do not
choose age cutoffs, effect margins, or a confirmatory donor count.
