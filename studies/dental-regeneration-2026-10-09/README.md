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
| [PDLSC trial 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4761216/) | Controlled intrabony-defect trial; bone height improved in both groups without significant between-group difference | Added-cell benefit and functional oriented attachment not established by that comparison |
| [ASC/PRP trial 2026](https://pubmed.ncbi.nlm.nih.gov/41624073/) | Bone-height advantage over EMD; no significant between-group attachment-gain difference in the abstract; 15 completers of 21 recruited | Attrition, outcome hierarchy and uncertainty require full-text review; nonsignificance is not equivalence |
| [DPSC trial 2025](https://www.nature.com/articles/s41392-025-02320-w) | Abstract reports a bone-defect-depth signal and a post hoc attachment signal in a stage-III subgroup | Subgroup findings are not an overall primary-endpoint confirmation or proof of complete periodontal regeneration |
| [Gingival-recession study 2017](https://pubmed.ncbi.nlm.nih.gov/28620633/) | Small study with 14 cases, multiple sites and a six-month root-coverage signal | Sites are not independent patients; seal/barrier, ligament and whole-tooth outcomes remain separate |

The table is a focused source review, not a meta-analysis. The 2026 ameloblast
paper's publisher full text was accessed. Other entries use indexed abstracts
and the 2016 primary PMC abstract available through the research tools. Source
abstracts remain abstract-limited; their conclusions do not replace inspection
of endpoint-specific between-group results.

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
and seven organoid assessment axes, four dental starters and two organoid/stem-cell
starters. Existing blueprint edits and observations are preserved by the desk's
seed migration. No private notes are published, no experiments are executed and
no source-review signoff by the owner is claimed.

Four source-scoped starting cards are also visible in the dental/organoid desk
areas. The existing 368-test regression suite completed in Docker `dev` with
four optional tests skipped; two new campaign/migration tests passed. The
existing source-card validation passed against the new cards. The long-lived
`workbench` service was not running, so `docker compose exec workbench regen
doctor` could not execute there. The separate research-desk service was running;
it was reloaded only after confirming no active runs, and saved blueprint
content and all five existing notes retained their pre-reload content hash.
This is software and source-scope verification, not biological validation.
