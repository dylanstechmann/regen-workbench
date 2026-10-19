"""Mass balance, capacity and selectivity checks for the exploratory buffer model."""
import importlib.util
import hashlib
import json
import math
from pathlib import Path
import unittest

STUDY = Path(__file__).resolve().parents[1] / "studies/checklist-mechanisms-2026-10-19/caffeine"
spec = importlib.util.spec_from_file_location("competitive_capture", STUDY / "competitive_capture.py")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)

class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.guests = [{"name": "caffeine", "total": 10e-6, "ka": 25100.0}]

    def test_zero_host_and_nonbinding_guest(self):
        state = model.equilibrium(0, self.guests)
        self.assertEqual(state["guests"][0]["free"], 10e-6)
        nonbinder = [{"name": "x", "total": 5e-6, "ka": 0}]
        state = model.equilibrium(3e-6, nonbinder)
        self.assertAlmostEqual(state["host_free"], 3e-6, places=16)
        self.assertEqual(state["guests"][0]["bound"], 0)

    def test_single_ligand_against_quadratic_solution(self):
        # Independently solve x^2-(H+L+Kd)x+HL=0 for bound complex x.
        h, l, k = 8e-6, 10e-6, 1/25100
        a = h+l+k
        bound = 2*h*l/(a+math.sqrt(a*a-4*h*l))
        state = model.equilibrium(h, self.guests)
        self.assertAlmostEqual(state["guests"][0]["bound"], bound, places=17)

    def test_guest_and_host_conservation_with_competitors(self):
        guests = self.guests + [{"name": "competitor", "total": 1e-3, "ka": 10000}]
        state = model.equilibrium(5e-5, guests)
        self.assertLess(abs(state["host_balance_error"]), 1e-17)
        for guest in state["guests"]:
            self.assertAlmostEqual(guest["free"]+guest["bound"], guest["total"], places=17)
        self.assertLessEqual(sum(g["bound"] for g in state["guests"]), state["host_total"])

    def test_capacity_and_adverse_competition(self):
        control = model.equilibrium(5e-6, self.guests)
        challenged = model.equilibrium(5e-6, self.guests + [{"name": "background", "total": 1e-3, "ka": 10000}])
        self.assertLessEqual(control["guests"][0]["bound"], 5e-6)
        self.assertLess(challenged["guests"][0]["bound"], control["guests"][0]["bound"])

    def test_required_capture_reconstructs_and_includes_occupied_host(self):
        req = model.required_host("caffeine", 0.9, self.guests)
        self.assertAlmostEqual(req["host_free"], 9/25100, places=16)
        self.assertAlmostEqual(req["host_total"], 9/25100+9e-6, places=16)
        state = model.equilibrium(req["host_total"], self.guests)
        self.assertAlmostEqual(state["guests"][0]["bound"]/10e-6, 0.9, places=12)

    def test_equal_affinities_produce_equal_free_fractions(self):
        state = model.equilibrium(1e-4, self.guests + [{"name": "y", "total": 40e-6, "ka": 25100}])
        fractions = [g["free"]/g["total"] for g in state["guests"]]
        self.assertAlmostEqual(*fractions, places=14)

    def test_invalid_inputs_and_complete_capture_rejected(self):
        for value in [-1, float("nan"), float("inf"), True]:
            with self.assertRaises(ValueError):
                model.equilibrium(value, self.guests)
        for fraction in [0, 1, 1.1]:
            with self.assertRaises(ValueError):
                model.required_host("caffeine", fraction, self.guests)
        with self.assertRaises(ValueError):
            model.equilibrium(1e-4, self.guests*2)

    def test_missing_paraxanthine_and_human_outcomes_remain_unknown(self):
        plan = json.loads((STUDY / "binding_plan.json").read_text())
        self.assertIsNone(plan["source"]["paraxanthine_ka_per_molar"])
        receipt = json.loads((STUDY / "derived/analysis_receipt.json").read_text())
        self.assertEqual(receipt["equilibrium_rows"], 180)
        self.assertEqual(receipt["requirement_rows"], 108)
        self.assertEqual(receipt["human_oral_sleep_result"], "not_identifiable_not_modelled")
        self.assertEqual(receipt["plan_sha256_lf_text"], hashlib.sha256((STUDY / "binding_plan.json").read_text(encoding="utf-8").encode("utf-8")).hexdigest())
        for name, expected in receipt["output_sha256_lf_text"].items():
            self.assertEqual(hashlib.sha256((STUDY/"derived"/name).read_text(encoding="utf-8").encode("utf-8")).hexdigest(), expected)

if __name__ == "__main__":
    unittest.main()
