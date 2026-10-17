"""Audit a public OES/EDJ pair and measure sectional contour gaps.

Research reference: Le Luyer et al. 2016, M3#83, GLN04-252-ULM2,
doi:10.18563/m3.sf.83, CC BY-NC 4.0. This is not photo reconstruction,
clinical original anatomy, a 3D thickness assay or a regeneration result.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import sys
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEST = ROOT / "data" / "literature" / "hard-tissue-reference-qualification"
ARCHIVE = DEST / "morphomuseum_M3_83.zip"
URL = "https://www.morphomuseum.com/specimenfiles/send-file-specimenfile/83"
SOURCE_SHA256 = "d475ce2ef330417bafb0029f42a11a2c07e56163a98dec42424d9997c41177c8"
SOURCE_BYTES = 4030861
IDENTIFIER = "GLN04-252-ULM2"


def fetch_reference() -> None:
    """Pinned bounded public fetch; never accepts changed bytes silently."""
    if ARCHIVE.is_file() and hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == SOURCE_SHA256:
        return
    with urlopen(Request(URL, headers={"User-Agent": "regen-workbench/0.1"}), timeout=45) as response:
        raw = response.read(SOURCE_BYTES + 1)
    if len(raw) != SOURCE_BYTES or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Source bytes changed; review before accepting a new reference")
    DEST.mkdir(parents=True, exist_ok=True)
    ARCHIVE.write_bytes(raw)
    sys.path.insert(0, str(ROOT / "tools"))
    import regen
    regen.record("dental-paired-surface-reference-fetch", {
        "url": URL, "doi": "10.18563/m3.sf.83", "license": "CC-BY-NC-4.0",
        "selection": "first ascending model ID with Table1 adult, H maturation, wear1, no reconstructed-tip flag",
    }, [ARCHIVE])


def read_ply(raw: bytes) -> tuple[np.ndarray, np.ndarray]:
    """Strict reader for this VTK binary triangle format, not arbitrary PLY."""
    marker = b"end_header\n"
    if marker not in raw[:4096]:
        raise ValueError("Unsupported PLY header")
    end = raw.index(marker) + len(marker)
    header = raw[:end].decode("ascii")
    if not header.startswith("ply\nformat binary_little_endian 1.0\n"):
        raise ValueError("Unsupported PLY encoding")
    vertex_match = re.search(r"element vertex (\d+)\n", header)
    face_match = re.search(r"element face (\d+)\n", header)
    if not vertex_match or not face_match:
        raise ValueError("Missing PLY element counts")
    expected_properties = ["property float x", "property float y", "property float z",
                           "property uchar red", "property uchar green", "property uchar blue",
                           "property list uchar int vertex_indices"]
    if [line for line in header.splitlines() if line.startswith("property ")] != expected_properties:
        raise ValueError("Unsupported PLY property layout")
    nv, nf = int(vertex_match[1]), int(face_match[1])
    vd = np.dtype([("xyz", "<f4", 3), ("rgb", "u1", 3)])
    fd = np.dtype([("n", "u1"), ("indices", "<i4", 3)])
    if nv <= 0 or nf <= 0 or end + nv * vd.itemsize + nf * fd.itemsize != len(raw):
        raise ValueError("PLY counts do not match payload")
    vertices = np.frombuffer(raw, dtype=vd, count=nv, offset=end)["xyz"].astype(float)
    face_records = np.frombuffer(raw, dtype=fd, count=nf, offset=end + nv * vd.itemsize)
    faces = face_records["indices"].copy()
    if (not np.all(np.isfinite(vertices)) or np.any(face_records["n"] != 3)
            or np.any(faces < 0) or np.any(faces >= nv)):
        raise ValueError("Invalid vertices or triangle indices")
    return vertices, faces


def read_pose(raw: bytes) -> np.ndarray:
    values = np.fromstring(raw.decode("ascii"), sep=" ")
    if len(values) != 32 or not np.all(np.isfinite(values)):
        raise ValueError("Expected two finite four-by-four pose matrices")
    matrices = values.reshape(2, 4, 4)
    for matrix in matrices:
        if (not np.allclose(matrix[:3, 3], 0, atol=1e-8)
                or not np.isclose(matrix[3, 3], 1)
                or not np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=3e-6)
                or not np.isclose(np.linalg.det(matrix[:3, :3]), 1, atol=3e-6)):
            raise ValueError("Pose must be a rigid row-vector transform")
    return matrices[0] @ matrices[1]


def transform(vertices: np.ndarray, pose: np.ndarray) -> np.ndarray:
    return (np.c_[vertices, np.ones(len(vertices))] @ pose)[:, :3]


def mesh_audit(vertices: np.ndarray, faces: np.ndarray) -> tuple[dict, np.ndarray]:
    directed = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges, inverse, counts = np.unique(np.sort(directed, axis=1), axis=0,
                                       return_inverse=True, return_counts=True)
    signs = np.where(directed[:, 0] < directed[:, 1], 1, -1)
    winding_sums = np.bincount(inverse, weights=signs, minlength=len(edges))
    boundary = edges[counts == 1]
    boundary_vertices = np.unique(boundary)
    degrees = np.bincount(boundary.ravel(), minlength=len(vertices)) if len(boundary) else np.zeros(len(vertices))
    tris = vertices[faces]
    double_areas = np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
    return {
        "vertices": len(vertices), "faces": len(faces), "unique_edges": len(edges),
        "boundary_edges": len(boundary), "boundary_vertices": len(boundary_vertices),
        "boundary_vertex_degree_not_two": int(np.count_nonzero(degrees[boundary_vertices] != 2)),
        "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
        "inconsistent_internal_edge_winding": int(np.count_nonzero((counts == 2) & (winding_sums != 0))),
        "zero_area_triangles": int(np.count_nonzero(double_areas <= 1e-14)),
        "area_mm2_nominal": float(double_areas.sum() / 2),
        "raw_axis_extents_mm_nominal": np.ptp(vertices, axis=0).tolist(),
        "watertight": bool(len(boundary) == 0 and np.all(counts == 2)),
        "not_checked": ["self-intersection", "independent segmentation correctness", "raw-scan registration"],
    }, vertices[boundary_vertices]


def plane_segments(vertices: np.ndarray, faces: np.ndarray, axis: int, value: float) -> np.ndarray:
    if axis not in (0, 1, 2) or not np.isfinite(value):
        raise ValueError("Invalid section plane")
    tris = vertices[faces]
    distances = tris[:, :, axis] - value
    if np.any(np.all(distances == 0, axis=1)):
        raise ValueError("Plane contains an entire triangle; choose and record another plane")
    points = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        da, db = distances[:, a], distances[:, b]
        crosses = ((da < 0) & (db >= 0)) | ((db < 0) & (da >= 0))
        idx = np.flatnonzero(crosses)
        t = da[idx] / (da[idx] - db[idx])
        xyz = tris[idx, a] + t[:, None] * (tris[idx, b] - tris[idx, a])
        points.append((idx, xyz))
    counts = np.zeros(len(faces), dtype=int)
    ends = np.zeros((len(faces), 2, 3), dtype=float)
    for idx, xyz in points:
        if np.any(counts[idx] >= 2):
            raise ValueError("Ambiguous triangle intersection")
        ends[idx, counts[idx]] = xyz
        counts[idx] += 1
    segments = ends[counts == 2]
    segments = segments[np.linalg.norm(segments[:, 1] - segments[:, 0], axis=1) > 1e-12]
    if not len(segments):
        raise ValueError("Plane has no nonzero contour segments")
    return segments


def nearest_segment_distances(points: np.ndarray, segments: np.ndarray) -> np.ndarray:
    if (points.ndim != 2 or points.shape[1] != 3 or segments.ndim != 3
            or segments.shape[1:] != (2, 3) or not len(segments)
            or not np.all(np.isfinite(points)) or not np.all(np.isfinite(segments))):
        raise ValueError("Require finite 3D points and nonempty line segments")
    starts = segments[:, 0]
    directions = segments[:, 1] - starts
    squared_lengths = np.sum(directions ** 2, axis=1)
    if np.any(squared_lengths <= 0):
        raise ValueError("Zero-length target segment")
    result = []
    for offset in range(0, len(points), 128):
        delta = points[offset:offset + 128, None, :] - starts[None, :, :]
        t = np.clip(np.sum(delta * directions, axis=2) / squared_lengths, 0, 1)
        residual = delta - t[:, :, None] * directions
        result.append(np.sqrt(np.min(np.sum(residual ** 2, axis=2), axis=1)))
    return np.concatenate(result) if result else np.empty(0)


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    if (values.ndim != 1 or weights.shape != values.shape or not len(values)
            or not np.isfinite(q) or not 0 <= q <= 1 or np.any(weights <= 0)
            or not np.all(np.isfinite(weights)) or not np.all(np.isfinite(values))):
        raise ValueError("Invalid weighted quantile inputs")
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    return float(values[order[min(np.searchsorted(cumulative, q * cumulative[-1]), len(order) - 1)]])


def section_metrics(outer: np.ndarray, inner: np.ndarray) -> tuple[dict, np.ndarray]:
    midpoints = outer.mean(axis=1)
    lengths = np.linalg.norm(outer[:, 1] - outer[:, 0], axis=1)
    values = nearest_segment_distances(midpoints, inner)
    return {"outer_segment_count": len(outer), "inner_segment_count": len(inner),
            "outer_contour_length_mm": float(lengths.sum()),
            "arc_weighted_mean_gap_mm": float(np.average(values, weights=lengths)),
            "arc_weighted_p10_gap_mm": weighted_quantile(values, lengths, .1),
            "arc_weighted_median_gap_mm": weighted_quantile(values, lengths, .5),
            "arc_weighted_p90_gap_mm": weighted_quantile(values, lengths, .9)}, values


def subdivide_segments(segments: np.ndarray, parts: int = 4) -> np.ndarray:
    if not isinstance(parts, int) or parts < 1:
        raise ValueError("Require a positive integer subdivision count")
    direction = segments[:, 1] - segments[:, 0]
    edges = segments[:, 0, None, :] + np.linspace(0, 1, parts + 1)[None, :, None] * direction[:, None, :]
    return np.stack([edges[:, :-1], edges[:, 1:]], axis=2).reshape(-1, 2, 3)


def draw_section(outer: np.ndarray, inner: np.ndarray, axis: int, output: Path) -> None:
    axes = [a for a in range(3) if a != axis]
    lo, hi = outer[:, :, axes].min(axis=(0, 1)), outer[:, :, axes].max(axis=(0, 1))
    scale = min(620 / (hi[0] - lo[0]), 275 / (hi[1] - lo[1]))
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="720" height="420" viewBox="0 0 720 420">',
             '<rect width="720" height="420" fill="white"/>',
             '<g font-family="sans-serif" fill="#173742">',
             '<text x="22" y="28" font-size="18">An external contour and its separately supplied internal boundary</text>',
             '<text x="22" y="51" font-size="13">M3#83 GLN04-252-ULM2; central posed x section; nominal millimetres</text>']
    for segments, color in ((outer, "#196c73"), (inner, "#c6761c")):
        commands = []
        for ends in segments:
            xy = (ends[:, axes] - lo) * scale
            commands.append(f'M{25+xy[0,0]:.2f},{345-xy[0,1]:.2f}L{25+xy[1,0]:.2f},{345-xy[1,1]:.2f}')
        parts.append(f'<path d="{"".join(commands)}" fill="none" stroke="{color}" stroke-width="1.8"/>')
    parts += ['<text x="22" y="378" font-size="13">Teal: outer enamel surface. Orange: enamel-dentine junction.</text>',
              '<text x="22" y="400" font-size="11">Le Luyer et al. 2016; Osteotheque de Pessac, Universite de Bordeaux; curator S. Rottier. CC BY-NC 4.0.</text>',
              '</g></svg>']
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--out", type=Path, default=HERE / "derived" / "paired_tooth_surfaces")
    args = parser.parse_args()
    if args.fetch:
        fetch_reference()
    raw = ARCHIVE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Reference archive SHA-256 mismatch")
    meshes, audits, poses, boundaries, members = {}, {}, {}, {}, []
    with zipfile.ZipFile(ARCHIVE) as archive:
        for role in ("OES", "EDJ"):
            member = f"M3#83/{IDENTIFIER}_{role}.ply"
            pose_member = f"M3#83/{IDENTIFIER}_{role}_M3_83.pos"
            data, pose_data = archive.read(member), archive.read(pose_member)
            vertices, faces = read_ply(data)
            pose = read_pose(pose_data)
            audit, boundary = mesh_audit(vertices, faces)
            posed = transform(vertices, pose)
            audit["posed_axis_extents_mm_nominal"] = np.ptp(posed, axis=0).tolist()
            meshes[role], audits[role], poses[role], boundaries[role] = (posed, faces), audit, pose, boundary
            for name, content in ((member, data), (pose_member, pose_data)):
                members.append({"member": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
        readme = archive.read("readme_sf83.txt").decode("utf-8")
    if not np.array_equal(poses["OES"], poses["EDJ"]):
        raise ValueError("Source surfaces do not share the same pose")
    a, b = boundaries["OES"], boundaries["EDJ"]
    same_boundary = bool(a.shape == b.shape and np.array_equal(a[np.lexsort(a.T[::-1])], b[np.lexsort(b.T[::-1])]))
    stated_length = float(re.search(r"maximal length \(mm\)\s*:(\d+(?:\.\d+)?)", readme)[1])
    rows, quadrature = [], []
    args.out.mkdir(parents=True, exist_ok=True)
    for axis in (0, 1, 2):
        outer_vertices, outer_faces = meshes["OES"]
        value = float((outer_vertices[:, axis].min() + outer_vertices[:, axis].max()) / 2)
        outer = plane_segments(outer_vertices, outer_faces, axis, value)
        inner = plane_segments(*meshes["EDJ"], axis, value)
        baseline, base_values = section_metrics(outer, inner)
        refined, _ = section_metrics(subdivide_segments(outer), inner)
        quadrature.append({"plane_axis": "xyz"[axis], "subdivision_factor": 4,
                           "mean_gap_change_um": (refined["arc_weighted_mean_gap_mm"]
                                                  - baseline["arc_weighted_mean_gap_mm"]) * 1000})
        for shift in (0.0, -.05, -.02, .02, .05):
            altered = inner.copy()
            altered[:, :, (axis + 1) % 3] += shift
            metrics, values = section_metrics(outer, altered)
            rows.append({"plane_axis": "xyz"[axis], "plane_coordinate_mm": value,
                         "in_plane_shift_axis": "xyz"[(axis + 1) % 3], "synthetic_EDJ_shift_mm": shift,
                         "outer_surface_changed": False,
                         "mean_gap_change_um": (metrics["arc_weighted_mean_gap_mm"] - baseline["arc_weighted_mean_gap_mm"]) * 1000,
                         "max_absolute_point_gap_change_um": float(np.max(np.abs(values - base_values)) * 1000),
                         **metrics})
        if axis == 0:
            draw_section(outer, inner, axis, args.out / "paired_section.svg")
    with (args.out / "section_gap_sensitivity.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader(); writer.writerows(rows)
    summary = {
        "analysis": "paired-source-surface intake and sectional contour-gap sensitivity",
        "specimen": IDENTIFIER, "model_id": "M3#83", "doi": "10.18563/m3.sf.83",
        "associated_dataset_article": "https://doi.org/10.18563/m3.2.1.e1",
        "primary_methods_article": "https://doi.org/10.1371/journal.pone.0159688",
        "authors": "Le Luyer M, Coquerelle M, Rottier S, Bayle P (2016)",
        "collection": "Osteotheque de Pessac, Universite de Bordeaux, France",
        "curator": "Dr Stephane Rottier", "source_license": "CC-BY-NC-4.0",
        "derived_data_license": "CC-BY-NC-4.0", "archive_sha256": SOURCE_SHA256,
        "archive_bytes": len(raw), "archive_url": URL, "source_members": members,
        "source_selection": "first ascending M3 ID meeting adult, H maturation, wear1, no reconstructed-tip flag in source metadata",
        "source_claims": {"age": ">30", "sex": "M", "maturation": "H", "wear_stage": "1",
                          "specific_native_scan_voxel_size_um": None,
                          "study_native_voxel_range_um": [17.93, 36.18],
                          "segmentation": "source half-maximum threshold segmentation, manual corrections, constrained surface smoothing"},
        "nominal_units": "mm, source instructions/readme; no independent calibration",
        "readme_stated_maximal_length_mm": stated_length,
        "maximal_length_definition": "unspecified; raw and posed bounding-box extents retained without rescaling",
        "same_source_pose": True, "identical_boundary_vertex_sets": same_boundary,
        "surface_audits": audits,
        "volume_assessment": "not computed: individual crown surfaces have open cervical boundaries",
        "measurement": "arc-length-weighted midpoint-to-nearest-EDJ-segment distance within each plane; not 3D local thickness",
        "midpoint_quadrature_sensitivity": quadrature,
        "perturbation": "synthetic rigid shifts of EDJ contours in plane; not measured segmentation uncertainty or new anatomy",
        "qualification": "provisional source-defined geometry reference; not independently adjudicated tissue truth",
        "unassessed": ["microstructure", "material identity", "pulp/PDL", "cracks", "living human repair",
                       "photo reconstruction", "2-10 um repair-layer detection", "3D surface self-intersection"],
        "software": {"python": platform.python_version(), "numpy": np.__version__}, "rows": rows,
    }
    (args.out / "paired_surface_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"surface_audits": audits, "same_boundary": same_boundary,
                      "baseline_sections": [v for v in rows if v["synthetic_EDJ_shift_mm"] == 0]}, indent=2))


if __name__ == "__main__":
    main()
