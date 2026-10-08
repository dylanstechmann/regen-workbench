from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import archive_collector as ac  # noqa: E402
import regen  # noqa: E402
import regen_desk as desk  # noqa: E402
import verify_dossier  # noqa: E402


def can_symlink() -> bool:
    with tempfile.TemporaryDirectory() as temporary:
        try:
            os.symlink(Path(temporary) / "target", Path(temporary) / "link")
        except (OSError, NotImplementedError):
            return False
    return True


SYMLINKS = can_symlink()
FIFOS = hasattr(os, "mkfifo")

# Names that must be refused by the collector and by the standalone verifier alike. The verifier
# cannot import the collector (it has to stay a single file), so this corpus keeps the two rules
# from drifting apart.
BAD_NAMES = ["", "/", "a/", "/abs.json", "C:/x.json", "c:x.json", "a\\b.json", "../x.json", "a/../x.json",
             "./x.json", "a/./x.json", "a//b.json", "a/b/", " lead.json", "trail.json ", "a/ b /c.json",
             "tab\tname.json", "nul\x00.json", "new\nline.json", "del\x7f.json"]
GOOD_NAMES = ["x.json", "runs/" + "a" * 32 + "/result.json", "linked-research/experiments/e1/experiment.json",
              "a/b.c/d-e_f.txt", "unicode-µ.csv"]


class NameRuleTests(unittest.TestCase):
    def test_collector_and_verifier_refuse_the_same_names(self):
        for name in BAD_NAMES:
            with self.subTest(name=name):
                self.assertIsNotNone(ac.member_name_problem(name))
                self.assertIsNotNone(verify_dossier._unsafe_member_reason(name))

    def test_collector_and_verifier_accept_the_same_names(self):
        for name in GOOD_NAMES:
            with self.subTest(name=name):
                self.assertIsNone(ac.member_name_problem(name))
                self.assertIsNone(verify_dossier._unsafe_member_reason(name))

    def test_limits_agree_between_producer_and_consumer(self):
        self.assertEqual(ac.MAX_MEMBER_BYTES, verify_dossier.MAX_MEMBER_BYTES)
        self.assertEqual(ac.VERIFIER_TOTAL_BYTES, verify_dossier.MAX_TOTAL_BYTES)
        self.assertEqual(ac.MAX_MEMBERS, verify_dossier.MAX_MEMBERS)
        self.assertLess(ac.MAX_TOTAL_BYTES, ac.VERIFIER_TOTAL_BYTES)


class TempCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tree = self.root / "tree"
        self.tree.mkdir()

    def write(self, relative, data=b"x"):
        path = self.tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


class ReadRegularFileTests(TempCase):
    def test_returns_the_exact_bytes_including_line_endings_and_nul(self):
        payload = b"a\r\nb\x00c\x1a\xff\n"
        self.write("run/result.bin", payload)
        self.assertEqual(ac.read_regular_file(self.tree, "run/result.bin"), payload)

    def test_a_file_at_the_limit_is_read_and_one_byte_more_is_refused_unread(self):
        self.write("at.bin", b"1234")
        self.write("over.bin", b"12345")
        self.assertEqual(ac.read_regular_file(self.tree, "at.bin", limit=4), b"1234")
        with patch.object(ac.os, "read", side_effect=AssertionError("must not read an oversize file")):
            with self.assertRaises(ac.SourceRefused) as caught:
                ac.read_regular_file(self.tree, "over.bin", limit=4)
        self.assertEqual(caught.exception.kind, "too_large")

    def test_missing_files_directories_and_unsafe_names_are_refused_with_a_kind(self):
        (self.tree / "folder").mkdir()
        for relative, kind in (("missing.json", "unreadable"), ("folder", "not_regular_file"),
                               ("../outside.json", "unsafe_name"), ("a//b", "unsafe_name"), ("", "unsafe_name")):
            with self.subTest(relative=relative):
                with self.assertRaises(ac.SourceRefused) as caught:
                    ac.read_regular_file(self.tree, relative)
                self.assertEqual(caught.exception.kind, kind)

    def test_details_never_contain_an_absolute_path(self):
        with self.assertRaises(ac.SourceRefused) as caught:
            ac.read_regular_file(self.tree, "missing.json")
        self.assertNotIn(str(self.root), caught.exception.detail)

    @unittest.skipUnless(SYMLINKS, "symbolic links are not available here")
    def test_a_symlinked_file_is_refused_and_its_target_is_never_returned(self):
        secret = self.root / "outside-secret.txt"
        secret.write_bytes(b"do not archive me")
        os.symlink(secret, self.tree / "link.txt")
        with self.assertRaises(ac.SourceRefused) as caught:
            ac.read_regular_file(self.tree, "link.txt")
        self.assertEqual(caught.exception.kind, "symlink")

    @unittest.skipUnless(SYMLINKS, "symbolic links are not available here")
    def test_a_symlinked_directory_component_is_refused(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "inner.txt").write_bytes(b"outside content")
        os.symlink(outside, self.tree / "linked-dir", target_is_directory=True)
        with self.assertRaises(ac.SourceRefused) as caught:
            ac.read_regular_file(self.tree, "linked-dir/inner.txt")
        self.assertEqual(caught.exception.kind, "symlink")

    @unittest.skipUnless(FIFOS, "named pipes are not available here")
    def test_a_named_pipe_is_refused_and_does_not_block(self):
        os.mkfifo(self.tree / "pipe")
        with self.assertRaises(ac.SourceRefused) as caught:
            ac.read_regular_file(self.tree, "pipe")
        self.assertEqual(caught.exception.kind, "not_regular_file")

    def test_a_file_that_changes_while_being_read_is_refused(self):
        self.write("moving.json", b"0123456789")
        real = os.fstat
        calls = {"n": 0}

        def second_look_differs(descriptor):
            info = real(descriptor)
            calls["n"] += 1
            if calls["n"] == 2:  # the check after the read
                return SimpleNamespace(st_mode=info.st_mode, st_size=info.st_size + 1,
                                       st_mtime_ns=info.st_mtime_ns + 1, st_ino=info.st_ino, st_dev=info.st_dev)
            return info

        with patch.object(ac.os, "fstat", second_look_differs):
            with self.assertRaises(ac.SourceRefused) as caught:
                ac.read_regular_file(self.tree, "moving.json")
        self.assertEqual(caught.exception.kind, "changed_during_read")

    def test_a_file_replaced_between_inspection_and_open_is_refused(self):
        self.write("swapped.json", b"original")
        real = os.fstat

        def other_inode(descriptor):
            info = real(descriptor)
            return SimpleNamespace(st_mode=info.st_mode, st_size=info.st_size, st_mtime_ns=info.st_mtime_ns,
                                   st_ino=info.st_ino + 7, st_dev=info.st_dev)

        with patch.object(ac.os, "fstat", other_inode):
            with self.assertRaises(ac.SourceRefused) as caught:
                ac.read_regular_file(self.tree, "swapped.json")
        self.assertEqual(caught.exception.kind, "changed_during_read")

    def test_a_file_that_grows_past_the_limit_while_being_read_is_refused(self):
        self.write("growing.json", b"1234")
        real_read = os.read
        grown = {"done": False}

        def read_more_than_listed(descriptor, count):
            if not grown["done"]:
                grown["done"] = True
                return b"x" * count  # more bytes than the file had when it was inspected
            return real_read(descriptor, count)

        with patch.object(ac.os, "read", read_more_than_listed):
            with self.assertRaises(ac.SourceRefused) as caught:
                ac.read_regular_file(self.tree, "growing.json", limit=4)
        self.assertIn(caught.exception.kind, {"too_large", "changed_during_read"})


class WalkTests(TempCase):
    def test_lists_regular_files_sorted_by_path_component(self):
        for relative in ("b.json", "a/z.txt", "a.json", "a/b/c.csv", "a/a.txt"):
            self.write(relative)
        files, refused = ac.walk_regular_files(self.tree)
        self.assertEqual(files, ["a/a.txt", "a/b/c.csv", "a/z.txt", "a.json", "b.json"])
        self.assertEqual(refused, [])

    @unittest.skipUnless(SYMLINKS, "symbolic links are not available here")
    def test_symlinks_are_reported_and_linked_directories_are_not_entered(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_bytes(b"outside")
        self.write("kept.json")
        os.symlink(outside, self.tree / "linked-dir", target_is_directory=True)
        os.symlink(outside / "secret.txt", self.tree / "linked-file.txt")
        files, refused = ac.walk_regular_files(self.tree)
        self.assertEqual(files, ["kept.json"])
        self.assertEqual({(path, kind) for path, kind, _ in refused},
                         {("linked-dir", "symlink"), ("linked-file.txt", "symlink")})

    @unittest.skipUnless(FIFOS, "named pipes are not available here")
    def test_special_files_are_reported(self):
        os.mkfifo(self.tree / "pipe")
        files, refused = ac.walk_regular_files(self.tree)
        self.assertEqual((files, [(p, k) for p, k, _ in refused]), ([], [("pipe", "not_regular_file")]))

    def test_an_unbounded_tree_is_refused_not_enumerated(self):
        for index in range(6):
            self.write(f"f{index}.txt")
        with self.assertRaises(ac.CollectionError):
            ac.walk_regular_files(self.tree, max_files=5)
        deep = self.tree
        for _ in range(5):
            deep = deep / "d"
        deep.mkdir(parents=True)
        with self.assertRaises(ac.CollectionError):
            ac.walk_regular_files(self.tree, max_depth=3)


class CollectorTests(unittest.TestCase):
    def test_the_recorded_hash_is_of_the_archived_bytes(self):
        collector = ac.ArchiveCollector()
        row = collector.add("a/result.json", b'{"ok":true}', flag=True)
        self.assertEqual(row["sha256"], hashlib.sha256(b'{"ok":true}').hexdigest())
        self.assertEqual((row["bytes"], row["flag"]), (11, True))
        self.assertEqual(collector.rows, [row])

    def test_unsafe_duplicate_and_case_variant_names_refuse_the_export(self):
        collector = ac.ArchiveCollector()
        collector.add("runs/a/Result.json", b"1")
        for name, raw in (("../escape.json", b"x"), ("runs/a/Result.json", b"different"),
                          ("runs/a/result.json", b"1")):
            with self.subTest(name=name):
                with self.assertRaises(ac.CollectionError):
                    collector.add(name, raw)
        self.assertEqual(len(collector.rows), 1)

    def test_the_same_path_with_the_same_bytes_is_not_a_second_member(self):
        collector = ac.ArchiveCollector()
        collector.add("a.json", b"1")
        collector.add("a.json", b"1")
        self.assertEqual(len(collector.blobs), 1)
        self.assertEqual(len(collector.rows), 1)

    def test_member_total_and_count_limits_apply_to_every_entry(self):
        collector = ac.ArchiveCollector(max_member_bytes=4, max_total_bytes=7, max_members=3)
        collector.add("a", b"1234")
        with self.assertRaisesRegex(ac.CollectionError, "per-file"):
            collector.add("b", b"12345")
        with self.assertRaisesRegex(ac.CollectionError, "total budget"):
            collector.add("c", b"1234")
        collector.add("c", b"123")
        collector.add("d", b"")
        with self.assertRaisesRegex(ac.CollectionError, "more than 3 members"):
            collector.add("e", b"")

    def test_metadata_documents_count_against_the_same_budget(self):
        collector = ac.ArchiveCollector(max_total_bytes=10)
        collector.add("dossier.json", b"123456")
        with self.assertRaisesRegex(ac.CollectionError, "total budget"):
            collector.add("archive-index.json", b"12345", listed=False)

    def test_exclusions_make_the_collection_incomplete_and_are_listed(self):
        collector = ac.ArchiveCollector()
        self.assertTrue(collector.complete)
        collector.exclude("runs/x/link.txt", "symlink", "runs/x/link.txt is a symbolic link")
        self.assertFalse(collector.complete)
        self.assertEqual(collector.excluded[0]["kind"], "symlink")

    def test_an_archive_over_the_verifier_size_is_refused_at_write_time(self):
        collector = ac.ArchiveCollector()
        collector.add("a.bin", os.urandom(4096))
        self.assertTrue(collector.write_zip().startswith(b"PK"))
        with self.assertRaisesRegex(ac.CollectionError, "verifier accepts"):
            collector.write_zip(max_archive_bytes=100)

    def test_unlisted_entries_get_no_inventory_row(self):
        collector = ac.ArchiveCollector()
        collector.add("archive-index.json", b"{}", listed=False)
        self.assertEqual((collector.rows, list(collector.blobs)), ([], ["archive-index.json"]))


class DeskExportCase(unittest.TestCase):
    """The Desk's run-snapshot collection, end to end, through the standalone verifier."""

    RUN = "c" * 32

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, value in (("DATA", self.root / "data"), ("CACHE", self.root / "cache"),
                            ("PROV", self.root / "provenance")):
            patcher = patch.object(regen, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        (self.root / "data").mkdir()
        self.desk = desk.Desk(self.root / "desk")
        self.addCleanup(lambda: self.desk.executor.shutdown(wait=True))
        self.run_dir = self.desk.runs / self.RUN
        self.run_dir.mkdir()
        self.desk.save_run(self.run_dir, {"id": self.RUN, "kind": "search", "status": "complete",
                                          "blueprint_id": "tissues", "created_utc": "2026-10-07T00:00:00Z"})
        (self.run_dir / "result.json").write_text('{"hits": 2}', encoding="utf-8")
        output = (self.run_dir / "result.json").read_bytes()
        (self.run_dir / "manifest.json").write_text(json.dumps({"outputs": {"result.json": {
            "sha256": hashlib.sha256(output).hexdigest(), "bytes": len(output)}}}), encoding="utf-8")

    def export(self):
        blob = self.desk.export_archive("tissues")
        path = self.root / f"dossier-{len(list(self.root.glob('dossier-*.zip')))}.zip"
        path.write_bytes(blob)
        return blob, path

    def index(self, blob):
        return json.loads(zipfile.ZipFile(io.BytesIO(blob)).read("archive-index.json"))

    def test_a_clean_run_folder_is_complete_and_verifies_strictly(self):
        blob, path = self.export()
        index = self.index(blob)
        self.assertTrue(index["complete"])
        self.assertEqual(index["excluded"], [])
        self.assertEqual(index["limits"], {"max_member_bytes": ac.MAX_MEMBER_BYTES,
                                           "max_total_bytes": ac.MAX_TOTAL_BYTES, "max_members": ac.MAX_MEMBERS})
        report = verify_dossier.verify_dossier(path, strict=True)
        self.assertTrue(report["verified"], report["errors"])
        row = next(item for item in index["files"] if item["path"] == f"runs/{self.RUN}/result.json")
        self.assertTrue(row["source_matches_run_manifest"])
        self.assertTrue(row["listed_in_run_manifest"])

    def test_the_inventory_hash_is_of_the_bytes_that_were_archived(self):
        blob, _ = self.export()
        archive = zipfile.ZipFile(io.BytesIO(blob))
        for row in self.index(blob)["files"]:
            self.assertEqual(row["sha256"], hashlib.sha256(archive.read(row["path"])).hexdigest(), row["path"])
            self.assertEqual(row["bytes"], len(archive.read(row["path"])))

    @unittest.skipUnless(SYMLINKS, "symbolic links are not available here")
    def test_a_symlinked_run_file_is_excluded_and_its_target_never_enters_the_archive(self):
        secret = self.root / "outside-secret.txt"
        secret.write_text("TOP-SECRET-MARKER", encoding="utf-8")
        os.symlink(secret, self.run_dir / "linked.txt")
        blob, path = self.export()
        archive = zipfile.ZipFile(io.BytesIO(blob))
        self.assertNotIn(f"runs/{self.RUN}/linked.txt", archive.namelist())
        self.assertFalse(any(b"TOP-SECRET-MARKER" in archive.read(name) for name in archive.namelist()))
        index = self.index(blob)
        self.assertFalse(index["complete"])
        self.assertEqual([(item["path"], item["kind"]) for item in index["excluded"]],
                         [(f"runs/{self.RUN}/linked.txt", "symlink")])
        self.assertNotIn(str(self.root), json.dumps(index))
        lenient = verify_dossier.verify_dossier(path, strict=False)
        self.assertTrue(lenient["verified"], lenient["errors"])
        self.assertTrue(any("incomplete" in item for item in lenient["warnings"]))
        self.assertEqual(lenient["inventory"]["excluded_at_export"][0]["kind"], "symlink")
        strict = verify_dossier.verify_dossier(path, strict=True)
        self.assertFalse(strict["verified"])
        self.assertTrue(any("incomplete" in item for item in strict["errors"]))

    def test_an_oversize_run_file_is_excluded_not_loaded(self):
        baseline, _ = self.export()
        largest = max(info.file_size for info in zipfile.ZipFile(io.BytesIO(baseline)).infolist())
        limit = largest + 4000  # roomy for the generated documents, small for the run file below
        (self.run_dir / "huge.bin").write_bytes(b"x" * (limit + 1000))
        with patch.object(ac, "MAX_MEMBER_BYTES", limit):
            blob, path = self.export()
        self.assertNotIn(f"runs/{self.RUN}/huge.bin", zipfile.ZipFile(io.BytesIO(blob)).namelist())
        excluded = self.index(blob)["excluded"]
        self.assertEqual([(item["path"], item["kind"]) for item in excluded],
                         [(f"runs/{self.RUN}/huge.bin", "too_large")])
        self.assertFalse(verify_dossier.verify_dossier(path, strict=True)["verified"])

    def test_a_file_that_changes_during_collection_is_excluded(self):
        real = ac.read_regular_file

        def racing(root, relative, *, limit):
            if relative == "result.json":
                raise ac.SourceRefused("changed_during_read", f"{relative} changed while being read")
            return real(root, relative, limit=limit)

        with patch.object(ac, "read_regular_file", racing):
            blob, _ = self.export()
        self.assertEqual([(item["path"], item["kind"]) for item in self.index(blob)["excluded"]],
                         [(f"runs/{self.RUN}/result.json", "changed_during_read")])

    def test_an_edited_run_output_is_flagged_against_its_manifest_not_hidden(self):
        (self.run_dir / "result.json").write_text('{"hits": 3}', encoding="utf-8")
        blob, path = self.export()
        row = next(item for item in self.index(blob)["files"] if item["path"] == f"runs/{self.RUN}/result.json")
        self.assertFalse(row["source_matches_run_manifest"])
        self.assertFalse(verify_dossier.verify_dossier(path, strict=True)["verified"])
        self.assertTrue(verify_dossier.verify_dossier(path, strict=False)["verified"])

    @unittest.skipUnless(SYMLINKS, "symbolic links are not available here")
    def test_a_symlinked_run_record_is_excluded_from_the_dossier_and_named_in_the_index(self):
        other = "d" * 32
        outside = self.root / "outside-run.json"
        outside.write_text(json.dumps({"id": other, "kind": "search", "status": "complete",
                                       "blueprint_id": "tissues", "created_utc": "2026-10-07T00:00:01Z"}),
                           encoding="utf-8")
        (self.desk.runs / other).mkdir()
        os.symlink(outside, self.desk.runs / other / "run.json")
        dossier = self.desk.export("tissues")
        self.assertEqual([run["id"] for run in dossier["runs"]], [self.RUN])
        self.assertEqual([(item["run_id"], item["kind"]) for item in dossier["run_records_excluded"]],
                         [(other, "symlink")])
        blob, path = self.export()
        index = self.index(blob)
        self.assertFalse(index["complete"])
        self.assertIn(f"runs/{other}/run.json", [item["path"] for item in index["excluded"]])
        self.assertNotIn(b"outside-run", blob)
        self.assertTrue(verify_dossier.verify_dossier(path, strict=False)["verified"])
        self.assertFalse(verify_dossier.verify_dossier(path, strict=True)["verified"])

    def test_a_run_record_whose_id_does_not_match_its_folder_is_excluded(self):
        other = "e" * 32
        (self.desk.runs / other).mkdir()
        (self.desk.runs / other / "run.json").write_text(
            json.dumps({"id": self.RUN, "blueprint_id": "tissues", "created_utc": "2026-10-07T00:00:02Z"}),
            encoding="utf-8")
        dossier = self.desk.export("tissues")
        self.assertEqual([run["id"] for run in dossier["runs"]], [self.RUN])
        self.assertEqual(dossier["run_records_excluded"][0]["kind"], "id_mismatch")

    def test_an_unreadable_run_record_is_excluded_not_fatal(self):
        other = "f" * 32
        (self.desk.runs / other).mkdir()
        (self.desk.runs / other / "run.json").write_bytes(b"\xff\xfe not json")
        dossier = self.desk.export("tissues")
        self.assertEqual([run["id"] for run in dossier["runs"]], [self.RUN])
        self.assertEqual(dossier["run_records_excluded"][0]["kind"], "unreadable_json")

    def test_the_submission_snapshot_is_parsed_and_hashed_from_one_read(self):
        submission = b'{"query": "x"}'
        (self.run_dir / "submission.json").write_bytes(submission)
        run = json.loads((self.run_dir / "run.json").read_text(encoding="utf-8"))
        run["submission_sha256"] = hashlib.sha256(submission).hexdigest()
        self.desk.save_run(self.run_dir, run)
        reads = []
        original = ac.read_regular_file

        def counting(root, relative, **kwargs):
            reads.append(relative)
            return original(root, relative, **kwargs)

        with patch.object(ac, "read_regular_file", counting):
            dossier = self.desk.export("tissues")
        self.assertEqual(reads.count(f"{self.RUN}/submission.json"), 1)
        self.assertTrue(dossier["runs"][0]["submission_sha256_valid"])
        self.assertEqual(dossier["runs"][0]["submission"], {"query": "x"})

    @unittest.skipUnless(SYMLINKS, "symbolic links are not available here")
    def test_a_symlinked_submission_is_not_followed_and_is_never_marked_valid(self):
        outside = self.root / "outside-submission.json"
        outside.write_text('{"secret": "do-not-archive"}', encoding="utf-8")
        os.symlink(outside, self.run_dir / "submission.json")
        dossier = self.desk.export("tissues")
        self.assertNotIn("submission", dossier["runs"][0])
        self.assertFalse(dossier["runs"][0]["submission_sha256_valid"])
        self.assertEqual(dossier["run_records_excluded"][0]["file"], "submission.json")
        self.assertNotIn("do-not-archive", json.dumps(dossier))

    def test_temporary_files_and_non_run_folders_are_not_archived(self):
        (self.run_dir / "partial.json.tmp").write_text("in progress", encoding="utf-8")
        blob, _ = self.export()
        self.assertFalse(any(name.endswith(".tmp") for name in zipfile.ZipFile(io.BytesIO(blob)).namelist()))

    def test_a_run_with_too_many_files_refuses_the_export_clearly(self):
        for index in range(5):
            (self.run_dir / f"extra-{index}.txt").write_text("x", encoding="utf-8")
        with patch.object(ac, "MAX_MEMBERS", 4):
            with self.assertRaisesRegex(ValueError, "cannot be archived"):
                self.desk.export_archive("tissues")

    def test_the_total_byte_budget_covers_run_snapshots_and_metadata(self):
        (self.run_dir / "big.txt").write_bytes(b"y" * 3000)
        with patch.object(ac, "MAX_TOTAL_BYTES", 2500):
            with self.assertRaisesRegex(ValueError, "total budget"):
                self.desk.export_archive("tissues")

    def test_a_lying_index_is_caught_by_the_verifier(self):
        blob, _ = self.export()
        source = zipfile.ZipFile(io.BytesIO(blob))

        def forged(complete, excluded):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as out:
                for name in source.namelist():
                    data = source.read(name)
                    if name == "archive-index.json":
                        index = json.loads(data)
                        index["complete"], index["excluded"] = complete, excluded
                        data = json.dumps(index).encode()
                    out.writestr(name, data)
            path = self.root / f"forged-{complete}-{len(excluded)}.zip"
            path.write_bytes(buffer.getvalue())
            return verify_dossier.verify_dossier(path, strict=True)

        claim_complete = forged(True, [{"path": "runs/x/y", "kind": "symlink", "reason": "r"}])
        self.assertTrue(any("claims to be complete" in item for item in claim_complete["errors"]))
        claim_incomplete = forged(False, [])
        self.assertTrue(any("claims to be incomplete" in item for item in claim_incomplete["errors"]))
        malformed = forged(False, ["not an object"])
        self.assertTrue(any("excluded must be a list" in item for item in malformed["errors"]))


if __name__ == "__main__":
    unittest.main()
