# Docking and Complex Prediction

This checkout runs AutoDock Vina locally, can add the optional GNINA CNN
rescoring binary to the shared cache, and provides OpenFold3 as an on-demand
model profile. Other named tools are cataloged for method selection, not
silently installed or called. Keep an experimental PDB structure with its
bound ligand ahead of predicted receptors when one exists.

## What Each Operation Means

- **Docking** searches ligand poses in a specified binding box and scores them
  with an approximate scoring function. A pose or score is not a measured
  affinity, target-engagement result, efficacy, safety, or anti-aging benefit.
- **Co-folding** predicts a protein-ligand or protein-protein complex from
  molecular inputs. It does not replace site-focused docking or experimental
  validation.
- **Rescoring** evaluates an already generated pose with another function or
  model. Agreement across methods is useful for prioritization, not independent
  biological confirmation.

## Local Vina Run

The MCP tool `regen_dock_vina` and CLI command `regen dock-vina` accept prepared
receptor and ligand `.pdbqt` files, an explicit search-box center and size in
Angstroms, and a new result path under `data/`. Inputs may be under `data/` or
`projects/`. The runner rejects files over 25 MiB, refuses to overwrite a
result, uses a fixed argument list (no shell), caps jobs at 15 minutes, and
stores input hashes, settings, engine version, success/failure status, and a
bounded transcript in the provenance receipt. Successful runs also include the
result hash; failures retain a receipt with diagnostics.

Example from the workbench root:

```bash
docker compose exec workbench regen dock-vina \
  data/structures/receptor.pdbqt data/structures/ligand.pdbqt \
  --center_x 10 --center_y 12 --center_z 8 \
  --size_x 20 --size_y 20 --size_z 20 \
  --exhaustiveness 16 --num_modes 9 --cpu 4 --seed 42 \
  --out data/structures/example-01.pdbqt
```

Files must already be properly prepared. This runner intentionally does not
guess protonation states, repair missing residues, remove cofactors/metals or
waters, assign ligand stereochemistry, or choose the pocket. Keep those
decisions in the job notes and test more than one defensible preparation where
they may change the answer. Use the official
[Vina manual](https://vina.scripps.edu/manual/) and
[basic docking guide](https://autodock-vina.readthedocs.io/en/latest/docking_basic.html)
for input preparation and search settings.

## Optional GNINA CNN Rescoring

GNINA is a Vina-derived docking program with CNN-based scoring. The workbench
does not put its roughly 2.06 GB executable in the base image. On first use,
install the pinned GNINA v1.3.3 CUDA 12.8 static Linux release to the shared
`cache/gnina/` volume; the installer checks the published asset size and a
pinned SHA-256 before making it executable. The workbench and research images
share the CUDA 12.8/cuDNN runtime expected by that release; docking still runs
CPU-only through this bounded interface:

```bash
docker compose exec workbench regen install-gnina
```

This cache is shared with the MCP service, so no container rebuild is needed.
The MCP tool `regen_dock_gnina` and CLI command `regen dock-gnina` use the same
prepared PDBQT inputs, explicit box, 15-minute limit, provenance and no-overwrite
rules as Vina. They run CPU-only, default to GNINA's faster `rescore` mode, and
write SDF so CNNscore/CNNaffinity properties are retained with poses. The
bounded interface permits `none` or `rescore`; CNN refinement and all-search
modes are intentionally not exposed because the latter modes cost much more.

```bash
docker compose exec workbench regen dock-gnina \
  data/structures/receptor.pdbqt data/structures/ligand.pdbqt \
  --center_x 10 --center_y 12 --center_z 8 \
  --size_x 20 --size_y 20 --size_z 20 \
  --exhaustiveness 8 --num_modes 9 --cpu 4 --seed 42 \
  --cnn_scoring rescore --out data/structures/gnina-example.sdf
```

GNINA's CNNscore and CNNaffinity are model predictions, not measured binding
affinity. Compare with Vina, inspect poses and contacts, and use known actives,
decoys, and experimental follow-up; rank agreement is only a prioritization
signal. See the [official GNINA project and install guidance](https://github.com/gnina/gnina),
[v1.3.3 release](https://github.com/gnina/gnina/releases/tag/v1.3.3), and
[CNN scoring modes](https://github.com/gnina/gnina#cnn-scoring).

Useful minimum validation for a target campaign: redock a known bound ligand
where available, inspect the pose and contacts, include known actives and
property-matched inactive/decoy controls, retain failures, and report the
whole ranking rather than only the best-scoring compound. Repeat across
relevant receptor conformations or independent scoring methods when possible.

### Local Validation Report

`regen docking-benchmark` and the allowlisted MCP tool
`regen_docking_benchmark` produce a hashed, portable report from a CSV of
existing scores. Provide one row per compound with `compound_id`, `role`,
`score`, and one consistent `method` name (for example `vina_affinity` or
`gnina_CNNscore`). Run separate reports for separate scoring methods. Roles are
`active_control`, `inactive_control`, `decoy`, or `candidate`. Active and
inactive controls must be labelled from an independent experimental assay and
include a `label_source` reference; `assay_id` records the assay context.
Decoys and candidates are kept in the ranking but excluded from primary
control metrics. The report computes ROC AUC and enrichment at 1%, 5%, and 10%
for active/inactive controls, with ties counted as half a win and a warning for
fewer than ten controls in either class. These descriptive metrics have no
confidence interval and small datasets are unstable.

Optional `pose_sdf` and `reference_sdf` columns compare a selected SDF record
to the experimental bound ligand in the same receptor coordinate frame.
`pose_index` and `reference_index` select zero-based records (default 0). The
report verifies exact isomeric molecular identity and computes a
symmetry-aware heavy-atom RMSD without aligning away translation or rotation.
It limits files to 25 MiB and total inputs to 200 MiB, and stores both the
source CSV and content-addressed SDF snapshots. `input.csv` is normalized to
rerun against those snapshots; `manifest.json` hashes every report artifact.

```csv
compound_id,role,score,method,assay_id,label_source,pose_sdf,reference_sdf
known-active-1,active_control,-9.1,vina_affinity,assay-42,https://example.org/assay.csv,,
known-inactive-1,inactive_control,-4.2,vina_affinity,assay-42,https://example.org/assay.csv,,
screen-hit-1,candidate,-8.3,vina_affinity,,,,
```

```bash
regen docking-benchmark data/structures/controls.csv \
  --direction lower --out data/structures/validation-01
```

The input CSV and referenced structures must be local files under `data/` or
`projects/`; result directories must be new and under `data/`. Choose `lower`
for scores where more negative ranks better (such as Vina affinity), and
`higher` for CNNscore-like values. This utility does not parse docking files,
validate assay quality, make inactive labels from decoys, estimate measured
affinity, or establish target engagement, efficacy, safety, or anti-aging
benefit. RDKit is required only when pose/reference columns are used.

## Optional OpenFold3 Preview

OpenFold3 is not replacing AlphaFold 3 in this image: AlphaFold 3 is not
installed here. OpenFold3 is provided as a separate, opt-in Compose profile so
its GPU stack does not inflate or destabilize the base workbench image. The
current upstream inference is explicitly a preview, and feature parity is
still in progress. Non-covalent small-molecule ligands are supported; covalent
ligands and polymeric ligands are listed upstream as coming soon. See the
[OpenFold3 project](https://github.com/aqlaboratory/openfold-3),
[inference documentation](https://openfold-3.readthedocs.io/en/stable/inference.html),
and [installation instructions](https://github.com/aqlaboratory/openfold-3/blob/main/docs/source/Installation.md).

Place a supported OpenFold3 query JSON in `data/structures/`, then run on the
host from the workbench root:

```bash
docker compose --profile openfold3 run --rm openfold3 predict \
  --query-json=/data/structures/query.json \
  --output-dir=/data/structures/openfold3/run-01
```

The default is pinned to the official OpenFold3 v0.4-pixi multi-platform image
manifest (`sha256:85be176dbb1955000423f5f72ce030afd2d68c3248e87418c6bff6084e8f038a`)
to keep runs reproducible; set `OPENFOLD3_IMAGE` intentionally to use another
version or digest. The image is multi-gigabyte. Model parameters are downloaded
on first use and cached in `cache/openfold3/`. See the [official image tags](https://hub.docker.com/r/openfoldconsortium/openfold3/tags).
Upstream lists a CUDA 12.1-or-newer GPU and 32 GB of memory, and reports most
testing on 40 GB A100s; its installation page does not clearly state whether
the 32 GB figure is host RAM or GPU memory ([upstream installation
requirements](https://github.com/aqlaboratory/openfold-3/blob/main/docs/source/Installation.md#pre-requisites)).
This host's NVIDIA RTX 3080 Laptop GPU (16 GiB) was successfully exposed to a
temporary workbench container through the opt-in GPU Compose overlay, but
OpenFold3 inference has not been run and this GPU is below the upstream's
reported memory configuration. The normal workbench container has no GPU
reservation. Use `./scripts/bootstrap.sh --gpu` (or
`./scripts/Bootstrap.ps1 -Gpu`) to opt in to GPU access for supported workloads;
do not assume that this makes OpenFold3 inference viable on a 16 GiB device.
By default, OpenFold3 sends protein sequences to the public ColabFold MSA
server. Use `--use-msa-server=False` with precomputed MSAs or for the no-MSA
mode when that data flow is not appropriate. Results are written under
`data/structures/` and are not exposed through MCP. Keep the query, image
reference/digest, parameters, software version, MSA mode, and output hashes
with any research record.

OpenFold3 and Boltz are alternatives for complex-structure hypotheses. For a
known ligand pocket, use an experimental receptor and a docking engine; do not
interpret co-folded placement as a docking score or measured binding.

### Remote OpenFold3 Options

Checked 2026-10-03. The explicit `regen fold-japanfold` and
`regen fold-nvidia` CLI commands run in a one-off Compose service. Remote model
inference is not exposed through MCP or the research desk.

- **JapanFold (ai& / Tenstorrent):** Its async API lists OpenFold3 and starts
  new accounts with $100 credit and no card. The published rate is
  **$0.26 per processor-hour**, billed for chip time used (queue wait is not
  charged), rather than a fixed price per prediction. The provider does not
  publish an OpenFold3 per-fold example, so actual cost depends on measured job
  time. Important capability caveat: its current `openfold3` model accepts
  protein/RNA/DNA but not small-molecule ligands; `openbind` is the separate
  OpenFold-derived checkpoint that accepts ligands. Its model table reports a
  1664-residue limit in the live `GET /v1/models` response checked on this date
  and describes OpenFold3 as a preview checkpoint. The provider says job files
  are retained for up to 30 days and inputs are not used to train models.
  With MSA enabled, the sequence also goes to an external MSA server; review
  that data flow before submitting private inputs. See [API overview and pricing](https://japanfold.aiand.com/),
  [API workflow](https://japanfold.aiand.com/docs/),
  [model limits](https://japanfold.aiand.com/docs/models-and-limits/), and
  [prediction input and MSA handling](https://docs.japanfold.aiand.com/predictions/).
- **NVIDIA API Catalog:** NVIDIA publishes a hosted OpenFold3 prediction
  endpoint. NVIDIA Developer program members have free NIM API access for
  prototyping, but I found no published per-job rate, quota, or production price.
  This preview is subject to NVIDIA API Trial Terms. NVIDIA's model page says
  trial inputs and outputs may be recorded to provide the trial and improve
  products; do not use it for confidential or personal data without reviewing
  the terms. The hosted service is the lowest-cost first test for public,
  non-sensitive sequences if the account is eligible. See the
  [endpoint reference](https://docs.api.nvidia.com/nim/reference/openfold-openfold3-infer),
  [NIM pricing/access](https://docs.api.nvidia.com/nim/docs/run-anywhere), and
  [model page and trial notice](https://build.nvidia.com/openfold/openfold3).
- **OMTX Om API:** Its public route list includes asynchronous OpenFold3 jobs
  (`POST /v2/hub/openfold3/start`). The authenticated `GET /v2/pricing`
  manifest returns current model prices. The configured account's manifest
  returned **150 cents ($1.50) per OpenFold3 job** on 2026-10-03; treat this as
  a dated account-specific snapshot and recheck before each campaign. See the
  [OpenFold3 route](https://www.omtx.ai/docs/api/hub/routes) and
  [pricing manifest](https://www.omtx.ai/docs/api/pricing).
- **Tamarind Bio:** Its hosted catalog includes OpenFold3 served by NVIDIA
  BioNeMo NIM, and its Free plan advertises 10 jobs/month with access to all
  models. Open API access is listed under Premium, whose price is not public.
  This may be useful for manual trials, but it is not yet a priced API option
  for automated workbench runs. See [OpenFold3](https://app.tamarind.bio/openfold)
  and [plan comparison](https://www.tamarind.bio/pricing).
- **Modal:** A self-hosted OpenFold3 NIM is supported on an L40S. Using
  Modal's published L40S, CPU, and memory rates with NVIDIA's minimum NIM
  allocation (8 physical CPU cores and 64 GiB RAM) gives a rough baseline of
  **$2.84 per billable hour** (about **$0.047 per minute**), before startup,
  model downloads, storage, or any region premium. Modal bills application
  loading and its default 60-second post-request container retention; Starter
  currently includes $30/month compute credit. This is an infrastructure
  estimate for the NIM deployment, not a measured per-prediction cost for the
  upstream `openfoldconsortium/openfold3` image used by this Compose profile.
  NVIDIA's developer-program NIM allowance is for research/development/testing;
  production NIM licensing is separate (NVIDIA currently lists AI Enterprise
  starting at $4,500/GPU/year) and is not included in this estimate.
  See [Modal pricing](https://modal.com/pricing), [NIM requirements](https://docs.nvidia.com/nim/bionemo/openfold3/1.6.0/support-matrix.html),
  and [Modal GPU options](https://modal.com/docs/guide/gpu).

**Recommended order:** for protein/RNA/DNA-only predictions, JapanFold is the
clearest low-cost API to benchmark: it has a $100 starter credit and the lowest
publicly posted compute rate. For an OpenFold3 protein-ligand complex, the
NVIDIA hosted preview is the first zero-price prototype to test if its trial
data terms are acceptable; its API schema supports ligand inputs. If that
preview's terms or account limits are unsuitable, query OMTX's authenticated
price or compare JapanFold's ligand-capable `openbind`/Boltz-2 as different
models. Use Modal when control, reproducibility, or provider limits justify
the higher infrastructure cost. The raw published hourly rates differ by
about 11x between JapanFold and the Modal NIM baseline, but their hardware and
resource units are not equivalent; benchmark actual time, cost, and outputs.
An `NGC_API_KEY` used to pull containers should not be assumed to authorize
NVIDIA API Catalog requests. Keep remote execution opt-in per run: show the
provider, data leaving the machine, and known cost/unknown pricing before
submission; record provider, model/version, input hash, job ID, and result
hashes without recording secrets.

### Remote CLI

From the repository root, these commands use only the configured provider
keys in the ignored host `.env`. Choose a new output directory for each run.
The one-off container has a read-only root and no host Git or Docker socket;
results and provenance remain under gitignored `data/`.

```powershell
docker compose --profile remote-fold run --rm --no-deps remote-fold fold-japanfold submit --input /lab/workbench/examples/mdm2-p53-1ycr.yaml --out /lab/data/structures/openfold3/my-1ycr-japanfold
docker compose --profile remote-fold run --rm --no-deps remote-fold fold-japanfold wait --out /lab/data/structures/openfold3/my-1ycr-japanfold
docker compose --profile remote-fold run --rm --no-deps remote-fold fold-japanfold collect --out /lab/data/structures/openfold3/my-1ycr-japanfold
docker compose --profile remote-fold run --rm --no-deps remote-fold fold-nvidia predict /lab/workbench/examples/openfold3-nvidia-mdm2-p53-1ycr.json --out /lab/data/structures/openfold3/my-1ycr-nvidia
```

Use `fold-japanfold submit --fasta` for a single protein chain and `--input`
for a protein/RNA/DNA complex FASTA or Boltz YAML. JapanFold's default MSA
step sends sequences to an external MSA server; `--no-msa` requests a
single-sequence fold. NVIDIA's hosted API requires an explicit MSA for each
protein/RNA input; the tracked JSON examples supply only the query sequence,
not a homology search. The NVIDIA API may retain trial inputs and outputs.
`regen compare-structures` validates run manifest hashes and reports selected
chain C-alpha RMSD; its optional partner-chain mode measures partner pose and
contact recovery after receptor alignment. It does not estimate binding.

### Public OpenFold3 Benchmarks

On 2026-10-03, we ran two public [RCSB 1UBQ](https://www.rcsb.org/structure/1UBQ)
ubiquitin monomer predictions and two public
[RCSB 1YCR](https://www.rcsb.org/structure/1YCR) MDM2/p53-peptide complex
predictions. Each used one diffusion sample and CIF output. The comparer
verified saved output hashes before measuring coordinates.

| Input | Provider and MSA | Receptor/monomer C-alpha RMSD vs PDB | Partner pose and 8 Angstrom contacts vs PDB |
|---|---|---:|---|
| 1UBQ (76 residues) | JapanFold, MSA depth 9656 | 1.0889 Angstrom (76/76 C-alpha) | Not applicable |
| 1UBQ (76 residues) | NVIDIA, query-only MSA | 0.9860 Angstrom (76/76 C-alpha) | Not applicable |
| 1YCR MDM2 A + p53 B | JapanFold, MSA depth 1202 | 0.7348 Angstrom (85 observed A C-alpha) | B pose 1.7000 Angstrom; 19/28 reference contacts recovered |
| 1YCR MDM2 A + p53 B | NVIDIA, query-only MSA | 8.0160 Angstrom (85 observed A C-alpha) | B pose 26.0104 Angstrom; 1/28 reference contacts recovered |

For 1YCR, the crystal structure has coordinates for 85/109 MDM2 and 13/15
p53 input residues. Comparisons used an explicit 0.75 candidate coverage gate
and exact sequence identity on aligned residues. JapanFold reported ipTM
0.79791; NVIDIA reported ipTM 0.13512. The NVIDIA result does not reproduce
the experimental complex placement in this run. Different MSA inputs are a
major confounder, and both PDB entries were released decades ago and may
overlap model training data. This is an operational benchmark, not a blind
accuracy study or evidence about
age reversal. Neither prediction is a measured interaction or treatment.

The JapanFold 1UBQ job reported 59.0 s runtime and 1.1 s load; the 1YCR job
reported 101.7 s runtime. At $0.26 per processor-hour on one processor, these
suggest approximately $0.00434 and $0.00735, respectively. The API did not
return billed amounts. NVIDIA's trial responses did not include a charge.
Saved structures, comparison reports, and provenance are local in gitignored
`data/structures/openfold3/` and `data/provenance/`. New submissions also save
the exact input and request bytes with hashes; the earlier 1YCR JapanFold run
has a plan input hash matching the tracked public YAML example.

## Tool Availability

The Campaign view in the research desk can group a target hypothesis and link
individual Vina/GNINA runs to it. It accepts one labelled prepared ligand per
run; candidate, active-control, inactive-control and reference-pose roles are
retained, not inferred from scores. Both Ubuntu 22.04 containers install the
`autodock-vina` 1.2.3-2 package and mount the shared GNINA cache; the workbench
has read-write cache access while the research desk mounts it read-only. The
binary version used is recorded by each runner.

| Area | Tool | Status in this setup |
|---|---|---|
| Small-molecule docking | AutoDock Vina | Installed in the workbench; CLI and allowlisted MCP runner available |
| Small-molecule docking | UCSF DOCK, rDock, LeDock | Not installed; no local runner yet |
| Small-molecule docking | SwissDock | Hosted/manual only; no automatic upload or API integration |
| Small-molecule docking | GOLD, Schrödinger Glide, MOE, Discovery Studio/FlexX | External suite/license required; not bundled |
| Protein-protein/peptide docking | HADDOCK, ClusPro, ZDOCK | Hosted/manual workflows; no automatic upload or API integration |
| Protein-protein/peptide docking | RosettaDock | Not installed; requires a separate Rosetta setup |
| AI small-molecule docking | GNINA | Optional pinned binary in shared cache; CPU-only CLI and MCP runner after explicit install |
| AI small-molecule docking | DiffDock | Not installed; separate model environment and weights required |
| Complex structure prediction | OpenFold3 | Optional Compose profile; preview model, not a docking engine |
| Complex structure prediction | Boltz | Optional isolated Python environment; check `boltz --help` |

For hosted or licensed software, verify current access terms, data handling, and
publication/commercial-use conditions before uploading structures or using
outputs. The workbench does not transmit structures to any listed hosted
service automatically. Add additional backends only with a named executable
or API, explicit license/source, bounded inputs and run time, version capture,
and a provenance receipt.
