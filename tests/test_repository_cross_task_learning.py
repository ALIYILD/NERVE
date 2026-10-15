import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from nerve_awim.adaptation_repository import build_repository, run_repository


class CrossTaskLearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'repo'
        self.root.mkdir()
        self.db=str(Path(self.tmp.name)/'learning.db')
        # Distinct files, each exposing regex's inability to exclude methods.
        (self.root/'training.py').write_text('class A:\n    def method(self): pass\ndef public(): pass\n')
        (self.root/'evaluation.py').write_text('class B:\n    def other(self): pass\nasync def fresh(): pass\n')

    def run_task(self, name, **kwargs):
        return run_repository(self.db,self.root,paths=[name+'.py'],initial_tool='regex-inventory',learn=True,**kwargs)

    def test_learns_verified_recovery_and_reuses_after_reopen(self):
        first=self.run_task('training',restart=True)
        second=self.run_task('evaluation')
        strong=run_repository(str(Path(self.tmp.name)/'control.db'),self.root,paths=['evaluation.py'])
        self.assertTrue(first['success'] and second['success'] and strong['success'])
        self.assertEqual(len(first['attempts']),2)
        self.assertEqual(first['review_probes'],1)
        self.assertEqual(second['memory_decision_id'],first['learned_episode_ids'][0])
        self.assertEqual(len(second['attempts']),1)
        self.assertEqual(second['review_probes'],0)
        self.assertEqual(second['outputs'],strong['outputs'])
        self.assertEqual(len(second['attempts']),len(strong['attempts']))

    def test_retraction_removes_influence(self):
        first=self.run_task('training')
        c=build_repository(self.db,repository_root=self.root)
        c['arc'].retract(c['operator'],first['learned_episode_ids'][0])
        result=self.run_task('evaluation')
        self.assertIsNone(result['memory_decision_id'])
        self.assertEqual(len(result['attempts']),2)

    def test_expiry_removes_influence(self):
        first=self.run_task('training')
        c=build_repository(self.db,repository_root=self.root)
        with c['engine']._db() as con:
            con.execute('UPDATE arc_memory SET expires=0 WHERE decision=?',(first['learned_episode_ids'][0],))
        self.assertIsNone(self.run_task('evaluation')['memory_decision_id'])

    def test_root_isolation_and_kill_switch(self):
        self.run_task('training')
        other=Path(self.tmp.name)/'other';other.mkdir()
        (other/'evaluation.py').write_text((self.root/'evaluation.py').read_text())
        result=run_repository(self.db,other,paths=['evaluation.py'],initial_tool='regex-inventory',learn=True)
        self.assertIsNone(result['memory_decision_id'])
        c=build_repository(self.db,repository_root=self.root)
        c['adaptation'].kill_switch(c['operator'],reason='test-stop')
        with self.assertRaises(RuntimeError): self.run_task('evaluation')

    def test_off_and_shadow_cannot_learn(self):
        for mode in ('off','shadow'):
            with self.assertRaises(ValueError): self.run_task('training',mode=mode)

    def test_default_does_not_consume_or_create_learning(self):
        self.run_task('training')
        result=run_repository(self.db,self.root,paths=['evaluation.py'],initial_tool='regex-inventory')
        self.assertFalse(result['learning_enabled'])
        self.assertIsNone(result['memory_decision_id'])
        self.assertEqual(result['learned_episode_ids'],[])
        self.assertEqual(len(result['attempts']),2)

    def test_memory_cannot_override_current_outcome_verification(self):
        from unittest.mock import patch
        self.run_task('training')
        with patch.dict('nerve_awim.adaptation_repository.TOOLS',{'ast-inventory':lambda source:['wrong']}):
            result=self.run_task('evaluation')
        self.assertFalse(result['success'])
        self.assertEqual(result['outputs'],[])
        self.assertEqual(result['learned_episode_ids'],[])
        self.assertTrue(all(a['status']=='failed' for a in result['attempts']))

    def test_other_review_provenance_does_not_select_route(self):
        first=self.run_task('training')
        c=build_repository(self.db,repository_root=self.root)
        c['arc'].review(c['operator'],first['learned_episode_ids'][0],label='accepted',provenance='unrelated-review')
        self.assertIsNone(self.run_task('evaluation')['memory_decision_id'])

    def test_cli_persists_across_processes(self):
        project=Path(__file__).resolve().parents[1]
        before={p.name:p.read_bytes() for p in self.root.glob('*.py')}
        results=[]
        for name in ('training','evaluation'):
            process=subprocess.run([sys.executable,str(project/'scripts/agentos_bridge.py'),
                'adaptation-run','--learn','--state',str(Path(self.tmp.name)/'cli-state'),
                '--repository',str(self.root),'--source',name+'.py','--scenario','recover-regex'],
                env={**os.environ,'PYTHONPATH':str(project/'src')},capture_output=True,text=True,timeout=30)
            self.assertEqual(process.returncode,0,process.stderr+process.stdout)
            results.append(json.loads(process.stdout))
        self.assertEqual(results[1]['memory_decision_id'],results[0]['learned_episode_ids'][0])
        self.assertEqual(len(results[1]['attempts']),1)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.glob('*.py')})
