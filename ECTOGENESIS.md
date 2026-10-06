# Artificial wombs and ectogenesis

ResearchDesk's `ectogenesis` area supports the theoretical
[artificial-womb-models](https://github.com/dylanstechmann/artificial-womb-models)
project. The long-term question is whether complete development from IVF to
birth could be supported outside a uterus. The current contribution is an
evidence map and computational engineering fixtures.

Each source retains its species, actual observed developmental interval,
endpoints, comparator, limitations and review date. Early embryo culture,
partial support of already-developed fetuses, and complete gestation require
separate records. Independent studies cannot be joined into a continuous
developmental pathway. Proposed surrogacy replacement and reduced congenital
anomalies remain hypotheses requiring direct evidence.

## Using the bridge

Start ResearchDesk with its existing configuration:

```powershell
docker compose -f compose.research.yaml up -d
```

Open http://127.0.0.1:8092 and select **Artificial wombs & ectogenesis**. New
seed areas are added when the service starts, preserving saved blueprint edits.
The area follows replacement organs while the existing first three priorities
remain in place.

The two starter campaigns cover complete-gestation capability gaps and growth
comparisons during partial support. Their evidence axes record developmental
scope, interface continuity, exchange, development, adverse outcomes,
post-support follow-up, model applicability, engineering reliability and
proposed complete-gestation benefits. A maintained physiological variable
does not establish normal growth or unmeasured organ function.

Use the existing literature providers and typed campaign observations, then
export a dossier for review. The public source cards include primary animal
and mouse-embryo studies, an official FDA meeting summary and a clearly labeled
institutional update. A source search returns leads until they are assessed.
Registered or planned studies are not positive clinical outcomes.

The sibling repo's `wombmodels desk-status` command provides a read-only,
loopback-only check that this area is available. It handles no credentials,
submits no jobs, and excludes private notes and unrelated campaign contents
from its output. Simulations run in the sibling package; ResearchDesk remains
the source and campaign workspace. No hardware endpoint is introduced.

## First software contribution

The sibling package explores dimensionless exchange balances and artificial
power or sensor faults, with source/config hashes and conservation checks.
Its values and alarm thresholds are synthetic software fixtures, not measured
physiology, life-support settings, or a pregnancy-duration prediction. The
future research roadmap can incorporate independently reviewed measurements,
stage-specific models and qualified animal-research partnerships as evidence
becomes available.

Run the focused integration checks from this repository:

```powershell
python -m unittest discover -s tests -p test_ectogenesis_desk.py -v
```
