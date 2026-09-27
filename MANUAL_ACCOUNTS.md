# Things you must do yourself

The workbench automates lookups and local compute. It cannot create vendor
accounts, accept licenses, or magically fit AlphaFold-3-scale jobs on 16 GB
VRAM. Do these once, then point agents at the resulting keys via `.env`.

## Do now (free, high leverage)

| Action | Why | URL / note |
|---|---|---|
| NCBI account + API key | PubMed / E-utilities rate limits. Without it the agent will get 429s. | https://www.ncbi.nlm.nih.gov/account/ |
| Put a real `.edu` email in `.env` | UniProt, OpenAlex, EBI expect a contact. | `.env` `EMAIL=` |
| GitHub CLI/device login or SSH key on the **host** | GitHub authentication stays on the laptop; perform Git push/pull from the host because host credentials are not mounted into workbench containers. Never paste a PAT into chat. | https://github.com/settings/keys |
| NVIDIA Container Toolkit on the host | Without it the container cannot see the GPU. | NVIDIA install guide |
| Create GitHub repos empty, or use `gh repo create` from the host | The workbench does not hold a cloud sandbox identity. | — |

## Academic / free tiers worth opening with the .edu address

| Service | What it replaces | Cost if you stay on the free/academic tier | When to actually use it |
|---|---|---|---|
| Tamarind Bio | Large Boltz / AF3-class folds, design campaigns | Free tier + academic bump (job caps) | 16 GB VRAM OOM, multimers, ligands + affinity at size |
| Colab (Google account you already have) | Occasional A100-class fold | AI Pro already paid; Colab compute is separate and metered | One showcase complex |
| RCSB / AFDB / UniProt / STRING / ChEMBL / PubChem / EuropePMC | Plugin databases | Free | Already wired in `regen` |
| ColabFold public MSA server | Local MMseqs2 1 TB+ DBs | Free, rate-limited | Default for ColabFold sibling jobs |
| OpenTargets / ClinVar / gnomAD web or REST | Genomic intelligence plugins | Free | Query, do not mirror the full DBs |
| Foldseek web / local binary | Structural search | Local binary is in the image; web for huge DBs | Local first |

## Paid or gated — only when a project needs that artifact

| Service | Why it is not in the image | Expected spend if you insist |
|---|---|---|
| AlphaFold 3 official weights | Google terms + 40–80 GB class GPUs | Request weights; run on cloud GPU, not this laptop |
| NVIDIA NIM Boltz-2 | Needs NGC account + large pull + often more VRAM than you have | NGC key in `.env`; prefer `pip install boltz` locally |
| PyMOL Incentive | Open-source PyMOL is already in the image | Skip unless you need incentive-only features |
| ChimeraX daily build | Better GUI, not required for headless figures | Free for non-commercial; install on the **host desktop**, not Docker |
| Schrödinger / MOE / GOLD | Closed docking suites | Not worth it vs GNINA/Vina for student repos |
| Rowan / DFT vendors | Quantum chemistry credits | One calculation for a paper figure, not a subscription |
| Adaptyv Bio | Wet-lab protein orders | Hundreds of $ per protein; only after computational triage |
| Inductive / commercial ADMET | Sales-gated | Use RDKit + public Chemprop weights first |
| Full AF2 genetic DBs (~2 TB+) | Disk + days of download | Use ColabFold MSA server instead |
| RFdiffusion all-atom campaigns | VRAM + weights + license maze | Tamarind or a rented A100 |
| scRNA reference atlases (full CELLxGENE mirrors) | Hundreds of GB | Download **one** tissue/study into `data/` |

## Google Cloud, on purpose

AI Pro **5 TB Drive** is for files, not GPUs.

Sensible GCP use (optional, not required to start):

1. Make a GCP project with billing alerts at $10 and $25.
2. Enable Cloud Storage. Sync bulky `data/` you do not want on GitHub.
3. Do **not** lift this whole IDE into a VM.
4. If a fold will not fit 16 GB, spin a short-lived GPU VM or use Tamarind. Delete the VM the same day.

## Plugin → workbench cheat sheet

| ChatGPT / Antigravity plugin-like thing | In this repo | Manual leftover |
|---|---|---|
| Life Sciences Literature | `regen pubmed / openalex / europepmc` | NCBI key |
| Life Sciences Databases | `regen uniprot / string / chembl / pubchem` | — |
| Molecular Structure Viewer | `regen pymol-png` + Jupyter py3Dmol | ChimeraX on host if you want a GUI |
| Biological Sequence & Alignment Viewer | `regen msa` + seqkit | — |
| Rosalind / NGS workbench | Nextflow/FastQC/MultiQC/Scanpy locally; run Docker-based nf-core pipelines from the host | AWS/GCP only for huge FASTQs |
| Genomic Intelligence | Ensembl/ClinVar REST from notebooks | gnomAD full VCF is a cloud object, not local |
| Boltz plugin | `boltz` pip if install succeeded; else Tamarind | NGC NIM optional |
| Proto / design plugins | ProteinMPNN clone into `projects/` when needed | RFdiffusion overflow |
| Inductive ADMET | RDKit descriptors + later Chemprop | Commercial API if you publish a screen |
| Rowan simulations | — | Pay-per-job only |
| Pendar / wet instrumentation | — | Lab access, not software |
| Adaptyv | — | Order after you have a design |

## Rules that keep quality high and bills low

1. Fetch AFDB or PDB before predicting.
2. Never commit FASTQs, model weights, or `.env`.
3. Every agent run must leave files under `data/provenance/`.
4. If `nvidia-smi` inside the container does not show the GPU, stop and fix the host toolkit. Do not “just use CPU folding.”
5. One planner at a time on a given repo (Grok **or** Codex **or** Antigravity), using this container as the shared computer.
