"""Strict, one-shot NVIDIA hosted Boltz-2 predictions with local receipts."""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from regen_nvidia import NvidiaError

ENDPOINT = "https://health.api.nvidia.com/v1/biology/mit/boltz2/predict"
MODEL = "mit/boltz2"
MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 100 * 1024 * 1024
MAX_STRUCTURE_BYTES = 32 * 1024 * 1024
MAX_CHAIN_KEYS = 64
MAX_METRIC_FIELDS = 256
MAX_JSON_NODES = 1_000_000
PROTEIN = re.compile(r"[ACDEFGHIKLMNPQRSTVWYX]{1,4096}\Z")
CCD = re.compile(r"[A-Z0-9]{1,5}\Z")
CHAIN_KEY = re.compile(r"[A-Za-z0-9_.:-]{1,32}\Z")
TOP_FIELDS = frozenset({
    "polymers", "ligands", "recycling_steps", "sampling_steps",
    "diffusion_samples", "step_scale", "output_format",
    "sampling_steps_affinity", "diffusion_samples_affinity",
    "affinity_mw_correction",
})
AFFINITY_SETTING_FIELDS = frozenset({
    "sampling_steps_affinity", "diffusion_samples_affinity",
    "affinity_mw_correction",
})
REQUIRED_SCORE_FIELDS = (
    "confidence_scores", "ptm_scores", "complex_plddt_scores",
    "complex_pde_scores",
)
OPTIONAL_SCORE_FIELDS = (
    "iptm_scores", "ligand_iptm_scores", "protein_iptm_scores",
    "complex_iplddt_scores", "complex_ipde_scores",
)
AFFINITY_REQUIRED_FIELDS = (
    "affinity_pic50", "affinity_pred_value", "affinity_probability_binary",
)
AFFINITY_ENSEMBLE_FIELDS = (
    "model_1_affinity_pred_value", "model_1_affinity_probability_binary",
    "model_2_affinity_pred_value", "model_2_affinity_probability_binary",
)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _object(value: object, label: str, allowed: set[str] | frozenset[str]) -> dict:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    if set(value) - allowed:
        raise ValueError(f"{label} contains unsupported fields")
    return value


def _integer(value: object, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer from {low} to {high}")
    return value


def validate_request(request: object) -> bytes:
    """Validate the one-protein/zero-or-one-ligand MVP and canonicalize it."""
    top = _object(request, "request", TOP_FIELDS)
    polymers = top.get("polymers")
    if not isinstance(polymers, list) or len(polymers) != 1:
        raise ValueError("polymers must contain exactly one protein")
    polymer = _object(
        polymers[0], "polymer", {"id", "molecule_type", "sequence"},
    )
    if set(polymer) != {"id", "molecule_type", "sequence"}:
        raise ValueError("polymer requires exactly id, molecule_type, and sequence")
    if polymer["id"] != "A" or polymer["molecule_type"] != "protein":
        raise ValueError("the sole polymer must be protein A")
    sequence = polymer["sequence"]
    if not isinstance(sequence, str) or not PROTEIN.fullmatch(sequence):
        raise ValueError("protein sequence must be 1-4096 standard amino-acid letters or X")

    raw_ligands = top.get("ligands", [])
    if not isinstance(raw_ligands, list) or len(raw_ligands) > 1:
        raise ValueError("ligands must be omitted, empty, or contain exactly one ligand")
    ligands = []
    affinity_enabled = False
    if raw_ligands:
        ligand = _object(
            raw_ligands[0], "ligand", {"id", "smiles", "ccd", "predict_affinity"},
        )
        if ligand.get("id") != "B1":
            raise ValueError("the sole ligand must have id B1")
        if ("smiles" in ligand) == ("ccd" in ligand):
            raise ValueError("ligand requires exactly one of smiles and ccd")
        affinity_enabled = ligand.get("predict_affinity", False)
        if type(affinity_enabled) is not bool:
            raise ValueError("predict_affinity must be boolean")
        normalized_ligand = {"id": "B1", "predict_affinity": affinity_enabled}
        if "smiles" in ligand:
            smiles = ligand["smiles"]
            if (not isinstance(smiles, str) or not 1 <= len(smiles) <= 4096
                    or any(ord(char) < 33 or ord(char) > 126 for char in smiles)):
                raise ValueError("ligand smiles must be 1-4096 printable ASCII characters")
            normalized_ligand["smiles"] = smiles
        else:
            ccd = ligand["ccd"]
            if not isinstance(ccd, str) or not CCD.fullmatch(ccd):
                raise ValueError("ligand ccd must be 1-5 uppercase letters or digits")
            normalized_ligand["ccd"] = ccd
        ligands.append(normalized_ligand)

    if not affinity_enabled and AFFINITY_SETTING_FIELDS.intersection(top):
        raise ValueError("affinity settings require ligand B1 with predict_affinity true")
    step_scale = top.get("step_scale", 1.638)
    if (isinstance(step_scale, bool) or not isinstance(step_scale, (int, float))
            or not math.isfinite(step_scale) or not 0.5 <= step_scale <= 5):
        raise ValueError("step_scale must be a finite number from 0.5 to 5")
    if top.get("output_format", "mmcif") != "mmcif":
        raise ValueError("output_format must be mmcif")
    diffusion_samples = top.get("diffusion_samples", 1)
    if type(diffusion_samples) is not int or diffusion_samples != 1:
        raise ValueError("diffusion_samples must be exactly 1")

    canonical = {
        "polymers": [{
            "id": "A", "molecule_type": "protein", "sequence": sequence,
        }],
        "ligands": ligands,
        "recycling_steps": _integer(top.get("recycling_steps", 3), "recycling_steps", 1, 10),
        "sampling_steps": _integer(top.get("sampling_steps", 50), "sampling_steps", 10, 1000),
        "diffusion_samples": 1,
        "step_scale": step_scale,
        "output_format": "mmcif",
    }
    if affinity_enabled:
        canonical.update({
            "sampling_steps_affinity": _integer(
                top.get("sampling_steps_affinity", 200), "sampling_steps_affinity", 10, 1000,
            ),
            "diffusion_samples_affinity": _integer(
                top.get("diffusion_samples_affinity", 5), "diffusion_samples_affinity", 1, 10,
            ),
            "affinity_mw_correction": top.get("affinity_mw_correction", False),
        })
        if type(canonical["affinity_mw_correction"]) is not bool:
            raise ValueError("affinity_mw_correction must be boolean")
    try:
        encoded = json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ValueError("request is not finite JSON") from None
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ValueError("request exceeds the 8 MiB limit")
    return encoded


def load_api_key() -> str:
    """Read only the injected process environment; never fall back to a file."""
    return os.environ.get("NVIDIA_API_KEY", "").strip()


def _api_key(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("NVIDIA_API_KEY is not configured in the process environment")
    if any((ord(char) < 32 and char != " ") or ord(char) > 126 for char in value):
        raise NvidiaError("NVIDIA_API_KEY contains unsafe header characters")
    key = value.strip()
    if any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise NvidiaError("NVIDIA_API_KEY contains unsafe header characters")
    return key


def _decoded_contains_credential(value: object, credential: str) -> bool:
    """Find exact key text after JSON unescaping, including object keys and mmCIF."""
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            if credential in item:
                return True
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return False


def _timeout(value: object) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 1 <= value <= 3600):
        raise ValueError("timeout must be between 1 and 3600 seconds")
    return float(value)


def _json_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise ValueError("nonfinite JSON number")


def _decode_json(blob: bytes) -> object:
    try:
        return json.loads(
            blob.decode("utf-8"), parse_constant=_reject_json_constant,
            object_pairs_hook=_json_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ValueError("invalid bounded UTF-8 JSON") from exc


def _send(encoded: bytes, api_key: str, timeout: float) -> tuple[dict, bytes]:
    """POST once to the fixed endpoint, refusing redirects and response bodies on errors."""
    key = _api_key(api_key)
    seconds = _timeout(timeout)
    if not isinstance(encoded, bytes) or len(encoded) > MAX_REQUEST_BYTES:
        raise ValueError("encoded request must be bounded bytes")
    req = Request(ENDPOINT, data=encoded, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "regen-workbench/0.1",
    }, method="POST")
    try:
        with build_opener(_NoRedirect()).open(req, timeout=seconds) as response:
            status = getattr(response, "status", response.getcode())
            if status != 200:
                raise NvidiaError(
                    f"NVIDIA API returned HTTP {status}", http_status=status,
                )
            blob = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        code = exc.code
        uncertain = code in (408, 429) or 500 <= code <= 599
        exc.close()
        raise NvidiaError(
            f"NVIDIA API returned HTTP {code}", http_status=code,
            submission_unknown=uncertain,
        ) from None
    except NvidiaError:
        raise
    except (URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
        raise NvidiaError(
            f"NVIDIA API connection failed ({type(exc).__name__}); submission status is unknown",
            submission_unknown=True,
        ) from None
    if len(blob) > MAX_RESPONSE_BYTES:
        raise NvidiaError("NVIDIA API response exceeds the 100 MiB limit")
    try:
        result = _decode_json(blob)
    except ValueError:
        raise NvidiaError("NVIDIA API returned invalid JSON") from None
    if not isinstance(result, dict):
        raise NvidiaError("NVIDIA API returned an invalid result object")
    return result, blob


def _check_finite_json(value: object) -> None:
    pending = [value]
    visited = 0
    while pending:
        item = pending.pop()
        visited += 1
        if visited > MAX_JSON_NODES:
            raise NvidiaError("NVIDIA API response has too many JSON values")
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
        elif isinstance(item, float) and not math.isfinite(item):
            raise NvidiaError("NVIDIA API response contains a nonfinite number")


def _number(value: object, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise NvidiaError(f"NVIDIA API returned an invalid {label}")
    return value


def _score_array(result: dict, name: str, *, required: bool) -> list[int | float] | None:
    value = result.get(name)
    if value is None:
        if required:
            raise NvidiaError(f"NVIDIA API response is missing {name}")
        return None
    if not isinstance(value, list):
        raise NvidiaError(f"NVIDIA API returned invalid {name}")
    if not value and not required:
        return None
    if len(value) != 1:
        raise NvidiaError(f"NVIDIA API returned invalid {name} cardinality")
    return [_number(item, name) for item in value]


def _chain_scores(result: dict, name: str, *, pairs: bool,
                  required: bool) -> list[dict] | None:
    value = result.get(name)
    if value is None:
        if required:
            raise NvidiaError(f"NVIDIA API response is missing {name}")
        return None
    if not isinstance(value, list):
        raise NvidiaError(f"NVIDIA API returned invalid {name}")
    if not value and not required:
        return None
    if len(value) != 1 or not isinstance(value[0], dict):
        raise NvidiaError(f"NVIDIA API returned invalid {name} cardinality")
    sample = value[0]
    if not 1 <= len(sample) <= MAX_CHAIN_KEYS:
        raise NvidiaError(f"NVIDIA API returned invalid {name} chain map")
    normalized = {}
    for chain, raw_score in sample.items():
        if not isinstance(chain, str) or not CHAIN_KEY.fullmatch(chain):
            raise NvidiaError(f"NVIDIA API returned invalid {name} chain key")
        if not pairs:
            normalized[chain] = _number(raw_score, name)
            continue
        if not isinstance(raw_score, dict) or not 1 <= len(raw_score) <= MAX_CHAIN_KEYS:
            raise NvidiaError(f"NVIDIA API returned invalid {name} pair map")
        pair_scores = {}
        for other_chain, pair_score in raw_score.items():
            if not isinstance(other_chain, str) or not CHAIN_KEY.fullmatch(other_chain):
                raise NvidiaError(f"NVIDIA API returned invalid {name} pair key")
            pair_scores[other_chain] = _number(pair_score, name)
        normalized[chain] = pair_scores
    return [normalized]


def _metrics(value: object) -> dict[str, int | float]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > MAX_METRIC_FIELDS:
        raise NvidiaError("NVIDIA API returned invalid metrics")
    metrics = {}
    for name, number in value.items():
        if not isinstance(name, str) or not CHAIN_KEY.fullmatch(name):
            raise NvidiaError("NVIDIA API returned an invalid metric name")
        metrics[name] = _number(number, f"metric {name}")
    return metrics


def _affinities(value: object, enabled: bool, expected: int | None) -> dict:
    if not isinstance(value, dict):
        raise NvidiaError("NVIDIA API returned invalid affinities")
    if not enabled:
        if value:
            raise NvidiaError("NVIDIA API returned affinity output that was not requested")
        return {}
    if set(value) != {"B1"} or not isinstance(value["B1"], dict):
        raise NvidiaError("NVIDIA API response must contain only ligand B1 affinities")
    affinity = value["B1"]
    allowed = set(AFFINITY_REQUIRED_FIELDS + AFFINITY_ENSEMBLE_FIELDS)
    if set(affinity) - allowed:
        raise NvidiaError("NVIDIA API returned unsupported affinity fields")
    normalized = {}
    for name in AFFINITY_REQUIRED_FIELDS:
        array = affinity.get(name)
        if not isinstance(array, list) or len(array) != expected:
            raise NvidiaError(f"NVIDIA API returned invalid {name} cardinality")
        normalized[name] = [_number(item, name) for item in array]
    for name in AFFINITY_ENSEMBLE_FIELDS:
        array = affinity.get(name)
        if array is None:
            continue
        if not isinstance(array, list) or len(array) != expected:
            raise NvidiaError(f"NVIDIA API returned invalid {name} cardinality")
        normalized[name] = [_number(item, name) for item in array]
    return {"B1": normalized}


def validate_response(result: object, request_settings: dict) -> dict:
    """Validate and retain flat Boltz arrays without selecting or ranking samples."""
    if not isinstance(result, dict):
        raise NvidiaError("NVIDIA API returned an invalid result object")
    settings = json.loads(validate_request(request_settings))
    affinity_enabled = bool(
        settings["ligands"] and settings["ligands"][0]["predict_affinity"]
    )
    affinity_count = settings.get("diffusion_samples_affinity") if affinity_enabled else None
    _check_finite_json(result)
    for name in ("pae", "pde"):
        if name in result and result[name] is not None:
            raise NvidiaError(f"NVIDIA API returned unsupported non-null {name}")

    structures = result.get("structures")
    if not isinstance(structures, list) or len(structures) != 1:
        raise NvidiaError("NVIDIA API must return exactly one structure")
    entry = structures[0]
    if not isinstance(entry, dict) or entry.get("format") != "mmcif":
        raise NvidiaError("NVIDIA API returned an invalid structure format")
    text = entry.get("structure")
    if not isinstance(text, str):
        raise NvidiaError("NVIDIA API returned no inline structure text")
    try:
        blob = text.encode("utf-8")
    except UnicodeEncodeError:
        raise NvidiaError("NVIDIA API returned invalid structure text") from None
    plausible = "data_" in text[:1024] and "_atom_site" in text
    if (not 1 <= len(blob) <= MAX_STRUCTURE_BYTES or not plausible
            or text.lstrip().startswith(("http://", "https://"))):
        raise NvidiaError("NVIDIA API returned invalid or oversized mmCIF text")

    scores = {}
    for name in REQUIRED_SCORE_FIELDS:
        scores[name] = _score_array(result, name, required=True)
    for name in OPTIONAL_SCORE_FIELDS:
        array = _score_array(result, name, required=False)
        if array is not None:
            scores[name] = array
    scores["chains_ptm_scores"] = _chain_scores(
        result, "chains_ptm_scores", pairs=False, required=True,
    )
    pair_chains = _chain_scores(result, "pair_chains_iptm_scores", pairs=True, required=False)
    if pair_chains is not None:
        scores["pair_chains_iptm_scores"] = pair_chains
    return {
        "structure": blob,
        "scores": scores,
        "affinities": _affinities(result.get("affinities", {}), affinity_enabled, affinity_count),
        "metrics": _metrics(result.get("metrics")),
    }


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _receipt(output_dir: Path, request_path: Path, status: str,
             files: list[Path], *, http_status: int | None = None) -> Path:
    data_root = Path(os.environ.get("REGEN_DATA", Path(__file__).resolve().parents[1] / "data"))
    provenance = data_root / "provenance"
    provenance.mkdir(parents=True, exist_ok=True)
    outputs = []
    for path in files:
        blob = path.read_bytes()
        outputs.append({
            "path": str(path), "sha256": hashlib.sha256(blob).hexdigest(),
            "bytes": len(blob),
        })
    record = {
        "action": "boltz2-predict",
        "when": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "provider": "nvidia", "model": MODEL, "status": status,
            "request_sha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
            "http_status": http_status, "run_directory": str(output_dir),
            "receipt_origin": "run",
        },
        "outputs": outputs,
    }
    path = provenance / f"{time.time_ns()}_boltz2-predict.json"
    path.write_bytes(_json_bytes(record))
    return path


def _destination(output_dir: object) -> tuple[Path, Path]:
    raw = Path(output_dir)
    if raw.is_symlink():
        raise ValueError("--out must be a new nonsymlink directory under data/structures/boltz2")
    destination = raw.resolve()
    data_root = Path(os.environ.get("REGEN_DATA", Path(__file__).resolve().parents[1] / "data"))
    allowed = (data_root / "structures" / "boltz2").resolve()
    if destination == allowed or allowed not in destination.parents:
        raise ValueError("--out must be a new directory under data/structures/boltz2")
    if destination.exists() or destination.is_symlink():
        raise ValueError("--out must not already exist")
    return allowed, destination


def predict(request, output_dir, api_key, *, timeout: float = 600, send=None) -> dict:
    """Submit exactly once and atomically publish either status or success artifacts."""
    encoded = validate_request(request)
    key = _api_key(api_key)
    seconds = _timeout(timeout)
    if key.encode("utf-8") in encoded:
        raise ValueError("request contains credential material")
    allowed, destination = _destination(output_dir)
    allowed.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".boltz2-staging-", dir=allowed))
    request_path = staging / "request.json"
    request_path.write_bytes(encoded)
    started = time.monotonic()
    published = False
    try:
        try:
            transport = _send if send is None else send
            result, raw = transport(encoded, key, seconds)
            if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE_BYTES:
                raise NvidiaError("NVIDIA API response exceeds the 100 MiB limit")
            if key.encode("utf-8") in raw:
                raise NvidiaError("NVIDIA API response contained credential material")
            try:
                raw_result = _decode_json(raw)
            except ValueError:
                raise NvidiaError("NVIDIA API returned invalid JSON") from None
            if raw_result != result:
                raise NvidiaError("NVIDIA API response bytes and result do not agree")
            if _decoded_contains_credential(result, key):
                raise NvidiaError("NVIDIA API response contained credential material")
            extracted = validate_response(result, json.loads(encoded))
        except NvidiaError as exc:
            message = str(exc).replace(key, "[redacted]")[:500]
            failure = {
                "schema_version": 1, "provider": "nvidia", "model": MODEL,
                "status": "unknown" if exc.submission_unknown else "failed",
                "http_status": exc.http_status, "message": message,
                "request_sha256": hashlib.sha256(encoded).hexdigest(),
                "elapsed_wall_seconds": round(time.monotonic() - started, 3),
                "submission_unknown": exc.submission_unknown,
            }
            status_path = staging / "status.json"
            status_path.write_bytes(_json_bytes(failure))
            staging.replace(destination)
            published = True
            _receipt(
                destination, destination / "request.json", failure["status"],
                [destination / "request.json", destination / "status.json"],
                http_status=exc.http_status,
            )
            raise NvidiaError(
                message, http_status=exc.http_status,
                submission_unknown=exc.submission_unknown,
            ) from None

        structure_path = staging / "structure-01.mmcif"
        response_path = staging / "response.json"
        response_path.write_bytes(raw)
        structure_path.write_bytes(extracted["structure"])
        manifest = {
            "schema_version": 1,
            "provider": "nvidia",
            "model": MODEL,
            "model_version": None,
            "endpoint": ENDPOINT,
            "status": "complete",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_wall_seconds": round(time.monotonic() - started, 3),
            "request": {
                "path": "request.json", "sha256": hashlib.sha256(encoded).hexdigest(),
                "bytes": len(encoded),
            },
            "response": {
                "path": "response.json", "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
            "structures": [{
                "path": "structure-01.mmcif", "format": "mmcif",
                "sha256": hashlib.sha256(extracted["structure"]).hexdigest(),
                "bytes": len(extracted["structure"]),
            }],
            "scores": extracted["scores"],
            "affinities": extracted["affinities"],
            "metrics": extracted["metrics"],
            "interpretation": (
                "Boltz-2 structures, confidence scores, and affinities are model predictions only; "
                "arrays are retained without positional best-sample selection or ranking. Predicted "
                "affinity is not measured IC50, Ki, or Kd and does not establish binding or efficacy."
            ),
            "msa": "not supplied; hosted MSA behavior was not established by this adapter",
        }
        manifest_path = staging / "manifest.json"
        manifest_path.write_bytes(_json_bytes(manifest))
        staging.replace(destination)
        published = True
        final_files = [
            destination / "request.json", destination / "response.json",
            destination / "structure-01.mmcif", destination / "manifest.json",
        ]
        receipt = _receipt(destination, final_files[0], "complete", final_files, http_status=200)
        return {
            "status": "complete",
            "manifest": str(destination / "manifest.json"),
            "structure": str(destination / "structure-01.mmcif"),
            "provenance": str(receipt),
            "elapsed_wall_seconds": manifest["elapsed_wall_seconds"],
        }
    finally:
        if not published and staging.exists():
            shutil.rmtree(staging)


def _read_request(path: Path) -> object:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REQUEST_BYTES:
        raise ValueError("request must be a regular JSON file of at most 8 MiB")
    with path.open("rb") as handle:
        blob = handle.read(MAX_REQUEST_BYTES + 1)
    if len(blob) > MAX_REQUEST_BYTES:
        raise ValueError("request must be a regular JSON file of at most 8 MiB")
    return _decode_json(blob)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="regen boltz2")
    subcommands = parser.add_subparsers(dest="command", required=True)
    run = subcommands.add_parser("predict", help="submit one explicit hosted Boltz-2 JSON request")
    run.add_argument("request", type=Path)
    run.add_argument("--out", required=True, type=Path)
    run.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args(argv)
    try:
        request = _read_request(args.request)
        summary = predict(
            request, args.out, load_api_key(), timeout=args.timeout,
        )
    except (ValueError, NvidiaError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
