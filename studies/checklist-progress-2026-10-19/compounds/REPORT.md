# Compound checklist: decisions after checking earlier work

Reviewed 2026-10-19. This advances the compound questions in the
[persistent goals](../../restoration-run-plan-2026-10-11/GOALS_AND_CONTINUITY.md),
especially useful tissue function, oral exposure, duration and reproductive
selectivity. No new molecule was generated or tested. The output is an
evidence-linked decision specification, not a human-use protocol.

The useful new result is a **counterexample to equating mitochondrial metabolic
activation with regenerative benefit**. The earlier public compound atlas
already contained substantial identity, oral-delivery and selectivity work.
This report distinguishes those existing results from newly checked details;
the checklist's earlier backlog wording did not describe all that work.

## What advances the earlier work

| Item | Earlier public atlas | This pass | Decision changed or sharpened |
| --- | --- | --- | --- |
| SLU-PP-915 | Exact parent/comparator graphs; mouse oral activity assessed from the abstract | Indexed primary full text, section 3.2/Figure 2, supplies oral half-life and sampling context | Optimize an already orally active mouse reference; require full intact-parent exposure rather than a single concentration |
| MOTS-c and stem cells | Parent/cap identities, K14Q counterexample, CK2/trafficking distinctions and separate trial records | Newly added 2026 human-adipose-MSC study, including contrary and favorable endpoints | Add donor-state and repair-function requirements before ranking a longer-lived or better-delivered version |
| SS-31 | FDA residence-versus-stability distinction; patent process comparator; cell-active comparator panel | Label rechecked; earlier conclusion retained | Compare unchanged-parent delivery/process work separately from covalent changes; require useful intracellular exposure |
| Acetylated Epitalon / Semax / Adamax | Exact cap matrix and bounded identity/evidence distinctions | Scoped searches and Semax primary abstract/metadata rechecked | Keep chemistry identity, demonstrated stability, oral exposure and retained function as separate claims |
| Rapamycin | Human reproductive signal and mechanism/distribution comparison | Human primary abstract rechecked | Retain testicular volume, sperm function and endocrine outcomes separately; complex selectivity alone cannot pass a reproductive endpoint |

The earlier artifacts are read-only references at atlas tree
`af7b57c2cfad64683f82044199cca812a01b9a03`:
[oral decisions](https://github.com/dylanstechmann/geroscience-compound-atlas/blob/af7b57c2cfad64683f82044199cca812a01b9a03/studies/oral-targeting-feasibility-2026-10-09/RESEARCH_DECISIONS.md),
[915 comparators](https://github.com/dylanstechmann/geroscience-compound-atlas/blob/af7b57c2cfad64683f82044199cca812a01b9a03/studies/slu915-oral-comparators-2026-10-09/README.md),
[SS-31 audit](https://github.com/dylanstechmann/geroscience-compound-atlas/blob/af7b57c2cfad64683f82044199cca812a01b9a03/studies/ss31-analog-audit-2026-10-09/README.md),
[peptide transfer](https://github.com/dylanstechmann/geroscience-compound-atlas/blob/af7b57c2cfad64683f82044199cca812a01b9a03/studies/peptide-delivery-transfer-2026-10-09/README.md),
and [rapamycin selectivity](https://github.com/dylanstechmann/geroscience-compound-atlas/blob/af7b57c2cfad64683f82044199cca812a01b9a03/studies/rapamycin-selectivity-2026-10-09/README.md).
No sibling repository was edited, and its structural hypotheses are not
relabelled as optimized drugs.

## 915: use the measured oral reference correctly

The discovery paper identifies **SLU-PP-915 as compound 10s**, a boronic-acid
2,5-disubstituted thiophene. It is chemically distinct from SLU-PP-332. Its
reported microsomal stability above 60 minutes is a bounded in-vitro result,
not a human systemic half-life. [Discovery paper](https://doi.org/10.1016/j.ejmech.2023.115582).

The oral paper reports a plasma half-life of **18–28 minutes after oral gavage
in mice**. Its voluntary oral-suspension dose-response plateaus; the authors
suggest the suspension as a possible explanation. Its repeated-administration
comparison uses concentrations one hour after the first versus final
administration. Equal values there do not constitute complete repeated-dose
AUC profiles. Mouse oral activity was already recorded in the atlas; these
sampling qualifications extend that abstract-only assessment. No numerical
absolute oral bioavailability is extracted here. In particular, this pass
does not verify the online claim of 56% availability. [Primary oral paper,
section 3.2 and Figure 2](https://doi.org/10.1016/j.jpet.2025.103787).

Source inconsistencies remain open: section 3.1's week-long wording differs
from Figure 1's acute wording; section 3.3 describes oral administration while
Figure 3A's caption says intraperitoneal. Do not silently resolve them when
assigning route or timing to observations. The next intake must retain
figure-level contexts, parent-specific analytical methods, complete time
courses and a suitable route reference. Compare dissolution/recovery and
chemical loss before assuming that a structural change addresses the limiting
step. An intraperitoneal comparator alone does not establish absolute oral F.

## MOTS-c: a repair-function requirement with a real failure case

Xing and colleagues studied adipose MSCs from six lean and six obese donors,
then tested untreated or peptide-pretreated cells in a mouse renal-injury
model with six mice per group. Metabolic signaling improved in obese MSCs,
while proliferation and senescence-related outcomes worsened. Renal repair
was not restored; pretreatment also blunted several lean-MSC benefits.
Some outcomes were favorable: the paper reports selected oxygenation changes,
and kidney volume improved across MSC groups. Thus neither “all endpoints
improved” nor “every endpoint worsened” describes the study.
[Primary study, Figures 1–5](https://doi.org/10.1186/s41232-026-00431-7).

This was pharmacological cell pretreatment, not a systemic human or oral
exposure experiment. Small groups, a homogeneous donor cohort, short follow-up
and incomplete donor-to-mouse linkage constrain transfer to other cells,
diseases or exposures. Raw data are available on request, not as a downloaded
donor-level dataset here. No independent reanalysis or clinical adverse-effect
frequency is claimed. This is newly added evidence relative to the five atlas
reports reviewed above, not a claim that the literature was discovered today.

The research inference is concrete: **do not select a MOTS-c delivery variant
solely because AMPK activity, stability or peptide signal increases**. Require
donor-stratified repair function, senescence/inflammatory outcomes and intact
exposure together. The [structured observations](mots_repair_observations.json)
preserve both favorable and contrary domains. Marker activation cannot offset
a failed required repair domain in the [decision cards](decision_cards.json).
This requirement also applies to stem-cell/organoid work, while this particular
adipose-MSC result does not establish a dental-cell result.

## SS-31, capped peptides and reproductive selectivity

The FDA label identifies SS-31/elamipretide as D-Arg-Dmt-Lys-Phe-NH2 and gives
approximately 92% absolute subcutaneous availability, low plasma binding and
urinary elimination of parent plus C-terminal products. Its approved route
does not supply an oral-exposure result. [Label, sections 11–12.3](https://www.accessdata.fda.gov/drugsatfda_docs/label/2025/215244s000lbl.pdf).
The earlier atlas separately read FDA human IV half-lives and in-vitro plasma
stability. That distinction and its manufacturing-process comparison remain
useful; they are not new measurements in this pass. Reducing proteolysis alone
need not fix parent renal clearance or preserve mitochondrial access. Compare
activity at matched free exposure before using residence as a benefit score.

The user’s cap analogy remains a hypothesis to test. A primary Semax study
found that N-acetylation changed metal coordination and lost protection in one
cell-toxicity endpoint. The 2013 stability paper is indexed, but its metadata
has no abstract; no numerical gain is inferred from its title. Neither source
establishes an Adamax result. [Semax primary abstract](https://doi.org/10.1016/j.jinorgbio.2016.08.013),
[stability metadata](https://pubmed.ncbi.nlm.nih.gov/23652441/).
Acetylated Epitalon free acid and acetylated amidate are distinct identities;
an acetate salt is another distinction. The current scoped title/abstract
searches located no Adamax-peptide or acetylated-Epitalon record. Their exact
queries and zero counts are retained in [source receipts](source_receipts.json);
this does not prove the absence of differently named or unindexed research.

Human sirolimus reproductive concerns are supported by a transplant cohort,
not only an animal-to-human conjecture. However, that observational population
does not establish healthy-user risk or testicular shrinkage. Recovery was
not uniform. Preserve volume, endocrine, sperm and recovery endpoints rather
than infer them from mTORC2 sparing. [Human primary abstract](https://doi.org/10.1111/j.1600-6143.2008.02267.x).
The earlier atlas contains the broader mechanism/selectivity comparison; no
fertility-sparing molecule is established here.

## Next computational work, in decision order

1. **915 PK intake.** Obtain an inspectable concentration-time table with route,
   matrix, intact-parent assay, uncertainty and comparison reference. Preserve
   the source timing/route conflicts. A numerical AUC or absolute F remains
   pending; do not fill missing curves with an assumed human half-life.
2. **MOTS-c repair-function intake.** Assemble donor-linked observations and
   matched untreated controls for each required endpoint. Keep metabolic and
   functional measures separate. The presently retrieved figures support a
   failure-case annotation, not fitting a donor-response predictor.
3. **SS-31 delivery/process comparison.** Use the existing exact parent and
   published comparators. Require intact-parent recovery, useful cellular
   exposure, relevant function and independent cost/impurity accounting.
   A new cap is not automatically the most useful first experiment.
4. **Capped Epitalon/Adamax identity gate.** Resolve termini, linkages and
   comparator assays before an oral/duration ranking. Retain the existing
   structural panels without inventing pharmacokinetics for them.
5. **Rapamycin target definition.** Declare which organ benefits must survive
   before comparing distribution strategies. Require reproductive outcomes;
   whole-testis averages and total carrier accumulation are insufficient.

These are engineering priorities, not efficacy or personal-use rankings.
They preserve youthful function as the target without turning a pathway,
clock, registry plan or geometry benchmark into whole-body rejuvenation.

## Access and validation

[Evidence ledger](evidence_ledger.tsv) records identity, population/route,
access mode, measured versus missing claims and continuity status.
Local Europe PMC, ClinicalTrials.gov and full-text XML downloads have real
`regen.record` receipts; their hashes are summarized without redistributing
full texts. The oral-paper extension uses indexed primary full text rather
than an archived author dataset. Native-named MOTS-c and CB4211 registry records
were rechecked and still have no posted results; both are subcutaneous, so
neither establishes oral performance. Docker doctor reported that the
workbench service was not running. Data structure/link validation is reported
to the parent run; no biological experiment was performed.
