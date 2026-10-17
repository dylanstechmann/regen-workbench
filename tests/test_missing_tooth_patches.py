"""Check hidden-target isolation and the geometry/error accounting used by the pilot."""
import importlib.util
from pathlib import Path
import unittest

try:
    import numpy as np
except ImportError:
    np = None

if np is not None:
    path = Path(__file__).resolve().parents[1] / "studies" / "periodontal-attachment-restoration-2026-10-11" / "benchmark_missing_tooth_patches.py"
    spec = importlib.util.spec_from_file_location("patch_benchmark", path)
    patch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patch)


@unittest.skipUnless(np is not None, "Optional NumPy study runtime unavailable")
class MissingToothPatchTests(unittest.TestCase):
    def grid_mesh(self):
        axis = np.linspace(-2, 2, 17)
        xx, yy = np.meshgrid(axis, axis)
        vertices = np.c_[xx.ravel(), yy.ravel(), (2 + xx + 2 * yy).ravel()]
        faces = []
        for y in range(len(axis) - 1):
            for x in range(len(axis) - 1):
                a = y * len(axis) + x
                faces += [[a, a + 1, a + len(axis)], [a + 1, a + len(axis) + 1, a + len(axis)]]
        return axis, vertices, np.array(faces)

    def test_disk_inside_large_triangle_is_held_out(self):
        vertices = np.array([[-10, -10, 0], [10, -10, 0], [0, 10, 0]], dtype=float)
        faces = np.array([[0, 1, 2]])
        self.assertTrue(patch.triangle_disk_intersections(vertices, faces, np.zeros(2), .1)[0])

    def test_edge_crossing_and_outside_triangle(self):
        vertices = np.array([[-2, .05, 0], [2, .05, 0], [0, 3, 0],
                             [2, 2, 0], [3, 2, 0], [2, 3, 0]], dtype=float)
        result = patch.triangle_disk_intersections(vertices, np.array([[0, 1, 2], [3, 4, 5]]), np.zeros(2), .1)
        np.testing.assert_array_equal(result, [True, False])

    def test_retained_mesh_has_no_surface_inside_withheld_disk(self):
        axis, vertices, faces = self.grid_mesh()
        mask = patch.triangle_disk_intersections(vertices, faces, np.zeros(2), .6)
        visible = patch.top_grid(vertices, faces[~mask], axis, axis)
        xx, yy = np.meshgrid(axis, axis)
        self.assertFalse(np.any(np.isfinite(visible)[xx * xx + yy * yy <= .6 ** 2]))

    def test_mutating_private_target_heights_cannot_change_visible_input(self):
        axis, vertices, faces = self.grid_mesh()
        removed = patch.triangle_disk_intersections(vertices, faces, np.zeros(2), .6)
        retained_faces = faces[~removed]
        baseline_visible = patch.top_grid(vertices, retained_faces, axis, axis)
        private = np.setdiff1d(np.unique(faces[removed]), np.unique(retained_faces))
        self.assertGreater(len(private), 0)
        altered = vertices.copy()
        altered[private, 2] += 1000
        changed_visible = patch.top_grid(altered, retained_faces, axis, axis)
        np.testing.assert_allclose(changed_visible, baseline_visible, equal_nan=True)
        full_a = patch.top_grid(vertices, faces, axis, axis)
        full_b = patch.top_grid(altered, faces, axis, axis)
        self.assertGreater(np.nanmax(np.abs(full_a - full_b)), 999)

    def test_raster_preserves_an_analytic_plane(self):
        axis, vertices, faces = self.grid_mesh()
        xx, yy = np.meshgrid(axis, axis)
        values = patch.top_grid(vertices, faces, axis, axis)
        np.testing.assert_allclose(values, 2 + xx + 2 * yy, atol=1e-12)

    def test_raster_uses_top_envelope_with_overlapping_surfaces(self):
        vertices = np.array([[0, 0, 1], [2, 0, 1], [0, 2, 1],
                             [0, 0, 3], [2, 0, 3], [0, 2, 3]], dtype=float)
        axis = np.array([.25, .5])
        values = patch.top_grid(vertices, np.array([[0, 1, 2], [5, 4, 3]]), axis, axis)
        np.testing.assert_allclose(values, 3)

    def test_quadratic_can_recover_known_quadratic_from_an_annulus(self):
        axis = np.linspace(-2, 2, 17)
        xx, yy = np.meshgrid(axis, axis)
        xy = np.c_[xx.ravel(), yy.ravel()]
        visible = np.linalg.norm(xy, axis=1) > 1
        truth_function = lambda p: 1 + p[:, 0] + 2 * p[:, 1] + 3 * p[:, 0] ** 2 - p[:, 0] * p[:, 1] + .2 * p[:, 1] ** 2
        query = xy[~visible]
        predicted, receipt = patch.fit_predict(xy[visible], truth_function(xy[visible]), query, np.zeros(2), 2., 2)
        np.testing.assert_allclose(predicted, truth_function(query), atol=1e-12)
        self.assertEqual(len(receipt["coefficients"]), 6)

    def test_collinear_support_is_rejected(self):
        xy = np.c_[np.arange(20), np.zeros(20)]
        with self.assertRaisesRegex(ValueError, "rank-deficient"):
            patch.fit_predict(xy, np.arange(20.), np.zeros((1, 2)), np.zeros(2), 1., 1)

    def test_volume_excess_and_deficit_do_not_cancel(self):
        result = patch.score_heights(np.array([1., -1.]), np.zeros(2), .5)
        self.assertEqual(result["mean_signed_error_mm"], 0)
        self.assertEqual(result["mae_mm"], 1)
        self.assertEqual(result["excess_envelope_volume_mm3"], .5)
        self.assertEqual(result["deficit_envelope_volume_mm3"], .5)

    def test_incomplete_predictions_are_preserved_as_unscored(self):
        result = patch.score_heights(np.array([0., np.nan]), np.zeros(2), 1)
        self.assertEqual(result["status"], "unscored_incomplete_coverage")
        self.assertEqual(result["finite_prediction_count"], 1)
        self.assertIsNone(result["mae_mm"])

    def test_incomplete_reference_does_not_become_a_favorable_score(self):
        result = patch.score_heights(np.zeros(2), np.array([0., np.nan]), 1)
        self.assertEqual(result["reference_hit_count"], 1)
        self.assertEqual(result["status"], "unscored_incomplete_coverage")

    def test_unit_scaling_changes_linear_error_and_cubic_volume(self):
        a = patch.score_heights(np.array([.2]), np.array([.1]), .25)
        b = patch.score_heights(np.array([200.]), np.array([100.]), 250000.)
        self.assertAlmostEqual(b["mae_mm"] / a["mae_mm"], 1000)
        self.assertAlmostEqual(b["excess_envelope_volume_mm3"] / a["excess_envelope_volume_mm3"], 1e9)


if __name__ == "__main__":
    unittest.main()
