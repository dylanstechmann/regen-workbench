# Human ameloblast organoids: what the 2026 graft result establishes

This source review examines Patni et al. (2026), ["Soluble Notch agonist enables human ameloblast maturation and enamel-like tissue formation for tooth regeneration"](https://doi.org/10.1038/s41368-026-00429-4), together with the primary article and selected pages of its supplementary PDF. It is an evidence review of a component model, not a treatment design or a claim of whole-tooth regeneration. The retrieval hashes and pages inspected are listed in [primary_context_receipt.json](primary_context_receipt.json); source files remain in ignored private literature storage.

## What the study demonstrates

The study uses a soluble multivalent DLL4 scaffold (C3-DLL4) to activate Notch signaling and advance human iPSC-derived ameloblast organoids toward a secretory/mature state. The reported cell markers include enamel-associated proteins and maturation markers, including ENAM, MMP20, AMELX, KLK4 and WDR72. Imaging shows epithelial polarity and rosette-like organization. These data support a human in-vitro differentiation and signaling result.

For the in-vivo component, the Methods describe day-25 C3-DLL4-treated ismAM organoids transplanted beneath the kidney capsule of adult male NOD-SCID mice (n=6), harvested after 21 days. Figure 4 shows local high-density foci on microCT and polarized human-cell regions; histology and staining include H&E, Masson's trichrome, Alizarin Red and von Kossa. The Supplementary Figure S5 shows mineral-staining and ameloblast-marker panels, including an additional graft sample labelled S2. This supports an ectopic, mineral-bearing graft containing human-derived epithelial structures with ameloblast-associated markers.

## What remains unresolved

The graft experiment is short and ectopic. A kidney capsule supplies a vascularized environment but does not recreate a tooth socket or test connection to dentin, pulp, cementum, PDL, alveolar bone or gingiva. The reported mineral signal does not itself establish mature enamel ultrastructure or function: the reviewed article and supplement do not report enamel rod/prism architecture, enamel-dentin bonding, hardness, wear, acid resistance, occlusal loading or repair performance on a tooth.

The denominator is also not fully resolved at the outcome level. The Methods report six recipient mice, while the figure presents representative graft images and the supplement labels one additional sample S2; sample-by-sample graft success, stage allocation and quantitative mineral outcomes are not itemized in the reviewed material. Figure 4's caption refers broadly to isAM/ismAM grafts, whereas the Methods describe the transplanted ismAM condition as C3-DLL4-treated for 25 days. The per-stage allocation therefore cannot be reconstructed from those descriptions alone.

The edited-cell work is based on the WTC11 iPSC background. The two DLX3 knockout clones, KO-10 and KO-13, are independent edited clones within that background, not independent donor lines. The deposited GSE307437 series contains six RNA libraries, two source-labelled replicates per condition; sample-to-clone and independent differentiation-batch identities are not resolved in the source labels. The separate RNA analysis in this repository is descriptive and retains those limits in [RNA_CONTEXT.md](RNA_CONTEXT.md).

## Supplementary workbook audit

The previously unreviewed supplementary workbook contains seven figure-labelled sheets with static heatmap or pathway-summary values (178 nonempty cells, no formulas). The article describes the human Fig. 1c and Fig. 5b values as cluster-average expression from the 20–22 gestational-week single-cell dataset; those summaries do not expose per-donor observations. The other tabs are figure-linked human or mouse heatmap values, not a sample-level expression matrix. The workbook provides no donor, clone, culture-batch, library, or graft-outcome fields, and its cells do not define units or normalization independently of the figure captions and article text.

The manuscript Methods report six iAM organoid RNA samples, two biological replicates per condition, and deposit them as GSE307437. The retrieved series labels one WTC-11 background, but neither its source labels nor this workbook identify clone assignment or independent differentiation batches. The workbook therefore does not upgrade the replicate labels to donor-independent validation. It also does not resolve the in-vivo graft denominator: the article reports six recipient mice, while outcome-by-graft success and stage allocation remain unitemized in the reviewed figures and supplement. The retained workbook hash and inventory are recorded in [primary_context_receipt.json](primary_context_receipt.json).

## Translational interpretation

The result is a meaningful step toward producing ameloblast-like cells and ectopic enamel-like mineral, and it gives a tractable platform for studying ameloblast maturation and DLX3 function. It does not show repair of worn or carious enamel in an adult tooth, nor does it show a complete bioidentical tooth. Enamel-only repair and whole-tooth replacement should remain separate development goals: the latter additionally requires dentin, pulp, a correctly positioned enamel-dentin interface, periodontal attachment, vascular and sensory integration, eruption/placement, occlusion and durability.

The next evidence should identify which target is being tested, then use independently differentiated and donor-diverse cell sources with explicit graft-level denominators. For an enamel-repair claim, the discriminating endpoints include the enamel-dentin interface, mineral composition/architecture and mechanical durability. For whole-tooth claims, an organized enamel-dentin-pulp unit and a functional periodontal interface must be measured in a tooth-site model. These are proposed evidence domains, not an experimental protocol.

## Source note

The full article and supplementary archive were retrieved through the workbench's source-recording workflow. Supplement pages 4, 8 and 10 were visually reviewed: the timeline, graft histology/marker panels and DLX3-edit descriptions, respectively. The companion XLSX was inventoried sheet-by-sheet for its figure-labelled values, formulas and sample-level fields; it contains no sample-level or graft-outcome records. The article's CC BY-NC-ND license remains applicable, so this summary paraphrases findings and does not redistribute figures or raw source data.
