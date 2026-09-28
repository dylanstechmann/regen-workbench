# Research philosophy and priorities

Recorded from the project owner's direction on 2026-09-27.

## Expanded direction: 2026-09-28

### Anti-aging focus update

Prioritize age-acquired damage and durable functional repair. The first three
research areas are somatic mutations and genome repair, engineered tissues,
and nanomedicine/tissue delivery. Organ replacement, senescent-cell clearance,
and structural restoration follow closely. Muscle, metabolic and cognitive
outcomes remain important endpoints, but no longer drive the default research
queue. NSI-189 remains a lower-priority archived lead, not a centerpiece.

Treat epigenetic reprogramming as one possible lever, not a substitute for
DNA-sequence correction, extracellular-matrix repair, cellular replacement or
restoration of organ architecture. A known disease-causing base corrected in
a monogenic model is a different problem from identifying and correcting the
distributed, heterogeneous somatic variants of ordinary aging. For each
proposed repair, ask which cells are affected, whether the change is causal,
what fraction can be reached, whether tissue function improves, and what
new risks arise from the intervention.

For engineered tissue, track donor-site cost, perfusion, integration,
mechanical or physiological function, adverse healing and durability. For
nanomedicine, separate organ accumulation, intended-cell uptake, actual cargo
activity and functional benefit. Record human trials, human cell constructs,
aged-animal experiments and computational hypotheses as different evidence
stages; none should silently inherit the claims of another.

The project now supports hypothetical research blueprints for age-related
damage reversal, body composition and muscle function, cognitive enhancement,
cosmetic and structural restoration, and organ replacement. A blueprint
records who, what, where, when, why and how, competing endpoints, desired
changes, missing evidence, and an observation that would disprove the idea.
CRISPR, stem cells, partial reprogramming, senolytic cell therapies and
bioprinting belong in this research space alongside existing small molecules.
Regulatory approval is a recorded attribute, not an admission requirement for
computational exploration.

Accept forum anecdotes, personal observations, gray-market reports and vendor
claims as research inputs. Keep their source type, provenance, uncertainty,
cointerventions and commercial interest visible. They can motivate tests;
they do not become independent efficacy confirmations through repetition.
Apply the same scrutiny to papers, our simulations and favored hypotheses.
Preserve negative and conflicting observations and differences in population.

Support property-directed exploration of existing structural neighbors and
unmeasured molecular variants. Name the actual operation: descriptor
calculation, graph enumeration, conformer sampling, docking or a particular
validated prediction model. Do not imply that a structure is novel because
our generator emitted it, or that a property improvement proves biological
improvement. Keep failed filters and unsupported molecule classes visible.

Success includes actual database/API runs and inspectable artifacts. The
[research desk](RESEARCH_DESK.md) is the local orchestration interface; methods
packages remain separate. Exportable research dossiers support eventual
human-reviewed public discussion without automatically publishing personal
observations or presenting a hypothetical blueprint as a treatment regimen.

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
