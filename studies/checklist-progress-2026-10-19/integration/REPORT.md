# One construct must meet its required endpoints together

AI-assisted research engineering, 2026-10-19. This connects the stem-cell,
organoid and genome-repair goals to the full dental and whole-body repair
checklist. It adds a joint-endpoint audit; it does not claim a repaired organ.

## Existing work and the added question

The public [base-editing-evidence project](https://github.com/dylanstechmann/base-editing-evidence)
already distinguishes reached cells, edited products and target-population
coverage. Its local README was inspected read-only; no code or evidence from
that project was copied into this repository or changed. The workbench's
[PDL endpoint contract](../../organoid/periodontal-ligament-interface/endpoint_contract.tsv)
already requires both fiber insertions, viable identity, no mineral bridge,
mechanics and durability. We extend the integration question: **are the
required outcomes present in the same target tissue, at the same time?**

Separate marginal success percentages cannot establish their overlap. An
editing allele fraction, perfused area and lineage-positive cell fraction
also cannot be multiplied as though they shared a denominator.

## Executed audit

In an explicitly synthetic set of 100 equal-volume registered target regions,
80, 90, 75 and 70 meet four declared criteria. With no overlap observations,
the possible joint count is **15–70**, not a known 37.8. The latter is only an
independence-product benchmark. A second fixture intentionally substitutes
an allele denominator: the audit returns an unidentified result. A third
fixture supplies a synthetic measured joint count of 40, which is compatible
with the bounds. None of these counts describes real cells or organoids.

For N shared units and k endpoint-attainment counts n_i, the exact marginal
overlap bounds are max(0, sum(n_i)−(k−1)N) and min(n_i). The audit requires an
explicit shared population, sampling frame, unit, count and timepoint.
Missing endpoints stay unknown. Different-unit measurements require a
validated crosswalk before they can become shared-unit observations.
These bounds concern declared assay criteria, not validated functional repair.

Six tests include an exhaustive 4-unit/3-endpoint overlap oracle, denominator
and time mismatch rejection, missingness, inconsistent joint counts and invalid
inputs. The implementation assumes exact counts in a fixed set: it does not
propagate assay error, sampling uncertainty or spatial dependence. A marker
criterion cannot become a functional one just by passing this audit.

## Source-qualified transfer limits

Quintard et al. established intravascular perfusion in blood-vessel
organoids-on-chip and examined pancreatic islet spheroid function. This is a
useful transport chassis, not a demonstration of a genetically corrected,
innervated tooth attachment or organ replacement.
[Primary study](https://doi.org/10.1038/s41467-024-45710-4).

The initial patient-specific CPS1 base-editing report concerns one infant and
a known liver-disease variant with short initial follow-up. It supplies a
clinical delivery/response precedent, not identification or correction of
distributed ordinary-aging variants across organs.
[Original report](https://doi.org/10.1056/NEJMoa2504747).

The newly qualified [MOTS-c stem-cell counterevidence](../compounds/REPORT.md)
is relevant when selecting functional endpoints: pathway engagement must be
paired with cell state and repair outcomes. Consult that report's exact
source, donor design and animal-model limitations.

## Next integrated research packet

1. Declare a relevant causal lesion if editing is proposed, the target
   lineage/compartment, comparator and functional deficit. Keep ordinary aging
   separate from a monogenic disease model.
2. Qualify assays and matched reference distributions for each endpoint.
   Preserve intended-only products, structural/RNA outcomes where relevant,
   identity, proliferation/clone behavior and adverse outcomes separately.
3. Register comparable target regions or traceable constructs. Measure
   perfusion and viability, then the tissue-specific interface/function on
   the same sampling frame. Destructive measurements require a validated
   pairing/crosswalk or remain separate observations.
4. Report joint attainment where observed, marginal bounds where identifiable
   and unknowns otherwise. Keep constructs and fields nested in donor, clone
   and manufacturing batch; this audit does not create independent donors.
5. Test persistence after intervention withdrawal. For dental attachment,
   intended pose after finite support ends, physiological mobility and no
   ankylosis/resorption remain distinct requirements. A chip cannot satisfy
   retained-tooth positional durability.

The immediate useful next input is a paired, traceable construct-level dataset
with calibrated perfusion, identity and functional-interface outcomes. Do not
choose editing targets, numerical repair thresholds or a delivery formulation
from the synthetic example. This is a measurement/integration specification,
not a wet-lab or human-treatment protocol.

## Reproduce

```text
python studies/checklist-progress-2026-10-19/integration/audit_joint_endpoints.py
python -m unittest discover -s tests -p test_joint_regeneration_endpoints.py -v
```

The [fixtures](joint_endpoint_examples.json) and
[hash-linked audit output](derived/joint_endpoint_audit.json) are public,
synthetic and contain no personal data. No organoid, animal or person was
treated, and no sibling repository was modified.
