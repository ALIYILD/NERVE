from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from nerve_awim.agent_learning_v12 import AgentTask
from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.repository_agents_v20 import CONTEXT, REPOSITORY_STRATEGIES, repository_judge
from nerve_awim.shadow_learning_v21 import ShadowLearning
from scripts.repository_shadow_v21 import file_task, main


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state.db'
        self.auth = LearningAuthority()
        self.actors = {role: self.auth.issue('tenant', 'agent', role)
                       for role in ('runtime', 'trainer', 'operator', 'auditor', 'evaluator')}
        self.engine = GovernedLearning(self.path, authority=self.auth,
            strategies=REPOSITORY_STRATEGIES, judge=repository_judge,
            contract_revision='test-v1', baseline_routes={CONTEXT: 'ast-inventory'})
        self.initial = self.engine.bootstrap(self.actors['operator'])
        self.shadow = ShadowLearning(self.engine, runtime=self.actors['runtime'],
                                     trainer=self.actors['trainer'], capacity=2)

    def task(self, n=0):
        return AgentTask('task-' + str(n), CONTEXT,
                         f'# private marker {n}\ndef real_{n}():\n    def nested(): pass\n')

    def test_returns_exact_active_result_then_learns_off_path(self):
        calls = []
        original = self.engine.judge
        self.engine.judge = lambda *args: (calls.append(1), original(*args))[1]
        result = self.shadow.execute(self.task())
        self.assertEqual(result, self.engine.execute(self.actors['runtime'], self.task()))
        self.assertEqual(calls, [])
        self.assertEqual(self.engine.status(self.actors['auditor'])['task_counts'], {})
        self.assertEqual(self.shadow.drain()['recorded'], 1)
        row = self.shadow.report(self.actors['auditor'])['actual_active_outcomes'][0]
        self.assertEqual((row['tasks'], row['hits'], row['errors']), (1, 1, 0))
        self.assertGreaterEqual(row['mean_latency_ms'], 0)
        self.assertEqual(self.engine.status(self.actors['auditor'])['active_release'], self.initial['active_release'])
        self.assertNotIn(b'private marker', self.path.read_bytes())

    def test_queue_full_does_not_change_result(self):
        for n in range(3):
            self.assertEqual(self.shadow.execute(self.task(n))['value'], [f'real_{n}'])
        self.assertEqual((self.shadow.pending, self.shadow.dropped), (2, 1))
        self.assertEqual(self.shadow.drain()['recorded'], 2)

    def test_original_handler_exception_and_denominator_preserved(self):
        error = RuntimeError('private failure')
        def broken(payload):
            raise error
        self.engine._registry[(CONTEXT, 'ast-inventory')] = broken
        with self.assertRaises(RuntimeError) as caught:
            self.shadow.execute(self.task())
        self.assertIs(caught.exception, error)
        self.shadow.drain()
        row = self.shadow.report(self.actors['auditor'])['actual_active_outcomes'][0]
        self.assertEqual((row['tasks'], row['hits'], row['errors']), (1, 0, 1))
        self.assertNotIn(b'private failure', self.path.read_bytes())

    def test_judge_failure_is_unjudged_not_success(self):
        self.engine.judge = lambda *args: 'yes'
        self.assertEqual(self.shadow.execute(self.task())['value'], ['real_0'])
        self.assertEqual(self.shadow.drain()['failed'], 1)
        row = self.shadow.report(self.actors['auditor'])['actual_active_outcomes'][0]
        self.assertEqual((row['tasks'], row['hits'], row['unjudged']), (1, 0, 1))
        self.assertEqual(self.engine.status(self.actors['auditor'])['task_counts'], {'train': 1})
        self.shadow.execute(self.task())
        self.assertEqual(self.shadow.drain()['rejected'], 1)

    def test_duplicates_do_not_weight_training(self):
        self.shadow.execute(self.task())
        self.shadow.drain()
        self.shadow.execute(AgentTask('renamed', CONTEXT, self.task().payload))
        self.assertEqual(self.shadow.drain()['rejected'], 1)
        self.assertEqual(self.engine.status(self.actors['auditor'])['task_counts'], {'train': 1})

    def test_holdout_not_reused_as_shadow_training(self):
        for n in range(3):
            self.shadow.execute(self.task(n))
            self.shadow.drain()
        candidate = self.engine.freeze_candidate(self.actors['trainer'])
        held = [self.task(n) for n in range(10, 15)]
        result = self.engine.evaluate_candidate(self.actors['evaluator'], candidate, held)
        self.assertEqual(result['status'], 'rejected')  # strong baseline already optimal
        self.engine.judge = lambda *args: self.fail('reserved holdout reached shadow judge')
        self.shadow.execute(held[0])
        self.assertEqual(self.shadow.drain()['rejected'], 1)

    def test_scope_roles_and_revocation(self):
        other = self.auth.issue('other', 'agent', 'trainer')
        with self.assertRaises(PermissionError):
            ShadowLearning(self.engine, runtime=self.actors['runtime'], trainer=other)
        with self.assertRaises(PermissionError):
            self.shadow.report(self.actors['trainer'])
        self.auth.revoke(self.actors['trainer'])
        self.shadow.execute(self.task())
        with self.assertRaises(PermissionError):
            self.shadow.drain()
        self.assertEqual(self.shadow.pending, 1)

    def test_restart_retains_aggregates_not_pending_payloads(self):
        self.shadow.execute(self.task())
        self.shadow.drain()
        self.shadow.execute(self.task(1))
        restarted = ShadowLearning(self.engine, runtime=self.actors['runtime'], trainer=self.actors['trainer'])
        self.assertEqual(restarted.pending, 0)
        self.assertEqual(restarted.report(self.actors['auditor'])['actual_active_outcomes'][0]['tasks'], 1)

    def test_observation_snapshot_not_mutated_by_consumer(self):
        result = self.shadow.execute(self.task())
        result['value'].append('corruption')
        self.shadow.drain()
        self.assertEqual(self.shadow.report(self.actors['auditor'])['actual_active_outcomes'][0]['hits'], 1)

    def test_cli_real_repository_and_persistent_proposal(self):
        root = Path(__file__).resolve().parents[1]
        db = str(Path(self.temp.name) / 'cli.db')
        files = ['src/nerve_awim/agent_learning_v12.py', 'src/nerve_awim/agent_bridge_v13.py',
                 'src/nerve_awim/core.py']
        with redirect_stdout(StringIO()):
            result = main(['run', '--db', db, '--root', str(root),
                           *[part for file in files for part in ('--file', file)]])
            report = main(['report', '--db', db])
            proposal = main(['propose', '--db', db])
        self.assertEqual(result['collection']['recorded'], 3)
        self.assertEqual(report['shadow']['actual_active_outcomes'][0]['hits'], 3)
        self.assertEqual(proposal['proposal']['status'], 'frozen')
        self.assertEqual(proposal['status']['generation'], 0)
        self.assertIsNone(report['shadow']['cost_usd'])

    def test_file_boundary_and_size(self):
        root = Path(self.temp.name) / 'repo'
        root.mkdir()
        outside = Path(self.temp.name) / 'outside.py'
        outside.write_text('def secret(): pass')
        (root / 'link.py').symlink_to(outside)
        for name in ('../outside.py', 'link.py'):
            with self.assertRaises(ValueError):
                file_task(root, name)
        (root / 'big.py').write_text('x' * 16385)
        with self.assertRaises(ValueError):
            file_task(root, 'big.py')


if __name__ == '__main__':
    unittest.main()
