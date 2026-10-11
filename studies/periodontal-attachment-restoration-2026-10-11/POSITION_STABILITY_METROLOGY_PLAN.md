# Position stability after tooth trauma: measurement qualification plan

## Decision

The next gate is to qualify how tooth position will be measured before comparing repair strategies. The target is not simply low mobility or a good-looking crown: it is recovery toward the tooth's declared pretreatment six-degree-of-freedom pose in a stable jaw coordinate frame, followed by low drift after temporary positional support is removed. Attachment and position remain separate outcomes. A tooth can be correctly positioned but ankylosed, or have a functional ligament while healing in a displaced position.

This is a research measurement plan, not a patient-care protocol. It does not establish a human regenerative treatment or authorize extra imaging. Acute trauma care stays with qualified dental professionals; any animal or human research requires institutional review and imaging justification.

## Why measurement qualification comes first

A 2024 study of 34 orthodontic patients compared serial digital dental models registered on the hard-palate region with 3D CT models registered on the cranium. Within the same operator, repeat-measurement standard errors were under 0.15 mm for dental-model displacement and under 0.20 mm for CT displacement; angular errors were 0.43° and 0.75°. But agreement between the two workflows was wider: the central-incisor axis-specific 95% limits of agreement were about 0.73–0.91 mm, and angular limits were 3.56°. This was an orthodontic movement study, not a trauma validation. It supports repeatability testing and consistent modality use, not a claim that a submillimeter movement is detectable in an injured tooth. [Kubota et al., 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11405094/)

For scale only, applying `MDC95 = 1.96 × sqrt(2) × SEM` to the published same-operator standard errors gives approximate analysis-only detectable changes of 0.17–0.25 mm for the central incisor and 0.30–0.42 mm for the first molar with digital-model analysis; the corresponding CT values are 0.33–0.53 mm and 0.39–0.55 mm. The central-incisor angular estimates are approximately 1.19° and 2.08°. These are derived from repeat measurements of existing scans, so they omit scan/reposition variability and are not trauma-specific thresholds. Cross-method limits of agreement (0.73–0.91 mm and 3.56°) are materially wider. The exact axis-level source SEMs and derived MDC95 values are recorded in [`position_mdc95_derived.tsv`](position_mdc95_derived.tsv); evidence scope and limitations are in [`position_error_budget.tsv`](position_error_budget.tsv).

Those error values cannot be imported as acceptance limits. The digital scan measures the visible crown and a maxillary palatal registration region; it does not measure root position inside the socket. The CT results came from a specific patient population and registration pipeline. Lower-jaw, growing, injured, splinted, and root-level measurements need separate qualification. Do not subtract an intraoral-scan pose from a CT pose and call the difference biological drift.

The IADT's permanent-tooth trauma guideline treats injury class and root development as consequential strata, calls for serial clinical/radiographic follow-up, and describes imaging as question-dependent. It is a 2020 consensus guideline for urgent care, not a research serial-imaging authorization. [IADT guideline, endorsed by the AAPD](https://www.aapd.org/research/oral-health-policies--recommendations/guidelines-for-the-management-of-traumatic-dental-injuries-1-fracture-and-luxations-or-permanent-teeth/)

## Target estimand and injury strata

For each target tooth, estimate two things separately:

1. **Residual pose error:** the rigid-body transform from the target tooth at baseline to each follow-up, expressed relative to a declared stable jaw reference. Report translation (mesiodistal, buccolingual, and axial) in millimeters and rotation (tip, torque, and rotation) in degrees. Report root pose when the imaging modality can resolve the root; crown pose is a distinct secondary measure.
2. **Post-support drift:** change in pose from the first prespecified observation after support removal to later observations. Also report the difference from baseline at each observation. Support state and elapsed time since removal are mandatory fields.

Do not pool concussion/subluxation, extrusion, lateral luxation, intrusion, avulsion/replantation, root fracture, or alveolar fracture into one model. Record open versus closed apex and combined crown/pulp injury. Simple subluxation mainly tests attachment recovery with a retained tooth; displacement injuries test whether a new position persists or drifts. Replantation tests severe root-surface injury and is not a substitute for in-socket displacement. Human natural-history cohorts and animal models define different comparator questions and must stay labeled as such.

When no true preinjury image exists, label the target source as `prior_clinical_record`, `contralateral_anatomic_proxy`, or `model_defined_baseline`. A contralateral tooth or mirrored anatomy is only a proxy: record its uncertainty and never report it as the individual's measured original position.

## Measurement stack

| Stage | Measurement | Reference frame | Main error to estimate | Output |
|---|---|---|---|---|
| Bench fixture | Ex-vivo tooth/socket phantom on a calibrated translation/rotation stage; impose known small shifts and rotations, including zero-motion repeats | Fixture fiducials and known stage coordinates | Acquisition, segmentation, registration, and pose-recovery error | Bias, repeatability SD, 95% limits of agreement, and smallest reliably resolved translation/rotation by axis |
| In-situ animal model | Baseline and follow-up root/socket volumes only under an approved imaging plan; separate crown scans may improve frequent surface tracking | Uninjured local bone ROI for root-to-socket pose; jaw ROI for jaw-frame pose | Repositioning, partial-volume, registration, segmentation, tooth growth, and radiation-related study effects | Root and crown pose with uncertainty; tooth position stays separate from tissue histology and force response |
| Human observational bridge | Use pre-existing or clinically acquired records and serial optical scans when available; use radiographic modalities only when clinically justified or separately approved | Stable, unaffected jaw/palatal ROI; target tooth excluded from registration | Missing true baseline, modality changes, splint/restoration artifacts, growth, and acquisition interval | Descriptive residual pose and drift, stratified by trauma type and root maturity; no causal claim of regeneration |

**Reference selection:** register the jaw using unaffected hard-tissue regions and exclude the injured tooth, its socket if remodeled, splint material, and any region altered by the injury from the registration mask. For maxillary optical models, palatal registration can be a candidate when the palate is unchanged; the published orthodontic evidence does not validate this for mandibular trauma or injured palatal tissue. For lower teeth, crown-only scans need a validated stable mandibular reference or should be treated as local relative movement rather than absolute jaw pose. For root position, use a modality and registration method that can actually resolve root and socket; do not infer it from a crown surface.

**Imaging policy:** do not acquire repeated ionizing scans solely to make a dense time series by default. In preclinical work, evaluate whether serial imaging, endpoint-only imaging, and sham-imaged controls are needed to quantify imaging effects. In people, use existing/clinically indicated images unless an ethics-reviewed protocol separately justifies additional exposure. The IADT guideline is a care guideline, not permission for a research imaging schedule.

## Qualification sequence and pass rules

1. **Lock the estimand and coordinate convention.** Fix axis signs, units, tooth pose representation, baseline source, target tooth, registration mask, support states, and timepoints before reading treatment outcomes. Store all six pose components; a single “distance from ideal” number can hide direction and tipping.
2. **Build truth-known fixtures.** Use a calibrated stage and scan/reposition/re-scan cycles. Test zero motion, translations, and rotations spanning the intended injury/recovery range. Have blinded raters repeat segmentation and registration. Avoid selecting only shifts that the algorithm handles well.
3. **Partition the error.** Estimate acquisition/repositioning, segmentation, registration, and rater components separately, then estimate combined 95% repeatability limits. A same-volume reanalysis isolates rater/segmentation error; scan/reposition cycles capture acquisition plus pipeline error; known fixture displacement tests accuracy and bias.
4. **Predefine the smallest biological change of interest.** No source reviewed here establishes a trauma-specific meaningful pose margin. Select the margin from the model's target displacement and the restoration contract, then require the empirically measured 95% uncertainty to be smaller than that margin before the method can test the hypothesis. Freeze the margin before intervention comparisons. Do not use correlation or intraclass correlation alone as proof of adequate absolute precision.
5. **Freeze a modality for longitudinal inference.** If modalities must change, run a paired bridge study and carry the empirically measured cross-method limits into uncertainty. Otherwise, report measurements as non-comparable rather than interpret the modality step as drift.
6. **Advance to biology only after metrology passes.** The injury model then needs a natural-healing comparator, an established positional-support comparator, prespecified support withdrawal, follow-up both soon after withdrawal and later, and separate attachment/safety outcomes. A “position-restored” result must also pass the independent cementum–PDL–bone, physiologic mobility, ankylosis/resorption, pulp, and gingival gates in the restoration contract.

Do not set numeric acceptance margins from the orthodontic paper. Its repeated-measure errors are useful planning anchors only. The benchmark must report the empirically qualified error for its own equipment, model, tooth class, and analysis pipeline.

## Analysis and reporting contract

- Use per-tooth rigid transformations relative to the stable jaw frame. Report the translation vector, three rotations, derived Euclidean translation, and measurement uncertainty. Keep root and crown estimates in distinct columns.
- Preserve raw meshes/volumes, acquisition metadata, registration masks, transforms, software/version, segmentation reviewer, and blinded repeat identifiers. Hash source images or store governed links; do not commit protected human images.
- Quantify measurement repeatability with within-subject SD and 95% limits of agreement. For a scalar component with same-method SEM, the conventional `MDC95 = 1.96 × sqrt(2) × SEM` is a descriptive detection limit under its assumptions; for six-dimensional pose, estimate component-wise limits and a validated joint pose region rather than treating axes as independent by default.
- Model longitudinal observations with time since injury and time since support removal, injury class, root maturity, and baseline source explicit. Subjects/animals, teeth, image acquisitions, raters, and repeated observations need their correct nested structure. Never turn group means or serial frames into independent biological replicates.
- The primary durability outcomes are residual pose error versus the declared target and post-support drift across later visits, reported as separate estimands. Attachment and safety outcomes accompany both. Reduced mobility, stable short-term position while splinted, marker shifts, or histology alone do not satisfy restoration.
- Report missing baselines, invalid registration, image artifacts, resorption, ankylosis, and exclusions before summarizing treatment differences. Retain failures in the denominator.

## Data template

The companion [`position_tracking_data_dictionary.tsv`](position_tracking_data_dictionary.tsv) defines the minimum row-level record for a future dataset. It is a schema, not fabricated observations. The literature-derived uncertainty anchors and their limits are in [`position_error_budget.tsv`](position_error_budget.tsv).

## Next execution gate

Start with an ex-vivo known-motion phantom and blinded repeat registration using the same image modality end-to-end. If the achieved limits cannot resolve the prespecified movement margin, improve the acquisition/registration pipeline before advancing to intervention biology. Once qualified, use the direct retained-tooth impact model for subluxation/stretch and a separate validated luxation model for actual displacement; neither is a human treatment recommendation. Include a long post-support observation because short-term alignment cannot establish durable restoration.

### Sources

- Kubota R, et al. *Analysis of Three-Dimensional Tooth Movement: A Comparative Study Between Digital Dental Models and Craniofacial Models.* 2024. [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC11405094/) · [DOI](https://doi.org/10.7759/cureus.67094).
- Bourguignon C, et al. *International Association of Dental Traumatology guidelines for the management of traumatic dental injuries: 1. Fractures and luxations.* 2020. [AAPD-hosted guideline](https://www.aapd.org/research/oral-health-policies--recommendations/guidelines-for-the-management-of-traumatic-dental-injuries-1-fracture-and-luxations-or-permanent-teeth/) · [DOI](https://doi.org/10.1111/edt.12578).
- Experimental subluxation and occlusal-loading model, 90 Wistar rats, 7- and 21-day endpoints. [PubMed record](https://pubmed.ncbi.nlm.nih.gov/38420008/).
- Experimental immature-rat intrusive-luxation model with micro-CT and histology through 90 days. [PubMed record](https://pubmed.ncbi.nlm.nih.gov/32771418/).
