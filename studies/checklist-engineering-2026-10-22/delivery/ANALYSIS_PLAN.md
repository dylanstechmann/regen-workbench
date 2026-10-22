# Organ accumulation and functional delivery

Frozen source scope: 2026-10-22. The numerical analysis uses six printed R-squared annotations from Figure 2 of Moore et al. (2026), DOI [10.1038/s41467-025-68103-7](https://doi.org/10.1038/s41467-025-68103-7), plus its primary XML for endpoint definitions. No new acquisition follows the freeze. The source set does not contain individual measurements or an animal-to-image-field crosswalk.

The original SORT study, Cheng et al. (2020), DOI [10.1038/s41565-020-0669-6](https://doi.org/10.1038/s41565-020-0669-6), was screened as a candidate. Its public main text says plot data are available on request. Its cell-type reporter summaries are already a delivery precedent; they are not new linked measurements here. A bounded EuropePMC XML request failed with HTTP500. No retry or author contact followed. PNAS2021 appeared as context in the search but was neither acquired nor analyzed.

Prior audit: the main workbench's CPS1 clinical report, synthetic joint-coverage model and restoration goals are already present. This analysis adds a specific measurement-time counterexample and an executable comparison of source-reported correlations. It does not repeat the CPS1 clinical calculation or optimize a formulation.

1. Transcribe each printed annotation with its exact panel and intended organ. Keep the source figure bytes in an ignored cache. Do not digitize plotted observations.
2. Compare 1-hour and 24-hour qPCR associations with the 24-hour reporter within each formulation/organ. Compute the difference of reported R-squared values, not a new correlation or a statistical test.
3. Enclose that difference under an explicit nearest-0.01 rounding assumption. This is a display-precision envelope, not a biological uncertainty interval or confidence interval.
4. Keep qPCR animals, technical wells and reporter image fields separate. Neither position nor shared dose levels establishes individual matching.
5. Retain source-described late off-target accumulation, low-level off-target reporter observations and the distinction between intra-sample barcode proportions and inter-organ measures.
6. Leave intended-cell coverage, causal lesion repair, disease function, oral exposure and rejuvenation unavailable.

Reproduction is offline and uses only Python's standard library. It recomputes summaries from the curated annotations. An optional verification mode checks actual source bytes and retained fetch receipts without downloading anything.
