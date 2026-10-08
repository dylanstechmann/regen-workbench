from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import rerun_check as rc  # noqa: E402

KIT = ROOT.parent / "regen-benchmark-kit"
KIT_COMMIT = "b0087c78ac3474aecdb6e5cc276d6ba79921df5d"
EXAMPLE = ROOT / "studies" / "frozen-evaluation-example"

# A stand-in producer: same command shape as regenbench, deterministic output, one float that a
# changed build could nudge. It lets the harness be tested without the real kit or a heavy stack.
FAKE_CLI = '''
import json, sys
from pathlib import Path
def main(argv):
    assert argv[0] == "regress"
    opts = dict(zip(argv[2::2], argv[3::2]))
    out = Path(opts["--out"]); out.mkdir(parents=True)
    rows = Path(argv[1]).read_text().strip().splitlines()
    value = 0.1 + 0.2 + int(opts["--seed"])
    (out / "metrics.json").write_text(json.dumps({
        "dataset_sha256": __import__("hashlib").sha256(Path(argv[1]).read_bytes()).hexdigest(),
        "n_rows": len(rows) - 1, "score": value, "group": opts["--group-by"],
        "environment": {"python": sys.version.split()[0]}}))
'''


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-C", str(repo), *args],
                          check=True, capture_output=True, text=True).stdout.strip()


class Fixture:
    def __init__(self, test: unittest.TestCase):
        self.tmp = tempfile.TemporaryDirectory()
        test.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "producer"
        (self.repo / "src" / "regenbench").mkdir(parents=True)
        (self.repo / "src" / "regenbench" / "__init__.py").write_text("")
        (self.repo / "src" / "regenbench" / "cli.py").write_text(FAKE_CLI)
        git(self.repo.parent, "init", "-q", str(self.repo))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "producer")
        self.commit = git(self.repo, "rev-parse", "HEAD")
        self.work = self.root / "spec"
        self.work.mkdir()
        self.table = b"a,b,t\n1,2,3\n4,5,6\n"
        (self.work / "table.csv").write_bytes(self.table)
        self.receipt = {"dataset_sha256": sha(self.table), "n_rows": 2, "score": 0.1 + 0.2,
                        "group": "a", "environment": {"python": "other"}}

    def write(self, receipt=None, **overrides) -> Path:
        receipt = self.receipt if receipt is None else receipt
        raw = json.dumps(receipt).encode()
        (self.work / "receipt.json").write_bytes(raw)
        spec = {"schema_version": 1, "entry_point": rc.ENTRY_POINT,
                "producer": {"repository": str(self.repo), "commit": self.commit},
                "input": {"path": "table.csv", "sha256": sha(self.table)},
                "receipt": {"path": "receipt.json", "sha256": sha(raw)},
                "arguments": {"group_by": "a", "target": "t", "seed": 0}}
        spec.update(overrides)
        path = self.work / "spec.json"
        path.write_text(json.dumps(spec))
        return path


class RerunTests(unittest.TestCase):
    def test_identical_output_is_exact_and_environment_is_recorded_not_compared(self):
        fixture = Fixture(self)
        report = rc.run_spec(fixture.write())
        self.assertEqual(report["rerun"]["status"], "reproduced_exact", report["rerun"])
        self.assertEqual(report["environments"]["stored"], {"python": "other"})
        self.assertEqual(report["environments"]["rerun"], {"python": sys.version.split()[0]})
        self.assertEqual(report["rerun"]["stored_metrics_sha256_without_environment"],
                         report["rerun"]["rerun_metrics_sha256_without_environment"])
        self.assertTrue(any("not scientific review" in item for item in report["limits"]))

    def test_last_digit_differences_are_within_tolerance_and_larger_ones_are_not(self):
        fixture = Fixture(self)
        nudged = dict(fixture.receipt, score=fixture.receipt["score"] * (1 + 1e-13))
        report = rc.run_spec(fixture.write(nudged))
        self.assertEqual(report["rerun"]["status"], "reproduced_within_tolerance")
        self.assertGreater(report["rerun"]["max_rel_deviation"], 0)
        off = dict(fixture.receipt, score=fixture.receipt["score"] * 1.001)
        report = rc.run_spec(fixture.write(off))
        self.assertEqual(report["rerun"]["status"], "not_reproduced")
        self.assertEqual(report["rerun"]["beyond_tolerance"], ["score"])

    def test_a_structural_difference_is_not_reproduced(self):
        fixture = Fixture(self)
        report = rc.run_spec(fixture.write(dict(fixture.receipt, extra_field=1)))
        self.assertEqual(report["rerun"]["status"], "not_reproduced")
        self.assertTrue(report["rerun"]["structural_differences"])

    def test_unknown_entry_point_and_hostile_arguments_are_refused_before_anything_runs(self):
        fixture = Fixture(self)
        for overrides, text in [
            ({"entry_point": "shell/1"}, "allowlist"),
            ({"arguments": {"group_by": "a; touch /tmp/x", "target": "t", "seed": 0}}, "group_by"),
            ({"arguments": {"group_by": "a", "target": "../t", "seed": 0}}, "target"),
            ({"arguments": {"group_by": "a", "target": "t", "seed": True}}, "seed"),
            ({"arguments": {"group_by": "a", "target": "t", "seed": 0, "command": "x"}}, "exactly"),
            ({"producer": {"repository": str(fixture.repo), "commit": "HEAD"}}, "40-character"),
        ]:
            report = rc.run_spec(fixture.write(**overrides))
            self.assertEqual(report["rerun"]["status"], "could_not_run", overrides)
            self.assertIn(text, report["rerun"]["reason"])

    def test_a_changed_input_or_receipt_is_could_not_run_not_not_reproduced(self):
        fixture = Fixture(self)
        spec = fixture.write()
        (fixture.work / "table.csv").write_bytes(fixture.table + b"7,8,9\n")
        report = rc.run_spec(spec)
        self.assertEqual(report["rerun"]["status"], "could_not_run")
        self.assertIn("SHA-256", report["rerun"]["reason"])

    def test_receipt_must_name_the_declared_table(self):
        fixture = Fixture(self)
        report = rc.run_spec(fixture.write(dict(fixture.receipt, dataset_sha256="0" * 64)))
        self.assertEqual(report["rerun"]["status"], "could_not_run")
        self.assertIn("dataset", report["rerun"]["reason"])

    def test_an_unknown_commit_is_refused(self):
        fixture = Fixture(self)
        spec = fixture.write(producer={"repository": str(fixture.repo), "commit": "1" * 40})
        report = rc.run_spec(spec)
        self.assertEqual(report["rerun"]["status"], "could_not_run")

    def test_uncommitted_changes_in_the_producer_do_not_reach_the_rerun(self):
        fixture = Fixture(self)
        (fixture.repo / "src" / "regenbench" / "cli.py").write_text("raise SystemExit('tampered')\n")
        self.assertEqual(rc.run_spec(fixture.write())["rerun"]["status"], "reproduced_exact")

    def test_a_failing_producer_is_could_not_run(self):
        fixture = Fixture(self)
        (fixture.repo / "src" / "regenbench" / "cli.py").write_text("def main(argv):\n    raise SystemExit('boom')\n")
        git(fixture.repo, "commit", "-qam", "break")
        spec = fixture.write(producer={"repository": str(fixture.repo), "commit": git(fixture.repo, "rev-parse", "HEAD")})
        report = rc.run_spec(spec)
        self.assertEqual(report["rerun"]["status"], "could_not_run")
        self.assertIn("boom", report["rerun"]["reason"])

    def test_duplicate_keys_and_nan_are_rejected_in_json(self):
        with self.assertRaises(rc.RerunError):
            rc._strict_json(b'{"a": 1, "a": 2}', "x")
        with self.assertRaises(rc.RerunError):
            rc._strict_json(b'{"a": NaN}', "x")

    def test_cli_never_overwrites_a_report(self):
        fixture = Fixture(self)
        out = fixture.root / "report.json"
        self.assertEqual(rc.main([str(fixture.write()), "--out", str(out)]), 0)
        before = out.read_bytes()
        self.assertEqual(rc.main([str(fixture.write()), "--out", str(out)]), 2)
        self.assertEqual(out.read_bytes(), before)


@unittest.skipUnless((KIT / ".git").exists() and (KIT / "examples/nist_ipsc/data/features.csv").exists(),
                     "sibling regen-benchmark-kit checkout not present")
class NistReceiptTests(unittest.TestCase):
    def test_the_vendored_nist_receipt_reruns_from_its_pinned_commit(self):
        try:
            import numpy, sklearn  # noqa: F401, E401
        except ImportError:
            self.skipTest("numpy and scikit-learn are needed to rerun regenbench")
        provenance = json.loads((EXAMPLE / "inputs" / "PROVENANCE.json").read_text(encoding="utf-8"))
        receipt = EXAMPLE / "inputs" / "nist_ipsc_regression_metrics.json"
        with tempfile.TemporaryDirectory() as temporary:
            spec = Path(temporary) / "spec.json"
            spec.write_text(json.dumps({
                "schema_version": 1, "entry_point": rc.ENTRY_POINT,
                "producer": {"repository": str(KIT), "commit": provenance["source_commit_that_added_the_receipt"]},
                "input": {"path": str(KIT / "examples/nist_ipsc/data/features.csv"),
                          "sha256": provenance["feature_table_sha256"]},
                "receipt": {"path": str(receipt), "sha256": provenance["receipt_sha256"]},
                "arguments": {"group_by": "source_well", "target": "reference_nuclear_fraction", "seed": 0}}))
            report = rc.run_spec(spec)
        self.assertIn(report["rerun"]["status"], {"reproduced_exact", "reproduced_within_tolerance"}, report["rerun"])
        self.assertLess(report["rerun"]["max_rel_deviation"], 1e-9)


if __name__ == "__main__":
    unittest.main()
