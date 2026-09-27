import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "studies" / "frozen_cohort" / "run_study.py"
_SPEC = importlib.util.spec_from_file_location("frozen_study", _PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
run = _MODULE.run


class FrozenStudyTests(unittest.TestCase):
    def test_preregistered_checks_pass_and_link_matches_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "cohort"
            result = run(out)
            self.assertTrue(all(result["checks"].values()), result["checks"])
            self.assertTrue((out / "expression-contrast" / "manifest.json").is_file())
            manifest = (out / "phenotype_manifest.json").read_bytes()
            self.assertEqual(result["atlas_link"]["phenotype_manifest_sha256"], hashlib.sha256(manifest).hexdigest())

    def test_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "cohort"
            run(out)
            with self.assertRaises(ValueError):
                run(out)


if __name__ == "__main__":
    unittest.main()
