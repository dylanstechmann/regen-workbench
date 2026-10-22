"""Meaningful balance, alias, limiting-case and discretization checks for the study."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "studies/checklist-engineering-2026-10-22/mechanics"
SPEC = importlib.util.spec_from_file_location("engineering_root_support", HERE / "analyze_root_support.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class RootSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((HERE / "model_inputs.json").read_text())
        cls.ref = cls.config["support_cases"][0]
        cls.contact = cls.config["contact_cases"][1]
        cls.results = M.analyze(cls.config)

    def assertVectorClose(self, a, b, places=11):
        self.assertEqual(len(a), len(b))
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, places=places)

    def test_uniform_matrix_matches_analytic_boundary_integrals(self):
        # Independent closed integrals over two length-1 sides and width-.3 base.
        a, kn, kt = .15, 1, .25
        expected = [[2*kn + 2*a*kt, 0, kn+2*a*kt],
                    [0, 2*kt+2*a*kn, 0],
                    [kn+2*a*kt, 0, 2*kn/3 + 2*kt*a*a + 2*a*kt + kn*2*a**3/3]]
        actual = M.assemble(self.ref, self.config)
        self.assertLess(M.max_matrix_error(actual, expected), 1e-14)

    def test_analytic_force_moment_solution_for_uniform_reference(self):
        k = M.assemble(self.ref, self.config)
        determinant = k[0][0]*k[2][2]-k[0][2]**2
        expected = [(k[2][2]+.5*k[0][2])/determinant, 0,
                    (-.5*k[0][0]-k[0][2])/determinant]
        self.assertVectorClose(M.response(self.ref, self.config, self.contact)["delta_q"], expected)

    def test_every_case_balances_both_forces_and_same_origin_moment(self):
        self.assertEqual(len(self.results["responses"]), 30)
        for r in self.results["responses"]:
            self.assertLess(max(abs(x) for x in r["force_moment_residual"]), 2e-13)
            self.assertVectorClose(M.matvec(r["matrix"], r["delta_q"]), r["generalized_load"])

    def test_independent_spring_energy_matches_half_generalized_work(self):
        for r in self.results["responses"]:
            self.assertAlmostEqual(r["foundation_energy"], r["half_load_work"], places=11)
            self.assertGreater(r["foundation_energy"], 0)
            self.assertAlmostEqual(r["contact_compliance"], 2*r["foundation_energy"], places=11)

    def test_linear_superposition_load_sign_and_scale(self):
        first = M.response(self.ref, self.config, self.contact)
        reverse = dict(self.contact, force=[-1, 0])
        reverse_result = M.response(self.ref, self.config, reverse)
        self.assertVectorClose(reverse_result["delta_q"], [-x for x in first["delta_q"]])
        scaled = dict(self.contact, force=[1e-6, 0])
        scaled_result = M.response(self.ref, self.config, scaled)
        self.assertVectorClose(scaled_result["delta_q"], [1e-6*x for x in first["delta_q"]])
        self.assertAlmostEqual(scaled_result["contact_compliance"], first["contact_compliance"])

    def test_scalar_stiffness_changes_displacement_not_reaction_pattern(self):
        ref = M.response(self.ref, self.config, self.contact)
        stiff_case = dict(self.ref, multiplier=1000)
        stiff = M.response(stiff_case, self.config, self.contact)
        self.assertVectorClose(stiff["delta_q"], [x/1000 for x in ref["delta_q"]])
        for node1, node2 in zip(M.quadrature(self.ref, self.config), M.quadrature(stiff_case, self.config)):
            d1 = M.displacement(ref["delta_q"], node1["point"])
            d2 = M.displacement(stiff["delta_q"], node2["point"])
            self.assertVectorClose([node1["kn"]*d1[0],node1["kt"]*d1[1]],
                                   [node2["kn"]*d2[0],node2["kt"]*d2[1]])

    def test_equal_loss_length_does_not_imply_equal_response(self):
        rs = [M.response(case, self.config, self.contact) for case in self.config["support_cases"][1:4]]
        self.assertTrue(all(abs(r["supported_boundary_length"]-1.7)<1e-14 for r in rs))
        self.assertEqual(len({round(r["contact_compliance"],8) for r in rs}), 3)
        self.assertGreater(rs[0]["contact_compliance"], rs[1]["contact_compliance"])
        self.assertNotAlmostEqual(rs[2]["delta_q"][1], 0)

    def test_load_contact_controls_moment_and_directional_response(self):
        rs = [M.response(self.ref,self.config,c) for c in self.config["contact_cases"]]
        self.assertLess(rs[0]["contact_compliance"], rs[1]["contact_compliance"])
        self.assertLess(rs[1]["contact_compliance"], rs[2]["contact_compliance"])
        self.assertEqual(rs[3]["generalized_load"][2], 0)
        self.assertAlmostEqual(rs[4]["generalized_load"][2], -.15)
        self.assertAlmostEqual(rs[3]["delta_q"][2], 0)
        self.assertNotAlmostEqual(rs[4]["delta_q"][2], 0)

    def test_same_incremental_mobility_does_not_identify_resting_pose(self):
        pose = self.results["resting_pose_example"]
        self.assertEqual(pose["reference"]["delta_q"],pose["wrong_resting_pose"]["delta_q"])
        self.assertEqual(pose["zero_load_pose_after_reversible_unloading"], [.02,0,.01])
        self.assertVectorClose([a-b for a,b in zip(pose["wrong_resting_pose"]["total_q"], pose["reference"]["total_q"])], [.02,0,.01])

    def test_spatial_alias_matches_entire_matrix_not_one_scalar(self):
        alias = self.results["spatial_nonidentifiability"]
        self.assertLess(alias["matrix_max_absolute_difference"], 1e-14)
        self.assertVectorClose(alias["reference_delta_q"],alias["alternative_delta_q"])
        self.assertAlmostEqual(alias["density_min"], .2)
        self.assertAlmostEqual(alias["density_max"], 1.8)
        # Manufactured high-order density is hidden to ALL three generalized probes.
        ka = M.assemble(alias["alias"],self.config)
        kr = M.assemble(self.ref,self.config)
        for rhs in ([1,0,0],[0,1,0],[0,0,1]):
            self.assertVectorClose(M.solve3(ka,rhs),M.solve3(kr,rhs))

    def test_alias_reaction_field_differs_even_with_equal_global_response(self):
        a = self.results["spatial_nonidentifiability"]
        self.assertEqual(a["local_reaction_ratio_at_right_cervical_endpoint"],1.8)
        self.assertAlmostEqual(a["local_reaction_ratio_at_right_apical_endpoint"],.2)
        self.assertNotEqual(M.p3(-1),M.p3(1))

    def test_local_reaction_profile_uses_config_geometry_and_stiffness(self):
        config=copy.deepcopy(self.config)
        config["geometry"]["root_length"]=2
        config["geometry"]["root_half_width"]=.2
        config["foundation"]["normal_density"]=1.3
        config["foundation"]["tangential_density"]=.4
        q=[.2,.3,.1]
        rows=M.local_reaction_profile(config,q,.8)
        self.assertEqual(len(rows),101)
        self.assertEqual(rows[0]["right_side_y"],-2)
        self.assertEqual(rows[-1]["right_side_y"],0)
        self.assertAlmostEqual(rows[0]["reference_reaction_x_per_length"],-.52)
        self.assertAlmostEqual(rows[0]["reference_reaction_y_per_length"],-.128)
        self.assertAlmostEqual(rows[0]["relative_density"],.2)
        self.assertAlmostEqual(rows[-1]["relative_density"],1.8)

    def test_midpoint_discretization_converges_to_exact_polynomial_integral(self):
        rows=self.results["midpoint_convergence"]
        for support in (c["id"] for c in self.config["support_cases"][:4]):
            selected=[r for r in rows if r["support_id"]==support]
            for a,b in zip(selected,selected[1:]):
                self.assertLess(b["crown_compliance_relative_error"],a["crown_compliance_relative_error"])
                self.assertAlmostEqual(a["matrix_max_absolute_error"]/b["matrix_max_absolute_error"],4,places=7)
            self.assertLess(selected[-1]["crown_compliance_relative_error"], 5e-5)

    def test_singular_missing_and_nonfinite_support_rejected(self):
        bad = dict(self.ref,multiplier=0)
        with self.assertRaises(ValueError): M.response(bad,self.config,self.contact)
        for value in (-1,float("nan"),float("inf")):
            with self.assertRaises(ValueError): M.assemble(dict(self.ref,multiplier=value),self.config)
        with self.assertRaises(ValueError): M.assemble(dict(self.ref,kind="unknown"),self.config)
        with self.assertRaises(ValueError): M.assemble(self.ref,self.config,panels=0)
        with self.assertRaises(ValueError): M.assemble(self.ref,self.config,rule="unknown")
        with self.assertRaises(ValueError): M.solve3([[1,0,0],[0,1,0],[0,0,0]],[1,0,0])

    def test_source_qualification_withholds_human_calibration(self):
        scope = json.loads((HERE/"source_scope.json").read_text())
        self.assertTrue(all(not r["used_for_numeric_calibration"] for r in scope["primary_context"]))
        self.assertIn("not fitted", self.results["status"])
        self.assertTrue(any("perfusion" in v for v in self.results["limits"]))

    def test_committed_outputs_reproduce_current_inputs(self):
        committed=json.loads((HERE/"derived/results.json").read_text())
        self.assertEqual(committed,self.results)


if __name__=="__main__":
    unittest.main()
