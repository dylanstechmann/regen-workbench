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

try:
    import jsonschema  # noqa: F401
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


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


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema is required to validate experiment manifests; installed in the workbench image")
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
        self.assertEqual(document["manifest_schema_version"], "1.2.0")
        self.assertEqual(document["modeling"]["donor_validation"]["status"], "not_testable")
        self.assertEqual(document["calibration"]["status"], "not_reported")
        self.assertEqual(
            {entry["domain"] for entry in document["environmental_conditions"]},
            {"oxygen", "perfusion"},
        )

    def test_legacy_manifest_without_environmental_extension_still_validates(self):
        def legacy(document):
            document["manifest_schema_version"] = "1.0.0"
            document.pop("environmental_conditions")
        path = self._temporary_manifest(legacy)
        self.assertEqual(validate_experiment_manifest(path)["manifest_schema_version"], "1.0.0")

    def test_legacy_version_cannot_claim_new_environmental_fields(self):
        path = self._temporary_manifest(
            lambda document: document.update(manifest_schema_version="1.0.0"))
        with self.assertRaisesRegex(ManifestValidationError, "schema validation failed"):
            validate_experiment_manifest(path)

    def test_environmental_conditions_require_linked_source_artifacts(self):
        path = self._temporary_manifest(
            lambda document: document["environmental_conditions"][0].update(source_artifact_id="missing-source")
        )
        with self.assertRaisesRegex(ManifestValidationError, "environmental_conditions\\[0\\].*unknown artifact id"):
            validate_experiment_manifest(path)

    def test_environmental_condition_cannot_be_added_without_all_provenance_fields(self):
        path = self._temporary_manifest(
            lambda document: document["environmental_conditions"][0].pop("status")
        )
        with self.assertRaisesRegex(ManifestValidationError, "schema validation failed"):
            validate_experiment_manifest(path)

    def test_reported_environmental_condition_cannot_cite_analysis_code(self):
        def cite_code_as_measurement(document):
            condition = document["environmental_conditions"][0]
            condition["status"] = "reported"
            condition["source_artifact_id"] = "analysis-code"

        path = self._temporary_manifest(cite_code_as_measurement)
        with self.assertRaisesRegex(ManifestValidationError, "status reported cannot cite analysis_code"):
            validate_experiment_manifest(path)

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
            validation = document["modeling"]["donor_validation"]
            validation.update(
                status="passed",
                heldout_result_artifact_id="benchmark-summary",
                success_criterion_artifact_id="benchmark-model-specification",
                success_criterion="The held-out donor must meet the prespecified functional threshold.",
            )

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

    def test_validation_endpoints_require_each_core_domain(self):
        def remove_domain(document):
            endpoint = next(item for item in document["validation_endpoints"]
                            if item["role"] == "durability")
            endpoint["role"] = "functional"

        path = self._temporary_manifest(remove_domain)
        with self.assertRaisesRegex(ManifestValidationError, "must report each core domain.*durability"):
            validate_experiment_manifest(path)

    def test_measured_validation_endpoint_requires_evidence(self):
        def unlink_evidence(document):
            endpoint = next(item for item in document["validation_endpoints"]
                            if item["role"] == "functional")
            endpoint.pop("assay_id")
            endpoint.pop("artifact_id", None)

        path = self._temporary_manifest(unlink_evidence)
        with self.assertRaisesRegex(ManifestValidationError, "schema validation failed"):
            validate_experiment_manifest(path)

    def test_validation_endpoint_rejects_unknown_assay(self):
        def unknown_assay(document):
            endpoint = next(item for item in document["validation_endpoints"]
                            if item["role"] == "functional")
            endpoint["assay_id"] = "missing-assay"

        path = self._temporary_manifest(unknown_assay)
        with self.assertRaisesRegex(ManifestValidationError, "references unknown assay id"):
            validate_experiment_manifest(path)

    def test_measured_validation_endpoint_rejects_non_assay_artifact(self):
        def link_model_artifact(document):
            endpoint = next(item for item in document["validation_endpoints"]
                            if item["role"] == "functional")
            endpoint.pop("assay_id")
            endpoint["artifact_id"] = "analysis-code"

        path = self._temporary_manifest(link_model_artifact)
        with self.assertRaisesRegex(ManifestValidationError, "not an assay-data artifact"):
            validate_experiment_manifest(path)

    def test_schema_1_3_can_record_an_assay_that_is_not_available_without_fabricating_raw_data(self):
        def mark_unavailable(document):
            document["manifest_schema_version"] = "1.3.0"
            assay = document["assays"][0]
            assay["status"] = "not_available"
            assay.pop("raw_artifact_id")
            assay["source_n"] = "No observations available in this record."
            assay["notes"] = "A future assay is planned but not present in the source files."
            endpoint = next(item for item in document["validation_endpoints"] if item["role"] == "functional")
            endpoint["status"] = "not_available"
            endpoint.pop("assay_id")
            endpoint["rationale"] = "No functional assay data are available in this source record."

        path = self._temporary_manifest(mark_unavailable)
        validated = validate_experiment_manifest(path)
        self.assertEqual(validated["assays"][0]["status"], "not_available")

    def test_schema_1_4_records_developmental_context_and_immutable_analysis_history(self):
        def add_run_history(document):
            document["manifest_schema_version"] = "1.4.0"
            document["developmental_context"] = {
                "species": "human", "stage_track": "organoid_or_tissue_model",
                "interval_label": "Adult vascular cells in vitro", "interval_kind": "source_defined_interval",
                "source_artifact_id": "paper-2025", "notes": "The source describes an adult-cell model, not embryo development."
            }
            document["analysis_history"] = [{
                "bundle_id": "abcdef0123456789", "kind": "benchmark",
                "registered_utc": "2026-10-06T12:00:00Z", "artifact_ids": ["benchmark-summary"],
                "status": "receipt_verified"
            }]
            document["current_analysis_by_kind"] = {"benchmark": "abcdef0123456789"}

        path = self._temporary_manifest(add_run_history)
        validated = validate_experiment_manifest(path)
        self.assertEqual(validated["current_analysis_by_kind"]["benchmark"], "abcdef0123456789")

    def test_current_analysis_pointer_must_resolve_to_same_kind_history(self):
        def wrong_pointer(document):
            document["manifest_schema_version"] = "1.4.0"
            document["developmental_context"] = {
                "species": "human", "stage_track": "organoid_or_tissue_model",
                "interval_label": "Adult vascular cells in vitro", "interval_kind": "source_defined_interval",
                "source_artifact_id": "paper-2025", "notes": "The source describes an adult-cell model, not embryo development."
            }
            document["analysis_history"] = [{
                "bundle_id": "abcdef0123456789", "kind": "benchmark",
                "registered_utc": "2026-10-06T12:00:00Z", "artifact_ids": ["benchmark-summary"],
                "status": "receipt_verified"
            }]
            document["current_analysis_by_kind"] = {"benchmark": "0123456789abcdef"}

        path = self._temporary_manifest(wrong_pointer)
        with self.assertRaisesRegex(ManifestValidationError, "must point to an analysis-history bundle"):
            validate_experiment_manifest(path)

    def test_measured_assay_cannot_omit_or_misclassify_its_data_artifact(self):
        def omit_data(document):
            document["manifest_schema_version"] = "1.3.0"
            document["assays"][0].pop("raw_artifact_id")

        path = self._temporary_manifest(omit_data)
        with self.assertRaisesRegex(ManifestValidationError, "schema validation failed"):
            validate_experiment_manifest(path)

        def cite_code(document):
            document["manifest_schema_version"] = "1.3.0"
            document["assays"][0]["raw_artifact_id"] = "analysis-code"

        path = self._temporary_manifest(cite_code)
        with self.assertRaisesRegex(ManifestValidationError, "measured status cannot cite analysis_code"):
            validate_experiment_manifest(path)

    def test_measured_domain_cannot_link_to_an_unavailable_assay(self):
        def mismatch(document):
            document["manifest_schema_version"] = "1.3.0"
            document["assays"][0]["status"] = "not_available"
            document["assays"][0].pop("raw_artifact_id")

        path = self._temporary_manifest(mismatch)
        with self.assertRaisesRegex(ManifestValidationError, "cannot cite an assay that is not measured"):
            validate_experiment_manifest(path)


if __name__ == "__main__":
    unittest.main()
