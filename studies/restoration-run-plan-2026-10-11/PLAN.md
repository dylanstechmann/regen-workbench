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

The initial quantitative source is [Komatsu et al., 2022](https://doi.org/10.1038/s41598-022-06865-6):
rat replantation with histology and mechanical extraction testing. At 21 days,
the reported failure energy was approximately 44% of uninjured controls even
though stiffness recovered more closely; area-standardized strength was about
76% as stated by the paper. Official Supplementary Table S3 confirms displayed
strengths of 2.45 and 3.39 N/mm², whose quotient is 72.27%; reconstructing the
table's group mean loads over representative-tooth areas gives 72.39%. The
supplement's values cannot explain 76%, and the source does not publish
per-tooth force-area records. Keep the conflict visible and unreconciled.
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

Qualify PDL age evidence separately. The 1999 human report links COL1A1 mRNA
and selected promoter methylation sites with age, but no donor-level public
tissue-age matrix was identified. Functional donor studies report age-related
PDLSC changes in proliferation, migration, lineage output and cell-sheet
matrix; a 2009 study reports improved aged-cell assays after young-donor
conditioned medium, while a 2012 ectopic-transplant study did not identify
cementum/PDL-like tissue in the two age groups included in its in-vivo
comparison. These are cell-source and niche hypotheses, not human attachment
repair. GSE227731 supplies a young-adult cell-identity reference; GSE306722
contrasts root maturity and osteogenic capacity, not chronological aging. See
the [PDL reference qualification](../aging-state-2026-10-11/PDL_AGE_REFERENCE_QUALIFICATION.md)
and [functional evidence table](../aging-state-2026-10-11/pdl_age_functional_evidence.tsv).
The focused source check found only the indexed abstract for Takatsu et al. and
no donor-level values or full methods; that study's sample count and donor
covariates remain unknown.

Do not repeat completed Salmon quantification merely to generate more tables.
Existing iPS-PDL libraries have one parental iPSC background and unresolved
source/batch mapping. GSE306722 has two group-level records with unknown donor
linkage, and its source maturity labels concern root development. Neither
limitation disappears through another marker score.

Deliverables: intake/hash receipts, biological-unit crosswalk, gene-coverage
table, a bounded gingival state-comparison report and a PDL age-reference
qualification. Report all prespecified axes; candidate programs must face
inflammatory and cell-composition alternatives.

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

- **D1 source qualification:** extracted one full-text rat PDL mechanics study and its fracture table; checksum-verified the official supplement and found that Table S3 confirms the displayed 2.45/3.39 N/mm² values but not the prose's 76% ratio. The supplement combines group mean load with one representative tooth area per group, so the 72.3–72.4% reconstruction is not an animal-level estimate. Reviewed the official page for the progenitor-driven reattachment study after its Europe PMC XML endpoint failed. Outcomes remain separate by study and loading protocol.
- **D2 reduced model:** built a source-anchored, two-point interpolation of rat crown displacement between published 10 N and 15 N means, plus a dimensionless stiffness non-identifiability sweep. The interpolation reproduces the measured endpoints and does not extrapolate; endpoint SD sensitivity ranges overlap. Both are explicitly limited models, not a human chewing or calibrated material model.
- **A1 broad age challenge:** trained age-direction panels inside repeated, age-stratified folds on GSE113957; transferred signs to matched GSE165177 samples; compared collagen, matrix, pluripotency, cell-cycle, p53/damage, acute-stress and inflammation axes by donor-coded line. The broad direction result is weak at the successful 13-day endpoint and based on two lines.
- **D3 oral aging input:** qualified GSE83382's processed gingiva matrix and GEO donor metadata, preserving the unresolved expression-alias-to-GSM mapping. Fixed matrix-turnover, matrix-inhibitor, structural ECM, inflammatory, epithelial, and stromal panels produce mixed group-level shifts in this three-versus-three, all-female bulk cohort. This is an exploratory input, not a gum-age clock; the donor-linked health/periodontitis comparison remains pending.
- **D3 comparator qualification:** linked 29 original GSE164241 single-cell libraries to the article's Table S1, separated the later 2023 `ID080UST` addition, and identified the paired healthy buccal/gingival samples plus repeated `PD161`/`PD164` disease biopsy codes. The 8 disease libraries represent five apparent donor-code groups; Cell Ranger versions differ across samples. This is an intake audit only; no cell-level pseudobulk or disease expression test has been run.
- **PDL age-reference qualification:** no donor-resolved adult human PDL tissue-age transcriptome passed the qualification gate. The literature does contain donor-derived PDLSC functional aging studies and a small young-conditioned-medium rescue report; one 2012 ectopic-transplant study did not identify cementum/PDL-like tissue in the two age groups used in its in-vivo comparison. These sources motivate an age-source-by-niche crossover, but no human in-socket restoration or tooth-position result follows from them. The [evidence table](../aging-state-2026-10-11/pdl_age_functional_evidence.tsv) keeps cell assays, graft outcomes, and mechanistic challenges separate.
- **D4 retained-tooth repair blueprint:** compared cell sheets, local cell-homing cues, multiphasic fiber-guiding scaffolds, layered factor carriers, a human PDL–bone microtissue, and the 2024 PDLSC-collagen root-surface construct. The 2024 study adds root-facing cell alignment and 4/10-week ectopic root-fragment observations, but no alveolar socket or physiological tooth loading; its in-vitro root-surface experiment did not observe new cementum. In-socket subluxation and intrusive-luxation injury models exist, but the reviewed regenerative attachment treatments were tested mainly in replantation/root-fragment or surgically created-defect settings. Human cohorts set a strong natural-healing comparator for mild subluxation and show different, root-maturity-dependent risks for displaced injuries. The [blueprint and evidence matrix](../periodontal-attachment-restoration-2026-10-11/IN_SITU_TRAUMA_REPAIR_BLUEPRINT.md) separate these tracks and identify baseline-registered position, load-bearing mechanics, and follow-up after temporary fixation withdrawal as the key combined gap.
- **Integration:** added the dental restoration contract and ranked experimental hypotheses, including explicit tooth position and post-support-removal stability.

This checkpoint has **not** completed the full 8–36-hour program. Remaining work is: preserve the 76% versus table-derived 72.3–72.4% conflict unless underlying data explain it; recover per-tooth displacement records and covariance if publicly or author-supplied; extend the response model only with defensible loading and material parameters; validate published subluxation/intrusive-luxation models with baseline-registered position and longitudinal functional measurements; qualify measurement repeatability and human donor inputs for the staged PDL-interface assay; run the donor-level cell-resolved oral disease challenge with processing-version and age sensitivity; and obtain a donor-resolved adult human PDL age cohort or underlying records. No human intervention has been designed or validated.


## PDL assay design checkpoint — 2026-10-11

Added an organoid-workbench experiment dossier with a staged root-facing to
two-interface human PDL model, machine-readable condition and endpoint matrices,
and explicit go/no-go logic. The main evidence update was the 2024 PDLSC-collagen
root-surface study: it showed aligned cells and ectopic root-fragment persistence,
but did not show new cementum in its in-vitro root-surface experiment, a
bone-facing insertion, orthotopic load-bearing repair, or positional recovery.
The assay design uses this as a benchmark, not as proof of functional PDL
regeneration. Numeric thresholds stay open until measurement repeatability and
matched-reference data exist.

## Cell-resolved oral-state checkpoint — 2026-10-11

Completed a donor-aware fixed-panel challenge using the curated CELLxGENE
GSE164241 gingival data. The original 21 gingival libraries contain 86,138
curated cells; after aggregating repeated disease biopsies to inferred sample-
code donor groups, the comparison is 13 healthy and 5 periodontitis donors.
The analysis verifies integer raw counts, audits all annotated cell sets,
records the inferred donor map and includes a Cell Ranger v3.0.1-only
sensitivity.

Within healthy fibroblasts, the frozen structural-ECM score trends upward by
about 0.17 mean-log1p(CPM) units per decade; matrix-degradation and
matrix-inhibitor age slopes are near zero with broad donor-bootstrap ranges.
Periodontitis raises the fibroblast inflammation, matrix-degradation and
matrix-inhibitor panels, while the structural-ECM score is approximately flat.
Inflammation also rises across epithelial, endothelial, dendritic and
perivascular groups. These exploratory expression patterns do not establish
protein activity, fiber insertion, epithelial seal, mechanics or regeneration.
The within-fibroblast age direction differs from the small bulk GSE83382
comparison; their designs and expression scales cannot be combined. Keep age
and inflammatory disease as separate assay challenges, and prioritize
donor-resolved adult PDL/gingival data plus functional attachment endpoints.

The [cell-resolved report](../aging-state-2026-10-11/GINGIVAL_CELL_RESOLVED_CHALLENGE_REPORT.md)
contains the contrast table and limits. Reproducible intake and analysis are
`fetch_periodontal_meta_atlas.py` and `analyze_gingival_cell_atlas.py`; compact
outputs are in the generated `derived/gingival-cell-atlas-GSE164241/` tables.

## Inflammatory assay extension — 2026-10-11

Translated that challenge into the staged PDL interface dossier: once the
two-sided fiber-insertion gate passes, compare a duration-matched control with
a separately qualified, literature-bounded periodontal inflammatory challenge
and washout. Record MMP and TIMP response together with cell survival, both
interfaces and mechanics. No stimulus, concentration or exposure duration is
selected without a measurement pilot. A gingival epithelial barrier remains a
separate module, and the inflammatory condition is not treated as an aging or
rejuvenation model. See the [assay dossier](../organoid/periodontal-ligament-interface/README.md)
and its condition and endpoint tables.

## PDL age-by-niche experiment update — 2026-10-11

The functional-source audit found donor-derived human PDLSC studies of age-
associated proliferation, migration, lineage and cell-sheet matrix changes,
plus a 2009 young-cell-conditioned-medium rescue result. A 2012 ectopic
transplant comparison is an important counterexample: its two in-vivo age
groups did not produce identified cementum/PDL-like tissue. The literature
therefore supports testing a reversible cell-source-age × niche-source-age
effect, not assuming age-associated cell assays transfer to a repaired
attachment.

Added a six-condition donor-crossed design to the PDL assay dossier: younger-
and older-adult PDL cells in matched unconditioned medium, plus both cell-age
strata exposed to independently sourced younger- or older-adult donor
conditioned medium. The assay retains exact age, root maturity, health,
extraction indication, sex, passage and batch, uses each donor as the
biological unit, and checks cell identity, bilateral fiber insertion and
mechanics after washout. The conditioned-medium exposure is an undefined
historical benchmark, not a therapeutic candidate; fixed donor cutoffs and
exposure settings await cohort and assay qualification. See
[`age_by_niche_test.tsv`](../organoid/periodontal-ligament-interface/age_by_niche_test.tsv)
and the [functional-source audit](../aging-state-2026-10-11/pdl_age_functional_evidence.tsv).

The Li et al. 2020 supplementary expression workbook does not provide a
donor-by-gene matrix; the paper reports a `p < 0.05` or fold-change `> 2`
microarray screen and discordant qRT-PCR directions for three selected
transcripts. Do not train an age panel or nominate a rejuvenation target from
that workbook. The age-by-niche follow-up now has a donor-level estimand and
analysis contract, including age-overlap and tooth-source confounding checks:
[`analysis plan`](../organoid/periodontal-ligament-interface/age_by_niche_analysis_plan.md).
