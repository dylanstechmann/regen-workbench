# Regen Workbench

Local Docker lab that covers most of the ChatGPT “Scientific Research”
plugins and DeepMind Science Skills **without** putting those vendors in
the loop for every lookup.

It is meant to be the computer that Codex / Grok Build / Antigravity
drive, instead of their small cloud sandboxes.

Research direction: prioritize exploratory molecular modeling, simulation,
and direct gene-expression and compound-data analysis for aging and
regeneration. See [Research philosophy and priorities](RESEARCH_PHILOSOPHY.md)
for the owner's ambitions and approach to scrutinizing evidence and bias.

New local activities: [compare expression datasets and explore compound
conformers](EXPLORATION.md), with runnable examples, sensitivity diagnostics,
3D SDF outputs, and reproducible input/parameter records. Use
`regen expression-contrast --help` and `regen compound-screen --help`.

## What you get after bootstrap

| Layer | Contents |
|---|---|
| Workbench image | Python 3.11, JupyterLab, RDKit, Open Babel, Open-source PyMOL, Biopython, Scanpy, Nextflow, MAFFT/MUSCLE/ClustalO, BLAST, MMseqs2, Foldseek, HMMER, FastQC, MultiQC, seqkit, samtools, minimap2, AutoDock Vina, fair-esm, `regen` CLI |
| Sibling image (optional) | Official ColabFold CUDA image, pulled on `--gpu` |
| Volumes | `projects/` (git repos), `data/` (fetched files), `cache/` (weights) |
| GPU | `--gpus all` + 16 GB `/dev/shm` |
| MCP server | Allowlisted research tools exposed to MCP-capable coding agents |

What is **not** baked in: AlphaFold 3, full AF2 genetic databases, RFdiffusion
weights, Schrödinger, wet-lab robots. See `MANUAL_ACCOUNTS.md`.

## Laptop prerequisites

- Docker Engine + Compose v2
- NVIDIA driver + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) for GPU workloads
- Enough disk for images + caches (budget 40–80 GB the first week)

## Start

```bash
chmod +x scripts/*.sh tools/regen tools/regen.py tools/regen_mcp.py
./scripts/host-setup.sh
./scripts/bootstrap.sh          # start workbench, Jupyter, and MCP service
```

On Windows (PowerShell, no Git Bash/WSL needed):

```powershell
.\scripts\Host-Setup.ps1
.\scripts\Bootstrap.ps1          # start workbench, Jupyter, and MCP service
```

For GPU workloads, check GPU support and start with the GPU override:

```bash
./scripts/host-setup.sh --gpu
./scripts/bootstrap.sh --gpu    # also pull ColabFold
```

Then:

```bash
docker compose exec workbench bash
regen doctor
regen uniprot P04637
regen afdb P04637
regen pubmed "AK2 splice variant iPSC" --retmax 8
```

The default workbench starts without a GPU reservation. Use `--gpu` when
running GPU workloads; to enable GPU access on an existing installation,
run `./scripts/bootstrap.sh --gpu` again. The MCP service remains CPU-only.

Jupyter: http://127.0.0.1:8888 (loopback only; keep Jupyter's token enabled).

## MCP tools for coding agents

The startup script runs a dedicated `mcp` service without published ports,
host credentials, or a Docker socket. Configure Codex, Cline, or a local
Antigravity client that supports custom stdio servers
to launch the allowlisted stdio server through the laptop's Docker Compose
CLI. See [`MCP_SETUP.md`](MCP_SETUP.md) for client-specific setup.

Tools cover PubMed, EuropePMC, OpenAlex, UniProt, InterPro, Ensembl,
AFDB/PDB fetches, STRING, ChEMBL, PubChem, local sequence alignment, RDKit
descriptors, batch compound conformers, expression contrasts, PyMOL rendering,
fold routing, and diagnostics. The server also
exposes read-only MCP **resources**: the `tools.yaml` capability map and the
provenance receipt log, so agents can inspect what the workbench supports and
what data has already been fetched. The server has no arbitrary shell tool and
does not run folding models. Fetch/render calls write provenance under
`data/provenance/`.

## How to use this with paid agents

1. Keep this container running.
2. Open the repo you want improved **inside** `/projects`.
3. Configure the selected agent with the MCP instructions in `MCP_SETUP.md`.
4. Paste `agent/AGENT_BRIEFING.md` as standing project guidance.
5. Review diffs and `data/provenance/`; keep one agent on a repo at a time.

Your 64 GB / 16 GB machine will beat a typical vendor sandbox on
Scanpy, RDKit, MSA, and modest folds. Their cloud box still wins at
unattended multi-hour jobs if you close the laptop — so do not start a
4-hour Boltz job on battery.

## Layout

```
regen-workbench/
  docker-compose.yml
  .dockerignore           # excludes secrets/data/projects from image context
  docker/workbench.Dockerfile
  tools/regen.py          # plugin stand-in CLI
  tools/regen_mcp.py      # allowlisted MCP stdio server (tools + resources)
  tests/test_regen_mcp.py # protocol/security tests
  MCP_SETUP.md            # Codex, Cline, Antigravity client setup
  config/tools.yaml       # capability map
  scripts/host-setup.sh   # Linux/macOS/Git Bash
  scripts/bootstrap.sh    # Linux/macOS/Git Bash
  scripts/Host-Setup.ps1  # PowerShell (Windows)
  scripts/Bootstrap.ps1   # PowerShell (Windows)
  agent/AGENT_BRIEFING.md
  agent/PROJECT_SEEDS.md
  MANUAL_ACCOUNTS.md
  projects/               # your GitHub checkouts
  data/                   # fetched biology artifacts
  cache/                  # model weights, ColabFold cache
```

## Development checks

The CLI and MCP regression tests use the Python standard library, mock remote
APIs, and do not require database credentials, a GPU, or the full scientific
image. From this repository in the shared workspace, run:

```powershell
docker compose -f ../compose.yaml run --rm --no-deps dev python3 -B -m unittest discover -s regen-workbench/tests -v
```

For a standalone checkout with Python 3.11 available, run
`python -B -m unittest discover -s tests -v` from the repository root.

The MCP server returns protocol errors for malformed resource requests and
unreadable resource files, keeping the session available for later requests.
Oversized input lines are discarded in bounded chunks. Individual resource
files are read only up to the output limit before a truncation marker is added.

## Frozen cohort check

`studies/frozen_cohort/PROTOCOL.md` is the estimand. The runner wires
`regen expression-contrast`, an explicit Welch/BH view, a GiWi window fixture,
and a group-aware morphology holdout. Age is aliased with donor on purpose.
A shared batch id is refused instead of scored. `atlas_link.json` carries the
phenotype manifest hash for a later compound-atlas citation. The hash is not
an activity label.

```bash
PYTHONPATH=tools python3 studies/frozen_cohort/run_study.py --out artifacts/frozen-cohort
```

The output directory must be new. The cohort is synthetic.

## License

Scripts in this folder are CC0. Third-party tools keep their own licenses
(RDKit BSD, PyMOL BSD-like open-source build, ColabFold / AF2 weights
Apache + DeepMind terms, Boltz separate, NCBI data use policies).
Read those before you publish a paper off this stack.
