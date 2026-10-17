"""Geometry/provenance failures that could falsely support restoration claims."""
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "studies" / "periodontal-attachment-restoration-2026-10-11"


def load(name):
    spec = importlib.util.spec_from_file_location(name, STUDY / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch = load("fetch_tooth_reference")
try:
    import numpy as np
    bench = load("benchmark_tooth_silhouettes")
except ImportError:
    np = bench = None


class ReferenceDownloadTests(unittest.TestCase):
    def member(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("source/0001.tiff", b"verified reference payload" * 100)
        raw = out.getvalue()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            info = archive.infolist()[0]
        return raw, info

    def test_range_download_decodes_and_checks_member(self):
        raw, info = self.member()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(fetch, "fetch_range", return_value=raw), patch.object(fetch, "DEST", Path(directory)):
                result = fetch.fetch_member(info)
            self.assertEqual(result["bytes"], 2600)
            self.assertEqual(len(result["sha256"]), 64)
            self.assertTrue((Path(directory) / "sampled_slices" / "0001.tiff").is_file())

    def test_wrong_crc_rejects_before_writing(self):
        raw, info = self.member()
        info.CRC ^= 1
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(fetch, "fetch_range", return_value=raw), patch.object(fetch, "DEST", Path(directory)):
                with self.assertRaisesRegex(ValueError, "CRC"):
                    fetch.fetch_member(info)
            self.assertFalse((Path(directory) / "sampled_slices").exists())

    def test_invalid_range_never_contacts_server(self):
        with patch.object(fetch, "urlopen") as request:
            with self.assertRaises(ValueError):
                fetch.fetch_range(-1, 2)
            request.assert_not_called()


@unittest.skipUnless(bench is not None, "Optional NumPy/Pillow study runtime unavailable")
class ToothSilhouetteTests(unittest.TestCase):
    def test_perfect_outlines_can_hide_wrong_volume(self):
        reference = np.ones((5, 5, 5), dtype=bool)
        reference[2, 2, 2] = False
        candidate = bench.visual_hull(reference.shape, {a: reference.any(axis=a) for a in range(3)})
        for a in range(3):
            self.assertEqual(bench.iou(reference.any(axis=a), candidate.any(axis=a)), 1)
        self.assertAlmostEqual(bench.iou(reference, candidate), 124 / 125)

    def test_more_views_never_increase_exact_visual_hull(self):
        reference = np.zeros((5, 6, 7), dtype=bool)
        reference[1:4, 2:5, 3:6] = True
        previous = np.ones_like(reference)
        for count in (1, 2, 3):
            hull = bench.visual_hull(reference.shape, {a: reference.any(axis=a) for a in range(count)})
            self.assertFalse(np.any(hull & ~previous))
            self.assertFalse(np.any(reference & ~hull))
            previous = hull

    def test_hole_fill_preserves_background_and_open_concavity(self):
        reference = np.zeros((1, 7, 7), dtype=bool)
        reference[0, 1:6, 1:6] = True
        reference[0, 3, 3] = False
        reference[0, 1:3, 1] = False
        filled = bench.fill_axial_holes(reference)
        self.assertTrue(filled[0, 3, 3])
        self.assertFalse(filled[0, 1, 1])
        self.assertFalse(filled[0, 0, 0])
        self.assertEqual(int(filled.sum()), int(reference.sum()) + 1)

    def test_largest_component_drops_disconnected_mounting_object(self):
        reference = np.zeros((4, 5, 6), dtype=bool)
        reference[0:2, 0:2, 0:2] = True
        reference[3, 4, 5] = True
        self.assertEqual(int(bench.largest_component(reference).sum()), 8)

    def test_anisotropic_volume_uses_all_three_spacings(self):
        reference = np.ones((2, 2, 2), dtype=bool)
        score = bench.score(reference, reference, (1000, 2000, 3000))
        self.assertEqual(score["reference_proxy_volume_mm3"], 48)
        self.assertEqual(score["missing_volume_mm3"], 0)

    def test_invalid_spacing_and_silhouette_rejected(self):
        reference = np.ones((2, 2, 2), dtype=bool)
        for value in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                bench.score(reference, reference, (value, 1, 1))
        with self.assertRaises(ValueError):
            bench.visual_hull((2, 2, 2), {0: np.ones((3, 2), dtype=bool)})

    def test_outer_shape_does_not_identify_internal_tissue_label(self):
        outer = np.ones((5, 5, 5), dtype=bool)
        dentin_a = np.zeros_like(outer)
        dentin_a[1:4, 1:4, 1:4] = True
        dentin_b = np.zeros_like(outer)
        dentin_b[2, 2, 2] = True
        enamel_a, enamel_b = outer & ~dentin_a, outer & ~dentin_b
        self.assertNotEqual(int(enamel_a.sum()), int(enamel_b.sum()))
        for axis in range(3):
            self.assertTrue(np.array_equal((dentin_a | enamel_a).any(axis),
                                           (dentin_b | enamel_b).any(axis)))


if __name__ == "__main__":
    unittest.main()
