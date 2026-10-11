from unittest.mock import patch
import unittest
import test_canary_learning_v23 as fixtures
from nerve_awim.canary_learning_v23 import CanaryLearning
from nerve_awim.repository_agents_v20 import CONTEXT


class PromotionTests(unittest.TestCase):
    task = staticmethod(fixtures.CanaryTests.task)
    start = fixtures.CanaryTests.start
    selected = fixtures.CanaryTests.selected
    execute = fixtures.CanaryTests.execute
    # Reuse fixtures without re-running the inherited canary test cases.
    def setUp(self):
        fixtures.CanaryTests.setUp(self)
        for n in range(5):
            self.execute(self.selected(100 + n * 10000))
        self.canary.promote(self.actors['operator'], self.id, expected_generation=0,
                           reason='monitor-review', monitor_latency_ms=1000)

    def monitored(self, n=999999):
        return self.canary.execute(self.actors['runtime'], self.id, self.task(n))

    def monitor_report(self):
        return self.canary.monitor.report(self.actors['auditor'], self.id)

    def test_checked_success_and_restart(self):
        self.assertTrue(self.monitored()['monitor']['used'])
        self.canary = CanaryLearning(self.engine)
        self.assertEqual(self.monitor_report()['outcomes'], {'passed': 1})
        self.assertEqual(self.monitored(999998)['strategy'], 'ast-inventory')
        self.assertNotIn(b'private source', self.path.read_bytes())

    def test_regression_rolls_back_persistently(self):
        self.engine._registry[(CONTEXT, 'ast-inventory')] = lambda _: []
        result = self.monitored()
        self.assertEqual(result['monitor']['reason'], 'quality_failure')
        self.assertEqual(result['release'], self.baseline['active_release'])
        self.assertEqual(result['generation'], 2)
        self.canary = CanaryLearning(self.engine)
        self.assertEqual(self.monitor_report()['phase'], 'rolled_back')
        self.assertEqual(self.monitored(999998)['strategy'], 'regex-inventory')

    def test_handler_failure_and_no_error_text(self):
        def broken(_):
            raise RuntimeError('secret-handler-text')
        self.engine._registry[(CONTEXT, 'ast-inventory')] = broken
        self.assertEqual(self.monitored()['monitor']['reason'], 'handler_error')
        self.assertNotIn(b'secret-handler-text', self.path.read_bytes())

    def test_nonboolean_judge(self):
        self.engine.judge = lambda *_: 'yes'
        self.assertEqual(self.monitored()['monitor']['reason'], 'judge_error')

    def test_judge_exception(self):
        def broken(*_):
            raise RuntimeError('secret-judge-text')
        self.engine.judge = broken
        self.assertEqual(self.monitored()['monitor']['reason'], 'judge_error')
        self.assertNotIn(b'secret-judge-text', self.path.read_bytes())

    def test_slow_success_rolls_back(self):
        with patch('nerve_awim.promotion_monitor_v24.perf_counter', side_effect=(0, 2)):
            self.assertEqual(self.monitored()['monitor']['reason'], 'latency_failure')
        self.assertEqual(self.monitor_report()['latency']['max_ms'], 2000)

    def test_replay_uses_prior_release_and_cannot_train(self):
        self.monitored()
        result = self.monitored()
        self.assertEqual(result['strategy'], 'regex-inventory')
        self.assertEqual(result['monitor']['reason'], 'not_fresh_or_reserved')
        self.assertEqual(self.monitor_report()['outcomes'], {'passed': 1})
        with self.assertRaises(ValueError):
            self.engine.learn_from_task(self.actors['trainer'], self.task(999999))

    def test_reserved_task_uses_previous_release(self):
        task = self.task(999999)
        _, digest = self.engine._task(task)
        with self.engine._db() as con:
            con.execute('INSERT INTO gl_holdout_reservations VALUES(?,?,?,?)',
                        ('tenant', 'agent', task.task_id, digest))
        self.assertEqual(self.monitored()['strategy'], 'regex-inventory')
        self.assertEqual(self.monitor_report()['outcomes'], {})

    def test_pending_after_restart_fails_closed(self):
        with self.engine._db() as con:
            con.execute('INSERT INTO gl_promotion_outcomes VALUES(?,?,?,NULL)',
                        (self.id, 'crashed', 'pending'))
        self.canary = CanaryLearning(self.engine)
        self.assertEqual(self.monitored()['monitor']['reason'], 'pending_attempt')
        self.assertEqual(self.monitored()['strategy'], 'regex-inventory')
        self.canary.monitor.stop(self.actors['operator'], self.id,
                                expected_generation=1, reason='recover-crash')
        self.assertEqual(self.monitor_report()['phase'], 'rolled_back')

    def test_concurrent_request_uses_previous_release(self):
        original = self.engine._registry[(CONTEXT, 'ast-inventory')]
        def reentrant(payload):
            other = self.monitored(888888)
            self.assertEqual(other['strategy'], 'regex-inventory')
            self.assertEqual(other['monitor']['reason'], 'pending_attempt')
            return original(payload)
        self.engine._registry[(CONTEXT, 'ast-inventory')] = reentrant
        self.assertTrue(self.monitored()['monitor']['used'])

    def test_operator_stop_suppresses_inflight_output(self):
        original = self.engine._registry[(CONTEXT, 'ast-inventory')]
        def stopped(payload):
            self.canary.monitor.stop(self.actors['operator'], self.id,
                                    expected_generation=1, reason='operator-stop')
            return original(payload)
        self.engine._registry[(CONTEXT, 'ast-inventory')] = stopped
        self.assertEqual(self.monitored()['strategy'], 'regex-inventory')
        self.assertEqual(self.monitor_report()['active_generation'], 2)

    def test_newer_generation_not_overwritten_on_failure(self):
        def changed(_):
            self.engine.rollback(self.actors['operator'], self.baseline['active_release'],
                                 expected_generation=1, reason='external-rollback')
            return []
        self.engine._registry[(CONTEXT, 'ast-inventory')] = changed
        self.assertEqual(self.monitored()['monitor']['reason'], 'active_release_changed')
        self.assertEqual(self.monitor_report()['phase'], 'superseded')
        self.assertEqual(self.monitor_report()['active_generation'], 2)

    def test_scope_roles_and_stale_stop(self):
        with self.assertRaises(PermissionError):
            self.canary.monitor.stop(self.actors['runtime'], self.id, expected_generation=1, reason='no')
        with self.assertRaises(ValueError):
            self.canary.monitor.stop(self.actors['operator'], self.id, expected_generation=0, reason='stale')
        other = self.engine.authority.issue('other', 'agent', 'operator')
        self.engine.bootstrap(other)
        with self.assertRaises(LookupError):
            self.canary.monitor.report(other, self.id)

    def test_baseline_error_propagates_after_rollback(self):
        self.engine.judge = lambda *_: False
        def broken(_):
            raise RuntimeError('baseline failed')
        self.engine._registry[(CONTEXT, 'regex-inventory')] = broken
        with self.assertRaisesRegex(RuntimeError, 'baseline failed'):
            self.monitored()
        self.assertEqual(self.monitor_report()['phase'], 'rolled_back')


    def test_fresh_process_resumes_and_rolls_back(self):
        import json
        import os
        import subprocess
        import sys
        code = """
import json, sys
from nerve_awim.agent_learning_v12 import AgentTask
from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.repository_agents_v20 import CONTEXT, REPOSITORY_STRATEGIES, repository_judge
from nerve_awim.canary_learning_v23 import CanaryLearning
auth = LearningAuthority()
engine = GovernedLearning(sys.argv[1], authority=auth, strategies=REPOSITORY_STRATEGIES,
    judge=repository_judge, baseline_routes={CONTEXT: 'regex-inventory'}, contract_revision='test')
controller = CanaryLearning(engine)
actor = auth.issue('tenant', 'agent', 'runtime')
result = controller.execute(actor, sys.argv[2], AgentTask('process-pass', CONTEXT, 'def process_fn(): pass'))
assert result['monitor']['used']
engine.judge = lambda *_: False
result = controller.execute(actor, sys.argv[2], AgentTask('process-fail', CONTEXT, 'def process_fail(): pass'))
assert result['strategy'] == 'regex-inventory'
print(json.dumps(controller.monitor.report(auth.issue('tenant', 'agent', 'auditor'), sys.argv[2])))
"""
        run = subprocess.run([sys.executable, '-c', code, str(self.path), self.id],
                             env={**os.environ, 'PYTHONPATH': 'src'}, check=True,
                             capture_output=True, text=True)
        report = json.loads(run.stdout)
        self.assertEqual(report['outcomes'], {'passed': 1, 'quality_failure': 1})
        self.assertEqual(report['active_generation'], 2)
        self.assertEqual(self.monitor_report()['phase'], 'rolled_back')


class PromotionAtomicTests(unittest.TestCase):
    task = staticmethod(fixtures.CanaryTests.task)
    start = fixtures.CanaryTests.start
    selected = fixtures.CanaryTests.selected
    execute = fixtures.CanaryTests.execute

    def setUp(self):
        fixtures.CanaryTests.setUp(self)
        for n in range(5):
            self.execute(self.selected(100 + n * 10000))

    def test_invalid_budgets_leave_release_unchanged(self):
        for budget in (True, 0, -1, float('nan'), float('inf'), 60001, '1000'):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                self.canary.promote(self.actors['operator'], self.id, expected_generation=0,
                                   reason='invalid-budget', monitor_latency_ms=budget)
        self.assertEqual(self.engine.status(self.actors['operator'])['generation'], 0)

    def test_arm_failure_rolls_back_entire_promotion(self):
        import sqlite3
        with patch.object(self.canary.monitor, 'arm', side_effect=sqlite3.OperationalError('disk error')):
            with self.assertRaises(sqlite3.OperationalError):
                self.canary.promote(self.actors['operator'], self.id, expected_generation=0,
                                   reason='atomic-test', monitor_latency_ms=1000)
        self.assertEqual(self.engine.status(self.actors['operator'])['generation'], 0)
        self.assertEqual(self.canary.report(self.actors['auditor'], self.id)['phase'], 'ready')
        with self.engine._db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM gl_releases').fetchone()[0], 1)
