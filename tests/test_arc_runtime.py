import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from nerve_awim.arc_contracts import DecisionRecord, EvidenceRef
from nerve_awim.arc_execution import ArcRuntime, ToolSpec, digest
from nerve_awim.agent_learning_v12 import RegisteredStrategy, AgentTask
from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority

class ArcRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.now=100.; self.effects=[]; self.failure=False; self.result={'done':True}
        self.auth=LearningAuthority(); self.runtime_actor=self.auth.issue('tenant','agent','runtime'); self.operator=self.auth.issue('tenant','agent','operator')
        def handler(args):
            self.effects.append(args)
            if self.failure: raise TimeoutError('after possible effect')
            return self.result
        self.engine=GovernedLearning(self.tmp.name+'/state.db',authority=self.auth,strategies=[RegisteredStrategy('read','read',handler),RegisteredStrategy('write','write',handler)],judge=lambda *a:True,contract_revision='arc-test',baseline_routes={'read':'read','write':'write'})
        self.engine.bootstrap(self.operator)
        self.tools={k:ToolSpec(k,lambda a:type(a) is dict and set(a)=={'x'},lambda value,args:{'done':value.get('done') is True},risk=k,required_sources=('input',)) for k in ('read','write')}
        self.arc=ArcRuntime(self.engine,tools=self.tools,clock=lambda:self.now,mode='enforce')
        self.ref=self.arc.snapshot(self.runtime_actor,'input',{'x':1})
    def propose(self,tool='read',**kw):
        return self.arc.propose(self.runtime_actor,kw.pop('task_id','task'),tool,kw.pop('arguments',{'x':1}),kw.pop('evidence_refs',[self.ref]),'complete',['done'],**kw)
    def test_roundtrip_and_verified_semantics(self):
        d=self.propose(); self.assertEqual(DecisionRecord.from_json(d.to_json()),d)
        outcome=self.arc.execute(self.runtime_actor,d.decision_id)
        self.assertEqual(outcome.semantic_status,'verified'); self.assertEqual(outcome.transport_status,'success')
    def test_empty_success_is_not_completion(self):
        self.result={}; out=self.arc.execute(self.runtime_actor,self.propose().decision_id)
        self.assertEqual(out.transport_status,'success');self.assertEqual(out.semantic_status,'failed')
    def test_stale_changed_missing_cross_scope(self):
        with self.assertRaises(ValueError): self.propose(evidence_refs=[])
        other=self.auth.issue('other','agent','runtime')
        with self.assertRaises(PermissionError): self.arc.propose(other,'task','read',{'x':1},[self.ref],'goal',['done'])
        d=self.propose(); self.now+=1;self.arc.snapshot(self.runtime_actor,'input',{'x':2})
        with self.assertRaisesRegex(ValueError,'source changed'): self.arc.execute(self.runtime_actor,d.decision_id)
    def test_expiry_and_fresh_same_content(self):
        self.now+=4000
        with self.assertRaisesRegex(ValueError,'stale'): self.propose()
        self.ref=self.arc.snapshot(self.runtime_actor,'input',{'x':1})
        self.assertEqual(self.arc.execute(self.runtime_actor,self.propose().decision_id).semantic_status,'verified')
    def test_write_approval_bound_and_revoked(self):
        d=self.propose('write')
        with self.assertRaises(PermissionError):self.arc.execute(self.runtime_actor,d.decision_id)
        self.arc.approve(self.operator,d.decision_id);self.auth.revoke(self.operator)
        with self.assertRaisesRegex(PermissionError,'revoked'):self.arc.execute(self.runtime_actor,d.decision_id)
        self.assertEqual(self.effects,[])
    def test_argument_tampering(self):
        d=self.propose('write');self.arc.approve(self.operator,d.decision_id)
        with self.engine._db() as con:con.execute('UPDATE arc_decisions SET arguments=? WHERE id=?',(json.dumps({'x':9}),d.decision_id))
        with self.assertRaisesRegex(ValueError,'tampered'):self.arc.execute(self.runtime_actor,d.decision_id)
    def test_direct_bypass_denied(self):
        with self.assertRaises(PermissionError):self.engine.execute(self.runtime_actor,AgentTask('direct','read',{'x':1}))
        self.assertEqual(self.effects,[])
    def test_duplicate_and_concurrent_dispatch_one_effect(self):
        d=self.propose();self.assertEqual(self.propose().decision_id,d.decision_id)
        def run(_):
            try:return self.arc.execute(self.runtime_actor,d.decision_id)
            except RuntimeError:return None
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,range(2)))
        self.assertEqual(len(self.effects),1)
    def test_uncertain_write_never_replayed(self):
        self.failure=True;d=self.propose('write');self.arc.approve(self.operator,d.decision_id)
        out=self.arc.execute(self.runtime_actor,d.decision_id);self.assertEqual(out.retry_classification,'reconcile_required')
        self.arc.execute(self.runtime_actor,d.decision_id)
        with self.assertRaises(RuntimeError):self.propose(arguments={'x':2})
        self.assertEqual(len(self.effects),1)
        self.arc.reconcile(self.operator,d.decision_id,observed_status='failed',review_ref='external-status-1')
    def test_cancel(self):
        d=self.propose();self.arc.cancel(self.runtime_actor,d.decision_id)
        with self.assertRaises(PermissionError):self.arc.execute(self.runtime_actor,d.decision_id)
        self.assertEqual(self.effects,[])
    def test_restart_intent_never_replayed(self):
        d=self.propose()
        with self.engine._db() as con:con.execute("UPDATE arc_decisions SET status='executing' WHERE id=?",(d.decision_id,))
        with self.assertRaises(RuntimeError):self.arc.execute(self.runtime_actor,d.decision_id)
        self.assertEqual(self.effects,[])
    def test_bounded_decisions_and_no_progress(self):
        d=self.propose()
        with self.assertRaisesRegex(RuntimeError,'no-progress'):self.propose(parent_decision_id=d.decision_id)
        for x in range(2,6):self.propose(arguments={'x':x})
        with self.assertRaisesRegex(RuntimeError,'budget'):self.propose(arguments={'x':6})
    def test_provider_invalid_and_invented_evidence(self):
        calls=[]
        def provider(request):calls.append(request);return '{invalid'
        with self.assertRaises(ValueError):self.arc.generate(self.runtime_actor,provider=provider,task_id='task',evidence_refs=[self.ref])
        self.assertEqual(len(calls),2);self.assertEqual(self.effects,[])
        bad={'tool':'read','arguments':{'x':1},'goal':'goal','completion_criteria':['done'],'evidence_ids':['invented']}
        with self.assertRaises(ValueError):self.arc.generate(self.runtime_actor,provider=lambda r:bad,task_id='task',evidence_refs=[self.ref])
    def test_valid_provider_reaches_dispatch(self):
        data={'tool':'read','arguments':{'x':1},'goal':'goal','completion_criteria':['done'],'evidence_ids':['input']}
        d=self.arc.generate(self.runtime_actor,provider=lambda r:data,task_id='task',evidence_refs=[self.ref]);self.arc.execute(self.runtime_actor,d.decision_id)
        self.assertEqual(len(self.effects),1)
    def test_review_scope_expiry_retraction_deletion(self):
        d=self.propose();self.arc.execute(self.runtime_actor,d.decision_id)
        self.assertEqual(self.arc.memories(self.runtime_actor,domain='nonclinical'),[])
        self.arc.review(self.operator,d.decision_id,label='accepted',expires_in=10)
        self.assertEqual(len(self.arc.memories(self.runtime_actor,domain='nonclinical')),1)
        self.assertEqual(self.arc.memories(self.runtime_actor,domain='other'),[])
        self.arc.retract(self.operator,d.decision_id);self.assertEqual(self.arc.memories(self.runtime_actor,domain='nonclinical'),[])
        self.arc.review(self.operator,d.decision_id,label='accepted',expires_in=10);self.now+=11
        self.assertEqual(self.arc.memories(self.runtime_actor,domain='nonclinical'),[])
        self.arc.delete_memory(self.operator,d.decision_id)
        with self.engine._db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM arc_memory').fetchone()[0],0)
    def test_modes_durable_shadow_no_effects(self):
        d=self.propose();self.arc.set_mode(self.operator,'read','shadow')
        self.assertEqual(self.arc.execute(self.runtime_actor,d.decision_id)['status'],'shadow');self.assertEqual(self.effects,[])
        with self.assertRaises(PermissionError):self.engine.execute(self.runtime_actor,AgentTask('raw','read',{'x':1}))
    def test_evidence_hash_binding(self):
        self.arc.tools['read']=ToolSpec('read',lambda a:True,lambda a,b:{'done':True},evidence_bindings=lambda a,refs:refs[0]['reference_to_redacted_or_protected_content']=='sha256:'+digest(a))
        with self.assertRaisesRegex(ValueError,'match immutable'):self.propose(arguments={'x':9})
    def test_contract_bad_version(self):
        raw=self.ref.to_dict();raw['schema_version']='future'
        with self.assertRaises(ValueError):EvidenceRef(**raw)
    def test_reopened_bare_dispatcher_fails_closed(self):
        self.propose()
        reopened=GovernedLearning(self.engine.path,authority=self.auth,strategies=[RegisteredStrategy(k,k,lambda a:a) for k in ('read','write')],judge=lambda *a:True,contract_revision='arc-test',baseline_routes={'read':'read','write':'write'})
        with self.assertRaisesRegex(PermissionError,'persisted ARC'):reopened.execute(self.runtime_actor,AgentTask('raw','read',{'x':1}))
    def test_expired_approval_rejected(self):
        d=self.propose('write');self.arc.approve(self.operator,d.decision_id,valid_for=1);self.now+=2
        with self.assertRaises(PermissionError):self.arc.execute(self.runtime_actor,d.decision_id)
    def test_partial_outcome(self):
        self.arc.tools['read']=ToolSpec('read',lambda a:True,lambda v,a:{'one':True,'two':False})
        d=self.arc.propose(self.runtime_actor,'partial','read',{'x':1},[self.ref],'goal',['one','two'])
        self.assertEqual(self.arc.execute(self.runtime_actor,d.decision_id).semantic_status,'partial')
    def test_readback_bounded_to_two_retries(self):
        calls=[]
        def verify(result,args):calls.append(1);raise TimeoutError()
        self.arc.tools['read']=ToolSpec('read',lambda a:True,verify)
        self.assertEqual(self.arc.execute(self.runtime_actor,self.propose().decision_id).semantic_status,'unverifiable')
        self.assertEqual(len(calls),3);self.assertEqual(len(self.effects),1)
    def test_cancellation_during_effect_requires_reconciliation(self):
        d=self.propose('write');self.arc.approve(self.operator,d.decision_id)
        def effect(args):self.arc.cancel(self.operator,d.decision_id);return {'done':True}
        self.engine._registry[('write','write')]=effect
        outcome=self.arc.execute(self.runtime_actor,d.decision_id)
        self.assertEqual(outcome.semantic_status,'unverifiable');self.assertEqual(self.arc.inspect(self.runtime_actor,d.decision_id)['decision']['status'],'uncertain')
    def test_redacted_rejection_metrics(self):
        with self.assertRaises(ValueError):self.propose(tool='unknown')
        with self.engine._db() as con:
            events=con.execute("SELECT event,details FROM gl_events WHERE event='arc_validation_rejection'").fetchall()
        self.assertEqual(len(events),1);self.assertNotIn('arguments',events[0]['details'])
    def test_legacy_shadow_and_training_cannot_bypass(self):
        from nerve_awim.shadow_learning_v21 import ShadowLearning
        trainer=self.auth.issue('tenant','agent','trainer')
        shadow=ShadowLearning(self.engine,runtime=self.runtime_actor,trainer=trainer)
        task=AgentTask('legacy','read',{'x':1})
        with self.assertRaises(PermissionError):shadow.execute(task)
        with self.assertRaises(PermissionError):self.engine.learn_from_task(trainer,task)
        self.assertEqual(self.effects,[])
    def test_off_context_preserves_legacy_flow(self):
        self.arc.set_mode(self.operator,'read','off')
        self.assertEqual(self.engine.execute(self.runtime_actor,AgentTask('raw','read',{'x':1}))['value'],{'done':True})
    def test_readback_expiry_after_callback_rejects_success(self):
        calls=[]
        def verify(result,args):
            calls.append(1);self.now+=301
            return {'done':True}
        self.arc.tools['read']=ToolSpec('read',lambda a:True,verify)
        out=self.arc.execute(self.runtime_actor,self.propose().decision_id)
        self.assertEqual(out.semantic_status,'unverifiable');self.assertEqual(len(calls),1)
    def test_retry_backoff_cannot_cross_deadline(self):
        calls=[];pauses=[]
        def verify(result,args):calls.append(1);raise TimeoutError()
        def sleeper(delay):pauses.append(delay);self.now+=delay
        self.arc.sleeper=sleeper
        self.arc.tools['read']=ToolSpec('read',lambda a:True,verify)
        out=self.arc.execute(self.runtime_actor,self.propose(expires_in=.005).decision_id)
        self.assertEqual(out.semantic_status,'unverifiable');self.assertEqual(len(calls),1)
        self.assertEqual(len(pauses),1);self.assertLessEqual(pauses[0],.005)
    def test_retry_backoff_is_bounded(self):
        calls=[];pauses=[]
        def verify(result,args):calls.append(1);raise TimeoutError()
        self.arc.sleeper=pauses.append
        self.arc.tools['read']=ToolSpec('read',lambda a:True,verify)
        self.arc.execute(self.runtime_actor,self.propose().decision_id)
        self.assertEqual(len(calls),3);self.assertEqual(pauses,[.01,.02])
    def test_review_references_reject_free_text(self):
        d=self.propose();self.arc.execute(self.runtime_actor,d.decision_id)
        with self.assertRaises(ValueError):self.arc.review(self.operator,d.decision_id,label='accepted',provenance='Sensitive free text')
        with self.assertRaises(ValueError):self.arc.reconcile(self.operator,d.decision_id,observed_status='failed',review_ref='Sensitive free text')
