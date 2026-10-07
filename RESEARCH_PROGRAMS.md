# Research programs for ectogenesis and durable youthful function

Planning revision: **2026-10-06**. The Initial Release A software tranche below
is implemented; remaining scientific gates and Releases B–D are proposed.
No biological measurements, source-review signoffs or empirical validation
are produced by this software tranche.

The long-term goals remain complete artificial gestation and sustained
youthful function. The useful near-term contribution is to identify a missing
capability, state competing explanations, qualify actual measurements, and
run a reproducible analysis that can favor or contradict those explanations.
Open-source releases should make that cycle easier for other researchers.

ResearchDesk owns the question, artifact and review workflow. The sibling
repositories continue to own their methods. Use this program plan with the
[implementation roadmap](ROADMAP.md), [research philosophy](RESEARCH_PHILOSOPHY.md)
and [ectogenesis program](https://github.com/dylanstechmann/artificial-womb-models/blob/main/RESEARCH_PROGRAM.md).

## 1. Choose questions that can change the next research decision

For each question, define the target tissue/system, actual age or developmental
interval, independent biological unit, measured outcome and relevant
comparator. Include a simple explanation such as batch, selection, altered
cell composition or measurement bias alongside the favored mechanism.

Keep identity, viability, genome stability, adverse findings, tissue function
and durability as separate outcome domains. Function needs a tissue-specific
definition and ascertainment window. A clock, expression panel, image feature
or predicted molecular interaction can support a narrower question; it does
not supply every outcome domain.

The common workflow should be:

1. **Question:** which missing capability or causal explanation matters?
2. **Alternatives:** which distinct explanations predict different observations?
3. **Data eligibility:** do the actual files, rights, units and groups permit the test?
4. **Frozen plan:** what estimand, baseline, split, exclusions and uncertainties were fixed?
5. **Runs:** can every displayed result be traced to inputs and implementation?
6. **Review and next decision:** supported within scope, contradicted,
   inconclusive or not testable; what observation would resolve the remaining gap?

Do not optimize for a universal youth score or the number of repositories.
Prioritize a release that reduces one uncertainty and is independently usable.

## 2. Four connected research programs

### P1 — Ectogenesis interfaces, developmental transitions and outcomes

**Question:** which biological capability or transition remains unresolved,
and can a specific interface model or measured outcome test it?

The existing model ledger covers separate embryonic and partial-fetal-support
intervals. Recent primary work supplies additional starting points: an
[implantation/endometrial model](https://doi.org/10.1016/j.cell.2025.10.027),
[placental barrier organoids](https://www.nature.com/articles/s41467-024-45279-y),
and a [maternal–fetal interface reference atlas](https://www.nature.com/articles/s41586-026-10316-x).
Their different stages, models and observables need independent qualification;
the new sources are planning candidates awaiting source review.

**First deliverables:** a stage-transition graph, executable observation
validation, dataset eligibility cards and one frozen interface question.
Prefer a unit-aware barrier/transfer benchmark if sufficient quantitative
measurements exist. A donor/stage-aware cell-state comparison is a separate
possible pilot and must retain its own endpoint scope.

**Competing explanations:** missing interface cell states, altered geometry/
organization, different exchange behavior, absent developmental signaling,
and source/site/measurement differences. A reference-expression match does
not decide among all of these explanations.

**Acceptance:** source-defined intervals and units; reviewed graph edges;
measured observables matched to equations; a simpler comparator; independent
unit evaluation when eligible; development, maintenance, attrition and
follow-up reported separately. Missing unit-level data yields a descriptive
or exclusion report. See the detailed [E1–E6 plan](https://github.com/dylanstechmann/artificial-womb-models/blob/main/RESEARCH_PROGRAM.md).

### P2 — Functional tissue regeneration and replacement

**Question:** can a source-defined tissue response be measured reproducibly,
and do morphology, cell state or transport explain an independently measured
functional endpoint?

Finish the existing [kidney-tubuloid image case](studies/organoid/kidney-tubuloid-cyst-induction/README.md)
first. The licensed intake has 280 images awaiting reviewed instance masks;
it already supplies source metadata and a kidney-grouped split. The
source kidney IDs are grouping identifiers, not verified donor identities. The
[Bonn archive](https://doi.org/10.60507/FK2/OM25XQ) and
[associated study](https://doi.org/10.1186/s12860-026-00591-x) are the biological
source, rather than a newly generated experiment.

**First deliverables:** genuine full-resolution image review, accepted-mask
revisions, dispositions for ambiguous/unusable fields, independent review and
adjudication, calibrated geometry and grouped instance-level evaluation.
Preserve the existing [TEBV functional reanalysis](studies/mutation_repair_pilot/tebv_benchmark/README.md)
as a separate functional case with its one-donor and missing-vessel-ID limits.

**Competing explanations:** actual tissue response, field/object selection,
segmentation error, scale differences, batch effects and altered cellular
composition. Cyst/area changes are morphology outcomes. Link them to function
only when the same eligible biological units have actual functional data.

**Acceptance:** every measurement resolves to an accepted mask, source field
and declared grouping hierarchy; independence claims require source-supported
donor/culture identities. Preserve unresolved independence and restrict
inference where those identities are absent. Report count/split/merge errors as well as foreground
overlap. A later functional model requires eligible outcome linkage, a frozen
group split and comparison against a simple baseline. Missing well/track/scale
information limits the stated analysis rather than being invented.

**Shared value:** measured geometry, grouped evaluation, oxygen/transport
models and calibration can support tissue-engineering and placental questions.
Do not convert 2D mask area into a spherical radius or oxygen demand without
a reviewed physical observation/model contract.

### P3 — Aging-state change versus identity, selection and stress confounding

**Question:** which reported molecular changes accompany retained/recovered
identity and independent functional evidence, and which are explained by
dedifferentiation, selection, quiescence or inflammatory state?

Two bounded study folders are proposed inside the existing workbench, rather
than new methods repositories:

- **Paired reprogramming audit:** qualify the RNA/methylation data in
  [GSE165180](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE165180)
  and its transient RNA subseries
  [GSE165177](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE165177).
  [Gill et al.](https://elifesciences.org/articles/71624) report fibroblast
  molecular changes, identity recovery and selected functional observations.
  Plan paired donor/culture comparisons, matched controls and separate
  expression/identity/function views. Establish which functional observations
  can actually be linked to each omics unit before joint analysis.
  The transient RNA subseries contains 95 libraries; these are not 95 donors.
- **Senescence specificity challenge:** qualify
  [GSE160166](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE160166)
  and [GSE160356](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE160356)
  from the [primary endothelial-senescence study](https://doi.org/10.1111/acel.14240).
  Freeze existing source-pinned panels and contrasts. Include inflammatory/
  arrest alternatives, matched random panels, gene coverage and available
  orthogonal observations. Check overlapping sample families, including
  GSE125792, before claiming independent replication.
  Treat the source interferon group as an alternative-response challenge,
  rather than senescence-negative truth without orthogonal evidence.
  Keep GSE160356 clone replication distinct from donor replication.

Candidate replication/challenge sources are
[Sarkar et al.](https://www.nature.com/articles/s41467-020-15174-3) with
[GSE142439](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE142439), and
[Lu et al., Cell 2025](https://doi.org/10.1016/j.cell.2025.07.031) with
[GSE297234](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE297234).
Qualify cell type, paired-unit structure and donor-age confounding before
choosing a comparison. Data availability does not establish endpoint linkage
or an independent safety/function benchmark.
GSE142439 contains 16 samples from eight donor pairs across two cell types.
GSE297234 includes only two fibroblast donors with different ages; donor and
age are confounded in that subset, which cannot establish an age effect across
people.

**Acceptance:** frozen mappings/preprocessing/contrasts, donor or culture
hierarchy preserved, effect sizes and missing domains visible, and sensitivity
to composition and selection. A molecular change with absent function or
durability is an unresolved functional-rejuvenation claim. Preserve the
existing [GSE268487 ranking failure](https://github.com/dylanstechmann/senescence-module-score/blob/main/validation/GSE268487/REPORT.md);
do not retune a panel against that inspected outcome.

### P4 — Age-acquired damage, clone behavior and functional repair

**Question:** which specific damage state is causally harmful in a defined
cell/tissue context, and what evidence would distinguish repair from a change
in clone composition or fitness?

Extend the existing [somatic mutation pilot](MUTATION_REPAIR_PILOT.md), which
already separates mutation calls, clone structure, cell state and tissue
function. Start with its unresolved metadata/assembly/allele-state questions
and source-linked public supplementary tables. Keep monogenic repair examples
as a separate positive-control class.

**First deliverables:** a variant/cell-context evidence matrix containing
allele state, assay sensitivity, causal evidence, clone fitness, functional
endpoint, reachable-cell coverage, durability and adverse/selection outcomes.
Record where those fields are unmeasured. A candidate additional descriptive
reproduction is the [Cagan et al. cross-species mutation study](https://www.nature.com/articles/s41586-022-04618-z),
with [processed data](https://doi.org/10.5281/zenodo.5554777) and
[author code](https://github.com/baezortega/CrossSpecies2021). Its associations
do not themselves establish functional rescue from sequence correction.

**Acceptance:** exact variant and cell context, proper donor/clone/assay
denominators, observational versus perturbational evidence explicit, and
unresolved off-target/selection/function questions retained. A selected clone
or a higher mutation burden alone is insufficient to select a repair target.
The key discriminator is genotype change within a retained lineage versus
clone depletion, dilution or altered fitness. A lower mutant fraction alone
does not distinguish these mechanisms; link either outcome to measured
tissue function before claiming repair.
Keep nuclear and mitochondrial damage, epigenetic state, extracellular matrix
and organ architecture as distinct intervention/evidence axes.

**Delivery/nanomedicine extension:** qualify an actual source with measurements
of intended-cell uptake, cargo activity and functional response. Organ
accumulation or a predicted complex alone leaves the downstream claims
unresolved. Prioritize an analysis/data contract before adding a new generator
or simulation.

## 3. Give each existing repository a precise contribution

| Owner | Next contribution | Completion evidence |
| --- | --- | --- |
| `artificial-womb-models` | E1–E3 transition/intake/data eligibility, then one appropriate empirical model; bounded forecast/observer methods alongside | Reviewed intervals, executable negative cases, frozen question, exact observables and baseline |
| `regen-workbench` | Immutable questions/reviews, dataset cards, frozen plans, validated artifact selectors and portable dossiers | Original revisions resolve after edits; displayed results retain scope, missing domains and review state |
| `organoid-phenotyping` | Complete accepted-mask review and source-faithful kidney case | Immutable accepted masks, independent review, full-resolution QA, group/scale/track provenance |
| `regen-benchmark-kit` | Paired group-level comparisons and a second eligible real case | Untouched group holdout, equal-group metrics, uncertainty, simple baseline and individual predictions |
| `senescence-module-score` | Prespecified endothelial specificity challenge with fixed panels | Gene coverage, deduplicated sample families, arrest/inflammation alternatives and all failed contrasts |
| `cell-fate-transport` | Separate prospective early-only predictions from transductive use of future snapshots; qualify an independent lineage experiment | Clone-level probability/error comparisons, prior/neighbor baselines, frozen preprocessing and support failures |
| `organoid-oxygen-lab` | Audit calibrated spatial profiles and repeat IDs before fitting a limited identifiable parameter set | Correct units/geometry/boundaries, parameter profiles and held-out measurements; eligibility failure if data are absent |
| `perfusion-calibration-lab` | Eligible independent nonbiological measured-trace analysis | Source-linked traces, reference instrument evidence, systematic/repeat uncertainty and exclusions |
| `open-perfusion-rig` | Finish pulse/quantization/toolchain verification; later commissioning evidence remains separate | Simulated and physical evidence labeled separately; bounded build/sequence/error reports |
| `cell-protocol-compiler` | Source-transcribed rule revisions and reviewer decisions; deviations linked to measured results | Exact source locators, preserved unmeasured/deviation gates and authorized result records |
| `diffmedia-loop` | Retrospective equal-budget replay on eligible measured outcomes; biological-unit/batch uncertainty | Frozen candidates/endpoints, random/simple-policy comparison, failures/cost and group provenance |
| `brightfield-colony-qc` | Reviewed real-image rubric and acquisition transfer/abstention | Source-group holdout, disagreements, domain-specific errors and missing/abstained units |
| `geroscience-compound-atlas` | Assay-context-qualified benchmark and new untouched evaluation after existing transfer failure | Assay/source/structure/censoring context, prevalence/simple baselines, calibration and applicability limits |

The [existing compound-transfer failure](https://github.com/dylanstechmann/geroscience-compound-atlas/blob/main/studies/chembl_external_2026-10-04/README.md)
and other negative studies remain valuable development evidence. Inspecting
a holdout changes its role; improvement needs a new frozen evaluation rather
than repeatedly tuning against known failures. Chemistry scores remain assay
predictions within their qualified scope.

## 4. Extend ResearchDesk around scientific decisions

Reuse campaigns, typed source observations, experiment manifests, imported
analysis history, receipt adapters and six outcome domains. Submitted jobs
already retain a canonical campaign/parameter snapshot and hash. The remaining
work is to extend the new immutable draft records into source-review decisions,
validated data eligibility, and run-to-revision bindings.

| Milestone | Concrete feature | Current status | Acceptance |
| --- | --- | --- |
| **D1 — Scientific revisions** | Content-addressed question, hypothesis-set, source observation and review revisions; supersession and current pointers | Partial: question revisions and supersession exist; source observations, reviews and run binding remain | Archived runs/dossiers resolve original revisions; source edits mark dependent plans/results stale |
| **D2 — Dataset cards** | Access/license, exact file inventory, unit hierarchy, units/calibration, groups, age/stage, raw/aggregate status, exclusions | Partial: structured cards exist; sibling ectogenesis intake offers local byte checks; source rights, review and eligibility remain unverified | Invalid pooling and missing identities produce explicit scope restrictions; publication presence does not create a measurement |
| **D3 — Discriminating plans** | Immutable method-neutral research plan with favored/simple/alternative explanations and opposing measurable predictions | Partial: draft plan structure exists; it is not frozen or bound to a run | Plans specify what would favor each explanation and what remains ambiguous; associations retain observational status |
| **D4 — Frozen evaluation** | Pin dataset, preprocessing, split and method revisions; registry of bounded sibling receipt adapters | Partial (2026-10-07): plan freeze, hash-chained holdout ledger and receipt bindings exist with two adapters; jobs submitted through the Desk are not bound, preprocessing is pinned as a description and the freeze clock is self-reported | Every metric resolves to exact inputs/code; changing the plan yields a new exploratory revision; final-test access is recorded |
| **D5 — Scientific review** | Append-only supported-within-scope/contradicted/inconclusive/not-testable decisions, rationale and next discriminator | Proposed: the verifier already reports separate byte, ancestry, lineage and review statuses (review is always `not_established_by_this_tool`), but no decision records exist | Byte integrity, computational reproduction, accepted annotation and scientific review are distinct statuses |
| **D6 — Portable reproduction** | Common bounded export collector, standalone verifier and reproduction manifest | Partial: standalone verifier and reproduction plan exist; the common bounded run-snapshot collector (R3) and a rerun harness do not | A relocated dossier verifies; eligible public analyses rerun; missing/private inputs and corrupt/escaping files fail explicitly |

### Initial Release A implementation (2026-10-06)

ResearchDesk's Study design view now appends content-hashed question, dataset
card and analysis-plan revisions. Plans link exact question and dataset-card
revisions; a later edit marks dependent plans stale. Dataset cards record
source/file metadata, stated access and license, species/model, stage/interval,
data granularity, unit hierarchy, endpoints/units, calibration state, groups,
missingness and exclusions. A deterministic gap list exposes absent fields;
  it is not an eligibility score. File hashes supplied to these Study design cards
  remain metadata and are not checked against external bytes in this feature;
  the sibling observation-intake tool provides a separate optional local check.
  Plans require multiple
hypothesis-linked predictions, an estimand, outcome/unit/time, comparator, baseline, split,
uncertainty, missingness, confounding, falsification and ambiguity rules.
Dossier exports preserve the exact structured records and hashes.

This is the first software tranche of D1–D3. It does not yet version source
observation review decisions, authenticate a reviewer's identity, verify
download rights or file availability, or bind jobs submitted through the Desk
to scientific revisions. Plans remain drafts until a plan freeze pins them (next
section).

### D4 increment: frozen evaluation records (2026-10-07)

Three append-only record types now sit on a saved analysis plan (details in
[RESEARCH_DESK.md](RESEARCH_DESK.md)):

- a **plan freeze** pins one plan revision, its question and dataset-card
  revisions by ID and content hash, the method (repository, commit, entry point,
  preprocessing, parameters), the primary metric and baseline, and a split with
  development and sealed final-test groups; the status is derived as
  exploratory, confirmatory or retrospective, with blockers listed;
- a **holdout access** ledger is a SHA-256 hash chain of every recorded
  development or final-test touch (evaluate, tune, inspect labels, export
  predictions);
- an **evaluation binding** reads one sibling-repository receipt once, through a
  registered adapter (regen-benchmark-kit metrics or a generic receipt format),
  and checks pinned inputs, split agreement, sealed groups used in training,
  producer-reported overlap, method revision and timing.

From these the Desk recomputes a claim state (`holdout_sealed`,
`single_final_evaluation_recorded`, `holdout_reused_not_independent`,
`holdout_compromised`, `ledger_integrity_failed`, `exploratory_only`,
`retrospective_not_confirmatory`). `tools/verify_dossier.py` recomputes the same
state, re-hashes every archived revision and checks pins and ledger chains
outside the Desk (`scientific_lineage`).

The worked example in [studies/frozen-evaluation-example/](studies/frozen-evaluation-example/)
applies this to the committed NIST iPSC benchmark receipt. It is
retrospective, and the Desk shows that the leave-one-well-out receipt cannot be
a final-test evaluation of any well because every well was in training. A second,
labeled-SYNTHETIC path shows the clean prospective case once. This is a negative
and procedural finding, not a biological result.

Not done, and not implied: bindings for jobs submitted through the Desk; adapters
for the other sibling tools (organoid agreement audits, ectogenesis receipts);
authenticated reviewers or external timestamping (the freeze clock, the "results
inspected" attestation and ledger actors are self-reported); pinning
preprocessing as code rather than a description; recomputing a receipt's metrics;
D5 decision records; and any scientific review of a frozen analysis. A clean
record means only that the recorded procedure was followed.

Remaining D4 plan fields not yet pinned by the freeze beyond what the pinned plan
revision itself contains, to be pinned through the existing run submission and
`analysis_specification` artifact mechanisms:

```text
plan/revision, question revision hash, scope and claim boundary
hypotheses: roles, assumptions, predictions, falsifiers
discriminators: measured outcome/unit/time, comparator, opposing predictions
dataset-card revisions and exact input hashes
estimand and independent-unit/repeated-measure definition
method owner/revision, preprocessing, baseline, split and metrics
uncertainty, missingness/exclusions, confounding and sensitivity rules
exploratory/confirmatory status, evaluation and ambiguity criteria
required outcome domains, source-review references and limitations
```

The UI progression is **Question → Alternatives → Data eligibility → Frozen
plan → Runs → Review**. The Study design view now provides the first three
draft record types, plus plan freezes, holdout-access events and receipt
bindings. Validated selectors, source/quantity compatibility and bindings for
jobs submitted through the Desk remain to be added. Keep browser-supplied shell
execution out of the Desk and keep sibling methods in their own repositories.

## 5. Sequence releases by evidence gates

| Release | Work to finish | Gate before expanding scope |
| --- | --- | --- |
| **A — Questions and eligible inputs** | D1–D3; ectogenesis E1–E3; qualify reprogramming/senescence candidates; keep current numerical verification | One frozen, genuinely discriminating analysis plan; source review and actual data eligibility recorded |
| **B — Measured demonstrator** | D4 input/preprocessing/split/method binding and receipt adapters before the run; accepted kidney-mask case; one eligible interface or paired-omics reanalysis; source-faithful baselines | Independent units and endpoint linkage support the stated analysis; uncertainty/missingness and negative cases retained |
| **C — Reproduction and challenge** | D5–D6; portable dossier; external source/cohort where eligible; forecast calibration with independent synthetic schedules | Untouched evaluation and independent method/source review; failures narrow the claim rather than disappear |
| **D — New mechanism or method** | A specific next equation, perturbation-analysis question or dataset interface justified by B/C | Observable, parameter provenance, simpler comparator, falsifier and usable data exist before implementation |

Release A tasks can be implemented alongside annotation review; genuine human
annotation, adjudication and scientific review cannot be supplied by generated
signoffs. When a gate cannot be satisfied, release the bounded eligibility,
reproduction or non-identification report and define the missing input.

**Contributor-sized first tasks:** observation validator; immutable revision
store; dataset-card schema with invalid examples; accepted-mask review export;
donor/culture mapping for one GEO study; prediction/error table with
unavailable denominators; a receipt adapter for another sibling tool (the
organoid agreement audits are the nearest); a bounded run-snapshot collector
(R3). Started 2026-10-07: frozen baseline/split plan (plan freeze, ledger and
binding, see above) and an archive ancestry verifier (`regen verify-dossier`,
which resolves linked manifests and receipts inside a dossier and does not
verify external data sources).

## 6. Open-source innovation and repository decisions

Favor reusable measurement/evaluation tools and independently inspectable
results. Release exact input locations and hashes, preprocessing and group
definitions, all predictions, uncertainty, negative findings, source rights,
an environment recipe and a concise methods explanation. Compare with the
source analysis and existing public tools before claiming method novelty.

Create another repository only when a distinct reusable method, eligible
data, stable interface and falsifiable question have outgrown a study folder.
A later rejuvenation-function benchmark or somatic-variant/clone evaluator
could meet that condition. Neither needs a new repository now.

Credit source biology, software contributions and actual reviewer work
precisely. Independent reproduction, review and clear methods make these
exploratory projects more useful and easier to assess. The full ambitions
remain open research goals; each release
should make one step toward them measurable and easier to challenge.
