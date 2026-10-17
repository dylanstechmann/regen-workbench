# Source-derived reconstruction benchmark outputs

All JSON, TSV and SVG outputs here and in `density_sensitivity/` derive from
**Le Luyer M., Coquerelle M., Rottier S., Bayle P. (2016), M3#83,
GLN04-252-ULM2**, [DOI 10.18563/m3.sf.83](https://doi.org/10.18563/m3.sf.83).
They are distributed under
[Creative Commons Attribution-NonCommercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/).
Generic analysis code is separate from this data license.

Associated dataset article:
[DOI 10.18563/m3.2.1.e1](https://doi.org/10.18563/m3.2.1.e1).
Primary biological study:
[DOI 10.1371/journal.pone.0159688](https://doi.org/10.1371/journal.pone.0159688).
We acknowledge **Osteotheque de Pessac, Universite de Bordeaux, France**, and
curator **Dr Stephane Rottier**. Retain the item readme's citation,
acknowledgment and curator-notification terms for any future scientific
article. No curator message or journal submission occurred in this run.

Changes: applied source rigid poses; digitally withheld triangle patches;
fit four fixed local-polynomial baselines to visible support; evaluated
vertical top-envelope errors against the withheld source; repeated at a finer
grid; generated a fixed-case error figure. Raw source meshes are not
redistributed. These outputs do not show regeneration or clinical repair.

`prediction_receipts.json` was written before full-reference evaluation and
contains coefficients, support/query hashes and prediction hashes.
`patch_summary.json` links its pre-evaluation hash and the experiment-plan
hash. Source/plan hashes and all method failures remain part of the record.
Text hashes use canonical UTF-8 with LF newlines, including when plans are
read from a Windows checkout with CRLF newlines. Generated receipts use LF.
The two grids are numerical sensitivity runs on one specimen.

See the [research report](../../MISSING_TOOTH_PATCH_RECONSTRUCTION_REPORT.md)
for representation limits, all-case comparisons and reproduction commands.
