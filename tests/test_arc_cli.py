import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ArcCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.state=Path(self.tmp.name)/'state'
        self.source=Path(self.tmp.name)/'sample.py'
        self.source.write_text('def real_local_function():\n    pass\n')

    def call(self,command,*args,code=0):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/agentos_bridge.py'),command,
                               '--state',str(self.state),*map(str,args)],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,code,result.stderr+result.stdout)
        return json.loads(result.stdout)

    def test_local_execution_inspection_and_side_effect_free_replay(self):
        result=self.call('arc-run','--source',self.source,'--task-id','test-local','--restart')
        self.assertTrue(result['verified']); self.assertEqual(result['value'],['real_local_function'])
        self.assertTrue(result['restart_same_outcome']); self.assertEqual(result['dispatches'],1)
        inspected=self.call('arc-inspect','--task-id','test-local')
        self.assertEqual(inspected['episodes'][0]['status'],'succeeded')
        self.assertNotIn('real_local_function',json.dumps(inspected))
        replay=self.call('arc-replay','--decision-id',result['decision_id'])
        self.assertFalse(replay['effects'])

    def test_shadow_release_and_rollback_across_processes(self):
        staged=self.call('arc-stage','--arc-mode','shadow','--context','inventory')
        self.call('arc-promote','--manifest-id',staged['manifest_id'],'--review-ref','local-shadow-review')
        shadow=self.call('arc-run','--source',self.source,'--task-id','shadow')
        self.assertEqual(shadow['status'],'shadow'); self.assertEqual(shadow['dispatches'],0)
        rolled=self.call('arc-rollback','--manifest-id','latest','--review-ref','local-rollback-review')
        self.assertEqual(rolled['modes']['inventory'],'off')
        blocked=self.call('arc-run','--source',self.source,'--task-id','after-rollback')
        self.assertEqual(blocked['status'],'blocked'); self.assertEqual(blocked['dispatches'],0)

    def test_clinical_activation_and_foreign_scope_fail_closed(self):
        blocked=self.call('arc-stage','--arc-mode','enforce','--context','prepare-draft',code=2)
        self.assertEqual(blocked['reason_category'],'PermissionError')
        fixture=Path(self.tmp.name)/'foreign.json'; fixture.write_text(json.dumps({'tenant':'foreign','source':'secret'}))
        blocked=self.call('arc-run','--task',fixture,code=2)
        self.assertEqual(blocked['status'],'blocked')
        self.assertNotIn('secret',json.dumps(blocked))
