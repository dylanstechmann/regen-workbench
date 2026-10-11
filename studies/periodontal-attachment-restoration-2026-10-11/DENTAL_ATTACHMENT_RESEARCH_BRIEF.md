# Periodontal attachment restoration benchmark

This study turns “restore a tooth to its youthful state” into a set of measurable outcomes. The unit of repair is the root cementum, inserting periodontal ligament (PDL) fibers, alveolar bone interface, gingiva, and the tooth’s position and loading environment. A tooth that is simply held in place, or feels stiff, has not necessarily regained the native attachment system.

This is an AI-assisted evidence synthesis and computational benchmark. The original animal experiments belong to the cited source authors; this workspace analysis is not a new biological experiment or clinical treatment validation.

## Evidence checkpoint

The 2022 rat replantation study measured extraction force–displacement after local PDGF-BB pretreatment. At day 21, the paper reports recovery to 54% of control for failure load, 68% for maximum deformation, and 44% for failure energy (toughness); stiffness was described as almost control, but an exact ratio was not given. Its table also reports root or socket fractures during the extraction test in 0/10 non-replanted controls, 8/9 PBS controls, 10/10 atelocollagen controls, and 3/10 PDGF-BB-treated replants. The same paper reports an area-standardized strength of 2.45 N/mm² versus 3.39 N/mm² control and calls that “approximately 76%.” Direct division of the rounded values is 72.3%, so both source statements remain visible in the derived data. Those measurements are animal group summaries, and extraction is not normal chewing. The authors also observed abnormal bone-like structures in the dental pulp in most replanted teeth, including the PDGF-BB group. [Komatsu et al., 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC8881622/)

A 2011 progenitor-cell replantation study provides a closer functional target. Mouse PDL progenitors were placed on denuded rat molar roots and replanted. At 8–16 weeks the treated roots had a PDL-like apparatus with fiber attachment; all 22 treated replants were reported firmly attached. At 10 N, displacement was 156 ± 19 μm in treated replants and 141 ± 23 μm in wild-type controls. At 15 N, it was 300 ± 26 μm and 297 ± 34 μm. Untreated loose replants displaced 626 ± 31 μm under 1 N. This is meaningful proof-of-concept that a progenitor-populated, topography-conditioned root can restore attachment and physiologic mobility in rats. It does not demonstrate how to reposition an in-situ, trauma-displaced human tooth or eliminate the need for any temporary stabilization. [Dangaria et al., 2011](https://pmc.ncbi.nlm.nih.gov/articles/PMC3029000/) [PubMed record](https://pubmed.ncbi.nlm.nih.gov/20795795/)

Together, these papers expose why a single stiffness value is a poor regeneration endpoint. Functional PDL and an ankylotic bone bridge can act as parallel load paths and produce similar apparent stiffness while differing in shock absorption, mobility, toughness, and tissue identity. The included reduced model is intentionally an algebraic identifiability demonstration, not a fitted or predictive finite-element model.

The generated comparison is available as a [vector figure](derived/mechanics_benchmark.svg).

## Engineering benchmark

The first restoration benchmark should track independent axes rather than collapse them into a “percent regenerated” number:

- Root position and occlusal contact before injury, after reduction, and after temporary support is removed.
- Root cementum continuity, width and vascularity of the ligament space, and fiber insertion into both cementum and alveolar bone.
- Absence of ankylosis, inflammatory or replacement root resorption, and pulpal injury.
- Tooth displacement and recovery under a defined force series, followed by load–deformation response, tangent stiffness, maximum load, failure energy, and fatigue across repeated loading.
- Stability of the restored position under physiologic loading after support removal, with relapse measured rather than assumed away.

For the user’s blunt-force injury case, the key gap is the transition from a tooth that has healed in a displaced position to a tooth returned to its original position with native attachment. A future model needs an explicit initial-position target, alveolar socket geometry, fiber direction and insertion, occlusal load vectors, and a time-varying healing state. It must distinguish short-term reduction or stabilization used to preserve alignment during repair from permanent retention required because the supporting tissues never recovered. The evidence reviewed here does not show that regenerative therapy alone can move an in-situ tooth back into its original position.

The next computational step is a calibrated, viscoelastic tooth–PDL–bone model with separate fiber and bridge elements. Fit it only when per-specimen force–displacement data or digitizable source curves are available; otherwise run clearly marked sensitivity cases. Use the model to ask which measurements distinguish healthy attachment from ankylosis, and whether a proposed repair restores both the desired position and the native compliance profile. Do not tune an unobserved material parameter until a desired clinical conclusion appears.

## Experimental sequence

1. **Recover source-level mechanics.** Obtain figure values or individual data from the authors or supplement for the PDGF-BB study; resolve the 76% versus 72.3% arithmetic discrepancy. Extract the progenitor paper’s displacement curves and group sizes from its official full text. Do not manufacture replicate rows from mean curves.
2. **Build a human-compatible co-culture screen.** Compare periodontal progenitors, cementoblast-lineage cells, gingival fibroblasts, endothelial support, and immune-context controls on root-mimetic mineral surfaces. Score lineage stability, oriented fiber deposition, insertion at both interfaces, mineral-bridge formation, viability, and inflammatory response together.
3. **Vary the engineering controls.** Test cementum microtopography and chemistry, scaffold modulus and degradation, cell-source composition, vascular support, and timed cyclic loading. Include no-cell, no-topography, misoriented-fiber, and pro-mineralization controls to reveal failure modes.
4. **Use functional organoid and bioreactor endpoints.** A periodontal tissue construct should be challenged under compressive and tensile cycles and then measured for recovery, stress relaxation, fatigue, and attachment failure. Imaging and transcript profiles support the readout; they do not substitute for force, displacement, insertion histology, or absence of bridging.
5. **Advance only on convergent restoration.** Require native-like displacement, toughness, fiber insertion, cementum and socket integrity, lack of ankylosis/resorption, viable pulp where relevant, and stable position after temporary support removal. A single growth-factor response or collagen marker increase is insufficient.

## Reproduction and generated files

Run the extraction and benchmark scripts in the repository’s `regen-workbench` container:

```bash
python /lab/workbench/studies/dental-attachment-mechanics-2026-10-11/fetch_mechanics_sources.py
python /lab/workbench/studies/periodontal-attachment-restoration-2026-10-11/build_mechanics_benchmark.py
```

The source extraction receipt distinguishes retrieved full text from endpoint failures. The derived folder contains normalized endpoint ratios, the full fracture table, the displacement comparison, a stiffness non-identifiability sweep, a figure, and a provenance record. The second article’s official PMC page was reviewed, but its Europe PMC full-text XML endpoint returned HTTP 500; it is not represented as a locally downloaded specimen-level dataset.
