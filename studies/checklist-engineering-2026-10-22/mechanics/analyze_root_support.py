"""Dimensionless rigid-body / distributed-foundation mechanics, standard library only.

This script is an engineering study, not a physiological or healing model.
The assembled matrix and reaction integral use independent implementations.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
GAUSS = ((-math.sqrt(3 / 5), 5 / 9), (0.0, 8 / 9), (math.sqrt(3 / 5), 5 / 9))


def finite_number(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError("Expected a finite real number")
    return float(x)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def matvec(k, q):
    return [dot(row, q) for row in k]


def solve3(matrix, rhs):
    """Scaled partial-pivot elimination; reject singular/ill-conditioned fixtures."""
    if len(matrix) != 3 or any(len(r) != 3 for r in matrix) or len(rhs) != 3:
        raise ValueError("Expected 3x3 matrix and three-vector")
    a = [[finite_number(x) for x in row] + [finite_number(b)] for row, b in zip(matrix, rhs)]
    scales = [max(abs(x) for x in row[:3]) for row in a]
    if any(x == 0 for x in scales):
        raise ValueError("Singular support matrix")
    for col in range(3):
        pivot = max(range(col, 3), key=lambda i: abs(a[i][col]) / scales[i])
        if abs(a[pivot][col]) <= scales[pivot] * 1e-12:
            raise ValueError("Singular or ill-conditioned support matrix")
        a[col], a[pivot] = a[pivot], a[col]
        scales[col], scales[pivot] = scales[pivot], scales[col]
        for i in range(col + 1, 3):
            factor = a[i][col] / a[col][col]
            for j in range(col, 4):
                a[i][j] -= factor * a[col][j]
    result = [0.0] * 3
    for i in range(2, -1, -1):
        result[i] = (a[i][3] - sum(a[i][j] * result[j] for j in range(i + 1, 3))) / a[i][i]
    return result


def displacement(q, point):
    x, y = point
    return [q[0] - y * q[2], q[1] + x * q[2]]


def generalized_load(force, point):
    fx, fy = [finite_number(v) for v in force]
    x, y = [finite_number(v) for v in point]
    return [fx, fy, x * fy - y * fx]


def p3(t):
    return (5 * t**3 - 3 * t) / 2


def segments(case, half_width=0.15, length=1.0):
    """Piecewise straight supports, explicitly split at each removed-band edge.

    Return (side, start, end, outward_normal). Missing side bands have no springs;
    the apical base remains in all three equal-length-loss comparisons.
    """
    if finite_number(half_width) <= 0 or finite_number(length) <= 0:
        raise ValueError("Positive geometry required")
    kind = case["kind"]
    if kind not in {"uniform", "cervical_loss", "apical_side_loss", "unilateral_loss", "spatial_alias"}:
        raise ValueError("Unknown support case")
    out = []
    for name, x, nx in (("left", -half_width, -1), ("right", half_width, 1)):
        low, high = -length, 0.0
        if kind == "cervical_loss":
            high = -0.30 * length
        elif kind == "apical_side_loss":
            low = -0.70 * length
        elif kind == "unilateral_loss" and name == "right":
            high = -0.60 * length
        out.append((name, (x, low), (x, high), (nx, 0.0)))
    out.append(("base", (-half_width, -length), (half_width, -length), (0.0, -1.0)))
    return out


def quadrature(case, config, rule="gauss", panels=1):
    if rule not in {"gauss", "midpoint"} or isinstance(panels, bool) or not isinstance(panels, int) or panels < 1:
        raise ValueError("Valid rule and positive integer panel count required")
    kn = finite_number(config["foundation"]["normal_density"])
    kt = finite_number(config["foundation"]["tangential_density"])
    multiplier = finite_number(case["multiplier"])
    if kn < 0 or kt < 0 or multiplier < 0:
        raise ValueError("Negative spring stiffness is not supported")
    length = finite_number(config["geometry"]["root_length"])
    alpha = finite_number(case.get("alias_amplitude", 0.0))
    if abs(alpha) > 1:
        raise ValueError("Alias density must remain nonnegative")
    points = GAUSS if rule == "gauss" else ((0.0, 2.0),)
    for side, a, b, n in segments(case, config["geometry"]["root_half_width"], length):
        ds = math.dist(a, b) / panels
        for panel in range(panels):
            for xi, weight in points:
                t = (panel + (xi + 1) / 2) / panels
                x = a[0] + t * (b[0] - a[0])
                y = a[1] + t * (b[1] - a[1])
                density = multiplier * (1 + alpha * p3(2 * y / length + 1) if side != "base" else 1)
                yield {"side": side, "point": (x, y), "normal": n,
                       "weight": ds * weight / 2, "kn": kn * density, "kt": kt * density}


def assemble(case, config, rule="gauss", panels=1):
    k = [[0.0] * 3 for _ in range(3)]
    for node in quadrature(case, config, rule, panels):
        x, y = node["point"]
        nx, ny = node["normal"]
        for direction, stiffness in (((nx, ny), node["kn"]), ((-ny, nx), node["kt"])):
            dx, dy = direction
            b = (dx, dy, -dx * y + dy * x)
            for i in range(3):
                for j in range(3):
                    k[i][j] += node["weight"] * stiffness * b[i] * b[j]
    return k


def reaction_integral(case, config, delta_q):
    """Compute physical 2D spring reactions + cross-product moments directly."""
    reaction = [0.0] * 3
    energy = 0.0
    for node in quadrature(case, config):
        d = displacement(delta_q, node["point"])
        nx, ny = node["normal"]
        normal_component = d[0] * nx + d[1] * ny
        tangent_component = -d[0] * ny + d[1] * nx
        traction = [-node["kn"] * normal_component * nx + node["kt"] * tangent_component * ny,
                    -node["kn"] * normal_component * ny - node["kt"] * tangent_component * nx]
        x, y = node["point"]
        weight = node["weight"]
        reaction[0] += weight * traction[0]
        reaction[1] += weight * traction[1]
        reaction[2] += weight * (x * traction[1] - y * traction[0])
        energy += weight * (node["kn"] * normal_component**2 + node["kt"] * tangent_component**2) / 2
    return reaction, energy


def response(case, config, contact, q0=None):
    k = assemble(case, config)
    f = generalized_load(contact["force"], contact["point"])
    q = solve3(k, f)
    d = displacement(q, contact["point"])
    force_norm = math.hypot(*contact["force"])
    if force_norm == 0:
        raise ValueError("Use a nonzero unit-response load")
    reaction, energy = reaction_integral(case, config, q)
    offset = [0.0] * 3 if q0 is None else [finite_number(x) for x in q0]
    if len(offset) != 3:
        raise ValueError("Three resting-pose coordinates required")
    return {"support_id": case["id"], "contact_id": contact["id"],
            "matrix": k, "generalized_load": f, "delta_q": q,
            "resting_q": offset, "total_q": [a + b for a, b in zip(offset, q)],
            "contact_delta": d, "contact_compliance": dot(d, contact["force"]) / force_norm**2,
            "integrated_reaction": reaction, "force_moment_residual": [a + b for a, b in zip(reaction, f)],
            "foundation_energy": energy, "half_load_work": dot(f, q) / 2,
            "supported_boundary_length": sum(math.dist(a, b) for _, a, b, _ in segments(case, config["geometry"]["root_half_width"], config["geometry"]["root_length"]))}


def max_matrix_error(a, b):
    return max(abs(x - y) for ar, br in zip(a, b) for x, y in zip(ar, br))


def write_tsv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, list(rows[0]), delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def local_reaction_profile(config, reference_q, amplitude):
    """Right-side continuous field, separate from integration nodes."""
    length = config["geometry"]["root_length"]
    a = config["geometry"]["root_half_width"]
    kn = config["foundation"]["normal_density"]
    kt = config["foundation"]["tangential_density"]
    rows = []
    for i in range(101):
        y = -length + length * i / 100
        d = displacement(reference_q, (a, y))
        density = 1 + amplitude * p3(2 * y / length + 1)
        ref = [-kn * d[0], -kt * d[1]]
        alt = [density * v for v in ref]
        rows.append({"right_side_y": y, "relative_density": density,
                     "reference_reaction_x_per_length": ref[0], "reference_reaction_y_per_length": ref[1],
                     "alternative_reaction_x_per_length": alt[0], "alternative_reaction_y_per_length": alt[1],
                     "reference_reaction_magnitude_per_length": math.hypot(*ref),
                     "alternative_reaction_magnitude_per_length": math.hypot(*alt)})
    return rows


def figure(path, cases, results, config, alias):
    """Original vector scientific plot of computed values; no adapted images."""
    reference_contact = next(c for c in config["contact_cases"] if c["id"] == "reference_lever")
    baseline = next(r for r in results if r["support_id"] == "reference" and r["contact_id"] == "reference_lever")["contact_compliance"]
    colors = ["#184e77", "#b34d24", "#387d3b", "#7652a3"]
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="520" viewBox="0 0 1120 520">',
           '<rect width="1120" height="520" fill="white"/>',
           '<g font-family="Arial, sans-serif" fill="#1d2833">',
           '<text x="25" y="30" font-size="20">Spatial root support and crown contact: illustrative linear model</text>',
           '<text x="25" y="53" font-size="13">Rigid crown/root; unit-response coefficients, no human calibration or acceptance threshold</text>',
           '<text x="25" y="90" font-size="16">A. Equal removed length, different compliance</text>']
    labels = {"reference": "Uniform", "cervical_loss": "Cervical loss", "apical_side_loss": "Apical-side loss", "unilateral_loss": "One-side loss"}
    for i, case in enumerate(cases[:4]):
        r = next(r for r in results if r["support_id"] == case["id"] and r["contact_id"] == reference_contact["id"])
        ratio = r["contact_compliance"] / baseline
        y = 125 + i * 62
        svg += [f'<text x="25" y="{y+17}" font-size="13">{labels[case["id"]]}</text>',
                f'<rect x="155" y="{y}" width="{ratio*55:.3f}" height="26" fill="{colors[i]}"/>',
                f'<text x="{163+ratio*55:.3f}" y="{y+18}" font-size="13">{ratio:.3f}x</text>']
    length = config["geometry"]["root_length"]
    total_length = 2 * length + 2 * config["geometry"]["root_half_width"]
    svg += ['<text x="155" y="397" font-size="13">Crown directional compliance / uniform reference</text>',
            f'<text x="25" y="432" font-size="12">Each loss removes {0.6*length:.2f} of {total_length:.2f} boundary-length units.</text>',
            '<text x="25" y="451" font-size="12">Base retained; changes are hypothetical support states.</text>',
            '<text x="585" y="90" font-size="16">B. Same whole matrix, different local reactions</text>']
    # Right-side spring force magnitude for reference unit horizontal crown force.
    q = next(r for r in results if r["support_id"] == "reference" and r["contact_id"] == "reference_lever")["delta_q"]
    profile = local_reaction_profile(config, q, alias["alias_amplitude"])
    curves = [[(r["right_side_y"], r[key]) for r in profile] for key in
              ("reference_reaction_magnitude_per_length", "alternative_reaction_magnitude_per_length")]
    max_force = max(f for curve in curves for _, f in curve)
    svg += ['<path d="M 640 115 V 370 H 1050" fill="none" stroke="#66717d"/>']
    for values, color in zip(curves, ("#184e77", "#b34d24")):
        pts = " ".join(f'{640+390*f/max_force:.3f},{370-255*(y/length+1):.3f}' for y, f in values)
        svg.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"/>')
    svg += ['<text x="594" y="103" font-size="12">Root y</text>',
            '<text x="605" y="120" font-size="12">0</text>', f'<text x="597" y="374" font-size="12">{-length:g}</text>',
            '<text x="675" y="397" font-size="13">Right-side local reaction magnitude (arbitrary units)</text>',
            '<text x="585" y="432" font-size="12" fill="#184e77">Uniform density</text>',
            f'<text x="585" y="451" font-size="12" fill="#b34d24">Density 1 + {alias["alias_amplitude"]:g} P3(2y/L+1); positive {1-alias["alias_amplitude"]:g} to {1+alias["alias_amplitude"]:g}</text>',
            '<text x="585" y="474" font-size="12">Global force/moment response cannot identify this spatial difference.</text>',
            '</g></svg>']
    path.write_text("\n".join(svg) + "\n", encoding="utf-8", newline="\n")


def analyze(config):
    cases, contacts = config["support_cases"], config["contact_cases"]
    if len({c["id"] for c in cases}) != len(cases) or len({c["id"] for c in contacts}) != len(contacts):
        raise ValueError("Duplicate support or contact identifiers")
    results = [response(case, config, contact) for case in cases for contact in contacts]
    ref_case = next(c for c in cases if c["id"] == "reference")
    contact = next(c for c in contacts if c["id"] == "reference_lever")
    baseline = response(ref_case, config, contact)
    alias = {"id": "spatial_alias", "kind": "spatial_alias", "multiplier": 1.0,
             "alias_amplitude": config["spatial_alias_amplitude"]}
    aliased = response(alias, config, contact)
    convergence = []
    for case in cases[:4]:
        exact = response(case, config, contact)
        for n in config["midpoint_panels_per_segment"]:
            k = assemble(case, config, "midpoint", n)
            q = solve3(k, exact["generalized_load"])
            compliance = dot(displacement(q, contact["point"]), contact["force"])
            convergence.append({"support_id": case["id"], "panels_per_retained_segment": n,
                                "matrix_max_absolute_error": max_matrix_error(k, exact["matrix"]),
                                "crown_compliance_relative_error": abs(compliance / exact["contact_compliance"] - 1)})
    # Distinct location and mechanics questions are separated explicitly.
    pose = response(ref_case, config, contact, config["pose_offset"])
    return {"schema_version": 1, "status": config["status"], "units": "dimensionless linear response coefficients; rotation in radians per unit load",
            "responses": results, "midpoint_convergence": convergence,
            "local_reaction_profile": local_reaction_profile(config, baseline["delta_q"], config["spatial_alias_amplitude"]),
            "spatial_nonidentifiability": {"alias": alias, "reference_matrix": baseline["matrix"],
                "alternative_matrix": aliased["matrix"], "matrix_max_absolute_difference": max_matrix_error(baseline["matrix"], aliased["matrix"]),
                "reference_delta_q": baseline["delta_q"], "alternative_delta_q": aliased["delta_q"],
                "density_min": 1-config["spatial_alias_amplitude"], "density_max": 1+config["spatial_alias_amplitude"],
                "reason": "P3(2y+1) is orthogonal on [-1,0] to polynomials of degree <=2. Rigid-body spring assembly contains only zeroth, first and second moments of side density. Three-point Gauss integrates degree <=5 exactly.",
                "local_reaction_ratio_at_right_cervical_endpoint": 1+config["spatial_alias_amplitude"],
                "local_reaction_ratio_at_right_apical_endpoint": 1-config["spatial_alias_amplitude"],
                "claim": "Exact continuum alias within this reduced model, not an assertion that real PDL follows this density law"},
            "resting_pose_example": {"reference": baseline, "wrong_resting_pose": pose,
                "zero_load_pose_after_reversible_unloading": config["pose_offset"],
                "claim": "Same incremental mobility can coexist with an imposed wrong resting pose. Unloading recovers that imposed pose; trauma, healing and drift were not simulated."},
            "max_force_moment_residual": max(abs(v) for r in results for v in r["force_moment_residual"]),
            "max_energy_identity_absolute_error": max(abs(r["foundation_energy"]-r["half_load_work"]) for r in results),
            "limits": config["limits"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "derived")
    args = parser.parse_args()
    config = json.loads((HERE / "model_inputs.json").read_text(encoding="utf-8"))
    results = analyze(config)
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(results, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    rows = []
    baselines = {r["contact_id"]: r["contact_compliance"] for r in results["responses"] if r["support_id"] == "reference"}
    for r in results["responses"]:
        rows.append({"support_id": r["support_id"], "contact_id": r["contact_id"], "supported_boundary_length": r["supported_boundary_length"],
                     "ux_per_unit_force": r["delta_q"][0], "uy_per_unit_force": r["delta_q"][1], "rotation_per_unit_force": r["delta_q"][2],
                     "directional_crown_compliance": r["contact_compliance"], "relative_to_same_contact_reference": r["contact_compliance"]/baselines[r["contact_id"]],
                     "max_equilibrium_residual": max(abs(x) for x in r["force_moment_residual"])})
    write_tsv(output / "support_contact_comparison.tsv", rows)
    write_tsv(output / "midpoint_convergence.tsv", results["midpoint_convergence"])
    write_tsv(output / "local_reaction_profile.tsv", results["local_reaction_profile"])
    figure(output / "root_support.svg", config["support_cases"], results["responses"], config, results["spatial_nonidentifiability"]["alias"])
    paths = [HERE / "model_inputs.json", Path(__file__), HERE / "source_scope.json"]
    canonical_hash = lambda p: hashlib.sha256(p.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    hashes = {p.name: canonical_hash(p) for p in paths}
    receipt = {"operation": "local illustrative rigid-tooth support calculation; no new source fetch", "python_version": platform.python_version(),
               "hash_mode": "UTF-8 text with line endings normalized to LF",
               "input_sha256": hashes, "outputs_sha256": {p.name: canonical_hash(p) for p in sorted(output.iterdir()) if p.name != "analysis_receipt.json" and p.is_file()}}
    (output / "analysis_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"response_cases": len(rows), "convergence_rows": len(results["midpoint_convergence"]),
                      "max_equilibrium_residual": results["max_force_moment_residual"],
                      "alias_matrix_difference": results["spatial_nonidentifiability"]["matrix_max_absolute_difference"]}))


if __name__ == "__main__":
    main()
