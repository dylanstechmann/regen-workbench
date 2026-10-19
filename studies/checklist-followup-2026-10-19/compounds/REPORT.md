# SLU-PP-915: oral PK intake and calculation eligibility

Reviewed 2026-10-19. This follows the [compound decision report](../../checklist-progress-2026-10-19/compounds/REPORT.md)
and preserves the goal of improving useful exposure without substituting a
marker or predicted property for tissue function. It does not repeat the
earlier molecular panels or propose another analogue.

**No numerical oral concentration-time curve was acquired.** This pass adds
an inspectable route/sample-context intake and executable checks that explain
which calculations remain unsupported. It produces no AUC, refitted half-life,
absolute oral bioavailability or human-exposure estimate. Empty point arrays
mean unacquired measurements, not zero concentrations or lack of oral activity.
Mouse oral activity and the reported 18–28-minute oral plasma half-life remain
as qualified in the earlier report. [Primary article](https://doi.org/10.1016/j.jpet.2025.103787).

## Access findings

Six direct official-source/metadata requests were made. Four downloads have
real `regen.record` receipts and source hashes; two article-page requests
returned HTTP 403. [Access receipt summary](source_access_receipts.json).

| Source checked | Retrieved content | What it can support |
| --- | --- | --- |
| ScienceDirect article page | HTTP 403 on direct request; indexed primary text remains readable through search | Qualified prose/caption context, not an archived quantitative figure extraction |
| JPET article page | HTTP 403 | Access limitation only |
| Crossref DOI metadata | Bibliographic metadata; registered publisher API links; empty relation object | Identity and registered access links; no data attachment identified in this record |
| Registered Elsevier XML endpoint | HTTP 200; 1,890 bytes containing core bibliographic data only | Identity; **HTTP success does not establish full-text or numeric-data access** |
| UHSP institutional record | Abstract and DOI link; no data attachment found among the inspected links | Institutional bibliographic cross-check |
| OpenAlex DOI record | Closed status; no listed OA full-text repository/PDF | Location metadata within that service, not proof that no copy or data exists elsewhere |

Bounded DOI/PII and repository searches did not locate an eligible numerical
oral PK source. The article's indexed data-availability statement offers raw
data from the authors; no author request or other external message was sent.
No access restriction was bypassed. These checks do not establish that a
supplement or differently indexed dataset does not exist.

## Route and sample contexts retained

[pk_context_intake.json](pk_context_intake.json) separates five route-specific
contexts rather than combining neighboring figure panels into a fictional
time course:

| Context | Route in source context | Sample relationship | Missing for quantitative PK |
| --- | --- | --- | --- |
| Figure 2A oral | Voluntary oral suspension | One-hour concentration across exposure groups; caption reports four mice/group | Numeric values, figure verification, assay and sample hierarchy |
| Figure 2A comparator | Intraperitoneal comparison described in text | Matching the text to the plotted comparator requires figure verification | Same gaps; route-to-curve assignment remains unresolved |
| Figure 2B | Oral gavage | Time-course/exposure experiment described in prose | Actual time/concentration values, per-time n, serial/terminal design and quantitative assay qualification |
| Figure 2C oral | Voluntary oral suspension | One-hour concentration after initial versus final administration | Full within-interval time courses and subject linkage |
| Figure 2C comparator | Intraperitoneal | Same initial/final single-time comparison | Same gaps; no intravenous reference |

The general mean/SEM statement is retained separately. A neighboring panel's
sample size is not assigned to Figure 2B. Ddit4 expression and running
performance remain separate pharmacodynamic/functional outcomes. They cannot
supply missing parent concentrations. The prior Figure 3 route discrepancy
is retained as an exclusion, without being used to resolve PK measurements.

## What the executable checks do

[assess_pk_intake.py](assess_pk_intake.py) reads the intake and regenerates
[eligibility_report.json](eligibility_report.json). All five actual contexts
currently fail qualified intact-parent AUC input eligibility; absolute F is
also withheld. Reasons remain explicit per context.

The checker distinguishes three questions:

1. **Can retrieved numerical signal be integrated over an observed interval?**
   It needs a real numeric source, ordered quantitative points, identified
   units and explicit handling of quantification limits. A reported half-life,
   dose-response panel or initial/final one-hour comparison cannot replace a
   concentration-time table. A future digitized curve additionally needs
   calibrated axes and time/concentration readout bounds.
2. **Can that signal be interpreted as intact-parent plasma exposure?**
   It also needs parent-specific assay qualification, route/matrix identity,
   resolved timing and biological sampling hierarchy. Numerical integration
   alone cannot establish these properties. Group means may support a
   descriptive mean curve when qualified; their SEMs do not identify
   individual AUC distributions or between-time covariance.
3. **Can absolute oral F be evaluated?**
   For this intake, a specifically linked qualified oral/IV pair, exposure
   normalization, comparable population/clearance and matched AUC coverage
   are required. The acquired intraperitoneal comparisons cannot supply that
   reference. No estimate is computed even in synthetic eligibility tests.

These checks evaluate declared metadata; they do not independently certify an
assay or identify a valid terminal phase. The utility implements no numerical
PK estimator. It neither fills gaps from the reported half-life nor makes
animal-to-human extrapolations.

## Next data that would unlock an analysis

The highest-value input is a source table for Figure 2B with time and
intact-parent concentration units, individual values or group summaries,
per-time n, uncertainty definitions, exposure-group identity and assay
qualification. Serial versus terminal sampling must be explicit. If a source
table remains unavailable, an accessible, calibrated figure can support a
**labelled digitized descriptive analysis**, with extraction uncertainty and
without invented individual records.

With those inputs, the next computation is an observed-interval AUC with its
actual start/end times. AUC from zero, extrapolated terminal exposure,
half-life fitting and uncertainty each need their own supported assumptions.
Absolute F remains a separate decision requiring an appropriate reference;
the current source intake cannot supply it. More chemistry enumeration would
not resolve this data gap.

## Reproduction and checks

From the repository root:

```powershell
python studies/checklist-followup-2026-10-19/compounds/assess_pk_intake.py
python -m unittest discover -s studies/checklist-followup-2026-10-19/compounds -p test_pk_intake.py -v
```

The generated report links the exact intake and assessor hashes. Twelve
tests cover actual missing-data behavior and scientific counterexamples:
metadata-only HTTP success, single-time comparisons, assay-signal versus
parent exposure, false serial pairing, group-SEM limits, digitization bounds,
censoring, invalid numbers and an intraperitoneal-only reference. All numeric
test curves are explicit synthetic fixtures, never published PK observations.
Full texts and raw metadata downloads remain ignored locally. The workbench
Docker service was not running; targeted checks use host Python.
