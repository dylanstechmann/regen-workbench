# Caffeine capture: finite capacity and reversible competition

AI-assisted exploratory research, 2026-10-19. This replaces the previous
idealized instantaneous capture assumption with a finite, reversible binding
calculation. It evaluates a published host in buffer, not a new oral molecule.

## What was measured, and what was chosen

The WP6 sensor paper reports caffeine association of `(2.51 ± 0.24) × 10^4 M⁻¹`
at 298 K in PBS pH 7.2, with inferred 1:1 binding. Theophylline and theobromine
central constants are `9.30 × 10^3` and `9.14 × 10^3 M⁻¹`. Thus caffeine's
central affinity ratios are **2.70 and 2.75**, despite the paper's stronger
verbal comparison. The ST indicator constant is a different measurement;
paraxanthine affinity is absent. [Duan et al., primary study](https://doi.org/10.3389/fchem.2021.816069).

The [source audit](source_qualification.json) distinguishes these measurements
from the [chosen sensitivity inputs](binding_plan.json). Total concentrations,
competitor abundances, capture targets and the fictional background guest are
arbitrary buffer cases. The reported ± endpoints are arithmetic sensitivities,
not confidence intervals; their uncertainty definition is unresolved.

## Executed calculation

For free host `h`, each guest has bound concentration
`L_total × K_a h / (1 + K_a h)`. A monotone mass-balance equation solves
`H_total = h + sum(bound guests)`. Every guest competes for the same finite
host pool. This conserves host sites and each guest; it has no time dimension.

For a desired captured fraction `q`, the required free host is
`h = q / ((1 − q) K_a)`. Total host must also supply occupied sites.
Complete capture therefore has no finite equilibrium solution in this model.
The [implementation](competitive_capture.py) produces
[180 equilibrium cases](derived/finite_capacity_equilibria.tsv) and
[108 target requirements](derived/target_capture_requirements.tsv), with
maximum absolute host-balance error below `9 × 10⁻¹⁹ M`.

In a **chosen 10 µM total-caffeine buffer case**, with central WP6 affinity
and no competitor:

| Chosen captured fraction | Required free host, µM | Required total host, µM |
| --- | ---: | ---: |
| 50% | 39.84 | 44.84 |
| 90% | 358.57 | 367.57 |
| 99% | 3,944.22 | 3,954.12 |

Equimolar total host captures **17.21%**, not complete capture. A 50-fold
total-host excess captures **92.49%** in this particular case. These are
mathematical buffer concentrations, not doses or achievable blood exposures.

Equal-total theophylline raises the 90% requirement to **375.26 µM**. The
fictional 1,000 µM background guest with chosen `K_a = 10,000 M⁻¹` raises it
to **1,149.49 µM**. This demonstrates how abundance and competition matter;
it does not identify a real physiological interferent or predict serum binding.

## What this changes in the research decision

An affinity screen should report intact accessible host, finite capacity,
matrix competition and free caffeine together. Detectable binding or successful
indicator displacement alone cannot establish useful systemic capture. Before
making a receptor-level claim, the missing tissue exchange and binding kinetics
would also need measurements. The human PET concentration discussed in the
[previous model](../../checklist-progress-2026-10-19/caffeine/REPORT.md) is not
used as a microscopic receptor dissociation constant here.

For the earlier question about other stimulants, the different P6AS host has
primary preclinical binding and mouse functional-reversal evidence for
methamphetamine and other guests. That supports host–guest sequestration as
a mechanism precedent, while leaving oral caffeine reversal and human sleep
unresolved. [Brockett et al., primary study](https://doi.org/10.1016/j.chempr.2022.11.019).
Its constants are not transferred into this calculation. The official XML
endpoint failed twice; the audit records those failures without download
provenance or an invented cached source.

This study cannot resolve oral absorption, host safety/clearance, brain
distribution, active paraxanthine capture, rebound after host loss or sleep
recovery. A stronger binder could still fail those requirements. Stimulant
peptides are not assumed easier to neutralize. This advances the caffeine
research lane while the full dental-restoration and whole-body youthful-function
goals remain in the [continuity record](../../restoration-run-plan-2026-10-11/GOALS_AND_CONTINUITY.md).
