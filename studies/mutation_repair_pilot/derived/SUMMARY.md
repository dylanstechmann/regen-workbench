# Mutation-repair pilot: reproducible descriptive tables

These are aggregate summaries of public supplementary workbooks. They are not per-cell mutation burdens, causal repair targets, or evidence of rejuvenation.

- Body-map coding calls: 66,188 rows in 1,731 samples; 18,246 liver rows.
- Skin panel: 5,214 calls joined one-to-one to 123 donor records; median 27 calls per donor.
- NanoSeq mutation rows: oral 341,620; blood 75,377. No participant identifiers are present in these public tables.
- Body-map driver-enrichment tests: 288 gene-tissue tests; BH adjustment is computed across the full table.

The skin model uses explicit categorical dummy variables and ordinary least squares. Bootstrap intervals resample donors within each phototype in sorted order using one NumPy generator with fixed seed 12345. Differences from the manuscript can arise from spreadsheet coercion, formula choices or study-specific analysis code.

A mutation or expanding clone is not automatically harmful. These tables contain no intervention that corrects ordinary age-acquired variants and restores tissue function.
