import dataclasses
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim.generation_memory import GenerationMemory, GenerationScope
from nerve_awim.memory_v18 import MemoryActor


class GenerationMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.host=AgentOSLearning(self.tmp.name)
        self.store=GenerationMemory(self.host.ledger)
        self.actor=self.host.actor('qa-release')
        self.scope=GenerationScope('qa-release','synthetic-audit','handoff','contract1','runtime1','model1','template1','grader1')
        self.until=int(time.time())+3600

    def note(self,*,approve=True,text='A simulated command failed; verify the output.',source='trial1',category='failed_attempt'):
        mid=self.store.propose_note(self.actor,self.scope,text=text,category=category,data_class='synthetic',source_id=source,valid_until=self.until)
        if approve:
            self.host.ledger.decide(self.actor,mid,approve=True,evaluator_id='grader1')
        return mid

    def freeze(self,mid,**kwargs):
        return self.store.freeze(self.actor,self.scope,memory_ids=[mid],valid_until=self.until,**kwargs)

    def test_real_subprocess_restart_and_parent_lineage(self):
        mid=self.note();parent=self.freeze(mid)
        child=self.freeze(mid,parent_id=parent)
        script='''import json,sys
from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim.generation_memory import GenerationMemory,GenerationScope
host=AgentOSLearning(sys.argv[1]); actor=host.actor('qa-release')
value=GenerationMemory(host.ledger).handoff(actor,sys.argv[2],GenerationScope(**json.loads(sys.argv[3])))
print(json.dumps(value))'''
        result=subprocess.run([sys.executable,'-c',script,self.tmp.name,child,json.dumps(dataclasses.asdict(self.scope))],check=True,capture_output=True,text=True)
        value=json.loads(result.stdout)
        self.assertEqual(value['parent'],parent)
        self.assertEqual(value['notes'][0]['memory_id'],mid)
        self.assertFalse(value['authorization_granted'])
        meta=self.store.metadata(self.actor,child,self.scope)
        self.assertNotIn('notes',meta)
        self.assertNotIn('simulated',json.dumps(meta))

    def test_pending_and_forged_authority_denied(self):
        mid=self.note(approve=False)
        with self.assertRaises(ValueError):self.freeze(mid)
        forged=MemoryActor(self.actor.tenant_id,self.actor.agent_id,self.actor.permissions,self.actor._capability)
        with self.assertRaises(PermissionError):
            self.store.freeze(forged,self.scope,memory_ids=[mid],valid_until=self.until)
        reader=self.host.authority.issue('agentos-local','qa-release',permissions=('read',))
        with self.assertRaises(PermissionError):
            self.store.propose_note(reader,self.scope,text='x',category='hypothesis',data_class='public',source_id='trial',valid_until=self.until)
        self.assertEqual(self.host.ledger.status(self.actor,mid).status,'pending')

    def test_scope_and_tenant_leaks_fail(self):
        mid=self.note();sid=self.freeze(mid)
        for field in dataclasses.asdict(self.scope):
            scope=dataclasses.replace(self.scope,**{field:'different'})
            with self.subTest(field=field),self.assertRaises((ValueError,PermissionError)):
                self.store.handoff(self.actor,sid,scope)
        other=self.host.authority.issue('different','qa-release',permissions=('read',))
        with self.assertRaises(LookupError):self.store.handoff(other,sid,self.scope)

    def test_revocation_and_expiry_revalidated_for_ancestors(self):
        mid=self.note();parent=self.freeze(mid)
        second=self.note(text='Hypothesis: verify return codes.',source='trial2',category='hypothesis')
        child=self.freeze(second,parent_id=parent)
        with patch('nerve_awim.generation_memory.time.time',return_value=self.until+1):
            with self.assertRaises(ValueError):self.store.handoff(self.actor,child,self.scope)
        self.host.ledger.revoke(self.actor,mid,evaluator_id='grader1')
        with self.assertRaises(ValueError):self.store.handoff(self.actor,child,self.scope)

    def test_immutable_snapshot_and_content_tampering(self):
        mid=self.note();sid=self.freeze(mid)
        with sqlite3.connect(self.host.path) as db:
            for sql in ('UPDATE generation_snapshots SET payload=\'{}\'','DELETE FROM generation_snapshots'):
                with self.assertRaises(sqlite3.IntegrityError):db.execute(sql)
            db.execute("UPDATE trusted_memory_v18 SET content='forged' WHERE memory_id=?",(mid,))
        with self.assertRaises(ValueError):self.store.handoff(self.actor,sid,self.scope)

    def test_duplicate_evidence_and_secret_or_patient_labels_rejected(self):
        first=self.note();second=self.note(source='trial2')
        with self.assertRaises(ValueError):
            self.store.freeze(self.actor,self.scope,memory_ids=[first,second],valid_until=self.until)
        third=self.note(text='Other observation',source='trial1')
        with self.assertRaises(ValueError):
            self.store.freeze(self.actor,self.scope,memory_ids=[first,third],valid_until=self.until)
        for kwargs in (dict(text='password=secret',data_class='public'),dict(text='patient history',data_class='patient')):
            with self.assertRaises(ValueError):
                self.store.propose_note(self.actor,self.scope,category='observation',source_id='trial3',valid_until=self.until,**kwargs)

    def test_legacy_context_never_imported(self):
        mid=self.host.ledger.propose(self.actor,context='legacy',content='Approved legacy note',source_id='legacy',valid_until=self.until)
        self.host.ledger.decide(self.actor,mid,approve=True,evaluator_id='grader1')
        with self.assertRaises(ValueError):self.freeze(mid)

    def test_wrong_evaluator_and_native_budget_unchanged(self):
        mid=self.note(approve=False)
        self.host.ledger.decide(self.actor,mid,approve=True,evaluator_id='other-grader')
        with self.assertRaises(ValueError):self.freeze(mid)
        with sqlite3.connect(self.host.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM nerve_calls').fetchone()[0],0)
        self.assertEqual(self.host.recall('qa-release'),[])

    def test_snapshot_bound_and_deterministic_retries(self):
        mid=self.note();sid=self.freeze(mid)
        self.assertEqual(self.freeze(mid),sid)
        with self.assertRaises(ValueError):
            self.store.freeze(self.actor,self.scope,memory_ids=[mid]*9,valid_until=self.until)
        with self.assertRaises(ValueError):
            self.store.freeze(self.actor,self.scope,memory_ids=[mid],valid_until=True)


if __name__=='__main__':unittest.main()
