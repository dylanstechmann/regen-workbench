# Measured enamel/dentin material results and their interface limits

Reanalyzed 2026-10-19. This advances the goal of restoring lost tooth substance
and living attachment beyond the earlier synthetic volume budgets. Actual
published numerical values were retrieved and checked against their assay
descriptions. No new tooth treatment or materials experiment was performed.

**Decision:** use the measured thin-layer fracture/wear results as qualified
positive-control targets, with their unfavorable comparisons intact. They do
not yet qualify a bulk, through-depth host/repair junction for the integrated
PDL and finite-support-withdrawal test.

## Actual source intake

The [Hasan et al. primary article](https://www.nature.com/articles/s41467-025-64982-y)
links the [publisher's Source Data workbook](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-025-64982-y/MediaObjects/41467_2025_64982_MOESM4_ESM.xlsx).
The full **185,838,555-byte** file was downloaded, with SHA-256
`04dcc52eb9a64a9bd695136ebd71cbfa06ba4f3a77d562436df16002e4cd4dcf`.
The [Europe PMC primary XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12586552/fullTextXML)
was also retrieved: **210,765 bytes**, SHA-256
`a78f5fc40ef98119469a87c07583a0ac2882f634a5edcad67b9a8a5360570057`.
Both actual fetches have local `regen.record` provenance receipts; filenames
are retained in the [analysis plan](analysis_plan.json). An initial 20 MB
bounded probe was stopped and was not treated as a complete workbook.

The workbook has 57 worksheets. The reader examines only the relevant
worksheet XML, without loading embedded images or modifying the workbook.
Fig. 6 supplies the selected numerical values; Fig. 3/5 indentation blocks
are inventoried to qualify their observation hierarchy. The public derived
outputs contain attributed numerical extracts, not the source workbook,
article, figures or embedded source metadata.

## Measured property comparison

The following are **recomputed means ± sample SD**, using denominator
`n_numeric_values − 1`. A number's source position is not a specimen ID.
No p-values, confidence intervals, paired comparisons or equivalence tests
are calculated.

| Source assay | Native reference | Mineralized/remineralized group | Difference between means |
|---|---:|---:|---:|
| Fig. 6d, apparent indentation fracture toughness, MPa·m^0.5; 3 listed values/group | 1.2165 ± 0.1564 | 1.0856 ± 0.1297 | −10.76% versus native |
| Fig. 6f, enamel wear volume loss, mm³; 8 values/group | 2.9174 ± 1.1532 | 3.4991 ± 1.5474 | +19.94% loss |
| Fig. 6f, enamel wear height loss, µm; 8 values/group | 29.1300 ± 9.9612 | 30.5523 ± 9.5751 | +4.88% loss |
| Fig. 6g, dentin wear volume loss, mm³; conditional first 8-value block | 2.5009 ± 1.0115 | 1.6743 ± 0.7182 | −33.05% loss; source-identity caveat below |
| Fig. 6g, dentin wear height loss, µm; 8 values/group | 28.0355 ± 11.0641 | 16.8214 ± 7.2322 | −40.00% loss |

For fracture toughness, the acid-etched group is **0.7243 ± 0.0951** from
`U20:U22`. The remineralized mean is **49.89% above acid-etched**, while still
10.76% below the native mean. The descriptive interval between those group
means is 73.4% recovered; this is an arithmetic reference-gap fraction,
**not a percentage of the tooth regenerated** or an individual recovery rate.

Enamel wear means move in an unfavorable direction in this source block.
The paper reports no significant enamel wear difference; that does not
demonstrate native-equivalent performance, and the mean direction must not
disappear from candidate selection. Dentin wear has favorable mean directions
under this assay, with the volume-input ambiguity kept explicit.

The article's rounded wear SDs are closer to population-divisor SDs of these
listed values than to the sample SDs above; for example, native enamel height
has SD **9.3179** with divisor 8, versus **9.9612** with divisor 7. The source
methods say mean ± SD without specifying the denominator. Both conventions
are exported in the [summary table](derived/material_summary.tsv); no exact
reproduction of published uncertainty or significance is claimed.

## Unresolved trailing dentin-volume values

Fig. 6g's caption and methods state 8 samples/group. The workbook's dentin
height columns contain 8 numbers each, but its volume columns contain **9**.

| Cell | Extra stored value | First 8 mean | First 8 median |
|---|---:|---:|---:|
| `Fig. 6!AC13` | 2.51 | 2.500875 | 2.516 |
| `Fig. 6!AD13` | 1.67 | 1.674250 | 1.424 |

The extra cells have no formulas and use the same numeric style (`8`) as the
preceding measurements. Adjacent rows/cells supply no summary label; `AE13`
and `AF13`, the corresponding height positions, are empty with style `7`.
The values are close to some summary quantities, but that does **not identify
them as means**, nor does the lack of a label make them ninth specimens.

The conditional first 8 rows match the caption count and height-block length.
Including every numeric entry changes the volume means to **2.501889** and
**1.673778**. That is retained only as an **input-intake sensitivity**; it does
not resolve the entries' identities or authorize a sample size of 9. The
[audit](derived/intake_and_hierarchy_audit.json) retains exact stored text,
styles, formulas, neighboring cells and mean/median diagnostics. The
[observation table](derived/material_observations.tsv) preserves both extra
values with status `ambiguous_trailing_cell_not_a_specimen`.

## Hierarchy and transfer restrictions

The wear methods describe **32 extracted human molars**, split into 8 per
substrate/condition group. The selected blocks have no tooth/donor IDs or
cross-endpoint mapping. Native and treated columns are separate groups;
matching row numbers do not establish pairs. Volume and height are two
readouts on the source groups, not independent replications or proven joint
success in the same identified specimen. Independent human donor count is
unknown.

The fracture caption reports 3 samples/group; methods describe multiple
indentations per sample. The three numerical values are compatible with
sample-level outputs, but their within-sample aggregation and donor mapping
cannot be reconstructed from these cells. Apparent indentation-based fracture
toughness is not bulk fracture toughness or host/repair interfacial toughness.

The Fig. 3f modulus columns contain **98, 98 and 69 indentation values** for
native, acid-etched and remineralized groups, while the caption says **3
independent experiments per group**. Fig. 5f contains **93, 98 and 97** values
with the same experiment-count qualification. These larger point counts are
inventoried, **not counted as independent teeth/donors or used for narrow
confidence intervals**. No indentation-to-experiment crosswalk is supplied.

The wear comparison also lacks an acid-etched-only arm in these figures:
native tissue is compared with the full preparation-plus-mineralization
process. It cannot isolate a component's contribution. Total profilometric
wear loss is not repaired-layer volume; without a per-specimen layer-depth
map, it cannot be divided by the earlier 8 mm² illustrative footprint to
infer how much new material survived. Laboratory loading is not converted
into demonstrated years of human service.

These numerical blocks provide no independently paired depth/property map,
repeated-layer interface test, host/repair crack-path load curve, pulp,
gingival barrier, living PDL or post-support positional stability. Imaging
continuity and material-property means cannot fill those gaps.

## Next falsifiable material/interface comparison

This source intake makes the next gate more concrete:

1. Resolve the specimen/indentation hierarchy, the two trailing values and
   variance convention before attempting a specimen/donor-level uncertainty
   analysis. If identities remain unavailable, retain descriptive values
   rather than inventing a crosswalk.
2. For an independently qualified next material comparison, retain native,
   damaged/process and appropriate restorative references. Link each measured
   repair's actual depth and substrate to **its own** through-depth
   architecture, interface crack path, leakage and wear/fatigue outcomes.
   Freeze a greater-depth target and reference-derived margins after metrology
   qualification and a variance pilot, before ranking candidates.
3. Require the same specimen's host/repair junction to pass at the intended
   depth. Surface indentation or acceptable group-average wear alone cannot
   advance it. An unfavorable wear direction, delamination or a continued
   host crack remains a failure signal to resolve.
4. Only then transfer to the existing
   [full-crown/PDL integration contract](../../checklist-progress-2026-10-19/dental/integration_contract.json),
   including final crown contacts, recoverable bilateral attachment and
   intended position after finite support ends. This preserves the original
   natural-tooth, gum and ligament objective.

This is an endpoint and evidence specification. It supplies no material
recipe, new procedure, growth forecast, treatment duration or patient advice.

## Reproduction, checks and rights

```text
python studies/checklist-followup-2026-10-19/dental/analyze_hasan_material_data.py --fetch
python -m unittest discover -s tests -p test_checklist_hasan_material_data.py -v
```

`--fetch` downloads only missing pinned public inputs to ignored
`data/literature/checklist-followup-2026-10-19/`, records actual downloads with
`regen.record`, and rejects a size/hash mismatch. Omitting it reruns from
cached files. The reader does not evaluate workbook formulas or overwrite
source cells. Runtime: Python standard library; no new package is needed.

The [six contrasts](derived/material_contrasts.tsv), 13 summaries and 75 exact
source-position values retain negatives and unknowns. Ten targeted checks
pass, including source-cell/formula identity, SD conventions, count limits,
unlabeled-value handling, unfavorable directions and persisted receipt hashes.
Source hashes are byte hashes; study text/output hashes use canonical UTF-8/LF.
Docker workbench is stopped; no successful `regen doctor` is claimed.

Hasan et al. (2025), source DOI **10.1038/s41467-025-64982-y**, is
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Numerical values
are extracted with original cell positions and attribution; recalculated
summaries/contrasts and ambiguity flags are this study's additions. Source
files, figures and images are not redistributed. Their rights remain with
the source license; no unrelated mesh license or new repository-wide license
is assigned here.
