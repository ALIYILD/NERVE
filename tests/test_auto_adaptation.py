from copy import deepcopy
import tempfile
import unittest

from nerve_awim import auto_adaptation as a
from nerve_awim.auto_adaptation_goal import build, dataset, execute, fault_probe, judge, sample


class AutoAdaptationTests(unittest.TestCase):
    def state(self):
        return a.initial_state('clinical_os', ['title', 'abstract'])

    def drift(self):
        state = sample('clinical_os', self.state(), dataset('clinical_os', 0, 'baseline', 4))['state']
        return sample('clinical_os', state, dataset('clinical_os', 1, 'shift', 4))['state']

    def evaluate(self, state, **overrides):
        kwargs = dict(execute=lambda task, strategy: execute('clinical_os', task, strategy),
                      judge=lambda task, output, expected: judge('clinical_os', task, output, expected))
        kwargs.update(overrides)
        return a.evaluate(state, dataset('clinical_os', 1, 'selection', 4), dataset('clinical_os', 1, 'retained', 4), **kwargs)

    def test_stable_data_never_triggers_or_calls_evaluator(self):
        state = sample('clinical_os', self.state(), dataset('clinical_os', 0, 'stable', 16))['state']
        self.assertFalse(a.detect(state)['triggered'])
        report = self.evaluate(state, execute=lambda *args: self.fail('no drift'))
        self.assertFalse(report['eligible'])
        self.assertEqual(a.switch(state, report), state)

    def test_insufficient_or_missing_feedback_does_not_trigger(self):
        state = self.state()
        for n in range(8):
            state = a.observe(state, dict(id=str(n), observed_at=n, success=None, scope='clinical_os', strategy='title', version=0))
        self.assertFalse(a.detect(state)['triggered'])
        self.assertIsNone(state['baseline'])

    def test_drift_connects_evaluation_to_versioned_switch(self):
        state = self.drift()
        self.assertTrue(a.detect(state)['triggered'])
        report = self.evaluate(state)
        self.assertTrue(report['eligible'])
        switched = a.switch(state, report)
        self.assertEqual(switched['active'], 'abstract')
        self.assertEqual(switched['version'], 1)
        self.assertEqual(switched['canary_remaining'], 8)
        self.assertFalse(a.detect(switched)['triggered'])
        self.assertEqual(state['active'], 'title')

    def test_duplicate_feedback_is_idempotent_and_conflicts_rejected(self):
        state = self.drift()
        event = state['events'][-1]
        self.assertEqual(a.observe(state, event), state)
        with self.assertRaises(ValueError):
            a.observe(state, dict(event, success=True))

    def test_foreign_stale_and_out_of_order_feedback_rejected(self):
        state = self.drift()
        event = dict(state['events'][-1], id='new', observed_at=20)
        for change in ({'scope': 'other'}, {'version': 1}, {'strategy': 'abstract'}, {'observed_at': 0}, {'success': 'yes'}):
            with self.assertRaises(ValueError):
                a.observe(state, dict(event, **change))

    def test_evaluation_bound_to_exact_observed_state(self):
        state = self.drift()
        report = self.evaluate(state)
        updated = sample('clinical_os', state, dataset('clinical_os', 1, 'later', 1))['state']
        with self.assertRaises(ValueError):
            a.switch(updated, report)
        with self.assertRaises(ValueError):
            a.switch(state, dict(report, scope='another'))

    def test_forged_eligibility_cannot_bypass_regression_gate(self):
        state = self.drift()
        report = self.evaluate(state)
        report['scores']['abstract'][-1] = False
        with self.assertRaises(ValueError):
            a.switch(state, report)

    def test_weak_or_bad_judge_does_not_qualify(self):
        state = self.drift()
        self.assertFalse(self.evaluate(state, judge=lambda *args: False)['eligible'])
        with self.assertRaises(ValueError):
            self.evaluate(state, judge=lambda *args: 'yes')

    def test_selection_retained_overlap_rejected(self):
        tasks = dataset('clinical_os', 1, 'same', 4)
        with self.assertRaises(ValueError):
            a.evaluate(self.drift(), tasks, tasks, execute=lambda *args: None, judge=lambda *args: True)

    def test_canary_reversal_rolls_back_and_enforces_cooldown(self):
        for domain in ('clinical_os', 'perfflux'):
            result = fault_probe(domain)
            self.assertTrue(result['rollback_verified'])
            self.assertEqual(result['trial_hits'], 6)
        state = a.switch(self.drift(), self.evaluate(self.drift()))
        rolled = sample('clinical_os', state, dataset('clinical_os', 0, 'reversal', 2))['state']
        self.assertEqual(rolled['cooldown'], 8)
        self.assertFalse(a.detect(rolled)['triggered'])

    def test_stop_prevents_observation_and_switch(self):
        state = self.drift()
        report = self.evaluate(state)
        stopped = a.stop(state)
        self.assertFalse(a.detect(stopped)['triggered'])
        with self.assertRaises(ValueError):
            a.switch(stopped, report)
        with self.assertRaises(PermissionError):
            a.observe(stopped, state['events'][-1])

    def test_restart_in_middle_of_canary_and_goal_completion(self):
        with tempfile.TemporaryDirectory() as root:
            # First phase takes five leaves; second phase's switch is leaf nine.
            partial = build(root).run(max_ticks=9)
            self.assertEqual(partial['status'], 'active')
            state = build(root).run()
            self.assertEqual(state['status'], 'complete')
            for result in state['tasks'][-1]['receipt']['domains'].values():
                self.assertEqual(result['adaptive_hits'], 28)
                self.assertEqual(result['tasks'], 36)
                self.assertEqual(result['switches'], 2)
                self.assertEqual(result['additional_evaluation_calls'], 32)
                self.assertTrue(result['beats_all_fixed_controls'])
            self.assertEqual(build(root).run(), state)
            with self.assertRaises(ValueError):
                build(root, ('perfflux',))

    def test_future_outcomes_do_not_affect_prefix_decisions(self):
        state = self.drift()
        snapshot = deepcopy(state)
        report = self.evaluate(state)
        self.assertEqual(state, snapshot)
        self.assertNotIn('monitor', str(report))
