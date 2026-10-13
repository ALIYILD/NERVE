import unittest
from nerve_awim.memory_gateway import online_forecast_demo as demo


class OnlineForecastDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = demo.run_demo()

    def test_four_real_online_development_cases_match_original_control(self):
        self.assertEqual(self.report['status'],'complete')
        self.assertEqual(self.report['online_episodes'],4)
        self.assertEqual(self.report['comparison_episodes'],8)
        self.assertEqual(self.report['plant_steps'],960)
        self.assertEqual({(r['seed'],r['scenario'],r['adaptive']) for r in self.report['rows']},
                         {(9,s,a) for s in ('stationary','drift') for a in (False,True)})
        for row in self.report['rows']:
            self.assertTrue(row['trajectory_unchanged'])
            self.assertTrue(row['controller_states_unchanged'])
            online = row['online']
            demo.validate(online['episode'],9,row['scenario'],row['adaptive'])
            self.assertEqual(len(online['controller_states']),80)
            self.assertEqual(len(online['forecasts']),80)
            self.assertTrue(online['enabled'])

    def test_online_reports_match_replay_and_preserve_controller_predictions(self):
        for row in self.report['rows']:
            self.assertTrue(row['online_matches_replay'])
            self.assertTrue(row['metrics']['controller_predictions_preserved'])
            self.assertFalse(row['metrics']['actions_changed'])
            self.assertEqual(row['metrics']['missing_forecasts'],0)
            online = row['online']
            for step,forecast in zip(online['episode']['trace'],online['forecasts']):
                self.assertEqual(forecast['step'],step['step'])
                self.assertEqual(forecast['source'],step['action_source'])
                if step['action_source'] == 'controller':
                    self.assertEqual(forecast['velocity'],step['predicted_velocity'])

    def test_actual_supervision_and_authorized_recovery_are_exercised(self):
        for row in self.report['rows']:
            episode = row['online']['episode']
            self.assertGreater(episode['metrics']['supervisor_steps'],0)
            self.assertGreater(episode['metrics']['active_steps'],0)
            self.assertGreater(episode['metrics']['successful_recoveries'],0)
            self.assertTrue(any(s['sensor'] and s['sensor']['accepted'] and
                                s['sensor']['route'] == 'recovery' for s in episode['trace']))

    def test_demo_makes_no_performance_promotion_or_deployment_claim(self):
        for key in ('performance_improvement_claimed','candidate_promoted','model_weights_trained','deployed'):
            self.assertIs(self.report[key],False)
        with self.assertRaises(ValueError): demo.online_episode(9,'drift',True,enabled='yes')
