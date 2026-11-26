# Things you must do yourself

The workbench automates lookups and local compute. It cannot create vendor
accounts, accept licenses, or guarantee that large structure-prediction jobs
fit on 16 GB VRAM. Do these once, then point agents at the resulting keys via
`.env`.

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
| OpenFold3 preview | Complex-structure prediction based on AlphaFold 3 | Open source; optional Docker image and model-parameter download | Use `docker compose --profile openfold3 run --rm openfold3 predict ...`; see [DOCKING.md](DOCKING.md) for caveats and data flow |
| OpenTargets / ClinVar / gnomAD web or REST | Genomic intelligence plugins | Free | Query, do not mirror the full DBs |
| Foldseek web / local binary | Structural search | Local binary is in the image; web for huge DBs | Local first |

## Paid or gated — only when a project needs that artifact

| Service | Why it is not in the image | Expected spend if you insist |
|---|---|---|
| AlphaFold 3 official weights | Separate model-parameter terms and substantial compute | Not configured in this checkout; use the OpenFold3 preview profile for local exploratory complex predictions |
| NVIDIA NIM Boltz-2 local container | Local NGC pulls are separate from hosted API Catalog inference and need a large image plus suitable VRAM | Local NGC credentials do not authorize or configure the hosted Boltz-2 CLI |
| PyMOL Incentive | Open-source PyMOL is already in the image | Skip unless you need incentive-only features |
| ChimeraX daily build | Better GUI, not required for headless figures | Free for non-commercial; install on the **host desktop**, not Docker |
| GOLD / Schrödinger Glide / MOE / Discovery Studio-FlexX | External commercial docking suites | Not bundled; use only with the appropriate current license |
| GNINA | Optional CNN-scoring dock engine | Install the checksum-pinned v1.3.3 binary into shared cache with `regen install-gnina`; runner is CPU-only |
| DiffDock | Separate deep-learning docking environment and model weights | Not installed; evaluate as an independent local backend before adding it |
| Rowan / DFT vendors | Quantum chemistry credits | One calculation for a paper figure, not a subscription |
| Adaptyv Bio | Wet-lab protein orders | Hundreds of $ per protein; only after computational triage |
| Inductive / commercial ADMET | Sales-gated | Use RDKit + public Chemprop weights first |
| Full AF2 genetic DBs (~2 TB+) | Disk + days of download | Use ColabFold MSA server instead |
| RFdiffusion all-atom campaigns | VRAM + weights + license maze | Tamarind or a rented A100 |
| CELLxGENE / BioHub bulk datasets | Full mirrors are not configured and H5AD is outside this integration | Inspect one public collection with `regen biohub collection COLLECTION_UUID --out data/provenance/biohub/NEW_DIR`; metadata/manifest only, no H5AD download |

### CELLxGENE / BioHub scope

The public collection command is unauthenticated and metadata-only. Review each
dataset's source, policy, attribution and license obligations before any future
use; the Discover portal policy link alone does not complete that review. New
output directories stay under ignored `data/provenance/biohub/`, and the receipt
hashes metadata JSON rather than claiming an H5AD checksum. Census, Virtual
Cells Platform, MLflow, model and benchmark entries from `regen biohub resources`
are links only. They do not execute models or benchmarks, connect to MLflow, or
assert universal open model licensing.

### NVIDIA hosted Boltz-2 scope

`regen boltz2 predict REQUEST.json --out data/structures/boltz2/NEW_DIR` is a
hosted API Catalog adapter, not a local NGC container pull. It reads only the
already-injected `NVIDIA_API_KEY` process variable and never falls back to
opening `.env` itself. The existing one-off `remote-fold` profile can inject
that variable without putting the key in command arguments.

This phase used no NVIDIA key and made no NVIDIA network request or hosted
inference; its responses and transports were synthetic/mocked. Hosted model
version, service limits, MSA behavior, runtime, charges, and inference results
remain unobserved. The previously exposed chat key is compromised and was not
used. Before any future live submission, rotate it privately and review the
hosted trial terms, NVIDIA Community Model License, upstream MIT license,
input/output retention, quota/cost, and input sensitivity. Do not paste the
rotated key into chat or write it into a request, fixture, receipt, or manifest.

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
