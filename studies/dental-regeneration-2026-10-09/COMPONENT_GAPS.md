# Component evidence and next comparisons

This is an AI-assisted research roadmap based on the focused source panel in
[README](README.md). “Gap” means unresolved in this review, not that all
literature lacks the result. No clinical or fabrication protocol is supplied.

| Component / function | Evidence anchor in this panel | Next evidence needed before a stronger claim |
|---|---|---|
| Enamel identity and architecture | Human ameloblast organoids, 2026; ectopic enamel-like material | Native-like architecture, tooth-site interface and repeated-load behavior in the relevant model |
| Dentin–pulp unit | Whole-tooth mouse reference, 2009 | Separate adult-human source, living pulp transport and functional interface observations |
| Cementum–ligament–bone attachment | Human periodontal clinical comparisons | Oriented attachment and load transfer; clinical attachment gain and bone fill remain separate proxies |
| Gingival coverage and barrier | Small 2017 recession study | Barrier/seal and inflammatory recurrence outcomes with patient/site hierarchy retained |
| Whole-tooth shape, sensation and integration | Functional embryonic-mouse tooth reference | Adult-human construct evidence, occlusal function, host integration and durability |
| Genome-corrected stem-cell construct | Base-editing evidence interface | Declared lesion correction plus independently measured construct function; no inherited whole-tooth efficacy |

## What the full-text follow-up changed

The 2016 primary radiographic analysis reports p=0.742; clinical attachment is a
secondary three-month endpoint (p=0.371), rather than a twelve-month attachment
result. Forty-one treated teeth are nested within thirty patients. The analysis
uses modified per-protocol inclusion and last observation carried forward.
[Methods and Tables 2–3](https://pmc.ncbi.nlm.nih.gov/articles/PMC4761216/).

The 2025 stage-III result is a post hoc pooled contrast: AL change difference
−0.64 mm, 95% CI −1.23 to −0.05, at day 180. Methods specify tooth-level
analysis. The sign, subgroup and pooling must remain attached to the estimate;
it cannot become overall primary confirmation or independent patient replication.
[Clinical outcomes and Table 3](https://www.nature.com/articles/s41392-025-02320-w).

The 2026 ASC+PRP trial's primary radiographic endpoint favored ASC+PRP over EMD
at 36 weeks: 4.010 versus 2.105 mm, difference 1.905 mm (95% CI 0.383–3.427;
p=.0184; analysis n=8 vs 6). The full text reports no between-group CAL or
probing-depth difference at 12, 24 or 36 weeks; a within-arm CAL change does not
establish added benefit. The official registry clarifies flow as 16 consented,
one pre-treatment withdrawal and 15 treated (9 vs 6). See the
[source-scoped ASC+PRP review](ASC_PRP_TRIAL_REVIEW.md) and
[official registry](https://jrct.mhlw.go.jp/latest-detail/jRCTb030190173).
The trial calls its design therapeutic equivalence, but the retrieved Methods
state ordinary t-tests and no equivalence margin. No histology was obtained, so
the radiographic signal does not show oriented cementum–PDL–bone attachment.
Reported AE and SAE were in two different ASC+PRP participants and judged
unrelated by the authors; the small sample cannot establish rare-event safety.

The next useful computational work is source-data qualification: donor/clone/
batch metadata for organoid datasets, and participant-to-tooth mappings and
outcome-specific follow-up for clinical data. Public figures and summary means
cannot supply those mappings or a covariance matrix. No new confidence interval,
pooled effect or ranking is calculated here.

[endpoint_review.json](endpoint_review.json) preserves six observations in the
desk's existing source-record format. The controlled-periodontal starter loads
these as editable records, requiring source review before saving. Existing saved
campaigns and notes are not replaced. [Full-text receipts](fulltext_receipt.json)
identify three actual exact-article retrievals, and
[trial_registry_receipt.json](trial_registry_receipt.json) identifies the
official registry fetch. Source files remain private ignored literature files;
retrieval hashes are not placed in the dataset-hash field.

## Software verification

The latest one-off Docker workbench-image run completed 383 unit tests with six
optional tests skipped. All four dental/organoid track tests passed, including
seed parity, distinct endpoint intervals, the mixed-signal attachment summary,
registry denominator, and stable editable record IDs. The live desk was not
reloaded and saved user campaigns or notes were not changed by this update.
This validates software behavior, not tissue regeneration.

The live check additionally exposed a missing `jsonschema` dependency in the
research image: the CLI validator exited the HTTP request worker. The Dockerfile
now includes that dependency, and the desk turns such a validator exit into an
explicit invalid card instead of disconnecting. Twenty-two manifest tests and
four desk-track tests passed after this repair. The Experiments endpoint returned
HTTP 200 on the repaired local image. Docker Hub prevented the full clean rebuild
with authorization-service errors; the local repair added the dependency to the
existing image. Saved workspace content and notes were preserved.
