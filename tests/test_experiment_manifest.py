from __future__ import annotations

import csv
import hashlib
import io
import json
import lzma
import os
import shutil
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile
import zlib
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "studies" / "mutation_repair_pilot" / "tebv_benchmark"))

import analyze  # noqa: E402
import archive_collector as ac  # noqa: E402
import validate_experiment_manifest as manifest_validator  # noqa: E402
from validate_experiment_manifest import (  # noqa: E402
    ManifestValidationError,
    ValidatedExperimentSnapshot,
    validate_experiment_manifest,
    validate_experiment_manifest_snapshot,
)

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


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema is required to validate experiment manifests; installed in the workbench image")
class ValidatedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.schema = self.root / "schema.json"
        self.schema.write_bytes(b"{}")

    def document(self):
        return {
            "manifest_schema_version": "1.0.0",
            "repository_id": "repo",
            "experiment_id": "snapshot-fixture",
            "title": "Snapshot fixture",
            "artifacts": [
                {"id": "paper", "kind": "publication", "repository": "external",
                 "uri": "https://example.org/paper"},
                {"id": "model", "kind": "analysis_code", "repository": "external",
                 "uri": "https://example.org/model"},
            ],
            "protocol": {"source_artifact_id": "paper"},
            "design": {"donor_structure": {
                "disease_donor_count": 0,
                "healthy_donor_count": 0,
                "observation_level_ids_available": False,
            }},
            "assays": [],
            "modeling": {
                "source_model": {"artifact_id": "model"},
                "donor_validation": {"status": "not_testable"},
            },
            "calibration": {"status": "not_reported"},
        }

    def declare(self, document, artifact_id, relative, data, kind="analysis_output", member_path=None):
        artifact = {
            "id": artifact_id,
            "kind": kind,
            "repository": "repo",
            "path": relative,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
        }
        if member_path is not None:
            artifact["member_path"] = member_path
        document["artifacts"].append(artifact)
        return artifact

    def write_manifest(self, document):
        path = self.root / "experiment.json"
        path.write_bytes(json.dumps(document, indent=2).encode("utf-8") + b"\n")
        return path

    def validate(self, document):
        path = self.write_manifest(document)
        return validate_experiment_manifest_snapshot(path, self.root, self.schema)

    def test_snapshot_is_frozen_and_retains_exact_selected_bytes(self):
        document = self.document()
        output = b"first\r\nsecond\x00third\xff\n"
        code = b"not retained\x00\r\n"
        self.declare(document, "output", "output.bin", output)
        self.declare(document, "code", "code.bin", code, kind="analysis_code")
        document["artifacts"].append({
            "id": "external-output", "kind": "analysis_output", "repository": "external",
            "uri": "https://example.org/output",
        })
        (self.root / "output.bin").write_bytes(output)
        (self.root / "code.bin").write_bytes(code)
        path = self.write_manifest(document)
        exact_manifest = path.read_bytes()

        snapshot = validate_experiment_manifest_snapshot(path, self.root, self.schema)
        self.assertIsInstance(snapshot, ValidatedExperimentSnapshot)
        self.assertEqual(snapshot.document, document)
        self.assertEqual(snapshot.manifest_bytes, exact_manifest)
        self.assertEqual(snapshot.analysis_outputs, {"output": output})
        self.assertEqual(validate_experiment_manifest(path, self.root, self.schema), document)
        with self.assertRaises(FrozenInstanceError):
            snapshot.manifest_bytes = b"changed"

    def test_repeated_sources_are_read_once_and_cached_by_canonical_path(self):
        document = self.document()
        self.declare(document, "schema-copy", "schema.json", b"{}", kind="analysis_specification")
        self.declare(document, "output-a", "shared.bin", b"shared")
        self.declare(document, "output-b", "shared.bin", b"shared")
        (self.root / "shared.bin").write_bytes(b"shared")
        path = self.write_manifest(document)
        counts = {}
        real_read = ac.read_regular_file

        def counting_read(root, relative, **kwargs):
            key = (Path(root).resolve(), relative)
            counts[key] = counts.get(key, 0) + 1
            return real_read(root, relative, **kwargs)

        with patch.object(ac, "read_regular_file", counting_read):
            snapshot = validate_experiment_manifest_snapshot(path, self.root, self.schema)
        self.assertEqual(snapshot.analysis_outputs, {"output-a": b"shared", "output-b": b"shared"})
        for filename in ("experiment.json", "schema.json", "shared.bin"):
            matching = [count for (_root, relative), count in counts.items()
                        if relative == filename or relative.endswith("/" + filename)]
            self.assertEqual(sum(matching), 1, (filename, counts))

    def test_post_snapshot_source_mutation_does_not_change_retained_bytes(self):
        document = self.document()
        self.declare(document, "output", "output.bin", b"original")
        (self.root / "output.bin").write_bytes(b"original")
        path = self.write_manifest(document)
        exact_manifest = path.read_bytes()
        snapshot = validate_experiment_manifest_snapshot(path, self.root, self.schema)
        (self.root / "output.bin").write_bytes(b"modified")
        path.write_bytes(b'{"changed":true}\n')
        self.assertEqual(snapshot.manifest_bytes, exact_manifest)
        self.assertEqual(snapshot.analysis_outputs["output"], b"original")

    def test_manifest_schema_artifact_and_total_output_bounds(self):
        document = self.document()
        path = self.write_manifest(document)
        with patch.object(ac, "MAX_MEMBER_BYTES", len(path.read_bytes()) - 1):
            with self.assertRaisesRegex(ManifestValidationError, "experiment manifest.*larger"):
                validate_experiment_manifest_snapshot(path, self.root, self.schema)

        self.schema.write_bytes(b'{"description":"' + b"x" * 3000 + b'"}')
        with patch.object(ac, "MAX_MEMBER_BYTES", len(path.read_bytes())):
            with self.assertRaisesRegex(ManifestValidationError, "experiment manifest schema.*larger"):
                validate_experiment_manifest_snapshot(path, self.root, self.schema)

        self.schema.write_bytes(b"{}")
        document = self.document()
        self.declare(document, "large", "large.bin", b"x" * 3000)
        (self.root / "large.bin").write_bytes(b"x" * 3000)
        path = self.write_manifest(document)
        with patch.object(ac, "MAX_MEMBER_BYTES", len(path.read_bytes())):
            with self.assertRaisesRegex(ManifestValidationError, "large.*larger"):
                validate_experiment_manifest_snapshot(path, self.root, self.schema)

        document = self.document()
        self.declare(document, "a", "a.bin", b"1234")
        self.declare(document, "b", "b.bin", b"5678")
        (self.root / "a.bin").write_bytes(b"1234")
        (self.root / "b.bin").write_bytes(b"5678")
        with patch.object(ac, "MAX_TOTAL_BYTES", 7):
            with self.assertRaisesRegex(ManifestValidationError, "total budget"):
                self.validate(document)

    def test_artifact_paths_and_symlinked_components_are_rejected(self):
        for unsafe in ("../escape", "/absolute", "a//b", "a\\b", "C:/drive", "./dot"):
            with self.subTest(path=unsafe):
                document = self.document()
                self.declare(document, "unsafe", unsafe, b"x")
                with self.assertRaisesRegex(ManifestValidationError, "artifact path"):
                    self.validate(document)

        target = self.root / "target.bin"
        target.write_bytes(b"secret")
        try:
            os.symlink(target, self.root / "link.bin")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symbolic links unavailable: {exc}")
        document = self.document()
        self.declare(document, "linked", "link.bin", b"secret")
        with self.assertRaisesRegex(ManifestValidationError, "symbolic link"):
            self.validate(document)

        (self.root / "actual").mkdir()
        (self.root / "actual" / "output.bin").write_bytes(b"secret")
        os.symlink(self.root / "actual", self.root / "linked-dir", target_is_directory=True)
        document = self.document()
        self.declare(document, "linked", "linked-dir/output.bin", b"secret")
        with self.assertRaisesRegex(ManifestValidationError, "symbolic link"):
            self.validate(document)

    def test_two_real_snapshots_retain_original_bytes_and_reject_mutated_source(self):
        document = self.document()
        self.declare(document, "output", "output.bin", b"original")
        (self.root / "output.bin").write_bytes(b"original")
        first = self.validate(document)
        (self.root / "output.bin").write_bytes(b"modified")
        with self.assertRaisesRegex(ManifestValidationError, "SHA-256 mismatch"):
            self.validate(document)
        self.assertEqual(first.analysis_outputs["output"], b"original")

    def test_collection_errors_become_manifest_validation_errors(self):
        path = self.write_manifest(self.document())
        for error in (ac.SourceRefused("symlink", "source link refused"),
                      ac.CollectionError("source budget refused")):
            with self.subTest(error=type(error).__name__):
                with patch.object(ac, "read_regular_file", side_effect=error):
                    with self.assertRaises(ManifestValidationError) as caught:
                        validate_experiment_manifest_snapshot(path, self.root, self.schema)
                self.assertIn(str(error), str(caught.exception))
                self.assertIn("experiment manifest", str(caught.exception))

    def zip_document(self, entries, selected):
        archive_path = self.root / "bundle.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, data in entries:
                    archive.writestr(name, data)
        container = archive_path.read_bytes()
        document = self.document()
        self.declare(document, "container", "bundle.zip", container, kind="source_dataset")
        for artifact_id, member in selected:
            data = next(data for name, data in entries if name == member)
            self.declare(document, artifact_id, "bundle.zip", data, member_path=member)
        return document

    def test_zip_container_is_read_once_and_members_come_from_memory(self):
        document = self.zip_document(
            [("a.bin", b"alpha\x00"), ("b.bin", b"beta\r\n")],
            [("a", "a.bin"), ("b", "b.bin")],
        )
        path = self.write_manifest(document)
        reads = []
        real_read = ac.read_regular_file
        real_zip = zipfile.ZipFile
        opened = []

        def counting_read(root, relative, **kwargs):
            reads.append(relative)
            return real_read(root, relative, **kwargs)

        def memory_only(source, *args, **kwargs):
            self.assertIsInstance(source, io.BytesIO)
            opened.append(source)
            return real_zip(source, *args, **kwargs)

        with patch.object(ac, "read_regular_file", counting_read), \
                patch.object(manifest_validator.zipfile, "ZipFile", memory_only):
            snapshot = validate_experiment_manifest_snapshot(path, self.root, self.schema)
        self.assertEqual(reads.count("bundle.zip"), 1)
        # One directory parse plus one in-memory archive per distinct member extraction.
        self.assertEqual(len(opened), 3)
        self.assertEqual(snapshot.analysis_outputs, {"a": b"alpha\x00", "b": b"beta\r\n"})

    def test_duplicate_member_references_share_directory_extraction_and_work(self):
        payload = b"shared payload" * 20
        document = self.zip_document(
            [("shared.bin", payload)], [("first", "shared.bin"), ("second", "shared.bin")])
        path = self.write_manifest(document)
        raw_source_bytes = (len(path.read_bytes()) + len(self.schema.read_bytes())
                            + len((self.root / "bundle.zip").read_bytes()))
        member_reads = 0
        directory_reads = 0
        real_open = zipfile.ZipFile.open
        real_infolist = zipfile.ZipFile.infolist

        def counting_open(archive, *args, **kwargs):
            nonlocal member_reads
            member_reads += 1
            return real_open(archive, *args, **kwargs)

        def counting_infolist(archive):
            nonlocal directory_reads
            directory_reads += 1
            return real_infolist(archive)

        # One extraction fits exactly; a duplicate decompression would exceed the work budget.
        with patch.object(manifest_validator, "MAX_VALIDATION_WORK_BYTES", raw_source_bytes + len(payload)), \
                patch.object(zipfile.ZipFile, "open", counting_open), \
                patch.object(zipfile.ZipFile, "infolist", counting_infolist):
            snapshot = validate_experiment_manifest_snapshot(path, self.root, self.schema)
        self.assertEqual(snapshot.analysis_outputs, {"first": payload, "second": payload})
        self.assertEqual(member_reads, 1)
        self.assertEqual(directory_reads, 1)

    def test_zip_member_count_limit_is_enforced_with_cached_directories(self):
        document = self.zip_document(
            [("a.bin", b"a"), ("b.bin", b"b")], [("a", "a.bin")])
        with patch.object(ac, "MAX_MEMBERS", 1):
            with self.assertRaisesRegex(ManifestValidationError, "more than 1 members"):
                self.validate(document)

    def test_aggregate_validation_budget_is_separate_from_retained_output_budget(self):
        document = self.document()
        path = self.write_manifest(document)
        with patch.object(manifest_validator, "MAX_VALIDATION_WORK_BYTES", len(path.read_bytes())):
            with self.assertRaisesRegex(ManifestValidationError, "source cache exceeds"):
                validate_experiment_manifest_snapshot(path, self.root, self.schema)

        payload = b"x" * 200_000
        document = self.zip_document([("large.bin", payload)], [("large", "large.bin")])
        path = self.write_manifest(document)
        raw_source_bytes = (len(path.read_bytes()) + len(self.schema.read_bytes())
                            + len((self.root / "bundle.zip").read_bytes()))
        with patch.object(manifest_validator, "MAX_VALIDATION_WORK_BYTES", raw_source_bytes):
            with self.assertRaisesRegex(ManifestValidationError, "decompressed bytes exceed"):
                validate_experiment_manifest_snapshot(path, self.root, self.schema)

        payload = b"small aggregate payload"
        document = self.zip_document([("member.bin", payload)], [("member", "member.bin")])
        path = self.write_manifest(document)
        raw_source_bytes = (len(path.read_bytes()) + len(self.schema.read_bytes())
                            + len((self.root / "bundle.zip").read_bytes()))
        with patch.object(manifest_validator, "MAX_VALIDATION_WORK_BYTES", raw_source_bytes):
            with self.assertRaisesRegex(ManifestValidationError, "validation work exceeds"):
                validate_experiment_manifest_snapshot(path, self.root, self.schema)

    def malformed_zip_document(self, compression):
        payload = bytes(range(256)) * 16
        archive_path = self.root / f"malformed-{compression}.zip"
        with zipfile.ZipFile(archive_path, "w", compression=compression) as archive:
            archive.writestr("payload.bin", payload)
        with zipfile.ZipFile(archive_path) as archive:
            info = archive.getinfo("payload.bin")
        raw = bytearray(archive_path.read_bytes())
        signature, = struct.unpack_from("<I", raw, info.header_offset)
        self.assertEqual(signature, 0x04034B50)
        filename_bytes, extra_bytes = struct.unpack_from("<HH", raw, info.header_offset + 26)
        data_offset = info.header_offset + 30 + filename_bytes + extra_bytes
        for index in range(info.compress_size):
            raw[data_offset + index] = 0xFF
        archive_path.write_bytes(raw)
        document = self.document()
        self.declare(document, "container", archive_path.name, bytes(raw), kind="source_dataset")
        self.declare(document, "payload", archive_path.name, payload, member_path="payload.bin")
        return document

    def test_malformed_compressed_streams_normalize_validator_and_cli_errors(self):
        methods = [zipfile.ZIP_DEFLATED, zipfile.ZIP_LZMA]
        if hasattr(zipfile, "ZIP_ZSTANDARD"):
            methods.append(zipfile.ZIP_ZSTANDARD)
        for compression in methods:
            with self.subTest(compression=compression):
                try:
                    document = self.malformed_zip_document(compression)
                except (NotImplementedError, RuntimeError):
                    continue
                with self.assertRaisesRegex(ManifestValidationError, "missing or unreadable"):
                    self.validate(document)
                path = self.write_manifest(document)
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    status = manifest_validator.main([
                        str(path), "--repo-root", str(self.root), "--schema", str(self.schema)])
                self.assertEqual(status, 1)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("Invalid experiment manifest:", stderr.getvalue())
                self.assertIn("missing or unreadable", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())

    def test_compressed_exception_types_normalize_without_catching_process_errors(self):
        document = self.zip_document([("small.bin", b"x")], [("small", "small.bin")])
        container = (self.root / "bundle.zip").read_bytes()
        artifact = next(item for item in document["artifacts"] if item["id"] == "small")
        errors = [EOFError(), zlib.error(), lzma.LZMAError()]
        for error_type in manifest_validator._ZSTD_ERROR_TYPES:
            try:
                errors.append(error_type())
            except TypeError:
                pass
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with patch.object(zipfile.ZipFile, "open", side_effect=error):
                    with self.assertRaisesRegex(ManifestValidationError, "missing or unreadable"):
                        manifest_validator._zip_member_bytes(container, artifact)
        for error in (MemoryError(), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                with patch.object(zipfile.ZipFile, "open", side_effect=error):
                    with self.assertRaises(type(error)):
                        manifest_validator._zip_member_bytes(container, artifact)

    def test_zip_duplicate_and_unsafe_members_are_rejected(self):
        document = self.zip_document([("safe.bin", b"one"), ("safe.bin", b"two")], [("safe", "safe.bin")])
        with self.assertRaisesRegex(ManifestValidationError, "duplicate archive member"):
            self.validate(document)
        for unsafe in ("../escape.bin", "/absolute.bin", "a//noncanonical.bin", "a\\backslash.bin"):
            with self.subTest(member=unsafe):
                document = self.zip_document([("safe.bin", b"one"), (unsafe, b"bad")], [("safe", "safe.bin")])
                with self.assertRaisesRegex(ManifestValidationError, "unsafe archive member"):
                    self.validate(document)

    def test_zip_declared_oversize_is_rejected_before_member_read(self):
        document = self.zip_document([("large.bin", b"x" * 5000)], [("large", "large.bin")])
        path = self.write_manifest(document)
        limit = max(len(path.read_bytes()), len(self.schema.read_bytes()), len((self.root / "bundle.zip").read_bytes()))
        with patch.object(ac, "MAX_MEMBER_BYTES", limit), \
                patch.object(zipfile.ZipFile, "open", side_effect=AssertionError("must not read member")):
            with self.assertRaisesRegex(ManifestValidationError, "archive member exceeds"):
                validate_experiment_manifest_snapshot(path, self.root, self.schema)

    def test_zip_member_stream_is_bounded_even_when_declaration_is_wrong(self):
        document = self.zip_document([("small.bin", b"x")], [("small", "small.bin")])
        container = (self.root / "bundle.zip").read_bytes()
        artifact = next(item for item in document["artifacts"] if item["id"] == "small")
        stream = io.BytesIO(b"123456")
        with patch.object(ac, "MAX_MEMBER_BYTES", 5), \
                patch.object(zipfile.ZipFile, "open", return_value=stream):
            with self.assertRaisesRegex(ManifestValidationError, "grew beyond"):
                manifest_validator._zip_member_bytes(container, artifact)
        self.assertTrue(stream.closed)

    def test_cli_preserves_success_and_validation_failure_behavior(self):
        document = self.document()
        path = self.write_manifest(document)
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = manifest_validator.main([str(path), "--repo-root", str(self.root), "--schema", str(self.schema)])
        self.assertEqual(status, 0)
        self.assertIn("Valid experiment manifest: snapshot-fixture", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

        document["artifacts"][0]["id"] = "renamed-paper"
        path = self.write_manifest(document)
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = manifest_validator.main([str(path), "--repo-root", str(self.root), "--schema", str(self.schema)])
        self.assertEqual(status, 1)
        self.assertIn("Invalid experiment manifest:", stderr.getvalue())
        self.assertIn("unknown artifact id", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
