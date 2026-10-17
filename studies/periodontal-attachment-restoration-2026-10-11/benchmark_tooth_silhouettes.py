"""Ideal orthographic silhouette baseline on a sampled public micro-CT tooth.

This is an outer-envelope proxy experiment, not photo reconstruction, enamel
segmentation, a patient target, or a biological regeneration result.
Requires NumPy and Pillow. No learned models, weights or private inputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import platform
import re
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, __version__ as pillow_version

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data" / "literature" / "dental-reference-ds-uct-002"
AXES = {0: "z", 1: "y", 2: "x"}


def largest_component(mask: np.ndarray) -> np.ndarray:
    """Six-connected component; retain no disconnected mounting material."""
    if mask.ndim != 3 or mask.dtype != np.bool_:
        raise ValueError("Expected a 3D Boolean occupancy array")
    visited = np.zeros_like(mask)
    largest = []
    shape = mask.shape
    for start in zip(*np.nonzero(mask)):
        if visited[start]:
            continue
        visited[start] = True
        queue = deque([start])
        members = []
        while queue:
            point = queue.popleft()
            members.append(point)
            for axis in range(3):
                for step in (-1, 1):
                    neighbor = list(point)
                    neighbor[axis] += step
                    if not 0 <= neighbor[axis] < shape[axis]:
                        continue
                    neighbor = tuple(neighbor)
                    if mask[neighbor] and not visited[neighbor]:
                        visited[neighbor] = True
                        queue.append(neighbor)
        if len(members) > len(largest):
            largest = members
    output = np.zeros_like(mask)
    if largest:
        output[tuple(np.array(largest).T)] = True
    return output


def fill_axial_holes(mask: np.ndarray) -> np.ndarray:
    """Explicit proxy: fill enclosed 2D holes, preserving open concavities."""
    output = []
    for plane in mask:
        # Padding guarantees a background seed even if an object reaches an edge.
        padded = np.pad(plane, 1)
        image = Image.fromarray(padded.astype(np.uint8) * 255).copy()
        ImageDraw.floodfill(image, (0, 0), 128)
        values = np.asarray(image)
        output.append((values != 128)[1:-1, 1:-1])
    return np.array(output, dtype=bool)


def visual_hull(shape: tuple, silhouettes: dict[int, np.ndarray]) -> np.ndarray:
    if len(shape) != 3 or any(n <= 0 for n in shape) or not silhouettes:
        raise ValueError("Require a positive 3D grid and at least one silhouette")
    result = np.ones(shape, dtype=bool)
    for axis, image in silhouettes.items():
        if axis not in AXES or image.dtype != np.bool_:
            raise ValueError("Invalid silhouette axis or type")
        expected = tuple(n for a, n in enumerate(shape) if a != axis)
        if image.shape != expected:
            raise ValueError("Silhouette dimensions disagree with grid")
        result &= np.expand_dims(image, axis)
    return result


def iou(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape or a.dtype != np.bool_ or b.dtype != np.bool_:
        raise ValueError("Require Boolean masks with equal shape")
    union = int(np.count_nonzero(a | b))
    return int(np.count_nonzero(a & b)) / union if union else 1.0


def score(reference: np.ndarray, candidate: np.ndarray, spacing_um: tuple) -> dict:
    if len(spacing_um) != 3 or any(not np.isfinite(s) or s <= 0 for s in spacing_um):
        raise ValueError("Require three positive finite voxel dimensions")
    overlap = iou(reference, candidate)
    n_ref = int(reference.sum())
    if n_ref == 0:
        raise ValueError("Reference is empty")
    voxel_mm3 = float(np.prod(np.array(spacing_um) / 1000))
    extra = int(np.count_nonzero(candidate & ~reference))
    missing = int(np.count_nonzero(reference & ~candidate))
    return {"volume_iou": overlap, "reference_proxy_volume_mm3": n_ref * voxel_mm3,
            "candidate_volume_mm3": int(candidate.sum()) * voxel_mm3,
            "excess_volume_mm3": extra * voxel_mm3,
            "missing_volume_mm3": missing * voxel_mm3,
            "excess_volume_percent_of_reference": extra / n_ref * 100,
            "missing_volume_percent_of_reference": missing / n_ref * 100}


def load_reference(manifest_path: Path) -> tuple[np.ndarray, float, dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    directory = manifest_path.parent / "sampled_slices"
    arrays = []
    files = [v for v in manifest["files"] if v["file"].endswith(".tiff")]
    indices = [int(Path(v["file"]).stem) for v in files]
    if len(files) < 3 or any(b - a != manifest["sample_stride_z"]
                             for a, b in zip(indices, indices[1:])):
        raise ValueError("Slice indices must be ordered and uniformly spaced")
    header_item = next(v for v in manifest["files"] if v["file"] == "Header.txt")
    header_raw = (directory / header_item["file"]).read_bytes()
    if hashlib.sha256(header_raw).hexdigest() != header_item["sha256"]:
        raise ValueError("Acquisition header hash mismatch")
    match = re.search(r"Pixel Size\s*=\s*([\d.]+)", header_raw.decode("utf-8-sig"))
    if not match:
        raise ValueError("Acquisition header lacks pixel size")
    pixel_um = float(match.group(1))
    if not np.isfinite(pixel_um) or pixel_um <= 0:
        raise ValueError("Invalid acquisition scale")
    for item in files:
        raw = (directory / item["file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Sampled slice hash mismatch")
        with Image.open(io.BytesIO(raw)) as image:
            if image.mode != "L":
                raise ValueError("Expected 8-bit grayscale reference")
            values = np.array(image)
        # Fixed four-by-four area mean. Preserve native intensity; no per-slice normalization.
        h, w = values.shape
        if h % 4 or w % 4:
            raise ValueError("Reference dimensions must be divisible by four")
        arrays.append(values.reshape(h // 4, 4, w // 4, 4).mean(axis=(1, 3)))
    return np.stack(arrays), pixel_um, manifest


def comparison_svg(reference: np.ndarray, candidate: np.ndarray, output: Path) -> None:
    """Small, code-native scientific figure; each cell retains its voxel coordinates."""
    index = int(np.argmax(reference.sum(axis=(1, 2))))
    truth, estimate = reference[index], candidate[index]
    h, w = truth.shape
    colors = np.zeros((*truth.shape, 3), dtype=np.uint8) + 246
    colors[truth & estimate] = (43, 111, 111)
    colors[estimate & ~truth] = (220, 123, 44)
    colors[truth & ~estimate] = (181, 40, 65)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="340" viewBox="0 0 760 340">',
             '<rect width="760" height="340" fill="white"/>',
             '<g font-family="sans-serif" fill="#172e36">',
             '<text x="20" y="28" font-size="19">Same three outlines; excess reconstructed volume</text>',
             '<text x="20" y="53" font-size="13">Public micro-CT proxy + ideal silhouettes; no photographs or repair experiment</text>']
    scale = min(620 / w, 200 / h)
    for y in range(h):
        x = 0
        while x < w:
            end = x + 1
            while end < w and np.array_equal(colors[y, end], colors[y, x]):
                end += 1
            if truth[y, x] or estimate[y, x]:
                c = colors[y, x]
                color = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
                parts.append(f'<rect x="{20+x*scale:.2f}" y="{75+y*scale:.2f}" width="{(end-x)*scale+.02:.2f}" height="{scale+.02:.2f}" fill="{color}"/>')
            x = end
    excess = np.count_nonzero(candidate & ~reference) / np.count_nonzero(reference) * 100
    parts += ['<text x="310" y="130" font-size="18">Supplied outlines match exactly</text>',
              f'<text x="310" y="164" font-size="22">Whole-volume excess: {excess:.1f}%</text>',
              '<text x="310" y="198" font-size="13">One specimen; middle segmentation threshold</text>',
              '<text x="310" y="222" font-size="13">The reconstruction fills space the outlines do not exclude.</text>']
    parts += [f'<text x="20" y="294" font-size="13">Axial slice index {index}; green = shared, orange = excess, red = missing</text>',
              '<text x="20" y="318" font-size="13">Slice thickness on screen is not a tissue-thickness measurement.</text>', '</g></svg>']
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DATA / "sampled_reference_manifest.json")
    parser.add_argument("--out", type=Path, default=HERE / "derived" / "tooth_silhouette_pilot")
    args = parser.parse_args()
    intensities, native_um, manifest = load_reference(args.manifest)
    spacing = (native_um * manifest["sample_stride_z"], native_um * 4, native_um * 4)
    rows, references = [], {}
    for threshold in (65, 80, 95):
        raw = intensities >= threshold
        component = largest_component(raw)
        filled = fill_axial_holes(component)
        if not filled.any():
            raise ValueError("Reference segmentation is empty")
        coords = np.nonzero(filled)
        crop = tuple(slice(max(int(v.min()) - 1, 0), min(int(v.max()) + 2, n))
                     for v, n in zip(coords, filled.shape))
        reference = filled[crop]
        references[threshold] = {
            "threshold": threshold, "grid_shape_zyx": list(reference.shape),
            "crop_bounds_zyx": [[s.start, s.stop] for s in crop],
            "threshold_positive_voxels_before_component_filter": int(raw.sum()),
            "largest_component_voxels": int(component.sum()),
            "enclosed_axial_hole_voxels_filled": int(filled.sum() - component.sum()),
        }
        for count in (1, 2, 3):
            for axes in itertools.combinations(range(3), count):
                silhouettes = {a: reference.any(axis=a) for a in axes}
                candidate = visual_hull(reference.shape, silhouettes)
                metrics = score(reference, candidate, spacing)
                fits = [iou(reference.any(axis=a), candidate.any(axis=a)) for a in axes]
                holdouts = [iou(reference.any(axis=a), candidate.any(axis=a))
                            for a in range(3) if a not in axes]
                rows.append({"threshold": threshold,
                             "supplied_projection_axes": "+".join(AXES[a] for a in axes),
                             "supplied_axis_count": count,
                             "minimum_supplied_silhouette_iou": min(fits),
                             "minimum_withheld_silhouette_iou": min(holdouts) if holdouts else None,
                             **metrics})
                if threshold == 80 and count == 3:
                    args.out.mkdir(parents=True, exist_ok=True)
                    comparison_svg(reference, candidate, args.out / "hull_cross_section.svg")
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "silhouette_metrics.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    result = {
        "analysis_type": "single-public-specimen ideal orthographic silhouette proxy",
        "doi": manifest["doi"], "source_license": manifest["license"],
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "source_archive_md5_verified": manifest["archive_md5_verified"],
        "source_members": manifest["files"],
        "sampled_slice_count": len(manifest["files"]) - 1,
        "native_header_pixel_size_um": native_um,
        "effective_voxel_spacing_zyx_um": list(spacing),
        "assumption": "header scalar pixel size treated as isotropic before subsampling",
        "segmentation": "4x4 area mean; fixed thresholds; largest six-connected component; enclosed axial holes filled",
        "optimistic_information_supplied": "perfect outlines, poses, scale, full-reference crop/bounding extent; roots exposed",
        "unassessed": ["clinical health/intactness", "photographic reconstruction accuracy",
                       "enamel or dentin thickness", "DEJ", "cracks", "gingiva/PDL",
                       "native voxel-resolution accuracy", "regeneration", "population generalization"],
        "references": list(references.values()),
        "software": {"python": platform.python_version(), "numpy": np.__version__,
                     "pillow": pillow_version},
        "rows": rows,
    }
    (args.out / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"spacing_um": spacing, "results": [r for r in rows if r["supplied_axis_count"] == 3]}, indent=2))


if __name__ == "__main__":
    main()
