# First repos that actually use this stack

Pick two, not ten. Each should compile to a public GitHub repo with
METHODS.md and a figure generated from `regen`.

1. **afdb-first structure cards**
   Input: a gene list in aging / reprogramming (e.g. Yamanaka factors, SASP receptors).
   Pipeline: `regen uniprot` → `regen afdb` → pLDDT summary → `regen pymol-png`.
   Output: one markdown page per gene. No folding required.

2. **organoid oxygen diffusion notebook**
   Re-implement a published analytic / numeric oxygen-gradient model
   (McMurtrey and follow-ups) with SI units, parameter table, and a
   figure that matches a paper panel qualitatively.
   Tools: numpy/scipy/matplotlib already in the image.

3. **public atlas slice**
   One CELLxGENE or GEO study (reprogramming, senescent fibroblasts, or
   a single organoid dataset). Scanpy QC + one biological question.
   Do not download every human cell.

4. **RDKit filter for senolytic-like chemistry**
   Pull a ChEMBL query (`regen chembl`), compute Lipinski / TPSA, write
   a documented screen. No paid ADMET.

5. **fold-or-fetch router**
   A tiny CLI wrapper around `regen fold-route` that a later agent can
   call before it wastes VRAM.

After those exist, *then* add Boltz/ColabFold jobs as a sixth repo that
wraps one showcase sequence, with an explicit “this OOM’d, used Tamarind”
note if needed.
