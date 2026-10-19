# Real specimen linkage in a restoration comparator

This batch retrieved and analyzed actual public numerical restoration data. It found no fully eligible source linking measured per-specimen repair depth and substrate to interface durability. The useful partial source is Theisen et al.'s 48-molar inlay dataset: 384 optical-margin records plus 48 terminal-fracture records. It provides a mechanical reference for the dental restoration program, with important source inconsistencies retained. It does not demonstrate biological tooth regeneration. [Primary article](https://doi.org/10.1007/s00784-022-04841-y), [deposited dataset, version 3](https://doi.org/10.5281/zenodo.7412385).

## What was acquired and qualified

Four primary-source candidates were screened. Eight actual files were retained with byte hashes and `regen.record` receipts. Acquisition stopped after the partial linked dataset qualified; no author was contacted. `candidate_intake.json` records units, physical replication, timing and why each candidate does or does not qualify. `source_manifest.json` records actual fetches separately from a source workbook response discarded at the 20 MB cap. The discarded workbook was not inspected.

Theisen's dataset contains resin-based composite, polymer-infiltrated ceramic network material (PICN) and lithium disilicate (LDS). Group G1 is PICN with prior composite aging, G2 is LDS with prior aging, G3 is PICN without prior aging, and G4 is LDS without prior aging. There are 12 source fracture-table teeth per group. Inlay interfaces were assessed after placement and after a common 1.2-million-cycle load block. Prior composite aging in G1/G2 was a separate earlier 240,000-cycle block; calling all groups identically aged would be wrong. The subsequent load-to-fracture assay is a later destructive endpoint. The root support is a silicone simulation of the periodontal ligament; it is not living PDL. [Article methods](https://doi.org/10.1007/s00784-022-04841-y).

The geometric depths are nominal preparation dimensions, not measured repair depths attached to specimen records. In particular, the nominal occlusal depth is at least 2.5 mm and proximal margins are positioned relative to the cementoenamel junction. Those locations do not become regenerated enamel thickness. The optical label `tooth` does not supply row-specific enamel/dentin segmentation. Marginal discontinuity length is not tracer leakage, and peak fracture load is not a fatigue event time. The earlier measurement bridge is reused to preserve these endpoints as unavailable rather than filling them from unrelated quantities.

## Findings that change interpretation

**Identity errors affect 11 possible teeth.** Fifty-six rows coded G3/T5 through G3/T12 instead declare specimen number 4. A further row, G4/T9/M/R2/InT, declares specimen 10. Both ends of each contradictory mapping are marked unresolved, including G3/T4 and G4/T10. This leaves 37 internally consistent teeth: G1 n=12, G2 n=12, G3 n=3 and G4 n=10. That is an internal consistency check, not external proof of identity. All 48 teeth remain in the registry and in uncertainty denominators. A separate sensitivity trusts row codes for all 48, without correcting the source identifiers. The two identity columns and original page/table-row positions remain inspectable in `source_extract.json` and the derived audit.

**The literal 6.76 N load materially changes G1.** The deposited fracture PDF prints 6.76 N for G1/T11; this was verified visually. Keeping all 12 source loads gives mean 1790.97 N and sample SD 726.74 N. Omitting that one record gives n=11, mean 1953.17 N and SD 483.40 N, reproducing the paper's rounded 1953.2 (483.4). This numerical match identifies an unresolved exclusion/value ambiguity. It does not justify deleting the tooth or inventing a replacement load. The released analysis retains 6.76 N and reports omission only as a diagnostic. G2/G3/G4 literal means reproduce the published rounded means.

**Fracture faces cannot be counted as independent teeth.** The source's Table 3 category counts reproduce counts across the four assessed tooth faces. For below-simulated-bone fractures, the face counts are 16, 19, 20 and 15, whereas the numbers of teeth with at least one such face are 7, 9, 11 and 8. Thus 70 face indicators correspond to 35/48 teeth with that terminal observation. Different categories can occur on the same tooth. No independent donor count can be recovered from the deposit. [Source fracture table](https://zenodo.org/records/7412385/files/1%20fracture%20analysis.pdf).

**Assessable-margin summaries conceal unobserved regions.** Five source rows leave the non-assessable-length field blank; four are in the final inlay interfaces. Blank fields remain unknown. Other rows explicitly record non-assessable margin lengths. The analysis reports both the source-style assessable-margin proportion and conservative whole-scanned-margin bounds. It does not call an observed 100% continuous assessable margin a fully gap-free interface. [Source marginal table](https://zenodo.org/records/7412385/files/3%20marginal%20analysis.pdf).

For the internally consistent subset, the mean paired changes in non-continuous assessable margin are:

| Group | Teeth | Composite-inlay change, percentage points | Tooth-inlay change, percentage points |
| --- | ---: | ---: | ---: |
| G1 | 12 | +0.8643 | +0.6813 |
| G2 | 12 | +0.2455 | +0.0720 |
| G3 | 3 | +0.1026 | +0.2177 |
| G4 | 10 | +0.1082 | +0.1151 |

These are descriptive changes within nominal interface regions. The baseline and final optical images do not supply pixel-level registration; this is not a map of local crack growth. The G3 subset is especially incomplete. No between-material effect, p value, equivalence claim, confidence interval or independent-donor inference is calculated. Printed lengths reconcile within 0.011 micrometers, a transcription/rounding tolerance rather than a biological acceptance threshold.

The difference made by unassessable regions is visible in G1 composite-inlay: assessable-margin change is +0.8643 points, but conservative whole-scanned-margin change spans -0.3065 to +7.8667 points when the blank field remains unknown. G1 tooth-inlay spans -6.6238 to +7.7386 points. The intervals describe missing-region identification uncertainty using printed values, not statistical confidence or measurement-error uncertainty. They need not be sharp and do not establish material improvement or deterioration.

The same-unit question is now executable: did a tooth have a recorded positive marginal discontinuity at either final inlay interface and later a below-simulated-bone fracture in the destructive assay? There are 19 internally identified joint positives; 9 additional root-fracture teeth have unresolved margin identities. Keeping all 48 teeth gives conservative bounds 19/48 to 28/48 (39.58%-58.33%). Trusting all row codes gives 26/48 (54.17%). This is an adverse co-occurrence in an extracted-tooth comparator, not a causal association, same-time endpoint, fatigue failure rate, human prognosis or regenerative success rate. The paper's experiment-wide statement of no debonding is retained; it does not resolve the later destructive fracture assay or furnish individual fatigue histories. [Article results](https://doi.org/10.1007/s00784-022-04841-y).

## How this advances the full restoration goal

The previous Hasan source exposed unlinked indentation/wear blocks. This source adds real tooth/region/state linkage and reveals how source identity, adverse observations and unobserved margins change a cross-endpoint interpretation. The code refuses to substitute nominal preparation geometry for measured repair depth, optical discontinuity for leakage, four faces for four independent teeth, or terminal overload cracks for cycling failures.

The next physically measurable hypothesis is: **at the intended replacement thickness on a specified host substrate, a candidate restored region retains its host-repair junction through loading without transferring damage into the remaining tooth.** The present source supplies reference adverse outcomes and the exact analysis that becomes possible when a real repaired region has measured depth and a valid specimen crosswalk. It cannot test the depth dependence itself. The closest screened thickness study measured adhesive film thickness and strength on the same fractured sticks, but the public source lacks numerical tooth-linked records and assesses immediate bond strength rather than durable regeneration. [Alam et al.](https://doi.org/10.3290/j.jad.b3240695).

Original enamel volume/thickness and dentin architecture remain targets alongside viable pulp, native PDL/cementum/socket attachment, youthful gum contour and durable original tooth position after finite support removal. No source screened here demonstrates those outcomes together. No brace/retainer assumption, unlimited external support or synthetic success record closes that gap. Prior Hasan adverse enamel wear and unresolved dentin entries remain unchanged.

## Reproduction and publication scope

From the repository root:

```text
python -B studies/checklist-translation-2026-10-19/dental/analyze_theisen_linked.py
python -B -m unittest discover -s tests -p test_checklist_translation_theisen.py -v
```

The default analysis and tests use the committed numeric extract and Python standard library. To verify all eight cached raw hashes, add `--verify-cache`. With bundled `pdfplumber` and the pinned cache available, `--extract-from-cache --verify-cache` repeats the read-only PDF table extraction before analysis. All seven PDF pages were rendered and visually inspected, including the low load, blank cells and contradictory specimen numbers. The extraction retains 384 original row codes and raw cell strings; no donor or specimen IDs were invented.

The source numeric tables are attributed to Theisen, Amato, Krastl, Attin, Blatz, Weiger and Eggmann, Zenodo dataset version 3 (2022), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Raw PDFs, primary XML files, DOCX, source renders and provenance receipts stay ignored. The 2026 adhesive paper/supplement and 2024 enamel analogue article carry CC BY-NC-ND 4.0 in the retrieved metadata; no figures, article text or adapted visual material from them are distributed. This report, calculations and eligibility judgments are original analysis. The source manifest contains every retained byte hash and actual fetch receipt; it does not claim a retained workbook where none exists.
