# Spherical Transient Oxygen Diffusion Model

Illustrative time-dependent numerical simulation of oxygen ramp-up from anoxic initial conditions.

Radius: 300 µm. Total simulated time: 120 s (24 steps).
Initial oxygen: 0 mol/m³. Bulk oxygen: 0.2 mol/m³.

| Quantity | Value |
|---|---:|
| Diffusion time scale R²/D (s) | 45.00 |
| Initial core oxygen (mol/m³) | 0 |
| Final core oxygen at 120.0s (mol/m³) | 0.00789644 |
| Steady-state core oxygen (mol/m³) | 0.00789644 |
| Difference vs steady state (mol/m³) | 2.1392e-09 |
| Time to 50% steady-state core | 15.65 s |
| Time to 95% steady-state core | 36.52 s |
| Final surface oxygen (mol/m³) | 0.115714 |
| Final volume-mean oxygen (mol/m³) | 0.0682666 |
| Final below-threshold fraction | 0.0610 |

## Interpretation

- Transient PDE mode solving del(c)/del(t) = D nabla^2(c) - R(c) from initial concentration.
- Illustrative numerical model; parameters need experimental calibration.
- Core oxygen is tracked at innermost shell center, surface at r=R with Robin/Dirichlet boundary.
- Times to 50% and 95% of steady-state core oxygen are first threshold crossings; the crossing direction follows whether the initial core is below or above steady state.
- Spherical, homogeneous organoid model with fixed bath oxygen; no vascularization or cell death.
