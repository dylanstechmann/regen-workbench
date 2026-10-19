# A real post-cycling dentin interface benchmark with incomplete depth linkage

This batch executed a new numerical comparison from **200 deposited OCT observations after 10,000 thermal cycles**. It provides established-restorative dentin-interface evidence at a nominal cavity depth, with a reproducible hierarchy audit. No screened source supplied the complete same-specimen actual-depth/interface/durability linkage. The bounded intake stopped at two new primary candidates. Earlier Shao, Hasan, HEA and Theisen analyses are unchanged. [Turkistani, Sonbul and Almarzouki, 2024](https://doi.org/10.1371/journal.pone.0315036), [original numerical workbook](https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0315036.s001&type=supplementary).

## What the source actually measures

The tested cavities were nominally 2 mm deep and 4 mm wide in extracted human coronal dentin, restored with an adhesive/composite system. There is no per-tooth measured thickness, missing-volume target or depth uncertainty. The OCT outcome is the percentage of selected cavity-floor width occupied by enhanced signal after the source's silver processing. It is an assay-defined interface signal, not a measured fluid flux, whole-interface gap volume or repaired-enamel thickness. The challenge is thermal cycling rather than mechanical chewing fatigue. Without a pre-aging measurement, a final defect value does not estimate deterioration during aging. [Primary specimen and OCT methods](https://doi.org/10.1371/journal.pone.0315036).

The paper reports five teeth per group and ten serial B-scans per tooth, averaged. The only source worksheet, `OCT data`, has four group columns and five separated ten-row blocks. Those blocks have no tooth or donor labels. Primary results below describe the deposited scan rows; the proposed nesting is explicitly conditional. No row count is used as an independent specimen count.

## The block grouping reproduces published variation

| Source group | Deposited scan rows | Mean signal percentage | SD of all scan rows | Conditional SD of five block means | Published SD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Etch-and-rinse (ER) | 50 | 34.34646 | 7.48750 | 5.59772 | 5.6 |
| ER with CHX | 50 | 33.50206 | 6.95771 | 4.68131 | 4.7 |
| Self-etch (SE) | 50 | 27.29802 | 8.63787 | 1.89858 | 1.9 |
| SE with CHX | 50 | 30.10082 | 7.45336 | 4.01663 | 4.0 |

Both the means and the SDs of block means reproduce all four Table 2 entries after rounding. This supports the five-block interpretation consistent with the paper's five-teeth/ten-scans description. It does not recover donor identity or prove that every source block is an independent tooth. The pooled scan SDs differ materially from the reported SDs: for SE, 8.63787 versus approximately 1.9. Treating all 50 scans as independent teeth would change the replication unit. We do not rerun a significance test using either grouping. The paper's reported p=0.068 does not establish equivalent interfaces. [Primary Table 2 and statistical methods](https://doi.org/10.1371/journal.pone.0315036).

Because every block has ten values, equal-block and pooled-row means agree exactly. That equality of means does not make their uncertainty or replication identical.

## Descriptive contrasts retain unfavorable directions

CHX-minus-no-CHX differences of the source means are **-0.84440 percentage points for ER** and **+2.80280 points for SE**. Higher OCT signal is the unfavorable direction in the source assay. The difference between those two descriptive contrasts is +3.64720 points. These compare unpaired groups; no matching of row positions across groups or individual response is inferred.

Deleting one source block independently from each group gives 25 possible contrasts per etching mode:

| Contrast | Original difference, percentage points | Source-block deletion range, percentage points |
| --- | ---: | ---: |
| ER/CHX minus ER | -0.84440 | [-4.34868, +1.87315] |
| SE/CHX minus SE | +2.80280 | [+0.87108, +4.88650] |

The ER direction changes within this deletion exercise; the SE direction remains positive. These are conditional record-sensitivity ranges, not confidence intervals, population effects, actual tooth-loss bounds or clinical efficacy ranges. No deletion is applied to the primary analysis.

There is also an unresolved repeated run: **A13:A19 exactly equals A46:A52**, seven consecutive ER values in different blocks. All are retained. This could reflect coincident measurements, source reuse or transcription, and the file alone cannot decide. It must not be silently deduplicated or treated as independent replication. The output lists both sets of source coordinates.

## Tensile failure data cannot be joined to OCT records

The source separately reports dentin-disc/beam tensile preparations, ten tested beams per group, means and failure categories. Its workbook contains only OCT data and no shared physical specimen IDs. The SE-with-CHX tensile summary is unfavorable: mean 13.1 MPa versus 22.5 MPa for SE, with 9/10 adhesive failures versus 6/10. These aggregate facts remain in `inputs.json` and `results.json`; they are not newly reconstructed raw observations, and they cannot be correlated with individual OCT values. The number of distinct donor teeth in the beam assay and its relation to the OCT teeth are not resolved here. Unreported losses and pretest failures are left unknown. [Primary Table 3 and tensile methods](https://doi.org/10.1371/journal.pone.0315036).

This separation prevents an apparent multi-endpoint comparison from becoming an invented same-tooth repair/durability result. The post-cycling OCT mean, a tensile mean from an unlinked assay and a nominal 2 mm preparation do not supply three measurements from one repaired specimen.

## Bounded intake and next decision

The second candidate was Baldion and Betancourt's 2021 primary data article and linked Myricetin repository. The primary source describes resin-dentin strength and failure observations after wet storage, but the workbook file listing/download did not resolve within the bounded public-page/API intake. The retrieved primary XML and repository page are retained; empty/error API responses are classified as access outcomes, not proof that the dataset has no files. No author contact, further retry or figure digitization followed. No numeric wet-storage comparison is invented from an unseen workbook. [Primary data article](https://doi.org/10.1016/j.dib.2021.106984), [repository version 3](https://doi.org/10.17632/p3g3zdv6zb.3).

The new source gives an inspectable post-challenge interface reference and an observation hierarchy that reproduces published summaries while retaining source ambiguity. The next useful physical comparison must add **actual regional depth and geometry**, pre/post-challenge interface measurements and adverse failure modes to the **same identified specimen**, with donor/tooth/section nesting retained. It must distinguish thermal cycling from mechanical loading and optical signal from material or barrier function. The present source cannot test whether increased replacement depth weakens the host junction.

Original natural enamel thickness/volume and dentin architecture, viable pulp and sensation, native cementum/PDL/socket attachment, youthful gums and stable original tooth position after finite support removal remain required. An established composite interface with nominal preparation dimensions does not complete any of those integrated restoration outcomes. The wider durable whole-body repair goal also remains in the continuity record.

## Reproduction and source scope

```text
python -B studies/checklist-integration-2026-10-19/materials/analyze_oct_interface.py --check-cache
python -B -m unittest discover -s tests -p test_checklist_integration_oct.py -v
```

Default analysis uses the tracked factual input without network access. The optional cache check validates six retained byte hashes and exact original-XLSX extraction of all 200 numerical cells; no image is read or digitized. The public numeric extract preserves source coordinates, blank-row segmentation and repeated values. `source_manifest.json` records actual receipts and distinguishes complete source data from repository metadata and access-error responses. `candidate_intake.json` records the two-candidate stopping point and missing linkage.

The numerical source is attributed to Alaa Turkistani, Helal M. Sonbul and Mai Almarzouki, PLOS ONE 19 (2024), e0315036, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The second repository identifies CC BY 4.0 and its primary data article identifies CC BY-NC-ND 4.0; no article images, adapted figures or unreceived raw values are published. Raw HTML/XML/XLSX and actual provenance receipts stay ignored. This package contains factual numeric extracts and original analysis, with no clinical application or preparation instructions.
