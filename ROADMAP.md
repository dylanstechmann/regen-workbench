# Biomedical development roadmap

Code and repository review: 2026-10-06. Prioritize stem cells, organoids and
tissue regeneration, with ectogenesis as a substantial theoretical research
area. This is an implementation plan; unchecked milestones are future work.

## Current baseline and this update

ResearchDesk already has an ectogenesis blueprint, stage-aware campaign
starters, receipt-checked artificial-womb reports, experiment cards, append-only
imported analysis-run history, separate current pointers by analysis kind, linked
artifacts and dossier exports. It can display TEBV measured-data reanalysis
and import blinded organoid pilot/repeat-agreement audits. These capabilities
should be extended rather than rebuilt.

This update fixes two integrity defects: transport/mechanics reports must
match their receipt's model family, and annotation re-imports compare the
receipt itself as well as outputs. Receipt and CSV interpretation use the
same bounded bytes that were checked and retained. The UI also explains
unavailable forecast intervals from the model package.

The next large milestone is one human-reviewed organoid measurement case
carried from source images through frozen masks, grouped evaluation and a
portable ResearchDesk dossier. Review agreement, morphology, model accuracy
and biological function must remain separately labeled.

## R1 — Preserve reviewed evidence and campaign revisions

- Store immutable source observations and campaign revisions, each with a
  content digest, source version/locator and reviewer identity/date/rationale.
- Pin a run or dossier to the reviewed revision, not just a mutable campaign
  ID. Preserve supersession and show changed links as stale until refreshed.
- Extend ectogenesis observations with actual species-specific intervals,
  explicit source class, measured endpoint, adverse/null results and excluded
  inference. A stage label alone is insufficient evidence for an interval.
- Keep conclusions and hypotheses distinct from source-transcribed facts.
  Repeated citations to one dataset do not create independent evidence.

**Acceptance:** rebuilding an archived dossier resolves its original campaign
and source revisions; revisions and reviewer decisions remain inspectable;
incompatible species,
stages or outcome contexts cannot silently become one comparison.

## R2 — Verify and reproduce a dossier outside this workstation

Coordinate the bundle contract with
[artificial-womb-models](https://github.com/dylanstechmann/artificial-womb-models/blob/main/ROADMAP.md).

- Add a standalone `verify-dossier` command for inventory, hashes, schemas,
  linked manifest/receipt ancestry, code revision and declared dependencies.
- Include a reproduction plan with exact input locations, commands,
  environment and expected outputs. Verification and rerunning are distinct
  statuses; missing data/dependencies must be reported explicitly.
- Copy source receipts when ancestry is claimed, including the simulation
  receipt for observability and pilot/manifest/plan/mask bindings for
  annotation-derived records when licensed and authorized for the archive.
- Distinguish output integrity, resolved source lineage and human scientific
  review. A receipt hash is not proof that an annotation was accepted.

**Acceptance:** a relocated synthetic dossier verifies without the original
absolute paths and reproduces in a clean environment; changed/missing inputs
produce actionable failures. A real-data dossier declares licensed download
steps or private dependencies instead of pretending to contain them.

## R3 — Unify archive limits and strict integrity checks

The linked-research collector has 20 MB per-file and 100 MB total limits.
The separate run-snapshot collector currently lacks equivalent limits and
can include undeclared/mismatched files with flags. Make this gap explicit
until a common collector replaces it.

- Use one bounded collector for every archive entry, with consistent limits,
  safe relative paths, symlink rejection, duplicate-entry checks and a total
  byte budget that includes metadata and receipts.
- Define a strict verified export that refuses mismatched/undeclared files.
  Keep diagnostic inspection available under a clearly distinct status.
- Read and archive the exact verified bytes, with an archive inventory that
  a standalone verifier can check after relocation.
- Test oversize run files, escaping paths, symlinks, duplicate names,
  corruption, missing ancestry and source files changed during collection.

**Acceptance:** every archive entry obeys the same rules, no partial archive
is presented as verified, and portable verification catches each negative case.

## R4 — Make comparisons useful for researchers

- Replace manual artifact-ID text fields with validated selectors showing
  source, run kind, context, review state and stale-link warnings.
- Introduce typed quantities with units, missingness, calibration and
  independent-unit hierarchy (for example donor → well → image → object).
- Build side-by-side comparisons that retain model assumptions and simpler
  baselines, group counts and errors. Never silently pool species, stages,
  outcomes, scales or repeated observations.
- Deduplicate papers/datasets without deleting distinct measured outcomes.
  Prefer narrow, reviewable computations over adding a generic chat surface.

**Acceptance:** users can select compatible records without copying IDs;
incompatible records show why they cannot be pooled; plots/tables preserve
source locators, units, denominators and missing observations.

## R5 — Complete the organoid case end to end

The local `organoid-phenotyping` package is the methods owner. Its first
source is the [Bonn kidney-tubuloid dataset](https://doi.org/10.60507/FK2/OM25XQ)
and [associated study](https://doi.org/10.1186/s12860-026-00591-x).

1. Fix annotation task-switch races and add reliable full-resolution review,
   editable contours and dispositions for empty/ambiguous/unusable images.
2. Freeze submitted masks; record independent review, adjudication and accepted
   revisions before calling geometry reviewed. Different pseudonyms alone do
   not demonstrate independent review.
3. Recover original well/ROI/scale/track metadata where possible; otherwise
   preserve missingness. Freeze preprocessing and group split before touching
   the final-test source kidney.
4. Run morphology and instance-level agreement with appropriate source-group
   denominators. Foreground Dice alone misses count and split/merge errors.
5. Link review audit, accepted-mask receipt, geometry receipt, grouped benchmark
   results and source/license card into one independently verifiable dossier.

**Acceptance:** a reviewer can follow every displayed number to the accepted
input and independent unit. Report descriptive image geometry if original
measurement identities are unavailable; do not label it an exact reproduction
of the paper's selected-object analysis or a biological treatment effect.

## Supporting repositories: next empirical or engineering milestone

These packages retain separate histories and methods ownership. Their current
README/method reports were inspected; their analyses were not rerun for this
roadmap. Use source-linked receipts as the integration boundary.

| Repository | Next milestone | Completion evidence |
| --- | --- | --- |
| [regen-benchmark-kit](https://github.com/dylanstechmann/regen-benchmark-kit) | A second reviewed real benchmark beyond the limited three-well NIST case; group-safe regression uncertainty where group counts support it. | Frozen targets/splits, every prediction, equal-group errors and simple baselines; adequate independent units. |
| Local organoid-phenotyping | Review lifecycle, full-resolution annotation, first accepted-mask development case, then reproducible package publication. | Immutable reviewed masks, dispositions, source/scale/group provenance, clean-install example and linked dossier. |
| [organoid-oxygen-lab](https://github.com/dylanstechmann/organoid-oxygen-lab) | Measured oxygen profiles/uptake with explicit units, boundary records and repeat IDs; fit a limited parameter subset. | Withheld-profile evaluation, identifiability and data/parameter uncertainty. A source audit is the deliverable if no eligible data exist. |
| [perfusion-calibration-lab](https://github.com/dylanstechmann/perfusion-calibration-lab) | First eligible native measured-trace case; the existing intake audit found no eligible public traces. | Run-linked measurement evidence, retained exclusions, repeat and systematic uncertainty. Third-party analysis does not commission the user's pump. |
| [open-perfusion-rig](https://github.com/dylanstechmann/open-perfusion-rig) | Discrete pulse/quantization simulation and a board-toolchain build compared with the real sketch. | Pulse-count, start/stop/idle/rollover and sequencing checks; later nonbiological characterization kept separate from simulation. |
| [cell-fate-transport](https://github.com/dylanstechmann/cell-fate-transport) | Preserve the existing LARRY held-out-clone result; label the secondary neighbor comparator, then freeze an independent-experiment evaluation. | Clone-level calibration, support/batch checks and transport sensitivity; source-experiment holdout with untouched outcomes. |
| [senescence-module-score](https://github.com/dylanstechmann/senescence-module-score) | Investigate the existing real-data ranking failure on an independent cohort with donor/experiment metadata and orthogonal state evidence. | Frozen contrasts/preprocessing, random-panel comparisons and explicit inflammation/quiescence confounding. |
| [cell-protocol-compiler](https://github.com/dylanstechmann/cell-protocol-compiler) | Auditable source transcription and reviewer signoff; repair the quarantined hepatocyte record only from verified primary material. | Source locations for each rule, reviewer decisions and a collaborator-reviewed result record with unmeasured/deviation gates preserved. |
| [diffmedia-loop](https://github.com/dylanstechmann/diffmedia-loop) | First real retrospective planning replay or measured collaborator campaign. | Frozen endpoints/candidates, equal-budget policy comparisons, held-back measurements, failed wells and batch/unit provenance; applicability checked beyond factor bounds. |
| [brightfield-colony-qc](https://github.com/dylanstechmann/brightfield-colony-qc) | Reviewed real-image rubric and model separate from the synthetic demo. | Source-group split, untouched acquisition/cohort holdout, abstention coverage, disagreements and domain-specific errors. |
| [geroscience-compound-atlas](https://github.com/dylanstechmann/geroscience-compound-atlas) | New prospectively qualified assay dataset after the existing negative external holdout. | Source/structure overlap exclusions, frozen assay/threshold/model plan, untouched evaluation, calibration and descriptor/fingerprint/prevalence baselines. |

Do not discard real negative results by retuning against the same holdout.
Do not convert organoid 2D mask area directly into spherical radius, oxygen
uptake or biological function. Any cross-package physical input needs measured
units, reviewed assumptions and propagated uncertainty.

## Delivery sequence and portfolio value

1. **Next release:** model accuracy/identifiability work, annotation correctness
   and frozen review lifecycle, plus immutable evidence/campaign revisions.
2. **Next integrated release:** strict portable dossier verification/export and
   the reviewed organoid development case with grouped evaluation.
3. **Next empirical release:** one eligible oxygen, perfusion or senescence
   case; independent-experiment lineage work and qualified chemical evaluation.
4. **After review:** a concise methods manuscript, reproducible figures,
   installation example, explicit limitations and contribution-sized issues.

Each release should have a tagged revision, passing relevant checks, exact
inputs/reproduction instructions and an inspectable failure example. Genuine
human annotation/review, real measurements and external feedback remain
required inputs; generated files cannot substitute for them.

Prioritize these existing repositories over new ones. A new repository is
justified when it has a distinct method, usable data, an independent interface
and a falsifiable question. These outputs can demonstrate useful research
software skills for paid research/engineering roles while preserving honest
limitations; repository count and software demos do not guarantee a position.
