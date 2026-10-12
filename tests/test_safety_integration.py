"""Protected runtime and training never fall back to local handlers."""
from pathlib import Path
import unittest

from nerve_awim.agent_learning_v12 import AgentTask, RegisteredStrategy
from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.safety_control.client import SafetyUnavailable
from nerve_awim.safety_control.integration import bind
from test_safety_transport import MODEL, ProcessFixture


class SafetyIntegrationTests(ProcessFixture):
    def setUp(self):
        super().setUp()
        self.authority = LearningAuthority()
        self.actors = {role: self.authority.issue('tenant', 'agent', role)
                       for role in ('operator', 'runtime', 'trainer', 'evaluator')}
        self.local_calls = []
        self.path = Path(self.temp.name) / 'learning.sqlite'
        self.engine = self.make_engine()
        self.engine.bootstrap(self.actors['operator'])

    def make_engine(self):
        def local(value):
            self.local_calls.append(value)
            return 'LOCAL'
        return GovernedLearning(self.path, authority=self.authority,
            strategies=[RegisteredStrategy(strategy_id='upper', context='work', handler=local)],
            judge=lambda task, value: value == task.payload.upper(),
            contract_revision='protected-test-v1', baseline_routes={'work': 'upper'})

    def bind(self, engine=None):
        bind(engine or self.engine, self.actors['operator'], 'work', self.client,
             model_digest=MODEL, tools={'upper': 'uppercase'})

    def test_unbound_baseline_uninterrupted_then_bound_remote_only(self):
        task = AgentTask('one', 'work', 'hello')
        self.assertEqual(self.engine.execute(self.actors['runtime'], task)['value'], 'LOCAL')
        self.bind()
        self.assertEqual(self.engine.execute(self.actors['runtime'], task)['value'], 'HELLO')
        self.assertEqual(self.local_calls, ['hello'])

    def test_restart_missing_adapter_denied_and_reattach_works(self):
        self.bind()
        reopened = self.make_engine()
        task = AgentTask('one', 'work', 'hello')
        with self.assertRaises(PermissionError):
            reopened.execute(self.actors['runtime'], task)
        self.bind(reopened)
        self.assertEqual(reopened.execute(self.actors['runtime'], task)['value'], 'HELLO')
        self.assertEqual(self.local_calls, [])

    def test_stop_denies_runtime_and_training_without_local_fallback(self):
        self.bind()
        self.owner_post('stop', {'reason': 'test-stop'})
        with self.assertRaises(SafetyUnavailable):
            self.engine.execute(self.actors['runtime'], AgentTask('live', 'work', 'hello'))
        with self.assertRaises(RuntimeError):
            self.engine.learn_from_task(self.actors['trainer'], AgentTask('train', 'work', 'training'))
        self.assertEqual(self.local_calls, [])
        with self.engine._db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM gl_outcomes').fetchone()[0], 0)

    def test_training_and_holdout_handlers_execute_remotely(self):
        self.bind()
        for index in range(3):
            self.engine.learn_from_task(self.actors['trainer'], AgentTask(f'train{index}', 'work', f'training{index}'))
        candidate = self.engine.freeze_candidate(self.actors['trainer'])
        report = self.engine.evaluate_candidate(self.actors['evaluator'], candidate,
                    [AgentTask(f'hold{index}', 'work', f'heldout{index}') for index in range(5)])
        # Both routes are already capable: remote execution is verified but
        # no improvement must not be mislabeled as an eligible release.
        self.assertEqual(report['status'], 'rejected')
        self.assertEqual(report['contexts']['work']['baseline_hits'], 5)
        self.assertEqual(report['contexts']['work']['candidate_hits'], 5)
        with self.engine._db() as con:
            self.assertEqual(con.execute('SELECT SUM(success) FROM gl_outcomes').fetchone()[0], 3)
        self.assertEqual(self.local_calls, [])

    def test_stop_cannot_be_bypassed_via_holdout_and_other_scope_continues(self):
        self.bind()
        for index in range(3):
            self.engine.learn_from_task(self.actors['trainer'], AgentTask(f'train{index}', 'work', f'training{index}'))
        candidate = self.engine.freeze_candidate(self.actors['trainer'])
        self.owner_post('stop', {'reason': 'test-stop'})
        with self.assertRaises(RuntimeError):
            self.engine.evaluate_candidate(self.actors['evaluator'], candidate,
                [AgentTask(f'hold{index}', 'work', f'heldout{index}') for index in range(5)])
        self.assertEqual(self.engine.candidate_report(self.actors['operator'], candidate)['status'], 'failed')
        self.assertEqual(self.local_calls, [])
        independent_operator = self.authority.issue('tenant', 'independent', 'operator')
        independent_runtime = self.authority.issue('tenant', 'independent', 'runtime')
        self.engine.bootstrap(independent_operator)
        self.assertEqual(self.engine.execute(independent_runtime, AgentTask('independent', 'work', 'hello'))['value'], 'LOCAL')

    def test_binding_owner_only_immutable_and_prior_guard_preserved(self):
        with self.assertRaises(PermissionError):
            bind(self.engine, self.actors['runtime'], 'work', self.client,
                 model_digest=MODEL, tools={'upper': 'uppercase'})
        self.bind()
        with self.assertRaises(PermissionError):
            bind(self.engine, self.actors['operator'], 'work', self.client,
                 model_digest='b' * 64, tools={'upper': 'uppercase'})
        def deny(*args):
            raise PermissionError('preexisting gate')
        with self.assertRaisesRegex(PermissionError, 'preexisting gate'):
            self.engine.execute(self.actors['runtime'], AgentTask('one', 'work', 'hello'), guard=deny)
        self.assertEqual(self.local_calls, [])


if __name__ == '__main__':
    unittest.main()
