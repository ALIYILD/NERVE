"""Offline fixtures exercise contracts; fabricated receipts are never live evidence."""
import itertools
import unittest
from nerve_awim.cue_cycle import DiscoveryReceipt, run_cue_cycle
from nerve_awim.cue_experiment import ExperimentTask, ProviderReceipt, JudgeReceipt
import test_cue_learning as fixtures


class CueCycleTests(unittest.TestCase):
    setUp = fixtures.CueLearningTests.setUp

    def run_cycle(self, **changes):
        self.calls = []
        self.discovery_payloads = []
        def discover(role, payload, **kwargs):
            self.discovery_payloads.append((role, payload, kwargs))
            return DiscoveryReceipt({'candidates': ['Check reasoning before answering.']}, .01, False)
        def provider(request):
            self.calls.append(request)
            return ProviderReceipt('right' if request.arm == 'candidate' else 'wrong',
                1. if request.arm == 'candidate' else 0., request.model,
                .009 if request.arm == 'candidate' else .01,
                request.task_id + request.arm, False, False, request.cue_digest, request.arm)
        ticks = itertools.count()
        values = dict(profile=self.profile, model=self.model, task_type='research', manifest=self.manifest,
            selection_tasks=[ExperimentTask(t, 'instruction:' + t, 'right') for t in self.manifest.selection],
            holdout_tasks=[ExperimentTask(t, 'instruction:' + t, 'right') for t in self.manifest.holdout],
            discovery_execute=discover, provider=provider,
            judge=lambda output, expected: JudgeReceipt(output == expected, True),
            generator_id='generator', evaluator_id='independent', max_calls=63,
            max_cost_usd=1, discovery_cost_cap_usd=.1, per_call_cost_cap_usd=.01,
            permission_granted=True, experiment_clock=lambda: next(ticks))
        values.update(changes)
        return run_cue_cycle(self.cce, self.actors['trainer'], self.actors['evaluator'], **values)

    def test_complete_cycle_stops_before_activation_and_never_leaks_test_answers(self):
        result = self.run_cycle()
        self.assertEqual(result['state'], 'awaiting_approval')
        self.assertEqual(result['attempted_calls'], 63)
        self.assertLess(result['known_cost_usd'], 1)
        self.assertFalse(result['activated'])
        self.assertEqual(self.cce.status(self.actors['auditor'], result['candidate'])['status'], 'passed')
        self.assertIsNone(self.cce.select(self.actors['runtime'], self.profile, 'research', permission_granted=True).cue)
        self.assertEqual(self.discovery_payloads[0][1],
            {'operation': 'propose_cognitive_cues', 'discovery_ids': ['d'], 'max_candidates': 1})
        self.assertNotIn('right', str(self.discovery_payloads))
        self.assertNotIn('right', str(result))
        with self.assertRaises(ValueError):
            self.run_cycle()
        self.assertEqual(self.discovery_payloads, [])
        self.assertEqual(self.calls, [])

    def test_absent_proposal_burns_study_without_provider_experiment(self):
        result = self.run_cycle(discovery_execute=lambda *args, **kw:
            DiscoveryReceipt({'candidates': []}, .01, False))
        self.assertEqual(result['reason'], 'no_candidate')
        self.assertEqual(result['attempted_calls'], 1)
        with self.assertRaises(ValueError):
            self.run_cycle()
        self.assertEqual(self.discovery_payloads, [])

    def test_synthetic_discovery_stops_before_selection(self):
        result = self.run_cycle(discovery_execute=lambda *args, **kw:
            DiscoveryReceipt({'candidates': ['Check reasoning.']}, .01))
        self.assertEqual(result['reason'], 'synthetic_discovery')
        self.assertEqual(self.calls, [])

    def test_no_gain_selection_does_not_consume_holdout_calls(self):
        calls = []
        def provider(request):
            calls.append(request)
            return ProviderReceipt('right', 1., request.model, .001,
                request.task_id + request.arm, False, False, request.cue_digest, request.arm)
        result = self.run_cycle(provider=provider)
        self.assertEqual(result['state'], 'rejected')
        self.assertEqual(result['reason'], 'selection_gate_failed')
        self.assertEqual(result['attempted_calls'], 3)
        self.assertEqual({r.task_id for r in calls}, {'s'})
        self.assertIsNone(result['holdout_digest'])
        self.assertEqual(self.cce.status(self.actors['auditor'], result['candidate'])['status'], 'rejected')
        with self.assertRaises(ValueError):
            self.cce.evaluate(self.actors['evaluator'], result['candidate'], (), evaluator_id='independent')

    def test_budget_failure_precedes_discovery(self):
        for change in ({'max_calls': 62}, {'max_cost_usd': .5}, {'per_call_cost_cap_usd': 0}):
            with self.assertRaises(ValueError):
                self.run_cycle(**change)
            self.assertEqual(self.discovery_payloads, [])
            self.assertEqual(self.calls, [])

    def test_permissions_and_risk_gate_before_discovery(self):
        for change in ({'permission_granted': False}, {'clinical': True}, {'risk': 'high'}):
            with self.assertRaises(PermissionError):
                self.run_cycle(**change)
            self.assertEqual(self.discovery_payloads, [])
        original = self.actors['evaluator']
        self.actors['evaluator'] = self.authority.issue('foreign', 'agent', 'evaluator')
        with self.assertRaises(PermissionError):
            self.run_cycle()
        self.actors['evaluator'] = original

    def test_unknown_discovery_billing_blocks_and_sanitizes_error(self):
        def fails(*args, **kwargs):
            raise RuntimeError('secret patient text')
        result = self.run_cycle(discovery_execute=fails)
        self.assertEqual(result['state'], 'blocked')
        self.assertEqual(result['attempted_calls'], 1)
        self.assertNotIn('secret', str(result))
        self.assertEqual(self.calls, [])

    def test_provider_cost_overrun_stops_immediately(self):
        def overspend(request):
            return ProviderReceipt('right', 1., request.model, 5,
                'one', False, False, request.cue_digest, request.arm)
        result = self.run_cycle(provider=overspend)
        self.assertEqual(result['state'], 'blocked')
        self.assertEqual(result['reason'], 'provider_cost_cap_violated')
        self.assertEqual(result['attempted_calls'], 2)
        self.assertGreater(result['known_cost_usd'], 1)
        self.assertEqual(self.cce.status(self.actors['auditor'], result['candidate'])['status'], 'rejected')


if __name__ == '__main__':
    unittest.main()
