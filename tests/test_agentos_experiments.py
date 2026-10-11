import copy
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from nerve_awim.agentos_experiments import RepositoryExperiments, SCOPE

BUDGET = dict(max_tokens=512, max_iterations=2, timeout_seconds=60)


def tasks(prefix=''):
    phases = ['train','train','selection','selection','retention','retention','final','final','final']
    return [dict(id=prefix+str(i), phase=p, family=prefix+'family-'+str(i),
                 task=dict(source=prefix+'def function_'+str(i)+'(): pass')) for i,p in enumerate(phases)]


def results(manifest, *, selection_gain=True, final_gain=True, retention_loss=False):
    rows = []
    for t in manifest:
        for arm in (('baseline',) if t['phase']=='train' else ('baseline','lesson')):
            passed = True
            if t['phase']=='selection' and selection_gain and arm=='baseline':
                passed=False
            if t['phase']=='final' and final_gain and arm=='baseline':
                passed=False
            if t['phase']=='retention' and retention_loss and arm=='lesson':
                passed=False
            rows.append(dict(task_id=t['id'], arm=arm, passed=passed, model='model-a', budget=BUDGET.copy()))
    return rows


class RepositoryExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'repository.sqlite3'
        self.now = 1000
        self.host = RepositoryExperiments(self.path, clock=lambda:self.now)
        self.tasks = tasks()

    def start(self, study='study', manifest=None):
        return self.host.start(study, profile='hermes', model='model-a', judge_revision='judge-1',
                               tasks=manifest or self.tasks, budget=BUDGET)

    def accepted(self):
        self.start()
        self.host.freeze('study','Inspect the result before claiming success.')
        return self.host.complete('study', results=results(self.tasks))['lesson_id']

    def observe(self, episode, lesson, passed, **kwargs):
        return self.host.observe(episode, profile='hermes', model='model-a', judge_revision='judge-1',
                                 lesson_id=lesson, passed=passed, **kwargs)

    def test_summary_has_dashboard_scope_and_empty_error(self):
        summary = self.host.summary()
        self.assertEqual(summary['scope'], 'agentos-repository-repair-v1')
        self.assertEqual(summary['status'], 'not_run')
        self.assertEqual(summary['last_error'], '')
        self.accepted()
        self.assertEqual(self.host.summary()['scope'], SCOPE)
        self.assertEqual(self.host.summary()['last_error'], '')

    def test_acceptance_persistence_scoped_recall_and_summary(self):
        lesson = self.accepted()
        restarted = RepositoryExperiments(self.path, clock=lambda:self.now)
        self.assertEqual(restarted.recall('hermes','model-a','judge-1')['id'], lesson)
        self.assertIsNone(restarted.recall('other','model-a','judge-1'))
        self.assertIsNone(restarted.recall('hermes','model-b','judge-1'))
        self.assertIsNone(restarted.recall('hermes','model-a','judge-2'))
        self.assertIsNone(restarted.recall('hermes','model-a','judge-1',scope='handoff'))
        s = restarted.summary()
        self.assertEqual((s['status'],s['wins'],s['tasks'],s['active_lessons']), ('observed_final_gain',3,3,1))
        self.now += 30*86400
        self.assertIsNone(restarted.recall('hermes','model-a','judge-1'))
        with self.assertRaises(ValueError):
            self.observe('expired', lesson, True)

    def test_reservations_ignore_cosmetic_ids_and_are_atomic(self):
        self.start()
        reused = copy.deepcopy(self.tasks)
        for task in reused:
            task['id'] += '-renamed'
            task['task']['id'] = 'cosmetic'
        with self.assertRaises(sqlite3.IntegrityError):
            self.start('repeated', reused)
        with self.assertRaises(LookupError):
            self.host.status('repeated')
        self.host.fail('study','provider unavailable')
        with self.assertRaises(sqlite3.IntegrityError):
            self.start('failed-reuse', reused)

    def test_final_family_separation_and_three_families(self):
        bad = copy.deepcopy(self.tasks)
        bad[-1]['family'] = bad[0]['family']
        with self.assertRaises(ValueError):
            self.start(manifest=bad)
        bad[-1]['family'] = bad[-2]['family']
        with self.assertRaises(ValueError):
            self.start(manifest=bad)

    def test_final_excluded_from_proposer_and_frozen_immutably(self):
        self.start()
        self.assertTrue(all(t['phase']!='final' for t in self.host.development('study')))
        with self.assertRaises(ValueError):
            self.host.complete('study',results=results(self.tasks))
        self.host.freeze('study','candidate')
        self.host.freeze('study','candidate')
        with self.assertRaises(ValueError):
            self.host.freeze('study','changed after evaluation')

    def test_model_budget_mismatch_and_incomplete_pairs_never_approve(self):
        self.start()
        self.host.freeze('study','candidate')
        for field,value in [('model','different'),('budget',dict(BUDGET,max_tokens=999))]:
            rows = results(self.tasks)
            rows[-1][field]=value
            with self.assertRaises(ValueError):
                self.host.complete('study',results=rows)
        with self.assertRaises(ValueError):
            self.host.complete('study',results=results(self.tasks)[:-1])
        self.assertEqual(self.host.status('study')['status'],'frozen')
        self.assertIsNone(self.host.recall('hermes','model-a','judge-1'))

    def test_selection_no_gain_keeps_final_unopened(self):
        self.start()
        self.host.freeze('study','candidate')
        ids = {t['id'] for t in self.tasks if t['phase'] in ('train','selection')}
        rows = [r for r in results(self.tasks,selection_gain=False) if r['task_id'] in ids]
        report = self.host.finish_no_gain('study',results=rows)
        self.assertEqual(report['status'],'no_gain')
        self.assertFalse(report['final']['evaluated'])
        self.assertIsNone(report['lesson_id'])

    def test_retention_regression_can_stop_before_final(self):
        self.start()
        self.host.freeze('study','candidate')
        ids = {t['id'] for t in self.tasks if t['phase']!='final'}
        rows = [r for r in results(self.tasks,retention_loss=True) if r['task_id'] in ids]
        self.assertEqual(self.host.finish_no_gain('study',results=rows)['status'],'no_gain')

    def test_early_stop_cannot_skip_successful_development_or_partial_phase(self):
        self.start()
        self.host.freeze('study','candidate')
        ids = {t['id'] for t in self.tasks if t['phase']=='selection'}
        rows = [r for r in results(self.tasks) if r['task_id'] in ids]
        with self.assertRaises(ValueError):
            self.host.finish_no_gain('study',results=rows)
        with self.assertRaises(ValueError):
            self.host.finish_no_gain('study',results=rows[:-1])

    def test_final_tie_or_loss_never_approves(self):
        self.start()
        self.host.freeze('study','candidate')
        self.assertEqual(self.host.complete('study',results=results(self.tasks,final_gain=False))['status'],'no_gain')
        fresh = tasks('second-')
        self.start('second',fresh)
        self.host.freeze('second','candidate')
        rows = results(fresh)
        for row in rows:
            if row['task_id']==fresh[-1]['id']:
                row['passed'] = row['arm']=='baseline'
        self.assertIsNone(self.host.complete('second',results=rows)['lesson_id'])

    def test_two_recent_failures_roll_back_atomically_after_restart(self):
        lesson = self.accepted()
        self.assertFalse(self.observe('first',lesson,False)['rollback'])
        self.host = RepositoryExperiments(self.path,clock=lambda:self.now)
        self.assertTrue(self.observe('second',lesson,False)['rollback'])
        self.assertIsNone(self.host.recall('hermes','model-a','judge-1'))
        self.assertEqual(self.host.summary()['rollbacks'],1)
        with self.assertRaises(ValueError):
            self.observe('third',lesson,True)
        self.assertEqual(self.observe('second',lesson,True),dict(duplicate=True,passed=False))

    def test_any_paired_regression_rolls_back_and_old_failures_age_out(self):
        lesson = self.accepted()
        self.observe('initial',lesson,False)
        for i in range(5):
            self.observe('pass-'+str(i),lesson,True)
        self.assertFalse(self.observe('later',lesson,False)['rollback'])
        self.assertTrue(self.observe('paired',lesson,False,baseline_passed=True)['rollback'])

    def test_exactly_once_concurrency_and_immutable_receipts(self):
        lesson = self.accepted()
        def record(_):
            host=RepositoryExperiments(self.path,clock=lambda:self.now)
            return host.observe('same', profile='hermes',model='model-a',judge_revision='judge-1',
                                lesson_id=lesson,passed=False)
        with ThreadPoolExecutor(max_workers=4) as pool:
            output=list(pool.map(record,range(8)))
        self.assertEqual(sum(not r['duplicate'] for r in output),1)
        self.assertIsNotNone(self.host.recall('hermes','model-a','judge-1'))
        with sqlite3.connect(self.path) as db:
            for statement in ('DELETE FROM events','UPDATE receipts SET passed=1','DELETE FROM tasks'):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(statement)

    def test_partial_failure_receipts_and_terminal_state(self):
        self.start()
        partial=results(self.tasks)[:2]
        self.host.fail('study','timeout',results=partial)
        self.assertEqual(self.host.summary()['last_error'],'timeout')
        with sqlite3.connect(self.path) as db:
            self.assertIn('timeout',db.execute("SELECT payload FROM events WHERE kind='failed'").fetchone()[0])
        with self.assertRaises(ValueError):
            self.host.freeze('study','new attempt')
        with self.assertRaises(ValueError):
            self.host.fail('study','repeated')

    def test_live_model_scope_mismatch_and_transaction_failure(self):
        lesson=self.accepted()
        with self.assertRaises(ValueError):
            self.observe('wrong-scope',lesson,True,scope='handoff')
        with self.assertRaises(ValueError):
            self.host.observe('wrong-model',profile='hermes',model='other',judge_revision='judge-1',lesson_id=lesson,passed=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TRIGGER fail_event BEFORE INSERT ON events WHEN NEW.kind='live_outcome' BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.observe('crashed',lesson,False,baseline_passed=True)
        self.assertIsNotNone(self.host.recall('hermes','model-a','judge-1'))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],0)


if __name__=='__main__':
    unittest.main()
