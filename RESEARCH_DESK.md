# Research desk

This interface implements the expanded [research direction](RESEARCH_PHILOSOPHY.md).
It is a local, working research workspace, with optional API integrations and
bounded CPU chemistry. It does not require a hosted LLM, GPU, or the full
workbench image. The existing methods repositories remain independent.

## Start and stop

```powershell
docker compose -f compose.research.yaml up -d --build
docker compose -f compose.research.yaml down
```

Open http://127.0.0.1:8092. If that port is occupied, set `RESEARCH_PORT=8093`
in your shell before starting and use that port. Only the host loopback
interface is published. The browser and server enforce same-origin JSON
writes. The service cannot run shell commands supplied by a browser and
does not fetch arbitrary submitted URLs. Source URLs on observations are
stored as citations, not silently scraped.

## Working views

The default order now opens with **Somatic mutations & genome repair**,
**Engineered tissues & repair**, and **Nanomedicine & tissue delivery**. The
source-reviewed cards include human cartilage and skin repair trials, an
engineered progeria vessel model, age-related mutation maps, and targeted
delivery studies. They are curated context, not outputs of a newly run model.
Adding new default areas on restart preserves saved blueprint changes and
observations; existing areas are reordered without overwriting their fields.

**Artificial wombs & ectogenesis** adds a separate developmental-bioengineering
area after replacement organs. It preserves complete IVF-to-birth gestation as
a theoretical ambition while tracking the actual species and developmental
interval of each source. Starter campaigns cover capability gaps and growth
comparisons during partial fetal support, including a source with impaired
growth despite physiological maintenance. The sibling `artificial-womb-models`
repository supplies the evidence ledger and dimensionless engineering fixtures.
Use ordinary source searches, typed campaign observations and dossier exports
to investigate it; these tools do not operate a biological-support device.

The ectogenesis area also has a **Model bench** view. The ResearchDesk Compose
service receives only `../artificial-womb-models/artifacts/`, mounted
read-only. The view checks each bundle's receipt, source binding, output sizes
and SHA-256 before displaying report/runtime provenance and the report's own
limitations. It shows reviewed evidence-map bundles, dimensionless exchange
runs and noise-aware forward identifiability reports. Evidence-map cards show
structured claim intervals only after checking their axis, exact unit and
bounds against linked source records. They also show stage-transition edges,
same-unit continuity state, linked source locators and the observation needed
to test each gap. The desk checks these curated bindings and source class but
does not verify publication transcription or infer a complete IVF-to-birth
path. Forecast cards compare
later readings with a last-reading baseline; endpoint-based integral-balance
residuals remain separately labeled as same-run consistency checks. The bounded
cadence/noise/fault/event-timing sweep filters a compact 3×3 design matrix by
profile and metric, including prospective forecast error, baseline error,
approximate interval coverage/width, and legacy residual or conditioning metrics.
Seeded runs share one fixture, so these are software sensitivity results. The
bridge also displays two-compartment transport and Kelvin–Voigt theory bundles
beside their simpler alternative equations. All values remain dimensionless;
developmental tags do not calibrate a model to a species. A receipt establishes
integrity of generated bundle files only. Observation-intake reports separately
show whether local source bytes matched declared hashes, and Model bench checks
that the file-level table agrees with the displayed counts. Those source files
are not copied into or verified by the bundle receipt. The model source and
configurations are not mounted; only
receipt-listed files inside recognized bundles can be opened through the UI.
It displays step-halving error curves from `verify-transport` against the
bundle's closed-form dimensionless reference, including actual steps, errors
and observed order. It also verifies `verify-mechanics` bundles and shows
pointwise plus load-boundary errors against the piecewise-load convolution
reference. The mechanics solver already uses exact transitions, so that report
is a consistency check rather than a discretization study. Neither report is
biological model validation. `verify-transport-matrix` adds seven deterministic
rate regimes, including a near-degenerate weak-coupling case, with their exact
hashed configurations, five-level convergence curves and separate finest-step
errors; the view compares rates, stability
products and finest-level errors. Those profiles are software stress cases,
not biological parameter estimates.
When two verified design sweeps use the same input hash and exact same design
coordinates, the bench can show their reported medians side by side and the
descriptive B−A difference. Missing metrics remain missing, estimable replicate
counts stay visible, and implementation-hash changes are flagged. The comparison
does not pool runs or rank models, and it carries no biological interpretation.
Each compatible view can be downloaded as JSON with its report IDs, versions,
input hash, comparison metric, per-condition values, missingness and deltas.

- **Evidence:** PubMed, Europe PMC, OpenAlex, ClinicalTrials.gov, Semantic
  Scholar, CORE, Brave and Exa. Select sources and request 1-10 results each.
  Bibliographic metadata is unreviewed until assessed. Registered/completed
  trials are not assumed to have positive results. Web hits remain leads.
  The display deduplicates DOI/PMID/exact-title matches where possible;
  original provider records remain in the run. This is not an exhaustive
  systematic search or a count of independent replications.
- **Claims and observations:** Record papers, preprints, anecdotes, vendor
  claims and personal observations, with population, direction, confounders
  and source URL. All start unreviewed. The interface does not infer efficacy
  from a forum vote count, repeat mention or product claim.
- **Molecules:** Resolve a PubChem name or CID, retrieve structural neighbors,
  compare a submitted SMILES variant, enumerate a bounded set of single
  aromatic C-H substitutions, and sample conformers. Images are real RDKit
  depictions, not generated scientific illustrations.
- **Campaign:** Keep one target hypothesis, species/tissue, endpoint and
  falsifier together with linked search and chemistry runs. Optional Vina or
  GNINA docking runs accept one labelled candidate, known-active, known-inactive
  or bound-reference ligand at a time. Prepared receptor and ligand files must
  be under `data/structures/`; campaign records also retain the search box and
  preparation notes. Pose files, copied inputs, settings and hashes are
  downloadable with each run. The CLI/MCP `regen docking-benchmark` report
  evaluates score ranking on labelled active/inactive controls and optionally
  computes no-alignment, symmetry-aware pose RMSD against a native reference.
  Decoys are excluded from primary metrics; small control sets remain unstable.
  Campaign evidence has an axis summary plus multiple source observation rows.
  Each row retains its own source, species, stage or model track, developmental
  interval, endpoint, comparator, reported value/unit, independent unit, reported
  sample size, follow-up, status, interpretation, license and optional dataset
  hash. These are citations and transcribed metadata; ResearchDesk does not pool
  values or infer effects across studies.
- **Blueprint:** Editable question, population, mechanism, tissue, time,
  rationale, computational approach, falsifier and desired changes.
- **Runs:** Persistent status, exact parameters, raw response snapshots
  reserialized with secrets removed, calculated results and SHA-256 manifests.
  Individual provider failures yield partial results. Interruptions and
  failures remain visible. History is paginated across all runs for the current
  blueprint. Exports include all persisted runs and their available artifacts.
- **Experiments:** discover `experiment.json` records beneath `studies/`, validate
  each against the shared schema and declared local artifact hashes, then display
  its question, model system, independent-unit metadata, assay endpoint/units,
  assay availability, six outcome-domain statuses, descriptive group summaries, author-reported
  analyses separately from local outputs, bounded CSV observations, calibration,
  falsifier and recorded limitations. Missing identifiers stay visible as
  “Not reported.”
  Only artifacts declared by a currently valid local manifest can be opened,
  and previews are limited to 20 MB. Schema 1.4 adds species/stage/interval
  context and immutable analysis-run history with one current pointer per kind.
  Re-importing a receipt appends a run and keeps earlier output records. A passed donor-validation status now also
  requires a linked held-out analysis result, a linked analysis specification,
  and a stated success criterion under manifest schema 1.2. Schema 1.3 adds
  measured/planned/unavailable assay status; measured assays require a linked
  data artifact, while an unavailable endpoint can be represented without a
  fabricated raw-data link. The kidney tubuloid cyst-induction card preserves
  its 280-image inventory, zero-mask receipt and treatment-concealed annotation
  worklist as distinct runs. Morphology remains unavailable until masks and
  object identities are reviewed. These links make
  evidence inspectable; the validator does not infer that an analysis or
  scientific criterion is sound.

  To register a run from the sibling `organoid-phenotyping` package, call
  `python tools/import_organoid_phenotyping.py --output PATH --manifest PATH
  --plan PATH` with the exact package output and the exact acquisition manifest
  and study plan used for that run. The adapter checks all three input hashes,
  the output hashes and split receipt, then copies only bounded CSV/JSON/Markdown
  outputs into the study folder. It does not copy raw images or overlays and
  does not mark a cyst assay as measured merely because mask geometry exists.

  The sibling package can also prepare a treatment-concealed 24-hour annotation
  worklist with one image per available development kidney × culture × treatment
  stratum and five hidden repeat assignments. To register its public queues,
  provisional protocol, plan, and low-resolution contact sheet, run from this
  repository:

  ```powershell
  python tools/import_organoid_annotation_pilot.py `
    --output ..\organoid-phenotyping\artifacts\annotation-pilot-bonn-cyst-24h-v1 `
    --manifest ..\organoid-phenotyping\artifacts\bonn-kidney-cyst-induction\acquisitions.csv `
    --plan ..\organoid-phenotyping\artifacts\bonn-kidney-cyst-induction\study-plan.json
  ```

  The import verifies the source frame hashes, private key, queue fields, and
  frozen final-test exclusion. It copies only those five public artifacts; the
  full-resolution source images and the unblinding key stay in the sibling
  package. ResearchDesk describes this as a worklist, not a completed mask
  assay or biological result. Visible morphology may still reveal treatment.

  The sibling package's `annotate` command opens a loopback-only polygon workbench
  for human mask creation. It preserves blinded task IDs, image hashes, protocol
  version, and pseudonymous annotator IDs. Once reviewers finish, run
  `organoid-phenotyping audit-annotations --session SESSION_PATH`; the local
  audit computes foreground Dice only for concealed repeats and writes a new
  annotated acquisition manifest only when every primary task has a mask.
  Register the audit summary in ResearchDesk with:

  ```powershell
  python tools/import_organoid_annotation_review.py `
    --audit ..\organoid-phenotyping\artifacts\bonn-kidney-cyst-induction\annotation-session-v1\audits\AUDIT_ID
  ```

  This import verifies receipt hashes and appends report, agreement table and
  receipt as an `annotation_review` run; it does not import masks, treatment
  labels, or biological outcomes. To calculate image geometry after mask
  review, run the package's `measure` command against the newly written
  `acquisitions-annotated-*.csv` and register that separate package receipt.
  Agreement, geometry, and treatment response remain distinct evidence stages.

  Imported organoid outputs under `studies/organoid/**/derived/` retain their
  exact receipt-bound bytes through Git checkout; their original line endings
  must not be reformatted. Editable source and documentation use the repository's
  normal LF policy.

- **Study design:** save immutable JSON revisions for a research question with
  competing hypotheses, a source-scoped dataset card, and an analysis plan
  linked to exact question/card revision IDs. Each revision records a canonical
  SHA-256; edits append a new revision, and plans show when linked inputs have
  since changed. Dataset cards capture access and license claims, file names
  and optional declared hashes, species/model and interval, data granularity, unit
  hierarchy, measured endpoints and units, calibration state, groups,
  missingness and exclusions. A generated gap list describes absent metadata;
  it does not certify eligibility. Plans require alternatives, a primary
  outcome, comparator, independent unit, baseline, split, uncertainty,
  confounding, falsification and ambiguity rules. Plans remain drafts and do not
  run analyses. Hashes on Study design dataset-card drafts remain user-supplied
  metadata; this view does not check them against external file bytes. The
  sibling observation-intake command has a separate optional local-byte check.
  Citations are stored but never fetched. Reviewer
  identity is not authenticated. Dossier exports include the exact revisions
  and their hashes. Source-observation review decisions and binding revisions
  to jobs submitted through the Desk remain future work; the frozen-evaluation
  records below bind a plan to a sibling receipt instead.

- **Frozen evaluation:** three more append-only record types sit on a saved
  analysis plan and are never edited or superseded (a changed plan needs a new
  freeze). A *plan freeze* pins the plan, question and dataset-card revisions
  by ID and content hash, a method (owner repository, 40-character commit, entry
  point, preprocessing, parameters) and a split naming its grouping unit,
  development groups and sealed final-test groups. The Desk hashes the split,
  stamps its own clock and derives a status: `retrospective` when the person
  attests that results were inspected first; `confirmatory` only when the plan is
  marked `proposed_confirmatory`, final-test groups are sealed, every pinned
  dataset file has a SHA-256, the method has a commit, and the grouping unit is
  an identified independent-unit level of a pinned dataset card; otherwise
  `exploratory`, with the blockers listed. A *holdout access* event appends to a
  SHA-256 hash-chained ledger bound to that freeze (scope development or final
  test; evaluate, tune, inspect labels or export predictions;
  `expected_previous_event_sha256` rejects a write that would fork the chain). An
  *evaluation binding* reads one receipt once (a regular `.json` file of at most
  4 MiB under `data/`, `studies/` or `projects/`, never through a symlink)
  through a registered adapter, `regenbench-metrics/1` for regen-benchmark-kit
  metrics or the generic `regen-workbench/evaluation-receipt/1`, and checks
  pinned inputs, split agreement, whether a sealed group was in training,
  producer-reported overlap, the method revision and whether the result postdates
  the freeze. Its status is `mismatch`, `unverifiable`, `bound_retrospective`,
  `bound_timing_unverified` or `bound_prospective`. A claim state is recomputed
  on every read: `holdout_sealed`, `single_final_evaluation_recorded`,
  `holdout_reused_not_independent`, `holdout_compromised`,
  `ledger_integrity_failed`, `exploratory_only` or
  `retrospective_not_confirmatory`, shown beside whether each pinned revision
  has since been superseded. "The record supports a confirmatory claim" means
  only that the recorded procedure was followed. The freeze clock, the "results
  inspected before the freeze" answer, ledger actors and receipts are
  self-reported or unauthenticated, and access that was never recorded cannot be
  detected except where a bound receipt reveals it. A binding shows that a
  receipt agrees with a plan, not that the analysis was correct, the receipt
  genuine, or a biological claim true. Nothing named in a record is executed,
  and no model is run. A leave-one-group-out receipt cannot be a confirmatory
  evaluation of any one group; the committed
  [worked example](studies/frozen-evaluation-example/) shows that on the NIST
  iPSC benchmark. Dossier exports include these records, and
  `tools/verify_dossier.py` re-checks hashes, pins, ledger chains and claim states
  as the separate `scientific_lineage` status.

Export downloads a ZIP with dossier JSON, immutable research-record JSON, a
research summary, a discussion draft, run snapshots, manifests and an artifact index. Campaign-linked
experiments contribute their freshly validated manifest and local analysis
outputs; linked artificial-womb bundles contribute their receipt and
hash-matched outputs. One bounded collector (`tools/archive_collector.py`)
gathers every entry, generated or copied, under the same rules: safe canonical
relative names, no duplicates (including names differing only by letter case),
20 MB per file, 20,000 members, and a 98 MB uncompressed budget that includes
the reproduction plan and the index. Each run-folder file is read once, never
through a symbolic link or reparse point, and the inventory hash is of exactly
the bytes archived. A run file that is a symbolic link, a special file, over the
per-file limit, or changed while it was being read is left out and listed under
`excluded` in `archive-index.json` with its reason (`complete` becomes false);
`verify_dossier.py` warns on such an archive and fails it under `--strict`. A
run folder with too many files, or a total over budget, refuses the export with
a message instead. The 98 MB budget leaves headroom under the verifier's
100 MB limit, and the written ZIP is checked against that limit too. The
filesystem check cannot detect a same-size rewrite on a filesystem with coarse
modification times. Reading the run list itself (`export`) and the
experiment-manifest validator's own reads are outside this collector. Manually entered notes
are excluded by default; an explicit option includes them. It does not publish
to Reddit or GitHub. Review private details and evidence claims; an exported
research dossier is not automatically anonymous.

## What the chemistry actually computes

RDKit 2026.3.6 computes molecular weight, cLogP, TPSA, donors/acceptors,
rotatable bonds, PAINS alerts and unspecified stereocenters. Local similarity
uses chirality-aware Morgan radius 2 / 2048-bit fingerprints. PubChem neighbor
search uses PubChem's different fingerprint implementation; the two scores
must not be equated.

Analog enumeration substitutes a single fluoro, methyl or hydroxy group at
eligible aromatic C-H sites and sanitizes/deduplicates products with RDKit.
It retains up to 18 variants and marks MW/TPSA/PAINS constraint failures
instead of silently discarding them. This small operator is not a universal
molecular generator. Existing database identity, synthesis feasibility,
stability and biological activity of the generated graphs are unverified.
No aromatic C-H means no variants from this operator. User-submitted
structures can still be compared.

The conformer view wraps the existing `regen_compute.compound_screen`:
ETKDGv3, MMFF94s, fixed recorded random seed, one thread and 500 iterations.
It exposes convergence and within-molecule relative energies, and saves SDF
coordinates plus the original input. It does not calculate reaction rates,
receptor affinity, ADMET, clinical benefit, molecular dynamics or whole-body
age reversal. Absolute force-field energies must not rank different molecules.

Compute inputs must be connected molecules with at most 100 heavy atoms;
the existing conformer engine also caps atoms including hydrogens at 300.
Large peptides such as tirzepatide can be resolved as database records but
are not forced through this small-molecule workflow. PubChem stereochemical
SMILES are retained, and unresolved stereochemistry is visible.

## Target Campaigns and Docking

The Campaign view organizes a specific target or mechanism with its species,
cell/tissue, causal hypothesis, functional endpoint and falsifier. Campaigns
belong to one research blueprint. Searches and chemistry jobs started while a
campaign is selected are attached to it. Docking is optional: the research
image provides Debian-packaged AutoDock Vina and mounts the shared
`cache/gnina/` directory read-only. GNINA is available only after its pinned
binary has been installed into that cache.

Docking accepts only existing `.pdbqt` files under `data/structures/`, limits
files to 25 MiB, fixes GNINA to CNN rescoring, and routes through the same
bounded workbench runner used by the CLI. No browser-supplied executable or
arbitrary shell command is run. The runner retains prepared inputs, output
poses, settings and SHA-256 provenance. Structure preparation, pocket
selection, protonation, cofactors/metals/waters and pose symmetry still require
human review. Use the separate `regen docking-benchmark` CLI/MCP operation for
labelled-control ranking and symmetry-aware redocking RMSD. Vina and GNINA are
related approaches, so agreement is not independent confirmation. Neither
score demonstrates binding, senolysis, mutation correction, tissue repair or
an anti-aging effect.

## Credentials and integration scope

The service forwards only these `.env` values: `EMAIL`, `NCBI_API_KEY`,
`OPENALEX_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `CORE_API_KEY`,
`BRAVE_SEARCH_API_KEY`, and `EXA_API_KEY`. PubChem, Europe PMC and the trial
registry need no API key. A configured key is not proof that the key works;
each run records actual provider success/failure. Selecting commercial web
providers can consume credits on the existing account; queries are capped
and no recurring campaign runs automatically.

Jina, Firecrawl, ORCID and Modal credentials in the private configuration are
not used by this interface. They have different jobs (page extraction,
identity, remote compute), and are not needed for the current run. The full
workbench's existing UniProt/ChEMBL/structure tools remain available separately.

No credentials are copied into source, generated images, browser state or
the Docker build context. Raw request URLs/headers and upstream exception
messages are not exposed. Saved response JSON redacts configured credentials
and contact email if a provider echoes them; hashes identify that saved
snapshot, not the original wire bytes.

## Scripted runs

With the server running, supply a JSON request file to the same queue:

```powershell
python tools/regen_desk.py run --request examples/research-search.json
```

The CLI is a client of the running service; it does not create a second
writer over the saved workspace. All completed runs contain `parameters.json`
that can be submitted again. The new run gets a new ID and keeps the old one.

## Validation

The standard-library suite runs in the shared dev container. Chemistry tests
also need RDKit and its drawing libraries; run them in the research image:

```powershell
docker compose -f ../compose.yaml run --rm --no-deps dev python3 -B -m unittest discover -s regen-workbench/tests -q
docker compose -f compose.research.yaml run --rm --no-deps -v "${PWD}/tests:/lab/workbench/tests:ro" research python -B -m unittest discover -s /lab/workbench/tests -p test_regen_desk.py -q
```

Tests cover partial failures, manifest integrity, source-label persistence,
redaction, same-origin writes, artifact paths, blueprint migration, curated
source references, stereochemistry, property gates and real conformer
calculations. The public source-reviewed seed cards
are separate from fetched records, so a starting point is never presented as
a result returned by an API run.

Primary implementation references: [RDKit](https://www.rdkit.org/docs/GettingStartedInPython.html),
[PubChem PUG REST](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest-tutorial),
[OpenAlex authentication](https://help.openalex.org/api/authentication/),
[ClinicalTrials.gov API](https://clinicaltrials.gov/data-api/api),
[Brave web search](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started),
and [Exa search](https://exa.ai/docs/reference/search).
