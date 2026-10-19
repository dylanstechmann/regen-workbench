# A specimen-linked test of depth, interfaces and fatigue

2026-10-19. This adds an executable measurement/analysis bridge for intended-depth
hard-tissue qualification. It follows the
[actual Hasan material-data reanalysis](../../checklist-followup-2026-10-19/dental/REPORT.md)
and implements the material stage of the
[full-crown/PDL integration contract](../../checklist-progress-2026-10-19/dental/integration_contract.json).
It produces endpoint estimands with missingness and censoring, rather than
another regeneration score or a new set of arbitrary pass thresholds.

**Physically measurable hypothesis:** a candidate that supplies an intended
repair depth must retain an appropriate host/repair load path and seal when
tested as that actual specimen. Favorable surface indentation averages may
coexist with a thin region, an interfacial crack, leakage or early failure.
The bridge lets those observations remain connected instead of combining
separate favorable experiments into a claim of one successful tooth repair.

No new biological data were obtained. The source-qualified example remains
unlinked; the linked records are explicitly synthetic software fixtures.

## What the actual source can and cannot supply

The new source adapter verifies the hash of the previously extracted
**75 stored numerical positions** from Hasan et al.'s Fig. 6. It leaves
specimen and donor IDs empty and retains ambiguous cells `AC13` and `AD13`.
The [generated linkage audit](derived/source_linkage_availability.json)
returns **zero identifiable linked specimens**, without deleting the numerical
observations or fabricating a crosswalk.

| Estimand | State for the reviewed actual source block |
|---|---|
| Marginal apparent toughness and wear summaries | Already available in the prior reanalysis |
| Specimen-specific depth minus intended depth | Unavailable: no depth/target crosswalk |
| Interface crack path versus depth | Unavailable: no linked crack-path observations |
| Leakage bounds by depth/substrate | Unavailable: no linked leakage data or assigned-specimen registry |
| Fatigue failure by a declared horizon | Unavailable: wear loss values are not event/censoring times |
| Tooth/donor-balanced indentation analysis | Unavailable: no indentation-to-specimen/tooth/donor mapping |

An approximate layer example elsewhere in the article cannot become the
measured depth of each Fig. 6 specimen. The earlier unfavorable enamel-wear
mean directions, sample/population SD distinction and unknown trailing-cell
identities remain unchanged. This source audit concerns the reviewed blocks;
it does not assert that no paired dataset exists elsewhere.
[Hasan et al., primary article](https://www.nature.com/articles/s41467-025-64982-y).

## A usable measurement packet

Use the empty [JSON template](measurement_template.json) and
[data dictionary](data_dictionary.tsv). Register every assigned physical
specimen before outcomes, with its donor, tooth, batch, substrate, architecture,
comparison condition, intended depth and one predeclared repair region.
Unknown donor/tooth identities stay null. A workbook cell, image field or
indentation is not a new specimen.

Each specimen packet joins the same region to:

- An independently measured **minimum depth over the declared region**, with
  the measurement bounds and their interpretation. The supplied point target
  is separate; unknown target depth stays unknown. This implementation does
  not propagate uncertainty in the target itself.
- Leakage at a common material state/exposure, with exact values, left
  detection limits or right limits retained as such.
- A terminal crack-path category and its **actual assessment cycles**.
  Interfacial, mixed, cohesive-host and cohesive-repair damage remain visible;
  none detected is limited by measurement resolution.
- The first material-failure timing or right-censoring record, including why
  observation ended. Fixture loss does not become a successful runout or a
  material failure event.
- Repeated apparent-toughness indentations linked to their own specimen,
  region, state and exposure time.

Depth, leakage and indentation snapshots must share the declared material
state and exposure time. Later fatigue follow-up is a separate endpoint.
Terminal crack paths retain their potentially different observation times;
their descriptive categories are **not incidence at the fatigue horizon** and
cannot be treated as pre-fatigue predictors. Destructive measurements cannot
be assigned to an ongoing-test specimen without a valid physical lineage and
time record. The software checks identifiers/state labels, not whether those
labels truthfully describe the experiment.

## Executable estimands

For observed depth `d`, measurement bounds `[l,u]` and supplied point target
`t`, report `d−t` and `[l−t,u−t]`. A bound wholly below zero identifies a target
shortfall under those supplied bounds. It does not establish failed biology,
native architecture or clinical acceptance. Missing depth is not replaced by
zero, and a measured depth is retained when its target is missing.

For apparent toughness, first average repeat indentations **within specimen**.
The output separately reports the observed specimen-weighted mean and an
equal-tooth-then-equal-donor mean. Observed/assigned endpoint counts accompany
both. Unknown tooth/donor identities block the balanced estimand. No count of
indentations becomes a donor sample size, and no population confidence interval
is inferred from these descriptive means.

Leakage uses only its declared nonnegative scale. An exact value supplies
`[x,x]`, a left limit supplies `[0,L]`, and a right limit supplies
`[L,unbounded]`. Missing data supply `[0,unbounded]` **as an identification
bound, never an imputed zero**. Averaging these bounds over every assigned
specimen gives bounds for that finite cohort's mean. No LOD/2 substitution,
confidence interval or cross-assay conversion is made.

For a declared observation horizon `H`, an event interval ending at or before
`H` is a known failure by `H`; an interval beginning after `H` is known not to
have failed by `H`. A straddling interval is unknown. A right-censored specimen
is known event-free through `H` only when it was observed through `H`.
Early censoring, missing records and technical loss remain unknown. With
`F` known failures, `U` unknown states and `N` assigned specimens, the
finite-cohort failure fraction lies in **`[F/N,(F+U)/N]`**. These are
identification bounds, without independent-censoring assumptions; they are not
clinical risk estimates or confidence limits.

Groups remain separate by condition, substrate, architecture and intended
depth. Batch IDs remain visible; this implementation supplies no causal
depth effect, batch adjustment, equivalence test or composite acceptance rule.

## Executed software demonstration

The [linked fixture](synthetic_linked_fixture.json) is entirely synthetic:
six assigned specimens, two known donor IDs, shared tooth/coupon nesting and
one unknown donor/tooth identity. It verifies the following behavior:

| Software fixture result | Computed output | Meaning |
|---|---:|---|
| Thin-group baseline apparent toughness | Naively pooled indents 1.1714; specimen mean 1.0667; tooth/donor-balanced mean 1.1250 | Unequal indentation and coupon counts change weighting; none is a biological result |
| A 50 µm target with measured depth 42 and bounds 40–44 µm | Target difference −8; bound −10 to −6 µm | The target shortfall is retained rather than hidden by a group mean |
| Thin-group failure fraction by synthetic horizon 100 cycles | 1/3–2/3 | One failure, one known event-free and one early-censored specimen |
| Greater-depth group's failure fraction | 0–2/3 | Straddling event timing and missing follow-up cannot be counted as runouts |
| Greater-depth all-assigned leakage mean | Lower bound 0.3667; no finite upper bound | An instrument-failure record is not an observed zero |

Deleting an entire packet leaves its specimen in the assigned denominator.
Interfacial and mixed terminal paths remain in the output alongside missing
adjudication. Wrong-region joins, mixed snapshot times, duplicate indentations,
inconsistent tooth/donor identity and technical loss labeled as a material
event are rejected. Blank templates emit no made-up results or passes.

The [generated linked analysis](derived/linked_specimen_analysis.json) retains
all specimen records and all nine full-restoration domains as **unassessed**.
The fixture supplies no evidence of regeneration, better materials or a
depth-dependent biological effect.

## Next physically measurable comparison

The next input should be a registered specimen series with an independently
qualified regional depth measure, a native/damaged/process/reference design
appropriate to its substrate, and linked seal, crack-path and failure follow-up.
Freeze the intended greater-depth target and observation horizon after
metrology qualification, before inspecting candidate outcomes. Acceptance
margins still require reference distributions and repeatability evidence;
this script does not invent them.

The immediate falsifier is a candidate that appears satisfactory by surface
indentation but has a region demonstrably below its intended depth, an
interfacial failure route, or unresolved leakage/fatigue under the same
qualified specimen history. The new bridge makes that disagreement inspectable
at the physical-specimen level. It also exposes when censoring is too severe
to rank alternatives, rather than resolving the question by dropping failures.

Material qualification remains one stage. PDL insertion at both interfaces,
gingival form/barrier, pulp, original pose, final-crown load transfer and
stability after **finite support withdrawal** remain independent required
outcomes in the full restoration contract. No materials-only result can
satisfy them. No recipe, new treatment procedure or growth forecast is given.

## Reproduce and verify

```text
python studies/checklist-mechanisms-2026-10-19/dental/analyze_linked_material_outcomes.py
python -m unittest discover -s tests -p test_checklist_linked_material_outcomes.py -v
```

The default run reproduces the clearly synthetic linked demonstration and
the actual-source linkage audit. Use `--input` for another compatible packet
and `--out` for a separate output directory; the default `derived/` is the
checked fixture output. The empty template can be analyzed without inventing
data. Seventeen targeted checks pass. Input/script/source-table hashes use
canonical UTF-8/LF text. No new source downloads or fetch-provenance claims
were made. Docker workbench remains stopped.

The source adapter cites Hasan et al. (2025), DOI
**10.1038/s41467-025-64982-y**, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
and reads the previously attributed numerical extract without copying source
figures/workbooks. The measurement template, analysis definitions and synthetic
records are this study's additions; no new repository-wide license is assigned.
