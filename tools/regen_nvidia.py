"""Opt-in hosted NVIDIA OpenFold3 predictions with bounded, local receipts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = "https://health.api.nvidia.com/v1/biology/openfold/openfold3/predict"
MODEL = "openfold/openfold3"
MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 100 * 1024 * 1024
MAX_STRUCTURE_BYTES = 32 * 1024 * 1024
IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
CHAIN_ID = re.compile(r"[A-Za-z0-9]{1,4}\Z")
DB_NAME = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
PROTEIN = re.compile(r"[ACDEFGHIKLMNPQRSTVWY]{2,4096}\Z")
DNA = re.compile(r"[ATCG]{2,4096}\Z")
RNA = re.compile(r"[AUCG]{2,4096}\Z")
SCORE_FIELDS = (
    "confidence_score", "complex_plddt_score", "complex_pde_score",
    "ptm_score", "iptm_score",
)


class NvidiaError(RuntimeError):
    """A provider or response failure with no response body or credential text."""

    def __init__(self, message: str, *, http_status: int | None = None,
                 submission_unknown: bool = False) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.submission_unknown = submission_unknown


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _receipt(output_dir: Path, request_path: Path, status: str,
             files: list[Path], *, http_status: int | None = None,
             backfilled_from_saved_manifest: bool = False) -> Path:
    data_root = Path(os.environ.get("REGEN_DATA", Path(__file__).resolve().parents[1] / "data"))
    provenance = data_root / "provenance"
    provenance.mkdir(parents=True, exist_ok=True)
    request = json.loads(request_path.read_bytes())
    outputs = []
    for path in files:
        blob = path.read_bytes()
        outputs.append({"path": str(path), "sha256": hashlib.sha256(blob).hexdigest(),
                        "bytes": len(blob)})
    record = {
        "action": "fold-nvidia",
        "when": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "provider": "nvidia", "model": MODEL, "status": status,
            "request_id": request.get("request_id"),
            "request_sha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
            "http_status": http_status,
            "run_directory": str(output_dir),
            "receipt_origin": "local_backfill" if backfilled_from_saved_manifest else "run",
        },
        "outputs": outputs,
    }
    path = provenance / f"{time.time_ns()}_fold-nvidia.json"
    path.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return path


def _object(value: object, label: str, allowed: set[str]) -> dict:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    extra = set(value) - allowed
    if extra:
        raise ValueError(f"{label} contains unsupported fields")
    return value


def _identifier(value: object, label: str) -> None:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a short ASCII identifier")


def _chain_ids(value: object, output_format: str) -> list[str]:
    ids = [value] if isinstance(value, str) else value
    if not isinstance(ids, list) or not ids or len(ids) > 5:
        raise ValueError("molecule id must be a chain ID or a list of 1-5 chain IDs")
    if any(not isinstance(chain, str) or not CHAIN_ID.fullmatch(chain) for chain in ids):
        raise ValueError("chain IDs must be 1-4 alphanumeric characters")
    if len(set(ids)) != len(ids):
        raise ValueError("chain IDs must be unique within a molecule")
    if output_format == "pdb" and any(len(chain) != 1 for chain in ids):
        raise ValueError("PDB output requires one-character chain IDs")
    return ids


def _msa(value: object, label: str, sequence: str) -> None:
    if not isinstance(value, dict) or not 1 <= len(value) <= 3:
        raise ValueError(f"{label} must contain 1-3 databases")
    for database, formats in value.items():
        if not isinstance(database, str) or not DB_NAME.fullmatch(database):
            raise ValueError(f"{label} database name is invalid")
        if not isinstance(formats, dict) or not 1 <= len(formats) <= 2:
            raise ValueError(f"{label} format map is invalid")
        for format_name, raw_record in formats.items():
            if format_name not in ("a3m", "csv"):
                raise ValueError(f"{label} format must be a3m or csv")
            record = _object(raw_record, f"{label} record", {"alignment", "format", "rank"})
            alignment = record.get("alignment")
            if record.get("format") != format_name or not isinstance(alignment, str):
                raise ValueError(f"{label} alignment/format is invalid")
            if not 1 <= len(alignment.encode("utf-8")) <= 2 * 1024 * 1024:
                raise ValueError(f"{label} alignment exceeds the 2 MiB limit")
            if "rank" in record and (type(record["rank"]) is not int or record["rank"] < -1):
                raise ValueError(f"{label} rank is invalid")
            if format_name == "a3m":
                lines = alignment.splitlines()
                first = lines[1].strip() if len(lines) > 1 and lines[0].startswith(">") else ""
            else:
                try:
                    rows = csv.reader(io.StringIO(alignment), strict=True)
                    header = next(rows)
                    first_row = next(rows)
                    first = first_row[header.index("sequence")]
                except (csv.Error, StopIteration, ValueError, IndexError):
                    first = ""
            if first != sequence:
                raise ValueError(f"{label} first sequence must match the molecule sequence")


def validate_request(request: object) -> bytes:
    """Validate the supported native NIM subset and return canonical JSON bytes."""
    top = _object(request, "request", {"request_id", "inputs"})
    if "request_id" in top:
        _identifier(top["request_id"], "request_id")
    inputs = top.get("inputs")
    if not isinstance(inputs, list) or len(inputs) != 1:
        raise ValueError("inputs must contain exactly one prediction")
    item = _object(inputs[0], "input", {"input_id", "molecules", "diffusion_samples", "output_format"})
    if "input_id" in item:
        _identifier(item["input_id"], "input_id")
    count = item.get("diffusion_samples", 1)
    if type(count) is not int or not 1 <= count <= 5:
        raise ValueError("diffusion_samples must be an integer from 1 to 5")
    output_format = item.get("output_format", "cif")
    if output_format not in ("cif", "pdb"):
        raise ValueError("output_format must be cif or pdb")
    molecules = item.get("molecules")
    if not isinstance(molecules, list) or not 1 <= len(molecules) <= 32:
        raise ValueError("molecules must contain 1-32 entries")
    seen_ids: set[str] = set()
    for index, raw_molecule in enumerate(molecules):
        molecule = _object(raw_molecule, f"molecule {index + 1}", {
            "type", "id", "sequence", "msa", "paired_msa", "structural_templates", "ccd_codes", "smiles",
        })
        kind = molecule.get("type")
        if kind not in ("protein", "dna", "rna", "ligand"):
            raise ValueError(f"molecule {index + 1} has invalid type")
        if "id" in molecule:
            chain_ids = _chain_ids(molecule["id"], output_format)
            if seen_ids.intersection(chain_ids):
                raise ValueError("chain IDs must be unique across molecules")
            seen_ids.update(chain_ids)
        if kind == "ligand":
            if set(molecule) - {"type", "id", "ccd_codes", "smiles"}:
                raise ValueError("ligands accept only ccd_codes or smiles")
            if ("ccd_codes" in molecule) == ("smiles" in molecule):
                raise ValueError("ligand requires exactly one of ccd_codes and smiles")
            if "ccd_codes" in molecule:
                code = molecule["ccd_codes"]
                if not isinstance(code, str) or not re.fullmatch(r"[A-Z0-9]{1,5}", code):
                    raise ValueError("ligand ccd_codes is invalid")
            else:
                smiles = molecule["smiles"]
                if (not isinstance(smiles, str) or not 1 <= len(smiles) <= 4096
                        or any(ord(char) < 33 or ord(char) > 126 for char in smiles)):
                    raise ValueError("ligand smiles must be 1-4096 printable ASCII characters")
            continue
        if set(molecule) & {"ccd_codes", "smiles"}:
            raise ValueError("polymer molecules cannot include ligand fields")
        if kind != "protein" and "structural_templates" in molecule:
            raise ValueError("structural_templates are supported only for proteins")
        if kind == "dna" and set(molecule) & {"msa", "paired_msa"}:
            raise ValueError("DNA molecules do not accept MSA fields")
        if kind == "rna" and "paired_msa" in molecule:
            raise ValueError("RNA molecules do not accept paired_msa")
        sequence = molecule.get("sequence")
        pattern = {"protein": PROTEIN, "dna": DNA, "rna": RNA}[kind]
        if not isinstance(sequence, str) or not pattern.fullmatch(sequence):
            raise ValueError(f"molecule {index + 1} has invalid {kind} sequence")
        if kind in ("protein", "rna") and "msa" not in molecule and "paired_msa" not in molecule:
            raise ValueError(f"{kind} requires an MSA")
        for name in ("msa", "paired_msa"):
            if name in molecule:
                _msa(molecule[name], name, sequence)
        if "structural_templates" in molecule:
            templates = molecule["structural_templates"]
            if not isinstance(templates, list) or len(templates) > 5:
                raise ValueError("structural_templates must contain at most five CIFs")
            for template in templates:
                entry = _object(template, "structural_template", {"structure", "format", "name", "chain_id"})
                structure = entry.get("structure")
                if (entry.get("format") != "cif" or not isinstance(structure, str)
                        or "data_" not in structure[:1024]
                        or len(structure.encode("utf-8")) > 2 * 1024 * 1024):
                    raise ValueError("structural_template must contain a CIF of at most 2 MiB")
                if "name" in entry:
                    _identifier(entry["name"], "structural_template name")
                if "chain_id" in entry and (not isinstance(entry["chain_id"], str)
                                             or not re.fullmatch(r"[A-Za-z0-9]{1,10}", entry["chain_id"])):
                    raise ValueError("structural_template chain_id is invalid")
    encoded = json.dumps(top, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ValueError("request exceeds the 8 MiB limit")
    return encoded


def single_protein_request(sequence: str, *, request_id: str, output_format: str = "cif") -> dict:
    """Build a no-hit MSA example; this is not a homology search."""
    request = {
        "request_id": request_id,
        "inputs": [{
            "input_id": request_id,
            "molecules": [{
                "type": "protein", "id": "A", "sequence": sequence,
                "msa": {"query_only": {"a3m": {
                    "alignment": f">query\n{sequence}\n", "format": "a3m",
                }}},
            }],
            "diffusion_samples": 1,
            "output_format": output_format,
        }],
    }
    validate_request(request)
    return request


def _send(encoded: bytes, api_key: str, timeout: float) -> dict:
    req = Request(ENDPOINT, data=encoded, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "regen-workbench/0.1",
    }, method="POST")
    try:
        with build_opener(_NoRedirect()).open(req, timeout=timeout) as response:
            blob = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        uncertain = exc.code in (408, 429) or exc.code >= 500
        exc.close()
        raise NvidiaError(f"NVIDIA API returned HTTP {exc.code}", http_status=exc.code,
                          submission_unknown=uncertain) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise NvidiaError(f"NVIDIA API connection failed ({type(exc).__name__}); submission status is unknown",
                          submission_unknown=True) from None
    if len(blob) > MAX_RESPONSE_BYTES:
        raise NvidiaError("NVIDIA API response exceeds the 100 MiB limit")
    try:
        result = json.loads(blob)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise NvidiaError("NVIDIA API returned invalid JSON") from None
    if not isinstance(result, dict):
        raise NvidiaError("NVIDIA API returned an invalid result object")
    return result


def _safe_scores(sample: dict) -> dict[str, float]:
    scores = {}
    for name in SCORE_FIELDS:
        value = sample.get(name)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise NvidiaError(f"NVIDIA API returned an invalid {name}")
        scores[name] = float(value)
    return scores


def _safe_runtime(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        name: float(number)
        for name, number in value.items()
        if isinstance(name, str) and DB_NAME.fullmatch(name)
        and isinstance(number, (int, float)) and not isinstance(number, bool)
        and math.isfinite(number)
    }


def _extract(result: dict, requested_format: str, request_id: str | None,
             input_id: str | None) -> tuple[list[tuple[bytes, str, dict]], dict]:
    if request_id is not None and result.get("request_id") not in (None, request_id):
        raise NvidiaError("NVIDIA API response request_id does not match submission")
    outputs = result.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != 1 or not isinstance(outputs[0], dict):
        raise NvidiaError("NVIDIA API returned no single output object")
    output = outputs[0]
    if input_id is not None and output.get("input_id") not in (None, input_id):
        raise NvidiaError("NVIDIA API response input_id does not match submission")
    samples = output.get("structures_with_scores")
    if not isinstance(samples, list) or not 1 <= len(samples) <= 5:
        raise NvidiaError("NVIDIA API returned no bounded structure samples")
    extracted = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict) or sample.get("format") != requested_format:
            raise NvidiaError(f"NVIDIA API returned an invalid format for sample {index + 1}")
        structure = sample.get("structure")
        if not isinstance(structure, str):
            raise NvidiaError(f"NVIDIA API returned no structure for sample {index + 1}")
        blob = structure.encode("utf-8")
        if not 1 <= len(blob) <= MAX_STRUCTURE_BYTES:
            raise NvidiaError(f"NVIDIA API returned an oversized structure for sample {index + 1}")
        if requested_format == "cif":
            plausible = "data_" in structure[:1024]
        else:
            plausible = any(line.startswith(("ATOM  ", "HETATM")) for line in structure.splitlines())
        if not plausible or structure.lstrip().startswith(("http://", "https://")):
            raise NvidiaError(f"NVIDIA API returned invalid structure text for sample {index + 1}")
        extracted.append((blob, requested_format, _safe_scores(sample)))
    metadata = {"runtime_metrics": _safe_runtime(output.get("runtime_metrics"))}
    return extracted, metadata


def predict(request: dict, output_dir: Path, api_key: str, *, timeout: float = 600) -> dict:
    """Submit once to NVIDIA and write a hash-linked, URL-free run record.

    A timed-out POST is never retried automatically because the server may have
    completed it. The output directory must be new to prevent accidental reuse.
    """
    encoded = validate_request(request)
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("NVIDIA_API_KEY is not configured")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 3600:
        raise ValueError("timeout must be between 1 and 3600 seconds")
    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(exist_ok=False)
    request_path = output_dir / "request.json"
    request_path.write_bytes(encoded)
    started = time.monotonic()
    try:
        result = _send(encoded, api_key, float(timeout))
        requested_format = request["inputs"][0].get("output_format", "cif")
        extracted, metadata = _extract(result, requested_format, request.get("request_id"),
                                       request["inputs"][0].get("input_id"))
    except NvidiaError as exc:
        failure = {"provider": "nvidia", "model": MODEL,
                   "status": "unknown" if exc.submission_unknown else "failed",
                   "http_status": exc.http_status, "message": str(exc),
                   "request_sha256": hashlib.sha256(request_path.read_bytes()).hexdigest()}
        status_path = output_dir / "status.json"
        status_path.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        _receipt(output_dir, request_path, failure["status"], [request_path, status_path],
                 http_status=exc.http_status)
        raise
    files = []
    for index, (blob, fmt, scores) in enumerate(extracted, 1):
        name = f"sample-{index:02d}.{fmt}"
        (output_dir / name).write_bytes(blob)
        files.append({"path": name, "sha256": hashlib.sha256(blob).hexdigest(),
                      "bytes": len(blob), "scores": scores})
    manifest = {
        "schema_version": 1,
        "provider": "nvidia",
        "model": MODEL,
        "model_version": None,
        "endpoint": ENDPOINT,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_wall_seconds": round(time.monotonic() - started, 3),
        "request_id": request.get("request_id"),
        "input_id": request["inputs"][0].get("input_id"),
        "request": {"path": request_path.name, "sha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
                    "bytes": request_path.stat().st_size},
        "outputs": files,
        **metadata,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    provenance_path = _receipt(output_dir, request_path, "complete",
                               [request_path, *(output_dir / entry["path"] for entry in files), manifest_path])
    return {"manifest": str(manifest_path), "outputs": [str(output_dir / entry["path"]) for entry in files],
            "scores": [entry["scores"] for entry in files], "elapsed_wall_seconds": manifest["elapsed_wall_seconds"],
            "provenance": str(provenance_path)}


def load_api_key(env_file: Path | None = None) -> str:
    """Read the host key without exposing it in process arguments or output."""
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if key:
        return key
    path = env_file or Path(__file__).resolve().parents[1] / ".env"
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if not stripped.startswith("NVIDIA_API_KEY="):
            continue
        value = stripped.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        return value
    return ""


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="regen fold-nvidia")
    subcommands = parser.add_subparsers(dest="command", required=True)
    run = subcommands.add_parser("predict", help="submit one explicit OpenFold3 JSON request")
    run.add_argument("request", type=Path)
    run.add_argument("--out", required=True, type=Path)
    run.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args(argv)
    try:
        allowed = (Path(os.environ.get("REGEN_DATA", Path(__file__).resolve().parents[1] / "data"))
                   / "structures").resolve()
        destination = args.out.resolve()
        if allowed not in destination.parents:
            raise ValueError("--out must be a new directory under data/structures")
        if not args.request.is_file() or args.request.stat().st_size > MAX_REQUEST_BYTES:
            raise ValueError("request must be a regular JSON file of at most 8 MiB")
        request = json.loads(args.request.read_text(encoding="utf-8"))
        summary = predict(request, args.out, load_api_key(), timeout=args.timeout)
    except (ValueError, NvidiaError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
