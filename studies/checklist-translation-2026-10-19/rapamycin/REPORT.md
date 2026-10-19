# Rapamycin: selective inhibition is measurable; reproductive protection remains unmeasured

**DL001 is a useful published mechanism comparator, not an established fertility-sparing rapamycin replacement.** This pass reconstructs original quantitative data rather than proposing a new analogue. It resolves the apparent selectivity-number discrepancy, shows that in-vivo pathway effects were unequal across tissues, and identifies the joint measurements missing from the user's goal of retained useful effects with reduced reproductive harm.

## New work versus the existing atlas

The [pinned rapamycin-selectivity audit](https://github.com/dylanstechmann/geroscience-compound-atlas/blob/af7b57c2cfad64683f82044199cca812a01b9a03/studies/rapamycin-selectivity-2026-10-09/README.md) already covered DL001, binary brain/periphery pharmacology, local skin delivery, transplant reproductive associations, mouse recovery and the need to measure testicular compartments. Its synthetic selectivity examples established algebraic counterexamples, not candidate-specific PK or reproductive outcomes. The [delivery-transfer audit](https://github.com/dylanstechmann/geroscience-compound-atlas/blob/af7b57c2cfad64683f82044199cca812a01b9a03/studies/peptide-delivery-transfer-2026-10-09/README.md) is also continuity context.

| Evidence | Existing conclusion | Newly reconstructed or qualified here |
|---|---|---|
| DL001 cell selectivity | Greater mTORC1 selectivity is possible | Original four biological IC50 pairs per compound; exact distinction between mean ratios and ratios of means |
| DL001 in-vivo pathway effects | Reduced C2 effects and altered metabolic outcomes in mice | 18 liver/muscle/heart series; unequal C1 effects are visible, and none measures testicular parent exposure |
| Compound exposure | PK/distribution must be measured | 27 source whole-blood compound observations; different sex/cohort/context from selected tissue measurements; no free or testicular concentrations |
| Reproduction/recovery | Human signal and partial animal recovery | Explicit denominators, mass-versus-function distinction and unresolved human semen-analysis sample size; no candidate risk reduction inferred |
| mTORC2 sparing | Hypothesis rather than fertility proof | Primary male-germline Raptor result supports a C1-dependent reproductive mechanism that C2 sparing alone cannot exclude |

## The selectivity figures are different estimands, not contradictory results

The original [DL001 Source Data workbook](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-019-11174-0/MediaObjects/41467_2019_11174_MOESM3_ESM.xlsx), Figure 1f, contains four paired IC50 estimates per compound. The [primary study](https://doi.org/10.1038/s41467-019-11174-0) identifies a 24-hour PC3-cell AlphaLISA readout of phospho-S6 S240/S244 and phospho-AKT S473. These are contextual pathway-response IC50s, not purified-complex binding constants or testicular-cell potencies. Three technical readings per biological experiment do not make twelve independent biological replicates.

| Descriptive estimate | Rapamycin | DL001 |
|---|---:|---:|
| Mean C1 IC50, pM | 63.30875 | 74.936 |
| Mean C2 IC50, pM | 534.8955 | 26,245.41275 |
| Mean of four paired C2/C1 ratios | 9.6944 | 433.3769 |
| SEM of those four ratios | 3.0595 | 168.3200 |
| Ratio of mean C2 IC50 to mean C1 IC50 | 8.4490 | 350.2377 |

Comparing the mean paired selectivities gives **44.7038-fold** DL001/rapamycin; comparing the ratios of mean IC50s gives **41.4532-fold**. The first reproduces the article's approximately 430-fold within-DL001 selectivity and approximately 44-fold relative improvement. Pairing follows the same source columns within each compound; no cross-compound replicate pairing is invented. The four DL001 ratio estimates span 94.54–829.23. Their dispersion and upstream IC50-fit uncertainty must not be erased by quoting one number as an intrinsic constant. No new p-value or confidence interval is manufactured from technical readings.

The Figure 1d workbook group headers say “S6K,” while the article caption/methods identify the AlphaLISA phospho-S6 endpoint. This audit uses the caption/method endpoint and the already provided Figure 1f IC50s; it does not silently refit ambiguously labeled curves or pool the separate 48-hour immunoblot assay with the 24-hour AlphaLISA assay.

The C1 and C2 AlphaLISA conditions also differ in serum/stimulation state.
Their response ratios therefore retain those assay contexts; they are not
an intrinsic binding-selectivity measurement under identical cell conditions.

## In-vivo comparison: unequal target effects and incomplete exposure information

Figure 3d source values are **normalized phosphorylation readouts**, not measured drug concentrations or equivalent tissue function. They come from female mice, four animals per group, in the source's approximately three-week experiment, after fasting and precollection insulin stimulation. The normalization and stimulation context matter. [Primary study, Figure 3 and animal methods](https://doi.org/10.1038/s41467-019-11174-0)

| Tissue | C1 readout rapamycin / DL001, means | C2 readout rapamycin / DL001, means |
|---|---:|---:|
| Liver | 0.04683 / 0.44925 | 0.20056 / 0.56494 |
| Gastrocnemius | 0 / 0.00575 | 0.14104 / 0.76769 |
| Heart | 0 / 0.32885 | 0.16852 / 1.24116 |

Vehicle means are approximately one. Zero entries are retained as source-normalized values; they do not prove absolute absence of kinase activity. Values above one are not forced into an inhibition-only model. Lower C2 suppression with DL001 occurs alongside materially different C1 readouts in liver and heart. This is not a matched-target-effect comparison, and a phospho-S6 readout does not establish retained action on every C1 substrate or an aging benefit. Testis is absent from the study's 11-tissue pathway panel.

Figure S4 reports whole-blood compound concentrations at one post-administration time point in a separate male, five-week context: DL001 **186.278 ±11.380 SEM ng/mL, n=9**; rapamycin **257.206 ±41.131 SEM ng/mL, n=18**. The descriptive ratio of means is **0.72424**. No new significance test is added, and the study describes the difference as nonsignificant. The retrieved main-text methods do not establish the blood assay's analytical specificity, recovery or lower limit. These reported compound values are not a verified unbound/native intracellular exposure measurement, a timecourse AUC, oral F, or a testicular concentration. They cannot be paired to the female Figure 3d animals or used to apportion selectivity between chemistry and exposure. [Primary source workbook, Figure S4](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-019-11174-0/MediaObjects/41467_2019_11174_MOESM3_ESM.xlsx)

## Reproductive outcomes: what is actually measured

In the separate adult-male mouse rapamycin study, the reported testis-pair mass was **72.88 ±7.876 mg** versus control **158.1 ±6.980 mg** (SD; four versus five animals). The ratio of reported means is **0.46097**, and the difference is **−85.22 mg/pair**. This study also measured testicular pathway/complex effects and showed meiotic/histological abnormalities; mass alone is not the functional evidence. No DL001 reproductive comparator, native testicular parent exposure or concurrent retained aging-function outcome is supplied. This animal mass result cannot establish human testicular shrinkage. [Adult-mouse primary study, Figure 1](https://doi.org/10.18632/aging.101740)

Its recovery comparison has **three animals per group** at two months after cessation. The abstract calls the effects partially reversible; results describe restored mass/motility and increased sperm counts. This intake has no individual numerical recovery data. Non-significance of a small-group mass comparison is not equivalence, recovery of every endpoint, or a human recovery guarantee. No numeric recovery probability is estimated. The publisher's original Figure 7 image link returned 404 through the web tool, so no invented or digitized recovery points replace the missing source observations.

The human transplant cohort's primary abstract reports **95/116 questionnaire respondents**; it does not establish the semen-analysis group denominators. Total sperm-count means were 28.6 versus 292.2 million, motility 22.2% versus 41.0%, and fathered-pregnancy rates 5.9 versus 92.9 per 1,000 patient-years (source 95% CIs 0.8–42.1 and 66.4–130.0). The associated unadjusted differences of means are −263.6 million sperm and −18.8 percentage points motility. The abstract reports improvement in three of six interruptions, not a general recovery probability. Transplant context, co-treatment, participation, regimen selection and pregnancy-attempt factors prevent a healthy-person causal or risk estimate. Testicular volume and a DL001 comparison are absent. Reported plus/minus dispersion is retained without assigning an unverified SD/SEM type. [Human primary abstract](https://pubmed.ncbi.nlm.nih.gov/18510638/)

## Why C2 sparing cannot pass the reproductive gate

Conditional male-germline **Raptor** disruption in mice caused meiotic arrest, defective sex-chromosome silencing and infertility. It supports an mTORC1 requirement in this cell context. It is a genetic intervention, not a pharmacological exposure threshold or evidence that DL001 itself causes the same outcome. It does provide a concrete mechanism counterexample to treating preserved C2 signaling as sufficient reproductive protection. Only the primary abstract was available in this intake. [Primary Raptor study](https://pubmed.ncbi.nlm.nih.gov/28490482/)

| Comparison context | C1/C2 data | Active/native parent in relevant testicular cells | Direct reproduction data | Matched intended geroscience function | Human candidate protection established |
|---|---|---|---|---|---|
| DL001 versus rapamycin, PC3 | Four paired estimates per compound | Absent | Absent | Absent | No |
| DL001 versus rapamycin, female tissue panel | Normalized pathway values | Testis not included | Absent | Absent | No |
| DL001 versus rapamycin, male metabolic/blood context | Separate study assays | Whole-blood values only | Absent | No aging-function equivalence | No |
| Rapamycin adult-male mouse reproduction | Testis pathway/histology observations | Not measured here | Mass, sperm/histology and recovery context | Absent | No |
| Sirolimus human transplant observation | Not linked to cellular pathway measurements | Not measured here | Semen/pregnancy association | Absent | No |

The executable gate keeps the missing columns missing; it does not convert cell selectivity, lower blood means, lower tissue mass, preserved motility, or an observational semen contrast into a candidate reproductive-risk reduction.

## What should happen next

1. **Use DL001 as a benchmark for pathway selectivity.** Preserve the assay duration, cell type, biological pairing and distinction between substrate readout and functional benefit. Its real source numbers improve a comparator specification; they do not justify a safe analogue.
2. **Choose the useful function that must be retained.** Systemic youthfulness is not an exposure-matching endpoint. For any specified tissue/function, compare compounds at retained function while independently tracking target and relevant testicular-cell parent exposure and C1/C2 responses. The current unequal tissue effects show why equal nominal input or a single blood time point cannot provide that match.
3. **Require direct reproductive outcomes alongside exposure.** Keep sperm quantity/quality, endocrine measures, testicular structure/volume, histology where appropriate, and recovery distinct. Evidence of C1-dependent germ-cell function means a C2-only protection hypothesis remains incomplete.
4. **Evaluate tissue-restricted delivery only against its stated scope.** The prior brain/periphery and local-delivery precedents do not establish testis-specific sparing or retained whole-body benefits. A useful next computational intake should require native released-parent measurements and same-context outcome links; there are no sufficient testicular PK data here to calibrate such a distribution model.

No new molecule, chemical structure, synthesis procedure, human regimen, safety threshold or equivalence claim is produced. Failure to locate joint measurements in these sources is not proof that no such evidence exists elsewhere.

## Files, source access and checks

`inputs.json` records source cells, units, population, sample hierarchy and missing measurements. `results.json` and `tissue_pathway_summary.csv` are deterministic descriptive outputs from `analyze_rapamycin.py`. Input hashing normalizes UTF-8 text line endings to LF.

`source_manifest.json` pins seven real downloads in ignored `data/literature/checklist-rapamycin-translation-2026-10-19/`, with their actual `regen.record` receipts. The complete original XLSX is 386,504,926 bytes; a bounded 400 MiB/55 s acquisition completed in 4.75 s. An earlier Range request was ignored by the server, and its 65,537-byte prefix is explicitly excluded from scientific extraction. XML and primary indexed abstracts supply source context; no inaccessible full text is invented. Only selected workbook worksheet/shared-string XML was parsed; embedded molecular depictions and images were not extracted.

Reproduce: `python studies/checklist-translation-2026-10-19/rapamycin/analyze_rapamycin.py --check-cache`. **Seven source hashes and 123 worksheet numeric values match.** The normal calculation works from tracked derived inputs without the raw cache; `--check-cache` additionally requires those local sources. Run `python -m unittest discover -s studies/checklist-translation-2026-10-19/rapamycin -p test_rapamycin_translation.py -v`: **8 targeted tests pass**. The Docker workbench service remains unavailable; root handles the full integration suite. These checks validate accounting and evidence boundaries, not a biological outcome.
