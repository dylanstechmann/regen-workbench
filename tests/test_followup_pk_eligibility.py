"""Include the study-local PK counterexamples in the repository test suite."""
import importlib.util
from pathlib import Path


def load_tests(loader, tests, pattern):
    path = Path(__file__).resolve().parents[1] / "studies/checklist-followup-2026-10-19/compounds/test_pk_intake.py"
    spec = importlib.util.spec_from_file_location("study_followup_pk_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
