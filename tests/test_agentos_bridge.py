import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.agentos_learning import AgentOSLearning, expected_handoff

_spec = importlib.util.spec_from_file_location('nerve_agentos_bridge_tests', Path(__file__).resolve().parents[1]/'scripts/agentos_bridge.py')
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)


class AgentOSBridgeTests(unittest.TestCase):
    def test_repository_diagnosis_does_not_infer_or_modify_receipt(self):
        source=Path(__file__).resolve().parents[1]/'docs/evidence/agentos-repository-repair-v2.json'
        raw=source.read_bytes()
        receipt=json.loads(raw)
        target=self.host.directory/'latest-repository-study.json'
        target.write_bytes(raw)
        with patch.object(bridge.RepositoryExperiments,'summary',return_value={'study_id':receipt['id']}), \
             patch.object(bridge.RepositoryExperiments,'status',return_value=dict(revision=receipt['judge_revision'],model=receipt['model'],status='completed',summary=receipt['result'])), \
             patch.object(bridge,'native',side_effect=AssertionError('no model calls')):
            report=bridge.repository_diagnosis(self.host)
        self.assertEqual(report['study_id'],receipt['id'])
        self.assertIn('summary',report)
        self.assertEqual(target.read_bytes(),raw)

    def test_repository_diagnosis_rejects_stale_or_malformed_receipt(self):
        target=self.host.directory/'latest-repository-study.json'
        self.assertEqual(bridge.repository_diagnosis(self.host)['status'],'not_run')
        target.write_text('{broken')
        self.assertEqual(bridge.repository_diagnosis(self.host)['status'],'invalid_receipt')
        target.write_bytes((Path(__file__).resolve().parents[1]/'docs/evidence/agentos-repository-repair-v2.json').read_bytes())
        self.assertEqual(bridge.repository_diagnosis(self.host)['status'],'invalid_receipt')

    def test_repository_diagnosis_rejects_matching_id_with_different_ledger_result(self):
        raw=(Path(__file__).resolve().parents[1]/'docs/evidence/agentos-repository-repair-v2.json').read_bytes()
        receipt=json.loads(raw)
        (self.host.directory/'latest-repository-study.json').write_bytes(raw)
        with patch.object(bridge.RepositoryExperiments,'summary',return_value={'study_id':receipt['id']}), \
             patch.object(bridge.RepositoryExperiments,'status',return_value=dict(revision=receipt['judge_revision'],model=receipt['model'],status='completed',summary={'status':'different'})):
            self.assertEqual(bridge.repository_diagnosis(self.host)['status'],'invalid_receipt')
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root/'vault'
        self.host = AgentOSLearning(self.root/'state')
        for name, value in (('HOME', self.root), ('VAULT', self.vault)):
            patcher = patch.object(bridge, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_publish_includes_budget_queue_in_status_and_obsidian(self):
        (self.vault/'Memory').mkdir(parents=True)
        pending=dict(profile='backend-engineer',cohort='v2',requested_day='2026-10-11',
                     status='deferred_daily_budget',required_sessions=8,remaining_sessions=7)
        (self.host.directory/'pending-repository-study.json').write_text(json.dumps(pending))
        with patch.object(bridge,'claude_key',return_value=None):
            status=bridge.publish(self.host)
        self.assertEqual(status['pending_repository_study'],pending)
        note=(self.vault/'Memory/nerve-status.md').read_text()
        self.assertIn('backend-engineer / v2',note)
        self.assertIn('7 of 8 required native sessions',note)
        self.assertIn('2026-10-11 UTC',note)

    def test_cycle_retries_queued_study_on_new_day_without_new_failures(self):
        import contextlib
        import io
        import sys
        from types import SimpleNamespace
        pending=self.host.directory/'pending-repository-study.json'
        request=dict(profile='queued-profile',cohort='v2',requested_day='2000-01-01',
                     status='deferred_daily_budget')
        pending.write_text(json.dumps(request))
        calls=[]
        def study(host,native,profile,vault,**kwargs):
            calls.append((profile,kwargs['cohort']))
            pending.unlink()
            return {'result':{'status':'no_gain'}}
        with patch.dict(sys.modules,{'agentos_repository':SimpleNamespace(study=study)}), \
             patch.object(sys,'argv',['bridge','cycle','--state',str(self.host.directory)]), \
             patch.object(bridge,'collect_missions',return_value={}), \
             patch.object(bridge,'publish',return_value={}),contextlib.redirect_stdout(io.StringIO()):
            bridge.main()
        self.assertEqual(calls,[('queued-profile','v2')])
        self.assertFalse(pending.exists())
        self.assertEqual(json.loads((self.host.directory/'auto-study.json').read_text())['status'],'no_gain')

    def test_cycle_does_not_retry_queued_budget_on_same_day(self):
        import contextlib
        import io
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock
        pending=self.host.directory/'pending-repository-study.json'
        today=bridge.datetime.now(bridge.timezone.utc).strftime('%Y-%m-%d')
        pending.write_text(json.dumps(dict(profile='worker',cohort='v2',requested_day=today)))
        study=Mock()
        with patch.dict(sys.modules,{'agentos_repository':SimpleNamespace(study=study)}), \
             patch.object(sys,'argv',['bridge','cycle','--state',str(self.host.directory)]), \
             patch.object(bridge,'collect_missions',return_value={}), \
             patch.object(bridge,'publish',return_value={}),contextlib.redirect_stdout(io.StringIO()):
            bridge.main()
        study.assert_not_called()
        self.assertTrue(pending.exists())

    def test_interrupted_repository_study_is_failed_without_recycling_tasks(self):
        experiments=bridge.RepositoryExperiments(self.host.directory/'repository-learning.sqlite3')
        phases=['train','selection','retention','final','final','final']
        tasks=[dict(id=str(n),phase=phase,family='family-'+str(n),task={'source':str(n)})
               for n,phase in enumerate(phases)]
        experiments.start('interrupted',profile='worker',model='model',judge_revision='judge',
                          tasks=tasks,budget=dict(max_tokens=4096,max_iterations=2,timeout_seconds=90))
        bridge.recover_interrupted_repository(self.host)
        bridge.recover_interrupted_repository(self.host)
        self.assertEqual(experiments.summary()['status'],'failed')
        self.assertEqual(experiments.summary()['active_lessons'],0)
        with sqlite3.connect(experiments.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],6)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE kind='failed'").fetchone()[0],1)

    def test_collection_requires_independent_qa_and_distinguishes_timeout_from_reclaim(self):
        path = self.root/'.hermes/kanban/boards/agentos-maintenance/kanban.db'
        path.parent.mkdir(parents=True)
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE tasks(id INTEGER,status TEXT)')
            db.execute('CREATE TABLE task_runs(id INTEGER,task_id INTEGER,profile TEXT,started_at REAL,ended_at REAL,outcome TEXT)')
            db.executemany('INSERT INTO tasks VALUES(?,?)', [(1,'done'),(2,'done'),(3,'done'),(4,'done')])
            db.executemany('INSERT INTO task_runs VALUES(?,?,?,?,?,?)', [
                (1,1,'worker',10,20,'completed'), (2,2,'verifier',10,20,'completed'),
                (3,3,'worker',10,20,'timed_out'), (4,4,'worker',10,20,'reclaimed')])
        mission = self.vault/'Journal/maintenance-missions/one'
        mission.mkdir(parents=True)
        (mission/'mission.json').write_text(json.dumps(dict(verifier_id=2,worker_ids=[1])))
        (mission/'verification.json').write_text(json.dumps(dict(accepted=True,checks=['artifact checked'],issues=[])))
        for name in ('routing.json','scheduling.json'):
            (mission/name).write_text('{}')
        first = bridge.collect_missions(self.host)
        self.assertEqual(first['added'], 2)
        self.assertEqual(bridge.collect_missions(self.host)['added'], 0)
        metrics = self.host.status()['missions'][0]
        self.assertEqual((metrics['tasks'], metrics['passed']), (2,1))
        with sqlite3.connect(path) as db:
            db.execute("UPDATE task_runs SET profile='worker' WHERE id=2")
        fresh = AgentOSLearning(self.root/'other-state')
        self.assertEqual(bridge.collect_missions(fresh)['added'], 1)
        self.assertEqual(fresh.status()['missions'][0]['passed'], 0)

    def test_host_review_vetoes_successful_independent_qa(self):
        path = self.root/'.hermes/kanban/boards/agentos-maintenance/kanban.db'
        path.parent.mkdir(parents=True)
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE tasks(id INTEGER,status TEXT)')
            db.execute('CREATE TABLE task_runs(id INTEGER,task_id INTEGER,profile TEXT,started_at REAL,ended_at REAL,outcome TEXT)')
            db.executemany('INSERT INTO tasks VALUES(?,?)', [(1,'done'),(2,'done')])
            db.executemany('INSERT INTO task_runs VALUES(?,?,?,?,?,?)', [
                (1,1,'worker',10,20,'completed'), (2,2,'verifier',10,20,'completed')])
        mission = self.vault/'Journal/maintenance-missions/reviewed'
        mission.mkdir(parents=True)
        (mission/'mission.json').write_text(json.dumps(dict(verifier_id=2,worker_ids=[1])))
        (mission/'verification.json').write_text(json.dumps(dict(accepted=True,checks=['worker assertion'],issues=[])))
        for name in ('routing.json','scheduling.json'):
            (mission/name).write_text('{}')
        review = mission/'host-review.json'
        rejected = [
            dict(accepted=False,checks=['route evidence'],issues=['unsupported no_paid_routes']),
            dict(accepted=True,checks=['route evidence'],issues=['unsupported no_paid_routes']),
            dict(accepted=1,checks=['route evidence'],issues=[]),
            dict(accepted=True,checks=[],issues=[]),
            dict(accepted=True,checks='assertion',issues=[]),
            dict(accepted=True,checks=['route evidence']),
            dict(accepted=True,checks=['route evidence'],issues=False),
            [], None,
        ]
        for index, value in enumerate(rejected):
            with self.subTest(review=value):
                review.write_text(json.dumps(value))
                host = AgentOSLearning(self.root/('reject-'+str(index)))
                result = bridge.collect_missions(host)
                self.assertEqual(result['added'],0)
                self.assertEqual(result['unverified_missions'],1)
        review.write_text('{invalid')
        self.assertEqual(bridge.collect_missions(self.host)['unverified_missions'],1)
        self.assertEqual(self.host.status()['missions'],[])
        review.write_text(json.dumps(dict(accepted=True,checks=['independent route evidence'],issues=[])))
        self.assertEqual(bridge.collect_missions(self.host)['added'],1)
        review.unlink()
        legacy = AgentOSLearning(self.root/'legacy-state')
        self.assertEqual(bridge.collect_missions(legacy)['added'],1)

    def run_study(self, gain):
        seen, proposals = [], []
        def batch(host, profile, tasks, lesson=None):
            seen.append(([dict(t) for t in tasks], lesson))
            return ({t['id']: expected_handoff(t) if lesson or not gain else {} for t in tasks},
                    dict(provider='mock',model='mock'))
        def native(host, profile, prompt):
            proposals.append(prompt)
            return dict(value=dict(lesson='Use only independent evidence.'),provider='mock',model='mock')
        with patch.object(bridge,'batch',batch), patch.object(bridge,'native',native), patch.object(bridge.subprocess,'check_output',return_value='mock-revision\n'):
            result = bridge.study(self.host,'qa-release')
        self.assertEqual(len(self.host.reserved_evidence()),18)
        self.assertEqual(len(proposals),1)
        training_ids = {t['id'] for t in seen[0][0]}
        for tasks, _ in seen[1:]:
            for task in tasks:
                self.assertNotIn(task['id'],training_ids)
                self.assertNotIn(json.dumps(task['id']),proposals[0])
        # Each factual split may repeat only as paired baseline/lesson arms.
        partitions = {}
        for tasks, advice in seen:
            hashes = frozenset(self.host.evidence_hash(t) for t in tasks)
            for existing in partitions:
                self.assertTrue(hashes == existing or not hashes & existing)
            partitions.setdefault(hashes,[]).append(advice)
        self.assertTrue(all(len(arms)<=2 for arms in partitions.values()))
        return result, seen

    def test_capable_baseline_does_not_manufacture_improvement(self):
        result, seen = self.run_study(False)
        self.assertEqual(result['report']['status'],'no_verified_improvement')
        self.assertIsNone(result['approved_memory'])
        self.assertIsNone(result['report']['final'])
        self.assertEqual(self.host.recall('qa-release'),[])
        self.assertEqual(len(seen),3)  # training + selection pair; final stays unopened.

    def test_positive_fixture_uses_disjoint_final_and_persists_scoped_lesson(self):
        result, seen = self.run_study(True)
        self.assertEqual(result['report']['status'],'observed_final_gain')
        self.assertEqual(result['report']['final']['wins'],5)
        self.assertEqual(result['report']['final']['losses'],0)
        self.assertEqual(len(seen),7)
        self.assertEqual(self.host.recall('qa-release')[0].memory_id,result['approved_memory'])
        self.assertEqual(self.host.recall('unrelated'),[])

    def test_model_change_between_training_and_evaluation_aborts_promotion(self):
        calls = []
        def batch(host, profile, tasks, lesson=None):
            calls.append(tasks)
            return ({t['id']: expected_handoff(t) for t in tasks},
                    dict(requested_model='first-model' if len(calls)==1 else 'changed-model'))
        with patch.object(bridge,'batch',batch), patch.object(bridge,'native',return_value=dict(value=dict(lesson='Check evidence.'))):
            with self.assertRaisesRegex(RuntimeError,'model changed'):
                bridge.study(self.host,'qa-release')
        self.assertEqual(self.host.recall('qa-release'),[])
        self.assertFalse((self.host.directory/'latest-study.json').exists())
