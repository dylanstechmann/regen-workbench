#!/usr/bin/env python3
"""A small, allowlisted stdio MCP server for the Regen Workbench.

This server deliberately exposes selected `regen` commands, not a shell,
arbitrary Python, raw HTTP, filesystem browsing, or GitHub credentials.
It uses only the Python standard library so the workbench image needs no MCP
SDK dependency. All protocol output is JSON-RPC on stdout; diagnostics go to
stderr.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(os.environ.get("REGEN_ROOT", "/lab")).resolve() / "workbench" / "config"
DATA_DIR = Path(os.environ.get("REGEN_DATA", Path(os.environ.get("REGEN_ROOT", "/lab")).resolve() / "data"))

PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = {
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
}
SERVER_VERSION = "0.1.0"
MAX_INPUT_CHARS = 1_000_000
MAX_OUTPUT_CHARS = 60_000
WORKBENCH_ROOT = Path(os.environ.get("REGEN_ROOT", "/lab")).resolve()
REGEN_CLI = Path(
    os.environ.get("REGEN_CLI", "/opt/regen/tools/regen.py")
).resolve()
if not REGEN_CLI.exists():
    REGEN_CLI = Path(__file__).with_name("regen.py").resolve()


class ToolInputError(ValueError):
    """An actionable error caused by invalid tool arguments."""


class RegenExecutionError(RuntimeError):
    """A bounded regen subcommand exited unsuccessfully."""


def _schema(
    properties: dict[str, Any], required: list[str] | None = None
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        result["required"] = required
    return result


TOOLS: list[dict[str, Any]] = [
    {
        "name": "regen_pubmed",
        "description": "Search PubMed and save a dated JSON result and provenance receipt.",
        "inputSchema": _schema(
            {
                "query": {"type": "string", "minLength": 1, "maxLength": 500},
                "retmax": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            ["query"],
        ),
    },
    {
        "name": "regen_openalex",
        "description": "Search OpenAlex scholarly works (citations, venues, years) and save a dated JSON result.",
        "inputSchema": _schema(
            {
                "query": {"type": "string", "minLength": 1, "maxLength": 500},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25},
            },
            ["query"],
        ),
    },
    {
        "name": "regen_europepmc",
        "description": "Search Europe PMC (PubMed + preprints + full text) and save a dated JSON result.",
        "inputSchema": _schema(
            {
                "query": {"type": "string", "minLength": 1, "maxLength": 300},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25},
            },
            ["query"],
        ),
    },
    {
        "name": "regen_uniprot",
        "description": "Fetch UniProt metadata and FASTA by accession.",
        "inputSchema": _schema(
            {"accession": {"type": "string", "minLength": 1, "maxLength": 30}},
            ["accession"],
        ),
    },
    {
        "name": "regen_afdb",
        "description": "Fetch an existing AlphaFold Database structure by UniProt accession; does not run a fold.",
        "inputSchema": _schema(
            {"accession": {"type": "string", "minLength": 1, "maxLength": 30}},
            ["accession"],
        ),
    },
    {
        "name": "regen_interpro",
        "description": "Fetch InterPro protein domain/family entries for a UniProt accession.",
        "inputSchema": _schema(
            {"accession": {"type": "string", "minLength": 1, "maxLength": 30}},
            ["accession"],
        ),
    },
    {
        "name": "regen_ensembl",
        "description": "Look up an Ensembl gene/transcript/protein record by stable ID (e.g. ENSG00000141510).",
        "inputSchema": _schema(
            {"id": {"type": "string", "minLength": 1, "maxLength": 22}},
            ["id"],
        ),
    },
    {
        "name": "regen_pdb",
        "description": "Fetch an experimental structure from RCSB PDB by four-character ID.",
        "inputSchema": _schema(
            {"pdb_id": {"type": "string", "minLength": 4, "maxLength": 4}},
            ["pdb_id"],
        ),
    },
    {
        "name": "regen_string",
        "description": "Fetch STRING protein interaction network edges for an identifier and species taxon.",
        "inputSchema": _schema(
            {
                "protein": {"type": "string", "minLength": 1, "maxLength": 100},
                "species": {"type": "string", "minLength": 1, "maxLength": 8},
            },
            ["protein"],
        ),
    },
    {
        "name": "regen_chembl",
        "description": "Search ChEMBL and save a bounded number of molecule records.",
        "inputSchema": _schema(
            {
                "query": {"type": "string", "minLength": 1, "maxLength": 200},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            ["query"],
        ),
    },
    {
        "name": "regen_pubchem",
        "description": "Fetch public PubChem compound properties by a compound name.",
        "inputSchema": _schema(
            {"name": {"type": "string", "minLength": 1, "maxLength": 100}},
            ["name"],
        ),
    },
    {
        "name": "regen_msa",
        "description": "Align an existing FASTA with MAFFT, MUSCLE, or Clustal Omega. Inputs may be under /lab/data or /lab/projects; outputs must be under /lab/data.",
        "inputSchema": _schema(
            {
                "fasta": {"type": "string", "minLength": 1, "maxLength": 1000},
                "output": {"type": "string", "minLength": 1, "maxLength": 1000},
                "engine": {"type": "string", "enum": ["mafft", "muscle", "clustalo"]},
            },
            ["fasta", "output"],
        ),
    },
    {
        "name": "regen_rdkit",
        "description": "Validate one SMILES string and optionally calculate standard RDKit descriptors; this is not an ADMET or efficacy prediction.",
        "inputSchema": _schema(
            {
                "smiles": {"type": "string", "minLength": 1, "maxLength": 10000},
                "descriptors": {"type": "boolean"},
            },
            ["smiles"],
        ),
    },
    {
        "name": "regen_pymol_png",
        "description": "Render a local structure to a PNG using headless PyMOL. Inputs may be under /lab/data or /lab/projects; outputs must be under /lab/data.",
        "inputSchema": _schema(
            {
                "structure": {"type": "string", "minLength": 1, "maxLength": 1000},
                "output": {"type": "string", "minLength": 1, "maxLength": 1000},
            },
            ["structure", "output"],
        ),
    },
    {
        "name": "regen_fold_route",
        "description": "Get a fetch-first structure/folding decision card for an accession or FASTA path; does not launch a model prediction.",
        "inputSchema": _schema(
            {"query": {"type": "string", "minLength": 1, "maxLength": 500}},
            ["query"],
        ),
    },
    {
        "name": "regen_doctor",
        "description": "Report installed workbench tools, Python imports, and visible GPU; writes a provenance receipt.",
        "inputSchema": _schema({}),
    },
]
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}
_LAST_PUBMED_CALL = 0.0
_PUBMED_RATE_LOCK = threading.Lock()
PUBMED_MIN_INTERVAL_SECONDS = 1.0


def _require_string(args: dict[str, Any], key: str, *, max_length: int) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"'{key}' must be a non-empty string")
    if len(value) > max_length:
        raise ToolInputError(f"'{key}' exceeds {max_length} characters")
    if any(ord(char) < 32 for char in value):
        raise ToolInputError(f"'{key}' must not contain control characters")
    return value.strip()


def _bounded_int(
    args: dict[str, Any], key: str, default: int, minimum: int, maximum: int
) -> int:
    value = args.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolInputError(f"'{key}' must be an integer")
    if value < minimum or value > maximum:
        raise ToolInputError(f"'{key}' must be between {minimum} and {maximum}")
    return value


def _contained_path(
    value: str, *, must_exist: bool, writable: bool = False
) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = WORKBENCH_ROOT / path
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError as exc:
        raise ToolInputError("input path does not exist or cannot be resolved") from exc
    allowed_roots = [(WORKBENCH_ROOT / "data").resolve()]
    if not writable:
        allowed_roots.append((WORKBENCH_ROOT / "projects").resolve())
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        roots = "/lab/data" if writable else "/lab/data or /lab/projects"
        raise ToolInputError(f"file paths must stay under {roots}")
    return resolved


def _validate_arguments(name: str, args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        raise ToolInputError("tool arguments must be a JSON object")
    allowed = set(TOOL_BY_NAME[name]["inputSchema"]["properties"])
    extra = set(args) - allowed
    if extra:
        raise ToolInputError(f"unknown argument(s): {', '.join(sorted(extra))}")

    if name == "regen_pubmed":
        result = {"query": _require_string(args, "query", max_length=500)}
        result["--retmax"] = str(_bounded_int(args, "retmax", 10, 1, 50))
        return result
    if name == "regen_openalex":
        result = {"query": _require_string(args, "query", max_length=500)}
        result["--limit"] = str(_bounded_int(args, "limit", 10, 1, 25))
        return result
    if name == "regen_europepmc":
        result = {"query": _require_string(args, "query", max_length=300)}
        result["--limit"] = str(_bounded_int(args, "limit", 10, 1, 25))
        return result
    if name in {"regen_uniprot", "regen_afdb", "regen_interpro"}:
        accession = _require_string(args, "accession", max_length=30)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,29}", accession):
            raise ToolInputError("accession contains unsupported characters")
        return {"accession": accession}
    if name == "regen_ensembl":
        record_id = _require_string(args, "id", max_length=22)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,21}", record_id):
            raise ToolInputError("id contains unsupported characters")
        return {"id": record_id}
    if name == "regen_pdb":
        pdb_id = _require_string(args, "pdb_id", max_length=4)
        if not re.fullmatch(r"[A-Za-z0-9]{4}", pdb_id):
            raise ToolInputError("pdb_id must be exactly four alphanumeric characters")
        return {"pdb_id": pdb_id}
    if name == "regen_string":
        protein = _require_string(args, "protein", max_length=100)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", protein):
            raise ToolInputError("protein contains unsupported characters")
        species = _require_string(args, "species", max_length=8) if "species" in args else "9606"
        if not re.fullmatch(r"\d{1,8}", species):
            raise ToolInputError("species must be a numeric taxonomy ID")
        return {"protein": protein, "--species": species}
    if name == "regen_chembl":
        result = {"query": _require_string(args, "query", max_length=200)}
        result["--limit"] = str(_bounded_int(args, "limit", 10, 1, 50))
        return result
    if name == "regen_pubchem":
        compound = _require_string(args, "name", max_length=100)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .,'()+-]{0,99}", compound):
            raise ToolInputError("name contains unsupported characters")
        return {"name": compound}
    if name == "regen_msa":
        source = _contained_path(
            _require_string(args, "fasta", max_length=1000), must_exist=True
        )
        if not source.is_file():
            raise ToolInputError("fasta must point to an existing regular file")
        if source.stat().st_size > 25 * 1024 * 1024:
            raise ToolInputError("FASTA input exceeds the 25 MiB MCP limit")
        destination = _contained_path(
            _require_string(args, "output", max_length=1000),
            must_exist=False,
            writable=True,
        )
        engine = args.get("engine", "mafft")
        if engine not in {"mafft", "muscle", "clustalo"}:
            raise ToolInputError("engine must be mafft, muscle, or clustalo")
        return {"fasta": str(source), "-o": str(destination), "--engine": engine}
    if name == "regen_rdkit":
        smiles = _require_string(args, "smiles", max_length=10000)
        descriptors = args.get("descriptors", True)
        if not isinstance(descriptors, bool):
            raise ToolInputError("descriptors must be a boolean")
        return {"smiles": smiles, "--descriptors": descriptors}
    if name == "regen_pymol_png":
        structure = _contained_path(
            _require_string(args, "structure", max_length=1000), must_exist=True
        )
        if not structure.is_file():
            raise ToolInputError("structure must point to an existing regular file")
        if structure.stat().st_size > 100 * 1024 * 1024:
            raise ToolInputError("structure exceeds the 100 MiB MCP limit")
        output = _contained_path(
            _require_string(args, "output", max_length=1000),
            must_exist=False,
            writable=True,
        )
        if output.suffix.lower() != ".png":
            raise ToolInputError("output must have a .png extension")
        return {"structure": str(structure), "-o": str(output)}
    if name == "regen_fold_route":
        return {"query": _require_string(args, "query", max_length=500)}
    if name == "regen_doctor":
        return {}
    raise ToolInputError(f"no argument validator for tool '{name}'")


def _cli_args(name: str, values: dict[str, Any]) -> list[str]:
    command = name.removeprefix("regen_").replace("_", "-")
    result = [command]
    for key, value in values.items():
        if key.startswith("--"):
            if isinstance(value, bool):
                if value:
                    result.append(key)
            else:
                result.extend([key, str(value)])
        elif key.startswith("-"):
            result.extend([key, str(value)])
        else:
            result.append(str(value))
    return result


def _redact(text: str) -> str:
    api_key = os.environ.get("NCBI_API_KEY", "")
    if api_key:
        text = text.replace(api_key, "[REDACTED_NCBI_API_KEY]")
    return text


def run_regen(name: str, args: list[str]) -> str:
    timeout = 600 if name in {"regen_msa", "regen_pymol_png"} else 180
    completed = subprocess.run(
        [sys.executable, str(REGEN_CLI), *args],
        cwd=str(WORKBENCH_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=os.environ.copy(),
    )
    stdout = _redact(completed.stdout or "")
    stderr = _redact(completed.stderr or "")
    output = stdout.strip()
    if completed.returncode != 0:
        detail = stderr.strip() or output or f"regen exited with status {completed.returncode}"
        raise RegenExecutionError(f"regen command failed ({completed.returncode}): {detail}")
    if not output:
        output = "Command completed successfully."
    if len(output) > MAX_OUTPUT_CHARS:
        output = output[:MAX_OUTPUT_CHARS] + "\n[output truncated]"
    return output


def call_tool(name: str, raw_args: Any) -> str:
    global _LAST_PUBMED_CALL
    if name not in TOOL_BY_NAME:
        raise KeyError(name)
    validated = _validate_arguments(name, raw_args)
    if name == "regen_pubmed":
        # A PubMed operation makes both ESearch and ESummary requests. Keep
        # calls at least a second apart to stay polite even without an API key.
        with _PUBMED_RATE_LOCK:
            delay = PUBMED_MIN_INTERVAL_SECONDS - (time.monotonic() - _LAST_PUBMED_CALL)
            if _LAST_PUBMED_CALL and delay > 0:
                time.sleep(delay)
            _LAST_PUBMED_CALL = time.monotonic()
    return run_regen(name, _cli_args(name, validated))


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def _list_resources() -> list[dict[str, Any]]:
    """Return the static resource list for resources/list."""
    return [
        {
            "uri": "regen://config/tools.yaml",
            "name": "Workbench capability map",
            "description": (
                "YAML file listing all hardware assumptions, tool capabilities, "
                "fold routing rules, and MCP security policy."
            ),
            "mimeType": "text/yaml",
        },
        {
            "uri": "regen://data/provenance",
            "name": "Provenance receipts",
            "description": (
                "Listing of all provenance receipt JSON files written by regen "
                "tool calls. Read individual receipts by appending the filename, "
                "e.g. regen://data/provenance/<receipt>.json"
            ),
            "mimeType": "application/json",
        },
    ]


def _read_resource(uri: str) -> dict[str, Any]:
    """Read the content of a known resource URI."""
    if uri == "regen://config/tools.yaml":
        tools_yaml = CONFIG_DIR / "tools.yaml"
        if not tools_yaml.is_file():
            return {"contents": [{"uri": uri, "text": "# tools.yaml not found", "mimeType": "text/yaml"}]}
        with tools_yaml.open(encoding="utf-8", errors="replace") as handle:
            text = handle.read(MAX_OUTPUT_CHARS + 1)
        if len(text) > MAX_OUTPUT_CHARS:
            text = text[:MAX_OUTPUT_CHARS] + "\n# [truncated]"
        return {"contents": [{"uri": uri, "text": text, "mimeType": "text/yaml"}]}

    if uri == "regen://data/provenance":
        provenance_dir = DATA_DIR / "provenance"
        if not provenance_dir.is_dir():
            return {"contents": [{"uri": uri, "text": "[]", "mimeType": "application/json"}]}
        files = sorted(provenance_dir.glob("*.json"), key=lambda p: p.name, reverse=True)[:100]
        listing = [{"name": f.name, "bytes": f.stat().st_size} for f in files]
        import json as _json
        return {"contents": [{"uri": uri, "text": _json.dumps(listing, indent=2), "mimeType": "application/json"}]}

    if uri.startswith("regen://data/provenance/") and uri.endswith(".json"):
        filename = uri.removeprefix("regen://data/provenance/")
        # Prevent path traversal: filename must be a plain basename.
        if "/" in filename or "\\" in filename or ".." in filename:
            return {"contents": [{"uri": uri, "text": "invalid filename", "mimeType": "text/plain"}]}
        receipt_path = (DATA_DIR / "provenance" / filename).resolve()
        allowed_root = (DATA_DIR / "provenance").resolve()
        if allowed_root not in receipt_path.parents and receipt_path != allowed_root:
            return {"contents": [{"uri": uri, "text": "path outside provenance directory", "mimeType": "text/plain"}]}
        if not receipt_path.is_file():
            return {"contents": [{"uri": uri, "text": "receipt not found", "mimeType": "text/plain"}]}
        with receipt_path.open(encoding="utf-8", errors="replace") as handle:
            text = handle.read(MAX_OUTPUT_CHARS + 1)
        if len(text) > MAX_OUTPUT_CHARS:
            text = text[:MAX_OUTPUT_CHARS] + "\n[truncated]"
        return {"contents": [{"uri": uri, "text": text, "mimeType": "application/json"}]}

    return {"contents": [{"uri": uri, "text": f"unknown resource: {uri}", "mimeType": "text/plain"}]}


def handle_message(message: Any, state: dict[str, bool]) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid JSON-RPC request")

    method = message.get("method")
    request_id = message.get("id")
    has_id = "id" in message
    if not isinstance(method, str):
        return _error(request_id, -32600, "Invalid JSON-RPC request") if has_id else None
    if has_id and not isinstance(request_id, (str, int)):
        return _error(None, -32600, "Invalid JSON-RPC request id")
    if isinstance(request_id, bool):
        return _error(None, -32600, "Invalid JSON-RPC request id")
    if not has_id and method in {"initialize", "tools/list", "tools/call", "resources/list", "resources/read", "ping"}:
        # JSON-RPC notifications must not trigger an operation with side effects.
        return None
    params = message.get("params", {})
    if not isinstance(params, dict):
        return _error(request_id, -32602, "params must be an object") if has_id else None

    if method == "initialize":
        if not has_id:
            return None
        state["initialize_received"] = True
        requested = params.get("protocolVersion")
        version = (
            requested
            if isinstance(requested, str) and requested in SUPPORTED_PROTOCOL_VERSIONS
            else PROTOCOL_VERSION
        )
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": version,
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {
                    "name": "regen-workbench",
                    "version": SERVER_VERSION,
                },
                "instructions": (
                    "Use only the exposed, bounded regen tools. Results are research aids, not clinical advice. "
                    "Fetch experimental/AlphaFold DB structures before proposing de novo folds; 16 GB VRAM is a hard local limit. "
                    "Tool calls write data and provenance under /lab/data. "
                    "Read the regen://config/tools.yaml resource to see the full capability map."
                ),
            },
        }

    if method == "notifications/initialized":
        if state.get("initialize_received"):
            state["initialized"] = True
        return None
    if method.startswith("notifications/"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    if not state.get("initialized"):
        return _error(request_id, -32002, "Server has not received notifications/initialized")
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"resources": _list_resources()}}
    if method == "resources/read":
        uri = params.get("uri")
        if not isinstance(uri, str) or not uri.strip() or any(ord(char) < 32 for char in uri):
            return _error(request_id, -32602, "uri must be a non-empty string without control characters")
        try:
            result = _read_resource(uri)
        except (OSError, RuntimeError) as exc:
            # Files can disappear, become unreadable, or contain a symlink loop
            # between validation and reading. Keep the client session alive.
            detail = _redact(str(exc))
            print(f"MCP resource read failed: {type(exc).__name__}: {detail}", file=sys.stderr)
            return _error(request_id, -32603, "Resource could not be read")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str) or name not in TOOL_BY_NAME:
            return _error(request_id, -32602, f"Unknown tool: {name}")
        try:
            text = call_tool(name, params.get("arguments", {}))
            result = {"content": [{"type": "text", "text": text}], "isError": False}
        except (ToolInputError, RegenExecutionError, subprocess.TimeoutExpired) as exc:
            result = _tool_error(_redact(str(exc))[:MAX_OUTPUT_CHARS])
        except Exception as exc:  # keep an implementation detail off the wire
            detail = _redact(str(exc))
            print(f"MCP tool {name} failed: {type(exc).__name__}: {detail}", file=sys.stderr)
            result = _tool_error(f"Tool failed: {type(exc).__name__}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    return _error(request_id, -32601, f"Method not found: {method}") if has_id else None


def serve() -> None:
    state = {"initialized": False}
    while raw_line := sys.stdin.readline(MAX_INPUT_CHARS + 1):
        if len(raw_line) > MAX_INPUT_CHARS:
            # Drain only this oversized message in bounded chunks so the next
            # newline-delimited request can still be processed.
            while not raw_line.endswith("\n"):
                raw_line = sys.stdin.readline(MAX_INPUT_CHARS + 1)
                if not raw_line:
                    break
            response = _error(None, -32600, "MCP message exceeds the maximum size")
        else:
            try:
                message = json.loads(raw_line)
            except (ValueError, RecursionError) as exc:
                detail = exc.msg if isinstance(exc, json.JSONDecodeError) else "Invalid or excessively nested JSON"
                response = _error(None, -32700, f"Parse error: {detail}")
            else:
                response = handle_message(message, state)
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":"), ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    serve()