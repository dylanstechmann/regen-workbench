from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "studies" / "mutation_repair_pilot" / "tebv_benchmark"))

import analyze  # noqa: E402
from validate_experiment_manifest import ManifestValidationError, validate_experiment_manifest  # noqa: E402


MANIFEST = ROOT / "studies" / "mutation_repair_pilot" / "tebv_benchmark" / "experiment.json"


class TEBVBenchmarkTests(unittest.TestCase):
    def test_public_archive_reproduces_endpoint_and_refuses_donor_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "derived"
            result = analyze.run_analysis(analyze.DEFAULT_INPUT, out)
            self.assertEqual(result["source_observation_count"], 35)
            self.assertEqual(result["donor_generalization"]["status"], "not_testable")
            self.assertEqual(result["donor_generalization"]["independent_hgps_donors"], 1)
            self.assertFalse(result["monotone_dose_response_supported_descriptively"])
            self.assertEqual(result["author_reported_model"]["ratio_p_value"], 0.0044)
            self.assertEqual(result["author_reported_model"]["week_p_value"], 0.4139)

            with (out / "vasodilation_observations.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 35)
            count_50_week3 = sum(row["group"] == "50:50" and row["week"] == "3" for row in rows)
            self.assertEqual(count_50_week3, 3)
            self.assertTrue(all(not row["tebv_id_at_observation_level"] for row in rows))

    def test_changed_source_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            altered = Path(temp) / "Figure_8.zip"
            shutil.copyfile(analyze.DEFAULT_INPUT, altered)
            altered.write_bytes(altered.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "pinned byte-count/SHA-256"):
                analyze.run_analysis(altered, Path(temp) / "derived")


class ExperimentManifestTests(unittest.TestCase):
    def _temporary_manifest(self, edit):
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
        edit(document)
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False)
        with temp:
            json.dump(document, temp)
        self.addCleanup(Path(temp.name).unlink, missing_ok=True)
        return Path(temp.name)

    def test_case_manifest_schema_and_all_local_hashes_pass(self):
        document = validate_experiment_manifest(MANIFEST)
        self.assertEqual(document["manifest_schema_version"], "1.0.0")
        self.assertEqual(document["modeling"]["donor_validation"]["status"], "not_testable")
        self.assertEqual(document["calibration"]["status"], "not_reported")

    def test_schema_can_validate_a_manifest_from_another_repo_id(self):
        def rename_local_repository(document):
            document["repository_id"] = "example-methods-repo"
            for artifact in document["artifacts"]:
                if artifact.get("repository") == "regen-workbench":
                    artifact["repository"] = "example-methods-repo"

        path = self._temporary_manifest(rename_local_repository)
        document = validate_experiment_manifest(path, repo_root=ROOT)
        self.assertEqual(document["repository_id"], "example-methods-repo")

    def test_unknown_artifact_reference_is_rejected(self):
        path = self._temporary_manifest(
            lambda document: document["protocol"].update(source_artifact_id="missing-paper")
        )
        with self.assertRaisesRegex(ManifestValidationError, "unknown artifact id"):
            validate_experiment_manifest(path)

    def test_hash_mismatch_is_rejected(self):
        def corrupt_hash(document):
            artifact = next(item for item in document["artifacts"] if item["id"] == "analysis-code")
            artifact["sha256"] = "0" * 64

        path = self._temporary_manifest(corrupt_hash)
        with self.assertRaisesRegex(ManifestValidationError, "SHA-256 mismatch"):
            validate_experiment_manifest(path)

    def test_donor_validation_cannot_be_marked_passed_without_donor_count_and_ids(self):
        def falsely_pass(document):
            document["modeling"]["donor_validation"]["status"] = "passed"

        path = self._temporary_manifest(falsely_pass)
        with self.assertRaisesRegex(ManifestValidationError, "below its minimum donor count"):
            validate_experiment_manifest(path)

    def test_artifact_path_traversal_is_rejected(self):
        def unsafe_path(document):
            artifact = next(item for item in document["artifacts"] if item["id"] == "analysis-code")
            artifact["path"] = "../outside.py"

        path = self._temporary_manifest(unsafe_path)
        with self.assertRaisesRegex(ManifestValidationError, "must stay inside the repository"):
            validate_experiment_manifest(path)


if __name__ == "__main__":
    unittest.main()
