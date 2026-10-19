"""Read-only, explicitly curated progress cards; no study execution or source fetching."""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlencode

KINDS = {
    "research_plan": "Research objectives and plan",
    "source_data_reanalysis": "Published data reanalysis",
    "observational_reanalysis": "Observational data reanalysis",
    "illustrative_model": "Illustrative model",
    "software_fixture": "Analysis software with synthetic examples",
    "source_audit_conditional_model": "Source audit with conditional calculations",
}
MAX_TEXT_BYTES = 1_000_000
ID = re.compile(r"[a-z0-9][a-z0-9-]{1,79}")


def _text(value, maximum=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("Progress catalog has an invalid text field")
    return value


def _document(repo_root, catalog_path=None):
    path = catalog_path or repo_root / "tools/data/research-progress.json"
    if path.stat().st_size > 256_000:
        raise ValueError("Progress catalog exceeds its size limit")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Progress catalog contains a duplicate field")
            result[key] = value
        return result
    document = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    if not isinstance(document, dict):
        raise ValueError("Unsupported progress catalog")
    rows = document.get("updates")
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1 or not isinstance(rows, list) or len(rows) > 32:
        raise ValueError("Unsupported progress catalog")
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not ID.fullmatch(row["id"]) or row["id"] in ids:
            raise ValueError("Progress IDs must be valid and unique")
        ids.add(row["id"])
        for key in ["title", "topic", "result", "boundary", "next_step"]:
            _text(row.get(key))
        if not isinstance(row.get("evidence_kind"), str) or row["evidence_kind"] not in KINDS:
            raise ValueError("Unknown progress evidence kind")
        stamp = row.get("updated_on", "")
        if not isinstance(stamp, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", stamp) or date.fromisoformat(stamp).isoformat() != stamp:
            raise ValueError("Invalid progress date")
        artifacts = row.get("artifacts")
        if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= 4:
            raise ValueError("A progress card requires one to four declared artifacts")
        artifact_ids = set()
        for artifact in artifacts:
            if not isinstance(artifact, dict) or not isinstance(artifact.get("id"), str) or not ID.fullmatch(artifact["id"]) or artifact["id"] in artifact_ids:
                raise ValueError("Artifact IDs must be valid and unique within a card")
            artifact_ids.add(artifact["id"])
            _text(artifact.get("label"), 200)
            _text(artifact.get("path"), 500)
            if not isinstance(artifact.get("sha256_lf_text"), str) or not re.fullmatch(r"[a-f0-9]{64}", artifact["sha256_lf_text"]):
                raise ValueError("Artifact requires a canonical text hash")
            size = artifact.get("bytes_utf8_lf")
            if isinstance(size, bool) or not isinstance(size, int) or not 0 <= size <= MAX_TEXT_BYTES:
                raise ValueError("Invalid artifact text size")
    return rows


def _artifact_bytes(repo_root, artifact):
    name = artifact["path"]
    relative = PurePosixPath(name)
    if ("\\" in name or ":" in name or relative.is_absolute() or ".." in relative.parts
            or not relative.parts or relative.parts[0] != "studies"
            or relative.suffix not in {".md", ".json", ".csv", ".tsv"}):
        raise ValueError("Artifact is outside the permitted study text files")
    current = repo_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or getattr(current.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("Study artifacts cannot pass through symbolic links")
    path = current.resolve(strict=True)
    path.relative_to(repo_root.resolve() / "studies")
    if not path.is_file() or path.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError("Study text file is unavailable or too large")
    raw = path.read_bytes()
    if len(raw) > MAX_TEXT_BYTES:
        raise ValueError("Study text file is too large")
    content = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    if len(content) != artifact["bytes_utf8_lf"] or hashlib.sha256(content).hexdigest() != artifact["sha256_lf_text"]:
        raise ValueError("Study text differs from the reviewed catalog version")
    return content


def catalog(repo_root, catalog_path=None):
    """Hide stale summaries and withhold downloads unless every card artifact matches."""
    repo_root = Path(repo_root)
    cards = []
    for row in _document(repo_root, catalog_path):
        errors = []
        for artifact in row["artifacts"]:
            try:
                _artifact_bytes(repo_root, artifact)
            except (OSError, ValueError, UnicodeError):
                errors.append(artifact["id"])
        card = {key: row[key] for key in ["id", "title", "topic", "updated_on", "evidence_kind"]}
        card.update(evidence_label=KINDS[row["evidence_kind"]], available=not errors)
        if errors:
            card.update(title="Progress entry needs review", unavailable_artifact_ids=errors,
                        message="Files changed or are unavailable. This summary is withheld until its catalog is reviewed.")
        else:
            card.update({key: row[key] for key in ["result", "boundary", "next_step"]})
            card["artifacts"] = [{"id": a["id"], "label": a["label"],
                "url": "/api/research-progress/artifact?" + urlencode({"update_id": row["id"], "artifact_id": a["id"]})}
                for a in row["artifacts"]]
        cards.append(card)
    return {"updates": cards, "count": len(cards),
            "boundary": "File matching checks integrity of the curated local version; it does not establish biological validity or human benefit."}


def artifact_file(repo_root, update_id, artifact_id, catalog_path=None):
    """Recheck the full card on every download; accepts IDs only, never a submitted path."""
    if not isinstance(update_id, str) or not ID.fullmatch(update_id) or not isinstance(artifact_id, str) or not ID.fullmatch(artifact_id):
        raise ValueError("Invalid progress or artifact ID")
    repo_root = Path(repo_root)
    for row in _document(repo_root, catalog_path):
        if row["id"] != update_id:
            continue
        contents = {a["id"]: _artifact_bytes(repo_root, a) for a in row["artifacts"]}
        if artifact_id not in contents:
            raise ValueError("Unknown progress artifact")
        return contents[artifact_id], "text/plain; charset=utf-8"
    raise ValueError("Unknown progress card")
