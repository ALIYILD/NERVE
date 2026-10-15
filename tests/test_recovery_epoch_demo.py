import unittest
from nerve_awim.memory_gateway import recovery_epoch_demo as demo
from nerve_awim.memory_gateway import evidence_gated_episode as original


class RecoveryEpochDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = demo.run()

    def test_complete_matched_roster_and_wrong_prior_conditions(self):
        self.assertEqual(self.report['episodes'],12)
        self.assertEqual(self.report['plant_steps'],960)
        self.assertEqual({(r['arm'],r['plant']) for r in self.report['rows']},
                         {(a,p) for a in demo.ARMS for p in demo.PLANTS})
        for row in self.report['rows']:
            self.assertEqual(row['nominal_gain'],.27)
            self.assertEqual(row['trace'][0]['model_gain'],.27)
            self.assertEqual(len(row['trace']),80)
            self.assertTrue(any(x['authorised'] for x in row['recoveries']))
            if row['arm'] == 'epoch':
                self.assertTrue(all(x['gain_after']==.27 for x in row['recoveries'] if x['authorised']))

    def test_plant_arithmetic_and_scores_reconcile(self):
        for row in self.report['rows']:
            p=v=0.
            for step in row['trace']:
                v=.82*v+demo.PLANTS[row['plant']][step['step']//20]*step['action']; p+=v
                self.assertEqual(step['true_velocity'],v)
                self.assertEqual(step['true_position'],p)
                self.assertEqual(step['goal_error'],abs(p-1.2))
                self.assertEqual(step['prediction_error'],abs(step['predicted_velocity']-v))
            self.assertEqual(row['mean_goal_error'],sum(s['goal_error'] for s in row['trace'])/80)

    def test_existing_control_trajectories_match_original_fixture(self):
        for plant in ('nominal','drift'):
            for arm,source in (('frozen','frozen_h1'),('gated','gated_forget_h1')):
                expected=original.execute(9,'stationary' if plant=='nominal' else 'drift',source)['episode']
                actual=next(r for r in self.report['rows'] if r['plant']==plant and r['arm']==arm)
                self.assertEqual([s['action'] for s in actual['trace']],[s['action'] for s in expected['trace']])
                self.assertEqual([s['model_gain'] for s in actual['trace']],[s['estimated_gain'] for s in expected['trace']])
                self.assertEqual(actual['mean_goal_error'],expected['metrics']['mean_goal_error'])

    def test_development_does_not_establish_improvement(self):
        for key in ('performance_improvement_established','candidate_promoted','model_weights_trained','deployed'):
            self.assertIs(self.report[key],False)
        with self.assertRaises(ValueError): demo.execute('best','nominal')

    def test_mismatched_prior_regressions_block_automatic_progression(self):
        self.assertFalse(self.report['eligible_for_registered_study'])
        self.assertEqual(self.report['next_action'],'retain_baselines_and_revise_hypothesis')
        comparisons=self.report['comparisons']
        self.assertEqual(len(comparisons),8)
        for plant in ('lower','higher'):
            result=next(r for r in comparisons if r['plant']==plant and r['baseline']=='gated')
            self.assertFalse(result['nonregression'])
            self.assertGreater(result['deltas']['mean_goal_error'],0)
            self.assertGreater(result['deltas']['mean_prediction_error'],0)
