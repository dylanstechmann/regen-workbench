# Gingival age-reference qualification: GSE83382

## Decision

GSE83382 is usable for a small, descriptive **group-level** comparison of young
and older gingival tissue. It is not a reliable gum-age clock, a causal test of
aging, or a cell-specific fibroblast/epithelial reference. The expression
matrix's sample aliases do not match GEO's individual sample titles, so the
expression values cannot be assigned to the six exact ages in the GEO records.
The analysis therefore retains the three replicate values per group and does
not fit an age trend.

The primary study sequenced gingiva from three young people (17–20 years) and
three older people (60 years or older); it reports that participants had no
periodontal disease. The public GEO records list ages 17, 19, 19 and 64, 66, 66,
all recorded as female. The paper's separate qPCR validation used five people
per group; that is not the RNA-seq sample size and is not included in these
calculations. Sources: [Kim et al., PLOS ONE (2016)](https://doi.org/10.1371/journal.pone.0158777),
[GSE83382](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE83382), and
[the GEO record for one older sample](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM2200464).

## Intake and mapping checks

- NCBI GEO's official series metadata and processed matrix were fetched and
  hashed. The matrix has 40,247 RefSeq rows and columns `Young1`, `Young3`,
  `Young4`, `Old1`, `Old2`, and `Old3`.
- GEO's individual records instead use titles `Young rep1–3` and `Old rep1–3`.
  The matrix aliases support a one-to-one group-count match (three per group),
  but no available metadata establishes an individual alias-to-GSM mapping.
  The crosswalk files preserve that uncertainty explicitly.
- GEO says the values are FPKM, quantile-normalized, log2-transformed, and
  median-centered across genes and samples. The analysis uses these values as
  supplied; it does not present them as raw counts or recalculate a count-based
  differential-expression test.
- The table has 23,502 non-placeholder gene symbols, and 7,694 symbols have
  multiple RefSeq rows. Because the values are already transformed, isoform
  values are not summed or averaged into pseudo-gene counts. A fixed-panel gene
  is included in the score only if it maps to exactly one RefSeq feature;
  multi-feature symbols are reported separately.

The machine-readable records are [the GEO sample metadata table](gingival_age_geo_samples.tsv),
[the matrix-to-group map](gingival_age_expression_group_map.tsv), and the
[source/hash intake receipt](gingival_age_intake_receipt.json).

## Fixed exploratory panels

Each panel score is the unweighted mean across its uniquely mapped, preselected
genes for each matrix column, followed by the difference between the old-group
and young-group means. Values are differences on GEO's processed expression
scale; they are not years, clinical effect sizes, or fold changes. `n` is the
number of genes contributing after coverage checks.

| Panel | Genes (`n`) | Old minus young | Reading |
|---|---:|---:|---|
| Matrix degradation | 6 | +0.721 | Higher in the older group; two older replicates are higher than the third. |
| Matrix inhibitors | 3 | −1.982 | Lower in the older group. |
| Structural ECM | 6 | −3.312 | Lower in the older group. |
| Inflammatory markers | 8 | +0.711 | Higher in the older group. |
| Epithelial/barrier identity | 8 | +0.749 | Higher in the older group; bulk cell mixture can change this score. |
| Fibroblast/stromal identity | 8 | −2.752 | Lower in the older group; this is not a fibroblast-purified assay. |

At the single-feature level, MMP3, MMP9, MMP12, and MMP13 are higher in the old
group by +1.232, +1.036, +1.714, and +1.404 processed units, respectively.
MMP8 is nearly unchanged (+0.008), and MMP27 is lower (−1.069). IL1B and IL1A
are higher (+1.557 and +1.579); IL6 and TNF are nearly unchanged (+0.149 and
+0.034). These directions are consistent with the original paper's reported
MMP pattern, but the panel-wide inflammatory signal also makes it unsafe to
call the matrix changes a clean intrinsic rejuvenation target. The original
paper likewise distinguishes the MMP12 signal from several MMP/inflammatory
signals it links to external stimulation.

## Interpretation and next experiment

This small cohort gives an oral-tissue-specific warning for the broader aging
project: matrix turnover, matrix inhibitors, stromal markers, epithelial
markers, and inflammation do not move as one “biological age” axis. Bulk
gingiva cannot distinguish a changed cell mixture from a cell-intrinsic state,
and the study cannot separate age from unmeasured donor, site, or exposure
differences. Its all-female sample makes sex-specific transfer especially
uncertain. None of these transcript summaries measures a healthy epithelial
seal, gingival recession, PDL attachment, mechanical stability, or gum
regeneration.

The donor/library qualification for the oral-cell atlas is now recorded in the
[GSE164241 audit](ORAL_ATLAS_DONOR_QUALIFICATION.md). It identifies repeated
periodontitis sample-code groups and a post-publication GEO addition, so any
follow-up must aggregate at the apparent donor level and separate tissue site
and pipeline version. The next analysis is a cell-resolved disease-state
challenge for these fixed panels, with age and cell-composition alternatives
reported separately. Any regenerative claim still needs barrier, matrix,
vascular, immune, and tooth-support function measured together.

## Reproduction

Run from the repository root:

```powershell
python studies/aging-state-2026-10-11/fetch_gingival_age_reference.py
python studies/aging-state-2026-10-11/analyze_gingival_age_reference.py
```

The fetched source files remain in ignored local literature storage. Tracked
outputs are in `derived/gingival-age-reference-GSE83382/`: gene-level summary,
feature-level contrasts for multi-RefSeq symbols, panel coverage, per-sample
panel scores, and an analysis summary with source checksums.
