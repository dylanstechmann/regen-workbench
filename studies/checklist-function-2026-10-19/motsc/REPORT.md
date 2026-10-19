# MOTS-c: identify the measured species before optimizing its delivery

**The useful new result is an analytical eligibility constraint.** Numerical donor-linked MSC repair data remain unavailable in the retrieved source, so no new metabolic-versus-repair effect size is claimed. The authorized pivot found primary evidence that reported immunoassay signal and native-parent LC/MS confirmation can disagree substantially. A delivery comparison must resolve the molecular species and intended function independently.

## What changed from earlier work

The [pinned atlas](https://github.com/dylanstechmann/geroscience-compound-atlas/blob/af7b57c2cfad64683f82044199cca812a01b9a03/studies/peptide-delivery-transfer-2026-10-09/README.md) already reviewed K14Q apparent clearance/function, CK2 binding and tagged nuclear trafficking. The [prior checklist qualification](../../checklist-progress-2026-10-19/compounds/mots_repair_observations.json) added the MSC metabolic-activation/repair counterexample. This package does not rediscover those findings or repeat an oral search.

New work: current primary MSC source-data/hierarchy intake; the primary Knoop analytical comparison and its numerical signal/LOD scale separation; explicit distinctions among sample-storage stability, a pump/ELISA steady-state comparison and administered intact-parent PK; executable missing-data gates.

## MSC source intake: demographics are not numerical repair observations

The current [MSC primary study](https://doi.org/10.1186/s41232-026-00431-7) has six lean and six obese adipose-MSC donors, three women/three men per group. Its only numerical table gives demographic aggregates. Endpoint results are figures, the listed supplement is a JPG, and the data statement requires a corresponding-author request. No public numerical endpoint workbook, individual donor IDs, culture crosswalk or donor-to-mouse assignment was located in the downloaded primary XML/HTML. No contact or figure digitization was performed.

The source's units remain distinct:

| Measurement context | Source unit and hierarchy | What this intake cannot reconstruct |
|---|---|---|
| Culture proliferation, adhesion, gene markers and immunoblots | Twelve human donors; with/without pretreatment; reported group n=6; cultured cells after three passages | Individual donor paired responses, culture/technical replication and cross-endpoint covariance |
| Mouse repair comparison | Six groups of six recipient mice; pretreated human MSC transplantation | Donor-to-recipient assignment, independent donor replication in mice or native peptide systemic PK |
| MRI perfusion/oxygenation/volume | Cortex/medulla nested in recipients; endpoint follow-up two weeks after cells | Raw mouse-level values and metabolic-marker/function pairing |
| Histology | Injury score and fibrosis; ten fields nested in kidney/mouse | Field independence, raw recipient-level values or joint endpoints |

The twelve donors and 36 recipients do not form 48 independent biological samples. Repeated visits, wells, fields and kidney compartments do not enlarge donor or mouse n. Source-reported activation and unfavorable repair findings remain qualified as before, including lean/obese differences and selected favorable oxygenation/volume outcomes. The prior T2* caption-direction ambiguity remains unresolved. They are not new independent reanalysis results.

Intracellular MOTS-c was assessed by antibody immunoblot; the methods document precautions for small-peptide transfer. Those precautions are real assay evidence, but do not identify exogenous intact parent separately from products or altered endogenous signal. The source's interpretation of increased signal as uptake does not supply an oral F or parent concentration-time profile.

## New primary analytical comparison

Knoop et al. report an LC/MS assay for human plasma with **LLOD 100 pg/mL**, four in-vitro-derived metabolites and two oxidation products included in its analytical scope. In 20 healthy reference subjects, ELISA signals **45.9–218.5 ng/mL** were not confirmed by LC/MS. The authors report validation for quantitative interpretation; this audit records that evidence without claiming independent revalidation or an unseen LLOQ/participant table. [Primary abstract, DOI 10.1002/rcm.8337](https://pubmed.ncbi.nlm.nih.gov/30394592/)

The reproducible arithmetic is:

`100 pg/mL = 0.1 ng/mL`

`reported ELISA signal / reported LC/MS LLOD = 459–2,185`

This is **reported signal/detection-limit scale separation**. It is not a true parent-concentration bound, assay-bias estimate, calibration slope, proof of specificity, proof that endogenous peptide is absent, or universal ELISA failure. There are no participant-level paired observations here; nondetects are not set to zero. Healthy reference samples are not administered-peptide PK data.

Two [publisher-visible supporting-information captions](https://analyticalsciencejournals.onlinelibrary.wiley.com/doi/10.1002/rcm.8337) further constrain interpretation. SI2 describes storage under different conditions, with relative parent/internal-standard peak-area ratios through 24 h and trend lines for visualization. That is sample-handling context, not a measured in-vivo half-life. SI5 describes a modified, C-terminally amidated ELISA-kit reference. It flags reference-form identity as relevant, but does not establish the cause of the human assay discrepancy. Both PDFs returned 403; no spectra, image-derived concentrations or stability curve were inspected or reconstructed.

## Preserve K14Q calibration while qualifying the steady-state claim

The [K14Q primary paper](https://doi.org/10.18632/aging.202529) explicitly found lower variant sensitivity in its ELISA, then used a **variant-specific calibration curve in human plasma** for variant measurements in carriers and infused mice. This corrective calibration must be retained, rather than dismissing the result using a different commercial assay's discrepancy.

The mouse pump comparison sampled plasma 24 h after implantation, called it steady state and checked remaining pump peptide. It reports a 2.6-fold slower calculated clearance for K14Q. This is not a comparative intact-parent decay series; no pump-PK sample size was located in the retrieved method, and functional-study mouse group sizes are not substituted.

For a simple linear parent mass balance at steady state:

`C_ss = F × R / CL`

Here `R` is input rate, `F` its systemic fraction and `C_ss` the exogenous intact-parent increment after resolving endogenous contribution. A single immunoreactive concentration does not independently identify each term. Variant calibration addresses sensitivity; it does not resolve every product's cross-reactivity, native species identity, endogenous baseline or intraperitoneal systemic fraction.

Under one-compartment linear disposition, `t½ = ln(2) × V / CL`; an appropriate terminal-volume interpretation is needed in more complex disposition. A steady-state ratio supplies neither terminal slope nor volume. Consequently, no native-parent clearance or half-life is calculated here. K14Q's functional counterexample remains useful, but improved molecular persistence is not newly proven by this intake.

## Concrete next decision

Before comparing delivery variants, require a parent-resolved assay with identity-qualified calibrators, matrix performance and controlled sample stability; distinguish endogenous background, intact administered peptide, products and labels. Then link that exposure to donor-stratified intended repair function and senescence/inflammatory outcomes. Greater immunoreactivity or AMPK activation cannot stand in for that link.

`inputs.json` preserves seven measurement domains and four PK evidence contexts. All four fail the concentration-time intake gate for explicit reasons; **zero numerical administered-parent PK datasets** qualify in this frozen source set. This is a bounded source finding, not proof of field-wide absence. The gates distinguish finite-interval parent AUC, terminal half-life, absolute clearance from AUC, and oral F. Clearance from AUC additionally requires known administered parent amount, systemic input fraction and complete AUC or qualified terminal extrapolation; two finite-interval points do not suffice. Absolute oral F separately requires dose-normalized paired oral/IV parent AUCs with complete or qualified extrapolated coverage for **both routes**; finite-window ratios or one route's complete coverage cannot pass. A proper steady-state mass-balance estimate is a separate method; it does not inherently require a decay series, but this source lacks the identified terms needed for native-parent clearance. Assay flags explicitly record source-reported evidence rather than independent validation certification. Source-presence gates alone never compute efficacy or validate a human use.

No oral F, analogue rank, new sequence, synthetic performance, human regimen or preparation method is supplied.

## Reproduction and access

Eight owned artifacts are this report, `ANALYSIS_PLAN.md`, `inputs.json`, `source_manifest.json`, `analyze_motsc.py`, `results.json`, `pk_eligibility.csv` and `test_motsc_specificity.py`. Run:

```text
python studies/checklist-function-2026-10-19/motsc/analyze_motsc.py --check-cache
python -m unittest discover -s studies/checklist-function-2026-10-19/motsc -p test_motsc_specificity.py -v
```

**Four downloaded source hashes match and ten targeted tests pass.** Scripts use the standard library and canonical UTF-8/LF input hashing. Raw sources and genuine `regen.record` receipts remain ignored in `data/literature/checklist-motsc-function-2026-10-19/` and `data/provenance/`. Full Knoop text redirects to its abstract; failed supplement/proceedings access is recorded separately without fabricated receipts or full-text claims. MSC source figures/text are not redistributed or adapted. The source set is frozen; no further access retries or contacts were made. Root performs full integration checks; Docker workbench is not running.
