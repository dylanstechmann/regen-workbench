"""Include the offline MOTS-c source-specificity regression checks in discovery."""
import importlib.util
from pathlib import Path


def load_tests(loader, tests, pattern):
    path = (Path(__file__).resolve().parents[1] / 'studies' /
            'checklist-function-2026-10-19' / 'motsc' / 'test_motsc_specificity.py')
    spec = importlib.util.spec_from_file_location('checklist_function_motsc_tests', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
