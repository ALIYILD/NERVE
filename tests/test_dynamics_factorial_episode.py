import copy
from functools import partial
import unittest
from unittest.mock import patch

from nerve_awim import consistent_dynamics
from nerve_awim.memory_gateway import dynamics_factorial_episode as factorial
from nerve_awim.memory_gateway import recovery_adaptation


class DynamicsFactorialEpisodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Smoke data only; no registered validation or holdout seeds.
        cls.rows = {arm: factorial.execute(4, 'drift', arm) for arm in factorial.ARMS}

    def test_all_arms_have_matched_exogenous_data_and_actual_planning_counts(self):
        runtime = recovery_adaptation.NerveResearchRuntime
        product = consistent_dynamics.product
        schedules = set()
        for arm, row in self.rows.items():
            with self.subTest(arm=arm):
                factorial.validate(row, 4, 'drift', arm)
                episode = row['episode']
                schedules.add(episode['schedule_sha256'])
                self.assertGreater(row['elapsed_seconds'], 0)
                self.assertEqual(episode['metrics']['violations'], 0)
                self.assertEqual(episode['metrics']['successful_recoveries'], 1)
                expected = 27 * episode['metrics']['active_steps'] if arm.endswith('h3') else 0
                self.assertEqual(row['planning_sequences'], expected)
                if arm.startswith('frozen'):
                    self.assertEqual(episode['learning_updates'], 0)
                    self.assertEqual(episode['final_gain'], episode['initial_gain'])
        self.assertEqual(len(schedules), 1)
        self.assertIs(recovery_adaptation.NerveResearchRuntime, runtime)
        self.assertIs(consistent_dynamics.product, product)

    def test_h1_legacy_and_frozen_match_unmodified_episodes(self):
        for arm, adaptive in [('frozen_h1', False), ('adaptive_legacy_h1', True)]:
            self.assertEqual(self.rows[arm]['episode'], recovery_adaptation.episode(4, 'drift', adaptive))

    def test_frozen_consistent_filter_matches_legacy_at_both_planning_depths(self):
        # Without gain updates the filters are equivalent, including recovery
        # reseeding. This smoke check supports omitting redundant frozen arms.
        for horizon in (1, 3):
            with self.subTest(horizon=horizon), patch.object(
                    recovery_adaptation, 'NerveResearchRuntime', partial(
                        consistent_dynamics.ConsistentDynamicsRuntime,
                        consistent_filter=True, planning_horizon=horizon)):
                consistent = recovery_adaptation.episode(4, 'drift', False)
            self.assertEqual(self.rows[f'frozen_h{horizon}']['episode'], consistent)

    def test_stationary_smoke(self):
        row = factorial.execute(4, 'stationary', 'adaptive_consistent_h3')
        factorial.validate(row, 4, 'stationary', 'adaptive_consistent_h3')

    def test_invalid_inputs_never_replace_globals(self):
        runtime, product = recovery_adaptation.NerveResearchRuntime, consistent_dynamics.product
        for args in [(True, 'drift', 'frozen_h1'), (-1, 'drift', 'frozen_h1'),
                     (4, 'unknown', 'frozen_h1'), (4, 'drift', True),
                     (4, 'drift', 'frozen_h2'), (4, 'drift', ['frozen_h1'])]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                factorial.execute(*args)
        self.assertIs(recovery_adaptation.NerveResearchRuntime, runtime)
        self.assertIs(consistent_dynamics.product, product)

    def test_failure_restores_both_globals_and_propagates(self):
        runtime, product = recovery_adaptation.NerveResearchRuntime, consistent_dynamics.product
        with patch.object(recovery_adaptation, 'episode', side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                factorial.execute(4, 'drift', 'adaptive_consistent_h3')
        self.assertIs(recovery_adaptation.NerveResearchRuntime, runtime)
        self.assertIs(consistent_dynamics.product, product)

    def test_planner_failure_restores_instrumented_product(self):
        runtime = recovery_adaptation.NerveResearchRuntime

        def broken_product(*args, **kwargs):
            yield (0, 0, 0)
            raise RuntimeError('planner injected')

        with patch.object(consistent_dynamics, 'product', broken_product):
            # The existing decide() guard converts planner RuntimeError to an
            # abstention; the episode rejects active-phase abstention outright.
            with self.assertRaisesRegex(RuntimeError, 'active controller infeasible'):
                factorial.execute(4, 'drift', 'adaptive_consistent_h3')
            self.assertIs(consistent_dynamics.product, broken_product)
            self.assertIs(recovery_adaptation.NerveResearchRuntime, runtime)

    def test_count_is_measured_not_computed_from_trace(self):
        original_product = consistent_dynamics.product

        def extra_product(*args, **kwargs):
            yield from original_product(*args, **kwargs)
            yield (0, 0, 0)

        # Every choice remains identical; only actual iteration count changes.
        with patch.object(consistent_dynamics, 'product', extra_product):
            with self.assertRaisesRegex(ValueError, 'planning sequence count'):
                factorial.execute(4, 'drift', 'adaptive_consistent_h3')
            self.assertIs(consistent_dynamics.product, extra_product)

    def test_rejects_invalid_timing_counts_arm_and_nested_trace(self):
        arm = 'adaptive_consistent_h3'
        mutations = [('elapsed_seconds', True), ('elapsed_seconds', -1),
                     ('elapsed_seconds', float('nan')), ('elapsed_seconds', float('inf')),
                     ('planning_sequences', True), ('planning_sequences', -1),
                     ('planning_sequences', 27 * 81), ('planning_sequences', 1),
                     ('arm', 'adaptive_legacy_h3')]
        for key, value in mutations:
            row = copy.deepcopy(self.rows[arm])
            row[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                factorial.validate(row, 4, 'drift', arm)
        row = copy.deepcopy(self.rows[arm])
        row['episode']['trace'][0]['true_position'] += .1
        with self.assertRaises(ValueError): factorial.validate(row, 4, 'drift', arm)
        row = copy.deepcopy(self.rows[arm])
        row['extra'] = 0
        with self.assertRaises(ValueError): factorial.validate(row, 4, 'drift', arm)


if __name__ == '__main__':
    unittest.main()
