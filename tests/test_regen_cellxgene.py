from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import regen
import regen_cellxgene as cx

COLLECTION_ID = "63d03351-06be-478e-a0db-f7a653b6b19b"
COLLECTION_VERSION = "10000000-0000-4000-8000-000000000001"
DATASET_ID = "20000000-0000-4000-8000-000000000001"
DATASET_VERSION = "30000000-0000-4000-8000-000000000001"
ASSET_URL = f"https://datasets.cellxgene.cziscience.com/{COLLECTION_ID}/synthetic.h5ad"


def dataset(number=1, *, stub=False):
    suffix = f"{number:012d}"
    item = {
        "dataset_id": f"20000000-0000-4000-8000-{suffix}",
        "dataset_version_id": f"30000000-0000-4000-8000-{suffix}",
        "title": f"Synthetic dataset {number}",
        "cell_count": 100 + number,
        "schema_version": "5.1.0",
        "tombstone": False,
        "assets": [
            {"filetype": "RDS"},
            {
                "filetype": "H5AD",
                "filesize": 4096 + number,
                "url": f"https://datasets.cellxgene.cziscience.com/{COLLECTION_ID}/synthetic-{number}.h5ad",
                **({"sha256": "A" * 64} if number == 1 else {}),
            },
        ],
        "assay": [{"label": "10x 3' v3", "ontology_term_id": "EFO:0009899"}],
        "tissue": [{"label": "kidney", "ontology_term_id": "UBERON:0002113"}],
        "organism": [{"label": "Homo sapiens", "ontology_term_id": "NCBITaxon:9606"}],
        "suspension_type": ["cell"],
    }
    if stub:
        del item["title"], item["cell_count"]
    return item


def collection(*, stub=False, dataset_count=2):
    return {
        "collection_id": COLLECTION_ID,
        "collection_version_id": COLLECTION_VERSION,
        "visibility": "PUBLIC",
        "name": "Synthetic public collection",
        "description": "A real-shape synthetic metadata fixture; no donor measurements.",
        "doi": "10.0000/SYNTHETIC",
        "created_at": "2026-01-01T00:00:00+00:00",
        "published_at": "2026-01-02T00:00:00+00:00",
        "revised_at": "2026-01-03T00:00:00+00:00",
        "tombstone": False,
        "links": [{"link_name": "Synthetic protocol", "link_type": "PROTOCOL", "link_url": "https://example.org/protocol"}],
        "publisher_metadata": {"journal": "Synthetic", "is_preprint": False},
        "datasets": [dataset(number, stub=stub) for number in range(1, dataset_count + 1)],
    }


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patcher = patch.object(regen, "PROV", self.root / "provenance")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_real_shape_normalization_and_deterministic_manifest(self):
        normalized = cx.normalize_collection(collection())
        self.assertEqual(normalized["collection_id"], COLLECTION_ID)
        self.assertEqual(normalized["collection_version_id"], COLLECTION_VERSION)
        first = normalized["datasets"][0]
        self.assertEqual(first["dataset_id"], DATASET_ID)
        self.assertEqual(first["dataset_version_id"], DATASET_VERSION)
        self.assertEqual(first["title"], "Synthetic dataset 1")
        self.assertEqual(first["cell_count"], 101)
        self.assertEqual(first["schema_version"], "5.1.0")
        self.assertEqual(first["tissue"][0]["ontology_term_id"], "UBERON:0002113")
        self.assertEqual(first["assets"], [{
            "filetype": "H5AD", "url": ASSET_URL.replace("synthetic.h5ad", "synthetic-1.h5ad"),
            "declared_bytes": 4097, "sha256": "a" * 64,
        }])
        self.assertIsNone(normalized["datasets"][1]["assets"][0]["sha256"])
        invalid_digest = dataset(1)["assets"][1]
        invalid_digest["sha256"] = "not-a-source-digest"
        self.assertIsNone(cx.normalize_asset(invalid_digest)["sha256"])
        invalid_digest["sha256"] = 123
        with self.assertRaises(cx.CellxGeneError):
            cx.normalize_asset(invalid_digest)
        self.assertTrue(first["source_review_required"])
        self.assertTrue(first["attribution_required"])
        manifest = cx.build_manifest(normalized)
        self.assertEqual(manifest, cx.build_manifest(normalized))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["provider"], "cellxgene")
        self.assertEqual(manifest["state"], "manifest_only")
        self.assertEqual(manifest["dataset_count"], 2)
        self.assertEqual(manifest["h5ad_asset_count"], 2)
        self.assertEqual(manifest["declared_bytes"], 8195)
        self.assertEqual(manifest["datasets"][0]["schema_version"], "5.1.0")
        for key, value in (("downloaded", False), ("asset_fetch_attempted", False),
                           ("h5ad_downloaded", False), ("measurements_imported", False)):
            self.assertIs(manifest[key], value)
        self.assertEqual(manifest["scientific_review"], "not_established")
        self.assertNotIn("observed_bytes", json.dumps(manifest))
        self.assertNotIn("downloaded_at", manifest)
        self.assertNotIn("local_path", json.dumps(manifest))

    def test_selected_manifest_is_version_pinned_and_hash_independent(self):
        normalized = cx.normalize_collection(collection())
        selected = cx.build_manifest(normalized, [normalized["datasets"][1]])
        self.assertEqual(selected["dataset_count"], 1)
        self.assertEqual(selected["datasets"][0]["dataset_version_id"], "30000000-0000-4000-8000-000000000002")
        self.assertEqual(selected["datasets"][0]["assets"][0]["sha256"], None)
        metadata_digest = hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest()
        self.assertNotEqual(metadata_digest, selected["datasets"][0]["assets"][0]["sha256"])
        with self.assertRaises(cx.CellxGeneError):
            cx.build_manifest(normalized, [])
        with self.assertRaises(cx.CellxGeneError):
            cx.build_manifest(normalized, [normalized["datasets"][0], normalized["datasets"][0]])

    def test_uuid_search_uses_one_exact_detail_get_and_never_assets(self):
        calls = []
        def fetch(url):
            calls.append(url)
            self.assertNotIn(cx.ASSET_HOST, url)
            return collection()
        raw, rows = cx.search_collections(COLLECTION_ID.upper(), 1, fetch)
        self.assertEqual(calls, [cx.collection_api_url(COLLECTION_ID)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["collection_id"], COLLECTION_ID)
        self.assertEqual(rows[0]["dataset_id"], DATASET_ID)
        self.assertEqual(rows[0]["manifest"]["state"], "manifest_only")
        wrong = collection()
        wrong["collection_id"] = "40000000-0000-4000-8000-000000000001"
        with self.assertRaisesRegex(cx.CellxGeneError, "identity"):
            cx.search_collections(COLLECTION_ID, 1, lambda _url: wrong)

    def test_text_search_uses_only_list_endpoint_and_supports_stubs(self):
        calls = []
        def fetch(url):
            calls.append(url)
            return [collection(stub=True)]
        for query in ("SYNTHETIC PUBLIC", "no donor measurements", "10.0000/synthetic", "KIDNEY", "5.1.0"):
            with self.subTest(query=query):
                calls.clear()
                _, rows = cx.search_collections(query, 10, fetch)
                self.assertEqual(calls, [cx.PUBLIC_COLLECTIONS_URL])
                self.assertEqual(len(rows), 2)
                self.assertIsNone(rows[0]["cell_count"])
                self.assertIn(DATASET_ID, rows[0]["title"])
        _, rows = cx.search_collections("not present", 10, fetch)
        self.assertEqual(rows, [])

    def test_text_search_sorts_then_limits_after_full_validation(self):
        other = collection()
        other["collection_id"] = "10000000-0000-4000-8000-000000000099"
        other["collection_version_id"] = "10000000-0000-4000-8000-000000000099"
        other["datasets"] = [dataset(3)]
        for item in other["datasets"]:
            item["assets"][1]["url"] = item["assets"][1]["url"].replace(COLLECTION_ID, other["collection_id"])
        _, rows = cx.search_collections("synthetic", 2, lambda _url: [other, collection()])
        self.assertEqual(len(rows), 2)
        self.assertEqual([(row["collection_id"], row["dataset_id"]) for row in rows],
                         [(other["collection_id"], "20000000-0000-4000-8000-000000000003"),
                          (COLLECTION_ID, DATASET_ID)])
        malformed = collection()
        malformed["name"] = "does not match"
        malformed["datasets"][0]["schema_version"] = "bad"
        with self.assertRaises(cx.CellxGeneError):
            cx.search_collections("synthetic", 1, lambda _url: [collection(), malformed])

    def test_list_stub_omissions_are_the_only_identity_asset_relaxation(self):
        for field in ("dataset_id", "dataset_version_id", "assets"):
            with self.subTest(field=field):
                raw = collection(stub=True)
                del raw["datasets"][0][field]
                with self.assertRaises(cx.CellxGeneError):
                    cx.normalize_collection(raw, list_stub=True)
        for field in ("collection_id", "collection_version_id"):
            with self.subTest(field=field):
                raw = collection(stub=True)
                del raw[field]
                with self.assertRaises(cx.CellxGeneError):
                    cx.normalize_collection(raw, list_stub=True)
        for field in ("title", "cell_count"):
            with self.subTest(detail_missing=field):
                raw = collection()
                del raw["datasets"][0][field]
                with self.assertRaises(cx.CellxGeneError):
                    cx.normalize_collection(raw)

    def test_tombstones_duplicates_and_non_h5ad_only_fail_closed(self):
        for owner in ("collection", "dataset"):
            with self.subTest(tombstone=owner):
                raw = collection()
                target = raw if owner == "collection" else raw["datasets"][0]
                target["tombstone"] = True
                with self.assertRaisesRegex(cx.CellxGeneError, "tombstone"):
                    cx.normalize_collection(raw)
        raw = collection()
        raw["datasets"].append(copy.deepcopy(raw["datasets"][0]))
        with self.assertRaisesRegex(cx.CellxGeneError, "dataset_id"):
            cx.normalize_collection(raw)
        raw = collection()
        raw["datasets"][1]["dataset_version_id"] = raw["datasets"][0]["dataset_version_id"]
        with self.assertRaisesRegex(cx.CellxGeneError, "dataset_version_id"):
            cx.normalize_collection(raw)
        raw = collection()
        raw["datasets"][0]["assets"].append(copy.deepcopy(raw["datasets"][0]["assets"][1]))
        with self.assertRaisesRegex(cx.CellxGeneError, "asset URL"):
            cx.normalize_collection(raw)
        raw = collection()
        raw["datasets"][0]["assets"] = [{"filetype": "RDS", "url": "https://example.org/not-fetched.rds"}]
        with self.assertRaisesRegex(cx.CellxGeneError, "1-8"):
            cx.normalize_collection(raw)
        with self.assertRaisesRegex(cx.CellxGeneError, "Duplicate public collection"):
            cx.search_collections("synthetic", 5, lambda _url: [collection(), collection()])
        for duplicate in ("dataset_id", "dataset_version_id", "asset_url"):
            with self.subTest(across_collections=duplicate):
                other = collection(dataset_count=1)
                other["collection_id"] = "40000000-0000-4000-8000-000000000001"
                other["collection_version_id"] = "40000000-0000-4000-8000-000000000002"
                if duplicate != "dataset_id":
                    other["datasets"][0]["dataset_id"] = "20000000-0000-4000-8000-000000000003"
                if duplicate != "dataset_version_id":
                    other["datasets"][0]["dataset_version_id"] = "30000000-0000-4000-8000-000000000003"
                if duplicate != "asset_url":
                    other["datasets"][0]["assets"][1]["url"] = other["datasets"][0]["assets"][1]["url"].replace(
                        "synthetic-1.h5ad", "unique-3.h5ad")
                with self.assertRaises(cx.CellxGeneError):
                    cx.search_collections("synthetic", 5, lambda _url: [collection(dataset_count=1), other])

    def test_malformed_types_counts_sizes_numbers_and_text_fail_closed(self):
        mutations = []
        for field in ("collection_id", "collection_version_id"):
            for value in (None, 1, "not-a-uuid", "00000000-0000-0000-0000-000000000000", " "+COLLECTION_ID):
                mutations.append((f"{field}-{value}", lambda raw, field=field, value=value: raw.__setitem__(field, value)))
        for value in (None, "3.0", "v3.0.0", 3):
            mutations.append((f"schema-{value}", lambda raw, value=value: raw["datasets"][0].__setitem__("schema_version", value)))
        for field, values in (("filesize", (0, -1, True, 1.5, cx.MAX_DECLARED_ASSET_BYTES + 1)),
                              ("cell_count", (0, -1, True, 1.5, cx.MAX_CELL_COUNT + 1))):
            for value in values:
                mutations.append((f"{field}-{value}", lambda raw, field=field, value=value:
                    (raw["datasets"][0]["assets"][1].__setitem__(field, value) if field == "filesize"
                     else raw["datasets"][0].__setitem__(field, value))))
        mutations.extend([
            ("nan", lambda raw: raw.__setitem__("publisher_metadata", {"value": float("nan")})),
            ("infinity", lambda raw: raw.__setitem__("publisher_metadata", {"value": float("inf")})),
            ("long-name", lambda raw: raw.__setitem__("name", "x" * (cx.MAX_NAME_CHARS + 1))),
            ("empty-name", lambda raw: raw.__setitem__("name", "")),
            ("datasets-type", lambda raw: raw.__setitem__("datasets", {})),
            ("assets-missing", lambda raw: raw["datasets"][0].__setitem__("assets", [])),
            ("asset-type", lambda raw: raw["datasets"][0]["assets"].append("H5AD")),
            ("metadata-type", lambda raw: raw["datasets"][0].__setitem__("tissue", {})),
            ("private", lambda raw: raw.__setitem__("visibility", "PRIVATE")),
        ])
        for label, mutate in mutations:
            with self.subTest(case=label):
                raw = collection()
                mutate(raw)
                with self.assertRaises(cx.CellxGeneError):
                    cx.normalize_collection(raw)
        for value in (None, [], 1, float("nan")):
            with self.subTest(collection_shape=repr(value)):
                with self.assertRaises(cx.CellxGeneError):
                    cx.normalize_collection(value)

    def test_explicit_collection_dataset_asset_and_metadata_bounds(self):
        with patch.object(cx, "MAX_DATASETS_PER_COLLECTION", 1):
            with self.assertRaisesRegex(cx.CellxGeneError, "datasets"):
                cx.normalize_collection(collection())
        with patch.object(cx, "MAX_ASSETS_PER_DATASET", 1):
            with self.assertRaisesRegex(cx.CellxGeneError, "assets"):
                cx.normalize_collection(collection(dataset_count=1))
        raw = collection(dataset_count=1)
        second_asset = copy.deepcopy(raw["datasets"][0]["assets"][1])
        second_asset["url"] = second_asset["url"].replace("synthetic-1.h5ad", "second-1.h5ad")
        raw["datasets"][0]["assets"].append(second_asset)
        with patch.object(cx, "MAX_H5AD_ASSETS_PER_DATASET", 1):
            with self.assertRaisesRegex(cx.CellxGeneError, "1-8"):
                cx.normalize_collection(raw)
        with patch.object(cx, "MAX_METADATA_ITEMS", 0):
            with self.assertRaisesRegex(cx.CellxGeneError, "assay"):
                cx.normalize_collection(collection(dataset_count=1))
        with patch.object(cx, "MAX_COLLECTIONS", 1):
            with self.assertRaisesRegex(cx.CellxGeneError, "bounded list"):
                cx.search_collections("x", 1, lambda _url: [collection(), collection()])
        for query, limit in (("", 1), (" ", 1), ("x" * 501, 1), ("x", 0), ("x", 11), ("x", True)):
            with self.subTest(query_length=len(query), limit=limit):
                with self.assertRaises(cx.CellxGeneError):
                    cx.search_collections(query, limit, lambda _url: [])

    def test_asset_url_host_path_and_escape_validation(self):
        valid = ASSET_URL
        self.assertEqual(cx.validate_asset_url(valid), valid)
        self.assertEqual(cx.validate_asset_url(valid.replace(".com/", ".com:443/")), valid.replace(".com/", ".com:443/"))
        bad = [
            valid.replace("https://", "http://"),
            valid.replace(cx.ASSET_HOST, "example.org"),
            valid.replace(cx.ASSET_HOST, "evil.datasets.cellxgene.cziscience.com"),
            valid.replace("https://", "https://user@"),
            valid.replace(".com/", ".com:444/"),
            valid + "?download=1", valid + "#fragment",
            valid.replace("synthetic.h5ad", "../secret.h5ad"),
            valid.replace("synthetic.h5ad", "%2e%2e/secret.h5ad"),
            valid.replace("synthetic.h5ad", "synthetic.txt"),
            valid.replace("/" + COLLECTION_ID, "//" + COLLECTION_ID),
            "https://datasets.cellxgene.cziscience.com\\@evil.example/synthetic.h5ad",
            "https://datasets.cellxgene.cziscience.com/" + "x" * 2100 + ".h5ad",
        ]
        for value in bad:
            with self.subTest(url=value[:120]):
                with self.assertRaises(cx.CellxGeneError):
                    cx.validate_asset_url(value)

    def test_resource_registry_is_defensive_link_only_and_nonclaiming(self):
        resources = cx.resource_catalog()
        self.assertEqual(len([item for item in resources if item["implemented"]]), 1)
        self.assertTrue(all(set(item) == {"id", "title", "url", "kind", "access", "implemented", "notes"}
                            for item in resources))
        for token in ("census", "virtual-cells", "mlflow", "models", "benchmarks"):
            with self.subTest(token=token):
                item = next(item for item in resources if token in item["id"])
                self.assertEqual(item["access"], "link_only")
                self.assertFalse(item["implemented"])
        joined = json.dumps(resources).lower()
        self.assertIn("no model execution", joined)
        self.assertIn("no claim that every model", joined)
        self.assertIn("does not replace dataset/source review", joined)
        resources[0]["notes"] = "mutated"
        self.assertNotEqual(cx.resource_catalog()[0]["notes"], "mutated")

    def test_no_asset_url_reaches_fetch_or_resource_output(self):
        def guarded(url):
            self.assertNotIn(cx.ASSET_HOST, url)
            self.assertNotRegex(url, r"\.h5ad(?:$|[?#])")
            return [collection(stub=True)] if url == cx.PUBLIC_COLLECTIONS_URL else collection()
        cx.search_collections(COLLECTION_ID, 2, guarded)
        cx.search_collections("kidney", 2, guarded)
        normalized = cx.normalize_collection(collection())
        cx.build_manifest(normalized)
        destination = regen.PROV / "biohub" / "resources-no-io"
        with patch.object(cx, "_public_get", side_effect=AssertionError("network forbidden")), \
                patch.object(regen, "record", side_effect=AssertionError("record forbidden")):
            result = cx.write_resource_catalog(destination)
        self.assertEqual(result["resource_count"], len(cx.resource_catalog()))
        saved = json.loads((destination / "resources.json").read_text())
        self.assertEqual(saved["resources"], cx.resource_catalog())
        self.assertFalse(any(path.suffix == ".h5ad" for path in destination.rglob("*")))

    def test_collection_fetch_publishes_metadata_and_records_real_get(self):
        calls = []
        receipt_path = regen.PROV / "cellxgene-test.json"
        def fetch(url):
            calls.append(url)
            return collection()
        fetch.last_http_status = 200
        def record(action, payload, outputs):
            self.assertEqual(calls, [cx.collection_api_url(COLLECTION_ID)])
            self.assertEqual(action, "cellxgene")
            self.assertEqual(payload["http_status"], 200)
            self.assertEqual(payload["requested_urls"], calls)
            self.assertFalse(payload["h5ad_downloaded"])
            self.assertFalse(payload["asset_fetch_attempted"])
            self.assertEqual(payload["dataset_count"], 2)
            self.assertEqual(payload["h5ad_asset_count"], 2)
            for output in outputs:
                self.assertTrue(output.is_file())
                self.assertNotEqual(output.suffix, ".h5ad")
            return receipt_path
        destination = regen.PROV / "biohub" / "collection-test"
        result = cx.fetch_collection_manifest(COLLECTION_ID, destination, fetch_json=fetch, record=record)
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["dataset_count"], 2)
        self.assertEqual(result["provenance_receipt"], str(receipt_path))
        for name, hash_key, bytes_key in (("source.json", "source_metadata_sha256", "source_metadata_bytes"),
                                           ("manifest.json", "manifest_metadata_sha256", "manifest_metadata_bytes")):
            content = (destination / name).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), result[hash_key])
            self.assertEqual(len(content), result[bytes_key])
        self.assertEqual(json.loads((destination / "source.json").read_text())["collection_id"], COLLECTION_ID)
        self.assertEqual(json.loads((destination / "manifest.json").read_text())["state"], "manifest_only")

    def test_output_rejections_and_invalid_response_happen_without_success_or_record(self):
        existing = regen.PROV / "biohub" / "existing"
        existing.mkdir(parents=True)
        outside = self.root / "outside"
        symlink = regen.PROV / "biohub" / "linked"
        try:
            os.symlink(self.root, symlink, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symbolic links unavailable: {exc}")
        fetch = unittest.mock.Mock(return_value=collection())
        record = unittest.mock.Mock()
        for destination in (existing, outside, symlink):
            with self.subTest(destination=destination):
                with self.assertRaises(cx.CellxGeneError):
                    cx.fetch_collection_manifest(COLLECTION_ID, destination, fetch_json=fetch, record=record)
        fetch.assert_not_called()
        record.assert_not_called()
        invalid = regen.PROV / "biohub" / "invalid"
        with self.assertRaises(cx.CellxGeneError):
            cx.fetch_collection_manifest(COLLECTION_ID, invalid, fetch_json=lambda _url: {"secret": "body"}, record=record)
        self.assertFalse(invalid.exists())
        record.assert_not_called()
        self.assertEqual(list(invalid.parent.glob(".invalid.tmp-*")), [])

    def test_main_success_and_errors_are_concise_and_confined(self):
        destination = regen.PROV / "biohub" / "main-resources"
        stdout = io.StringIO()
        with patch.object(regen, "record") as record, redirect_stdout(stdout):
            status = cx.main(["resources", "--out", str(destination)])
        self.assertEqual(status, 0)
        self.assertTrue((destination / "resources.json").is_file())
        record.assert_not_called()
        self.assertNotIn("# provenance", stdout.getvalue())
        stderr = io.StringIO()
        with patch.object(cx, "_public_get", return_value={"private_response_body": "do-not-echo"}), \
                patch.object(regen, "record") as record, redirect_stderr(stderr):
            status = cx.main(["collection", COLLECTION_ID, "--out", str(regen.PROV / "biohub" / "bad-main")])
        self.assertEqual(status, 1)
        self.assertNotIn("Traceback", stderr.getvalue())
        self.assertNotIn("do-not-echo", stderr.getvalue())
        record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
