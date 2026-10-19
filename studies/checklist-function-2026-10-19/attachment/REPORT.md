# Attachment function: an executed mechanics audit, with donor-age gaps retained

This batch shifts from transcript directions to physical function. It executes
a numerical audit of printed human-cell construct and native-PDL summaries.
**No accessed source qualifies for donor-age-by-niche analysis or for jointly
verified regenerated attachment and physiological recovery.** The new result
is a concrete distinction between active contraction, passive tissue mechanics
and durable tooth attachment, with every available numerical row retained.

The [plan](analysis_plan.json) is post-source exploratory. The three-source set
was frozen after inspection; no additional cohort, download retry, contact,
wet-lab work or treatment protocol was pursued.

## Human PDL constructs: force and recovery are different observations

[Mulimani et al. 2024](https://doi.org/10.1177/00220345241264792) embedded a
heterogeneous, healthy-donor PDL-cell population in collagen between silicone
posts. The accessed article describes one donor, without numeric age or sex;
construct counts do not create independent people. This is not a purified
PDLSC age cohort or a root-cementum/bone attachment model.

The reported means imply **777 micrometres shortening, or 9.7125%**, relative
to the acellular reference. Multiplying shortening by the modeled post
stiffness gives **738.15 micronewtons**, versus 739 reported: a 0.115% difference.
The bare-post calculation reproduces 408.5 micronewtons exactly. Force and
length are algebraically linked here; agreement does not independently
validate contractility. Original SEM labels are retained; no uncertainty in
post stiffness, recovery distribution or unsupported sample size is supplied.

The article reports partial recovery at 4 h, persistent deformation at 24 h and
creep at 1 week. The figure caption gives 5/6/6 constructs for stretch/release
panels, but individual before/during/after lengths were not obtained. We do
not reconstruct numerical recovery fractions from qualitative descriptions
or combine different panels into a same-construct joint endpoint.

## Native human attachment: the reference depends on the test regime

[Wu et al. 2018](https://doi.org/10.1186/s12938-018-0607-0) tested 18 slices
from 6 incisors from 3 male cadavers aged 31–52. All six Table 2 rows are
transcribed with their SDs in the [source extract](source_summary_extract.json).
Individual ages and donor-to-tooth-to-slice mapping are unavailable. Four
cycles per test are repeated observations.

| Peak force / loading rate | Tooth class | E1 mean ± SD, MPa | E2 mean ± SD, MPa | E2/E1 ratio of means |
| --- | --- | ---: | ---: | ---: |
| 1 N / 1 N·min⁻¹ | Central incisor | 0.67 ± 0.45 | 2.63 ± 0.51 | 3.925 |
| 1 N / 1 N·min⁻¹ | Lateral incisor | 0.33 ± 0.20 | 2.32 ± 1.15 | 7.030 |
| 3 N / 3 N·min⁻¹ | Central incisor | 1.16 ± 0.73 | 4.50 ± 1.01 | 3.879 |
| 3 N / 3 N·min⁻¹ | Lateral incisor | 0.52 ± 0.30 | 2.75 ± 1.16 | 5.288 |
| 5 N / 5 N·min⁻¹ | Central incisor | 1.82 ± 1.07 | 5.59 ± 1.23 | 3.071 |
| 5 N / 5 N·min⁻¹ | Lateral incisor | 0.81 ± 0.36 | 4.14 ± 1.31 | 5.111 |

Between the 1 N and 5 N regimes, E1 means rise 2.716-fold centrally and 2.455-fold
laterally; E2 means rise 2.125-fold and 1.784-fold. Peak force and loading rate
change together, so this does not isolate a rate effect. Ratios of group means
are not distributions of donor-paired ratios.

Published branch means span 0.33–5.59 MPa. The discussion's 6.82 MPa upper value
equals 5.59 + 1.23, the largest E2 mean plus its SD; no individual extreme can be
recovered. The source's “ultimate strain” is the bilinear transition described
in its methods, not an observed rupture threshold. Neither range supplies a
healthy-function acceptance band.

## Exact endpoint eligibility

| Required question | Magnetic construct | Native tensile reference | Viscoelastic PDLSC source |
| --- | --- | --- | --- |
| Traceable individual donor age and age-by-niche crossing | Missing | Missing individual ages/crosswalk; no niche crossing | Six donors aged 18–30; individual crosswalk and age crossing missing |
| Numerical mechanics available here | Printed active-force/calibration summaries | All 6 passive tensile summary rows | Context only; underlying data on request |
| Numerical per-construct stretch/release recovery | Not obtained | Not a construct-recovery series | Not obtained |
| Regenerated fibers inserted at both mineralized interfaces, jointly linked to mechanics | Silicone posts; absent | Native anatomy present, no numerical insertion/mechanics crosswalk | Not established as a joint physiological endpoint |
| Original tooth position after finite support withdrawal | Not measured | Not measured | Not established |

[Zhang et al. 2024](https://doi.org/10.1002/advs.202309562) supplies relevant
human PDLSC niche context, but cultured-cell responses, material rheology and
separate rat replantation histology do not establish human attachment function.
Hydrogel stiffness and relaxation vary together. Its data statement offers
underlying data on request; no author was contacted, animal outcomes were
not pooled with human assays, and no age effect was estimated. The complete
[source qualification](source_qualification.json) preserves model, unit,
access and endpoint limits.

## What changes in the restoration decision

An active force reported in micronewtons is not a passive elastic modulus
reported in MPa. The post is a sensor/support, not the tissue. The analysis
explicitly withholds a tissue-modulus conversion: matched tissue geometry
and a passive tissue force–displacement slope are missing. A large force,
increased stiffness or aligned collagen cannot independently pass attachment.

The next useful dataset must connect **the same donor-derived construct** to
its geometry, independently varied niche, insertion at both mineralized
interfaces and recoverable mechanical response. A valid native comparator
requires matched fixture, anatomical region, loading regime and tissue state;
these cross-source numbers do not establish equivalence. Exact donor age and
donor/construct/batch IDs are required before age-by-niche effects are tested.

Permanent original tooth pose remains a separate orthotopic outcome, alongside
living PDL/cementum/socket attachment, youthful gums, pulp and original tooth
substance/architecture. Construct recovery after stretch cannot establish that
a damaged tooth returns to its original position or stays there after support
is removed. These are unresolved required endpoints, not surrogate successes.

## Reproduce and inspect

```text
python -B studies/checklist-function-2026-10-19/attachment/analyze_mechanical_summaries.py
python -B -m unittest discover -s tests -p test_checklist_function_attachment.py -v
```

The default analysis uses committed aggregate extracts and the standard
library. `extract_numeric_summaries.py` repeats extraction from the ignored
cache and verifies all four actual response hashes; analysis `--verify-cache`
also checks them. [Results](derived/mechanical_summary_results.json) and the
[analysis receipt](derived/analysis_receipt.json) pin inputs, plan and scripts.

[Fetch receipts](source_receipts.json) distinguish three obtained primary
documents from a retained 1816-byte HTML download-challenge response advertised
as DOCX. It is **not** counted as an obtained supplement. XML HTTP 500 and
publisher HTTP 403 attempts have no fabricated payload hashes or fetch receipts.
Raw files stay in the explicitly scoped ignored cache
`data/literature/checklist-function-2026-10-19/attachment/`; no challenge was
bypassed and no further retry was made after freezing the source set.

Source observations belong to their authors. Wu et al.'s numerical table is
attributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
No source figures or article text are redistributed. These are original
calculations on published aggregate observations, not new constructs or
wet-lab findings. Docker workbench remains stopped.
