#!/usr/bin/env python3
"""Explicit, resumable JapanFold OpenFold3 structure predictions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

import regen

BASE_URL = "https://api.japanfold.aiand.com"
MAX_JSON_BYTES = 2_000_000
MAX_ARCHIVE_BYTES = 700_000_000
MAX_UNPACKED_BYTES = 700_000_000
MAX_ARCHIVE_FILES = 60
TERMINAL = {"succeeded", "failed", "canceled"}
RETRYABLE = {429, 500, 502, 503, 504}
AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWYX")
JOB_ID = re.compile(r"[0-9a-f]{32}\Z")
SAFE_NAME = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")


class JapanFoldError(ValueError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request: Request, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        # urllib can forward Authorization to another host on redirect.
        return None


def _api_key() -> str:
    key = os.environ.get("JAPANFOLD_API_KEY", "").strip()
    if key:
        return key
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            name, sep, value = line.strip().partition("=")
            if sep and name.strip() == "JAPANFOLD_API_KEY":
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                return value
    return ""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _bytes_write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(value)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _request_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json_read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JapanFoldError(f"Missing or invalid job file: {path.name}") from exc
    if not isinstance(value, dict):
        raise JapanFoldError(f"Invalid job file: {path.name}")
    return value


def _read_fasta(path: Path) -> tuple[str, bytes]:
    try:
        if path.stat().st_size > 100_000:
            raise JapanFoldError("FASTA input exceeds size limit")
        raw = path.read_bytes()
        lines = raw.decode("utf-8-sig").splitlines()
    except OSError as exc:
        raise JapanFoldError("Cannot read FASTA input") from exc
    headers = [i for i, line in enumerate(lines) if line.startswith(">")]
    if len(headers) != 1 or headers[0] != 0:
        raise JapanFoldError("FASTA must contain exactly one protein sequence")
    sequence = "".join(line.strip().upper() for line in lines[1:] if line.strip())
    if not sequence or any(residue not in AMINO_ACIDS for residue in sequence):
        raise JapanFoldError("FASTA contains no sequence or unsupported residue symbols")
    return sequence, raw


def _read_complex(path: Path) -> tuple[str, int, bytes]:
    try:
        if path.stat().st_size > 200_000:
            raise JapanFoldError("Complex input exceeds size limit")
        raw = path.read_bytes()
        content = raw.decode("utf-8-sig")
    except OSError as exc:
        raise JapanFoldError("Cannot read complex input") from exc
    if not content or len(content) > 50_000:
        raise JapanFoldError("Complex input must contain 1-50000 characters")
    if content.lstrip().startswith(">"):
        records = []
        current = []
        headers = 0
        for line in content.splitlines():
            if line.startswith(">"):
                if headers and not current:
                    raise JapanFoldError("Complex FASTA has an empty chain")
                if headers:
                    records.append("".join(current))
                    current = []
                headers += 1
            elif line.strip():
                if not headers:
                    raise JapanFoldError("Invalid complex FASTA")
                current.append(line.strip().upper())
        if current:
            records.append("".join(current))
        if not 1 <= len(records) <= 10 or any(not re.fullmatch(r"[A-Z]+", item) for item in records):
            raise JapanFoldError("Complex FASTA must contain nonempty chains with letters only")
        return content, sum(map(len, records)), raw
    try:
        import yaml
    except ImportError as exc:
        raise JapanFoldError("PyYAML is required to validate Boltz YAML input") from exc
    try:
        document = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise JapanFoldError("Invalid Boltz YAML input") from exc
    if not isinstance(document, dict) or set(document) != {"sequences"}:
        raise JapanFoldError("OpenFold3 input must contain only a sequences block")
    chains = document["sequences"]
    if not isinstance(chains, list) or not 1 <= len(chains) <= 10:
        raise JapanFoldError("Boltz YAML must contain 1-10 chains")
    total = 0
    for chain in chains:
        if not isinstance(chain, dict) or len(chain) != 1:
            raise JapanFoldError("Each Boltz YAML chain needs one molecule type")
        molecule_type, data = next(iter(chain.items()))
        if molecule_type not in {"protein", "dna", "rna"}:
            raise JapanFoldError("JapanFold OpenFold3 supports protein, DNA and RNA chains; no ligands")
        if not isinstance(data, dict) or not isinstance(data.get("sequence"), str):
            raise JapanFoldError("Each Boltz YAML chain needs a sequence")
        sequence = data["sequence"].upper()
        allowed = AMINO_ACIDS if molecule_type == "protein" else set("ACGTN") if molecule_type == "dna" else set("ACGUN")
        if not sequence or any(symbol not in allowed for symbol in sequence):
            raise JapanFoldError(f"Invalid {molecule_type} chain sequence")
        total += len(sequence)
    return content, total, raw


def _job_id(job: dict[str, Any]) -> str:
    value = job.get("id")
    if not isinstance(value, str) or not JOB_ID.fullmatch(value):
        raise JapanFoldError("JapanFold returned an invalid job id")
    return value


def _safe_job(job: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"id": _job_id(job)}
    for key in ("model", "status", "created_at", "started_at", "finished_at", "stage"):
        value = job.get(key)
        if isinstance(value, str) and len(value) <= 128:
            result[key] = value
    for key in ("progress", "done", "total", "residues", "elapsed_wall_seconds"):
        value = job.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[key] = value
    if isinstance(job.get("results_ready"), bool):
        result["results_ready"] = job["results_ready"]
    if isinstance(job.get("params"), dict):
        result["params"] = {key: job["params"][key] for key in
                            ("diffusion_samples", "output_format", "seed", "use_msa_server")
                            if key in job["params"] and isinstance(job["params"][key], (str, int, bool))}
    return result


def _safe_results(results: dict[str, Any], job_id: str) -> dict[str, Any]:
    if results.get("job_id") != job_id or results.get("ready") is not True:
        raise JapanFoldError("JapanFold results are not ready for this job")
    artifacts = results.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise JapanFoldError("JapanFold returned no result artifacts")
    safe_artifacts = []
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            raise JapanFoldError("Invalid result artifact metadata")
        path = _archive_path(artifact["path"])
        safe_artifacts.append({"path": str(path).replace("\\", "/"),
                               "type": str(artifact.get("type", ""))[:32],
                               "target": str(artifact.get("target", ""))[:64]})
    rows = []
    for row in results.get("rows", []):
        if not isinstance(row, dict):
            continue
        safe_row = {key: row[key] for key in
                    ("id", "status", "confidence_score", "plddt", "complex_plddt", "ptm", "iptm",
                     "msa_depth", "n_residues", "n_chains", "n_atoms", "samples", "runtime_s", "load_s")
                    if key in row and isinstance(row[key], (str, int, float, bool))}
        rows.append(safe_row)
    return {"job_id": job_id, "ready": True, "rows": rows, "artifacts": safe_artifacts}


def _archive_path(name: str) -> Path:
    if not name or "\\" in name or name.startswith("/") or "\x00" in name:
        raise JapanFoldError("Unsafe archive path")
    path = Path(name)
    if any(part in ("", ".", "..") for part in path.parts) or ":" in path.parts[0]:
        raise JapanFoldError("Unsafe archive path")
    return path


class JapanFoldClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else _api_key()
        if not self.api_key:
            raise JapanFoldError("JAPANFOLD_API_KEY is missing from the environment or repo .env")
        self.opener = build_opener(_NoRedirect())

    def _open(self, method: str, path: str, payload: dict[str, Any] | None = None,
              idempotency_key: str | None = None) -> Any:
        if not path.startswith("/v1/") or "?" in path:
            raise JapanFoldError("Invalid JapanFold API path")
        data = _request_bytes(payload) if payload is not None else None
        accept = "application/octet-stream" if path.endswith("/archive") else "application/json"
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": accept}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        for attempt in range(4):
            request = Request(BASE_URL + path, data=data, headers=headers, method=method)
            try:
                return self.opener.open(request, timeout=60)
            except HTTPError as exc:
                if exc.code not in RETRYABLE or attempt == 3:
                    raise JapanFoldError(f"JapanFold HTTP {exc.code} on {method} {path}") from None
                retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
                delay = min(30.0, max(1.0, float(retry_after))) if retry_after.isdigit() else 2 ** attempt
            except (URLError, TimeoutError, OSError):
                if attempt == 3:
                    raise JapanFoldError(f"JapanFold network failure on {method} {path}") from None
                delay = 2 ** attempt
            time.sleep(delay)
        raise JapanFoldError("JapanFold request failed")

    def json(self, method: str, path: str, payload: dict[str, Any] | None = None,
             idempotency_key: str | None = None) -> dict[str, Any]:
        with self._open(method, path, payload, idempotency_key) as response:
            body = response.read(MAX_JSON_BYTES + 1)
        if len(body) > MAX_JSON_BYTES:
            raise JapanFoldError("JapanFold JSON response exceeded size limit")
        try:
            value = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JapanFoldError("JapanFold returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise JapanFoldError("JapanFold returned an unexpected JSON shape")
        return value

    def download_archive(self, job_id: str, dest: Path) -> None:
        with self._open("GET", f"/v1/jobs/{job_id}/archive") as response, dest.open("wb") as output:
            total = 0
            while chunk := response.read(1 << 20):
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise JapanFoldError("JapanFold archive exceeded size limit")
                output.write(chunk)


def _client(client: JapanFoldClient | None) -> JapanFoldClient:
    return client if client is not None else JapanFoldClient()


def submit_prediction(fasta_path: Path | None, run_dir: Path, *, input_path: Path | None = None,
                      name: str | None = None,
                      use_msa_server: bool = True, diffusion_samples: int = 1, seed: int = 0,
                      client: JapanFoldClient | None = None) -> dict[str, Any]:
    if (fasta_path is None) == (input_path is None):
        raise JapanFoldError("Choose exactly one FASTA monomer or complex input file")
    run_dir = Path(run_dir)
    if fasta_path is not None:
        content, source_bytes = _read_fasta(Path(fasta_path))
        input_kind = "sequence"
        residue_count = len(content)
        snapshot_name = "input.fasta"
    else:
        content, residue_count, source_bytes = _read_complex(Path(input_path))
        input_kind = "input"
        snapshot_name = "input.txt"
    if not 1 <= diffusion_samples <= 5 or not 0 <= seed <= 2_147_483_647:
        raise JapanFoldError("Samples must be 1-5 and seed must be 0-2147483647")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    name = name or f"openfold3-{digest[:12]}"
    if not SAFE_NAME.fullmatch(name):
        raise JapanFoldError("Job name must use 1-64 ASCII letters, digits, dots, dashes or underscores")
    api = _client(client)
    catalog = api.json("GET", "/v1/models")
    model = next((item for item in catalog.get("models", [])
                  if isinstance(item, dict) and item.get("id") == "openfold3"), None)
    if not model or not isinstance(model.get("max_residues"), int):
        raise JapanFoldError("OpenFold3 is absent from the live JapanFold catalog")
    if "structure" not in model.get("caps", ["structure"]):
        raise JapanFoldError("Live OpenFold3 catalog does not advertise structure output")
    if residue_count > model["max_residues"]:
        raise JapanFoldError(f"Input exceeds live OpenFold3 limit of {model['max_residues']} residues")
    params = {"use_msa_server": use_msa_server, "diffusion_samples": diffusion_samples,
              "output_format": "cif", "seed": seed}
    payload = {"model": "openfold3", "name": name, input_kind: content, "params": params}
    request_bytes = _request_bytes(payload)
    input_file_hash = hashlib.sha256(source_bytes).hexdigest()
    request_hash = hashlib.sha256(request_bytes).hexdigest()
    plan_path = run_dir / "plan.json"
    if plan_path.exists():
        plan = _json_read(plan_path)
        if (plan.get("input_sha256") != digest or plan.get("input_kind") != input_kind or plan.get("name") != name
                or plan.get("params") != params):
            raise JapanFoldError("Run directory belongs to a different input or request")
        if (run_dir / "job.json").exists():
            return _json_read(run_dir / "job.json")
        if (plan.get("input_file_sha256") not in (None, input_file_hash)
                or plan.get("request_sha256") not in (None, request_hash)):
            raise JapanFoldError("Input snapshot or request changed during submission retry")
    else:
        if run_dir.exists() and any(run_dir.iterdir()):
            raise JapanFoldError("Run directory already contains unrelated files")
        run_dir.mkdir(parents=True, exist_ok=True)
        plan = {"schema_version": 1, "provider": "japanfold", "model": "openfold3",
                "name": name, "input_kind": input_kind, "input_sha256": digest,
                "input_residues": residue_count,
                "params": params, "idempotency_key": uuid.uuid4().hex,
                "model_catalog_checked_at": datetime.now(timezone.utc).isoformat(),
                "live_model_max_residues": model["max_residues"],
                "live_model_measured_wall": model.get("measured_wall"),
                "live_model_caps": [cap for cap in model.get("caps", []) if isinstance(cap, str)],
                "live_model_msa_default": model.get("msa_default"),
                "external_msa_enabled": use_msa_server,
                "price": "Check JapanFold account billing; job API does not quote an exact charge"}
        _json_write(plan_path, plan)
    input_snapshot = run_dir / snapshot_name
    request_snapshot = run_dir / "request.json"
    for path, value in ((input_snapshot, source_bytes), (request_snapshot, request_bytes)):
        if path.exists():
            if path.read_bytes() != value:
                raise JapanFoldError("Saved input or request snapshot differs from the submission")
        else:
            _bytes_write(path, value)
    plan.update(input_file=snapshot_name, input_file_sha256=input_file_hash,
                request_file="request.json", request_sha256=request_hash)
    _json_write(plan_path, plan)
    job = _safe_job(api.json("POST", "/v1/predictions", payload, plan["idempotency_key"]))
    if job.get("model") != "openfold3":
        raise JapanFoldError("JapanFold returned a different prediction model")
    _json_write(run_dir / "job.json", job)
    regen.record("japanfold-submit", {"provider": "japanfold", "model": "openfold3",
                                     "job_id": job["id"], "input_sha256": digest,
                                     "input_kind": input_kind, "input_residues": residue_count,
                                     "params": params,
                                     "catalog_checked_at": plan["model_catalog_checked_at"],
                                     "live_max_residues": plan["live_model_max_residues"],
                                     "live_caps": plan["live_model_caps"],
                                     "input_file_sha256": input_file_hash,
                                     "request_sha256": request_hash},
                 [plan_path, input_snapshot, request_snapshot, run_dir / "job.json"])
    return job


def _fetch_status(run_dir: Path, api: JapanFoldClient, *, receipt: bool) -> dict[str, Any]:
    prior = _json_read(run_dir / "job.json")
    job_id = _job_id(prior)
    job = _safe_job(api.json("GET", f"/v1/jobs/{job_id}"))
    if job["id"] != job_id or job.get("model") != "openfold3":
        raise JapanFoldError("JapanFold job identity or model changed")
    _json_write(run_dir / "job.json", job)
    if receipt:
        regen.record("japanfold-status", {"provider": "japanfold", "job_id": job_id,
                                          "status": job.get("status")}, [run_dir / "job.json"])
    return job


def status_prediction(run_dir: Path, *, client: JapanFoldClient | None = None) -> dict[str, Any]:
    return _fetch_status(Path(run_dir), _client(client), receipt=True)


def wait_prediction(run_dir: Path, *, timeout_seconds: int = 1800, poll_seconds: int = 15,
                    client: JapanFoldClient | None = None) -> dict[str, Any]:
    if not 1 <= timeout_seconds <= 7200 or not 1 <= poll_seconds <= 60:
        raise JapanFoldError("Wait timeout must be 1-7200 seconds and poll interval 1-60 seconds")
    api = _client(client)
    deadline = time.monotonic() + timeout_seconds
    while True:
        job = _fetch_status(Path(run_dir), api, receipt=False)
        if job.get("status") in TERMINAL:
            regen.record("japanfold-status", {"provider": "japanfold", "job_id": job["id"],
                                              "status": job["status"]}, [Path(run_dir) / "job.json"])
            return job
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return job
        time.sleep(min(poll_seconds, remaining))


def _verify_existing_manifest(run_dir: Path, manifest: dict[str, Any]) -> None:
    if (manifest.get("provider"), manifest.get("model"), manifest.get("status")) != (
            "japanfold", "openfold3", "succeeded"):
        raise JapanFoldError("Saved JapanFold manifest identity is invalid")
    _job_id({"id": manifest.get("job_id")})
    root = run_dir.resolve()

    def verify_file(relative_name: str, expected_hash: str, label: str,
                    expected_bytes: int | None = None) -> Path:
        relative = _archive_path(relative_name)
        path = run_dir / relative
        if not path.resolve().is_relative_to(root) or not path.is_file():
            raise JapanFoldError(f"Saved {label} file is missing or outside the run directory")
        if expected_bytes is not None and path.stat().st_size != expected_bytes:
            raise JapanFoldError(f"Saved {label} file size mismatch")
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise JapanFoldError(f"Saved {label} hash is invalid")
        if _sha256(path) != expected_hash:
            raise JapanFoldError(f"Saved {label} hash mismatch")
        return path

    files = manifest.get("files")
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_ARCHIVE_FILES:
        raise JapanFoldError("Saved JapanFold manifest has no valid output list")
    seen = set()
    for entry in files:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise JapanFoldError("Saved JapanFold output entry is invalid")
        relative = _archive_path(entry["path"])
        if not relative.parts or relative.parts[0] != "outputs" or len(relative.parts) < 2:
            raise JapanFoldError("Saved JapanFold output path is invalid")
        if relative.as_posix() in seen:
            raise JapanFoldError("Saved JapanFold output list contains a duplicate")
        seen.add(relative.as_posix())
        if not isinstance(entry.get("bytes"), int) or entry["bytes"] < 0:
            raise JapanFoldError("Saved JapanFold output size is invalid")
        verify_file(entry["path"], entry.get("sha256"), "output", entry["bytes"])
    verify_file("outputs.zip", manifest.get("archive_sha256"), "archive")
    for label, filename_key, hash_key, allowed in (
            ("input", "input_file", "input_file_sha256", {"input.fasta", "input.txt"}),
            ("request", "request_file", "request_sha256", {"request.json"})):
        filename, digest = manifest.get(filename_key), manifest.get(hash_key)
        if filename is None and digest is None:
            continue
        if filename not in allowed:
            raise JapanFoldError(f"Saved {label} snapshot path is invalid")
        verify_file(filename, digest, label)


def collect_prediction(run_dir: Path, *, client: JapanFoldClient | None = None) -> dict[str, Any]:
    run_dir = Path(run_dir)
    if (run_dir / "manifest.json").exists():
        manifest = _json_read(run_dir / "manifest.json")
        _verify_existing_manifest(run_dir, manifest)
        return manifest
    api = _client(client)
    job = _fetch_status(run_dir, api, receipt=False)
    if job.get("status") != "succeeded":
        raise JapanFoldError(f"JapanFold job is {job.get('status', 'unknown')}, not succeeded")
    job_id = job["id"]
    results = _safe_results(api.json("GET", f"/v1/jobs/{job_id}/results"), job_id)
    archive_path = run_dir / "outputs.zip"
    outputs_path = run_dir / "outputs"
    archive_temp = run_dir / f".outputs.{uuid.uuid4().hex}.zip"
    staging = run_dir / f".outputs.{uuid.uuid4().hex}"
    try:
        existing = archive_path.exists() or outputs_path.exists()
        if existing and not (archive_path.is_file() and outputs_path.is_dir()):
            raise JapanFoldError("Run directory has incomplete output files")
        if not existing:
            api.download_archive(job_id, archive_temp)
            staging.mkdir()
        with zipfile.ZipFile(archive_path if existing else archive_temp) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if not members or len(members) > MAX_ARCHIVE_FILES:
                raise JapanFoldError("JapanFold archive has an invalid file count")
            if sum(item.file_size for item in members) > MAX_UNPACKED_BYTES:
                raise JapanFoldError("JapanFold archive exceeds unpacked size limit")
            names = set()
            for item in members:
                relative = _archive_path(item.filename)
                name = relative.as_posix()
                if name in names or (item.external_attr >> 16) & 0o170000 == stat.S_IFLNK:
                    raise JapanFoldError("JapanFold archive contains a duplicate or symbolic link")
                names.add(name)
                output = (outputs_path if existing else staging) / relative
                if existing:
                    if not output.is_file() or output.stat().st_size != item.file_size:
                        raise JapanFoldError("Saved output does not match JapanFold archive")
                    saved_hash = _sha256(output)
                    archive_hash = hashlib.sha256()
                    with archive.open(item) as source:
                        for chunk in iter(lambda: source.read(1 << 20), b""):
                            archive_hash.update(chunk)
                    if archive_hash.hexdigest() != saved_hash:
                        raise JapanFoldError("Saved output hash does not match JapanFold archive")
                else:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as source, output.open("wb") as target:
                        shutil.copyfileobj(source, target, length=1 << 20)
                if output.stat().st_size != item.file_size:
                    raise JapanFoldError("JapanFold archive member size mismatch")
        expected = {entry["path"] for entry in results["artifacts"]}
        if not expected.issubset(names):
            raise JapanFoldError("JapanFold archive is missing a reported artifact")
        _json_write(run_dir / "results.json", results)
        if not existing:
            os.replace(staging, outputs_path)
            os.replace(archive_temp, archive_path)
        files = [{"path": str(Path("outputs") / name).replace("\\", "/"),
                  "bytes": (outputs_path / name).stat().st_size,
                  "sha256": _sha256(outputs_path / name)} for name in sorted(names)]
        plan = _json_read(run_dir / "plan.json")
        input_file = plan.get("input_file")
        request_file = plan.get("request_file")
        input_snapshot = run_dir / input_file if input_file in ("input.fasta", "input.txt") else None
        request_snapshot = run_dir / "request.json" if request_file == "request.json" else None
        for snapshot, hash_key in ((input_snapshot, "input_file_sha256"),
                                   (request_snapshot, "request_sha256")):
            if snapshot is not None and (not snapshot.is_file() or _sha256(snapshot) != plan.get(hash_key)):
                raise JapanFoldError("Saved input or request snapshot hash mismatch")
        manifest = {"schema_version": 1, "provider": "japanfold", "model": "openfold3",
                    "job_id": job_id, "status": "succeeded", "input_sha256": plan["input_sha256"],
                    "input_kind": plan["input_kind"], "input_residues": plan["input_residues"],
                    "input_file": input_file, "input_file_sha256": plan.get("input_file_sha256"),
                    "request_file": request_file, "request_sha256": plan.get("request_sha256"),
                    "params": plan["params"],
                    "model_catalog_checked_at": plan["model_catalog_checked_at"],
                    "live_model_max_residues": plan["live_model_max_residues"],
                    "live_model_caps": plan.get("live_model_caps"),
                    "live_model_msa_default": plan.get("live_model_msa_default"),
                    "job": job, "results": results, "files": files,
                    "archive_sha256": _sha256(archive_path),
                    "interpretation": "Predicted structure and confidence only; no binding or biological efficacy claim"}
        _json_write(run_dir / "manifest.json", manifest)
        regen.record("japanfold-openfold3", {"provider": "japanfold", "model": "openfold3",
                                              "job_id": job_id, "input_sha256": plan["input_sha256"],
                                              "input_file_sha256": plan.get("input_file_sha256"),
                                              "request_sha256": plan.get("request_sha256"),
                                              "archive_sha256": manifest["archive_sha256"],
                                              "files": files},
                     [run_dir / "manifest.json", archive_path] +
                     [path for path in (input_snapshot, request_snapshot) if path is not None] +
                     [run_dir / file["path"] for file in files])
        return manifest
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise JapanFoldError("JapanFold archive is invalid") from exc
    finally:
        archive_temp.unlink(missing_ok=True)
        if staging.exists():
            shutil.rmtree(staging)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    submit = commands.add_parser("submit", help="Submit a protein FASTA or complex file to JapanFold OpenFold3")
    inputs = submit.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--fasta", type=Path, help="Single protein FASTA")
    inputs.add_argument("--input", type=Path, help="Protein/DNA/RNA complex FASTA or Boltz YAML")
    submit.add_argument("--out", type=Path, required=True, help="Ignored local run directory")
    submit.add_argument("--name")
    submit.add_argument("--no-msa", action="store_true", help="Disable external MSA search")
    submit.add_argument("--samples", type=int, default=1)
    submit.add_argument("--seed", type=int, default=0)
    for command in ("status", "wait", "collect"):
        sub = commands.add_parser(command)
        sub.add_argument("--out", type=Path, required=True)
        if command == "wait":
            sub.add_argument("--timeout", type=int, default=1800)
            sub.add_argument("--interval", type=int, default=15)
    ns = parser.parse_args(argv)
    try:
        output_root = (regen.DATA / "structures").resolve()
        output_path = ns.out.resolve()
        if not output_path.is_relative_to(output_root) or output_path == output_root:
            raise JapanFoldError("--out must be a run directory under data/structures")
        ns.out = output_path
        if ns.command == "submit":
            result = submit_prediction(ns.fasta, ns.out, name=ns.name,
                                       input_path=ns.input,
                                       use_msa_server=not ns.no_msa,
                                       diffusion_samples=ns.samples, seed=ns.seed)
        elif ns.command == "status":
            result = status_prediction(ns.out)
        elif ns.command == "wait":
            result = wait_prediction(ns.out, timeout_seconds=ns.timeout, poll_seconds=ns.interval)
        else:
            result = collect_prediction(ns.out)
    except JapanFoldError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
