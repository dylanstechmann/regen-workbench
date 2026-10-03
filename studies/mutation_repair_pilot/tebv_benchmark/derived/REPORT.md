# HGPS LMNA correction: TEBV vasodilation benchmark

> This is a descriptive reanalysis of one published in-vitro HGPS donor model. It is not evidence of ordinary human aging reversal, treatment efficacy, or a clinical intervention.

## Question and falsifier

Does the initial edited-cell fraction predict a monotone increase in acetylcholine-evoked vasodilation in HGPS tissue-engineered blood vessels? Any adjacent dose pair with a lower mean at the higher edited fraction falsifies the descriptive monotone pattern.

## Reproduced values

Values are reported percent diameter change from after phenylephrine to after acetylcholine. Summary statistics are recomputed from the public workbook; author-reported ANOVA values below are transcribed from the archive's `ANOVA_Fig8.pdf` and were not refit.

| Group | Week | n in workbook | Mean | SD |
|---|---:|---:|---:|---:|
| 25:75 | 3 | 4 | 1.2390 | 0.8107 |
| 50:50 | 3 | 3 | 2.2323 | 0.1248 |
| 75:25 | 3 | 4 | 2.0806 | 0.5581 |
| HGPS | 3 | 4 | 1.2264 | 0.4708 |
| Healthy | 3 | 4 | 3.3940 | 1.6701 |
| 25:75 | 5 | 4 | 2.5321 | 1.1300 |
| 50:50 | 5 | 4 | 1.5469 | 0.6270 |
| 75:25 | 5 | 4 | 1.4184 | 0.8874 |
| HGPS | 5 | 4 | 0.0672 | 0.5270 |

The published Figure 8 caption says N=4 TEBVs per vasoactivity group, while the public workbook and its ANOVA summary contain 35 values: the 50:50 group at week 3 has three values. The workbook has no TEBV identifiers, so the missing value and longitudinal pairing cannot be resolved here.

## Benchmark result

The edited-fraction means are not monotone at either week. At week 3, the 50:50 mean is above the 75:25 mean; at week 5, the 25:75 mean is highest. The author's ordinary two-way ANOVA reports a ratio effect (p=0.0044), no overall week effect (p=0.4139), and a week-5 25% edited versus HGPS comparison (adjusted p=0.0156). These source-level results do not support a simple monotone dose rule.

## Donor and calibration gates

Donor-held-out validation is **not testable**: the HGPS cell lines used in the study come from one person (donor 003), and the Figure 8 workbook has no donor or vessel ID on individual values. The paper itself identifies testing the correction and mixing experiment in the second HGPS donor (HGADFN167) as future work. The public data therefore support within-study description, not donor-general model performance.

The paper reports a perfusion setting of 0.5 mL/min per TEBV and nominal wall shear of 6.8 dyn/cm². No original flow trace, pump calibration record, or uncertainty budget is included in the Figure 8 archive. The related `perfusion-calibration-lab` repository is linked as a candidate analysis tool only; it was not applied to this experiment.

## Reproduction

```powershell
docker compose exec workbench python /lab/workbench/studies/mutation_repair_pilot/tebv_benchmark/analyze.py
docker compose exec workbench python /lab/workbench/tools/validate_experiment_manifest.py /lab/workbench/studies/mutation_repair_pilot/tebv_benchmark/experiment.json
```

Source: Abutaleb et al., APL Bioengineering (2025), doi:10.1063/5.0244026; Duke Research Data Repository, doi:10.7924/r4pg1xv1b (CC0).
