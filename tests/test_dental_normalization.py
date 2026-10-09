"""Optional package integration against constructed, not biological, counts."""

import importlib.util
import sys
import unittest
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1] / "studies/dental-regeneration-2026-10-09"
AVAILABLE = all(importlib.util.find_spec(p) is not None for p in ("pydeseq2", "numpy", "pandas"))
if AVAILABLE:
    sys.path.insert(0, str(STUDY))
    import numpy as np
    import pandas as pd
    import rna_normalization_diagnostics as diagnostics


@unittest.skipUnless(AVAILABLE, "Optional isolated PyDESeq2 study runtime")
class NormalizationTests(unittest.TestCase):
    def test_known_library_multiplier_is_removed_by_both_methods(self):
        genes = list(diagnostics.intake.PANEL)
        base = np.arange(1, len(genes) + 1)
        data = np.arange(1, 7)[:, None] * base[None, :]
        counts = pd.DataFrame(data, index=[r[0] for r in diagnostics.intake.LABELS], columns=genes)
        methods, total, ratio = diagnostics.normalize(counts)
        expected = np.arange(1, 7) / np.exp(np.log(np.arange(1, 7)).mean())
        np.testing.assert_allclose(total, expected)
        np.testing.assert_allclose(ratio, expected)
        for values in methods.values():
            np.testing.assert_allclose(values, np.tile(values[0], (6, 1)))
            panel = diagnostics.describe(values, genes)["panel"]
            self.assertAlmostEqual(panel[0]["treatment_in_WT"]["log2_mean_ratio_pc1"], 0)

    def test_invalid_factor_shape_zero_nan_and_inf_fail(self):
        for values in ([1], [0] * 6, [float("nan")] * 6, [float("inf")] * 6):
            with self.subTest(values=values), self.assertRaises(ValueError):
                diagnostics.validate_factors(values, 6)

    def test_no_positive_pca_features_is_an_explicit_gap(self):
        values = np.zeros((6, len(diagnostics.intake.PANEL)))
        with self.assertRaisesRegex(ValueError, "No genes positive"):
            diagnostics.describe(values, list(diagnostics.intake.PANEL))

    def test_normalization_cannot_silently_enter_iterative_model_fitting(self):
        counts = pd.DataFrame(np.eye(6, dtype=int), index=[r[0] for r in diagnostics.intake.LABELS])
        with self.assertRaisesRegex(ValueError, "iterative fallback is excluded"):
            diagnostics.normalize(counts)


if __name__ == "__main__":
    unittest.main()
