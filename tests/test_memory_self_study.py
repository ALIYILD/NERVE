import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway.self_study import (
    BASELINE_WINDOW, WINDOWS, CANDIDATES, _cases, _select, _trial, protocol_manifest, run_self_study)


class MemorySelfStudyTests(unittest.TestCase):
    def test_manifest_reproduces_and_splits_are_disjoint(self):
        first = protocol_manifest()
        self.assertEqual(first, protocol_manifest())
        groups = [set(row['payload_sha256']) for row in first['splits'].values()]
        for index, group in enumerate(groups):
            self.assertEqual(len(group), (200 if index < 2 else 500))
            for other in groups[index+1:]:
                self.assertFalse(group & other)
        self.assertTrue(first['public_synthetic_nonsealed'])
        self.assertEqual(first['baseline_window'], 3)

    def test_payload_contains_no_answer_key(self):
        for task, answer in _cases(101, 'mixed'):
            self.assertEqual(set(task), {'document'})
            self.assertIs(type(answer), bool)
        self.assertEqual(_cases(101, 'mixed'), _cases(101, 'mixed'))

    def test_closed_protocol_rejects_unknowns(self):
        for seed, scenario in [(1, 'mixed'), (True, 'mixed'), (101, 'new')]:
            with self.assertRaises(ValueError):
                _cases(seed, scenario)
        for kw in [dict(window=4), dict(window=True), dict(fixed='arbitrary'), dict(window=3, fixed='lower-only')]:
            with self.assertRaises(ValueError):
                _trial(101, 'mixed', **kw)

    def test_selection_keeps_current_default_on_tie(self):
        equal = {f'{window}:{tie}': [{'probe_hits': 5}] for window, tie in CANDIDATES}
        self.assertEqual(_select(equal)[0], (BASELINE_WINDOW, 'relevance'))
        equal['20:relevance'][0]['probe_hits'] = 6
        self.assertEqual(_select(equal)[0], (20, 'relevance'))

    def test_real_learning_has_frozen_probe_and_reproducible_outcomes(self):
        first = _trial(101, 'abrupt', window=3)
        second = _trial(101, 'abrupt', window=3)
        for field in ('feedback_outcomes', 'probe_outcomes', 'feedback_strategies', 'payload_sha256'):
            self.assertEqual(first[field], second[field])
        self.assertEqual(first['feedback_strategies'][0], 'lower-only')
        self.assertEqual(first['executions'], 25)
        self.assertEqual(first['feedback_writes'], 20)
        self.assertEqual(first['probe_feedback_writes'], 0)
        self.assertTrue(first['frozen_probe_state_unchanged'])
        self.assertGreater(first['strategy_switches'], 0)

    def test_stationary_capable_control_prevents_false_gain(self):
        adaptive = _trial(101, 'stationary', window=3)
        base = _cases(101, 'stationary')[0][1]
        fixed = _trial(101, 'stationary', fixed='trim-lower' if base else 'lower-only')
        self.assertEqual(adaptive['probe_hits'], fixed['probe_hits'])
        self.assertEqual(fixed['probe_hits'], 5)
        self.assertEqual(adaptive['executions'], fixed['executions'])
        self.assertEqual(fixed['feedback_writes'], 0)
        self.assertEqual(fixed['probe_feedback_writes'], 0)

    def test_holdout_cannot_reselect_candidate_or_authorize_promotion(self):
        calls = []
        def fake(seed, scenario, window=None, fixed=None, tie_break='relevance'):
            calls.append((seed, scenario, window, fixed, tie_break))
            # Validation prefers 10, but unseen holdout reverses the winner.
            success = window == (3 if seed >= 300 else 10)
            return {'seed': seed, 'scenario': scenario, 'probe_hits': 5*success,
                    'probe_outcomes': [success]*5}
        with patch('nerve_awim.memory_gateway.self_study._trial', side_effect=fake):
            report = run_self_study()
        self.assertEqual(report['selected_window'], 10)
        self.assertEqual(report['recommendation'], 'retain_baseline')
        self.assertFalse(report['promotion_authorized'])
        self.assertEqual(len(calls), 176)
        self.assertTrue(all(row[0] < 300 for row in calls[:96]))
        self.assertTrue(all(row[0] >= 300 for row in calls[96:]))
        self.assertEqual(report['paired']['baseline']['losses'], 100)

    def test_seeds_vary_regimes_not_only_identifiers(self):
        for scenario in ('stationary', 'abrupt', 'recurrent', 'mixed'):
            schedules = {tuple(answer for _, answer in _cases(seed, scenario))
                         for seed in (101, 102, 201, 202, 301, 302, 303, 304, 305)}
            self.assertGreater(len(schedules), 1)
        for task, _ in _cases(301, 'recurrent'):
            self.assertNotIn('recurrent', task['document'])
            self.assertNotIn('301-', task['document'])
