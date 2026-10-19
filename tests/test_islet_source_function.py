import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / "studies/checklist-followup-2026-10-19/organoid/analyze_islet_function.py"
spec = importlib.util.spec_from_file_location("islet_source", source)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class Cell:
    def __init__(self, value, coordinate): self.value, self.coordinate = value, coordinate


class Sheet:
    def __init__(self): self.values = {}
    def cell(self, row, column):
        coordinate = f"{chr(64+column)}{row}"
        return Cell(self.values.get(coordinate), coordinate)
    def __getitem__(self, coordinate): return Cell(self.values.get(coordinate), coordinate)


class IsletSourceTests(unittest.TestCase):
    def fixture(self):
        sheet = Sheet()
        sheet.values = {"A1":"Figure 7c", "A38":"Figure 7d", "K2":"(pg/ml)",
            "A2":"fixture", "A3":"Low Glucose", "B3":"High Glucose", "A40":"fixture",
            "A4":1., "B4":2., "A5":10., "B5":10., "A41":2., "A42":1.}
        plan={"groups":[{"low_column":1,"si_column":1,"id":"fixture","source_label":"fixture","expected_observations":2}]}
        return sheet,plan

    def test_source_ratio_reconstruction_and_cell_trace(self):
        sheet,plan=self.fixture();rows=analysis.extract_pairs(sheet,plan)
        self.assertEqual([r['stimulation_index_high_over_low'] for r in rows],[2.,1.])
        self.assertEqual(rows[0]['source_low_cell'],'Figure 7!A4')
        self.assertIsNone(rows[0]['donor_id'])

    def test_mean_individual_ratios_is_not_ratio_of_group_means(self):
        sheet,plan=self.fixture();summary=analysis.summarize(analysis.extract_pairs(sheet,plan))[0]
        self.assertEqual(summary['mean_stimulation_index'],1.5)
        self.assertAlmostEqual(summary['ratio_of_group_mean_concentrations'],12/11)
        self.assertIsNone(summary['n_independent_human_donors'])

    def test_source_si_disagreement_stops_intake(self):
        sheet,plan=self.fixture();sheet.values['A41']=3.
        with self.assertRaisesRegex(ValueError,'source SI'): analysis.extract_pairs(sheet,plan)

    def test_zero_low_or_missing_high_cannot_produce_valid_ratio(self):
        for value in (0.,-1.,None,float('nan'),True):
            sheet,plan=self.fixture();sheet.values['A4']=value
            with self.assertRaises(ValueError):analysis.extract_pairs(sheet,plan)
        sheet,plan=self.fixture();sheet.values['B4']=None
        with self.assertRaises(ValueError):analysis.extract_pairs(sheet,plan)

    def test_zero_high_is_a_measured_zero(self):
        sheet,plan=self.fixture();sheet.values['B4']=0.;sheet.values['A41']=0.
        self.assertEqual(analysis.extract_pairs(sheet,plan)[0]['stimulation_index_high_over_low'],0.)

    def test_missing_pair_with_unmatched_si_is_not_silently_dropped(self):
        sheet,plan=self.fixture();sheet.values['A4']=None;sheet.values['B4']=None
        with self.assertRaisesRegex(ValueError,'lacks'):analysis.extract_pairs(sheet,plan)

    def test_units_and_expected_count_are_checked(self):
        sheet,plan=self.fixture();sheet.values['K2']='ng/ml'
        with self.assertRaisesRegex(ValueError,'units'):analysis.extract_pairs(sheet,plan)
        sheet,plan=self.fixture();plan['groups'][0]['expected_observations']=3
        with self.assertRaisesRegex(ValueError,'size'):analysis.extract_pairs(sheet,plan)

    def test_omissions_are_assay_units_and_not_donor_resampling(self):
        groups={'in_well':[1.,1.5],'static_without_vascularization':[1.,1.],
            'static_with_vascularization':[1.,2.],'flow_without_vascularization':[1.,2.],
            'flow_with_vascularization':[3.,4.]}
        rows=[]
        for group,values in groups.items():
            for i,v in enumerate(values):
                rows.append({'group':group,'reported_point_id':f'{group}{i}',
                    'stimulation_index_high_over_low':v,'low_insulin_pg_per_ml':1.,'high_insulin_pg_per_ml':v})
        contrasts,omissions,interaction=analysis.compare(rows)
        self.assertEqual(len(contrasts),4);self.assertEqual(len(omissions),16)
        self.assertAlmostEqual(interaction,1.5)
        case=[r for r in contrasts if r['comparator']=='in_well'][0]
        self.assertAlmostEqual(case['mean_si_difference'],2.25)
        self.assertAlmostEqual(case['single_observation_omission_min_difference'],1.75)


if __name__ == '__main__': unittest.main()
