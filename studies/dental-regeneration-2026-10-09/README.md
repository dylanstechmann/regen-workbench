# Teeth, gums and periodontal attachment — 2026-10-09

This AI-assisted research track defines bioidentical restoration as a collection
of component identities and functions to be evaluated, not a result produced
by this repository. Whole-tooth formation, replacement of an enamel component,
restoration of attachment and gum coverage are separate questions.

## Evidence that changes the next comparison

| Source | Model and observed scope | Gap retained |
|---|---|---|
| [Ikeda 2009](https://pubmed.ncbi.nlm.nih.gov/19666587/) | Functional bioengineered mouse tooth replacement | Adult-human cell source, controlled shape/number and human tooth integration |
| [Anti-USAG-1 2021](https://pubmed.ncbi.nlm.nih.gov/33579703/) | Animal tooth-regeneration signaling precedent | No adult-human acquired-tooth-loss efficacy inferred; tooth number is not full periodontal function |
| [Human ameloblast organoids 2026](https://www.nature.com/articles/s41368-026-00429-4) | Human iPSC organoid maturation and enamel-like material in mouse kidney-capsule grafts | Prismatic architecture, tooth-site bonding, loading and complete organ/attachment integration |
| [iPS-PDL functional study 2026](https://doi.org/10.4012/dmj.2025-235); [feeder-free iPDLSC study 2024](https://doi.org/10.1089/scd.2024.0122) | One study reports selected human iPSC-derived in-vitro responses; another reports marker-positive tissue in an eight-week ectopic mouse graft | One 2026 iPSC line with batch variation; the 2024 abstract omits cell-line and graft denominators; ectopic tissue does not establish oriented tooth-site insertion or load transfer |
| [PDLSC trial 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4761216/) | Controlled intrabony-defect trial; bone height improved in both groups without significant between-group difference | Added-cell benefit and functional oriented attachment not established by that comparison |
| [ASC/PRP trial 2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC12855574/) | Full text: 36-week radiographic bone-height difference 1.905 mm (95% CI 0.383–3.427; p=.0184) vs EMD; no between-group CAL or probing-depth signal | Only 15 treated (9 vs 6), primary endpoint n=8 vs 6; no histology or proof of oriented PDL attachment; clinical attachment is a separate endpoint |
| [DPSC trial 2025](https://www.nature.com/articles/s41392-025-02320-w) | Abstract reports a bone-defect-depth signal and a post hoc attachment signal in a stage-III subgroup | Subgroup findings are not an overall primary-endpoint confirmation or proof of complete periodontal regeneration |
| [Gingival-recession study 2017](https://pubmed.ncbi.nlm.nih.gov/28620633/) | Small study with 14 cases, multiple sites and a six-month root-coverage signal | Sites are not independent patients; seal/barrier, ligament and whole-tooth outcomes remain separate |

The table is a focused source review, not a meta-analysis. The 2026 ameloblast
paper's publisher full text and primary articles for the 2016 PDLSC, 2025 DPSC,
2026 ASC+PRP trial and 2026 iPS-PDL cell-function study were accessed. Other
entries remain abstract-limited;
their conclusions do not replace inspection of endpoint-specific between-group
results.

The subsequent [component and endpoint audit](COMPONENT_GAPS.md) adds focused
full-text review of the 2016 PDLSC, 2025 DPSC and 2026 ASC+PRP sources. Their
retrievals are identified in [fulltext_receipt.json](fulltext_receipt.json);
the official enrollment-flow cross-check is recorded in
[trial_registry_receipt.json](trial_registry_receipt.json). Six typed
observations load with the controlled-periodontal campaign starter, keeping
primary/secondary and post hoc comparisons, clinical attachment, bone height,
safety and outcome-specific follow-up apart.

For the ASC+PRP trial, the official registry reports 16 consented, one withdrew
before treatment, and 15 treated (9 ASC+PRP; 6 EMD). The primary radiographic
analysis includes 8 and 6 at 36 weeks. The article reports no significant
between-group clinical attachment or probing-depth difference at 12, 24 or 36
weeks. It uses the term “therapeutic equivalence,” but the retrieved Methods do
not state an equivalence margin or formal equivalence test. One AE and one SAE
were reported in different ASC+PRP participants; the authors judged both
unrelated to the procedure. The numeric supplement tables were unavailable to
this review, so exact CAL contrasts are not reconstructed. This trial used
expanded adipose-derived cells plus PRP, not PDLSCs, and did not test a whole
tooth or histologic PDL architecture. See [the trial review](ASC_PRP_TRIAL_REVIEW.md)
for the scope and remaining caveats.

The separate [iPS-PDL functional review](IPS_PDL_FUNCTION_REVIEW.md) compares
the 2026 one-line/three-batch in-vitro study with a 2024 feeder-free protocol
and ectopic graft result. A fifth dental starter keeps the cell-source and
ectopic-graft evidence distinct from clinical periodontal comparisons and the
ameloblast-organoid component study.

## Component roadmap

- **Enamel/dentin:** identity, spatial architecture, interface bonding, hardness
  and repeated-load behavior. Calcification alone does not qualify every item.
- **Pulp:** living tissue identity, vascular supply and sensory integration.
- **Cementum–ligament–bone:** oriented attachment, physiological mobility and
  load transfer; distinguish useful ligament integration from ankylosis.
- **Gingiva:** coverage, native-like phenotype, epithelial seal, inflammation
  and recurrence. Appearance and a radiograph cannot supply barrier function.
- **Whole organ:** placement, shape, eruption/occlusion, sensation, host
  integration and durability. A component's positive result cannot fill an
  unmeasured domain.

These are proposed assessment domains. No universal acceptance threshold or
claim of a fabricated tooth is assigned. The first computational comparison
should preserve the source-defined primary endpoint, comparator, patient/animal/
culture hierarchy and uncertainty. A study with teeth or sites nested within
patients cannot acquire more independent patients by counting those sites.

## Organoids and genome-repair interfaces

The 2026 ameloblast source lists GSE307437 and previously published GSE184749.
They are candidate dataset accessions from the source's data-availability
statement, not files downloaded, licensed or donor-qualified by this tranche.
A later expression analysis needs sample, clone, batch and biological-unit
metadata before a held-out test can be defined. Marker expression and mineral
images remain distinct from functional tooth performance.

The follow-up [GEO metadata intake](GEO_QUALIFICATION.md) has now acquired those
two metadata families, with six and nineteen source sample records. It retains
an incomplete factorial comparison, shared cell-line labels, pooling and a
tissue-label conflict. This supersedes the earlier “not downloaded” description
for metadata only; matrices, independent biological units and reuse rights
remain unqualified. No expression or functional analysis was performed.

The subsequent [deposited-count comparison](AMELOBLAST_EXPRESSION.md) now
qualifies the six GSE307437 column labels and performs an explicitly descriptive
CPM comparison using the existing expression tool. It retains low-count and
pseudocount sensitivity, incomplete factorial design and unknown biological
independence. This supersedes the earlier unacquired-matrix statement for that
one table; GSE184749 matrices and functional tooth outcomes remain unassessed.

The next [RNA context and normalization follow-up](RNA_CONTEXT.md) reviews the
actual primary manuscript and selected supplement pages, compares total-count
and PyDESeq2 median-ratio size factors, and adds per-library PCA and panel plots.
It retains unresolved clone-to-library/culture mapping and sparse RNA versus
protein-assay discrepancies. Only normalization is fitted; no dispersion model
or significance tests are run.

[organoid-oxygen-lab](https://github.com/dylanstechmann/organoid-oxygen-lab)
owns numerical transport and source-linked measurement intake. Its homogeneous
sphere is a reduced model, not a validated dental-organoid geometry.
[base-editing-evidence](https://github.com/dylanstechmann/base-editing-evidence)
owns nucleotide-change classification and count-denominator audits. A declared
genetic correction cannot itself supply the missing tooth architecture or
periodontal interface.

## Provenance and desk integration

[fetch_metadata.py](fetch_metadata.py) made a real bounded Europe PMC core
retrieval through `regen.http_json` and `regen.record`. The
[receipt](metadata_receipt.json) retains exact query, IDs, date and response
hash. Full responses and abstracts stay in ignored `data/literature/`; original
provenance stays in ignored `data/provenance/`. The hash identifies the retrieved
response, not independent validation of an interpretation.

[desk_seeds.json](desk_seeds.json) defines the two new desk areas, eight dental
and seven organoid assessment axes, five dental starters and three organoid/stem-cell
starters. Existing blueprint edits and observations are preserved by the desk's
seed migration. No private notes are published, no experiments are executed and
no source-review signoff by the owner is claimed.

Source-scoped starting cards are available in the dental/organoid desk
areas. The latest one-off Docker workbench-image run passed 384 unit tests, with
six optional tests skipped; all five dental/organoid track tests passed. This
checks seed parity and editable endpoint-record round-tripping. The live desk
was restarted after confirming no active runs and now exposes five dental
starters. Its API reports the same saved-campaign and note counts as before
(one campaign, five notes); a pre-reload content-hash request timed out, so exact
saved-content parity was not verified. This is software and source-scope
verification, not biological validation.

The deposited-count continuation reused `regen expression-contrast` for four
descriptive runs: two declared comparisons at two pseudocounts. It verified
the source count and metadata hashes, CPM column totals, study-script hash and
all four method-manifest hashes. The full workbench regression suite passed,
including four new count-qualification/desk-integration fixtures;
the new script and tests passed Ruff. The live `/api/experiments` endpoint
returned two valid cards, and `/api/state` exposed the calculated dataset
observation. The entire saved workspace and all five notes matched the
pre-reload snapshot. No owner note or campaign was created by this analysis.
