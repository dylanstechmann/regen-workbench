# Enamel analogue source data qualify bulk mechanics, not tooth repair

The previously uninspected HEA workbook now yields real numerical comparisons of contact fatigue, crack resistance and surface roughness. It supports a **bulk material/architecture comparator** and a limited same-figure comparison of two host-enamel delamination trace peaks. It still does not link a measured repaired-tooth thickness to a host-interface durability outcome. In particular, the workbook's small Supplementary Fig.48 force/displacement example belongs to **SENB compliance corroboration, not enamel bonding**. Reclassifying it as an adhesive interface test would create evidence the source does not supply. [Primary article and methods](https://doi.org/10.1038/s41467-024-54576-5), [original source workbook](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-024-54576-5/MediaObjects/41467_2024_54576_MOESM4_ESM.xlsx).

## What was inspected

The complete workbook is 29,902,662 bytes and downloaded within the newly authorized 400 MiB/60-second bound. Its SHA256 is `242fcb42e123669a80c891f74036c979de7be78c1e78d7cac4d0eb31a0f717b8`. The previous 20 MB intake cap had prevented inspection; this is an actual new fetch, with a real receipt. The workbook has 53 worksheets. This package retains a small factual numerical extract from eight selected worksheet XML members, with source addresses and member hashes. No images, molecular depictions or adapted figures were extracted or published. The prior primary XML is reused with its original hash/receipt; no second XML-fetch event is invented.

The analyzed records are three contact-fatigue displacement traces (477 serial points), fourteen bulk R-curves (154 serial points), three roughness before/after summary pairs, separate published KIC/KJC summaries, and two host-delamination traces (491 serial points). The source addresses are `Fig.4c!B4:F162`, `Fig.5e!B4:H5`, `Fig.6b!C3:N13`, `Supplementary Fig.43c/f!E3:O13`, `Supplementary Fig.41!E4:P4`, and `Supplementary Fig.8!C3:D300/E3:F195`. Addresses identify source records; they do not identify physical specimens or donors.

## Actual bulk crack-resistance comparison

The main Fig.6b curves are source-processed resistance values versus crack extension, expressed in MPa sqrt(m) and millimeters. Two listed curves exist per material, although the paper describes at least three tests. There is no per-curve geometry/donor crosswalk. We do not convert the two displayed curves into all experimental specimens or manufacture a new group SD from their serial points.

The exploratory, source-inspected comparison uses the intersection of all six curves' observed supports: **0-0.0784 mm crack extension**. Every result below lies inside every included curve. Piecewise-linear interpolation aligns the upper endpoint; trapezoids use the full clipped curve to compute mean reported K over that interval. That mean is a mathematical curve summary, not fracture energy. The endpoint is not a biological acceptance threshold.

| Material | Listed curves | K at 78.4 micrometers, trace mean [range], MPa sqrt(m) | Mean K across the common interval, averaged over traces |
| --- | ---: | ---: | ---: |
| HEA | 2 | 14.1338 [14.0013, 14.2664] | 9.6069 |
| Natural enamel | 2 | 5.5449 [5.4450, 5.6448] | 4.0827 |
| Reference enamel analogue (EA) | 2 | 7.7115 [6.9472, 8.4757] | 5.4869 |

The individual original final crack extensions differ: approximately 0.193-0.198 mm for HEA, 0.0784-0.0859 mm for enamel, and 0.1307-0.1339 mm for EA. Comparing those terminal resistances as if measured at the same crack extension would confound the comparison. Both the original endpoints and the aligned results remain in `results.json`.

The separate source summary reports HEA KIC 3.79 (SD 0.55) and KJC 19.8 (SD 2.9) MPa sqrt(m). Those are retained as published summaries; the two displayed curves are not forced to reproduce them. The deposited R-curves are processed source results, and this analysis does not independently validate compliance calibration, crack-length estimation, specimen validity or the underlying mechanics model. [Primary fracture-resistance results and Fig.6](https://doi.org/10.1038/s41467-024-54576-5).

The source-labeled LD/TD curves are a separate context. Their eight-curve common observed interval ends at **0.04577 mm**. At that point, the listed-trace means are HEA-LD 4.0971, enamel-LD 1.9734, HEA-TD 4.3786 and enamel-TD 4.0588 MPa sqrt(m). Individual ranges and full-interval summaries are retained in the output. Labels such as `HEA-LD-1` are source curve labels, not a donor identity or a pairing key between LD and TD. Without inspecting a source geometry crosswalk, they are not reassigned to new anatomical axes. The favorable material contrast is clearly context dependent; this does not isolate a causal architecture effect.

Test-piece dimensions are nominal. The primary caption gives analogue bending/SENB pieces roughly 15-20 by 1-2 by 0.5-1.2 mm, while natural enamel specimens and support spans are smaller. The methods provide nominal dimensions and notch ranges, not each plotted curve's actual thickness. Those dimensions, the nanowire/microbundle hierarchy, indentation contact depth and crack extension all describe different quantities. None is a measured amount of restored tooth enamel.

## Contact-fatigue traces retain residual limitations

For Fig.4c, the complete deposited vectors contain 159 displacement observations per material from cycle 100 through cycle 150,000. They are one listed trace each, not 159 independent specimens. The primary fatigue context uses contact loading on supported standalone samples; it does not load a regenerated host-repair junction. [Fig.4 and contact-fatigue methods](https://doi.org/10.1038/s41467-024-54576-5).

| Material | Recorded displacement at first/last observed cycles, mm | Net change over the observed window, mm | Cycle-weighted mean recorded displacement, mm |
| --- | ---: | ---: | ---: |
| HEA | 0.01830 / 0.17356 | +0.15526 | 0.07802 |
| Enamel | 0.02033 / 0.20008 | +0.17975 | 0.18447 |
| EA | 0.01886 / 0.30076 | +0.28190 | 0.16304 |

The final value and cycle-weighted mean are distinct summaries. Both are shown to avoid silently replacing an entire trajectory with one favorable endpoint. There is no fabricated zero-cycle point. Decreasing displacement steps are retained: 15 for HEA, 31 for enamel and 2 for EA. The vectors do not identify individual failure times or justify a survival curve, independent-replicate confidence interval, unloaded permanent-deformation estimate or clinical service-life forecast.

The source's morphology description reports additional cracks on the HEA surface after loading while the comparison samples showed breakage. That adverse HEA observation is retained even though its displacement trace compares favorably. Images are not extracted here, and no crack-count or specimen-linked crack-path table is reconstructed from that description. The primary text also equates roughly 4,000 chewing cycles per day with 150,000 per year; that arithmetic is internally inconsistent. This analysis keeps measured cycle counts and makes no calendar equivalence.

## Surface roughness worsens in every material summary

Fig.5e labels material and brushing cycles explicitly. The reported mean roughness increases after 15,000 cycles:

| Material | Before / after mean roughness, nm | Difference of means, nm | Relative change of means |
| --- | ---: | ---: | ---: |
| HEA | 3.35 / 4.13 | +0.78 | +23.28% |
| Enamel | 3.27 / 4.08 | +0.81 | +24.77% |
| EA | 3.41 / 12.14 | +8.73 | +256.01% |

The original SDs are retained separately. Before/after summary columns do not reveal paired specimens, individual changes, covariance or a precise summary-level independent sample count. The paper describes repeated tests and at least three samples in its mechanical characterization; the more-than-ten-test indentation hierarchy cannot simply be assigned to this roughness table. No paired test, equivalence inference or claim of unchanged HEA roughness follows. Mechanical-property sheets Fig.5b/c/d also lack explicit material labels within those numerical blocks; they are not silently relabeled or pooled into this comparison. [Toothbrush-wear results and Fig.5](https://doi.org/10.1038/s41467-024-54576-5).

## Interface evidence and the full restoration objective

The actual host-interface numerical evidence is **Supplementary Fig.8**, identified by the primary results as the HEA-versus-ZrO2 delamination comparison on enamel. Its worksheet supplies 298 serial HEA points and 193 ZrO2 points, with both ordinates labeled `stress` and both abscissae labeled `displacement`. Absolute units are omitted from these worksheet headers. The listed peak stress ordinates are 63.39339 and 18.50492, a dimensionless peak ratio of **3.4258**, conditional on the common stress scale used by the two curves in that source figure. The identical headers and primary same-assay comparison support that interpretation. The peak ratio is not a cohort mean, independently replicated advantage, validated absolute bond strength or biological attachment result. It does not establish the units, actual contact areas, per-specimen repaired depth, independent donor count or interface-fatigue outcomes.

Supplementary Fig.48 is a different assay record, explicitly referenced under SENB compliance/crack-length corroboration. Its force/displacement headers cannot supply a bond force, bond area or bond strength for Supplementary Fig.8. The software distinguishes the two records and does not normalize the calibration curve into an invented host-interface result. This correction matters: host-interface observations exist here, but are still unlinked to intended repair thickness or durability on the same physical specimen.

These results make the material comparison more useful: they quantify the curves at like crack extension, preserve an architecture-context difference, show whole observed fatigue trajectories and retain worsening roughness/cracks. They do not establish that a bulk crack-resistance advantage transfers to a repaired enamel/dentin boundary. The next falsifiable engineering question is whether the same intended-thickness host-attached region retains the favorable response through loading without new interface failure or damage in the retained tooth. The current source cannot test that question because geometry, host junction and durability outcomes are not linked on the same physical specimen.

The goal still includes restoration of original natural enamel thickness/volume and dentin architecture, living pulp, native PDL/cementum/socket attachment, youthful gums and original tooth position under load after finite support withdrawal. Standalone bulk samples, polymer support, cell compatibility and internal microbundle interfaces do not satisfy those endpoints. Earlier unfavorable Hasan enamel-wear values and Theisen source identity/load ambiguities remain unchanged.

## Reproduction and rights

```text
python -B studies/checklist-function-2026-10-19/dental/analyze_hea_mechanics.py
python -B studies/checklist-function-2026-10-19/dental/analyze_hea_mechanics.py --check-cache
python -B -m unittest discover -s tests -p test_checklist_function_hea.py -v
```

The default run uses the small tracked factual numeric input. `--check-cache` verifies the full workbook SHA, worksheet names/relationships, eight selected XML hashes and exact extraction equality; it reads no images. `--extract-source --check-cache` regenerates the small input from that pinned source. The script rejects extrapolation, unordered or duplicate x coordinates, nonfinite values, incomplete traces and duplicate trace labels.

The source is attributed to Lu Junfeng, Deng Jingjing, Wei Yan, Yang Xiuyi, Zhao Hewei, Zhao Qihan, Liu Shaojia, Li Fengshi, Li Yangbei, Deng Xuliang, Jiang Lei, Guo Lin, *Hierarchically mimicking outer tooth enamel for restorative mechanical compatibility*, Nature Communications (2024), DOI 10.1038/s41467-024-54576-5. Retrieved article metadata identifies [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/). This package contains factual numerical observations, source-cell locations and original calculations/prose; it does not redistribute the workbook, article text, illustrations or adapted figures. Raw source bytes and the genuine receipt remain ignored. `source_manifest.json` distinguishes the new workbook fetch from reuse of the earlier primary XML and records the publication scope.
