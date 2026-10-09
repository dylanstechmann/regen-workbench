# Regen Workbench

This is a personal hobby and learning project, developed with substantial
assistance from AI coding tools.

Local Docker lab that covers most of the ChatGPT “Scientific Research”
plugins and DeepMind Science Skills **without** putting those vendors in
the loop for every lookup.

It is meant to be the computer that Codex / Grok Build / Antigravity
drive, instead of their small cloud sandboxes.

Research direction: prioritize exploratory molecular modeling, simulation,
and direct gene-expression and compound-data analysis for aging and
regeneration. See [Research philosophy and priorities](RESEARCH_PHILOSOPHY.md)
for the owner's ambitions and approach to scrutinizing evidence and bias.

The [dental-regeneration research track](studies/dental-regeneration-2026-10-09/README.md)
adds desk areas for teeth/gums/periodontal attachment and organoid/stem-cell
construct function. It records component-level evidence, conflicting clinical
endpoints and six starter campaigns. The independent
[base-editing-evidence](https://github.com/dylanstechmann/base-editing-evidence)
repo audits genome-editing source scope and cell-count denominators.

The [biomedical development roadmap](ROADMAP.md) prioritizes ectogenesis model
verification, reviewed organoid measurements, portable ResearchDesk dossiers
and concrete empirical milestones across the companion methods repositories.
The [research programs](RESEARCH_PROGRAMS.md) develop the next questions toward
artificial gestation and durable youthful function, with competing explanations,
eligible dataset candidates, repository ownership and release gates.

## Interactive research desk

The [research desk](RESEARCH_DESK.md) adds editable hypothesis blueprints,
literature/registry/web searches, explicitly tagged anecdote and vendor-claim
intake, PubChem structural neighbors, small-molecule analog enumeration,
property comparisons, and reproducible RDKit conformer runs. Existing API
keys stay in the gitignored `.env`; the browser receives configuration flags
and research results, never credentials.

```powershell
docker compose -f compose.research.yaml up -d --build
```

Open [http://127.0.0.1:8092](http://127.0.0.1:8092). This lightweight service
does not require the full scientific/folding image. Runs and saved
observations stay under `data/research-desk/`; fetch receipts remain under
`data/provenance/`. The default priorities are somatic mutation repair,
engineered tissues and nanomedicine, followed by organs, senescence and
structural restoration.

The **Study design** view stores content-hashed, append-only question,
dataset-card and analysis-plan drafts. Dataset metadata includes source-file
inventory, unit hierarchy, exact quantities, missingness and exclusions; plans
link exact revisions and require competing predictions and a falsifier. The
records are included in dossier exports. Their presence does not establish
source review, data eligibility or a completed analysis.

Three further record types **freeze a plan before it is run**. A *plan freeze*
pins one plan revision, the question and dataset-card revisions it links, a
method revision and a development / final-test split. A *holdout-access ledger*
is a hash-chained list of every recorded touch of those groups. An *evaluation
binding* checks one sibling-repository receipt (regen-benchmark-kit metrics, or a
generic receipt format) against the freeze: pinned inputs, the same split,
whether a sealed group was used in training, producer-reported overlap, the
method revision and timing. From these the Desk derives a claim state such as
`holdout_sealed`, `single_final_evaluation_recorded`,
`holdout_reused_not_independent` or `retrospective_not_confirmatory`. This is
procedural bookkeeping. The freeze clock, the "results already inspected" answer
and ledger actors are self-reported; a binding does not show that an analysis was
correct or that a receipt is genuine; nothing here runs a model. The
[worked example](studies/frozen-evaluation-example/) applies it to the committed
NIST iPSC benchmark receipt (a retrospective, development-only record: its
leave-one-well-out design cannot be a final test of any well) and to one labeled
synthetic fixture.

### Verify an exported dossier somewhere else

A dossier export now carries `reproduction-plan.json` beside its inventory: the
checked-out workbench revision (with an explicit `unknown` when git is absent and
a flag when the working tree was dirty), the Python version, the dependencies a
rerun would need, the commands, the hashed inputs and the expected outputs.

`regen verify-dossier <archive.zip>` checks that archive on its own, using only
the Python standard library, so a reviewer needs neither this repository nor the
machine that exported it:

```bash
python tools/verify_dossier.py path/to/dossier.zip --strict --json
```

It rejects unsafe member paths, symlink entries, duplicate members and oversize
files before reading them, recomputes every SHA-256 against the inventory,
requires the core documents, and checks that each linked experiment manifest and
model receipt declared in `dossier.json` resolves to the exact bytes archived
alongside it. Relocating or renaming the archive does not affect the result.

The report keeps four questions apart: `bytes_verified` (archive integrity),
`ancestry_resolved` (declared sources resolve inside the archive),
`scientific_lineage` (the archived research revisions re-hash to their declared
content hashes; plan-freeze pins resolve to unchanged revisions inside the
archive; each ledger hash chain is intact; the exported claim state matches a
recomputation) and
`scientific_review`, which is always `not_established_by_this_tool`.
`reproduction` is always `not_attempted` — verifying an archive is not rerunning
an analysis. Lineage needs `frozen_evaluation.py` beside the verifier and is
`not_checked` without it. `--strict` also fails on members the inventory does not
declare, on run outputs that did not match their run manifest at export time, and
on an archive whose index lists source files excluded at export (a symbolic link,
a special file, an oversize or concurrently changed file); without it, those are
reported as warnings.

The dated [API and chemistry campaign report](RESEARCH_RUN_2026-09-28.md) is a
historical snapshot:
57 runs, 173 provider records before deduplication, 236 verified artifact
hashes, four compared dipeptides, six structural hypotheses and 30 converged
conformers. Run counts are not independent studies or efficacy evidence.

New local activities: [compare expression datasets and explore compound
conformers](EXPLORATION.md), with runnable examples, sensitivity diagnostics,
3D SDF outputs, and reproducible input/parameter records. Use
`regen expression-contrast --help`, `regen compound-screen --help`, and
`regen pipeline --help` (chained contrast -> source-labeled module scoring -> grouped, fold-local benchmark evaluation with cryptographic provenance wiring).

Structure-based exploration includes local, provenance-recorded Vina and
optional GNINA CNN-rescoring CLI/MCP runners plus an on-demand OpenFold3 preview
container profile. GNINA is installed explicitly into the shared cache with a
version-pinned, checksum-verified asset. See [DOCKING.md](DOCKING.md) for input
preparation boundaries, commands, and the status of the other small-molecule
and protein/peptide docking engines. The control-aware docking benchmark
reports active/inactive-control ROC AUC, enrichment, and optional
symmetry-aware pose RMSD; it does not claim biological activity. OpenFold3
predicts complex structures; it does not replace docking.

The mutation-repair pilot includes a deterministic regeneration script for
selected body-map, skin, and NanoSeq supplementary-table summaries. It verifies
all six workbook snapshots against pinned sizes and SHA-256 values before
writing aggregate tables; it does not model or demonstrate mutation repair.
See [`MUTATION_REPAIR_PILOT.md`](MUTATION_REPAIR_PILOT.md).

The pilot also includes a reproducible HGPS TEBV vasodilation benchmark. A
versioned 1.4 [experiment manifest schema](tools/schemas/experiment-manifest.schema.json)
links protocol, raw assay data, analysis/model, and calibration status;
`docker compose exec workbench python /lab/workbench/tools/validate_experiment_manifest.py PATH`
checks the schema, linked artifact IDs, safe repository paths, and local
SHA-256/byte counts. The current
public study has one HGPS donor, so its donor-held-out validation is marked
`not_testable`.

Manifests can also enumerate functional, cell-identity, viability,
genome-stability, adverse-effect, and durability outcomes as measured, planned,
not assessed, or unavailable. `not_assessed` means the study explicitly did not
collect that outcome; `not_available` means this manifest lacks supporting
evidence. A measured outcome must link to assay data, and all six domains must
be represented when this section is present.

Schema 1.3 also distinguishes measured, planned, and unavailable assays. A
measured assay must link its data artifact; planned or unavailable assays can
be described without inventing a raw-data link. ResearchDesk displays assay
status alongside its endpoint and sample-count description. The kidney
tubuloid cyst-induction image inventory is an example: the public archive has
images but no masks or object tracks in this local record, so the analysis is
marked unavailable pending reviewed annotations. Schema 1.4 records the model
system's species and developmental interval separately from run history, and
preserves imported runs with explicit current-analysis pointers. The local
annotation plan and the package's zero-mask receipt remain separate, hash-linked
records; re-imports append history instead of replacing previous outputs.

The [simulation-toolchain fixture](studies/simulation-toolchain/README.md) links
protocol constraints, synthetic media-planner observations, an illustrative
oxygen transient, and a synthetic calibration report across the sibling methods
repositories. Its local validator checks all artifact hashes. It is software
verification only and makes no wet-lab, physical calibration, or biological claim.

## What you get after bootstrap

| Layer | Contents |
|---|---|
| Workbench image | Python 3.11, JupyterLab, RDKit, Open Babel, Open-source PyMOL, Biopython, Scanpy, Nextflow, MAFFT/MUSCLE/ClustalO, BLAST, MMseqs2, Foldseek, HMMER, FastQC, MultiQC, seqkit, samtools, minimap2, AutoDock Vina, fair-esm, `regen` CLI |
| Sibling images (optional) | Official ColabFold CUDA image; OpenFold3 preview image on the `openfold3` profile |
| Volumes | `projects/` (git repos), `data/` (fetched files), `studies/` (reproducible analyses), `cache/` (weights) |
| GPU | `--gpus all` + 16 GB `/dev/shm` |
| MCP server | Allowlisted research tools exposed to MCP-capable coding agents |

What is **not** baked into the workbench image: OpenFold3 weights (cached on
first use by its optional profile), the optional GNINA binary (explicitly
downloaded into shared cache), DiffDock, RosettaDock, licensed commercial
suites, full AF2 genetic databases, RFdiffusion weights, or wet-lab robots.
See `MANUAL_ACCOUNTS.md` and `DOCKING.md`.

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
descriptors, batch compound conformers, Vina docking and optional GNINA CNN
rescoring on prepared PDBQT files, docking validation, expression contrasts,
PyMOL rendering, fold routing, and diagnostics. The server also
exposes read-only MCP **resources**: the `tools.yaml` capability map and the
provenance receipt log, so agents can inspect what the workbench supports and
what data has already been fetched. The server has no arbitrary shell tool and
does not run folding models. Fetch/render calls write provenance under
`data/provenance/`.

Hosted OpenFold3 runs use a separate, one-off `remote-fold` Compose profile:
`regen fold-japanfold` for protein/RNA/DNA inputs and `regen fold-nvidia` for
native NVIDIA requests, followed by `regen compare-structures` for a reference
check. The profile reads only the two provider keys from the ignored host
`.env`, saves outputs under ignored `data/structures/`, and exits after each
command. It does not expose inference through MCP or the research desk. See
[DOCKING.md](DOCKING.md) for commands, provider limits, and public benchmarks.

Saved desk-run integrity can be checked without changing data or making
network calls:

```bash
python tools/research_audit.py --root data/research-desk
```

This fails on missing or malformed manifests, hash mismatches, unlisted files,
or orphan runs. Older saved runs from before manifest finalization was added
are reported rather than silently marked verified.

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


The signed Fridman score subtracts independently control-adjusted raw DOWN
expression from raw UP expression; training folds normalize that contrast only
after subtraction, matching the standalone scorer's direction convention.
Stage 3 honors the requested expression-bin count and marker pseudocount.
Simulation manifests validate in any sibling workspace, while standalone
contract tests require no sibling clone. Experiment manifest version 1.0
remains supported; environmental fields require version 1.1.
