"""Include the offline clinical-summary/coverage checks in default discovery."""
import importlib.util
from pathlib import Path


def load_tests(loader, tests, pattern):
    path = (Path(__file__).resolve().parents[1] / 'studies' /
            'checklist-integration-2026-10-19' / 'genome' / 'test_genome_clinical_transfer.py')
    spec = importlib.util.spec_from_file_location('checklist_integration_genome_tests', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
