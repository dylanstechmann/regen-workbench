# Agent briefing — Regen Workbench

You are working on a laptop lab, not a tiny cloud sandbox.

Read [RESEARCH_PHILOSOPHY.md](../RESEARCH_PHILOSOPHY.md) before choosing new
features. One child git repo per session unless the user names an interface
between two. Do not merge the methods packages. Do not write a lab offer.
Do not ask anyone to paste API keys or passwords into chat.

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

If the user started Grok Build in the parent workspace folder, still edit
only the named child repo. See [PROJECT_SEEDS.md](PROJECT_SEEDS.md).

## Fold routing (mandatory)

1. Experimental structure? `regen pdb ID`
2. Natural UniProt protein? `regen afdb ACCESSION`
3. Designed / orphan monomer ≲ 600 aa? ESMFold (`fair-esm`) on this GPU
4. Natural sequence that needs an MSA? Use the ColabFold image manually from the host + public MSA server
5. Known small-molecule site with prepared receptor/ligand PDBQT? Run `regen dock-vina` with an explicit box; if GNINA is installed, compare using `regen dock-gnina --cnn_scoring rescore` with the same box and retain both hash-linked receipts. Agreement prioritizes follow-up; it does not establish binding.
6. Need a predicted non-covalent protein-ligand complex? Try the optional OpenFold3 preview profile or Boltz if installed and the job fits. These are co-folding predictions, not docking or affinity measurements.
7. Anything that OOMs or needs more than this laptop? Stop. Write a Tamarind/Colab job card in METHODS.md

## Chemistry

- Play gallery: `python -m gen.pipeline` in `geroscience-compound-atlas`
- Hypothesis cards: `python -m gen.hypothesis` — hard gates + anti-clone cap
- A card is not something a person consumes

## What to write in each GitHub repo

- `METHODS.md` — which command, which database version/date, which local tool
- `data/ACCESSIONS.tsv` — IDs + retrieval date
- raw files + sha256 via `regen` provenance under `data/provenance/`
- a script that regenerates figures (`regen pymol-png` or a `.pml`)
- no secrets, no model weights, no FASTQs

## Quality bar

Good: units, hashes, group holdout, published protocol windows, fixtures labeled
as fixtures, hypothesis cards that include a way to be wrong. Docking records
must retain receptor/ligand hashes and search settings; compare methods where
feasible.

Not good: home cell therapy, uncited structure hallucinations, AF3 claims from
ESMFold, committing checkpoints, stacking advice, keys in git or chat.

## Compute etiquette

- One agent product per repo per session.
- Prefer editing files in `/lab/projects/<repo>`.
- Jupyter is at http://127.0.0.1:8888 if you need a notebook artifact.
- GitHub authentication stays on the host. Do not expect host `~/.ssh`, an SSH agent, or a Docker socket inside the workbench; perform push/pull on the host.
- Never ask the user to paste a personal access token into chat.
