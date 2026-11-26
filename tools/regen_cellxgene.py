#!/usr/bin/env python3
"""Strict CELLxGENE public-metadata inspection without H5AD retrieval."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import regen

API_ROOT = "https://api.cellxgene.cziscience.com"
PUBLIC_COLLECTIONS_URL = API_ROOT + "/curation/v1/collections?visibility=PUBLIC"
PUBLIC_COLLECTION_WEB_ROOT = "https://cellxgene.cziscience.com/collections/"
PUBLIC_DATA_POLICY_URL = "https://cellxgene.cziscience.com/docs/032__Contribute%20and%20Publish%20Data"
ASSET_HOST = "datasets.cellxgene.cziscience.com"  # SECRETS-GUARD-IGNORE: public hostname, not a credential

MAX_COLLECTIONS = 1000
MAX_DATASETS_PER_COLLECTION = 500
MAX_ASSETS_PER_DATASET = 32
MAX_H5AD_ASSETS_PER_DATASET = 8
MAX_METADATA_ITEMS = 100
MAX_LINKS = 32
MAX_QUERY_CHARS = 500
MAX_NAME_CHARS = 1024
MAX_TITLE_CHARS = 2048
MAX_DESCRIPTION_CHARS = 16_384
MAX_DOI_CHARS = 512
MAX_DATE_CHARS = 64
MAX_URL_CHARS = 2048
MAX_DECLARED_ASSET_BYTES = 1 << 40
MAX_CELL_COUNT = 1_000_000_000
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_METADATA_DEPTH = 6

_ONTOLOGY_FIELDS = (
    "assay", "cell_type", "development_stage", "disease", "organism",
    "self_reported_ethnicity", "sex", "tissue",
)
_DATE_FIELDS = ("created_at", "published_at", "revised_at")
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_SCHEMA_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
_SAFE_ASSET_PATH = re.compile(r"/[A-Za-z0-9._/-]+\.h5ad")
_UUID_PLACEHOLDERS = {"00000000-0000-0000-0000-000000000000"}

_RESOURCES = (
    {
        "id": "cellxgene-discover-public-metadata",
        "title": "CELLxGENE Discover public collection metadata",
        "url": PUBLIC_COLLECTIONS_URL,
        "kind": "public_metadata_api",
        "access": "public_get",
        "implemented": True,
        "notes": "Only fixed collection list/detail GET metadata is implemented; H5AD and other assets are never requested.",
    },
    {
        "id": "cellxgene-discover-public-data-policy",
        "title": "CELLxGENE Discover public data policy",
        "url": PUBLIC_DATA_POLICY_URL,
        "kind": "policy",
        "access": "link_only",
        "implemented": False,
        "notes": "A portal policy link does not replace dataset/source review or attribution review.",
    },
    {
        "id": "cellxgene-census",
        "title": "CELLxGENE Census documentation",
        "url": "https://chanzuckerberg.github.io/cellxgene-census/",
        "kind": "documentation",
        "access": "link_only",
        "implemented": False,
        "notes": "Documentation link only; no Census client, dataset download, query, or measurements import is implemented.",
    },
    {
        "id": "cz-virtual-cells-platform",
        "title": "CZI Virtual Cells Platform",
        "url": "https://virtualcellmodels.cziscience.com/",
        "kind": "platform",
        "access": "link_only",
        "implemented": False,
        "notes": "Link only; no model execution, inference, or universal model-license claim is implemented.",
    },
    {
        "id": "cz-virtual-cells-platform-docs",
        "title": "Virtual Cells Platform documentation",
        "url": "https://chanzuckerberg.github.io/virtual-cells-platform/",
        "kind": "documentation",
        "access": "link_only",
        "implemented": False,
        "notes": "Documentation link only; hosted capabilities and model-specific terms require separate review.",
    },
    {
        "id": "cz-virtual-cells-mlflow",
        "title": "Virtual Cells Platform MLflow references",
        "url": "https://chanzuckerberg.github.io/virtual-cells-platform/",
        "kind": "mlflow_reference",
        "access": "link_only",
        "implemented": False,
        "notes": "MLflow reference only; no tracking-server connection, registry access, artifact download, or model execution.",
    },
    {
        "id": "cz-virtual-cell-models",
        "title": "Virtual cell model catalog",
        "url": "https://virtualcellmodels.cziscience.com/",
        "kind": "model_catalog",
        "access": "link_only",
        "implemented": False,
        "notes": "Model links only; no inference and no claim that every model has the same or an open license.",
    },
    {
        "id": "cz-benchmarks",
        "title": "CZI virtual-cell benchmarks",
        "url": "https://github.com/chanzuckerberg/cz-benchmarks",
        "kind": "benchmark_repository",
        "access": "link_only",
        "implemented": False,
        "notes": "Repository link only; no benchmark execution, model inference, or result validation is implemented.",
    },
)


class CellxGeneError(ValueError):
    """A bounded public-metadata schema, output, or transport failure."""


def resource_catalog() -> list[dict[str, Any]]:
    """Return the static link registry without performing I/O."""
    return copy.deepcopy(list(_RESOURCES))


def validate_uuid(value: Any, label: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise CellxGeneError(f"{label} must be a canonical UUID")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise CellxGeneError(f"{label} must be a canonical UUID") from None
    canonical = str(parsed)
    if value.lower() != canonical or canonical in _UUID_PLACEHOLDERS:
        raise CellxGeneError(f"{label} must be a canonical non-placeholder UUID")
    return canonical


def validate_asset_url(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_URL_CHARS or value != value.strip():
        raise CellxGeneError("H5AD asset URL must be bounded HTTPS metadata")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise CellxGeneError("H5AD asset URL is malformed") from None
    if (parts.scheme != "https" or parts.hostname != ASSET_HOST
            or parts.username is not None or parts.password is not None
            or port not in (None, 443) or parts.query or parts.fragment):
        raise CellxGeneError("H5AD asset URL has an unapproved scheme, host, or URL component")
    if parts.netloc not in (ASSET_HOST, ASSET_HOST + ":443"):
        raise CellxGeneError("H5AD asset URL has unapproved userinfo or port syntax")
    path = parts.path
    if (not _SAFE_ASSET_PATH.fullmatch(path) or "%" in path or "\\" in path
            or "//" in path or any(segment in ("", ".", "..") for segment in path.split("/")[1:])):
        raise CellxGeneError("H5AD asset URL path is not a safe canonical .h5ad path")
    return value


def _text(value: Any, label: str, maximum: int, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise CellxGeneError(f"{label} must be text")
    value = value.strip()
    if not value and not optional:
        raise CellxGeneError(f"{label} must not be empty")
    if len(value) > maximum or any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise CellxGeneError(f"{label} exceeds its text bounds or contains control characters")
    return value


def _integer(value: Any, label: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise CellxGeneError(f"{label} must be an integer from 1 to {maximum}")
    return value


def _bounded_json(value: Any, label: str, depth: int = 0) -> Any:
    if depth > MAX_METADATA_DEPTH:
        raise CellxGeneError(f"{label} is nested too deeply")
    if value is None or isinstance(value, (str, bool)):
        if isinstance(value, str):
            return _text(value, label, MAX_DESCRIPTION_CHARS, optional=True)
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CellxGeneError(f"{label} contains a nonfinite number")
        return value
    if isinstance(value, list):
        if len(value) > MAX_METADATA_ITEMS:
            raise CellxGeneError(f"{label} has too many items")
        return [_bounded_json(item, label, depth + 1) for item in value]
    if isinstance(value, dict):
        if len(value) > MAX_METADATA_ITEMS:
            raise CellxGeneError(f"{label} has too many fields")
        result = {}
        for key, item in value.items():
            key = _text(key, f"{label} key", 128)
            result[key] = _bounded_json(item, label, depth + 1)
        return result
    raise CellxGeneError(f"{label} contains a non-JSON value")


def normalize_asset(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise CellxGeneError("H5AD asset must be an object")
    if raw.get("filetype") != "H5AD":
        raise CellxGeneError("Normalized asset filetype must be exactly H5AD")
    declared_bytes = _integer(raw.get("filesize"), "H5AD filesize", MAX_DECLARED_ASSET_BYTES)
    digest = raw.get("sha256")
    if digest is not None and not isinstance(digest, str):
        raise CellxGeneError("H5AD sha256 must be text when supplied")
    if isinstance(digest, str) and _SHA256.fullmatch(digest):
        digest = digest.lower()
    else:
        digest = None
    return {
        "filetype": "H5AD",
        "url": validate_asset_url(raw.get("url")),
        "declared_bytes": declared_bytes,
        "sha256": digest,
    }


def _ontology_list(value: Any, label: str) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) > MAX_METADATA_ITEMS:
        raise CellxGeneError(f"{label} must be a bounded list")
    rows = []
    for item in value:
        if not isinstance(item, dict):
            raise CellxGeneError(f"{label} entries must be objects")
        rows.append({
            "label": _text(item.get("label"), f"{label} label", 512),
            "ontology_term_id": _text(item.get("ontology_term_id"), f"{label} ontology ID", 128),
        })
    return rows


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_METADATA_ITEMS:
        raise CellxGeneError(f"{label} must be a bounded list")
    return [_text(item, label, 512) for item in value]


def _reject_tombstone(raw: dict[str, Any], label: str) -> None:
    for field in ("tombstone", "tombstoned"):
        if field in raw and (not isinstance(raw[field], bool) or raw[field]):
            raise CellxGeneError(f"{label} tombstones are not ordinary public results")


def normalize_dataset(raw: Any, *, list_stub: bool = False) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise CellxGeneError("Dataset must be an object")
    _reject_tombstone(raw, "Dataset")
    dataset_id = validate_uuid(raw.get("dataset_id"), "dataset_id")
    version_id = validate_uuid(raw.get("dataset_version_id"), "dataset_version_id")
    if "title" not in raw and not list_stub:
        raise CellxGeneError("Dataset title is required for detail metadata")
    if "cell_count" not in raw and not list_stub:
        raise CellxGeneError("Dataset cell_count is required for detail metadata")
    title = _text(raw.get("title"), "Dataset title", MAX_TITLE_CHARS, optional=True)
    count = raw.get("cell_count")
    cell_count = None if count is None and list_stub else _integer(count, "Dataset cell_count", MAX_CELL_COUNT)
    schema = raw.get("schema_version")
    if not isinstance(schema, str) or not _SCHEMA_VERSION.fullmatch(schema):
        raise CellxGeneError("Dataset schema_version must be a three-part version")
    raw_assets = raw.get("assets")
    if not isinstance(raw_assets, list) or not 1 <= len(raw_assets) <= MAX_ASSETS_PER_DATASET:
        raise CellxGeneError("Dataset assets must be a bounded nonempty list")
    assets = []
    seen_urls = set()
    for item in raw_assets:
        if not isinstance(item, dict):
            raise CellxGeneError("Dataset asset entries must be objects")
        filetype = item.get("filetype")
        if not isinstance(filetype, str) or not 1 <= len(filetype) <= 32:
            raise CellxGeneError("Dataset asset filetype must be bounded text")
        if filetype != "H5AD":
            continue
        asset = normalize_asset(item)
        if asset["url"] in seen_urls:
            raise CellxGeneError("Duplicate H5AD asset URL within a dataset")
        seen_urls.add(asset["url"])
        assets.append(asset)
    if not 1 <= len(assets) <= MAX_H5AD_ASSETS_PER_DATASET:
        raise CellxGeneError("Dataset must have 1-8 unique H5AD assets")
    assets.sort(key=lambda item: item["url"])
    result = {
        "dataset_id": dataset_id,
        "dataset_version_id": version_id,
        "title": title,
        "cell_count": cell_count,
        "schema_version": schema,
        "assets": assets,
        "source_review_required": True,
        "attribution_required": True,
    }
    for field in _ONTOLOGY_FIELDS:
        if field in raw:
            result[field] = _ontology_list(raw[field], f"Dataset {field}")
    if "suspension_type" in raw:
        result["suspension_type"] = _string_list(raw["suspension_type"], "Dataset suspension_type")
    return result


def _normalize_links(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) > MAX_LINKS:
        raise CellxGeneError("Collection links must be a bounded list")
    result = []
    for item in value:
        if not isinstance(item, dict):
            raise CellxGeneError("Collection link entries must be objects")
        url = _text(item.get("link_url"), "Collection link URL", MAX_URL_CHARS)
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username is not None or parts.password is not None:
            raise CellxGeneError("Collection links must be HTTPS URLs without userinfo")
        result.append({
            "link_name": _text(item.get("link_name"), "Collection link name", 512, optional=True),
            "link_type": _text(item.get("link_type"), "Collection link type", 64),
            "link_url": url,
        })
    return result


def normalize_collection(raw: Any, *, list_stub: bool = False) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise CellxGeneError("Collection must be an object")
    _reject_tombstone(raw, "Collection")
    if "visibility" in raw and raw["visibility"] != "PUBLIC":
        raise CellxGeneError("Only PUBLIC collections are accepted")
    collection_id = validate_uuid(raw.get("collection_id"), "collection_id")
    version_id = validate_uuid(raw.get("collection_version_id"), "collection_version_id")
    raw_datasets = raw.get("datasets")
    if (not isinstance(raw_datasets, list)
            or not 1 <= len(raw_datasets) <= MAX_DATASETS_PER_COLLECTION):
        raise CellxGeneError("Collection datasets must be a bounded nonempty list")
    datasets = []
    dataset_ids, version_ids, asset_urls = set(), set(), set()
    for item in raw_datasets:
        dataset = normalize_dataset(item, list_stub=list_stub)
        if dataset["dataset_id"] in dataset_ids:
            raise CellxGeneError("Duplicate dataset_id within a collection")
        if dataset["dataset_version_id"] in version_ids:
            raise CellxGeneError("Duplicate dataset_version_id within a collection")
        for asset in dataset["assets"]:
            if asset["url"] in asset_urls:
                raise CellxGeneError("Duplicate H5AD asset URL within a collection")
            asset_urls.add(asset["url"])
        dataset_ids.add(dataset["dataset_id"])
        version_ids.add(dataset["dataset_version_id"])
        datasets.append(dataset)
    datasets.sort(key=lambda item: item["dataset_id"])
    result = {
        "collection_id": collection_id,
        "collection_version_id": version_id,
        "name": _text(raw.get("name"), "Collection name", MAX_NAME_CHARS),
        "description": _text(raw.get("description"), "Collection description", MAX_DESCRIPTION_CHARS, optional=True),
        "doi": _text(raw.get("doi"), "Collection DOI", MAX_DOI_CHARS, optional=True),
        "datasets": datasets,
        "source_review_required": True,
        "attribution_required": True,
        "public_data_policy": PUBLIC_DATA_POLICY_URL,
    }
    for field in _DATE_FIELDS:
        if field in raw:
            result[field] = _text(raw[field], f"Collection {field}", MAX_DATE_CHARS, optional=True)
    if "links" in raw:
        result["links"] = _normalize_links(raw["links"])
    if "publisher_metadata" in raw:
        if not isinstance(raw["publisher_metadata"], dict):
            raise CellxGeneError("Collection publisher_metadata must be an object")
        result["publisher_metadata"] = _bounded_json(raw["publisher_metadata"], "Collection publisher_metadata")
    if "consortium" in raw:
        result["consortium"] = _text(raw["consortium"], "Collection consortium", 512, optional=True)
    return result


def _normalize_collection_list(raw: Any) -> list[dict[str, Any]]:
    rows = raw.get("collections") if isinstance(raw, dict) else raw
    if not isinstance(rows, list) or len(rows) > MAX_COLLECTIONS:
        raise CellxGeneError("Public collection response must be a bounded list")
    collections = [normalize_collection(item, list_stub=True) for item in rows]
    collections.sort(key=lambda item: item["collection_id"])
    ids = [item["collection_id"] for item in collections]
    versions = [item["collection_version_id"] for item in collections]
    if len(ids) != len(set(ids)) or len(versions) != len(set(versions)):
        raise CellxGeneError("Duplicate public collection or collection-version identity")
    dataset_ids, dataset_versions, asset_urls = set(), set(), set()
    for item in collections:
        for dataset in item["datasets"]:
            if dataset["dataset_id"] in dataset_ids:
                raise CellxGeneError("Duplicate dataset_id across public collections")
            if dataset["dataset_version_id"] in dataset_versions:
                raise CellxGeneError("Duplicate dataset_version_id across public collections")
            for asset in dataset["assets"]:
                if asset["url"] in asset_urls:
                    raise CellxGeneError("Duplicate H5AD asset URL across public collections")
                asset_urls.add(asset["url"])
            dataset_ids.add(dataset["dataset_id"])
            dataset_versions.add(dataset["dataset_version_id"])
    return collections


def build_manifest(collection: dict[str, Any], datasets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build deterministic version-pinned remote-asset metadata, never a download receipt."""
    available = {item["dataset_id"]: item for item in collection["datasets"]}
    selected = collection["datasets"] if datasets is None else datasets
    if not isinstance(selected, list) or not selected:
        raise CellxGeneError("A manifest requires at least one normalized dataset")
    chosen = []
    seen = set()
    for dataset in selected:
        dataset_id = dataset.get("dataset_id")
        if dataset_id not in available or available[dataset_id] is not dataset and available[dataset_id] != dataset:
            raise CellxGeneError("Manifest dataset does not belong to the normalized collection")
        if dataset_id in seen:
            raise CellxGeneError("Duplicate dataset selected for manifest")
        seen.add(dataset_id)
        chosen.append(copy.deepcopy(dataset))
    chosen.sort(key=lambda item: item["dataset_id"])
    assets = [asset for dataset in chosen for asset in dataset["assets"]]
    return {
        "schema_version": 1,
        "provider": "cellxgene",
        "state": "manifest_only",
        "collection_id": collection["collection_id"],
        "collection_version_id": collection["collection_version_id"],
        "collection_name": collection["name"],
        "collection_url": PUBLIC_COLLECTION_WEB_ROOT + collection["collection_id"],
        "public_data_policy": PUBLIC_DATA_POLICY_URL,
        "source_review_required": True,
        "attribution_required": True,
        "dataset_count": len(chosen),
        "h5ad_asset_count": len(assets),
        "declared_bytes": sum(asset["declared_bytes"] for asset in assets),
        "datasets": chosen,
        "downloaded": False,
        "asset_fetch_attempted": False,
        "h5ad_downloaded": False,
        "scientific_review": "not_established",
        "measurements_imported": False,
    }


def collection_api_url(collection_id: str) -> str:
    return API_ROOT + "/curation/v1/collections/" + validate_uuid(collection_id, "collection_id")


def _dataset_search_text(dataset: dict[str, Any]) -> str:
    metadata = {key: value for key, value in dataset.items() if key != "assets"}
    return json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).casefold()


def _records_for_collection(
    collection: dict[str, Any], query: str, *, exact: bool,
) -> list[dict[str, Any]]:
    collection_text = json.dumps(
        {key: value for key, value in collection.items() if key != "datasets"},
        ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).casefold()
    collection_matches = exact or query in collection_text
    date = collection.get("revised_at") or collection.get("published_at") or collection.get("created_at") or ""
    records = []
    for dataset in collection["datasets"]:
        if not collection_matches and query not in _dataset_search_text(dataset):
            continue
        manifest = build_manifest(collection, [dataset])
        title = dataset["title"] or f"Dataset {dataset['dataset_id']}"
        records.append({
            "title": f"{title} — {collection['name']}",
            "url": PUBLIC_COLLECTION_WEB_ROOT + collection["collection_id"],
            "date": date,
            "collection_id": collection["collection_id"],
            "collection_version_id": collection["collection_version_id"],
            "dataset_id": dataset["dataset_id"],
            "dataset_version_id": dataset["dataset_version_id"],
            "cell_count": dataset["cell_count"],
            "schema_version": dataset["schema_version"],
            "h5ad_asset_count": len(dataset["assets"]),
            "declared_bytes": sum(asset["declared_bytes"] for asset in dataset["assets"]),
            "source_review_required": True,
            "attribution_required": True,
            "manifest": manifest,
        })
    return records


def search_collections(
    query: str, limit: int, fetch_json: Callable[[str], Any],
) -> tuple[Any, list[dict[str, Any]]]:
    query = _text(query, "CELLxGENE query", MAX_QUERY_CHARS)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
        raise CellxGeneError("CELLxGENE result limit must be from 1 to 10")
    folded = query.casefold()
    try:
        collection_id = validate_uuid(query, "collection_id")
    except CellxGeneError:
        collection_id = None
    if collection_id is not None:
        raw = fetch_json(collection_api_url(collection_id))
        collection = normalize_collection(raw)
        if collection["collection_id"] != collection_id:
            raise CellxGeneError("Collection detail response identity did not match the request")
        records = _records_for_collection(collection, folded, exact=True)
    else:
        raw = fetch_json(PUBLIC_COLLECTIONS_URL)
        collections = _normalize_collection_list(raw)
        records = [record for collection in collections
                   for record in _records_for_collection(collection, folded, exact=False)]
    records.sort(key=lambda item: (item["collection_id"], item["dataset_id"]))
    return raw, records[:limit]


def _json_bytes(value: Any) -> bytes:
    try:
        encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise CellxGeneError("Public metadata is not serializable bounded JSON") from None
    if len(encoded) > MAX_RESPONSE_BYTES:
        raise CellxGeneError("Public metadata output exceeds 8 MiB")
    return encoded


def _new_output_directory(output_dir: str | os.PathLike[str]) -> Path:
    base_absolute = Path(os.path.abspath(regen.PROV / "biohub"))
    candidate = Path(os.path.abspath(Path(output_dir)))
    try:
        candidate.relative_to(base_absolute)
    except ValueError:
        raise CellxGeneError("BioHub output must be beneath data/provenance/biohub") from None
    if candidate == base_absolute or candidate.exists() or candidate.is_symlink():
        raise CellxGeneError("BioHub output must be a new nonsymlink directory")
    if base_absolute.is_symlink():
        raise CellxGeneError("BioHub output root must not be a symbolic link")
    try:
        base_absolute.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CellxGeneError("BioHub output root is unavailable") from exc
    base = base_absolute.resolve(strict=True)
    current = base_absolute
    relative = candidate.relative_to(base_absolute)
    for component in relative.parts[:-1]:
        current = current / component
        if current.is_symlink() or not current.is_dir():
            raise CellxGeneError("BioHub output parents must be nonsymlink directories")
    if not candidate.parent.is_dir():
        raise CellxGeneError("BioHub output parent must already exist")
    try:
        candidate.parent.resolve(strict=True).relative_to(base)
    except ValueError:
        raise CellxGeneError("BioHub output escapes its confined root") from None
    return candidate


def _publish(output_dir: Path, files: list[tuple[str, bytes]]) -> None:
    stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=output_dir.parent))
    try:
        for name, content in files:
            (stage / name).write_bytes(content)
        if output_dir.exists() or output_dir.is_symlink():
            raise CellxGeneError("BioHub output appeared before publication; refusing to overwrite")
        stage.rename(output_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def write_resource_catalog(output_dir: str | os.PathLike[str]) -> dict[str, Any]:
    destination = _new_output_directory(output_dir)
    resources = resource_catalog()
    content = _json_bytes({"resources": resources})
    _publish(destination, [("resources.json", content)])
    return {
        "output_dir": str(destination),
        "resource_count": len(resources),
        "implemented_network_capabilities": 1,
        "h5ad_downloaded": False,
        "asset_fetch_attempted": False,
    }


def fetch_collection_manifest(
    collection_id: str,
    output_dir: str | os.PathLike[str],
    *,
    fetch_json: Callable[[str], Any],
    record: Callable[..., Path],
) -> dict[str, Any]:
    destination = _new_output_directory(output_dir)
    url = collection_api_url(collection_id)
    raw = fetch_json(url)
    collection = normalize_collection(raw)
    manifest = build_manifest(collection)
    source_content = _json_bytes(raw)
    manifest_content = _json_bytes(manifest)
    _publish(destination, [("source.json", source_content), ("manifest.json", manifest_content)])
    source_path = destination / "source.json"
    manifest_path = destination / "manifest.json"
    source_hash = hashlib.sha256(source_content).hexdigest()
    manifest_hash = hashlib.sha256(manifest_content).hexdigest()
    observed_status = getattr(fetch_json, "last_http_status", None)
    if isinstance(observed_status, bool) or not isinstance(observed_status, int):
        observed_status = None
    payload = {
        "source_url": url,
        "requested_urls": [url],
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "http_status": observed_status,
        "collection_id": collection["collection_id"],
        "collection_version_id": collection["collection_version_id"],
        "dataset_count": manifest["dataset_count"],
        "h5ad_asset_count": manifest["h5ad_asset_count"],
        "declared_bytes": manifest["declared_bytes"],
        "h5ad_downloaded": False,
        "asset_fetch_attempted": False,
        "measurements_imported": False,
        "metadata_outputs": {
            "source.json": {"sha256": source_hash, "bytes": len(source_content)},
            "manifest.json": {"sha256": manifest_hash, "bytes": len(manifest_content)},
        },
        "hash_scope": "Metadata JSON only; these are not H5AD checksums",
    }
    receipt = record("cellxgene", payload, [source_path, manifest_path])
    return {
        "collection_id": collection["collection_id"],
        "collection_version_id": collection["collection_version_id"],
        "dataset_count": manifest["dataset_count"],
        "h5ad_asset_count": manifest["h5ad_asset_count"],
        "declared_bytes": manifest["declared_bytes"],
        "http_status": observed_status,
        "output_dir": str(destination),
        "source_metadata_sha256": source_hash,
        "source_metadata_bytes": len(source_content),
        "manifest_metadata_sha256": manifest_hash,
        "manifest_metadata_bytes": len(manifest_content),
        "provenance_receipt": str(receipt),
        "h5ad_downloaded": False,
        "asset_fetch_attempted": False,
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _public_get(url: str) -> Any:
    """One bounded unauthenticated GET for the CLI's fixed metadata endpoint."""
    _public_get.last_http_status = None
    request = Request(url, headers={"User-Agent": regen.UA, "Accept": "application/json"})
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=60) as response:
            status = response.status
            content = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        status = exc.code
        exc.close()
        raise CellxGeneError(f"CELLxGENE metadata GET returned HTTP {status}") from None
    except (URLError, OSError, TimeoutError):
        raise CellxGeneError("CELLxGENE metadata GET failed: network timeout or connection failure") from None
    if status != 200:
        raise CellxGeneError(f"CELLxGENE metadata GET returned HTTP {status}")
    if len(content) > MAX_RESPONSE_BYTES:
        raise CellxGeneError("CELLxGENE metadata response exceeded 8 MiB")
    try:
        text = content.decode("utf-8")
        result = json.loads(text, parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError):
        raise CellxGeneError("CELLxGENE metadata GET returned invalid JSON") from None
    _public_get.last_http_status = status
    return result


_public_get.last_http_status = None

# ResearchDesk reuses this exact no-redirect transport only for CELLxGENE.
# Keep the CLI's existing private name and function attributes unchanged.
public_get = _public_get


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="regen biohub")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    resources = subparsers.add_parser("resources", help="write the static link-only BioHub resource catalog")
    resources.add_argument("--out", required=True)
    collection = subparsers.add_parser("collection", help="inspect one public collection without fetching H5AD")
    collection.add_argument("collection_id")
    collection.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation == "resources":
            result = write_resource_catalog(args.out)
        else:
            result = fetch_collection_manifest(
                args.collection_id, args.out, fetch_json=_public_get, record=regen.record)
    except (CellxGeneError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
