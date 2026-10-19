# SS-31: what would actually improve useful exposure per material cost?

The next decision should be driven by **intact native-parent exposure at the relevant cells, function at that exposure, and released-parent process yield**. The sources below do not establish an oral SS-31 bioavailability, a functionally equivalent longer-lasting covalent analogue, or a lower commercial manufacturing cost. They do support a useful conditional clearance calculation, an oral material-burden bound, and a reproducible check of cellular endpoint tradeoffs.

## What was already present, and what this adds

| Question | Already in the pinned atlas | New qualification in this package |
|---|---|---|
| Plasma stability versus human residence | Long fitted human-plasma incubation half-life versus much shorter IV plasma half-life | Route/statistic-separated IV residence and SC terminal half-life inputs; no quotient used to assign mechanism |
| Urinary elimination | Label says parent and metabolites are recovered in urine | FDA review separates approximately 10% parent, 34% M1 and 57% M2; only the parent fraction is used as a conditional clearance anchor |
| Cellular function of existing comparators | SPN4 and SPN10 function differs by assay; biotinylated localization does not measure native uptake | Actual Figure 6 workbook acquired; all 21 series means/SD reproduced at the correct source unit; exact repeated cross-endpoint entries flagged |
| Process alternative | EP3160984B1's purification/process claims | Final-salt/precursor mass does not establish molar yield; separate EP3774844B1 intermediate distinguishes area purity from weight assay; cost-identification gaps made explicit |
| Oral advantage | Earlier model had illustrative F/access/activity multipliers | Bound based on the label's approximate SC F, plus a strict missing/invalid-data gate; no oral F or analogue activity assigned |

Continuity source: [prior SS-31 audit](https://github.com/dylanstechmann/geroscience-compound-atlas/blob/af7b57c2cfad64683f82044199cca812a01b9a03/studies/ss31-analog-audit-2026-10-09/README.md), [peptide-transfer audit](https://github.com/dylanstechmann/geroscience-compound-atlas/blob/af7b57c2cfad64683f82044199cca812a01b9a03/studies/peptide-delivery-transfer-2026-10-09/README.md), [earlier illustrative model](https://github.com/dylanstechmann/geroscience-compound-atlas/blob/af7b57c2cfad64683f82044199cca812a01b9a03/studies/oral-targeting-feasibility-2026-10-09/analysis_models.py). This is a quantitative qualification of that backlog, not discovery of those comparators.

## Parent exposure is different from urine recovery or plasma stability

The FDA review's human IV cohorts report parent terminal half-life means of **3.23–3.93 h** and mean residence times of **2.40–2.67 h** (five source cohorts, six subjects each; arithmetic means/SD). Separate single-SC cohorts report parent terminal half-life geometric means **1.76–2.79 h**, with CVs and source cohort sizes five or six. These ranges describe reported cohort summaries, not confidence intervals. The review explicitly cautions against generally extrapolating IV parameters to SC. [FDA integrated review, printed pp187–190 / PDF pp256–259](https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/215244Orig1s000IntegratedR.pdf)

The human-plasma **26.1–30.8 h** fitted half-lives come from an in-vitro incubation observed through six hours. That assay does not measure whole-body elimination, tissue residence, or the fraction of human clearance attributable to plasma proteolysis. M1/M2 are separate C-terminal degradation products; a longer-lived metabolite signal is not longer-lived parent or demonstrated useful activity. [FDA integrated review, printed pp181–182 and190](https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/215244Orig1s000IntegratedR.pdf)

The renal-function IV study collected urine through 48 h. Its normal-renal cohort had six subjects; Figure 35 and the review summary give approximately **10% unchanged parent, 34% M1, 57% M2**. These rounded values sum to 101%; they are preserved without renormalization. Thus near-complete urinary recovery of drug-related material does **not** mean near-complete unchanged-parent renal clearance. Metabolites may be formed in renal or other tissues; their urinary exit does not locate their formation. [FDA integrated review, printed pp200–203 / PDF pp269–272](https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/215244Orig1s000IntegratedR.pdf)

## A conditional calculation, not a universal analogue ceiling

Let `fe≈0.10` be that rounded IV parent recovery anchor and let hypothetical `q` be the fraction of **all other parent disappearance** remaining. Under adequate unchanged-parent collection, linear time-invariant parent PK and fixed unchanged-parent renal clearance:

`relative parent clearance = fe + (1 − fe) × q`

At fixed parent input and F, systemic parent AUC scales inversely with this expression. The stated counterfactual also holds distribution volume fixed; this package makes no terminal half-life prediction. Other disappearance is not identified as plasma proteolysis or as nonrenal clearance.

| Hypothetical other disappearance remaining, q | Relative clearance | Conditional AUC gain | Oral F at equal parent material to the approximate SC reference |
|---:|---:|---:|---:|
| 1 | 1 | 1 | 0.92 |
| 0.5 | 0.55 | 1.82 | 0.506 |
| 0 | 0.10 | 10 | 0.092 |

The last row is an algebraic sensitivity result. It does not demonstrate that a modification can remove those routes. Rounded recovery, limited collection and the small cohort leave uncertainty; the 0.05 and 0.20 recovery values in `results.json` are explicitly hypothetical sensitivity anchors, not a confidence interval. A modification can also alter renal clearance, distribution, absorption, identity and activity. **There is no established universal ten-fold ceiling for an analogue.** Improving only plasma proteolysis has an unidentified effect because its contribution to parent disappearance is unknown.

For **unchanged parent with unchanged clearance**, matching systemic parent AUC gives an independent material identity: `oral parent mass / SC parent mass = 0.92 / oral F`, using the label's approximate absolute SC bioavailability. With only `0 < F <= 1`, the lower bound is **0.92**, maximum possible parent-material reduction is **8%**, and no uniform finite upper bound exists as F approaches zero. This assigns no oral F to SS-31. AUC matching does not match intracellular access, peak/trough behavior, effect duration or function; neither protein unbound fraction nor biotinylated imaging supplies those missing quantities. [FDA label, section 12.3](https://www.accessdata.fda.gov/drugsatfda_docs/label/2025/215244s000lbl.pdf)

The table's oral-F thresholds combine independent source contexts and hypothetical clearance changes; they are decision thresholds, not observed outcomes or a route recommendation. Finished-material cost, formulation overhead and relative useful cellular effect remain unidentified. The executable gate rejects missing, Boolean, nonnumeric, nonfinite or nonpositive required values, and F/access outside (0,1]. No numerical useful-cost rank is produced.

## Cellular function: real observations, unresolved exposure and dependence

The [primary Figure 6 workbook](https://cdn.elifesciences.org/articles/75531/elife-75531-fig6-data1-v1.xlsx) and [article](https://doi.org/10.7554/eLife.75531) allow descriptive reconstruction of previously known assay differences. TMRM has **three independent experiment-level summaries**; four to six image fields were averaged within each experiment. The workbook does not make those fields independent replicates. HK-2 viability has six source samples under unstressed conditions and five under serum withdrawal; ATP has five. The caption calls them independent samples, but donor, batch and cross-assay sample identity are unavailable here.

| Existing compound | ARPE-19 TMRM, % of serum-supplemented control, mean ± SD; n=3 | Stressed HK-2 viability, relative to no-peptide stressed control; n=5 | Stressed HK-2 ATP, same type of within-condition normalization; n=5 |
|---|---:|---:|---:|
| SS-31 | 68.696 ±4.757 | 1.344 ±0.162 | 1.276 ±0.101 |
| SPN4 | 64.851 ±1.736 | 1.553 ±0.063 | 1.395 ±0.189 |
| SPN10 | 78.782 ±6.142 | 1.799 ±0.162 | 1.799 ±0.162 |

SPN4's descriptive direction relative to SS-31 reverses across TMRM and stressed viability. This is not a single potency ranking. All **five SPN10 normalized entries are exactly identical across stressed-viability and ATP worksheets**; SS-31 and SS-20 each share two same-position entries and SPN4 shares three. The underlying reason and cross-assay independence cannot be resolved from this workbook. Do not count these as established independent endpoint replication or assert a cause for the repeated values. No new significance tests are added.

Native intact intracellular concentrations were not measured in these data, and Figure 6A localization uses **N-biotinylated** SS-31/SPN10. Function at a nominal common extracellular condition cannot establish unchanged intracellular exposure, oral absorption, retained activity of a different analogue, or rejuvenation in humans. The workbook's normalized controls lack raw denominators, so these ratios do not establish absolute restoration to a youthful or healthy reference.

## Process accounting: what can and cannot be priced

The [EP3160984B1 process patent](https://patents.google.com/patent/EP3160984B1/en) claims final purity above 98.5% and avoidance of final HPLC/freeze-drying. Its general purity paragraph does not identify a weight-assay method, and these are applicant assertions rather than a verified released commercial lot. Example 6 reports 0.7 g final triacetate from 2.0 g protected precursor: **0.35 is only an isolated mass ratio**, not 35% molar yield. Removed protecting groups and changed salt/content prevent that interpretation; other examples do not establish a single end-to-end released-parent batch balance. No preparation instructions are reproduced here.

The separately located [EP3774844B1 patent, Example 2](https://patents.google.com/patent/EP3774844B1/en) reports **99.4 area% HPLC purity versus 98.7% calculated weight assay** for crystalline **Compound II intermediate**, corrected for residual material. Those are different quantities. For that intermediate alone, fixed assayed content requires `0.994/0.987 = 1.00709` times the bulk that an area%-as-content assumption would predict (about 0.71% more). This is neither a final SS-31 assay nor a cost saving. Intermediate gram/kg charge tables are process inputs, not demonstrated released-parent production output.

Actual cost per released assayed-parent mass requires total process, QC/release and rejected-batch cost divided by released assayed-parent mass. Both are unidentified. A process-change claim needs matched batch identity, stage recovery, final content/counterion/water correction, impurity/release specifications, rejected lots and cost inputs. No vendor-price proxy, overall yield, commercial scale claim or absolute cost is supplied.

## Decisions this changes

1. **Prioritize native-parent target exposure and process accounting before new covalent variants.** Existing plasma stability alone does not identify the loss mechanism worth blocking. Obtain parent-specific, route-resolved PK/urinary data and analytically resolved intracellular parent exposure paired with function; distinguish parent from M1/M2 and imaging tags.
2. **Make an oral-route proposal meet an exposure/material threshold.** Require measured intact oral parent F and relative clearance, with matched cellular access/function and formulation/material costs. Approximate SC F already leaves only 8% theoretical material saving from absorption alone at unchanged clearance; an oral convenience benefit is a different outcome.
3. **Evaluate process changes on released-parent output.** Request end-to-end assayed yield and cost inputs rather than converting HPLC area purity or precursor mass to parent quantity. The new intermediate patent provides a real quality-accounting distinction, not sufficient evidence of cheaper SS-31.
4. **Keep covalent alterations gated.** No named existing comparator earns an oral/duration/cost recommendation from these sources. Demonstrate intact route exposure, renal/distribution changes and function at matched native intracellular exposure before assigning benefit. Preserve the workbook's unresolved cross-endpoint dependence in subsequent comparisons.

## Reproduction and limits

`inputs.json` contains route/species/matrix/statistic/source locations and the derived workbook observations. `source_manifest.json` pins seven actual downloaded files, SHA-256 values and real `regen.record` receipts. The direct eLife HTML fetch returned a client challenge and is excluded from scientific extraction; complete primary XML and the genuine XLSX supplied the article/data instead. Raw downloads and receipts are ignored locally, not redistributed as tracked source artifacts. The PDF image tables were visually checked before transcription. This is a source audit, not an independent clinical or manufacturing replication.

Run `python studies/checklist-mechanisms-2026-10-19/ss31/analyze_ss31.py --check-cache` to regenerate `results.json` and `cell_endpoint_summary.csv`. Seven source hashes match; all 21 means/SD reproduce. Run `python -m unittest discover -s studies/checklist-mechanisms-2026-10-19/ss31 -p test_ss31_bounds.py -v`: **9 targeted tests pass**. Input hashing normalizes line endings to LF. The workbench Docker service is not running; no successful `regen doctor` or biological validation is claimed. Root performs integration and the full repository suite.
