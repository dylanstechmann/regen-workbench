"""Withheld tooth top-envelope patches: exterior and internal-imaging baselines.

One source specimen per invocation; synthetic digital omissions. Generic local polynomial
fits do not imply enamel growth, exact historical recovery or clinical repair.
Source-derived outputs: Le Luyer et al. 2016, source model in plan, CC BY-NC 4.0.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import importlib.util
import json
import math
import platform
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("paired_tooth_reference", HERE / "analyze_paired_tooth_surfaces.py")
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def digest_array(values: np.ndarray) -> str:
    array = np.asarray(values, dtype="<f8")
    return hashlib.sha256(str(array.shape).encode() + array.tobytes()).hexdigest()


def triangle_disk_intersections(vertices: np.ndarray, faces: np.ndarray,
                                center: np.ndarray, radius: float) -> np.ndarray:
    """Intersect the closed XY disk with triangle interiors, edges and vertices."""
    if np.shape(center) != (2,) or not np.all(np.isfinite(center)) or not np.isfinite(radius) or radius <= 0:
        raise ValueError("Require a finite XY center and positive radius")
    triangles = vertices[faces, :2]
    a, b = triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    p = center - triangles[:, 0]
    denominator = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    safe = np.where(np.abs(denominator) > 1e-15, denominator, 1.)
    u = (p[:, 0] * b[:, 1] - p[:, 1] * b[:, 0]) / safe
    v = (a[:, 0] * p[:, 1] - a[:, 1] * p[:, 0]) / safe
    selected = (np.abs(denominator) > 1e-15) & (u >= -1e-12) & (v >= -1e-12) & (u + v <= 1 + 1e-12)
    for i, j in ((0, 1), (1, 2), (2, 0)):
        direction = triangles[:, j] - triangles[:, i]
        length2 = np.sum(direction ** 2, axis=1)
        t = np.clip(np.sum((center - triangles[:, i]) * direction, axis=1)
                    / np.where(length2 > 0, length2, 1.), 0, 1)
        closest = triangles[:, i] + t[:, None] * direction
        selected |= np.sum((closest - center) ** 2, axis=1) <= radius ** 2 + 1e-12
    return selected


def top_grid(vertices: np.ndarray, faces: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Rasterize maximum z at fixed XY rays; only supplied faces are consulted."""
    if len(xs) < 2 or len(ys) < 2:
        raise ValueError("Require at least two grid coordinates per axis")
    dx, dy = xs[1] - xs[0], ys[1] - ys[0]
    if (dx <= 0 or dy <= 0 or not np.all(np.isfinite(xs)) or not np.all(np.isfinite(ys))
            or not np.allclose(np.diff(xs), dx, rtol=0, atol=1e-10)
            or not np.allclose(np.diff(ys), dy, rtol=0, atol=1e-10)):
        raise ValueError("Require finite, increasing uniform grid coordinates")
    result = np.full((len(ys), len(xs)), -np.inf)
    triangles = vertices[faces]
    low = np.ceil((triangles[:, :, :2].min(axis=1) - [xs[0], ys[0]]) / [dx, dy] - 1e-10).astype(int)
    high = np.floor((triangles[:, :, :2].max(axis=1) - [xs[0], ys[0]]) / [dx, dy] + 1e-10).astype(int)
    low = np.maximum(low, [0, 0]); high = np.minimum(high, [len(xs) - 1, len(ys) - 1])
    for index in np.flatnonzero(np.all(low <= high, axis=1)):
        triangle = triangles[index]
        x0, y0, z0 = triangle[0]; x1, y1, z1 = triangle[1]; x2, y2, z2 = triangle[2]
        denominator = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denominator) <= 1e-14:
            continue
        xlo, ylo = low[index]; xhi, yhi = high[index]
        gx, gy = np.meshgrid(xs[xlo:xhi + 1], ys[ylo:yhi + 1])
        a = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / denominator
        b = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / denominator
        c = 1 - a - b
        inside = (a >= -1e-10) & (b >= -1e-10) & (c >= -1e-10)
        heights = np.where(inside, a * z0 + b * z1 + c * z2, -np.inf)
        block = result[ylo:yhi + 1, xlo:xhi + 1]
        np.maximum(block, heights, out=block)
    return np.where(np.isfinite(result), result, np.nan)


def design(xy: np.ndarray, center: np.ndarray, scale: float, degree: int) -> np.ndarray:
    if degree not in (1, 2) or not np.isfinite(scale) or scale <= 0:
        raise ValueError("Require plane/quadratic degree and a positive finite scale")
    normalized = (xy - center) / scale
    x, y = normalized.T
    terms = [np.ones(len(x)), x, y]
    if degree == 2:
        terms += [x * x, x * y, y * y]
    return np.column_stack(terms)


def fit_predict(support_xy: np.ndarray, support_z: np.ndarray, query_xy: np.ndarray,
                center: np.ndarray, scale: float, degree: int,
                minimum_support: int = 12, maximum_condition: float = 1e10) -> tuple[np.ndarray, dict]:
    if (len(support_xy) < minimum_support or support_z.shape != (len(support_xy),)
            or not np.all(np.isfinite(support_xy)) or not np.all(np.isfinite(support_z))
            or not np.all(np.isfinite(query_xy))):
        raise ValueError("Insufficient or invalid visible support")
    matrix = design(support_xy, center, scale, degree)
    condition = float(np.linalg.cond(matrix))
    coefficients, _, rank, _ = np.linalg.lstsq(matrix, support_z, rcond=None)
    if rank != matrix.shape[1] or not np.isfinite(condition) or condition > maximum_condition:
        raise ValueError("Visible-support fit is rank-deficient or ill-conditioned")
    prediction = design(query_xy, center, scale, degree) @ coefficients
    return prediction, {"coefficients": coefficients.tolist(), "degree": degree,
                        "normalization_center_xy_mm": center.tolist(), "normalization_scale_mm": scale,
                        "support_count": len(support_xy), "design_condition_number": condition,
                        "support_xy_sha256": digest_array(support_xy), "support_target_sha256": digest_array(support_z)}


def score_heights(prediction: np.ndarray, truth: np.ndarray, cell_area: float) -> dict:
    if prediction.shape != truth.shape or prediction.ndim != 1 or not np.isfinite(cell_area) or cell_area <= 0:
        raise ValueError("Require matching height vectors and positive cell area")
    result = {"query_count": len(truth), "reference_hit_count": int(np.isfinite(truth).sum()),
              "finite_prediction_count": int(np.isfinite(prediction).sum())}
    if not len(truth) or not np.all(np.isfinite(truth)) or not np.all(np.isfinite(prediction)):
        return {**result, "status": "unscored_incomplete_coverage", "mae_mm": None, "rmse_mm": None,
                "mean_signed_error_mm": None, "maximum_absolute_error_mm": None,
                "excess_envelope_volume_mm3": None, "deficit_envelope_volume_mm3": None}
    errors = prediction - truth
    return {**result, "status": "scored", "mae_mm": float(np.mean(np.abs(errors))),
            "rmse_mm": float(np.sqrt(np.mean(errors ** 2))), "mean_signed_error_mm": float(np.mean(errors)),
            "maximum_absolute_error_mm": float(np.max(np.abs(errors))),
            "excess_envelope_volume_mm3": float(np.maximum(errors, 0).sum() * cell_area),
            "deficit_envelope_volume_mm3": float(np.maximum(-errors, 0).sum() * cell_area)}


def error_map(case: dict, truth: np.ndarray, spacing: float, output: Path,
              source_label: str = "M3#83 GLN04-252-ULM2") -> None:
    methods = ["exterior_quadratic", "internal_imaging_quadratic_residual"]
    errors = [case["predictions"][m] - truth for m in methods]
    finite = np.concatenate([e[np.isfinite(e)] for e in errors])
    limit = max(.1, math.ceil(float(np.max(np.abs(finite))) * 10) / 10) if len(finite) else .1
    scale = 230 / (2 * case["radius"] + spacing)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="410" viewBox="0 0 760 410">',
             '<rect width="760" height="410" fill="white"/><g font-family="sans-serif" fill="#173742">',
             '<text x="20" y="26" font-size="18">Errors inside a digitally withheld tooth-surface patch</text>',
             '<text x="20" y="50" font-size="13">Fixed central location; radius 0.8 mm; predictions fitted before reference scoring</text>']
    for panel, (method, values) in enumerate(zip(methods, errors)):
        left = 45 + panel * 375
        label = "Exterior only: quadratic" if panel == 0 else "Internal imaging: quadratic residual"
        parts.append(f'<text x="{left-15}" y="80" font-size="14">{label}</text>')
        for xy, value in zip(case["query_xy"], values):
            x, y = (xy - case["center"] + case["radius"]) * scale
            if not np.isfinite(value):
                color = "#999999"
            else:
                fraction = min(abs(value) / limit, 1.)
                destination = np.array([215, 112, 42] if value >= 0 else [40, 100, 180])
                rgb = np.rint(248 * (1 - fraction) + destination * fraction).astype(int)
                color = "#" + "".join(f"{v:02x}" for v in rgb)
            parts.append(f'<rect x="{left+x:.2f}" y="{105+y:.2f}" width="{spacing*scale:.2f}" height="{spacing*scale:.2f}" fill="{color}"/>')
    parts += [f'<text x="20" y="350" font-size="13">Shared scale: +/-{limit:.1f} mm vertical error. Orange: excess; blue: deficit; gray: unavailable.</text>',
              f'<text x="20" y="375" font-size="12">{html.escape(source_label)}; geometry test, not regenerated tooth material.</text>',
              '<text x="20" y="397" font-size="10">Le Luyer et al. 2016; Osteotheque de Pessac, Universite de Bordeaux; curator S. Rottier. CC BY-NC 4.0.</text>',
              '</g></svg>']
    output.write_text("\n".join(parts) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=HERE / "patch_reconstruction_plan.json")
    parser.add_argument("--out", type=Path, default=HERE / "derived" / "missing_tooth_patches")
    parser.add_argument("--archive", type=Path, default=reference.ARCHIVE)
    args = parser.parse_args()
    # Hash text in canonical UTF-8/LF form so Git checkout newline settings
    # cannot invalidate otherwise identical prediction/plan receipts.
    plan_raw = args.plan.read_text(encoding="utf-8").encode("utf-8")
    plan = json.loads(plan_raw)
    raw = args.archive.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    if source_hash != plan["archive_sha256"]:
        raise ValueError("Source does not match the recorded plan")
    model_id = plan.get("model_id", 83)
    identifier = plan.get("specimen_identifier", reference.IDENTIFIER)
    if model_id == 83 and source_hash != reference.SOURCE_SHA256:
        raise ValueError("Development specimen does not match its pinned archive")
    meshes = {}
    with zipfile.ZipFile(args.archive) as archive:
        for role in ("OES", "EDJ"):
            base = f"M3#{model_id}/{identifier}_{role}"
            vertices, faces = reference.read_ply(archive.read(base + ".ply"))
            pose = reference.read_pose(archive.read(base + f"_M3_{model_id}.pos"))
            meshes[role] = (reference.transform(vertices, pose), faces)
    vertices, faces = meshes["OES"]
    lo, hi = vertices[:, :2].min(axis=0), vertices[:, :2].max(axis=0)
    spacing = float(plan["grid_spacing_mm"])
    if not np.isfinite(spacing) or spacing <= 0:
        raise ValueError("Invalid planned grid spacing")
    axes = [np.arange(math.ceil(lo[a] / spacing), math.floor(hi[a] / spacing) + 1) * spacing for a in (0, 1)]
    if len(axes[0]) * len(axes[1]) > 2000000:
        raise ValueError("Planned grid exceeds study memory bound")
    xx, yy = np.meshgrid(*axes)
    xy = np.stack([xx, yy], axis=-1)
    internal = top_grid(*meshes["EDJ"], *axes)
    cases, receipts = [], []
    for location_index, fraction in enumerate(plan["center_fractions_xy"]):
        center = lo + np.array(fraction) * (hi - lo)
        radial = np.linalg.norm(xy - center, axis=2)
        for radius in plan["patch_radii_mm"]:
            case_id = f"location{location_index+1}_r{radius:.1f}"
            removed = triangle_disk_intersections(vertices, faces, center, radius)
            visible = top_grid(vertices, faces[~removed], *axes)
            query = radial <= radius
            support = ((radial >= radius + plan["support_inner_margin_mm"])
                       & (radial <= radius + plan["support_outer_margin_mm"]) & np.isfinite(visible))
            predictions, method_receipts = {}, {}
            for method in plan["methods"]:
                degree = 2 if "quadratic" in method else 1
                informed = method.startswith("internal_imaging_")
                allowed_support = support & np.isfinite(internal) if informed else support
                sx, sz = xy[allowed_support], visible[allowed_support]
                if informed:
                    sz = sz - internal[allowed_support]
                try:
                    predicted, receipt = fit_predict(sx, sz, xy[query], center,
                        radius + plan["support_outer_margin_mm"], degree,
                        plan["minimum_support_points"], plan["maximum_design_condition_number"])
                    if informed:
                        predicted = predicted + internal[query]
                    receipt["status"] = "predicted"
                except ValueError as exc:
                    predicted = np.full(int(query.sum()), np.nan)
                    receipt = {"status": "fit_failed", "reason": str(exc), "support_count": len(sx)}
                receipt["information_branch"] = "full_source_internal_imaging" if informed else "retained_exterior_only"
                receipt["prediction_sha256"] = digest_array(predicted)
                predictions[method], method_receipts[method] = predicted, receipt
            receipts.append({"case_id": case_id, "center_fraction_xy": fraction,
                "center_xy_mm": center.tolist(), "radius_mm": radius,
                "removed_triangle_count": int(removed.sum()), "retained_triangle_count": int((~removed).sum()),
                "removed_face_indices_sha256": hashlib.sha256(np.flatnonzero(removed).astype("<i8").tobytes()).hexdigest(),
                "query_count": int(query.sum()), "query_xy_sha256": digest_array(xy[query]), "methods": method_receipts})
            cases.append({"case_id": case_id, "center": center, "radius": radius,
                          "query": query, "query_xy": xy[query], "predictions": predictions})
    # Commit the prediction artifact to disk before accessing full-source OES heights.
    args.out.mkdir(parents=True, exist_ok=True)
    prediction_path = args.out / "prediction_receipts.json"
    prediction_path.write_text(json.dumps({"plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
        "source_sha256": source_hash, "grid_xy_extent_mm": [lo.tolist(), hi.tolist()],
        "spacing_mm": spacing, "text_hash_convention": "UTF-8 with LF newlines",
        "stage": "predictions finalized before reference evaluation", "cases": receipts}, indent=2) + "\n", encoding="utf-8", newline="\n")
    prediction_hash = hashlib.sha256(prediction_path.read_bytes()).hexdigest()
    full_reference = top_grid(vertices, faces, *axes)
    rows = []
    for case in cases:
        truth = full_reference[case["query"]]
        for method, prediction in case["predictions"].items():
            rows.append({"case_id": case["case_id"], "radius_mm": case["radius"], "method": method,
                         **score_heights(prediction, truth, spacing ** 2)})
        if case["case_id"] == "location2_r0.8":
            error_map(case, truth, spacing, args.out / "fixed_patch_error_map.svg", plan["source_model"])
    with (args.out / "patch_errors.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    summary = {"analysis": plan["analysis_type"], "source_model": plan["source_model"],
        "source_sha256": source_hash, "plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
        "pre_evaluation_prediction_receipts_sha256": prediction_hash,
        "text_hash_convention": "UTF-8 with LF newlines",
        "clinical_pass_margin": None, "independent_specimens": 1,
        "case_count": len(cases), "comparison_count": len(rows),
        "scored_comparisons": sum(v["status"] == "scored" for v in rows),
        "height_error_direction": "posed z, not surface-normal/nearest-3D-surface distance",
        "volume_proxy": "regular-XY-cell integration of vertical envelope error; not segmented enamel volume",
        "qualification": "exploratory baselines on digital omissions; no camera reconstruction or biological repair",
        "source_derived_license": "CC-BY-NC-4.0",
        "software": {"python": platform.python_version(), "numpy": np.__version__}, "rows": rows}
    (args.out / "patch_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"cases": len(cases), "rows": len(rows),
                      "scored": summary["scored_comparisons"], "errors": rows}, indent=2))


if __name__ == "__main__":
    main()
