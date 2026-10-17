# Full-tooth restoration: lost substance, original form and living attachment

Research specification updated 2026-10-17. This extends the attachment project
to the tooth itself: missing enamel and dentin, damaged interfaces and cracks,
pulp, root surfaces, gums, ligament and socket. No individual photographs or
case records were used. The specification is a development target, not a
validated clinical procedure.

## The expanded target

The target is the individual's intended, undamaged anatomy and durable adult
function. For a tooth with lost substance, restoring position and periodontal
attachment alone is incomplete. A visually similar crown also leaves the
question of material identity, internal structure and durability unresolved.
The machine-readable requirements are in
[`restoration_contract.json`](restoration_contract.json), version 2.

| Component | Required restoration outcome | Important competing outcome |
|---|---|---|
| Crown form and tooth substance | Appropriate original contour, contacts, cusp/incisal geometry and separate recovery of lost enamel and dentin volumes | Correct silhouette with a remaining internal deficit or excessive bulk |
| Enamel | Appropriate thickness distribution, composition, regional architecture, integration and surface behavior | A mineral coating or hard deposit counted as full-thickness enamel |
| Dentin and enamel-dentin interface | Organized dentin with a durable, mechanically continuous junction | Weak bond, leakage, brittle interface or uncharacterized repair mineral |
| Cracks and fractures | Defined crack extent, load-path integrity and resistance to further propagation | Surface sealing while a deeper crack persists |
| Pulp | Vital perfused tissue, appropriate neural support and preserved internal space | Calcification, necrosis or loss of sensation concealed by a repaired surface |
| Root, cementum, PDL and socket | Inserting fibers at both interfaces, physiological mobility and stable pose | Fusion, resorption, scar or stable attachment around the wrong geometry |
| Gingiva and barrier | Individual margin/papilla form, volume, appropriate tissue phenotype and barrier function | Coverage or cosmetic similarity without durable healthy attachment |
| Integrated tooth | Compatible bite and repeated-load function after intervention and temporary support end | Separate components that fail when loaded together |

Damage mechanism does not replace structural assessment. Record reported
mechanical, restorative, thermal, laser or disease history separately from the
measured defect. Historical photographs alone cannot decide why a defect
occurred or whether a prior intervention was indicated.

## What historical photographs can establish

Photos can constrain visible incisal edges, cusp contours, tooth proportions,
position, color appearance and gingival margins. Multiple suitable views may
support surface reconstruction if scale, camera geometry, coverage and error
are qualified. A photograph does not expose the enamel-dentin junction, hidden
surfaces, pulp or the depth of an internal crack. Appearance also depends on
lighting, perspective, hydration and camera processing.

Use a region-by-region target record with four separate states: directly
measured historical anatomy; geometry constrained by historical images;
anatomy inferred from individual surviving structures; and anatomy inferred
from another tooth or a population prior. A plausible reconstruction cannot
silently become a record of the person's exact original tooth.

Prefer any available earlier scans or casts as dimensional references, using
photos to add visible surface and soft-tissue constraints. Combine these with
appropriate current examinations and existing imaging selected for the actual
clinical question. This blueprint does not prescribe new radiation imaging.
The field definitions are in
[`full_tooth_target_data_dictionary.tsv`](full_tooth_target_data_dictionary.tsv).
Keep identifiable images and clinical records private; the repository holds
schemas and research summaries.

## Distinguish the biological and materials problems

1. **Demineralization with retained structure:** loss of mineral within a
   remaining enamel framework. Early mineral loss can be remineralized; this
   differs from replacing a physically absent crown segment. [NIDCR](https://www.nidcr.nih.gov/health-info/tooth-decay/more-info/tooth-decay-process).
2. **Missing enamel over surviving enamel:** a growth or fabrication approach
   must recover the missing thickness and architecture, connect to the host and
   survive the oral loading environment.
3. **Missing enamel over exposed dentin:** the design also needs an appropriate
   dentin-enamel transition. Successful growth on remaining enamel cannot be
   assumed to transfer unchanged to dentin.
4. **Missing dentin or pulp involvement:** volume, tissue organization and
   vitality require separate repair modules. A dentin result cannot be counted
   as enamel repair.
5. **Cracked or thermally altered tissue:** continuity and residual mechanical
   integrity must be assessed through the affected depth. Filling the visible
   contour does not establish that the load-bearing structure has recovered.

Existing restorative material is a separate compartment in the inventory.
Record its extent, interfaces and remaining native substrate. Removing it is
not an assumed first step of a future regenerative strategy; that decision
depends on the specific substrate, vitality and intervention evidence.

## Research leads and the unresolved scale gap

The source ledger is [`hard_tissue_evidence.tsv`](hard_tissue_evidence.tsv).
It is a set of qualified leads, not a clinical efficacy ranking.

- **Acellular enamel-like regrowth:** Hasan et al. (2025) report organized,
  integrated mineral layers on extracted human enamel and dentin, with tested
  coatings/layers around 2-10 micrometres and laboratory mechanical, wear and
  acid challenges. This supports investigating host-integrated mineral
  growth; it does not demonstrate millimetre-scale crown reconstruction or
  long-term treatment outcomes in people. [Primary article](https://www.nature.com/articles/s41467-025-64982-y).
- **Repeat-cycle thickening:** Shao et al. (2019), supplementary Figure S10,
  show approximately 5 and 10 micrometre layers after two and four cycles.
  This supplies a scale-up lead while leaving bulk reconstruction unresolved.
  [Primary article](https://doi.org/10.1126/sciadv.aaw9569).
- **Enamel-forming cells:** Patni et al. (2026) report human iPSC-derived
  ameloblast organoids producing enamel-like calcified material under a mouse
  kidney capsule. That provides a cell-development lead; it does not establish
  original-thickness enamel integrated onto a damaged adult tooth. The existing
  [source review](../dental-regeneration-2026-10-09/AMELOBLAST_ORGANOID_REVIEW.md)
  records the structural and functional gaps. [Primary article](https://doi.org/10.1038/s41368-026-00429-4).
- **Dentin repair:** Neves et al. (2017) demonstrate enhanced reparative dentin
  formation in injured mouse teeth using local GSK3 inhibition. This is a
  dentin/pulp research lead; it does not restore enamel or establish the whole
  integrated restoration target in humans. [Primary article](https://www.nature.com/articles/srep39654).
- **Living attachment:** progenitor-based rat replantation provides a separate
  attachment and mechanics precedent. It supplies no missing-crown restoration
  result. [Dangaria et al.](https://pubmed.ncbi.nlm.nih.gov/20795795/).

For scale only, an illustrative 1 mm defect is 1,000 micrometres deep; a 10
micrometre layer spans 1% of that depth. This arithmetic is not a growth-rate
prediction. Repeating a thin-layer process does not establish thick tissue
formation: orientation, internal defects, interlayer bonds, stress, access and
durability must all be measured at the intended depth. No reviewed study
combines the full hard-tissue and periodontal target in a mature human tooth.

## Integrated research sequence

1. **Define the individual target and confidence map.** Link each surface or
   internal region to a baseline source, visibility, metric scale and
   uncertainty. Report enamel and dentin deficits separately. Preserve unknown
   thickness and hidden crack extent as unknown.
2. **Classify the surviving substrate.** Separate retained enamel, exposed
   dentin, root/cementum, restorative material and pulp/attachment involvement.
   Identify which interfaces a candidate must rebuild. The required route may
   differ across regions of one tooth.
3. **Compare repair architectures against those defects.** Evaluate acellular
   mineral growth, cell-produced enamel components and dentin/pulp repair as
   separate candidates. A tooth-replacement strategy is a separate branch if
   preserving the natural tooth is not supported; it must not silently replace
   the primary preservation objective.
4. **Test hard-tissue recovery in characterized ex-vivo specimens.** Use
   independently measured geometry and material references. Compare appropriate
   intact, damaged and established restorative controls; retain donor/tooth
   nesting. Determine recovered volume, depth, architecture, interface strength,
   leakage, crack progression and repeated-load behavior. These are endpoint
   requirements, not instructions for making or treating a lesion.
5. **Evaluate interactions with living tissues.** Determine compatibility with
   pulp, gingival barrier and the attachment niche. Mineral-forming strategies
   must preserve the soft ligament space. Record perfusion, adult cell identity,
   controlled proliferation and adverse healing where relevant.
6. **Test the reconstructed tooth as an integrated load-bearing unit.** Restored
   crown height, contacts and shape change force transfer into the root and PDL.
   Evaluate the final intended crown geometry with the attachment; successful
   tests on the damaged crown cannot establish the final loading state.
7. **Evaluate durability after withdrawal.** Track both tissue/structural
   maintenance after the intervention ends and positional stability after any
   finite support is removed. Retain failures, tissue loss, resorption and
   fracture in the denominator.

## Acceptance and falsification

Set domain-specific margins before comparative outcomes are inspected. Missing
data remain unassessed. There is no universal percentage of regeneration that
allows a good appearance to offset failed pulp, crack or attachment outcomes.
Report successful components separately until every damaged, required domain
passes the [restoration contract](restoration_contract.json).

The full-restoration hypothesis fails if the target thickness cannot be reached,
the new material is architecturally or mechanically unsuitable, a crack keeps
propagating, the interface leaks/delaminates, the pulp loses vitality, the PDL
mineralizes, or the tooth drifts after finite support ends. A purely geometric
match establishes only the geometric endpoint.

## Immediate computational deliverable

Build a small target-reconstruction benchmark using a known intact 3D tooth
surface with withheld views and regions. Test how well a photo-constrained
method recovers visible shape and how uncertainty grows in hidden regions.
Separately benchmark material candidates by demonstrated depth, volume and
interface performance. Do not use a rendered surface or a predicted thickness
map as evidence of biological regeneration. Actual historical photographs can
then supply individual constraints when privately available and suitable.

The first [public-data silhouette pilot](TOOTH_TARGET_RECONSTRUCTION_PILOT.md)
is now complete: one pre-instrumentation scan, with intactness unqualified,
provides a coarse outer-envelope reference. Three perfect outlines still
permit approximately 21% excess reconstructed volume for this baseline.
This establishes a failure case, not validated photo reconstruction or enamel
thickness recovery. The [depth/interface comparison](ENAMEL_SCALE_AND_INTERFACE_COMPARISON.md)
now distinguishes single-layer, repeated-layer and cell-generated evidence.
