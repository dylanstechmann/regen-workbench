# A separate gingival cohort challenges the age directions

Reviewed and computed 2026-10-19. This advances the persistent goal of durable
youthful tissue function by testing whether previously used transcript panels
retain their age directions in another deposited human cohort. It does not
train an age clock or establish a regeneration target.

**Result:** in source-labelled healthy bulk gingiva from GSE173078, the frozen
structural-ECM panel declines with age, including every specified donor
omission. This agrees in sign with the earlier small bulk reference and
opposes the earlier cell-resolved fibroblast association. Other panel
directions also disagree across references. The new cohort therefore retains
the transport problem; it does not resolve it into one universal oral-age
score.

## Candidate qualification and exclusions

The focused primary-source search used human gingival/PDL aging, healthy
gingival transcriptomes, and donor age/sex terms. It was not an exhaustive
systematic review. New leads were checked against official GEO metadata,
including complete series sample lists, individual characteristics and
supplementary-file declarations. Five GEO families and one primary-paper XML
were actually downloaded, followed by the selected count table and one HGNC
record. All eight fetches have real `regen.record` receipts, byte sizes and
SHA-256 hashes in [source receipts](source_receipts.json).

| Candidate | What is actually available | Disposition |
| --- | --- | --- |
| [GSE173078](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE173078) | 12 healthy, 12 gingivitis and 12 periodontitis participant codes; numeric age, sex and batch per library; 1.20 MB compressed integer gene counts | Selected for a bounded healthy bulk challenge. Healthy donors are 10 women and two men; this is not a sex-balanced reference. |
| [GSE111523](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE111523) | 18 control/previously wounded-side libraries from nine volunteer codes; processed workbook; individual age/sex absent from the retrieved GEO metadata | Defer until author demographics and control-side timing are linked. Eighteen biopsies are not eighteen people. |
| [GSE133603](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE133603) | Four healthy human gingival donors aged 23, 25, 27 and 43; three women/one man; separate APECED and mouse libraries | Insufficient healthy age coverage and donor number for this reference step. Do not use disease/mouse samples to extend human healthy aging. |
| [GSE224044](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE224044) | Three healthy labels and three peri-implantitis labels; no numeric age/sex or formal donor key in the retrieved GEO metadata | Defer demographic/donor linkage; do not recover ages by assuming another analysis's aliases. |
| [GSE312885](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE312885), cited by a 2026 gingival-aging paper | The deposit contains six cultured shIFT88/control bulk libraries without numeric age/sex. The paper's separate single-cell study pools gingiva from similar donors into two young/three aged samples | Exclude as a donor-resolved healthy-age reference. The five pooled single-cell samples cannot become five independent donors, and that age dataset was not located in the cited deposit. |

The pooling statement is in Methods 4.3 of
[Shao et al., Aging Cell 2026](https://doi.org/10.1111/acel.70627); the
accession's actual sample records describe a different experiment. This does
not invalidate the paper's mechanistic experiments, but it prevents the
desired donor-level age reanalysis from those deposited records. No further
single-cell matrices or large raw sequencing files were downloaded.

[The executable metadata qualification](qualify_sources.py) checks unique
GSMs against the official series list, rejects conflicting characteristics,
retains paired volunteer nesting, and writes
[all 81 library records](derived/candidate_geo_samples.tsv) and
[candidate dispositions](derived/candidate_qualification.tsv). No new eligible
human PDL age series was identified in this focused screen. Previously
reviewed GSE83382 and GSE164241 remain historical comparisons, not new
independent inputs.

## The selected cohort and its limits

GSE173078 describes patient-based gingival RNA sequencing with one deposited
RNA library per distinct `AC` participant code. Its 36 count columns map
exactly to 36 GSMs, without pooled expression columns or repeated RNA-seq
biopsies. A related methylation subseries is not extra independent people.
The data were processed against hg19 with STAR and featureCounts and generated
on HiSeq 4000, with processing batches A and B supplied per participant.
[Official design](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE173078),
[example individual age/sex/batch record](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM5259456).

Healthy participant ages are **28, 32, 37, 39, 40, 42, 42, 45, 63, 66, 68 and
75**. The only two healthy men are 32 and 39, both in batch A. The primary
model is therefore the ten healthy women, with age and processing batch as
covariates. The restriction was specified from demographics before computing
panel outcomes. The four frozen models retain all-healthy age only,
all-healthy age/sex/batch, female age only and female age/batch. No older-male
trajectory can be estimated from this sampling.

Within this new cohort, the healthy/periodontitis age-range intersection is
29–75 years, containing 11/12 donors from each group. The male intersection
contains only one healthy and one disease donor. Better overall age-range
overlap does not create sex-matched coverage or remove cohort differences.
These disease samples are inventoried and scored for transparency, but **none
enters the healthy age fits**. See the
[participant manifest](derived/GSE173078_sample_manifest.tsv) and
[common-support table](derived/cohort_common_support.tsv).

Health is the submitter's `Healthy` designation, not an independently
adjudicated diagnosis. Detailed clinical ascertainment, extraction indication,
sampling region, medications and oral exposures are not recovered here.
Participant codes are linked by the source design and titles rather than
externally verified person identifiers. The cohort is separately deposited
from the earlier two workbench inputs; historical cross-study participant
identity overlap cannot be certified from public codes alone. Thus this is a
separate-cohort direction challenge, not validated clinical or population
ground truth.

## Frozen panels and numerical findings

The [primary plan](analysis_plan.json) was written after metadata review and
before the new panel results; it was not independently preregistered. The
25,559 unique supplied gene-count rows were checked for nonnegative integers.
Every feature contributes to each library's denominator. For each unchanged
panel, exact-symbol gene CPM values are transformed by `log1p` and averaged
without expression/age-based gene filtering. Gene counts, normalized values,
panel coverage and all 216 donor-panel scores are retained.

| Fixed panel | Exact genes / specified | Primary slope per decade | Leave-one-woman-out range |
| --- | ---: | ---: | ---: |
| Matrix degradation | 8 / 8 | −0.244 | −0.309 to −0.155 |
| Matrix inhibitors | 3 / 3 | −0.138 | −0.162 to −0.068 |
| Structural ECM | 8 / 8 | −0.246 | −0.311 to −0.101 |
| Inflammation | 8 / 9 | −0.246 | −0.287 to −0.135 |
| Epithelial barrier/identity | 9 / 9 | −0.050 | −0.096 to −0.034 |
| Fibroblast/stromal identity | 9 / 9 | −0.272 | −0.319 to −0.135 |

Units are mean `log1p(CPM)` per ten chronological years. The omission ranges
are sensitivity ranges, not confidence intervals. All six directions remain
negative in each primary donor omission and in each of the four full
model fits. The full twelve-donor age/sex/batch structural-ECM slope is −0.236
(omission range −0.297 to −0.089). These results describe **relative bulk
expression**: they cannot establish an absolute transcript decline, a
cell-intrinsic mechanism, less inflammatory disease, or better/worse barrier
function. Cell mixture and denominator composition can change all these
relative panels together.

The [24 model fits](derived/healthy_age_effects.tsv) and
[132 individual donor omissions](derived/healthy_age_donor_omissions.tsv)
are retained. There are no rank/sample-size failures in these specified
fits; the code retains such states rather than dropping a covariate.

An annotation issue is kept visible. `CXCL8` is absent under the exact symbol,
while the matrix contains its official previous symbol `IL8`. The original
eight-exact-gene inflammation result stays unchanged. A **post-hoc annotation
sensitivity** adds the same prespecified ninth gene through the
[HGNC:6025 previous-symbol record](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:6025),
without selecting features by their outcomes. It requires `CXCL8` absent and
`IL8` uniquely present, and never sums two names into one gene. Its separately
recorded [plan](annotation_sensitivity_plan.json) yields a nine-gene primary
female/batch slope of **−0.282**, with ten donor-omission values from −0.342
to −0.147. The annotation check therefore retains the negative direction.
[All four annotation fits](derived/annotation_sensitivity_age_effects.tsv)
remain labelled post hoc.

## What transferred and what did not

The structural-ECM, inhibitor and stromal-identity directions agree in sign
with the earlier GSE83382 bulk old-versus-young comparison. Degradation,
inflammation and epithelial/barrier directions do not. Against the earlier
GSE164241 selected-cell age associations, structural ECM, stromal identity
and fibroblast inflammation disagree. The
[direction table](derived/direction_transport.tsv) preserves every panel.

These are sign comparisons across different gene coverage, age ranges,
assays, processing and estimands; no effect magnitudes or participants are
pooled. In particular, bulk gingiva and fibroblast-only pseudobulk are
different measurements. Agreement between two bulk datasets does not prove
that the cell-resolved result is incorrect or that raising collagen
transcripts rejuvenates tissue. Conversely, within-cohort donor robustness
does not establish general transportability.

For the restoration/youthful-function program, freeze the panel, annotation
and assay context before selecting a repair candidate. Require independent
tissue-identity, barrier, attachment, mechanics, integration and durability
outcomes alongside molecular measurements. Neither lower relative
inflammation nor higher structural-matrix score can stand in for those
functions. No intervention, organ rejuvenation, tooth restoration, PDL
integration or lifespan effect was tested here.

## Ranked next intake and reproduction

The next useful intake is a cell-resolved healthy cohort with actual
donor-to-cell mapping across older women **and men**, rather than more pooled
age libraries. For this screened set, recovering GSE111523 volunteer
demographics/control timing is the next small public-data task; the
ciliogenesis single-cell study requires the correct deposit and pool
constituents before any donor-level use. For GSE173078, further analysis
requires clinical sampling definitions and additional age-matched male data;
the twelve existing participants cannot supply those missing strata.

From the repository root, using Python with NumPy for the final two commands:

```powershell
python studies/checklist-followup-2026-10-19/aging/fetch_reference_sources.py
python studies/checklist-followup-2026-10-19/aging/qualify_sources.py
python studies/checklist-followup-2026-10-19/aging/analyze_fixed_panels.py
python -m unittest discover -s tests -p test_checklist_followup_aging_reference.py -v
```

The fetch script verifies existing cached bytes, fetches missing sources with
bounded sizes, and checks published source pins on a later download. It does
not create fetch receipts for cache hits. The new twelve tests pass in the
bundled NumPy runtime; they check library/donor nesting, conflicting ages,
healthy-only models, rank failures, exact count-column matching, all-feature
library denominators, duplicates/fractional counts, omission units and
separate primary/post-hoc receipt chains. Docker's workbench service remains
stopped; these checks establish computational consistency, not biological
performance.

[The summary](derived/analysis_summary.json) records software, source receipts,
plan/script/output hashes and limits. New source caches/provenance stay
ignored locally. Only selected public count values, metadata qualification,
original calculations and commentary are published, with primary-source
attribution; source full texts, figures and complete sequencing matrices are
not redistributed.
