#!/usr/bin/env python3
"""Validate structure, provenance references and local simulation artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
MANIFEST = HERE / "simulation-toolchain.json"
SCHEMA = HERE / "manifest-schema.json"


def validate(manifest_path=MANIFEST, *, workspace=WORKSPACE, verify_files=True) -> dict:
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError("jsonschema is required for simulation manifest validation") from exc
    document = json.loads(Path(manifest_path).read_bytes())
    schema = json.loads(SCHEMA.read_bytes())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(document)
    by_id = {artifact["artifact_id"]: artifact for artifact in document["artifacts"]}
    if len(by_id) != len(document["artifacts"]):
        raise ValueError("duplicate artifact_id")
    steps = document["steps"]
    if len({step["step_id"] for step in steps}) != len(steps):
        raise ValueError("duplicate step_id")
    producer = {}
    for index, step in enumerate(steps):
        for field in ("input_artifacts", "output_artifacts"):
            references = step[field]
            if len(references) != len(set(references)):
                raise ValueError(f"{step['step_id']} has duplicate {field}")
            for artifact_id in references:
                if artifact_id not in by_id:
                    raise ValueError(f"{step['step_id']} refers to unknown artifact {artifact_id}")
        for artifact_id in step["output_artifacts"]:
            if artifact_id in producer:
                raise ValueError(f"multiple producers for {artifact_id}")
            producer[artifact_id] = index
    for index, step in enumerate(steps):
        for artifact_id in step["input_artifacts"]:
            source = producer.get(artifact_id)
            if source is not None and source >= index:
                raise ValueError(f"{step['step_id']} consumes {artifact_id} before it is produced")
            if (source is not None and step["execution_status"] == "completed"
                    and steps[source]["execution_status"] != "completed"):
                raise ValueError(f"completed step consumes output of an unrun step: {artifact_id}")

    workspace = Path(workspace).resolve()
    for artifact_id, artifact in by_id.items():
        path_text = artifact["path"]
        path = PurePosixPath(path_text)
        if (path.is_absolute() or ".." in path.parts or "\\" in path_text
                or PureWindowsPath(path_text).drive):
            raise ValueError(f"unsafe artifact path: {path_text}")
        repository_root = (workspace / artifact["repository"]).resolve()
        repository_root.relative_to(workspace)
        local = (repository_root / Path(*path.parts)).resolve()
        local.relative_to(repository_root)
        if not verify_files:
            continue
        data = local.read_bytes()
        if hashlib.sha256(data).hexdigest() != artifact["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {artifact_id}")
        if len(data) != artifact["size_bytes"]:
            raise ValueError(f"byte-count mismatch for {artifact_id}")
    return document


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--workspace", type=Path, default=WORKSPACE,
                        help="parent directory containing the sibling repositories")
    parser.add_argument("--structure-only", action="store_true",
                        help="validate the contract without checking artifact bytes")
    args = parser.parse_args(argv)
    result = validate(args.manifest, workspace=args.workspace,
                      verify_files=not args.structure_only)
    scope = "Structure only; artifact bytes NOT verified" if args.structure_only else "Structure and artifact hashes verified"
    print(f"{scope}: {result['workflow_id']} ({len(result['artifacts'])} artifacts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
