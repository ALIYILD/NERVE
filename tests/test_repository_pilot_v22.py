from pathlib import Path
import tempfile
import unittest

from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.repository_agents_v20 import CONTEXT, REPOSITORY_STRATEGIES, repository_judge
from nerve_awim.repository_pilot_v22 import RepositoryPilot, file_task
from nerve_awim.shadow_learning_v21 import ShadowLearning


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for n in range(16):
            (self.root / f'{n}.py').write_text(f'def top_{n}():\n    def nested(): pass\n')
        self.train = [f'{n}.py' for n in range(3)]
        self.holdout = [f'{n}.py' for n in range(3, 8)]
        auth = LearningAuthority()
        self.actors = {r: auth.issue('tenant', 'agent', r)
                       for r in ('trainer', 'runtime', 'evaluator', 'operator', 'auditor')}
        self.engine = GovernedLearning(self.root / 'state.db', authority=auth,
            strategies=REPOSITORY_STRATEGIES, judge=repository_judge,
            baseline_routes={CONTEXT: 'ast-inventory'}, contract_revision='test')
        self.engine.bootstrap(self.actors['operator'])
        self.pilot = RepositoryPilot(self.engine, self.root)
        self.shadow = ShadowLearning(self.engine, runtime=self.actors['runtime'], trainer=self.actors['trainer'])

    def plan(self, study='study', train=None, holdout=None):
        return self.pilot.plan(self.actors['evaluator'], study=study, repository='repo',
                               train=train or self.train, holdout=holdout or self.holdout)

    def test_full_lifecycle_restart_and_no_gain(self):
        planned = self.plan()
        self.pilot = RepositoryPilot(self.engine, self.root)
        self.assertEqual(self.pilot.collect(self.actors['trainer'], 'study', self.shadow)['recorded'], 3)
        candidate = self.pilot.freeze(self.actors['trainer'], 'study')
        self.assertEqual(candidate, self.pilot.freeze(self.actors['trainer'], 'study'))
        self.assertEqual(self.pilot.evaluate(self.actors['evaluator'], 'study')['status'], 'rejected')
        review = self.pilot.review(self.actors['auditor'], 'study')
        self.assertEqual(review['recommendation'], 'reject_rollout')
        self.assertEqual(review['active_release'], planned['active_release'])
        self.assertEqual(review['manifest_sha256'], planned['manifest_sha256'])
        with self.assertRaises(ValueError):
            self.pilot.evaluate(self.actors['evaluator'], 'study')
        with self.assertRaises(ValueError):
            self.pilot.collect(self.actors['trainer'], 'study', self.shadow)

    def test_reserved_holdout_cannot_train_through_core_or_shadow(self):
        self.plan()
        task = file_task(self.root, '3.py')
        with self.assertRaises(ValueError):
            self.engine.learn_from_task(self.actors['trainer'], task)
        self.shadow.execute(task)
        self.assertEqual(self.shadow.drain()['rejected'], 1)

    def test_changed_holdout_path_cannot_become_training(self):
        self.plan()
        (self.root / '3.py').write_text('def changed(): pass')
        with self.assertRaisesRegex(ValueError, 'assignment'):
            self.plan('new', train=['3.py', '1.py', '2.py'], holdout=[f'{n}.py' for n in range(8, 13)])

    def test_changed_training_preflight_has_no_partial_learning(self):
        self.plan()
        (self.root / '2.py').write_text('def changed(): pass')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.pilot.collect(self.actors['trainer'], 'study', self.shadow)
        self.assertEqual(self.engine.status(self.actors['auditor'])['task_counts'], {})

    def test_holdout_change_rejected_before_scoring(self):
        self.plan()
        self.pilot.collect(self.actors['trainer'], 'study', self.shadow)
        self.pilot.freeze(self.actors['trainer'], 'study')
        (self.root / '7.py').write_text('def changed(): pass')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.pilot.evaluate(self.actors['evaluator'], 'study')
        self.assertEqual(self.pilot.review(self.actors['auditor'], 'study')['candidate_status'], 'frozen')

    def test_no_freeze_without_complete_training(self):
        self.plan()
        with self.assertRaises(ValueError):
            self.pilot.freeze(self.actors['trainer'], 'study')
        with self.assertRaises(ValueError):
            self.pilot.evaluate(self.actors['evaluator'], 'study')

    def test_duplicate_bytes_and_failed_plan_are_atomic(self):
        (self.root / '7.py').write_bytes((self.root / '0.py').read_bytes())
        with self.assertRaises(ValueError):
            self.plan()
        with self.engine._db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM gl_holdout_reservations').fetchone()[0], 0)

    def test_reused_holdout_not_new_evidence(self):
        self.plan()
        with self.assertRaises(ValueError):
            self.plan('another')

    def test_roles_and_scope_isolation(self):
        with self.assertRaises(PermissionError):
            self.pilot.plan(self.actors['trainer'], study='study', repository='repo', train=self.train, holdout=self.holdout)
        self.plan()
        other = self.engine.authority.issue('other', 'agent', 'operator')
        self.engine.bootstrap(other)
        with self.assertRaises(LookupError):
            self.pilot.review(other, 'study')

    def test_positive_quality_review_becomes_stale_after_activation(self):
        engine = GovernedLearning(self.root / 'positive.db', authority=self.engine.authority,
            strategies=REPOSITORY_STRATEGIES, judge=repository_judge,
            baseline_routes={CONTEXT: 'regex-inventory'}, contract_revision='positive-test')
        engine.bootstrap(self.actors['operator'])
        pilot = RepositoryPilot(engine, self.root)
        shadow = ShadowLearning(engine, runtime=self.actors['runtime'], trainer=self.actors['trainer'])
        pilot.plan(self.actors['evaluator'], study='positive', repository='repo',
                   train=self.train, holdout=self.holdout)
        pilot.collect(self.actors['trainer'], 'positive', shadow)
        candidate = pilot.freeze(self.actors['trainer'], 'positive')
        self.assertEqual(pilot.evaluate(self.actors['evaluator'], 'positive')['status'], 'passed')
        self.assertEqual(pilot.review(self.actors['auditor'], 'positive')['recommendation'],
                         'quality_passed_operator_review_required')
        self.assertEqual(engine.status(self.actors['auditor'])['generation'], 0)
        engine.activate(self.actors['operator'], candidate, expected_generation=0, reason='test-review')
        self.assertEqual(pilot.review(self.actors['auditor'], 'positive')['recommendation'],
                         'stale_candidate_reject_rollout')


if __name__ == '__main__':
    unittest.main()
