# From missing crown volume to a stable living tooth

Reviewed and computed 2026-10-19. This advances the preserved goal of restoring
the individual's tooth substance, original form, gums and living attachment,
with durable position after **finite** support. The new deliverable is a
quantitative material budget and an integrated test specification, following
the completed geometry work. No tooth was treated or material manufactured.

**Engineering decision:** the next biological/materials milestone should be
through-depth and interface performance at a measured defect volume. Only a
material architecture that passes that test should enter the bilateral-insertion
PDL assay with the **full intended crown** and a documented support-removal
transition. The current evidence does not justify assuming either bulk growth
or native load-bearing attachment from separate thin-layer and cell studies.

## Computed volume/depth budget

The [inputs](inputs.json) keep published configurations separate from synthetic
defects. Hasan et al. report a **2 × 4 mm** aprismatic-enamel footprint, an
approximately **10 µm** mineral layer (Fig. 2d), an approximately **5 µm** dentin
example (Fig. 2i), and a **2 µm coating** configuration with growth through it
for prismatic enamel (Fig. 3). These supply nominal scale anchors. They do not
supply an independently mapped, uniformly covered final volume or uncertainty
distribution. The dentin examples differ between figures and are not pooled.
[Primary article and figure captions](https://www.nature.com/articles/s41467-025-64982-y).

The script applies those depths to a **flat 8 mm² reference footprint** for
comparison. `Volume = area × depth`; a 10 µm configuration gives a prism-equivalent
0.080 mm³, 5 µm gives 0.040 mm³, and 2 µm gives 0.016 mm³. These are calculated
equivalent volumes, **not measured recovered volumes**. Curvature, incomplete
coverage, porosity, a thickness distribution and uncertainty in source depth
are unmeasured here.

| Synthetic defect over the reference footprint | Missing enamel volume | Missing dentin volume | Matching nominal configuration / equivalent enamel-depth span |
|---|---:|---:|---|
| 0.05 mm enamel loss; 0.04–0.06 mm sensitivity bounds | 0.40 mm³; 0.32–0.48 | 0 | 2 µm: 4%; 10 µm: 20% |
| 0.5 mm enamel loss; 0.45–0.55 mm bounds | 4.00 mm³; 3.60–4.40 | 0 | 2 µm: 0.4%; 10 µm: 2% |
| 0.5 mm enamel plus 0.5 mm dentin loss; independent depth bounds | 4.00 mm³; 3.60–4.40 | 4.00 mm³; 3.20–4.80 | Dentin-surface 5 µm example: 1% of enamel depth; dentin replacement unestablished |
| 0.5 mm enamel loss at a native/restorative-material boundary | 4.00 mm³; 3.60–4.40 | 0 | No matched substrate result in this input set; no transfer estimate |

Bounds in this table are investigator-defined **synthetic target sensitivities**,
not source variance, confidence intervals, segmentation errors or a person's
measurements. For example, 10 µm divided by 0.45–0.55 mm gives 1.82–2.22%; this
does not include uncertainty in the approximate source depth. Do not interpret
the reciprocal ratios as a treatment count or a growth rate. Published
repeat-cycle thickening remains a positive lead in the earlier
[scale comparison](../../periodontal-attachment-restoration-2026-10-11/ENAMEL_SCALE_AND_INTERFACE_COMPARISON.md),
with its interlayer and bulk-depth limitations retained.

The combined-loss fixture exposes a different gap from a low depth fraction:
a superficial enamel-like layer on dentin cannot be credited as replacement
of the separate **4 mm³ missing dentin compartment**. Nor does it establish the
new dentin/enamel transition, pulp-space integrity or a reconstructed crack
path. The script deliberately leaves qualified dentin recovery **unknown**.

## Substrate and transition requirements

| Surviving substrate | Required additional evidence before transfer | Useful way the architecture could fail |
|---|---|---|
| Enamel | Depth-resolved prism/interprism organization, host continuity, spatial coverage and wet cyclic interface integrity at the intended thickness | Good superficial indentation with deep interlayer separation or progressive cracking |
| Exposed dentin | Separate dentin volume/organization; a graded transition and adjacent tissue; permeability, crack path and fatigue across the reconstructed region | Hard enamel-like cap on missing/weak dentin; leakage or a crack crossing the repair |
| Existing restorative boundary | Boundary-specific continuity, sealing, differential deformation and failure mode; separate from native enamel/dentin results | Delamination at the old material edge despite mineral growth elsewhere |
| Cracked or altered host tissue | Independently characterized depth and viability/structural state; do not infer integrity from surface closure | A restored outline conceals a propagating host crack |

The transition must include more than a crystallographic boundary. Dong and
Ruse's human-specimen fatigue study described crack deflection across a broad
DEJ complex. Imbeni et al.'s later interfacial-fracture study instead found
cracks traversing the optical DEJ and arresting in adjacent mantle dentin with
ligament bridging. These different observations/definitions make **crack path
through the whole reconstructed region** a stronger required endpoint than
assuming the visible interface itself is the barrier.
[Dong and Ruse, primary-study abstract](https://pubmed.ncbi.nlm.nih.gov/12833436/),
[Imbeni et al., primary-study abstract](https://pubmed.ncbi.nlm.nih.gov/15711554/).
Only these abstracts were inspected for those two sources; raw fracture data
and complete methods have not been independently audited.

The existing [human PDL dossier](../../organoid/periodontal-ligament-interface/README.md)
already requires bilateral fiber insertion and recoverable mechanics rather
than aligned cells or stiffness alone. This study preserves its negative
results and gate order; it does not count a root-fragment or ectopic construct
as an intact-socket result. The new link is to test **the final crown and its
material junctions during the same loading history as the attachment**.

## Why crown repair changes the attachment test

The six synthetic contact/load cases evaluate `moment = contact vector × unit
load direction` about a fixed root/socket origin. The damaged contact is
`(0,0,4)` mm; the restored height is 4.5 mm, with lateral offsets −0.5, 0 or
+0.5 mm. A normalized oblique load has direction `(0.5,0,−√0.75)`.
These are deliberately invented geometry probes, not measured anatomy or a
recommended applied load.

| Restored contact | Oblique moment magnitude, N·mm per N | Change from damaged geometry |
|---|---:|---:|
| Negative lateral offset | 1.817 | −9.15% |
| Height change only | 2.250 | +12.50% |
| Positive lateral offset | 2.683 | +34.15% |

The damaged reference is 2.000 N·mm per N. With a normalized axial load, the
damaged contact has zero moment about this origin; ±0.5 mm offsets create
opposite signed moments of magnitude 0.5 N·mm per N. A percentage change from
zero is undefined and remains null. Preserving the decreasing-moment case
prevents claiming that every restored contour increases bending.

This calculation establishes only the equilibrium sensitivity to contact
location. A root/socket origin is not a fitted center of resistance. No PDL
material law, force magnitude, contact redistribution, interface strength,
stress/strain, support load share or predicted drift is available. The
practical implication is to record the actual load vector and contact map
before and after crown repair, and to test both supported and unsupported
states at the same final geometry. A result on a shortened crown or behind
a rigid support cannot answer that question.

## Integrated test specification

The [machine-readable contract](integration_contract.json) preserves all nine
domains of the parent restoration contract and four transfer gates:

1. **I0: qualify measurements and the target.** Independent tooth/donor identity,
   enamel and dentin surfaces, host crack extent, substrate and baseline-pose
   provenance. Determine uncertainty and reference distributions before fixing
   candidate acceptance margins. Unknown hidden anatomy remains unknown.
2. **I1: meet a real defect-volume and interface target.** Compare matched intact,
   damaged, process and relevant restorative controls. Replicate a source-scale
   positive control, then test one prospectively chosen greater depth; record
   all unsuccessful architectures. Recover volume and architecture through
   depth, plus permeability, interlayer failure, crack path and wet cyclic
   performance. An insert and a growth process are distinct architectures.
3. **I2: challenge crown and attachment together.** Use the full intended crown
   with qualified root-facing/bone-facing insertion, compartment identity and
   no mineral bridge. Measure force/displacement, recovery and crown-interface
   damage under the same loading history, with support state explicitly known.
   A fixture cannot establish in-socket positional recovery.
4. **I3: test durable living integration after withdrawal.** In a separately
   qualified retained-tooth model, assess final-crown integrity, unloaded
   target-pose error, loaded excursion, drift from the immediate post-removal
   baseline, PDL identity, pulp, gingiva, ankylosis and resorption. Record actual
   support/intervention withdrawal times and a predeclared follow-up horizon.
   Every required damaged domain must pass independently.

Once the modules qualify, crossing hard-tissue candidate/control with
attachment candidate/control tests their interaction, with appropriate intact
and failure references. Independent teeth/donors and manufacturing batches are
the units; images and loading cycles are nested observations. Specimen count
and numerical acceptance margins remain unresolved until repeatability and a
variance pilot support them. No material recipe, treatment schedule, animal
operation or patient procedure is specified here.

**Pose measurement needs an unchanged frame:** crown reconstruction changes
the surface being registered. Register stable jaw/root structures with a
qualified mask; exclude the repaired crown and remodeled socket as stable
references. Keep rigid motion separate from added/lost material and keep
unloaded drift separate from reversible loaded movement. The existing
[pose metrology plan](../../periodontal-attachment-restoration-2026-10-11/POSITION_STABILITY_METROLOGY_PLAN.md)
remains the measurement prerequisite.

The goal of independence from lifelong retention is retained as a durability
requirement. It is not demonstrated by low movement while support remains in
place, nor by stability accompanied by ankylosis. Finite follow-up also cannot
establish lifelong stability. The generated audit reports all **nine domains
unassessed**, with no integrated success claim.

## Next falsifiable step and reproduction

The next material decision is whether a substrate-qualified candidate retains
through-depth organization, sealing and crack resistance at one **measured,
prospectively selected greater depth**, compared with its thin-layer positive
control and intact tissue. Failure at depth blocks transfer to the existing
PDL assay; passing it earns an I2 integration test, not a complete-regeneration
claim. Choose depth, specimen count and margins after the measurement/variance
pilot, before candidate ranking. This converts the budget into a measurable
decision without predicting that more repetitions will grow bulk enamel.

From the repository root:

```text
python studies/checklist-progress-2026-10-19/dental/analyze_integration_gaps.py
python -m unittest discover -s tests -p test_checklist_dental_integration.py -v
```

[Generated results](derived/integration_gap_results.json) contain **five
substrate-matched scale comparisons and six contact/load cases**, input/script/
contract SHA-256 receipts and all unresolved domains. The calculation has no
external dependencies and no random sampling. Ten study checks pass. Docker's
workbench service was stopped, so `regen doctor` was unavailable; these study
checks do not establish biological performance. Primary pages were reviewed
through the browser on 2026-10-19. No new source files were downloaded and no
local-fetch provenance record is claimed.

Source rights remain separate from this original study commentary and code.
Hasan et al.'s article is [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/);
the inputs extract selected approximate numerical facts with attribution, and
the derived output adds explicitly synthetic calculations. No source figure,
photograph, mesh, full text or raw fracture dataset is redistributed. The two
DEJ articles are cited and briefly paraphrased; their source rights are not
changed. This study assigns no new repository-wide license and does not import
the unrelated MorphoMuseuM mesh license into these non-mesh calculations.
