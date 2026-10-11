# Area-normalized PDL strength: source audit

## Finding

Komatsu et al. report that the day-21 PDGF-BB group reached approximately 76%
of control mechanical strength, while giving 2.45 and 3.39 N/mm² for the treated
and control groups. Those displayed strengths divide to 72.27%. The official
supplement confirms both displayed strength values and exposes the calculation
inputs in Supplementary Table S3, but it does not reconcile the paper's 76%
statement.

The table defines root surface area as perimeter multiplied by root length.
For the representative PDGF-BB tooth `#5430`, the four root areas sum to
7.58 mm²; the listed group mean maximum load is 18.6 N. This gives
18.6 / 7.58 = 2.4538 N/mm², which rounds to the table's 2.45. For representative
control tooth `#5545`, 34.1 N / 10.06 mm² = 3.3897 N/mm², which rounds to 3.39.
Their reconstructed ratio is 72.39%. Taking the already rounded strengths
directly gives 2.45 / 3.39 = 72.27%.

Even if each displayed strength were rounded to the nearest 0.01 N/mm², the
possible quotient would be approximately 72.02–72.53%, still below 76%. The
source-level arithmetic therefore confirms a discrepancy, not its cause. The
source data are stated to be available from the corresponding author upon
reasonable request; no public per-tooth force/area records or calculation
worksheet were located.

## Important denominator limit

Table S3 pairs each group's mean maximum load from Figure 2d with the root area
measured from one representative CT-scanned tooth in that group. It does not
report the force and surface area for every mechanically tested tooth. The
72.39% reconstruction is consequently an audit of the published summary
calculation, not an animal-level area-normalized treatment effect. It supplies
no variance, covariance, confidence interval, or significance test. The value
must remain separate from the paper's other day-21 endpoints: 54% for failure
load, 68% for maximum deformation, and 44% for failure energy.

## Reproducible calculation

The audited Table S3 inputs are transcribed in
[`mechanics_benchmark_inputs.json`](mechanics_benchmark_inputs.json). The
fetcher downloads the official supplementary PDF and checks its MD5 against
the checksum embedded in the article XML. The audit script checks the source
checksum, root-area totals, and displayed rounded strengths before writing
[`derived/area_normalized_strength_audit.json`](derived/area_normalized_strength_audit.json).

```powershell
python studies/dental-attachment-mechanics-2026-10-11/fetch_mechanics_sources.py
python studies/periodontal-attachment-restoration-2026-10-11/audit_area_normalized_strength.py
```

This rat tooth-replantation experiment is not a measurement of human chewing,
post-trauma in-situ tooth repositioning, or long-term positional stability.
The discrepancy does not change those translational limitations.

Sources: [Komatsu et al., 2022](https://doi.org/10.1038/s41598-022-06865-6) and
[the official Supplementary Information PDF](https://static-content.springer.com/esm/art%3A10.1038%2Fs41598-022-06865-6/MediaObjects/41598_2022_6865_MOESM1_ESM.pdf).
