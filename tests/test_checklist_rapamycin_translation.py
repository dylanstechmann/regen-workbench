"""Include study-local selectivity and reproductive-evidence checks in discovery."""
import importlib.util
from pathlib import Path

def load_tests(loader, tests, pattern):
    path = Path(__file__).resolve().parents[1] / "studies/checklist-translation-2026-10-19/rapamycin/test_rapamycin_translation.py"
    spec = importlib.util.spec_from_file_location("study_rapamycin_translation_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
