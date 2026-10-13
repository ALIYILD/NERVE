"""Actual prospective executions and strict evidence validation; no study tuning."""
import copy
from dataclasses import FrozenInstanceError, asdict
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import online_adaptation_study as study


class ConfigurableOnlineTrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = study.OnlinePolicy(window=5, tie_break='least_recent', discount_half_life=3)
        cls.row = study._configured_trial(6199, 'mixed', cls.config)

    def test_actual_nondefault_prospective_execution(self):
        row = study._validate_configured(self.row, 6199, 'mixed', self.config)
        self.assertEqual(row['policy_config'], asdict(self.config))
        self.assertEqual(row['feedback_writes'], 32)
        self.assertEqual(row['episode_feedback_writes'], [1] * 32)

    def test_legacy_baseline_and_candidate_execution_preserved(self):
        for arm, half in (('baseline', None), ('candidate', 1)):
            row = study._trial(6198, 'recurrent', arm)
            study._validate(row, 6198, 'recurrent', arm)
            study._validate_configured({**row, 'arm': 'configured'}, 6198,
                                      'recurrent', study.OnlinePolicy(discount_half_life=half))
            self.assertEqual(row['policy_config']['discount_half_life'], half)

    def test_actual_fixed_controls_do_not_learn(self):
        for fixed in ('lower-only', 'trim-lower'):
            row = study._configured_trial(6197, 'abrupt', self.config, fixed)
            study._validate_configured(row, 6197, 'abrupt', self.config, fixed)
            self.assertEqual(row['feedback_writes'], 0)
            self.assertEqual(row['strategies'], [fixed] * 32)

    def test_only_registered_typed_policies(self):
        for fields in ({'window': True}, {'window': 3.0}, {'window': 4},
                       {'tie_break': 'custom'}, {'tie_break': None},
                       {'discount_half_life': True}, {'discount_half_life': 1.0},
                       {'discount_half_life': float('nan')},
                       {'discount_half_life': float('inf')}, {'discount_half_life': 2}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                study.OnlinePolicy(**fields)
        with self.assertRaises(FrozenInstanceError):
            self.config.window = 10
        for config, fixed in ((asdict(self.config), None), (self.config, True),
                              (self.config, 'agent-selected')):
            with self.assertRaises(ValueError):
                study._configured_trial(6199, 'mixed', config, fixed)

    def test_evidence_mutations_rejected(self):
        changes = ({'policy_config': {}}, {'fixed': 'lower-only'},
                   {'strategies': ['agent-plan'] * 32}, {'wall_ms': True},
                   {'wall_ms': float('nan')}, {'wall_ms': -1},
                   {'payload_sha256': ['invented'] * 32}, {'executions': 33},
                   {'feedback_writes': 0}, {'arm': 'candidate'},
                   {'policy_config': {**asdict(self.config), 'discount_half_life': True}})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                study._validate_configured({**self.row, **change}, 6199, 'mixed', self.config)
        forged = copy.deepcopy(self.row)
        forged['outcomes'][0] = not forged['outcomes'][0]
        forged['hits'] = sum(forged['outcomes'])
        with self.assertRaisesRegex(ValueError, 'host truth'):
            study._validate_configured(forged, 6199, 'mixed', self.config)

    def test_truth_never_enters_agent_task(self):
        original = study.AutomaticLearningRun.execute
        observed = []
        def observe(runner, episode_id, task):
            observed.append(copy.deepcopy(task))
            self.assertEqual(set(task), {'document'})
            return original(runner, episode_id, task)
        with patch.object(study.AutomaticLearningRun, 'execute', observe):
            study._configured_trial(6196, 'stationary', study.OnlinePolicy())
        self.assertEqual(len(observed), 32)
        self.assertEqual(observed, [task for task, _ in study._cases(6196, 'stationary')])

    def test_legacy_fixture_without_configuration_remains_supported(self):
        row = {**self.row, 'arm': 'candidate'}
        del row['policy_config']
        study._validate(row, 6199, 'mixed', 'candidate')
        with self.assertRaises(ValueError):
            study._validate_configured({**row, 'arm': 'configured'}, 6199, 'mixed', self.config)


if __name__ == '__main__':
    unittest.main()
