# Crown contact and distributed root support: an executed engineering model

This AI-assisted study connects a crown contact's location to translation,
rotation and local attachment reactions in a small, inspectable mechanical
solver. **It is an illustrative dimensionless experiment, not a fitted human
tooth, biological repair simulation or clinical load recommendation.** It
demonstrates that equal amounts of support loss can give different responses,
and that even a complete global stiffness matrix can hide spatially different
support reactions. The missing observations are made specific below.

## What was added beyond earlier work

The prior [rat displacement interpolation](../../periodontal-attachment-restoration-2026-10-11/build_displacement_model.py)
connects two published group means. The prior
[mechanics benchmark](../../periodontal-attachment-restoration-2026-10-11/build_mechanics_benchmark.py)
shows scalar ambiguity between parallel load paths. This study adds a
distributed boundary, three rigid-body degrees of freedom, applied moments,
asymmetric support loss, local reactions, equilibrium/energy verification and
an exact spatial inverse-problem counterexample. It is not another fit of
those two means.

The [paired crown OES/EDJ reference](../../periodontal-attachment-restoration-2026-10-11/PAIRED_TOOTH_SURFACE_REFERENCE.md)
does not supply a matched root, PDL and socket. We therefore use no anatomical
mesh. A rigid crown/root transfers contact force and its lever-arm moment to
the support. **Rigid-body mechanics does not resolve enamel/dentin thickness,
restored material quality, internal damage, pulp, fracture or fatigue.** This
advances geometry-to-attachment coupling without validating hard tissue.

## Frozen assumptions and equations

All numbers are in the [input file](model_inputs.json). A rectangular root
has length 1 and half-width 0.15. Its two sides and apical base are supported;
the cervical top is unsupported. The crown contact is a point above that
root. Independent linear springs are anchored to a fixed socket, with normal
density 1 and tangential density 0.25 per boundary length. These densities are
not a Young's modulus. No PDL thickness, human load, native displacement scale,
time scale, tissue fit, population variation or physiological threshold is
assigned. Width and length ratios are engineering choices, not anatomy.

Coordinates use x horizontally and y upward, with root y from -1 to 0. Let
q=(u_x,u_y,theta); at a boundary point r=(x,y), displacement is

```text
d(r) = B(r) q = (u_x - y theta, u_y + x theta)
C(r) = k_n(r) n n^T + k_t(r) t t^T
K = integral B^T C B ds
f = (F_x, F_y, x_contact F_y - y_contact F_x)
K (q - q0) = f
traction(r) = -C(r) B(r) (q - q0)
U = (q - q0)^T K (q - q0) / 2
2U = f^T (q - q0)
```

Both force components and moments use the same cervical-center origin.
Rotation is an infinitesimal angle. Normal springs resist both signs equally;
there is no tension/compression asymmetry, collagen recruitment, viscosity,
fluid flow, damage, active contraction, socket compliance or neighboring teeth.

Unit forces report derivatives of the linear response about q0. For example,
a rotation coefficient larger than 1 is **not** a predicted finite rotation;
it multiplies an arbitrarily small force parameter. Linearity permits smaller
probes without changing compliance ratios. No physical conversion is supplied.

The human passive-PDL primary study
[Wu et al. 2018](https://doi.org/10.1186/s12938-018-0607-0) uses sectioned
native tissue, bilinear branches and coupled load/rate regimes. It does not
calibrate these whole-root springs or establish universal linear behavior.
The [existing source audit](../../checklist-function-2026-10-19/attachment/REPORT.md)
retains the separate six summary rows and their sampling limitations.
Active construct post stiffness is excluded. The
[source scope](source_scope.json) distinguishes contextual evidence from
illustrative numeric inputs; no new raw source download is claimed.

## Executed comparisons

The solver executed 6 support states by 5 contact cases, giving 30 responses.
The following values use a horizontal unit response at (0,0.5). Compliance
is displacement along the force divided by force, normalized to the uniform
reference at that same contact. It is not a fraction of biological recovery.

| Illustrative support state | Retained boundary length | Crown compliance / reference | Meaning within this model |
|---|---:|---:|---|
| Uniform reference |2.30|1.0000|Computational comparator, not a healthy acceptance band|
| Remove cervical 0.30 on both sides |1.70|3.2606|Loss near cervical side has greater effect for this load/geometry|
| Remove apical 0.30 on both sides |1.70|1.5212|Same removed side length, base retained|
| Remove cervical 0.60 on right side only |1.70|1.6967|Asymmetry couples horizontal loading to vertical motion|
| All spring densities multiplied by 0.25 |2.30|4.0000|Uniformly more compliant|
| All spring densities multiplied by 1000 |2.30|0.0010|Uniformly stiffer; not biological ankylosis detection|

The three loss cases all remove 0.60 of 2.30 boundary-length units. These are
2D lengths, **not** measured ligament surface area, healing fractions or
clinical loss percentages. The ranking is conditional on this geometry,
stiffness ratio and contact. A central axial unit response gives identical
compliance 1.53846 for the two symmetric loss cases, while horizontal crown
response separates them. One load direction can conceal relevant differences.

Moving a horizontal contact from y=0.25 to 0.50 to 0.75 in the uniform case
changes directional compliance from 3.45781 to 5.71032 to 8.59339. The force is
unchanged; its moment increases. Moving an axial contact from x=0 to x=0.15
creates a moment and rotation that the centered axial contact lacks. These
are lever-arm effects; they do not make the rigid crown a thickness model.
Every configuration, including adverse high-compliance states, remains in the
[comparison table](derived/support_contact_comparison.tsv).

![Computed support sensitivity and exact spatial ambiguity](derived/root_support.svg)

## A stronger nonidentifiability result

On each vertical side, compare uniform spring density with
1+0.8P3(2y+1), where P3(t)=(5t^3-3t)/2. Keep the apical base unchanged and
multiply both normal and tangential densities by the same profile. The
alternative density remains positive, from 0.2 to 1.8 of reference.

Rigid-body K depends on side-density moments of order 0, 1 and 2. P3 is
orthogonal to each of those polynomials on the root interval, so these two
fields produce **exactly the same entire 3x3 stiffness matrix** in the
continuum model. Three-point Gauss quadrature integrates the degree-five
terms exactly; the executed floating-point matrix difference is 0. Independent
horizontal, vertical and pure-moment probes all give the same global pose.

Local reaction fields still differ: under the same horizontal crown probe,
the alternative/reference right-side reaction ratio is 1.8 at the cervical
endpoint and 0.2 at the apical endpoint. This is a manufactured mathematical
counterexample, not a claimed disease pattern. It establishes a limit of
this inverse problem: **more global mobility probes can identify more of K,
but cannot uniquely recover the spatial support field even if K is known.**
Regional attachment/imaging information or local strain/reaction measurements
would supply information absent from global compliance alone. The chosen
profile is disclosed, not inferred from measurements. All 101 sampled right-side
locations and reaction components are in the
[local profile table](derived/local_reaction_profile.tsv); its rows are
computational samples of the same two fields, not biological replicates.

## Resting pose, compliance and stiff support are separate questions

The baseline and a deliberately displaced resting pose q0=(0.02,0,0.01)
have identical incremental K and mobility. The prescribed offset remains
after reversible unloading because q0 was supplied to the model. We did
**not** simulate trauma, movement back to an original pose, remodeling,
support withdrawal or subsequent drift. A normal-looking incremental response
cannot recover an unmeasured original resting pose.

Uniformly multiplying all spring densities by 1000 produces much less motion
under force control but the same spatial reaction distribution for that
load. Stiffness alone supplies neither tissue identity nor proof of healthy
shock absorption. The state is simply an illustrative high-stiffness support;
it is not a biological simulation or diagnosis of ankylosis. Anatomical
insertion, tissue viability, recovery/dissipation and adverse bridging remain
separate required observations.

## Verification and limits

Independent traction integration balances both forces and same-origin moment
for all 30 cases: maximum absolute residual 2.11e-15 in model units. Integrated
spring energy matches half the generalized load work. Uniform-boundary K is
also checked against closed analytical integrals, and the lateral response
against a separate 2x2 closed solution.

A distinct midpoint discretization uses 2, 4, 8, 16, 32, 64 and 128 panels per
retained segment for four states. Matrix error decreases fourfold each
doubling, as expected for quadratic integrands. At 128 panels, the largest
crown compliance relative error against exact polynomial quadrature is
4.76205e-5. These are numerical convergence and algebra checks; they are
**not** anatomical or biological validation. The
[convergence table](derived/midpoint_convergence.tsv) retains all 28 rows.

The model cannot predict permanent repositioning, relapse after finite support
withdrawal, healing, fracture/fatigue life, perfusion, gum/papilla/barrier
restoration, pulp recovery or original tooth substance. It has no tooth–tooth
contact area, dynamic bite cycle, stress acceptance cutoff, crown compliance,
real socket geometry or donor data. The entire support model is illustrative;
parameter uncertainty is not assigned invented probabilities. The rectangular
root is a deliberate simplification, with no claim of anatomical accuracy.

## Next measurement decision

For the same specimen, retain original and unloaded pose, crown contact point
and force direction, root/socket geometry, region-specific attachment status,
and paired reversible force–displacement–rotation responses. Multi-direction
responses distinguish some stiffness changes missed by one probe. Regional
observations are still needed because the exact alias survives complete
global K. Track material thickness/internal integrity, native inserted
attachment, gums, pulp and stability after finite support removal as separate
linked outcomes; this static solver does not pass any of those endpoints.

These requirements specify an inspectable research dataset, not a procedure
for manipulating a person's teeth. The ambitious full-restoration goal is
unchanged; this calculation narrows which measurements can discriminate its
mechanical alternatives.

## Reproduce

```text
python -B studies/checklist-engineering-2026-10-22/mechanics/analyze_root_support.py
python -B -m unittest discover -s tests -p test_checklist_engineering_mechanics.py -v
```

Only Python's standard library is required. The analysis produces
[results](derived/results.json), three tables, the original SVG figure and a
[local analysis receipt](derived/analysis_receipt.json) with canonical UTF-8/LF
input/script and output hashes. The original SVG was rendered and visually
checked. It creates no source-fetch provenance. The 16 focused checks
include balance/energy, exact integrals, scale/sign limits, asymmetric loss,
contact moments, full-matrix spatial alias, resting-pose ambiguity,
discretization convergence and rejection of singular/nonfinite supports.
Docker workbench was stopped when checked; no passing doctor result is claimed.
