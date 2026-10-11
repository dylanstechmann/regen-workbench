#!/usr/bin/env python3
"""Monte Carlo planning approximation for a crossed donor age×niche interaction.

This estimates power for one continuous post-washout interaction endpoint.
It is not a fitted mixed model and does not select a biological effect size.
All variance and effect inputs must come from a pilot or be labeled as a
hypothetical sensitivity scenario.
"""

from __future__ import annotations

import argparse
import math
import random
from statistics import NormalDist


def interaction_se(
    n_per_stratum: int,
    target_donor_slope_sd: float,
    niche_lot_interaction_sd: float,
    construct_residual_sd: float,
    constructs_per_pair: int,
) -> float:
    """SE of the balanced difference-in-differences estimator.

    n_per_stratum is used for each target-cell age stratum and each niche-donor
    age stratum. The residual term is reduced by nested construct replicates;
    donor and lot terms are not.
    """
    n = n_per_stratum
    variance = (
        2 * target_donor_slope_sd**2 / n
        + 2 * niche_lot_interaction_sd**2 / n
        + 4 * construct_residual_sd**2 / (n * n * constructs_per_pair)
    )
    return math.sqrt(variance)


def t_critical_approx(alpha: float, degrees_freedom: int) -> float:
    """Two-sided Student-t critical value via a Cornish-Fisher expansion."""
    if not 0 < alpha < 1 or degrees_freedom < 1:
        raise ValueError("alpha must be in (0,1) and degrees of freedom positive")
    z = NormalDist().inv_cdf(1 - alpha / 2)
    v = float(degrees_freedom)
    z2, z3, z5, z7 = z * z, z**3, z**5, z**7
    return (
        z
        + (z3 + z) / (4 * v)
        + (5 * z5 + 16 * z3 + 3 * z) / (96 * v**2)
        + (3 * z7 + 19 * z5 + 17 * z3 - 15 * z) / (384 * v**3)
    )


def simulate_power(
    effect: float,
    se: float,
    degrees_freedom: int,
    alpha: float,
    simulations: int,
    seed: int,
) -> tuple[float, float]:
    """Simulate rejection probability and its Monte Carlo standard error."""
    rng = random.Random(seed)
    critical = t_critical_approx(alpha, degrees_freedom)
    rejected = 0
    for _ in range(simulations):
        numerator = rng.normalvariate(effect / se, 1.0)
        denominator = math.sqrt(rng.gammavariate(degrees_freedom / 2, 2) / degrees_freedom)
        rejected += abs(numerator / denominator) > critical
    power = rejected / simulations
    mcse = math.sqrt(power * (1 - power) / simulations)
    return power, mcse


def validate_inputs(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    positive = {
        "effect": args.effect,
        "target-donor-slope-sd": args.target_donor_slope_sd,
        "niche-lot-interaction-sd": args.niche_lot_interaction_sd,
        "construct-residual-sd": args.construct_residual_sd,
    }
    for name, value in positive.items():
        if not math.isfinite(value) or value < 0:
            parser.error(f"--{name} must be finite and nonnegative")
    if args.effect == 0:
        parser.error("--effect must be nonzero for sample-size search; use a nonzero null-calibration test in the unit checks")
    if args.constructs_per_pair < 1 or args.simulations < 1000 or args.max_per_stratum < 3:
        parser.error("constructs per pair must be positive, simulations at least 1000, and search cap at least 3")
    if not any((args.target_donor_slope_sd, args.niche_lot_interaction_sd, args.construct_residual_sd)):
        parser.error("at least one variance-component SD must be positive")
    if not 0 < args.alpha < 1 or not 0 < args.target_power < 1:
        parser.error("alpha and target power must be between 0 and 1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effect", type=float, required=True, help="Smallest relevant interaction, in endpoint units")
    parser.add_argument("--target-donor-slope-sd", type=float, required=True,
                        help="SD of donor-specific niche-age response slopes, in endpoint units")
    parser.add_argument("--niche-lot-interaction-sd", type=float, required=True,
                        help="SD of niche-lot variation in the recipient-age interaction, in endpoint units")
    parser.add_argument("--construct-residual-sd", type=float, required=True,
                        help="SD of construct-level post-washout residual, in endpoint units")
    parser.add_argument("--constructs-per-pair", type=int, required=True,
                        help="Nested constructs per target x niche donor pair; these do not count as donors")
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--target-power", type=float, default=0.80)
    parser.add_argument("--simulations", type=int, default=50000)
    parser.add_argument("--max-per-stratum", type=int, default=100,
                        help="Search cap for donors in each target and niche age stratum")
    parser.add_argument("--seed", type=int, default=20261011)
    args = parser.parse_args()
    validate_inputs(args, parser)

    selected: int | None = None
    selected_power = 0.0
    selected_se = math.nan
    for n in range(3, args.max_per_stratum + 1):
        se = interaction_se(
            n, args.target_donor_slope_sd, args.niche_lot_interaction_sd,
            args.construct_residual_sd, args.constructs_per_pair,
        )
        df = 2 * n - 2
        estimate, mcse = simulate_power(
            args.effect, se, df, args.alpha, args.simulations, args.seed + n,
        )
        # Guard the search against selecting a sample size on Monte Carlo noise.
        if estimate - 3 * mcse >= args.target_power:
            selected, selected_power, selected_se = n, estimate, se
            break

    if selected is None:
        selected = args.max_per_stratum
        selected_se = interaction_se(
            selected, args.target_donor_slope_sd, args.niche_lot_interaction_sd,
            args.construct_residual_sd, args.constructs_per_pair,
        )
        selected_power, mcse = simulate_power(
            args.effect, selected_se, 2 * selected - 2, args.alpha,
            args.simulations, args.seed + 1_000_000,
        )
        print(f"No searched design reached target power by {selected} donors per stratum.")
    else:
        selected_power, mcse = simulate_power(
            args.effect, selected_se, 2 * selected - 2, args.alpha,
            args.simulations, args.seed + 1_000_000,
        )

    null_rate, null_mcse = simulate_power(
        0.0, selected_se, 2 * selected - 2, args.alpha,
        args.simulations, args.seed + 2_000_000,
    )
    print("Planning approximation for one continuous post-washout interaction endpoint")
    print("Variance components and smallest relevant effect are inputs, not empirical findings.")
    print(f"Effect: {args.effect:g}; interaction SE: {selected_se:.4g}; alpha: {args.alpha:g}")
    print(f"Donors per target-age stratum: {selected}")
    print(f"Donors per niche-age stratum: {selected}")
    print(f"Total independent donor preparations: {4 * selected}")
    print(f"Nested constructs per target x niche pair: {args.constructs_per_pair}")
    print(f"Simulated power: {selected_power:.3f} (Monte Carlo SE {mcse:.3f}; target {args.target_power:.2f})")
    print(f"Null rejection calibration: {null_rate:.3f} (Monte Carlo SE {null_mcse:.3f}; nominal alpha {args.alpha:.2f})")
    print("Interpretation: confirm with the preregistered crossed-effects model; this approximation omits missingness and batch imbalance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
