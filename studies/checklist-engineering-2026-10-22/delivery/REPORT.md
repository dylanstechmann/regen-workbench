# Sampling time changes the evidence for functional organ delivery

**The new calculation compares six printed fit summaries from a mouse delivery study.** The reported association with a fixed 24-hour Cre/tdTom reporter is higher for 1-hour qPCR than for 24-hour qPCR in each of three source formulation/organ series. More importantly for repair research, the source describes a liver-directed formulation whose late qPCR signal becomes predominantly splenic while its reporter activity remains mainly hepatic. A single late accumulation measurement can therefore give a misleading impression of functional organ targeting in this setting. [Moore et al., 2026](https://doi.org/10.1038/s41467-025-68103-7), Figure2 and its results discussion.

This package advances the delivery part of the restoration checklist. It adds an executable source-summary comparison and a specific measurement counterexample. It has no newly fitted biological data, therapeutic correction result or functional repair result. The earlier CPS1 clinical and synthetic joint-coverage analyses remain separate.

## Numerical result

The figure's colored fit series are blue/liver, red/lung and green/spleen across the source dose-response conditions. The organ labels identify the source series and intended target. They do not establish intended-cell identity. The underlying fit-input table, exact number of fitted observations and field-to-animal crosswalk are unavailable in the acquired main text/figure. Scatterplot marks were not digitized or promoted to individual observations.

The retained XML caption labels panels l/m as Liver SORT, while the figure's third block and surrounding discussion identify Spleen SORT. The selected n/o fit annotations follow the figure labels and discussion; the conflicting l/m caption wording is not silently treated as a verified mapping.

| Source formulation and fit-series organ | R²: qPCR1h versus reporter24h | R²: qPCR24h versus reporter24h | Difference: first association minus second | Display-rounding enclosure of difference |
| --- | ---: | ---: | ---: | --- |
| Liver SORT, liver, panels2d/e | 0.97 | 0.93 | +0.04 | +0.03 to +0.05 |
| Lung SORT, lung, panels2i/j | 0.92 | 0.87 | +0.05 | +0.04 to +0.06 |
| Spleen SORT, spleen, panels2n/o | 0.98 | 0.86 | +0.12 | +0.11 to +0.13 |

The enclosures assume nearest-0.01 rounding of each printed value. They account only for display precision. They are not confidence intervals, animal-level variability, uncertainty in the source regression, or evidence of a statistically significant difference. All three signs stay positive under this rounding assumption. Their sizes cannot rank formulations or establish a superior biological outcome.

The two columns share the reporter at 24 h. They are not two longitudinal measurements in which both qPCR and reporter are collected at 1 h and 24 h. An association across source dose-response conditions also does not establish a predictor's accuracy for new formulations, animals, cell populations or repair targets. No out-of-sample validation is performed.

## Measurement and linkage limits

The source labels the qPCR axis `qPCR Fold Change` and the reporter axis `tdTom area %`. Methods describe actin normalization. The barcode-method section separately describes log2 fold change versus actin normalized to an input pool. A complete Figure2 numeric transformation/calibration table was not supplied, so no conversion to absolute mRNA mass, percent injected dose, intact-cargo fraction or cell coverage is made.

Figure 2 reports 3 mice per qPCR condition and 3 technical wells per measurement. Reporter quantification reports 3 image fields. Technical wells and image fields are not extra independent animals. Common formulation, organ and time labels do not supply an animal-to-field crosswalk. Even the 24 h/24 h comparison is not treated here as paired individual measurements.

The reporter is generated after Cre-mediated recombination activates stable tdTom expression. Its 24 h area includes prior successful activity and reporter-production/detection history. It is not an instantaneous translation rate or a direct readout of remaining active cargo. Its denominator is a DAPI-defined image region, rather than a count of intended cells. The source's approximate proportionality assumption between area and positive-cell number does not provide a cell-count calibration for this analysis.

The manuscript also distinguishes within-sample NGS barcode proportions from inter-organ measurements. A barcode's share of the reads in one sample cannot directly measure which organ received the largest amount. The source uses a separate actin-normalized qPCR approach for organ comparisons. Multiple time-coded barcodes recovered within one animal remain dependent observations. This package calculates no Figure3 AUC, clearance rate or half-life.

## Negative evidence and the next engineering decision

The late liver-formulation qPCR/spleen preference is retained alongside the favorable correlations. The source also reports low-level off-target reporter activity for some conditions. Consequently, neither organ-selective terminology nor a high R² licenses a zero-off-target assumption. The experiment tests a reporter, rather than correction of a causal disease lesion or improved organ function.

The next useful evidence unit is a linked record containing animal/cohort identity, organ, intended-cell identity, an eligible-cell denominator, cargo assay molecular scope and normalization, collection time and activity history. That record must connect intracellular cargo activity to intended correction, survival/integration, disease-relevant function and adverse activity in unintended cells. [The measurement crosswalk](measurement_crosswalk.json) states which links are available here. Its current joint intended-cell repair coverage remains unavailable. This avoids promoting accumulation, reporter-positive area or allele fractions into whole-body restoration coverage.

## Reproduce and inspect

From the repository root:

```text
python studies/checklist-engineering-2026-10-22/delivery/analyze_delivery.py
python -m unittest discover -s studies/checklist-engineering-2026-10-22/delivery -p test_delivery_summary.py -v
```

The optional `--verify-sources` flag checks the two retained raw-source hashes and their actual download receipts offline. Public [inputs](inputs.json) and [results](results.json) reproduce the arithmetic without the ignored image/XML cache. The [source manifest](source_manifest.json) records exact bytes, rights, receipts, the failed original-SORT XML request and acquisition limits. No source microscopy image, RNA sequence, formulation recipe, administration instruction or raw sequencing reads are republished.

Moore et al. acknowledge commercial interests in ReCode Therapeutics, Signify Bio, Newlimit, Chroma Therapeutics, Quotient Therapeutics and Jumble Therapeutics. These are source-declared interests, not evidence that the measurements are invalid. The paper is CC BY4.0. The analysis and small panel-labeled numerical transcription here are new; original source images remain in the ignored audit cache.
