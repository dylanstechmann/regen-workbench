import importlib.util
import math
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / "studies/checklist-progress-2026-10-19/caffeine/compare_reversal_mechanisms.py"
spec = importlib.util.spec_from_file_location("caffeine_bookkeeping", source)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


class CaffeineMechanismBookkeepingTests(unittest.TestCase):
    def scenario(self, **changes):
        row = {"event_hours": 2., "extra_parent_clearance_per_hour": 0.,
               "extra_clearance_active_product_fraction": 0.,
               "capture_parent_fraction": 0., "capture_metabolite_fraction": 0.}
        return dict(row, **changes)

    def test_zero_time_and_half_life(self):
        self.assertEqual(model.advance(1., 0., 0., 1., 1., 1.), (1., 0., 0.))
        p, _, _ = model.advance(1., 0., 4.1, math.log(2)/4.1, .3, .1)
        self.assertAlmostEqual(p, .5)

    def test_equal_rate_analytic_limit(self):
        p, m, loss = model.advance(1., .1, 2., .5, .5, .5)
        self.assertAlmostEqual(m, 1.1 * math.exp(-1))
        self.assertAlmostEqual(p+m+loss, 1.1)

    def test_phase_splitting_preserves_solution(self):
        p, m, a = model.advance(1., .2, 2., .3, .5, .15)
        p, m, b = model.advance(p, m, 4., .3, .5, .15)
        reference = model.advance(1., .2, 6., .3, .5, .15)
        for actual, expected in zip((p,m,a+b),reference):
            self.assertAlmostEqual(actual,expected)

    def test_parent_only_capture_cannot_remove_existing_metabolite(self):
        baseline=model.state_at(2.,self.scenario(),4.1,3.1)
        captured=model.state_at(2.,self.scenario(capture_parent_fraction=.8),4.1,3.1)
        self.assertEqual(baseline["modeled_active_metabolite_fraction"],captured["modeled_active_metabolite_fraction"])
        self.assertAlmostEqual(captured["parent_fraction"],.2*baseline["parent_fraction"])
        self.assertAlmostEqual(sum(captured.values()),1.)

    def test_same_parent_clearance_different_active_product(self):
        active=model.state_at(6.,self.scenario(extra_parent_clearance_per_hour=.7,extra_clearance_active_product_fraction=1.),4.1,3.1)
        inactive=model.state_at(6.,self.scenario(extra_parent_clearance_per_hour=.7),4.1,3.1)
        self.assertEqual(active["parent_fraction"],inactive["parent_fraction"])
        self.assertGreater(active["modeled_active_metabolite_fraction"],inactive["modeled_active_metabolite_fraction"])

    def test_future_intervention_cannot_change_earlier_state(self):
        baseline=model.state_at(1.,self.scenario(),4.1,3.1)
        treatment=model.state_at(1.,self.scenario(extra_parent_clearance_per_hour=5.,capture_parent_fraction=1.),4.1,3.1)
        self.assertEqual(baseline,treatment)

    def test_molecular_balance_with_capture_and_inactivation(self):
        scenario=self.scenario(capture_parent_fraction=.8,capture_metabolite_fraction=.4,extra_parent_clearance_per_hour=.7)
        for hours in (0,1,2,3,6,24,100):
            values=model.state_at(hours,scenario,8.,3.1,.5)
            self.assertTrue(all(v>=0 for v in values.values()))
            self.assertAlmostEqual(sum(values.values()),1.)

    def test_invalid_or_nonconserving_inputs_are_rejected(self):
        for args in ((1.,0.,1.,.1,.2,.3),(1.,0.,-1.,.1,.2,.1),(1.,0.,1.,float('nan'),.2,.1)):
            with self.assertRaises(ValueError): model.advance(*args)
        with self.assertRaises(ValueError):
            model.state_at(6.,self.scenario(capture_parent_fraction=1.1),4.1,3.1)


if __name__ == "__main__": unittest.main()
