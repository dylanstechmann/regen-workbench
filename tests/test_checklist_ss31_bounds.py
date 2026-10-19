"""Include study-local SS-31 accounting checks in the repository suite."""
import importlib.util
from pathlib import Path


def load_tests(loader, tests, pattern):
    path = Path(__file__).resolve().parents[1] / "studies/checklist-mechanisms-2026-10-19/ss31/test_ss31_bounds.py"
    spec = importlib.util.spec_from_file_location("study_ss31_bounds_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
