# What a clinical correction case contributes to restoration research

The CPS1 report adds a human example of an intervention targeting a known inherited lesion, followed by reported clinical and biochemical changes. It supplies no measured patient liver editing fraction and no ordinary-aging coverage threshold. The new work here is a reproducible comparison of published clinical summaries and their observation windows; the earlier `base-editing-evidence` card and workbench integration had only abstract-level clinical information.

## Numerical evidence and its unit

All rows below describe **one infant**, with repeated laboratory observations whose numerical group counts were not supplied in the inspected text. Values are reported medians [interquartile range], not means, confidence intervals, or observations from independent patients. Clinical extraction: original article page 2241; group labels visually checked in Figure 3 on page 2240. [Original primary report](https://doi.org/10.1056/NEJMoa2504747).

| Endpoint | Baseline | First follow-up group | Second follow-up group |
|---|---:|---:|---:|
| Ammonia, µmol/L | 23 [14–48] | 9 [9–19] | 13 [9–28] |
| Urinary orotic acid, mmol/mol creatinine | 1.7 [1.6–1.8] | 2.4 [2.0–3.0] | 2.6 [2.0–3.6] |

The ammonia baseline is labelled age three months until the first intervention; the later groups are between interventions and after the second. The orotic-acid groups are baseline and **steady state** after each intervention, without exact numerical boundaries. These labels do not establish paired specimens, identical windows, endpoint covariance, or simultaneous joint attainment. The ammonia baseline already reflects ongoing intensive care; it is not an untreated disease state.

The first and second ammonia summaries differ from baseline by −14 and −10 µmol/L: ratios of reported medians 0.3913 and 0.5652 (descriptive relative differences −60.87% and −43.48%). Orotic-acid summary differences are +0.7 and +0.9 mmol/mol creatinine, with ratios 1.4118 and 1.5294. A ratio of group medians is not a median of paired measurement ratios. The source associates the orotic-acid change with urea-cycle correction; neither endpoint is a directly measured fraction of corrected cells.

## Timing, care, and safety limit the transfer

The first intervention was on day of life 208; the reported 22-day interval places the second on day 230. Follow-up ended on day 256: 48 elapsed days from the first intervention, 49 inclusively counted calendar days, and 26 elapsed days from the second. The original rounded descriptions of seven weeks overall and four weeks after the second are retained. The reported later medication reduction occurred about two weeks after the second intervention, leaving nominally 12 days to this report's endpoint. The week-based conversion does not identify an exact clinical day; these calculations are temporal arithmetic, not newly observed dates.

The initial nitrogen-scavenger wean was reversed when glutamine rose. Later the report describes a requirement of approximately half the starting amount. Protein plans changed; premature birth complicates chronological-age intake targets. One post-intervention illness involved fluids and a protein-free day; later illnesses occurred during full-protein feeding. Citrulline, nitrogen-scavenger treatment and immunosuppression continued. Earlier spontaneous biochemical improvement during infancy is another reason a simple before/after comparison cannot isolate treatment effects. No protein-intake percentage or event rate is reconstructed.

Weight changed from 7.14 to 8.17 kg over days 207–256: +1.03 kg, or +14.43%. The reported percentile change, ninth to 26th, is **17 percentile points**, a different quantity. Infant growth is not evidence of rejuvenation, reversal of prior neurologic damage, or an editing-attributable growth effect.

The original short report records no serious adverse events, while describing transient liver-enzyme elevations and a resolved coughing episode; neurologic status was reported stable. These observations neither estimate long-term adverse-event risk nor establish long-term developmental recovery. Timing alone does not assign the enzyme changes to a single cause.

## What to do next with this evidence

1. **Keep function separate from molecular coverage.** Liver biopsy was deferred because of patient risk. Patient allele correction, corrected-hepatocyte fraction, and their overlap with viable/functioning tissue therefore remain unknown. Preclinical measurements cannot replace these patient denominators; no risky sampling is proposed here.
2. **Preserve a clinical evidence contract.** A future clinical comparison needs timestamped functional observations, specimen counts, illness histories, feeding/care changes and longer follow-up. More repeated samples improve a time course but do not create more independent participants. No causal effect, p-value, confidence interval, AUC or covariation is calculated from these summaries.
3. **Require a separate aging case.** This inherited enzyme defect offers a causal lesion and a measurable organ-function pathway. Ordinary aging involves different candidate lesions, tissues and failure mechanisms. An aging-restoration project needs its own causal-target evidence and durable native-function outcomes; this case supplies no transferable edited-cell percentage, rejuvenation threshold or universal body-repair result.

## Access and reproducibility

One original PDF was acquired from the [author institution](https://www.med.upenn.edu/cstr/assets/user-content/Fall%202025/Patient-Specific%20In%20Vivo%20Gene%20Editing%20to%20Treat%20a%20Rare%20Genetic%20Disease.pdf), with a genuine fetch receipt and hash in `source_manifest.json`. Clinical supplementary access failed after bounded attempts; this does not establish that underlying numerical series do not exist. The clinical protocol and editing-site workbook were left unread. Copyrighted PDF/page renders remain in the ignored local cache; no source figure, adapted figure or digitized pseudo-series is published.

`analyze_genome_clinical.py --check --verify-sources` reproduces six summary groups, four descriptive contrasts, timeline arithmetic and the weight comparison. Nine targeted tests check those calculations, missing denominators, numerical validation, output consistency and canonical UTF-8/LF hashing. The study is an evidence-analysis artifact; it contains no clinical regimen or editing design.
