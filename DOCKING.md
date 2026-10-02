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
