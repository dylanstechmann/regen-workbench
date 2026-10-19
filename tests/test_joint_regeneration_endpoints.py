import copy
import importlib.util
import itertools
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / "studies/checklist-progress-2026-10-19/integration/audit_joint_endpoints.py"
spec = importlib.util.spec_from_file_location("joint_endpoints", source)
joint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(joint)


class JointEndpointTests(unittest.TestCase):
    def payload(self, counts, n=100):
        population = {"population_id":"fixture", "unit":"registered_equal_volume_region",
            "timepoint":"end", "sampling_frame":"same fixed regions", "n_units":n}
        names = [f"endpoint{i}" for i in range(len(counts))]
        return {"population":population,"required_endpoints":names,
            "observations":[dict(population,endpoint=name,attaining_count=c) for name,c in zip(names,counts)]}

    def test_marginals_do_not_identify_joint_success(self):
        result=joint.audit(self.payload([80,90,75,70]))
        self.assertEqual((result['lower_bound_count'],result['upper_bound_count']),(15,70))
        self.assertAlmostEqual(result['independence_product_benchmark_fraction'],.378)
        self.assertIsNone(result['joint_attaining_count'])

    def test_bounds_agree_with_exhaustive_small_population_oracle(self):
        possibilities={}
        for masks in itertools.product(range(16),repeat=3):
            counts=tuple(mask.bit_count() for mask in masks)
            overlap=(masks[0]&masks[1]&masks[2]).bit_count()
            possibilities.setdefault(counts,set()).add(overlap)
        for counts, overlaps in possibilities.items():
            result=joint.audit(self.payload(counts,n=4))
            self.assertEqual((result['lower_bound_count'],result['upper_bound_count']),(min(overlaps),max(overlaps)))

    def test_cell_and_allele_or_timepoint_mismatch_remains_unidentified(self):
        for field,value in (("unit","allele"),("timepoint","different"),("n_units",99),("population_id","other")):
            payload=self.payload([80,70])
            payload['observations'][1][field]=value
            result=joint.audit(payload)
            self.assertIsNone(result['lower_bound_count'])
            self.assertIn('unidentified',result['status'])

    def test_missing_unmeasured_endpoint_is_not_zero_or_pass(self):
        payload=self.payload([80,None])
        self.assertIsNone(joint.audit(payload)['upper_bound_count'])
        payload['observations'].pop()
        self.assertEqual(joint.audit(payload)['problems'][0]['reason'],'missing_endpoint')

    def test_joint_observation_must_respect_bounds(self):
        payload=self.payload([80,70])
        payload['joint_attaining_count']=55
        self.assertEqual(joint.audit(payload)['status'],'joint_measured')
        payload['joint_attaining_count']=49
        with self.assertRaises(ValueError): joint.audit(payload)

    def test_duplicates_invalid_counts_and_boolean_counts_rejected(self):
        for count in (True,-1,101,.8):
            with self.assertRaises(ValueError): joint.audit(self.payload([count,70]))
        payload=self.payload([80,70])
        payload['observations'].append(copy.deepcopy(payload['observations'][0]))
        with self.assertRaises(ValueError): joint.audit(payload)
        with self.assertRaises(ValueError): joint.unique_object([('a',1),('a',2)])


if __name__ == "__main__": unittest.main()
