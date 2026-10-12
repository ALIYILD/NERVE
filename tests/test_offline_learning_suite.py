import unittest
from scripts.offline_learning_suite import partitions, capable, run
from nerve_awim.improvement_loop import run_improvement_loop
from nerve_awim.learning_study import Episode


class OfflineSuiteTests(unittest.TestCase):
    def test_all_authored_answers_match_capable_control(self):
        for group in partitions():
            for episode in group:
                self.assertEqual(capable(episode.task), episode.expected)

    def test_no_gain_for_capable_control_and_regression_rejected(self):
        report = run()
        self.assertEqual(report['api_calls'], 0)
        self.assertEqual(report['scenarios']['capable_control']['status'], 'no_verified_improvement')
        repair = report['scenarios']['controlled_repair']
        self.assertEqual(repair['history'][0]['status'], 'reverted')
        self.assertEqual(repair['history'][0]['regression']['losses'], 1)
        self.assertEqual(repair['history'][1]['status'], 'kept')
        self.assertEqual(repair['status'], 'observed_final_gain')
        self.assertFalse(repair['promotion_authorized'])

    def test_unseen_csv_family_is_only_in_final(self):
        train, selection, regression, final = partitions()
        self.assertNotIn('csv', {e.task['family'] for e in train+selection+regression})
        self.assertIn('csv', {e.task['family'] for e in final})

    def test_regression_budget_is_reserved_before_callbacks(self):
        train, selection, regression, final = partitions()
        with self.assertRaises(ValueError):
            run_improvement_loop(train, selection, final, regression=regression,
                max_prediction_calls=200, propose=lambda _: self.fail('budget'), predict=capable,
                judge=lambda *args: True)

    def test_regression_final_overlap_rejected(self):
        train, selection, regression, final = partitions()
        regression = (Episode('duplicate-payload', 'evaluation', final[0].task, final[0].expected),)+regression[1:]
        with self.assertRaises(ValueError):
            run_improvement_loop(train, selection, final, regression=regression,
                propose=lambda _: self.fail('overlap'), predict=capable, judge=lambda *args: True)
