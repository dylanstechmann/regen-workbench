"""Include the source-summary timing and denominator checks in full discovery."""
import importlib.util
from pathlib import Path


def load_tests(loader, tests, pattern):
    path = (Path(__file__).resolve().parents[1] / 'studies' /
            'checklist-engineering-2026-10-22' / 'delivery' / 'test_delivery_summary.py')
    spec = importlib.util.spec_from_file_location('checklist_engineering_delivery_tests', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
