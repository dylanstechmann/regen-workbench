"""Guard against incorrect units, hidden-boundary claims and invalid mesh data."""
import importlib.util
from pathlib import Path
import struct
import unittest

try:
    import numpy as np
except ImportError:
    np = None

STUDY = Path(__file__).resolve().parents[1] / "studies" / "periodontal-attachment-restoration-2026-10-11"
if np is not None:
    spec = importlib.util.spec_from_file_location("paired", STUDY / "analyze_paired_tooth_surfaces.py")
    paired = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(paired)


@unittest.skipUnless(np is not None, "Optional NumPy study runtime unavailable")
class PairedToothSurfaceTests(unittest.TestCase):
    def ply(self, bad_index=False, nonfinite=False):
        header = ("ply\nformat binary_little_endian 1.0\nelement vertex 3\n"
                  "property float x\nproperty float y\nproperty float z\n"
                  "property uchar red\nproperty uchar green\nproperty uchar blue\n"
                  "element face 1\nproperty list uchar int vertex_indices\nend_header\n").encode()
        vertices = [(0., 0., 0.), (1., 0., 0.), (0., 1., float("nan") if nonfinite else 0.)]
        payload = b"".join(struct.pack("<3f3B", *v, 0, 0, 0) for v in vertices)
        return header + payload + struct.pack("<B3i", 3, 0, 1, 7 if bad_index else 2)

    def test_ply_preserves_coordinates_and_exposes_open_surface(self):
        vertices, faces = paired.read_ply(self.ply())
        audit, boundary = paired.mesh_audit(vertices, faces)
        self.assertEqual(audit["area_mm2_nominal"], .5)
        self.assertEqual(audit["boundary_edges"], 3)
        self.assertFalse(audit["watertight"])
        self.assertEqual(len(boundary), 3)

    def test_ply_bad_indices_nonfinite_and_truncated_input_rejected(self):
        for raw in (self.ply(bad_index=True), self.ply(nonfinite=True), self.ply()[:-1]):
            with self.assertRaises(ValueError):
                paired.read_ply(raw)

    def test_closed_tetrahedron_has_no_boundary(self):
        vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
        faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
        audit, boundary = paired.mesh_audit(vertices, faces)
        self.assertTrue(audit["watertight"])
        self.assertEqual(audit["inconsistent_internal_edge_winding"], 0)
        self.assertEqual(len(boundary), 0)

    def test_degenerate_face_reported(self):
        vertices = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=float)
        audit, _ = paired.mesh_audit(vertices, np.array([[0, 1, 2]]))
        self.assertEqual(audit["zero_area_triangles"], 1)

    def test_pose_uses_row_translation_without_changing_length(self):
        matrix = np.eye(4)
        matrix[3, :3] = [4, 5, 6]
        raw = (" ".join(str(v) for v in np.r_[np.eye(4).ravel(), matrix.ravel()])).encode()
        pose = paired.read_pose(raw)
        points = np.array([[0, 0, 0], [3, 4, 0]], dtype=float)
        altered = paired.transform(points, pose)
        np.testing.assert_allclose(altered[0], [4, 5, 6])
        self.assertAlmostEqual(np.linalg.norm(altered[1] - altered[0]), 5)

    def test_pose_with_scale_rejected(self):
        matrix = np.eye(4)
        matrix[0, 0] = 1000
        raw = (" ".join(str(v) for v in np.r_[np.eye(4).ravel(), matrix.ravel()])).encode()
        with self.assertRaises(ValueError):
            paired.read_pose(raw)

    def test_plane_triangle_intersection_analytic(self):
        vertices = np.array([[-1, 0, 0], [1, 0, 0], [1, 2, 0]], dtype=float)
        segments = paired.plane_segments(vertices, np.array([[0, 1, 2]]), 0, 0.)
        np.testing.assert_allclose(segments[0, :, 0], 0)
        self.assertAlmostEqual(np.linalg.norm(segments[0, 1] - segments[0, 0]), 1.)

    def test_coplanar_plane_refused(self):
        vertices = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
        with self.assertRaisesRegex(ValueError, "entire triangle"):
            paired.plane_segments(vertices, np.array([[0, 1, 2]]), 0, 0.)

    def test_segment_distance_handles_projection_and_endpoint(self):
        points = np.array([[0, 1, 0], [3, 0, 0]], dtype=float)
        segments = np.array([[[-1, 0, 0], [1, 0, 0]]], dtype=float)
        np.testing.assert_allclose(paired.nearest_segment_distances(points, segments), [1, 2])

    def test_same_outer_contour_different_internal_boundary(self):
        outer = np.array([[[0, 2, 0], [1, 2, 0]]], dtype=float)
        inner = np.array([[[0, 0, 0], [1, 0, 0]]], dtype=float)
        original = outer.copy()
        baseline, _ = paired.section_metrics(outer, inner)
        shifted = inner + np.array([0, .05, 0])
        altered, _ = paired.section_metrics(outer, shifted)
        np.testing.assert_array_equal(outer, original)
        self.assertAlmostEqual((baseline["arc_weighted_mean_gap_mm"] - altered["arc_weighted_mean_gap_mm"]) * 1000, 50)

    def test_arc_weighting_and_subdivision_preserve_constant_gap(self):
        outer = np.array([[[0, 1, 0], [1, 1, 0]], [[1, 1, 0], [4, 1, 0]]], dtype=float)
        inner = np.array([[[0, 0, 0], [4, 0, 0]]], dtype=float)
        refined = paired.subdivide_segments(outer)
        result, _ = paired.section_metrics(refined, inner)
        self.assertEqual(len(refined), 8)
        self.assertAlmostEqual(result["outer_contour_length_mm"], 4)
        self.assertAlmostEqual(result["arc_weighted_mean_gap_mm"], 1)
        self.assertEqual(paired.weighted_quantile(np.array([1., 3.]), np.array([9., 1.]), .5), 1)

    def test_invalid_weights_and_degenerate_target_rejected(self):
        for weights in (np.array([0.]), np.array([float("nan")]), np.array([float("inf")])):
            with self.assertRaises(ValueError):
                paired.weighted_quantile(np.array([1.]), weights, .5)
        with self.assertRaises(ValueError):
            paired.nearest_segment_distances(np.zeros((1, 3)), np.zeros((1, 2, 3)))


if __name__ == "__main__":
    unittest.main()
