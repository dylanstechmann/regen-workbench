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
limitations. It shows
reviewed evidence-map bundles, synthetic exchange runs and dimensionless
identifiability diagnostics. It also displays a bounded cadence/noise/fault/
event-timing sweep with seeded replicates and post-fit synthetic parameter-recovery
summaries and same-run temporal holdout residuals. The holdout fits the first 70%
of usable intervals and scores only later intervals from that generated run;
it is an internal diagnostic, not independent validation. When outages or monitor faults are configured, it includes a reflected
event-timing sensitivity profile that preserves interval lengths; this does not
represent a realistic outage distribution. Sweep bundles expose a design-plan
artifact with actual cadence/noise values and the configured/reflected intervals.
Simulation reports can plot the receipt-checked dimensionless sensor trace,
including scheduled gaps and modeled power states. A matching receipt means
the listed bytes match that receipt; it does not establish the truth of a
claim or the validity of a model. The model source and working configuration
folders are not mounted; only safe, receipt-listed files within recognized
bundle directories can be opened through the local interface.

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
- **Blueprint:** Editable question, population, mechanism, tissue, time,
  rationale, computational approach, falsifier and desired changes.
- **Runs:** Persistent status, exact parameters, raw response snapshots
  reserialized with secrets removed, calculated results and SHA-256 manifests.
  Individual provider failures yield partial results. Interruptions and
  failures remain visible. History is paginated across all runs for the current
  blueprint. Exports include all persisted runs and their available artifacts.
Export downloads a ZIP with dossier JSON, a research summary, a discussion
draft, run snapshots, manifests and an artifact index. Manually entered notes
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
