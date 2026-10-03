# Local computational experiments

These activities implement the priorities in [RESEARCH_PHILOSOPHY.md](RESEARCH_PHILOSOPHY.md).
Both commands work offline, save exact input snapshots, record parameters,
software versions and hashes, and refuse to overwrite an existing report.
The parent of `--out` must already exist. Each input is limited to 25 MiB.
Reports are rolled back on ordinary errors; a killed process or power loss
may leave an incomplete directory. `manifest.json` and the provenance receipt
identify completed outputs.

Run these examples inside the workbench container (`docker compose exec
workbench bash`). Tools, config and examples have read-only mounts under
`/lab/workbench`; results go under `/lab/data`. Existing installations should
run `docker compose up -d workbench` once to apply the new examples mount.
No GPU or API account is needed.

## 1. Explore expression differences and sample sensitivity

```bash
regen expression-contrast \
  --matrix /lab/workbench/examples/exploration/expression.csv \
  --samples /lab/workbench/examples/exploration/samples.csv \
  --reference young --comparison older --pseudocount 1 \
  --out /lab/data/expression-demo
```

The included matrix is **synthetic**, with deliberately stable, changing,
zero, and outlier-driven genes. It is not an aging dataset or a biological
claim. Replace it with your own appropriately normalized expression matrix:

- Matrix CSV: `gene,sample1,sample2,...`; one unique gene ID per row and
  finite, nonnegative, **linear-scale normalized** values. No implicit
  normalization is performed. Raw counts and log-transformed values need
  an appropriate preprocessing workflow before this command.
- Metadata CSV: `sample,group` plus optional `donor_id,batch_id`, with every matrix sample listed once.
  Exactly two groups and at least two sample rows per group, at most 200 samples
  and 50,000 genes. The expression contrast validates the file contract; it
  cannot verify biological independence or how values were normalized. The
  grouped pipeline uses the optional identifiers to keep linked samples out of
  different folds.
- IDs and group labels: 1-128 ASCII letters/digits/`_.:-`, starting with a
  letter, digit, or underscore. Map other identifiers explicitly before use.
- `contrast.csv` / `contrast.json`: group means, sample standard deviations,
  nonzero counts, log2 ratio of means with the selected pseudocount, and
  leave-one-out effect ranges. Positive means higher in `--comparison`.

Try `--pseudocount 0.1` and `--pseudocount 10` in separate output directories.
Inspect genes whose direction changes when one sample is omitted; inspect
low-expression effects that depend on the pseudocount. These ranges are
sensitivity checks, not confidence intervals. No p-values, FDR, significance
calls, batch correction, paired analysis, or covariate adjustment are supplied.
Use an appropriate statistical model for confirmatory differential expression.
For single-cell data, establish donor-level biological replication and a
justified aggregation/normalization strategy first; cells are not independent
donors. Preserve tissue, age, sex, batch, and normalization information with
the source dataset. Expression shifts alone do not establish rejuvenation.

## 2. Explore compound shape and force-field behavior

```bash
regen compound-screen \
  --input /lab/workbench/examples/exploration/compounds.csv \
  --conformers 10 --seed 42 --max-iters 500 \
  --out /lab/data/compound-demo
```

Input CSV has exactly `id,smiles`, with 1-50 unique IDs (same identifier rules
as above). This is a small batch exploration tool. Larger libraries should be
split into tracked batches. The example compounds demonstrate formats and
failure handling; they are not recommended longevity interventions.

For each supported connected molecule (at most 100 heavy atoms / 300 total
atoms after hydrogens), the command computes molecular weight, calculated
logP, TPSA, donor/acceptor counts and rotatable bonds. It then generates
1-20 ETKDGv3 conformers with a recorded seed and one thread, and minimizes
them using MMFF94s (1-2000 iterations). It writes:

- `compounds.csv` / `compounds.json`: descriptors, explicit success/failure
  statuses, convergence counts, per-conformer energies and optimizer codes.
- `compound-NNN.sdf`: every generated conformer, including nonconverged ones
  marked with status. File names are mapped in the JSON/CSV and avoid
  platform-specific identifier collisions.
- Original input, explanatory notes, and a manifest with hashes and versions.

Only finite energies from converged conformers participate in minimum and
relative energy calculations. Compare energies **within the same molecule**;
absolute MMFF energies do not rank different compounds by benefit, affinity,
or stability. Invalid SMILES, salts/disconnected fragments, size limits and
missing MMFF parameters produce explicit status rows. No silently discarded
salt fragments, substituted force field, or hidden ranking is used. A report
can complete with zero usable molecules: always inspect its status column.

Try a second seed and a larger iteration budget. Inspect whether the sampled
low-energy conformers and convergence counts change. View SDF output with
PyMOL or an SDF-capable notebook viewer. Specified stereochemistry is retained;
unspecified stereo elements are counted but not enumerated. Examine
protonation, tautomers, stereochemistry and input identity before downstream
experiments. The same seed and version are useful for reruns, but numerical
results can vary between platforms or RDKit versions.

This workflow performs conformer sampling and minimization. It does not run
molecular dynamics, receptor docking, solvent models, or predict affinity,
toxicity, clinical effects, or rejuvenation. Those require additional models
and validation. The outputs provide structures and diagnostics for subsequent
computational experiments, not conclusions about eternal youth.

Implementation references: [RDKit getting started](https://www.rdkit.org/docs/GettingStartedInPython.html),
[ETKDG parameters](https://www.rdkit.org/docs/source/rdkit.Chem.rdDistGeom.html),
[MMFF optimization and return codes](https://www.rdkit.org/docs/source/rdkit.Chem.rdForceFieldHelpers.html).

## MCP access

`regen_expression_contrast` accepts `matrix`, `samples`, `reference`,
`comparison`, `output`, and optional `pseudocount`.
`regen_compound_screen` accepts `input`, `output`, and optional `conformers`,
`seed`, `max_iters`. Inputs must be under `/lab/data` or `/lab/projects`,
and outputs must be new directories under `/lab/data`. Copy the example CSVs
there when exercising MCP; CLI examples above can read the repository mount.
Both MCP operations have a ten-minute subprocess timeout.

## Frozen cohort

The registered end-to-end check lives in [studies/frozen_cohort/PROTOCOL.md](studies/frozen_cohort/PROTOCOL.md).
It calls `expression-contrast`, then a separate Welch/BH summary, and records
hashes for a later atlas citation. Read the protocol before the report.
Swapped labels and `FLIP_A` are the negative control and the declared failure case.

## Chained pipeline (contrast → senescence scoring → grouped benchmark evaluation)

The `pipeline` subcommand runs a unified, multi-stage workflow in one call:
1. **Stage 1 (Expression Contrast)**: Calculates linear differential fold-changes, non-zero counts, and leave-one-out sensitivity diagnostics.
2. **Stage 2 (Senescence Module Scoring)**: Quantifies control-subtracted scores. `senmayo` is the published 125-gene set; `fridman` and `sasp` are explicitly marked custom, unverified panels. Runs fail below 60% gene-set coverage and never substitute contrast-selected genes for a missing signature.
3. **Stage 3 (Benchmark Evaluation)**: Evaluates predictions in stratified out-of-fold cross-validation. Every fold refits expression-matched controls, score scaling, differential marker selection, and logistic scaling on its training samples only. Samples sharing a `donor_id` or `batch_id` are held together as connected components. If these identifiers are absent, folds are sample-level and biological independence remains unverified. At least two independent components per class are required.
4. **Stage 4 (Provenance Audit)**: Generates a unified `pipeline_manifest.json` and `REPORT.md` cryptographically linking every stage manifest to its upstream inputs and predecessor stage manifests via SHA-256 hashes.

```bash
regen pipeline \
  --matrix data/expression.csv \
  --samples data/samples.csv \
  --reference young \
  --comparison older \
  --gene-set senmayo \
  --out data/pipeline_report
```

The stage 2 whole-dataset module score is descriptive and is not used as a
cross-validation feature; the benchmark recomputes its score inside every
training fold. The SenMayo source paper used GSEA; this pipeline uses a distinct
control-subtracted score. Cross-validation metrics with few donors or batches
are unstable and do not establish external generalization or rejuvenation.

## Development validation

The standard-library suite covers expression math, strict input contracts,
snapshot hashes, failed writes, output preservation, and MCP containment.
Optional tests exercise real RDKit embedding, energies, 3D SDF output,
stereochemistry flags, reproducible seeds, and exclusion of nonconverged
conformers. CI runs the standard suite on Linux/Windows and Python 3.11/3.12,
plus a Linux job with RDKit 2026.3.6. The full scientific image may use a
different RDKit version; every compound report records the version actually used.
