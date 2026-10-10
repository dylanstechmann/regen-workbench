import gzip
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(os.environ.get("NATIVE_PDLS_MARKER_SCRIPT", str(
    Path(__file__).resolve().parents[1] / "studies" / "dental-regeneration-2026-10-09" / "summarize_native_pdls_markers.py")))
SPEC = importlib.util.spec_from_file_location("summarize_native_pdls_markers", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
try:
    import numpy as np
    from scipy.sparse import csr_matrix
    SCIENTIFIC_LIBRARIES = True
except ImportError:
    SCIENTIFIC_LIBRARIES = False


class NativeMarkerBindingTests(unittest.TestCase):
    def test_hash_changed_inputs_and_parent_path_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "matrix.gz"
            path.write_bytes(b"original")
            record = {"local_path_relative_to_data": "matrix.gz", "sha256": MODULE.digest(path)}
            self.assertEqual(MODULE.verified_path(root, record), path.resolve())
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Input hash"):
                MODULE.verified_path(root, record)
            with self.assertRaisesRegex(ValueError, "leaves data"):
                MODULE.verified_path(root, {**record, "local_path_relative_to_data": "../outside.gz"})

    def test_frozen_panel_requires_unique_symbols_and_original_screen(self):
        panel_path = SCRIPT.with_name("native_marker_panel.json")
        panel, symbols, _ = MODULE.load_panel(panel_path)
        self.assertEqual(len(symbols), 45)
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "panel.json"
            panel["control_contexts"][0]["symbols"][0] = panel["bulk_existing"][0]
            changed.write_text(json.dumps(panel), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "45-symbol"):
                MODULE.load_panel(changed)
            panel = json.loads(panel_path.read_text(encoding="utf-8"))
            panel["bulk_existing"][0] = "ANOTHER_UNIQUE_SYMBOL"
            changed.write_text(json.dumps(panel), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "45-symbol"):
                MODULE.load_panel(changed)
            panel = json.loads(panel_path.read_text(encoding="utf-8"))
            panel["sensitivity_screen"]["minimum_detected_gene_expression_features"] = 199
            changed.write_text(json.dumps(panel), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "screen has changed"):
                MODULE.load_panel(changed)

    def test_feature_type_and_identifier_integrity_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "features.gz"
            path.write_bytes(gzip.compress(b"ENSG1\tPOSTN\n"))
            with self.assertRaisesRegex(ValueError, "Feature type"):
                MODULE.load_labels(path, "features")
            path.write_bytes(gzip.compress(b"ENSG1\tPOSTN\tGene Expression\nENSG1\tOTHER\tGene Expression\n"))
            with self.assertRaisesRegex(ValueError, "duplicated"):
                MODULE.load_labels(path, "features")


@unittest.skipUnless(SCIENTIFIC_LIBRARIES, "NumPy and SciPy required")
class NativeMarkerNumericalTests(unittest.TestCase):
    def test_screen_boundary_overlap_and_zero_total_accounting(self):
        features = [{"id": str(i), "symbol": "MT-CO1" if i == 0 else "GENE" + str(i), "type": "Gene Expression"}
                    for i in range(200)]
        values = np.ones((200, 5))
        values[199, 1] = 0  # 199 detected: fails.
        values[0, 2] = 30  # More than 10% mitochondrial: fails.
        values[:, 3] = 9
        values[0, 3] = 199  # Exactly 199/(199 + 199*9) = 10%: passes.
        values[:, 4] = 0  # Undefined fraction/abundance, excluded from screen.
        metrics = MODULE.cell_metrics(csr_matrix(values), features)
        self.assertEqual(metrics["passes_sensitivity_screen"].tolist(), [True, False, False, True, False])
        accounting = MODULE.summarize_screen(metrics)
        self.assertEqual(accounting["all_barcodes"], 5)
        self.assertEqual(accounting["source_rule_sensitivity_retained"], 2)
        self.assertEqual(accounting["zero_gene_expression_total"], 1)
        self.assertEqual(accounting["excluded_union"], 3)
        self.assertTrue(np.isnan(metrics["mitochondrial_fraction"][4]))

    def test_missing_ambiguous_and_measured_zero_remain_distinct(self):
        features = [{"id": "A", "symbol": "ZERO", "type": "Gene Expression"},
                    {"id": "B", "symbol": "DUP", "type": "Gene Expression"},
                    {"id": "C", "symbol": "DUP", "type": "Gene Expression"},
                    {"id": "D", "symbol": "PROTEIN", "type": "Antibody Capture"}]
        matrix = csr_matrix([[0, 0], [1, 0], [0, 2], [1000, 2000]])
        metrics = {"total": np.array([1., 2.]), "passes_sensitivity_screen": np.array([True, True])}
        symbols = ["ZERO", "DUP", "MISSING", "PROTEIN"]
        rows = MODULE.marker_metrics(matrix, features, symbols, dict.fromkeys(symbols, "fixture"), metrics, "GSM_fixture", "unknown")
        all_rows = {row["gene_symbol"]: row for row in rows if row["screen"] == "all_barcodes"}
        self.assertEqual(all_rows["ZERO"]["detection_fraction"], 0)
        self.assertEqual(all_rows["ZERO"]["mean_log1p_entry_cp10k"], 0)
        self.assertEqual(all_rows["DUP"]["feature_status"], "ambiguous_symbol")
        self.assertEqual(all_rows["DUP"]["feature_ids"], ["B", "C"])
        self.assertIsNone(all_rows["DUP"]["mean_log1p_entry_cp10k"])
        self.assertEqual(all_rows["MISSING"]["feature_status"], "missing_feature")
        self.assertIsNone(all_rows["MISSING"]["detection_fraction"])
        self.assertEqual(all_rows["PROTEIN"]["feature_status"], "non_gene_expression_feature")

    def test_protein_counts_do_not_enter_gene_or_mitochondrial_denominator(self):
        features = [{"id": "A", "symbol": "MT-CO1", "type": "Gene Expression"},
                    {"id": "B", "symbol": "POSTN", "type": "Gene Expression"},
                    {"id": "C", "symbol": "OTHER", "type": "Antibody Capture"}]
        matrix = csr_matrix([[1, 0], [9, 0], [100000, 100000]])
        metrics = MODULE.cell_metrics(matrix, features, minimum_features=2)
        self.assertEqual(metrics["total"].tolist(), [10, 0])
        self.assertEqual(metrics["detected_features"].tolist(), [2, 0])
        self.assertEqual(metrics["passes_sensitivity_screen"].tolist(), [True, False])
        rows = MODULE.marker_metrics(matrix, features, ["POSTN"], {"POSTN": "fixture"}, metrics, "GSM_fixture", "unknown")
        self.assertEqual(rows[0]["n_barcodes"], 2)
        self.assertEqual(rows[0]["n_abundance_defined"], 1)
        self.assertEqual(rows[0]["detection_fraction"], .5)
        self.assertAlmostEqual(rows[0]["mean_log1p_entry_cp10k"], np.log1p(9000))

    def test_empty_sensitivity_denominator_stays_undefined(self):
        features = [{"id": "A", "symbol": "POSTN", "type": "Gene Expression"}]
        matrix = csr_matrix([[1, 1]])
        metrics = {"total": np.array([2., 2.]), "passes_sensitivity_screen": np.array([False, False])}
        rows = MODULE.marker_metrics(matrix, features, ["POSTN"], {"POSTN": "fixture"}, metrics, "GSM_fixture", "unknown")
        self.assertEqual(rows[1]["n_barcodes"], 0)
        self.assertIsNone(rows[1]["detection_fraction"])
        self.assertIsNone(rows[1]["mean_log1p_entry_cp10k"])

    def test_nonfinite_negative_fractional_and_missing_mito_context_fail(self):
        features = [{"id": "A", "symbol": "MT-CO1", "type": "Gene Expression"}]
        for value in (np.nan, -1., .5):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "integer-like"):
                MODULE.cell_metrics(csr_matrix([[value]]), features)
        with self.assertRaisesRegex(ValueError, "MT-"):
            MODULE.cell_metrics(csr_matrix([[1]]), [{"id": "A", "symbol": "OTHER", "type": "Gene Expression"}])


if __name__ == "__main__":
    unittest.main()
