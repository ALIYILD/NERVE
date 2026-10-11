import unittest
from nerve_awim.improvement_loop import run_improvement_loop
from nerve_awim.learning_study import Episode


class LoopTests(unittest.TestCase):
    def run_loop(self, **kwargs):
        train = [Episode(str(n), 'train', {'n': n}, n) for n in range(3)]
        selection = [Episode(str(n), 'evaluation', {'n': n}, n) for n in range(3, 8)]
        final = [Episode(str(n), 'evaluation', {'n': n}, n) for n in range(8, 13)]
        defaults = dict(propose=lambda request: 'lesson-' + str(request['iteration']),
                        predict=lambda task, lesson: task['n'],
                        judge=lambda task, output, expected: output == expected)
        defaults.update(kwargs)
        return run_improvement_loop(train, selection, final, **defaults)

    def test_capable_baseline_has_no_manufactured_gain(self):
        report = self.run_loop()
        self.assertEqual(report['status'], 'no_verified_improvement')
        self.assertEqual(report['proposal_calls'], 10)
        self.assertEqual(report['prediction_calls'], 100)
        self.assertIsNone(report['final'])

    def test_final_is_frozen_and_not_proposal_feedback(self):
        events = []
        def propose(request):
            events.append('proposal')
            self.assertEqual(set(request), {'iteration', 'incumbent', 'training', 'history'})
            self.assertTrue(all(e.task['n'] < 3 for e in request['training']))
            return str(request['iteration'])
        def predict(task, lesson):
            if task['n'] >= 8:
                self.assertEqual(events.count('proposal'), 10)
                events.append('final')
            return task['n'] if lesson else -1
        report = self.run_loop(propose=propose, predict=predict)
        self.assertEqual(report['status'], 'observed_final_gain')
        self.assertEqual(events.count('final'), 10)
        self.assertFalse(report['promotion_authorized'])

    def test_selection_gain_can_fail_final(self):
        report = self.run_loop(predict=lambda task, lesson: task['n'] if lesson and task['n'] < 8 else -1)
        self.assertEqual(report['status'], 'no_verified_improvement')
        self.assertIsNotNone(report['final'])

    def test_duplicate_candidates_do_not_repeat_evaluation(self):
        report = self.run_loop(propose=lambda request: 'same')
        self.assertEqual(report['prediction_calls'], 10)
        self.assertEqual(sum(h['status'] == 'duplicate_skipped' for h in report['history']), 9)

    def test_budget_and_iteration_limits_preflight(self):
        for kwargs in ({'iterations': 11}, {'max_prediction_calls': 109}, {'iterations': True}):
            with self.assertRaises(ValueError):
                self.run_loop(propose=lambda request: self.fail('must not call'), **kwargs)

    def test_judge_failure_aborts(self):
        with self.assertRaises(ValueError):
            self.run_loop(judge=lambda *args: 'yes')

    def test_cross_split_overlap_rejected(self):
        train = [Episode(str(n), 'train', {'n': n}, n) for n in range(3)]
        selection = [Episode(str(n), 'evaluation', {'n': n}, n) for n in range(3, 8)]
        final = [Episode(str(n), 'evaluation', {'n': n}, n) for n in range(8, 13)]
        final[-1] = Episode('12', 'evaluation', {'n': 3}, 3)
        with self.assertRaises(ValueError):
            run_improvement_loop(train, selection, final,
                propose=lambda request: self.fail('overlap'), predict=lambda *args: 0,
                judge=lambda *args: True)

    def test_net_gain_with_regression_is_reverted(self):
        def predict(task, lesson):
            correct = task['n'] != 3 if lesson else task['n'] == 3
            return task['n'] if correct else -1
        report = self.run_loop(predict=predict)
        self.assertIsNone(report['selected_lesson'])
        self.assertTrue(all(h['status'] == 'reverted' for h in report['history']))
