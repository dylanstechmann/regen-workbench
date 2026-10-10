import gzip
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(os.environ.get("PDLS_MATRIX_AUDIT_SCRIPT", str(
    Path(__file__).resolve().parents[1] / "studies" / "dental-regeneration-2026-10-09" / "audit_pdls_maturity_matrices.py")))
SPEC = importlib.util.spec_from_file_location("audit_pdls_maturity_matrices", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
try:
    import numpy
    import scipy
    SCIENTIFIC_LIBRARIES = True
except ImportError:
    SCIENTIFIC_LIBRARIES = False


class MatrixIntakeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def compressed(self, name, text):
        path = self.root / name
        path.write_bytes(gzip.compress(text.encode("ascii")))
        return path

    def test_gzip_crc_and_expansion_bounds_are_checked(self):
        path = self.compressed("fixture.gz", "a" * 2000)
        self.assertEqual(MODULE.verify_gzip(path)["expanded_bytes"], 2000)
        with self.assertRaisesRegex(ValueError, "Expanded gzip"):
            MODULE.verify_gzip(path, expanded_limit=1000)
        blob = bytearray(path.read_bytes())
        blob[-8] ^= 1
        path.write_bytes(blob)
        with self.assertRaises((OSError, EOFError)):
            MODULE.verify_gzip(path)

    def test_feature_names_can_repeat_but_feature_ids_and_barcodes_cannot(self):
        features = self.compressed("features.gz", "ENSG1\tGENE\tGene Expression\nENSG2\tGENE\tGene Expression\n")
        result, _ = MODULE.audit_labels(features, "features")
        self.assertEqual(result["repeated_gene_name_rows"], 1)
        self.assertEqual(result["repeated_identifier_rows"], 0)
        features = self.compressed("features.gz", "ENSG1\tGENE\nENSG1\tGENE2\n")
        with self.assertRaisesRegex(ValueError, "Duplicate features"):
            MODULE.audit_labels(features, "features")
        barcodes = self.compressed("barcodes.gz", "CELL-1\nCELL-1\n")
        with self.assertRaisesRegex(ValueError, "Duplicate barcodes"):
            MODULE.audit_labels(barcodes, "barcodes")

    def test_intake_is_limited_to_source_scoped_official_files(self):
        source = "ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM9206nnn/GSM9206804/suppl/GSM9206804_Immature_matrix.mtx.gz"
        self.assertTrue(MODULE.official_https_url(source).startswith("https://"))
        for changed in [source.replace("ftp.ncbi.nlm.nih.gov", "example.org"),
                        source.replace("ftp://", "https://password@"), source + "?token=abc"]:
            with self.assertRaises(ValueError):
                MODULE.official_https_url(changed)

    def test_stream_download_rejects_content_length_mismatch_and_limit(self):
        source = "https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM9206nnn/GSM9206804/suppl/GSM9206804_Immature_matrix.mtx.gz"

        class Response(io.BytesIO):
            headers = {"Content-Length": "5"}

            def geturl(self):
                return source

        with patch.object(MODULE.regen, "_http_with_retry", return_value=Response(b"abc")):
            with self.assertRaisesRegex(ValueError, "Content-Length"):
                MODULE.download_file(source, self.root)
        with patch.object(MODULE, "COMPRESSED_LIMIT", 2), \
                patch.object(MODULE.regen, "_http_with_retry", return_value=Response(b"abc")):
            with self.assertRaisesRegex(ValueError, "intake limit"):
                MODULE.download_file(source, self.root)
        self.assertFalse(list(self.root.glob("*.part")))

    @unittest.skipUnless(SCIENTIFIC_LIBRARIES, "NumPy and SciPy required for sparse-matrix audit")
    def test_duplicate_coordinates_are_detected_before_sparse_summing(self):
        path = self.compressed("matrix.gz", "%%MatrixMarket matrix coordinate integer general\n3 2 5\n1 1 2\n1 1 3\n1 1 4\n2 2 1\n2 2 7\n")
        result = MODULE.audit_matrix(path, 3, 2)
        self.assertEqual(result["actual_stored_entries"], 5)
        self.assertEqual(result["duplicate_coordinate_groups"], 2)
        self.assertEqual(result["repeated_coordinate_entries"], 3)
        self.assertEqual(result["unique_coordinates"], 2)
        self.assertFalse(result["structural_quality_passed"])
        self.assertNotIn("per_barcode_positive_feature_count", result)

    @unittest.skipUnless(SCIENTIFIC_LIBRARIES, "NumPy and SciPy required for sparse-matrix audit")
    def test_real_values_and_transposed_orientation_are_reported(self):
        path = self.compressed("matrix.gz", "%%MatrixMarket matrix coordinate real general\n2 3 3\n1 1 1.5\n1 2 -2.0\n2 3 nan\n")
        result = MODULE.audit_matrix(path, 3, 2)
        self.assertEqual(result["orientation_from_label_dimensions"], "barcodes_by_features")
        self.assertEqual(result["fractional_finite_entries"], 1)
        self.assertEqual(result["negative_entries"], 1)
        self.assertEqual(result["nonfinite_entries"], 1)
        self.assertFalse(result["nonnegative_integer_numeric_form"])
        self.assertNotIn("per_barcode_entry_sum", result)

    @unittest.skipUnless(SCIENTIFIC_LIBRARIES, "NumPy and SciPy required for sparse-matrix audit")
    def test_count_like_form_does_not_claim_raw_umi_lineage(self):
        path = self.compressed("matrix.gz", "%%MatrixMarket matrix coordinate integer general\n3 2 2\n1 1 2\n3 2 4\n")
        result = MODULE.audit_matrix(path, 3, 2)
        self.assertTrue(result["nonnegative_integer_numeric_form"])
        self.assertTrue(result["structural_quality_passed"])
        self.assertNotIn("raw_umi_counts", result)
        self.assertEqual(result["per_barcode_entry_sum"]["median"], 3)
        self.assertEqual(result["barcodes_with_fewer_than_200_positive_features"], 2)

    @unittest.skipUnless(SCIENTIFIC_LIBRARIES, "NumPy and SciPy required for sparse-matrix audit")
    def test_invalid_sparse_indices_declared_nnz_and_label_dimensions_fail(self):
        cases = ["3 2 1\n4 1 2\n", "3 2 2\n1 1 2\n", "3 2 1\n1 1 2\n2 2 3\n",
                 "3 2 1\n0 1 2\n", "8 9 1\n1 1 2\n"]
        for content in cases:
            with self.subTest(content=content):
                path = self.compressed("matrix.gz", "%%MatrixMarket matrix coordinate integer general\n" + content)
                with self.assertRaises(ValueError):
                    MODULE.audit_matrix(path, 3, 2)

    @unittest.skipUnless(SCIENTIFIC_LIBRARIES, "NumPy and SciPy required for sparse-matrix audit")
    def test_empty_sparse_matrix_is_valid_and_has_zero_barcode_totals(self):
        path = self.compressed("matrix.gz", "%%MatrixMarket matrix coordinate integer general\n3 2 0\n")
        result = MODULE.audit_matrix(path, 3, 2)
        self.assertEqual(result["duplicate_coordinate_groups"], 0)
        self.assertEqual(result["zero_total_barcodes"], 2)
        self.assertTrue(result["structural_quality_passed"])


if __name__ == "__main__":
    unittest.main()
