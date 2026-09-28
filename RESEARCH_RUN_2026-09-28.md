# Live research campaign: 2026-09-28

Actual API and CPU chemistry runs on a local workstation. Full artifacts
remain local under `data/research-desk/runs/`; IDs below identify folders.

## What ran

57 desk runs: 43 complete, 10 partial and four initial failures. This total
includes 12 new anti-aging-focused searches plus the earlier campaign. Cache
and drawing-library problems were corrected; failures were kept.
OpenAlex and CORE timed out initially, then succeeded on narrower retries. An Exa
site-restricted query returned zero records; a broader follow-up returned
five. Empty results were not converted into invented findings.

All eight search integrations returned records: PubMed, Europe PMC,
OpenAlex, ClinicalTrials.gov, Semantic Scholar, CORE, Brave and Exa. Six
configured API keys were used through their intended services. The current
audit contains 173 records before deduplication; these are not 173 independent
studies. PubChem lookups and UniProt retrieval of human mTOR (`P42345`, 2549
aa) also succeeded.

The artifact audit verified 236 hashes without mismatches. To rerun it:

```powershell
docker compose -f compose.research.yaml exec -T research python /lab/workbench/tools/research_audit.py --out /lab/data/research-desk/campaign-audit.json
```

Saved audit: `data/research-desk/campaign-audit.json`.

## Anti-aging focus: tissue, delivery, sequence damage

The live workspace now opens with **Somatic mutations & genome repair**,
**Engineered tissues & repair**, and **Nanomedicine & tissue delivery**. It
has 10 blueprints and 33 source-reviewed starting cards. Saved blueprint edits
and observations were preserved through the area migration. Epigenetic
reprogramming remains a research lever, but its cell-state effects are not
described as correction of mutated DNA bases.

The [2026 Cell mouse dataset](https://pubmed.ncbi.nlm.nih.gov/42716011/)
reports about 29%, 15% and 39% fewer somatic substitutions under caloric
restriction in liver, kidney and sorted hepatocytes, respectively; the
measured neuron difference was not significant. These reductions are the
authors' published results, not our independent per-sample calculation.
Their two restricted-feeding schedules did not show detectably different
mutation burdens despite previously reported different lifespan effects.
The result supports genome integrity as a modifiable dimension, not a claim
that dietary restriction edits existing damage or explains lifespan alone.
The paper's Table S4 workbook was identified in official PMC metadata, but
PMC served a download challenge and Europe PMC did not expose the supplement;
no per-sample reanalysis or plot is claimed here.

A [single-cell study of six aged human esophagi](https://pubmed.ncbi.nlm.nih.gov/41481786/)
linked NOTCH1 and TP53 mutant clones to different cellular phenotypes. That
is a much sharper target-discovery question than assuming every somatic
mutation is harmful. Known-base correction is technically demonstrated in
[progeria mouse models](https://pubmed.ncbi.nlm.nih.gov/33408413/) and a
[single infant with CPS1 deficiency](https://pubmed.ncbi.nlm.nih.gov/40373211/),
but neither solves the heterogeneous mutation burden of ordinary aging.

For tissue engineering, a [randomized human cartilage trial](https://pubmed.ncbi.nlm.nih.gov/40043142/)
found a 7.27-point adjusted KOOS advantage for mature engineered cartilage
over a less-mature matrix at 24 months in focal knee lesions. A
[23-person intra-patient skin-graft trial](https://pubmed.ncbi.nlm.nih.gov/41890789/)
found better scar scores and much less donor-skin demand, but slower wound
closure (median 60.5 versus 22 days). A
[human engineered-vessel model](https://pubmed.ncbi.nlm.nih.gov/40027545/)
combined HGPS base correction with restored vessel function in vitro. A
[retinal implant study](https://pubmed.ncbi.nlm.nih.gov/34613357/) reached 15
older patients, but its visual signal was not statistically established and
early surgical adverse events matter. These are distinct levels of evidence,
not interchangeable examples of an age-reversing organ transplant.

For nanomedicine, [lung-directed LNPs](https://pubmed.ncbi.nlm.nih.gov/38870301/)
corrected a CFTR base in about half of isolated mouse lung basal stem cells
and restored function in patient-derived airway cells in vitro; whole-lung
editing was lower. The 660-day persistence experiment used a different
reporter model, not long-term CFTR rescue. Two separate
[aged-mouse](https://www.nature.com/articles/s41467-025-67364-6) and
[aged-rat](https://pubmed.ncbi.nlm.nih.gov/42442544/) nanosenolytic studies
reported short-term functional or barrier-marker improvements, with small
groups and no human or lifespan result. Organ accumulation, target-cell
uptake, active cargo and durable function remain separate filters.

New live run IDs:

| Area | Run IDs | Observation |
|---|---|---|
| Somatic mutation mapping | `4d7f54272dda4ff8a7cd55894976a471` | PubMed and OpenAlex returned 10 records; Europe PMC 503, so partial |
| Base editing / engineered vessel | `5ecd9cf82c5b4f628da2cbc7b67291bf` | Exact primary vessel study among six records; Europe PMC 503 |
| Broad engineered tissue | `8cbcd8404ce54eb3b0deb4c9c607e015` | Five OpenAlex leads, mainly reviews; broad PubMed query yielded zero; Europe PMC 503 |
| Broad nanosenolytic delivery | `49db7b71a9f94b43bd27d786d8f5d8bd` | Seven PubMed/OpenAlex leads; Europe PMC 503 |
| Exact cartilage and skin | `ec1cd839d2c0433ca869ccea4b80ddcc`, `3da6c15ccb6c44f5a3d01abc0224bc1f` | Primary human studies retrieved from PubMed |
| Exact brain endothelial and lung LNP | `e093520d3ac445f5bd93eff7857078f1`, `4d88ddb40b594613b6b0ee69d7843b3e` | Primary animal and patient-cell studies retrieved from PubMed |

Four additional PubMed/Europe PMC searches preceded the new areas and returned
39 records before deduplication, covering mutation burden, extrahepatic LNP
delivery, vascularized grafts and senescent-cell targeting. Their IDs are
`a8d83fd2831b4a2196545727493ea9eb`,
`1802c1bbc80f41669a462e03e7451c0a`,
`f8f92b7650f74492936cd29c9076d1bc`, and
`22223f1ebbd2458bb4e0926c304ea563`.

## Broader campaign

Eleven further live jobs searched metformin and training, incretin outcomes,
epithalamin and Epitalon, SARMs, and CRISPR in progeria models. Longer
compound-name queries often returned no relevant PubMed hits; focused
retries produced better records. Some Europe PMC calls returned HTTP 503
and one broad registry query returned HTTP 400; these errors remain in
their run records.

Useful run IDs:

| Topic | Run ID | Result |
|---|---|---|
| Metformin / MASTERS | `2e8e59ff7f24483faac618b80daa5fe0` | PubMed paper and ClinicalTrials.gov registration; Europe PMC unavailable |
| Epitalon and thymalin web leads | `0bffb652a9e24bf09ce3c3dd2a02527d` | 10 Brave/Exa records; includes a telomere cell study, historical peptide reports and vendor material |
| Epithalamin clinical reports | `e20b17f47e15481f87e3a806327aa354` | 5 PubMed records |
| Enobosarm in older adults | `3f8c40038e5f47358cde593f8f0c17a9` | Exact phase II trial record |
| Retatrutide phase III | `3fcc839416f94dd68b31ffd0eb02bc89` | Published TRANSCEND-T2D-1 paper among 5 records |
| CRISPR in progeria | `2049e12d420349048a2474d4806d5efc` | Four PubMed records including the 2021 base-editing study |
| Progeria bone editing | `53a32113629f44639c40402964c01c41` | September 2026 HGPS mouse bone study |

The blueprints now include these source-reviewed leads. The epithalamin
papers report striking outcomes in small older cohorts but do not establish
that modern vendor Epitalon or Thymalin products are equivalent. A 2025
Epitalon cell study reports telomerase-related changes in normal lines and
telomere extension in breast-cancer lines involving ALT; its figures were
corrected after publication. This is a cell-model question, not an aging
outcome.

The enobosarm phase II trial reported lean-mass and physical-function gains
in older adults over 12 weeks; FDA's current SARM safety page says SARMs
are unapproved and describes serious reported risks. The molecules and
evidence types should stay distinct.

In retatrutide's 40-week phase III trial in adults with type 2 diabetes,
mean weight fell 11.5-15.3% across groups versus 2.6% with placebo. The
published study does not establish muscle gain or cognitive enhancement.

Base editing corrected the known HGPS mutation in mice. A new 2026 study
reports partial bone rescue and sharply lower correction when treatment
occurred later in life. This is a powerful result for one causal mutation
in progeria, while ordinary aging's many mosaic mutations remain a different
targeting and delivery problem.

## Tissue, cognition, and cell-therapy follow-up

Eight earlier follow-up searches ran through the local service. All
completed. Broad uPAR queries returned no PubMed hits; focused organ and
scar queries located primary studies. Exact query runs relevant to the
current anti-aging focus:

| Topic | Run ID | Result |
|---|---|---|
| Senolytic uPAR CAR-T in age-related dysfunction | `8336178bb60342ee81fd7915b79346fa` | PubMed 0; the focused mouse CAR-T lead was already represented by the 2024 card |
| Human-scale kidney graft perfusion | `7940a180aeed4c8f9e4db5f5979b28a4` | PubMed 1, PMID 37388767 |
| Hair follicles in mature scars | `9029f6b3372e4028825f73bdaf1dc89c` | PubMed 1, PMID 36609660 |
| Focused uPAR CAR-T query | `44e3e6108fd54442932823a1ee523947` | PubMed 0 |
| Recellularized kidney filtration | `012b34ea2f5b4c3b80162034753f1d91` | PubMed 1 and Europe PMC 5; includes the 2024 pig filtration paper and 2023 perfusion paper, alongside reviews and unrelated results |
| uPAR-positive tumor ecosystem | `b4fc35d45621415992c2e05ab2210e5d` | PubMed 0 and Europe PMC 5; includes the 2026 Cell oncology paper plus reviews and unrelated CAR-T results |

The 2023 kidney-graft study demonstrated vascular patency, not kidney
function: mean perfusion remained measurable to day 7, but the comparison
with native controls was not statistically significant. The distinct 2024
study seeded human podocytes as well as endothelial cells into decellularized
porcine scaffolds. In heterotopic pig implants, the grafts produced urine
with filtration indices, with the longest observation lasting five hours
in one graft. Tubular epithelial cells were absent, so tubular reabsorption
and full renal function were not tested; the animals' native kidneys remained
in place. The authors disclose that most were or had been employed by
Miromatrix, whose parent company held exclusive rights to the technology.

A three-person human pilot found structural and transcriptional remodeling
after hair follicles were transplanted into mature scalp scars; a separate
split-thickness skin-graft scar was also studied. This is a useful human
regeneration lead, not evidence of scarless healing or a general method for
reversing visible aging.

A separate 2026 uPAR CAR-T oncology paper reports killing both tumor cells
and supportive stroma across preclinical models, including humanized mice.
This is a distinct therapeutic context from senolytic CAR-T work in aged
mice. It raises a tractable target-expression and selectivity question but
does not establish human cancer efficacy or safety for whole-body senescent
cell clearance.

## A useful new hypothesis

A retrieved [June 2026 preprint](https://doi.org/10.64898/2026.06.25.734660)
reports greater glyceraldehyde reactivity for carnosine and balenine than
anserine, homocarnosine and 2-oxocarnosine, with protection in SH-SY5Y cells.
The abstract was available via Europe PMC (`PPR1260452`); full text was not
retrieved. This motivates examining reaction-specific chemistry, conformation
and exposure, not claiming cognitive benefit in people.

Our RDKit calculation illustrates why a bulk-property score is insufficient.
These are neutral PubChem representations, not pH-dependent speciation:

| Compound | PubChem CID | MW | cLogP | TPSA | HBD | HBA |
|---|---:|---:|---:|---:|---:|---:|
| Carnosine | 439224 | 226.236 | -1.130 | 121.10 | 4 | 4 |
| Anserine | 112072 | 240.263 | -1.119 | 110.24 | 3 | 4 |
| Homocarnosine | 10243361 | 240.263 | -0.739 | 121.10 | 4 | 4 |
| Balenine | 10198648 | 240.263 | -1.119 | 110.24 | 3 | 4 |

Anserine and balenine have equal bulk descriptors here but chirality-aware
Morgan similarity of 0.5918. The calculation does not validate the preprint;
it shows these descriptors miss chemical differences relevant to its claim.
Comparison run: `a6a8a604f7bb4f2f9a233a04f765cda9`.

Related [original in-vitro research](https://www.mdpi.com/2673-9623/6/1/15)
reports ROS-related activity for 2-oxocarnosine and sensitivity of apparent
antioxidant activity to trace 2-oxo impurities. A cross-study hypothesis is
that antioxidant and carbonyl-scavenging objectives may favor different
structures. This has not been shown as a clinical tradeoff.

[PMID 42206507](https://pubmed.ncbi.nlm.nih.gov/42206507/) is a review/comment,
despite its title sounding like a new design experiment. It is a lead to
cited original experiments, not evidence of human skin rejuvenation.

## Structural exploration

PubChem's 90% neighbor query returned 12 records including the reference,
anserine and N-acetyl-L-carnosine, plus salts/complexes rejected by the local
connected-molecule computation. PubChem and Morgan similarity use different
fingerprints. Run: `f7001d2ec24e49bc998e75d9e1f043c1`.

Aromatic C-H substitutions produced six carnosine variants. Four passed
MW <= 250, TPSA <= 125 and no PAINS alerts. Two hydroxy variants failed TPSA
(141.33) and remain visible. These exploratory gates do not establish
activity or safety; database novelty and synthesis feasibility were not
checked. Run: `040b23d077df42efb965b5256aca714e`.

ETKDGv3/MMFF94s generated 30 conformers; all converged within 500 iterations.
For carnosine, five conformers with seed 42 gave a minimum of -8.02255
kcal/mol; ten conformers with seed 77 gave -9.02561 kcal/mol. The 1.00307
kcal/mol within-molecule difference demonstrates sampling sensitivity.
Both seed and sample count changed, so their effects are not separated.
These are force-field minima, not free energies, affinities or efficacy.
Solvent, physiological protonation and reaction kinetics were not modeled.

| Molecule / setting | Run ID | Converged |
|---|---|---:|
| Carnosine / seed 42 | `5955479e9deb408a9c32f9906eb424ba` | 5/5 |
| Anserine / seed 42 | `b0778b795526419895e7bce263792a2f` | 5/5 |
| Homocarnosine / seed 42 | `30708cda4a974b52bfcda9fb073d9aa5` | 5/5 |
| Balenine / seed 42 | `e71c0a71165c4f9e8da28e5bc8a04cad` | 5/5 |
| Carnosine / seed 77 | `60af7cbd45a04c91933df927d02deda7` | 10/10 |

Tirzepatide resolved to five records with stereochemical differences. All
were retained as metadata and excluded from small-molecule computation due
to size. The current interface flags ambiguous names and requires an exact
CID for neighbor search when several structures match. No peptide-folding
or affinity result was invented.

## Other evidence distinctions

- [MASTERS](https://pubmed.ncbi.nlm.nih.gov/31557380/) found smaller muscle-mass
  gains during resistance training with metformin in older adults. This
  does not establish the effect in younger healthy adults.
- The [tirzepatide DXA substudy](https://doi.org/10.1111/dom.16275) reported
  fat loss together with lean-mass loss. DXA lean tissue includes water and
  nonmuscle tissue; it is not a direct muscle-anabolism measurement.

## Verification and limits

The standard suite ran 93 tests, with 10 optional chemistry tests skipped
in the generic dev image. The research image passed all 20 research-desk
tests and all 16 existing compute tests, including real RDKit calculations.
Desktop and phone-width browser checks covered navigation, structure images,
constraint filtering, blueprint save, and observation save. Images loaded;
tested text/controls had no horizontal overflow. The service remains at
http://127.0.0.1:8092.

This campaign creates a working research loop and testable questions. It
does not validate a rejuvenation treatment, perform wet-lab work or publish
to a public account. Jina, Firecrawl, ORCID and Modal were not used; the full
folding workbench image was not installed or claimed operational.
