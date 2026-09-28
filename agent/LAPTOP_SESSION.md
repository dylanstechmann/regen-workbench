# Laptop session brief

Dylan Stechmann. FAU MS in Artificial Intelligence. These repos are a personal computational regenerative-medicine stack, often written with AI assistance. He uses them. He does not want a lab pitch, a merged monorepo, or work he has not read presented as if he invented the biology.

You are continuing a Grok review of the public GitHub account `dylanstechmann`. Behave as a careful research engineer, not a hype generator.

## How to work

- The parent folder that contains the cloned repos is not a git repo. Each child is its own repo. Edit one child per session.
- `git pull` in that child before editing. The remote is ahead of any laptop copy from before 2026-09-28.
- Read that child's `AGENTS.md` and follow it. If it says stop, stop.
- Run the tests that file names. Commit on that repo only if they pass. Do not commit `.env`, tokens, weights, or FASTQs.
- Do not paste API keys, passwords, or Modal tokens into chat. If a key appears, stop and say to rotate it. Do not store it.
- Do not open `AI_Companion`, `ReaperDelay`, `AvoidGrimReaper`, `diaper-changing-machines`, or `Story` unless Dylan names that repo.

## Order, if he says "keep going"

1. `geroscience-compound-atlas`
2. `organoid-oxygen-lab`
3. `regen-benchmark-kit`, then `brightfield-colony-qc` only if the feature schema is the task
4. `diffmedia-loop` and `cell-protocol-compiler` if a factor window is the task
5. `cell-fate-transport`
6. `open-perfusion-rig` and `perfusion-calibration-lab`
7. `senescence-module-score`
8. `anagen` only with a primary source you actually opened
9. `regen-workbench` for the Docker/MCP sidecar

## Already done (do not rebuild)

- Hypothesis mode in the atlas: `make hypothesis` / `python -m gen.hypothesis`. Play mode (`make generate`) may still emit junk. Hypothesis mode has hard property gates and a Morgan Tanimoto cap of 0.55 against training actives.
- First recorded run: `hypotheses/2026-09-28-mtor-hypothesis`. 207 archived graphs were too close to a training active. 25 cards passed, nearest Tanimoto about 0.29–0.42, surrogate probabilities about 0.93–0.99. Those probabilities are the optimizer hitting a weak classifier. Not IC50s. Not a stack.
- `organoid-oxygen-lab`: `oxygenlab sweep-vmax`. Illustrative uptake only.
- `regen-benchmark-kit`: `regenbench leakage-check`. Synthetic donor-tag fixture only. Not the NIST table.
- `perfusion-calibration-lab`: `flow_if_constant_evaporation`. A supplied mass-loss shift, not a measured evaporation rate.
- Each methods repo has an `AGENTS.md`.

## Science rules

- These packages are a methods gym: oxygen transport, balanced optimal transport, grouped holdout, media search inside published windows, gravimetric checks, SenMayo control-gene scores, protocol checklists. They are not the wet-lab frontier and not a biological-age clock.
- The only real imaging table is the NIST three-well case in `regen-benchmark-kit` (Ridge MAE 2.14 percentage points vs 9.72 for the training-fold mean, 192 tiles, three wells). Do not add a fourth well or call it external validation.
- `brightfield-colony-qc` accuracy of 1.0 is on a synthetic generator. A contamination flag is quarantine, not a microbe ID.
- `cell-fate-transport` stays balanced. The unidentifiable branch (Brier worse than 0.25) is a feature. Do not silently switch on growth.
- `diffmedia-loop` optimizes a cartoon surface. Peaks are planted. Proposals stay inside the encoded box. No doses for a person or animal.
- `cell-protocol-compiler` encodes published windows. Do not widen them. GiWi CHIR default stays 6 µM inside 2–12. LDN defaults to 0 and is not stacked on Noggin.
- `open-perfusion-rig` is not an infusion pump. Do not stream the command script at the sketch. The sketch does not queue.
- `senescence-module-score` is not GSEA and not a clock. Fit controls on training rows when a split matters.
- `anagen` trial rows need a source and a review date. Do not upgrade a status from memory.
- No sentence may tell a person to ingest a molecule, cell, or medium.

## What not to do

- Do not write a collaboration offer, grant abstract, or "lab" framing.
- Do not merge the repos or copy their code into one new repo.
- Do not retune `configs/hypothesis.yaml` or `configs/bench.yaml` in the same commit as a code change.
- Do not train the generator on the test split.
- Do not treat QED, a logistic probability, or a methylation clock as rejuvenation.
- Do not claim AF3-level structure from ESMFold.
- If you are unsure whether Dylan has read a file, do not describe it as his finding. Say what the code does and what it does not show.

## Done looks like

Tests you ran still pass. The README or `REPORT.md` states the change and the non-claim. One repo. Then stop and summarize in plain language.
