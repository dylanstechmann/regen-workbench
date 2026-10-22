# Oral epithelial thickness, electrical resistance and inert-tracer transport

The published ALI and submerged TR146 model summaries differ **7.54-fold in thickness**, **1.016-fold in TEER**, and **0.577-fold in standard FD20 apparent permeability**. These descriptive ratios show why a gum-restoration assessment needs separate structural and transport endpoints. They do not measure regenerated gingiva or establish equivalence to native tissue.

## Frozen source and calculations

Only the benign measurement summaries in [the primary article, DOI 10.1021/acs.molpharmaceut.4c01186](https://pmc.ncbi.nlm.nih.gov/articles/PMC12135942/) are analyzed: Table 2 physical properties and Table 7 standard, noninfectious FITC-dextran (FD20) transport. Enhancer and infection results are excluded. The broader intake stopped after a source-content processing failure; no additional acquisition followed the scope restriction. Previously fetched but unused responses remain identified in the [retrieval ledger](source_receipts.json); the unused workbook was not opened or extracted.

| Model | Reported TEER, Ω·cm² | Reported thickness, µm |
|---|---:|---:|
| Submerged TR146 | 124 ± 2 | 35 ± 4 |
| ALI TR146 | 126 ± 2 | 264 ± 15 |
| Commercial Hu-Mic | 410 ± 50 | 119 ± 14 |
| Commercial Hu-FT | 351 ± 28 | 1064 ± 107 |

Table 2 labels dispersion as **SEM**, with three replicates per group. Its Hu-Mic/Hu-FT thickness entries were supplied by MatTek. These summaries provide neither donor counts nor an insert-level crosswalk. TR146 models use a human buccal cell line. The article cites a head-and-neck squamous-cell-carcinoma cell-line characterization paper for its origin; that original characterization was not retrieved in this audit. This is not a healthy-donor gingival cohort. The commercial models represent oral microtissue/full-thickness tissue; none is demonstrated here to be restored human junctional gingiva.

The ALI/Submerged thickness ratio is 264/35 = **7.543**. The TEER ratio is 126/124 = **1.016**. Table 7 reports FD20 coefficients of **5.6 × 10⁻⁷** and **9.7 × 10⁻⁷ cm/s**, respectively: their ratio is **0.577**, a **42.27% lower reported coefficient** for ALI. The accompanying measurement caption reports three replicates per group; Table 7 supplies no dispersion for these coefficients. No uncertainty interval or paired effect is calculated.

The Hu-FT/Hu-Mic ratio is **8.941** for total thickness and **0.856** for TEER. Full-thickness tissue includes its underlying matrix; this is not a comparison of epithelial thickness alone. It is not a ranking of clinical suitability.

## Measurement boundaries

- TEER is a resistance-area product. The source subtracts the blank-insert resistance before multiplying by growth area; TR146 inserts have **0.336 cm²** area. Raw resistance and blank measurements are unavailable in this extract, so they cannot be recomputed. TEER does not identify FD20 transport by itself.
- FD20 is fluorescent dextran with average molecular mass **20 kDa**. Its apparent permeability coefficient uses measured flux, area and initial donor concentration. The reported observation times span **1–24 hours**, with serial receiver sampling and replacement. No concentration-time table is used here, so fitting-window and sampling-correction choices cannot be independently refit. No continuous flow rate is inferred.
- The physical-property summaries are not synchronized measurements on identified inserts. The article describes morphology after 30 days, while its supplemented TEER maxima occur on different days for Sub and ALI. Source SEMs cannot supply the missing covariance across thickness, resistance and transport.
- Donor/lot identifiers, paired viability outcomes, native human gingival benchmarks and durability after support withdrawal remain absent. Ratios of aggregate summaries do not create those observations.

## Engineering consequence

The next useful evidence record would link **tissue identity, insert identity and measurement time** to thickness region, resistance, blank, area, tracer identity and transport, plus a separately identified viability endpoint. Those are data requirements, not a fabrication protocol. Without the crosswalk, neither a thick construct nor a favorable electrical reading establishes a complete, stable gingival seal.

## Reproduction

The [factual extract](source_facts.json) contains source locators and retained-byte hash. The [offline analysis](analyze_oral_measurements.py) regenerates [results](results.json) using Python's standard library. The optional [source verifier](verify_source_tables.py) checks only the two selected table sections against the ignored retained HTML. It performs no network request. No script re-enters the stopped source route.

```text
python studies/checklist-engineering-2026-10-22/barrier/analyze_oral_measurements.py
python studies/checklist-engineering-2026-10-22/barrier/verify_source_tables.py
python -m unittest discover -s tests -p test_checklist_engineering_barrier.py -v
```

The workbench container was not running when checked. This package is descriptive source-summary computation, not a biological experiment or a clinical protocol.
