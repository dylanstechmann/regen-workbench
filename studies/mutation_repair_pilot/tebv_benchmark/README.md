# HGPS TEBV vasodilation benchmark

This small reproducibility package asks whether the initial fraction of
`LMNA`-corrected HGPS vascular cells predicts a monotone rise in
acetylcholine-evoked vasodilation in tissue-engineered blood vessels (TEBVs).
The functional endpoint is percent vessel-diameter change after
phenylephrine followed by acetylcholine.

The package converts the public Figure 8 workbook into a tidy table, checks the
source archive hash, reports replicate-level descriptive summaries, records a
simple falsifier, and links the source protocol, assay data, author ANOVA,
analysis code, model specification, and calibration status in the shared
experiment manifest. The generic manifest format lives in the
[shared JSON Schema](../../../tools/schemas/experiment-manifest.schema.json).
The manifest marks vasodilation as the available functional outcome and
separately records cell identity, viability, genome stability, adverse effects,
and durability as unavailable in the linked evidence. Those gaps are not
imputed from the functional result.

Run from the workbench root:

```powershell
docker compose exec workbench python /lab/workbench/studies/mutation_repair_pilot/tebv_benchmark/analyze.py
docker compose exec workbench python /lab/workbench/tools/validate_experiment_manifest.py /lab/workbench/studies/mutation_repair_pilot/tebv_benchmark/experiment.json
```

The analysis runner uses Python's standard library. The manifest validator uses
`jsonschema`, included in the workbench image.

The source archive is CC0 and is pinned in `source_manifest.json`. Derived
files are written to `derived/`; rerunning the command refreshes them from the
same checked source bytes.

## What this benchmark can say

The source contains 35 vasoactivity values for five group labels over weeks 3
and 5. Its workbook has only three values for the 50:50 group at week 3, though
the paper caption reports four TEBVs per group. It also lacks individual TEBV
and donor identifiers. The source study used HGPS lines from one person,
donor 003; two clones from that donor do not provide independent donor
replication. The paper names another HGPS donor (HGADFN167) as a future
correction study.

For those reasons the manifest marks donor-held-out validation as
`not_testable`. The runner reports descriptive values and transcribes the
authors' ANOVA result from the provided PDF; it does not train a predictive
model or refit the ANOVA. The nondecreasing dose-response rule is falsified by
the observed group means at both timepoints. This is a one-donor in-vitro
monogenic disease model. It does not establish a correction threshold across
people, reverse ordinary aging, or support a human treatment.

The paper reports perfusion at 0.5 mL/min per TEBV and nominal wall shear of
6.8 dyn/cm². The public Figure 8 archive contains no measured flow trace or
calibration record. The related `perfusion-calibration-lab` entry in the
manifest is a tool reference only; its synthetic example is not the study's
physical calibration.
