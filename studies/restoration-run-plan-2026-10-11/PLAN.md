# Dental restoration and durable youthful function: next 8–36-hour run

Planning date: 2026-10-11. AI-assisted research and engineering proposal for the
owner's personal computational projects. This document specifies work to run;
it does not report that the proposed analyses or interventions have succeeded.

## Objective and allocation

The flagship question is: **Can a damaged natural tooth regain its intended
position, living cementum–periodontal-ligament–bone attachment, gum architecture,
and physiological function, with stable position after temporary support is
removed?** Freedom from lifelong external retention is a desired durability
endpoint. Any finite positioning or healing support is an engineering variable
whose withdrawal must be followed by measurements of stability.

Allocate approximately 60% of a sustained work window to dental restoration,
30% to challenging the existing cellular-aging result, and 10% to repair
coverage and integration. The horizons below are cumulative scope targets,
conditional on qualifying inputs. They are computational work products, not a
promise of human tissue regeneration within that time.

The long-term objective is sustained healthy adult function throughout the
body, preserving personal anatomy, specialized cell identity and useful
acquired information. A low biological-age score is a supporting observation.
The acceptance criterion is durable recovery of the relevant tissue function.

## Why dental trauma is the first engineering case

Dental trauma is more varied than stretched ligament. The IADT describes
displacement, socket-wall injury, bone damage and risks to the pulp in different
injury categories. Our engineering states should therefore distinguish
attachment disruption, tissue loss, altered geometry and impaired vitality.
[Primary IADT injury descriptions](https://doi.org/10.1111/edt.12578).

Regenerating an attachment around a displaced tooth could preserve the wrong
position. The target must combine geometry with biological repair. If actual
pre-injury imaging is absent, an estimate based on earlier records, adjacent
teeth or a reference anatomy must carry explicit uncertainty; it cannot silently
become the person's exact original geometry.

The mouth is a useful flagship because several difficult interfaces must work
together: mineral–soft tissue attachment, mechanical loading, epithelial seal,
perfusion, sensation, spatial organization and continued exposure to microbes.
The same design discipline can later apply to tendon–bone attachment, cartilage,
skin, vessels and organ constructs, while their parameters and success criteria
remain tissue specific.

## Work package D1: define restoration and extract actual functional evidence

**Question:** Which published interventions recover attachment function, and
what important deficits remain?

Create a restoration contract covering:

| Domain | Required evidence | Competing outcome to retain |
|---|---|---|
| Tooth position and bite | Three-dimensional position/rotation relative to a declared target; occlusal compatibility; stability after support removal | Correct support around the wrong position; recurrent drift |
| Cementum–PDL–bone | Fibers inserting into both interfaces; continuous ligament space; organized orientation; physiological mobility | Scar, detached fibers, excessive bone, ankylosis or root resorption |
| Attachment mechanics | Matched loading regime; force–displacement; compliance, failure load and energy; creep/recovery where measured | Apparently firm fixation with abnormal mechanics |
| Gingiva | Margin, volume, papillae, appropriate phenotype, seal/barrier, inflammation and recurrence | Coverage alone, long junctional epithelium or unstable contour |
| Enamel and dentin | Geometry, native-like microstructure, bonding, hardness, wear and fatigue behavior | Mineral deposits without a functional tooth surface |
| Pulp and neural support | Viable vascularized tissue, sensory function and continued host integration | Calcification, necrosis or absent functional integration |

The initial quantitative source is [Komatsu et al., 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC8881622/):
rat replantation with histology and mechanical extraction testing. At 21 days,
the reported failure energy was approximately 44% of uninjured controls even
though stiffness recovered more closely; area-standardized strength was about
76% as stated by the paper. The reported rounded values 2.45 and 3.39 N/mm²
divide to 72.3%, so the discrepancy is preserved for source clarification.
These are distinct short-term mechanical outcomes in a specific animal model,
not human chewing performance or long-term positional stability.

Qualify [Dangaria et al., Apatite Microtopographies, 2011](https://doi.org/10.1089/ten.TEA.2010.0264)
as a separate mechanical-source comparison. Do not confuse it with the already
reviewed root-preseeding paper. Differences in applied loads and comparator
attachment must remain visible.

Deliverables: `restoration_contract.json`, `attachment_function_benchmark.tsv`,
`SOURCE_QUALIFICATION.md` and recovery-ratio plots. Each row retains species,
injury model, animal/tooth hierarchy, time, loading method, source table/figure,
units and missing outcomes. Prefer supplied numeric data. Digitized values are
labelled estimates with extraction uncertainty. Summary data cannot supply
individual observations or otherwise unavailable confidence intervals.

**Completion gate:** at least one qualified source-based functional comparison;
no invented universal recovery cutoff or pooled human/animal efficacy ranking.

## Work package D2: a reduced tooth–attachment mechanics study

**Question:** Which combinations of geometry, attachment coverage and tissue
organization can recover useful compliance without instability or fusion?

Build a small reproducible study script using a tooth/root and socket geometry
with an oriented, compliant attachment layer. Start with a limited loading
direction; extend to rotation/lateral loading only if the parameter basis and
time permit. This is a reduced model, not a personalized digital twin.

Compare an intact reference with disrupted attachment, misoriented fibers,
shifted geometry, partial repair, altered support height and bone-bridge states.
Sweep attachment fraction, ligament width, fiber orientation and constitutive
parameters across source-based ranges. Clearly mark any illustrative range.
Use relaxation/creep behavior only where a defensible viscoelastic parameter
source exists; a destructive extraction experiment does not calibrate normal
chewing or every loading direction.

Deliverables: study code, parameter-source table, reproducible scenario manifest,
force–displacement figures, sensitivity maps and `MODEL_LIMITS.md`. Check units,
equilibrium, limiting cases, numerical convergence and parameter identifiability.
Show whether attachment area and material stiffness can be distinguished from
the available measurements. Synthetic verification cases remain labelled.

**Falsifiers:** the intact baseline cannot reproduce the matching reference
regime; apparent benefits reverse across defensible ranges; a rigid bone bridge
is incorrectly scored as successful ligament; restored mechanics occur only
with wrong geometry. A separate uncertainty on remodeling governs claims about
long-term drift: a static mechanics model cannot establish lifetime retention.

## Work package D3: gum aging, inflammation and cell-source qualification

**Question:** Do the candidate youthful features reflect adult tissue state,
inflammation, cell mixture or developmental immaturity?

Qualify [GSE83382](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE83382),
which exposes six human gingiva records labelled young/old. Audit donor identity,
sampling conditions, age metadata and the actual processed-value transformation
before analysis. If eligible, calculate descriptive effect sizes for fixed
matrix-turnover, inflammatory, epithelial and fibroblast programs. This small
study cannot supply a robust universal gum-age predictor.

Use [GSE164241](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE164241),
the human oral-mucosa health/periodontitis atlas, as a candidate inflammatory
comparison. Qualify its donor-to-library map before donor-level pseudobulk.
Keep gingival fibroblast and epithelial populations separate. A developmental
tooth reference such as GSE184749 supplies lineage context, not youthful adult
ground truth.

Do not repeat completed Salmon quantification merely to generate more tables.
Existing iPS-PDL libraries have one parental iPSC background and unresolved
source/batch mapping. GSE306722 has two group-level records with unknown donor
linkage, and its source maturity labels concern root development. Neither
limitation disappears through another marker score.

Deliverables: intake/hash receipts, biological-unit crosswalk, gene-coverage
table and a bounded state-comparison report. Report all prespecified axes;
candidate programs must face inflammatory and cell-composition alternatives.

**Completion gate:** eligibility is documented before inference. If the donor
map or expression scale remains unresolved, deliver a qualification report and
limited descriptive result rather than substitute samples for donors.

## Work package A1: challenge the existing reprogramming result

**Question:** Does the response extend beyond collagen and remain compatible
with healthy adult fibroblast identity after withdrawal?

Reuse the qualified GSE113957 age-reference and GSE165177 intervention inputs.
Freeze analysis axes before inspecting new treatment-panel results: broad
adult age direction, extracellular matrix, fibroblast identity, pluripotency,
cell cycle, inflammation/stress and a source-defined senescence program.
Expression alone cannot establish senescence or malignant behavior; these are
alternative-state screens.

Select and weight age-associated genes only within reference training folds,
with donor-level held-out evaluation. Exclude HGPS and childhood development
from the primary adult reference. Retain age-range, sex, biopsy-site and
available culture/batch sensitivities; record missing covariates. On the
intervention data, preserve donor/experiment/duration matching and the
successful/failing intermediate and post-withdrawal comparisons.

The primary output is broad age-direction concordance with donor-level effects,
not a newly invented estimate of years younger. Include expression/size-matched
random panels, collagen/ECM-excluded sensitivity and leave-one-donor checks.
With three intervention donor lines, sampling uncertainty stays substantial.

Audit clock transfer separately. [Gill et al.](https://elifesciences.org/articles/71624)
report that existing transcription clocks poorly predicted negative controls,
then trained a custom predictor after batch correction to the intervention
dataset. Reproduce only what the source code and inputs allow. Compare a fixed
reference-only transform with any reproducible joint harmonization; record
which observations influence feature choice, scaling and batch estimation.
Resolve the exact training accession, feature mapping and processing against
the original author code before claiming a reproduction. Inspect control-age
calibration and sensitivity. This investigates a transfer
dependency without presuming that the paper's conclusion is wrong.

If time and metadata qualification permit, apply frozen panels to
[GSE297233](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE297233),
an eight-library reprogramming series from one 96-year-old male fibroblast
donor. It can challenge direction in another series, but cannot validate donor
generality or post-withdrawal durability.

Deliverables: `BROAD_STATE_ANALYSIS_PLAN.json`, gene-level paired effects,
held-out reference metrics, panel/normalization sensitivity figures and
`CLOCK_TRANSFER_AUDIT.md`.

**Falsifiers:** age agreement disappears when ECM genes are removed; failing
intermediates reproduce the same apparent benefit; the conclusion depends on
one donor or harmonization choice; identity recovery is incomplete. Retain a
negative or mixed outcome as the result.

## Work package I1: repair architectures and body-wide translation

Compare three attachment hypotheses: root-localized progenitor/cell placement,
spatial cementum–ligament–bone guidance, and local cell-free repair cues. Rank
them by demonstrated endpoints, manufacturability, spatial control, integration
and the missing measurement most likely to change the ranking. Favoring one
requires evidence for both attachment interfaces and mineralization boundaries.

Keep gum reconstruction, enamel/dentin material development, vascularized pulp
and whole-tooth replacement as distinct connected modules. Specify the missing
material, geometry, perfusion, innervation and durability measurements for each.
New organoid software is useful only when it resolves one of those questions.
Existing oxygen models need measured inputs for calibration; existing image
tools need genuine reviewed masks and valid biological-unit metadata.

For other body systems, apply the same repair contract:

| Repair axis | Next engineering question | Functional gate |
|---|---|---|
| Nuclear/mitochondrial sequence damage | Which lesion is causal in which cell population, and is correction or replacement preferable? | Intended repair, surviving cells, clone behavior and restored tissue function |
| Cell-state dysfunction | Can specialized adult function be restored and maintained after the intervention ends? | Identity, function, controlled proliferation and durability |
| Senescence/inflammatory niche | Which dysfunctional cells can be removed or repaired without exhausting replacement capacity? | Resolution, useful-cell preservation and recovered function |
| ECM, deposits and interfaces | Which structure is missing or harmful, and how is it remodeled without scar or fusion? | Tissue-specific composition, mechanics, geometry and turnover |
| Cell loss and organ architecture | Can appropriate mature cells be assembled and connected to the host? | Perfusion, sensory/electrical/mechanical integration and persistence |
| Delivery and accessibility | How much of the intended compartment is reached with active cargo? | Correctly repaired functional target cells, rather than organ accumulation alone |

In `base-editing-evidence`, extend the existing denominator discipline through
intended-cell uptake, intracellular activity, intended-only product, survival
and tissue function. Use source measurements to build the coverage chain;
unknown stages remain unknown. Allele fractions, edited-cell fractions and
functional tissue fractions are different denominators. A monogenic correction
does not identify which distributed somatic mutations of ordinary aging should
be corrected. Do not impose a universal linear coverage-to-function rule.

Deliverables: 2–3 ranked dental hypothesis cards, `REPAIR_COVERAGE_FUNCTION_MAP.tsv`
and a discriminating study-design brief. For neural tissue, preserve memory and
learned organization explicitly in the target; generic developmental resetting
does not satisfy that contract.

## Cumulative checkpoints and scope control

| Horizon | Committed scope | Conditional extension |
|---|---|---|
| 8 hours | Restoration contract; at least one functional dental-source benchmark; initial reduced mechanics baseline; frozen broader-aging plan and input audit | First source-qualified numerical contrast if inputs permit |
| 16–24 hours | Mechanical scenario/sensitivity study; broad paired aging-state results and competing-state checks; dental architecture comparison | One qualified gingival-state analysis |
| 36 hours | Source/model uncertainty audit; independent mechanical comparison where comparable; clock-transfer sensitivity; ranked hypotheses and next decisive measurements; reproducible report bundle | One independent reprogramming-series check or a measured delivery/coverage audit; choose the stronger eligible input |

The run should yield two substantial quantitative studies—attachment mechanics
and broad cellular-state response—plus a focused integration map. Full human
tooth morphogenesis, personalized FE validation, whole-body editing, organoid
clinical performance and long-term unsupported position stability require
additional measurements and experiments beyond this window.

Use read-only parallel research roles with one implementation owner per working
tree. Keep methods packages in their existing repositories; do not merge them.
Excluded projects remain uniStemCourseSimulators, CAD, artificial-womb models
and AI_Companion. Use local CPU analyses and cached matrices first. No paid
compute dependency is needed for the core scope.

At each checkpoint, save code, exact input hashes, assumptions, source units,
failed hypotheses and outputs. Public updates should credit source work and
identify agent-run analyses. Preserve private ResearchDesk observations and
raw data in their existing ignored stores. Tests and numerical checks establish
software behavior; biological restoration requires its own measured evidence.

Finish the run with the results that survived challenges, the results that
failed, and the highest-value next measurement. The immediate advance is a
clearer, quantitatively tested route toward functional restoration, with a
record of exactly what remains unproven.

## Run checkpoint — 2026-10-11

The first execution checkpoint is complete and saved in the workbench:

- **D1 source qualification:** extracted one full-text rat PDL mechanics study and its fracture table; reviewed the official PMC page for the progenitor-driven reattachment study after its Europe PMC XML endpoint failed. The recovered functional outcomes remain separate by study and loading protocol.
- **D2 reduced model:** built a source-anchored, two-point interpolation of rat crown displacement between published 10 N and 15 N means, plus a dimensionless stiffness non-identifiability sweep. The interpolation reproduces the measured endpoints and does not extrapolate; endpoint SD sensitivity ranges overlap. Both are explicitly limited models, not a human chewing or calibrated material model.
- **A1 broad age challenge:** trained age-direction panels inside repeated, age-stratified folds on GSE113957; transferred signs to matched GSE165177 samples; compared collagen, matrix, pluripotency, cell-cycle, p53/damage, acute-stress and inflammation axes by donor-coded line. The broad direction result is weak at the successful 13-day endpoint and based on two lines.
- **Integration:** added the dental restoration contract and ranked experimental hypotheses, including explicit tooth position and post-support-removal stability.

This checkpoint has **not** completed the full 8–36-hour program. Remaining work is: resolve the paper's 76% versus rounded-value 72.3% strength discrepancy from source data; recover per-tooth displacement records and covariance if available; extend the response model only with defensible loading and material parameters; qualify oral-cell donor mappings and age references; and connect tissue-specific state panels to organoid or construct function. No human intervention has been designed or validated.
