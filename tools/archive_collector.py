"""One bounded collector for every entry of an exported dossier archive.

A dossier archive is only as trustworthy as the way its bytes were gathered. Before this
module, linked research files were collected under size limits while run snapshots were not:
the run-folder walk followed symlinked files out of the run directory, read each file two or
three times (so the hash recorded for the archived bytes could differ from the hash of the file
that was compared with its run manifest), and applied no per-file, per-archive or member-count
limit. This module is the single place those rules now live.

* ``read_regular_file`` reads one regular file beneath a root exactly once, never through a
  symbolic link or reparse point, within a byte limit, and refuses a file that changed while it
  was being read.
* ``walk_regular_files`` lists the regular files below a root without following links and
  reports what it refused (links, special files) instead of silently dropping it.
* ``ArchiveCollector`` applies the same name, duplicate, per-member, total-byte and member-count
  rules to every entry, generated or copied, and records exclusions so that an archive missing a
  source file says so in its own inventory.

The member-name rules intentionally mirror ``verify_dossier._unsafe_member_reason`` (the verifier
must stay a standalone file); a test keeps the two in agreement.

Standard library only. Nothing here opens a network connection or runs a command.
"""
from __future__ import annotations

import hashlib
import io
import os
import stat
import zipfile
from pathlib import Path, PurePosixPath

MAX_MEMBER_BYTES = 20_000_000
# The verifier rejects an archive whose file size or uncompressed total exceeds 100 MB. Zip
# headers and incompressible deflate blocks add overhead to what is collected, so the collector
# stops short of that figure.
VERIFIER_TOTAL_BYTES = 100_000_000
MAX_TOTAL_BYTES = 98_000_000
MAX_MEMBERS = 20_000
MAX_WALK_DEPTH = 32
READ_CHUNK = 1 << 20


class CollectionError(ValueError):
    """The export cannot be produced as asked (a limit, a name or a duplicate)."""


class SourceRefused(CollectionError):
    """One source file is unsuitable for the archive; the caller may exclude it and say so."""

    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def member_name_problem(name: str) -> str | None:
    """Reject archive names that could escape an extraction directory or hide a duplicate."""
    if not isinstance(name, str) or not name or name.endswith("/"):
        return "empty or directory entry"
    if any(ord(char) < 32 or ord(char) == 127 for char in name):
        return "control character in archive path"
    if "\\" in name:
        return "backslash in archive path"
    if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        return "absolute archive path"
    parts = PurePosixPath(name).parts
    if any(part in {"..", "."} for part in parts):
        return "relative traversal segment"
    if PurePosixPath(name).as_posix() != name:
        return "non-canonical archive path"
    if any(part.strip() != part for part in parts):
        return "leading or trailing whitespace in a path segment"
    return None


def _is_link(info: os.stat_result) -> bool:
    """A symbolic link, or on Windows any reparse point (junctions and mount points included)."""
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def read_regular_file(root, relative: str, *, limit: int = MAX_MEMBER_BYTES) -> bytes:
    """Read ``relative`` beneath ``root`` once, within ``limit`` bytes, never through a link.

    Raises ``SourceRefused`` with a machine-readable ``kind`` when the file is missing a safe
    shape: a link at any component, a non-regular file, larger than ``limit``, swapped for another
    file while being opened, or modified while being read. The detail never contains an absolute
    path.
    """
    parts = PurePosixPath(relative).parts
    if not parts or member_name_problem(relative) is not None:
        raise SourceRefused("unsafe_name", f"{relative!r} is not a safe relative path")
    current = Path(root)
    try:
        for part in parts:
            current = current / part
            if _is_link(os.lstat(current)):
                raise SourceRefused("symlink", f"{relative} is or passes through a symbolic link")
        listed = os.lstat(current)
    except OSError as exc:
        raise SourceRefused("unreadable", f"{relative} could not be inspected ({type(exc).__name__})") from None
    if not stat.S_ISREG(listed.st_mode):
        raise SourceRefused("not_regular_file", f"{relative} is not a regular file")
    if listed.st_size > limit:
        raise SourceRefused("too_large", f"{relative} is larger than the {limit} byte limit")

    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        descriptor = os.open(current, flags)
    except OSError as exc:
        raise SourceRefused("unreadable", f"{relative} could not be opened ({type(exc).__name__})") from None
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise SourceRefused("not_regular_file", f"{relative} is not a regular file")
        if listed.st_ino and before.st_ino and (listed.st_ino, listed.st_dev) != (before.st_ino, before.st_dev):
            raise SourceRefused("changed_during_read", f"{relative} was replaced while being opened")
        chunks, remaining = [], limit + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(READ_CHUNK, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise SourceRefused("unreadable", f"{relative} could not be read ({type(exc).__name__})") from None
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if len(raw) > limit:
        raise SourceRefused("too_large", f"{relative} grew beyond the {limit} byte limit while being read")
    if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns) or len(raw) != after.st_size:
        raise SourceRefused("changed_during_read", f"{relative} changed while being read")
    return raw


def walk_regular_files(root, *, max_files: int = MAX_MEMBERS, max_depth: int = MAX_WALK_DEPTH):
    """Return ``(files, refused)`` for the tree beneath ``root`` without following any link.

    ``files`` are sorted relative POSIX paths of regular files. ``refused`` lists
    ``(relative_path, kind, detail)`` for symbolic links (a linked directory is reported once and
    not entered) and for special files. More than ``max_files`` entries, or a tree deeper than
    ``max_depth``, is a ``CollectionError``: a run folder is not a place to enumerate without bound.
    """
    root = Path(root)
    files: list[str] = []
    refused: list[tuple[str, str, str]] = []
    seen = 0

    def visit(directory: Path, prefix: tuple[str, ...], depth: int) -> None:
        nonlocal seen
        if depth > max_depth:
            raise CollectionError(f"directory tree is deeper than {max_depth} levels")
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            raise CollectionError(f"directory could not be listed ({type(exc).__name__})") from None
        for entry in entries:
            seen += 1
            if seen > max_files:
                raise CollectionError(f"directory tree holds more than {max_files} entries")
            relative = "/".join((*prefix, entry.name))
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError as exc:
                refused.append((relative, "unreadable", f"{relative} could not be inspected ({type(exc).__name__})"))
                continue
            if _is_link(info):
                refused.append((relative, "symlink", f"{relative} is a symbolic link"))
            elif stat.S_ISDIR(info.st_mode):
                visit(Path(entry.path), (*prefix, entry.name), depth + 1)
            elif stat.S_ISREG(info.st_mode):
                files.append(relative)
            else:
                refused.append((relative, "not_regular_file", f"{relative} is not a regular file"))

    visit(root, (), 0)
    files.sort(key=lambda value: PurePosixPath(value).parts)
    refused.sort(key=lambda item: PurePosixPath(item[0]).parts)
    return files, refused


class ArchiveCollector:
    """Apply one set of rules to every archive entry and remember what was left out."""

    def __init__(self, *, max_member_bytes: int | None = None, max_total_bytes: int | None = None,
                 max_members: int | None = None):
        # Read the module values at construction so a test (or a deployment) can adjust them.
        self.max_member_bytes = MAX_MEMBER_BYTES if max_member_bytes is None else max_member_bytes
        self.max_total_bytes = MAX_TOTAL_BYTES if max_total_bytes is None else max_total_bytes
        self.max_members = MAX_MEMBERS if max_members is None else max_members
        self.blobs: dict[str, bytes] = {}
        self.rows: list[dict] = []
        self.excluded: list[dict] = []
        self.total_bytes = 0
        self._folded: dict[str, str] = {}

    def add(self, archive_path: str, raw: bytes, *, listed: bool = True, **row) -> dict:
        """Add one entry. A rule violation refuses the whole export (``CollectionError``)."""
        problem = member_name_problem(archive_path)
        if problem:
            raise CollectionError(f"unsafe archive path ({problem}): {archive_path!r}")
        if archive_path in self.blobs:
            if self.blobs[archive_path] != raw:
                raise CollectionError(f"conflicting content for archive path {archive_path}")
            return next((item for item in self.rows if item["path"] == archive_path), {"path": archive_path})
        folded = archive_path.casefold()
        if folded in self._folded:
            raise CollectionError(
                f"archive paths {self._folded[folded]!r} and {archive_path!r} differ only by letter case")
        if len(raw) > self.max_member_bytes:
            raise CollectionError(f"{archive_path} exceeds the {self.max_member_bytes} byte per-file limit")
        if len(self.blobs) + 1 > self.max_members:
            raise CollectionError(f"the archive would hold more than {self.max_members} members")
        if self.total_bytes + len(raw) > self.max_total_bytes:
            raise CollectionError(f"the archive would exceed the {self.max_total_bytes} byte total budget")
        self.blobs[archive_path] = raw
        self._folded[folded] = archive_path
        self.total_bytes += len(raw)
        # The recorded hash is of the exact bytes that will be archived, computed here and nowhere else.
        entry = {"path": archive_path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), **row}
        if listed:
            self.rows.append(entry)
        return entry

    def exclude(self, archive_path: str, kind: str, detail: str) -> None:
        """Record a source that was left out so the archive's own inventory says so."""
        self.excluded.append({"path": archive_path, "kind": kind, "reason": detail})

    def write_zip(self, *, max_archive_bytes: int | None = None) -> bytes:
        """Write every collected entry and refuse an archive the verifier would reject for size."""
        limit = VERIFIER_TOTAL_BYTES if max_archive_bytes is None else max_archive_bytes
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, blob in self.blobs.items():
                archive.writestr(name, blob)
        data = buffer.getvalue()
        if len(data) > limit:
            raise CollectionError(
                f"the written archive is {len(data)} bytes, over the {limit} byte limit a verifier accepts")
        return data

    @property
    def complete(self) -> bool:
        return not self.excluded

    def limits(self) -> dict:
        return {"max_member_bytes": self.max_member_bytes, "max_total_bytes": self.max_total_bytes,
                "max_members": self.max_members}
