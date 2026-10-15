import copy
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import standard_learning_demo as demo


def fixture(arm,scenario,timeout=30):
    return {'arm':arm,'episode':{'seed':9,'scenario':scenario,'metrics':{
        'mean_goal_error':.9 if arm=='single_use' else 1.,'mean_prediction_error':.1,
        'violations':0,'supervisor_steps':10}},'audit':{'accepted':1},
        'elapsed_seconds':.1,'source_sha256':{'fixture':'pin'}}


class StandardLearningDemoTests(unittest.TestCase):
    def rows(self): return [fixture(a,s) for s in demo.SCENARIOS for a in demo.ARMS]

    def test_each_baseline_and_regime_must_pass_with_strict_gain(self):
        self.assertTrue(demo.compare(self.rows())['passed'])
        for metric in ('mean_goal_error','mean_prediction_error','violations','supervisor_steps'):
            rows = self.rows(); rows[2]['episode']['metrics'][metric] = 11
            self.assertFalse(demo.compare(rows)['passed'])
        rows = self.rows()
        for row in rows: row['episode']['metrics']['mean_goal_error'] = 1.
        self.assertFalse(demo.compare(rows)['passed'])
        rows = self.rows(); rows[1]['episode']['metrics']['mean_goal_error'] = .5
        result = demo.compare(rows)
        self.assertTrue(result['comparisons'][0]['passed'])
        self.assertFalse(result['comparisons'][1]['passed'])
        self.assertFalse(result['passed'])

    def test_roster_seed_and_metrics_strict(self):
        for mutation in ('missing','duplicate','seed','nan','bool'):
            rows = self.rows()
            if mutation=='missing': rows.pop()
            elif mutation=='duplicate': rows[-1]=copy.deepcopy(rows[0])
            elif mutation=='seed': rows[0]['episode']['seed']=44001
            elif mutation=='nan': rows[0]['episode']['metrics']['mean_goal_error']=float('nan')
            else: rows[0]['episode']['metrics']['violations']=False
            with self.assertRaises(ValueError): demo.compare(rows)

    def test_host_reaudits_fixed_roster_and_keeps_claim_narrow(self):
        with patch.object(demo,'sources',return_value={'fixture':'pin'}), \
             patch.object(demo,'_execute',side_effect=fixture) as execute, \
             patch.object(demo.episode,'validate') as validate, \
             patch.object(demo.auditor,'audit',return_value={'accepted':1}) as audit:
            report = demo.run_demo()
            self.assertEqual(execute.call_count,6); self.assertEqual(validate.call_count,6)
            self.assertEqual(audit.call_count,6); self.assertEqual(report['plant_steps'],480)
            self.assertTrue(report['development_screen_passed'])
            for key in ('registered_streams_used','heldout_outcomes_analyzed','performance_improvement_claimed','candidate_promoted','model_weights_trained'):
                self.assertIs(report[key],False)
            self.assertEqual([(call.args[0],call.args[1]) for call in execute.call_args_list],
                             [(a,s) for s in demo.SCENARIOS for a in demo.ARMS])

    def test_worker_pin_and_audit_mismatch_rejected(self):
        for bad in ('source','audit'):
            def altered(*args):
                row = fixture(*args)
                if bad=='source': row['source_sha256']={'altered':'pin'}
                else: row['audit']={'accepted':True}
                return row
            with patch.object(demo,'sources',return_value={'fixture':'pin'}), \
                 patch.object(demo,'_execute',side_effect=altered), \
                 patch.object(demo.episode,'validate'), \
                 patch.object(demo.auditor,'audit',return_value={'accepted':1}):
                with self.assertRaises(ValueError): demo.run_demo()

    def test_source_change_or_budget_stops_before_dispatch(self):
        with patch.object(demo,'sources',side_effect=[{'a':1},{'a':2}]), patch.object(demo,'_execute') as execute:
            with self.assertRaisesRegex(ValueError,'source_drift'): demo.run_demo()
            execute.assert_not_called()
        with patch.object(demo,'sources',return_value={}), patch.object(demo.time,'monotonic',side_effect=[0,181]), patch.object(demo,'_execute') as execute:
            with self.assertRaises(TimeoutError): demo.run_demo()
            execute.assert_not_called()

    def test_real_isolated_child_matches_host_sources_and_audit(self):
        original = demo.episode.NerveResearchRuntime
        row = demo._execute('single_use','drift')
        self.assertIs(demo.episode.NerveResearchRuntime,original)
        self.assertEqual(row['source_sha256'],demo.sources())
        demo.episode.validate(row['episode'],9,'drift',True)
        self.assertEqual(row['audit'],demo.auditor.audit(row['episode'],'single_use'))
        self.assertEqual(row['audit']['repeated_applications'],0)
        self.assertGreater(row['audit']['ema_applications'],0)
        for arm,scenario in (('unknown','drift'),('single_use','other')):
            with self.assertRaises(ValueError): demo._execute(arm,scenario)
