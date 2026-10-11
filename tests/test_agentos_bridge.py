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
