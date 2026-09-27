# Research philosophy and priorities

Recorded from the project owner's direction on 2026-09-27.

## Ambition

This workbench supports exploratory research into aging, regeneration, and
radical extension of healthy lifespan. The owner's long-term aspiration is
"eternal youth": sustained youthful function rather than accepting present
limits as permanent. This is a research ambition, not a demonstrated outcome
or a promise that current tools can deliver it.

## Preferred way of working

Prioritize molecular modeling and simulation, direct analysis of
gene-expression data, and compound datasets over building a literature-review
product. Give researchers tools to inspect underlying data, generate and
challenge hypotheses, compare alternatives, and reproduce computational
experiments. Favor ambitious exploration and rapid, measurable iteration;
conventional caution alone should not decide which hypotheses may be tested
in silico.

The owner is concerned that published studies and claims can be shaped by
methodological flaws, selective reporting, political or institutional
pressures, commercial incentives, and attachment to existing beliefs or
profit models. The project should record and investigate these possible
influences instead of treating publication, consensus, reputation, or a
conservative conclusion as automatic authority.

These concerns are a reason to scrutinize evidence, not proof that a
particular person, group, or result is compromised. Apply the same scrutiny
to optimistic longevity claims, commercial anti-aging products, and our own
preferred hypotheses. Disagreement or caution alone does not establish bias.

## How this changes implementation

- Build local analysis and simulation activities first: expression contrasts,
  gene-set scoring, compound characterization, conformer generation, and
  reproducible comparisons of model settings.
- Retain source data, identifiers, hashes, parameters, random seeds, software
  versions, and explicit assumptions so results can be inspected and rerun.
- Expose effect sizes, sample sizes, missing data, sensitivity to choices,
  controls, and contradictory results. Separate exploratory results from
  confirmatory analyses; avoid silently selecting only favorable outcomes.
- Treat publications as useful inputs and leads, alongside raw data and
  independently reproduced results. Record funding or conflicts where known;
  do not invent motives or infer them from an inconvenient finding.
- Distinguish simulated behavior, measured biological effects, and demonstrated
  human benefit. Docking scores, force-field energies, expression changes,
  and model predictions are not evidence of rejuvenation on their own.
- Make uncertainty and limitations inspectable without using them as a reason
  to abandon exploratory computational work. Let failed hypotheses improve
  the next experiment.

## Immediate direction

Expand this existing sandbox with practical molecular and dataset-analysis
tools before creating another project or a broad study-aggregation service.
Keep literature lookup available as supporting context. Success means more
testable ideas and more reproducible computation, with conclusions that can
survive attempts to disprove them.
