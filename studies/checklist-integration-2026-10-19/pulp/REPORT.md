# Living pulp: five linked patient records expose sensory and imaging discordance

This is an executed reanalysis of all five patient/tooth columns in the
[Nakashima et al. 2017 pilot](https://doi.org/10.1186/s13287-017-0506-5),
not another review of stem-cell markers. Its 24-week records support a precise
measured pattern: **patients 1, 3 and 5 had source-positive electric sensibility,
a recorded apical MRI ratio and unambiguously absent periapical radiolucency**.
That is 3/5 observed records, **not a regenerated-pulp success rate**.

The [plan](analysis_plan.json) was frozen after source inspection. Prior goal
documents required viable pulp and sensation but supplied no patient-level
analysis of this pilot. Only this primary source was acquired; no second trial,
contact, figure digitization or new experiment was needed.

## Keep patient, tooth and visit together

Five patients aged 20–44 supplied one affected tooth each. Three dentists'
EPT readings, repeated visits and MRI regions remain nested within those five
people. All five have Table 4 EPT status, an apical MRI number and an X-ray
symbol at 24 weeks. The source does not supply a screening/approach denominator
or formal dropout flow. A late note about one patient cannot create a complete
36-week cohort.

| Patient | First reported positive EPT | EPT at 12 / 24 weeks | Apical MRI ratio, 24 weeks | X-ray radiolucency, 24 weeks | CBCT lateral-mineralization flag, time not stated in Table 4 |
| --- | --- | --- | ---: | --- | --- |
| 1 | Day 6 | + / + | 0.8 | Absent | + |
| 2 | After 36 weeks, exact day not supplied | − / − | 0.9 | Ambiguous −/+; prior lesion shrank, PDL widened | − |
| 3 | Day 6 | + / + | 0.9 | Absent | − |
| 4 | Day 28 | + / + | 0.7 | Present; PDL widening preceded it | + |
| 5 | Day 14 | + / + | 0.9 | Absent | + |

Enrollment EPT was positive in Table 1, before intervening pulpectomy. The
narrative separately states that pre-transplant EPT was negative in all five.
Those are different baselines, not contradictory values silently combined.
The four positive 12-week patients remain positive at 24 weeks. Patient 2's
late response is retained as **after 36 weeks**, without changing the earlier
negative status or assigning an exact later observation day.

The [patient extract](patient_records.json) retains all 36 nested device
readings. Two onset readings are `80+`, preserved as right-censored values.
Comparison-control teeth change across visits in patients 1, 3 and 4.
No EPT reading is converted into a percentage of recovered sensation, nerve
amount or pulp vitality, and no pooled control-normalized improvement is
calculated. The source itself cautions against treating the numeric display
as a validated vitality measure.

## MRI is an observed signal ratio, not blood flow

The source methods reference canal-tissue signal to surrounding dentin in the
same tooth, compared with normal pulp/dentin at the opposite site. The five
published apical ratios average **0.84**, with median **0.9** and range
**0.7–0.9**. These are continuous image-signal observations. A ratio near 1 is
not a fraction of normal perfusion, histological identity or a noninferiority
test. No healthy cutoff or MRI-positive classification is introduced.

Patient 2 has an apical ratio of 0.9 while remaining EPT-negative through
24 weeks. Patient 4 has a positive EPT response and a ratio of 0.7 while
developing periapical radiolucency after earlier PDL-space widening. These
linked discordances survive the analysis. They prevent sensory response or
MRI signal from standing in for the other outcomes.

## Exact bounds describe measured patterns

All denominators remain the five enrolled patients; unknown is never replaced
with absence. The bounds below describe this finite observed cohort, not
sampling confidence or causal efficacy.

| Explicitly timed pattern | Patient IDs meeting it | Count bounds |
| --- | --- | ---: |
| Source-positive EPT at both 12 and 24 weeks | 1, 3, 4, 5 | 4–4 / 5 |
| At 24 weeks: MRI number available and periapical radiolucency absent | 1, 3, 5; patient 2 unresolved | 3–4 / 5 |
| At 24 weeks: EPT-positive, MRI number available and radiolucency unambiguously absent | 1, 3, 5 | 3–3 / 5 |
| At 24 weeks: EPT-positive with radiolucency present | 4 | 1–1 / 5 |

“MRI number available” is explicitly a record-availability condition, not a
physiological pass. Patient 2's ambiguous radiograph does not enlarge the
third pattern's upper bound because that patient's 24-week EPT is negative.
The CBCT row has no explicit visit and is excluded from these same-time
patterns. Nor are the separate apical-obliteration and lateral-mineralization
flags silently treated as the same structural endpoint.

## Pulp-space change and adverse findings remain visible

The Results narrative supplies one internally consistent low-density-space
volume pair: patient 1, **0.0143 to 0.0125 cm³**, at nominal 16→28 weeks.
That is a **0.0018 cm³ / 12.59% decrease** in the source's CBCT-defined
low-density space. It does not identify regenerated-tissue loss, native dentin,
vascularization or mechanical benefit. Increasing mineralization can also
constrain the remaining pulp space; no favorable threshold is selected here.

For patient 4, the retrieved primary XML prints **0.0110 cm³ to 0.0081 m³**.
Its Results, figure caption and Discussion also use inconsistent visit labels
(16→28, 16→28/32 and 12→24 weeks). The unit and timing conflict remains
unresolved: **no corrected or conditional volume change is calculated**.
Patient 5 lacks the initial CBCT, so no volume change is invented. There is
no cohort mean volume-change estimate.

The source reports no transplantation-attributed laboratory/clinical events
or postoperative pain through 24 weeks. That does not erase patient 4's
radiographic deterioration or patient 2's residual/ambiguous findings, establish
their cause, or prove long-term safety. Literal cell-culture karyotype entries
are also retained separately rather than describing every preparation as
unconditionally normal or inferring patient constitutional diagnoses.

## What this changes in the restoration work

This source supplies real same-patient sensory/imaging follow-up and adverse
discordance, whereas earlier work lacked living-pulp records. It does **not**
directly measure blood flow or verify human pulp histology/innervation. It is
a small, selected, uncontrolled pilot; opposite-tooth MRI references are not
randomized untreated patients. No treatment effect or age effect is fitted.

The next needed evidence is joint, time-stamped sensory response, directly
qualified perfusion, preserved pulp-space/structural integrity and infection
status on the same tooth, followed long enough to assess calcification and
durability. Native pulp identity, dentin/enamel architecture, PDL/cementum/socket
attachment, youthful gums and stable original tooth position remain separate
required outcomes. The observed patterns here do not close that full contract.

## Reproduce and inspect

```text
python -B studies/checklist-integration-2026-10-19/pulp/analyze_patient_endpoints.py
python -B -m unittest discover -s tests -p test_checklist_integration_pulp.py -v
```

Default analysis and tests use the committed extract and standard library.
`extract_nakashima.py` repeats table extraction from the ignored primary XML;
analysis `--verify-cache` also verifies its actual byte hash. The source-specific
module name avoids another study's extraction module during combined tests.
[Results](derived/patient_endpoint_summary.json),
[hash receipt](derived/analysis_receipt.json) and
[actual fetch receipt index](source_receipts.json) are inspectable.

The numerical/categorical observations are attributed to Nakashima, Iohara,
Murakami and colleagues, *Stem Cell Research & Therapy* 8:61 (2017), under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The transcription,
bounded calculations and interpretation are this reanalysis; original findings
belong to the authors. Raw XML and genuine provenance stay ignored. No source
figures, patient treatment steps, doses, preparation methods or wet-lab work
are supplied. Docker workbench remains stopped.
