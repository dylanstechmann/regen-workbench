# Missing tooth-surface reconstruction across additional specimens

The frozen methods do not show a consistent advantage from adding the internal
enamel-dentine junction (EDJ). On two additional teeth, the quadratic EDJ-gap
method improved nine-patch mean error slightly on M3#88 and worsened it on
M3#90. This supports keeping the exterior-only comparison in the next study.
It does not establish that internal imaging is unhelpful in general.

This is an AI-assisted computational research exercise. It estimates missing
external geometry, one input to the [full restoration target](FULL_TOOTH_RESTORATION_BLUEPRINT.md).
It does not replace missing enamel, regenerate dentin or restore attachment.

## Frozen transport check

The [development experiment](MISSING_TOOTH_PATCH_RECONSTRUCTION_REPORT.md)
used M3#83. Before evaluating new patch outcomes, `prepare` froze the same
0.125 mm grid, three XY fractional locations, three radii (0.4/0.8/1.2 mm),
support annulus, four methods, minimum support and conditioning gates in
[the intake record](derived/patch_replication/frozen_intake.json) and two
specimen plans. This is a local before-evaluation freeze, not an independent
preregistration. No models, support rules or locations were tuned using these
new outcomes. The original development case remains separate.

Selection used Table 1 of the [primary study](https://doi.org/10.1371/journal.pone.0159688)
and the [dataset descriptions](https://doi.org/10.18563/m3.2.1.e1): remaining
adult specimens with completed H maturation, wear stage 1 and no flagged
reconstructed dentine horn tip. M3#88 is GLN04-289B-URM2 (female, >30 years);
M3#90 is GLN05-292-URM2 (female, 20–29 years). The two teeth are right upper
second molars; M3#83 was left-sided. Supplied poses were retained without
mirroring. Fractional XY locations are computational locations, not matched
anatomical landmarks. Both additional specimens come from the same collection
and processing pipeline, so this is not independent-laboratory validation.

Every triangle whose XY projection intersects the withheld disk is removed
from visible support. Fits use retained support only; their coefficients and
prediction hashes are saved before computing full-reference OES heights.
The informed branch receives full EDJ imaging in the supplied shared pose.
All branches receive full-source XY extents and metric scale. These are
privileged inputs; no photographs, unknown scale, registration uncertainty,
cracks or actual injury boundaries were tested.

## Results

Mean of nine patch mean absolute vertical errors, in nominal millimetres:

| Method | M3#88 | M3#90 |
| --- | ---: | ---: |
| Exterior plane | 0.3547 | 0.2768 |
| Exterior quadratic | 0.1552 | 0.1621 |
| Internal imaging, plane residual | 0.1902 | 0.2676 |
| Internal imaging, quadratic residual | 0.1530 | 0.2258 |

Compared with exterior quadratic, informed quadratic improved 5/9 patches on
M3#88 and 4/9 on M3#90. Mean difference was -0.0022 mm and +0.0636 mm,
respectively; negative favors the informed method. All 36 comparisons per
specimen scored with complete reference and prediction coverage. The
[transport summary](derived/patch_replication/transport_summary.json) retains
all paired differences; each specimen directory contains all rows, plans,
prediction receipts and the fixed central-patch figure.

Maximum absolute errors across the quadratic-method queries were 0.6666 mm
(exterior) and 0.6761 mm (informed) on M3#88, and 1.1133 mm and 1.0139 mm on
M3#90. Lower average error does not remove substantial local mismatch.

There are two additional specimens, not 18 independent patches or 72
independent observations. Patches overlap. No population significance test,
clinical success threshold or claim of original pre-damage anatomy is made.
These are z-direction top-envelope errors, not surface-normal distances or
three-dimensional enamel thickness errors. Excess/deficit volumes are
heightfield proxies, not segmented enamel volumes.

## Source defects and limits

Both pairs are open meshes. M3#88 has 789 boundary edges/788 boundary vertices
in each mesh, including one boundary vertex whose degree is not two.
M3#90 has 990 boundary edges/vertices in each mesh and one nonmanifold edge
in OES. Neither pair has zero-area triangles or inconsistent internal-edge
winding in the implemented audit. These defects were retained without mesh
repair or exclusion. Complete query coverage does not establish that the
defects are harmless; their local influence has not been isolated.

The dataset uses source segmentation with manual corrections and smoothing.
No independent segmentation adjudication, self-intersection test or raw-scan
registration check was performed. Nominal millimetres follow the item readmes;
exact per-specimen scan resolution and calibration are unresolved. The
archaeological, slightly worn crowns are geometry references, not documented
undamaged youthful anatomy. Missing historical information cannot be recovered
uniquely merely by fitting a smooth patch.

## Reproduce

With NumPy available, from the repository root:

```text
python studies/periodontal-attachment-restoration-2026-10-11/replicate_missing_tooth_patches.py prepare
python studies/periodontal-attachment-restoration-2026-10-11/replicate_missing_tooth_patches.py run
python -m unittest discover -s tests -p test_patch_replication.py -v
python -m unittest discover -s tests -p "test_*tooth*.py" -v
```

`prepare` downloads only missing public archives with a 12 MB bound and
records actual fetch provenance. Existing frozen intake/plans cannot be
silently replaced with differing contents. Subsequent analysis checks pinned
archive hashes, source identity, the canonical pilot-plan hash and all frozen
numeric settings. This is a reproducibility record, not a tamper-proof audit
or independent preregistration. Outputs use UTF-8/LF for stable hash chains.

Source-derived outputs retain [CC BY-NC 4.0 and full credits](derived/patch_replication/README.md).
No raw source meshes or personal dental records are published.

Validation: the full default-host suite ran **537 tests, OK, 74 skipped**.
The optional NumPy tooth-study suite ran **34 tests, all passed**, separately;
the full-suite skips include optional scientific runtimes. Five new tests
check frozen settings, pilot hash and source identity. The original M3#83
summary, numerical table, prediction receipts and SVG remained unchanged on
rerun. New plan/prediction/intake hashes, row counts, document links and both
rendered figures were checked. Initial sandbox runs hit temporary-file
permission errors; the reported successful test runs used the host outside
that sandbox. Docker's `workbench` service was stopped, so no successful
`regen doctor` result is claimed.

## Next decision

Freeze this result before developing a better method. The next development
comparison should test spatially varying geometry priors and constrained
surface continuity against these baselines, with separate development and
untouched test specimens. Qualify additional source collections and their
license, age/wear, paired tissue labels, defects and calibration first.
Treat the present three teeth as already seen for future method development.
Add realistic injury shapes and uncertain scale/pose as separate challenges;
do not describe this favorable known-pose setting as photograph recovery.

Geometry should then specify an independently tested material/interface
target: enamel structure and wear, dentin/pulp compatibility, crack integrity,
load transfer and PDL/gingival attachment remain separate required endpoints.
