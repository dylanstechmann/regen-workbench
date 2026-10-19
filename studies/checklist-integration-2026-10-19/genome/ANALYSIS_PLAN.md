# Clinical correction and functional evidence transfer

Frozen source set: one successful original-article PDF acquisition, DOI [10.1056/NEJMoa2504747](https://doi.org/10.1056/NEJMoa2504747), with clinical pages 2237 and 2239–2241 selectively inspected. Figure 3 and page 2241 were visually checked. The clinical supplement was attempted but unavailable; no additional candidate is pursued. No figure is reproduced or digitized. The editing-site workbook, clinical administration protocol and supplementary design sections remain unread.

The existing `base-editing-evidence` clinical card and prior workbench integration used the abstract and metadata. This batch adds numerical clinical-summary contrasts and a time/unit audit. It does not add independent clinical observations.

## Before calculation

1. Extract only reported ammonia and urinary-orotic-acid median/IQR summaries, their different group labels, weight/time endpoints, relative medication change and concurrent-care context. Preserve missing measurement counts and raw series as unknown.
2. Retain one independent patient, regardless of the number of laboratory measurements, plots, endpoints or time windows. Do not convert IQRs into confidence intervals or infer a statistical test from summaries.
3. Compute differences and ratios **of reported medians**, IQR widths, and the weight contrast. These are neither patient-paired measurement ratios nor causal treatment effects.
4. Reconstruct elapsed days and distinguish elapsed subtraction from inclusive calendar-day counting. Preserve source-rounded week descriptions; do not force them to equal exact timestamp differences.
5. Do not compute protein-intake percentages from the figure, clinical AUC, hyperammonemia event rates, gene-editing fractions, corrected-cell fractions or an aging coverage threshold.
6. Compare the clinical inference unit against the earlier same-tissue joint-endpoint framework. A clinical response without a patient biopsy cannot supply the missing molecular denominator or an overlap with viable, correctly edited hepatocytes.

## Decision enabled

Use this as an example of a known inherited lesion with downstream organ-function signals and continued supportive care. For a future correction/restoration claim, request explicitly defined functional endpoints, care/illness histories, independent participants and follow-up, plus separately measured molecular and safety endpoints in a shared sampling frame. Do not require risky patient sampling merely to fill a data schema. Natural-aging restoration would additionally require a causal target and appropriate aged-tissue function evidence; neither follows from this case.

## Reproduction

From the repository root, run `python studies/checklist-integration-2026-10-19/genome/analyze_genome_clinical.py --check` and `python -m unittest discover -s studies/checklist-integration-2026-10-19/genome -p test_genome_clinical_transfer.py -v`. Add `--verify-sources` to the first command only when the ignored local cache is available. The script hashes the canonical UTF-8/LF input text and never downloads sources.
