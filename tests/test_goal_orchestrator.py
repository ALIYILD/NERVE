import json
from pathlib import Path
import tempfile
import unittest

from nerve_awim.goal_orchestrator import GoalOrchestrator
from nerve_awim.goal_learning import build, execute, fixtures, observe_policy


class GoalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 100.
        self.calls = []

    def supervisor(self, handler=None, validator=None):
        def default(context):
            self.calls.append(context)
            return {'verified': True}
        return GoalOrchestrator(self.temp.name, handlers={'work': handler or default},
                                validators={'work': validator or (lambda r: r['verified'])},
                                clock=lambda: self.now)

    def create(self, supervisor, tasks=None):
        return supervisor.create(goal_id='test', target='independently verified result',
                                 tasks=tasks or [{'id': 'a', 'handler': 'work'}])

    def test_dependency_and_group_completion_survive_restart(self):
        supervisor = self.supervisor()
        self.create(supervisor, [{'id': 'group'}, {'id': 'a', 'parent': 'group', 'handler': 'work'},
                                {'id': 'b', 'handler': 'work', 'depends_on': ['group', 'a']}])
        self.assertEqual(supervisor.tick()['status'], 'active')
        restarted = self.supervisor()
        state = restarted.run()
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[1]['a'], {'verified': True})
        restarted.run()
        self.assertEqual(len(self.calls), 2)

    def test_bounded_failed_target_retry_and_blocked_parent(self):
        supervisor = self.supervisor(handler=lambda _: {'verified': False})
        self.create(supervisor, [{'id': 'group'}, {'id': 'a', 'parent': 'group', 'handler': 'work', 'max_attempts': 3}])
        state = supervisor.run()
        self.assertEqual(state['status'], 'blocked')
        self.assertEqual(state['tasks'][1]['attempts'], 3)
        self.assertEqual(state['tasks'][0]['status'], 'blocked')

    def test_interrupted_execution_is_not_replayed(self):
        def crash(_):
            raise KeyboardInterrupt()
        supervisor = self.supervisor(handler=crash)
        self.create(supervisor)
        with self.assertRaises(KeyboardInterrupt):
            supervisor.tick()
        state = self.supervisor().run()
        self.assertEqual(state['status'], 'blocked')
        self.assertIn('reconciliation', state['tasks'][0]['error'])
        self.assertEqual(self.calls, [])

    def test_exception_blocks_without_leaking_message(self):
        def fail(_):
            raise RuntimeError('secret-content')
        supervisor = self.supervisor(handler=fail)
        self.create(supervisor)
        state = supervisor.run()
        self.assertEqual(state['status'], 'blocked')
        self.assertNotIn('secret-content', json.dumps(state))

    def test_deadline_before_and_during_handler(self):
        def slow(_):
            self.now = 1000.
            return {'verified': True}
        supervisor = self.supervisor(handler=slow)
        self.create(supervisor)
        self.assertEqual(supervisor.run()['status'], 'budget_exhausted')
        self.assertEqual(supervisor.inspect()['tasks'][0]['status'], 'blocked')

    def test_expired_goal_never_calls_handler(self):
        supervisor = self.supervisor()
        self.create(supervisor)
        self.now = 1000.
        self.assertEqual(supervisor.run()['status'], 'budget_exhausted')
        self.assertEqual(self.calls, [])

    def test_cancel_and_tick_budget(self):
        supervisor = self.supervisor()
        self.create(supervisor, [{'id': 'a', 'handler': 'work'}, {'id': 'b', 'handler': 'work'}])
        self.assertEqual(supervisor.run(max_ticks=1)['status'], 'active')
        self.assertEqual(supervisor.cancel()['status'], 'cancelled')
        supervisor.run()
        self.assertEqual(len(self.calls), 1)

    def test_invalid_graph_and_handler(self):
        for tasks in ([{'id': 'a', 'handler': 'missing'}],
                      [{'id': 'group'}, {'id': 'child', 'parent': 'group', 'handler': 'work', 'depends_on': ['group']}],
                      [{'id': 'a', 'handler': 'work', 'depends_on': ['b']}],
                      [{'id': 'a', 'handler': 'work', 'max_attempts': True}],
                      [{'id': 'empty-group'}]):
            with self.assertRaises(ValueError):
                self.create(self.supervisor(), tasks)

    def test_validator_cannot_return_truthy_text(self):
        supervisor = self.supervisor(validator=lambda _: 'yes')
        self.create(supervisor)
        self.assertEqual(supervisor.run()['status'], 'blocked')

    def test_existing_goal_cannot_be_overwritten(self):
        supervisor = self.supervisor()
        self.create(supervisor)
        with self.assertRaises(FileExistsError):
            self.create(supervisor)

    def test_both_domain_loops_with_restart_before_monitor(self):
        supervisor = build(self.temp.name)
        supervisor.run(max_ticks=2)
        state = build(self.temp.name).run()
        self.assertEqual(state['status'], 'complete')
        for domain in ('clinical_os', 'perfflux'):
            receipt = next(t['receipt'] for t in state['tasks'] if t['id'] == domain+':study')
            self.assertEqual(receipt['final']['lesson_hits'], 12)
            self.assertEqual(receipt['final']['losses'], 0)
            self.assertEqual(receipt['capable_control_hits'], 12)
            self.assertEqual(receipt['history'][0]['regression']['baseline_hits'], 8)
            monitor = next(t['receipt'] for t in state['tasks'] if t['id'] == domain+':monitor')
            self.assertTrue(monitor['rollback_verified'])
            self.assertEqual(monitor['healthy_policy']['version'], 1)
            self.assertEqual(monitor['fault_policy']['version'], 2)
        self.assertEqual(state, build(self.temp.name).run())
        with self.assertRaises(ValueError):
            build(self.temp.name, ('perfflux',))

    def test_perf_improves_actual_operations_preserving_digest(self):
        task = fixtures('perfflux', 'unseen', 1)[0].task
        direct, memo = execute('perfflux', task, 'direct'), execute('perfflux', task, 'memoized')
        self.assertEqual(direct['digests'], memo['digests'])
        self.assertEqual(direct['hash_calls'], 12)
        self.assertEqual(memo['hash_calls'], 4)

    def test_rollback_does_not_mutate_prior_policy(self):
        policy = dict(active_strategy='memoized', previous_strategy='direct', version=1, scope='sandbox', status='active')
        rolled = observe_policy(policy, verified=False)
        self.assertEqual(rolled['active_strategy'], 'direct')
        self.assertEqual(policy['active_strategy'], 'memoized')
        with self.assertRaises(ValueError):
            observe_policy(policy, verified='yes')
