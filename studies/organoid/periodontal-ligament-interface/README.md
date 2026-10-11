# Human periodontal attachment interface assay

## Decision

Use two published model features in sequence: the 2024 PDLSC-laden collagen
construct printed on root fragments as a root-facing cell-organization
benchmark, and the 2022 human PDL–alveolar-bone microtissue as a
compartment/perfusion benchmark. Neither currently demonstrates a functional
tooth attachment. The first showed cell survival, migration, and alignment on
root fragments, but no new cementum in the in-vitro root-surface experiment;
its in-vivo root-fragment experiment was ectopic under the skin, without an
alveolar socket or chewing load. The second maintained a two-cell biointerface
under flow but lacked a cementum-facing root, inserting fibers, and tooth-scale
mechanics.

The next model should therefore be a staged human-cell assay, not a merged
claim of regeneration. Start by reproducing a root-facing cell-organization
readout; add a distinct bone-side compartment; then test whether guided fibers
insert at both mineralized interfaces and carry cyclic load without a bone
bridge. Keep tooth position as a separate in-vivo endpoint: an in-vitro assay
cannot show that a tooth returns to or remains in its intended position.

## What this assay can decide

It can rank architectures for cell survival, interface continuity, fiber
orientation and insertion, compartment-specific mineralization, low-amplitude
mechanical response, and recovery after a defined inflammatory challenge. It
can also test whether a donor-derived niche modifies the same cell preparation
after washout. It cannot establish durable tooth repositioning, human benefit,
adult tissue rejuvenation, or lifetime stability. Do not call an aligned cell
layer a ligament, or a high stiffness value a successful attachment.

The experimental unit is an independently sourced human donor/cell preparation
within a manufacturing batch. Constructs, images, sections, and repeated loads
are nested observations, not independent donor replicates. Record cell-source
age, tooth type/root maturity, periodontal health, extraction indication,
passage, and batch where available. For stem/progenitor-cell preparations,
track donor and clone identity and retain a matched fibroblast identity check.

## Staged comparison

1. **Root-facing benchmark:** cell-laden versus cell-free construct on a
   dentin/root-surface substrate, with matched surface preparation and an
   acellular substrate control. This tests assay repeatability for viability,
   migration, adhesion, and orientation; it does not test cementogenesis.
2. **Compartment benchmark:** add a separate bone-facing osteogenic region and
   compare biphasic versus homogeneous architecture. Keep mineral deposition
   spatially localized; quantify any mineral crossing into the ligament region.
3. **Fiber guidance:** compare aligned versus non-aligned guidance while
   holding cell source and compartment layout fixed. Score bundle orientation
   and continuous insertion independently at the root-facing and bone-facing
   surfaces.
4. **Inflammatory challenge:** after G2 passes, compare the same qualified
   architecture and donor preparation under a duration-matched control and a
   literature-bounded oral-disease inflammatory challenge, followed by a
   defined washout/recovery period. Lock the stimulus, delivered activity and
   exposure only after a measurement pilot. Keep donor age and periodontal
   health as source covariates; a disease challenge is not an aging model.
   Track inflammation and MMP/TIMP response together with viability, both
   interfaces, fiber insertion and mechanics. Add a gingival epithelial barrier
   module separately if seal function is a target; a PDL-only construct cannot
   stand in for a gum barrier.
5. **Age-by-niche fork:** separately cross younger- and older-adult healthy PDL
   cell donors with conditioned-medium donors from both source-age strata,
   with matched unconditioned controls. Record exact age, mature-root status,
   periodontal health, extraction indication, passage and batch; analyze age
   continuously as well as in any prospectively chosen recruitment strata.
   Conditioned medium is an undefined historical benchmark from the 2009
   human PDLSC study, not a treatment candidate. Test persistence after
   washout, then require the same bilateral insertion and mechanics gates as
   the main architecture. See
   [`age_by_niche_test.tsv`](age_by_niche_test.tsv).
6. **Flow and load:** add perfusion only after the static two-interface
   construct is reproducible. Add defined cyclic loading only after the
   mechanical platform is calibrated, then assess recovery after unloading.
   This is still not an in-socket trauma model.

The comparison rows and endpoints are specified in
[`condition_matrix.tsv`](condition_matrix.tsv) and
[`endpoint_contract.tsv`](endpoint_contract.tsv). Numeric go/no-go limits are
intentionally marked `calibrate_first`: they must be frozen from matched
healthy-reference distributions and measurement repeatability before candidate
ranking. A convenient threshold invented in advance would be less defensible
than an explicitly unresolved threshold.

## Decision gates

- **G0, measurement qualification:** blind image and mechanics scoring is
  repeatable; donor, construct, section, and load hierarchies are retained.
- **G1, viable organization:** the root-facing and bone-facing cell regions
  remain viable and distinct, with stable geometry and no ectopic mineral
  bridge.
- **G2, true attachment:** collagen bundles connect the ligament compartment
  to both mineralized boundaries. Cell proximity or parallel alignment alone
  fails this gate.
- **G3, useful mechanics:** the construct has compliant, recoverable response
  under the prespecified loading regime and remains distinct from a rigid
  fusion/bone-bridge control. Compare with ex-vivo healthy reference tissue
  under the same geometry and fixture; do not compare unmatched raw force
  values.
- **G4, challenge and niche recovery:** a disease challenge or cell-free niche
  exposure does not hide cell loss or attachment failure, and the construct
  moves toward its matched pre-exposure state after washout. Persistence of a
  transcript-panel shift alone is not a functional failure or success; pair it
  with interface, barrier-module where present, and mechanical outcomes.
- **G5, transfer:** only after G0–G4 pass should a separate orthotopic retained-
  tooth injury model assess position, pulp, gingiva, resorption, and stability
  after temporary support removal.

## Evidence and limits

- The published 2024 collagen/PDLSC study reported a root-fragment surface
  construct with migration and aligned cells in vitro and ectopic root-fragment
  implantation in immunocompromised mice at 4 and 10 weeks. The authors note
  that alignment remained parallel to the root rather than functionally
  oriented insertion; the in-vitro root-surface study reported no new
  cementum. [Primary study](https://doi.org/10.1021/acsami.4c13830).
- The published 2022 human PDL–bone microtissue provides a perfused
  PDL/alveolar-bone interface chassis, but not a root-facing cementum interface
  or tooth-load function. [Primary study](https://doi.org/10.1016/j.gendis.2020.11.011).
- Fiber-guiding scaffolds have encouraging short-term periodontal-defect
  results in rats, but those are not blunt-impact repair in an intact socket.
  [Primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC4074763/).
- The donor-aware GSE164241 challenge identified a stronger disease-associated
  inflammatory/matrix-turnover signal than a shared within-fibroblast adult
  age direction. Use it to keep inflammatory disease and aging as separate
  assay challenges, not to set a rejuvenation target. [Analysis and limits](../../aging-state-2026-10-11/GINGIVAL_CELL_RESOLVED_CHALLENGE_REPORT.md).
- Donor-derived human PDLSC studies report reduced functional assays with age;
  a 2009 study reports improvement after exposure to young-donor conditioned
  medium, while a 2012 transplantation study did not identify cementum/PDL-like
  tissue in the two age groups included in its in-vivo comparison. These are
  cell and ectopic-model results, not proof of in-socket restoration. The
  [PDL age qualification](../../aging-state-2026-10-11/PDL_AGE_REFERENCE_QUALIFICATION.md)
  separates those results from a donor-resolved tissue age reference.

No wet-lab work is represented by this design dossier. No human treatment
protocol or efficacy claim follows from the proposed assay.
