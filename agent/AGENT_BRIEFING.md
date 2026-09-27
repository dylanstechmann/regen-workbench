# Agent briefing — Regen Workbench

You are working on a laptop lab, not a tiny cloud sandbox.

Read [RESEARCH_PHILOSOPHY.md](../RESEARCH_PHILOSOPHY.md) before choosing new
features. Prioritize exploratory molecular modeling and direct expression
and compound-data analysis. Scrutinize published claims and our own
hypotheses consistently; preserve reproducibility and distinguish predictions
from demonstrated biological or human outcomes.

Hardware: ~64 GB RAM, 16 GB VRAM, i9, lots of disk. Docker image
`regen-workbench:local` is already running. Heavy tools that do not fit
16 GB must be routed to Tamarind / Colab, not hammered until OOM.

## First commands

```bash
regen doctor
cat /lab/workbench/config/tools.yaml
```

Use `regen` for literature (PubMed, OpenAlex, EuropePMC), UniProt, InterPro,
Ensembl, AFDB, PDB, STRING, ChEMBL, PubChem, MSA, RDKit, and PyMOL stills.
Do not invent curl loops against NCBI.

## Fold routing (mandatory)

1. Experimental structure? `regen pdb ID`
2. Natural UniProt protein? `regen afdb ACCESSION`
3. Designed / orphan monomer ≲ 600 aa? ESMFold (`fair-esm`) on this GPU
4. Natural sequence that needs an MSA? Use the ColabFold image manually from the host + public MSA server
5. Complex + ligand + affinity, modest token count? `boltz predict` if installed
6. Anything that OOMs or needs AF3-class size? Stop. Write a Tamarind/Colab job card in METHODS.md

## What to write in each GitHub repo

- `METHODS.md` — which command, which database version/date, which local tool
- `data/ACCESSIONS.tsv` — IDs + retrieval date
- raw files + sha256 via `regen` provenance under `data/provenance/`
- a script that regenerates figures (`regen pymol-png` or a `.pml`)
- no secrets, no model weights, no FASTQs

## Quality bar for regenerative-medicine student repos

Good:
- organoid oxygen/nutrient diffusion notebooks with units and citations
- iPSC protocol formalization as executable YAML + QC checklists
- aging atlas analysis on **one** public dataset (not a 400 GB mirror)
- binder design *pipeline* that stops at in-silico metrics
- open hardware control (syringe pump, incubator log parser) with a BOM

Not good:
- “home iPSC therapy”
- uncited structure hallucinations
- claiming AF3 accuracy from an ESMFold monomer
- committing a 2 GB checkpoint

## Compute etiquette

- One agent product per repo per session.
- Prefer editing files in `/lab/projects/<repo>`.
- Jupyter is at http://127.0.0.1:8888 if you need a notebook artifact.
- GitHub authentication stays on the host. Do not expect host `~/.ssh`, an SSH agent, or a Docker socket inside the workbench; perform push/pull on the host.
- Never ask the user to paste a personal access token into chat.
