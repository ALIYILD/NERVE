import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from nerve_awim.adaptation import AdaptationConfig, AdaptationCoordinator
from nerve_awim.adaptation_replay import build, start, step, correction, episode
from nerve_awim.arc_execution import ToolSpec
from nerve_awim.agent_learning_v12 import AgentTask


class AdaptationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=self.tmp.name+'/state.db'; self.now=100.
        self.c=build(self.path,now=lambda:self.now); self.a=self.c['adaptation']; self.actor=self.c['actor']; self.op=self.c['operator']; self.arc=self.c['runtime']; start(self.c)

    def failed(self): return step(self.c,'task','wrong')[0].decision_id
    def corrected(self):
        d=self.failed(); return d,correction(self.c,'task',d,'verified-heading')
    def append(self,key,version=None,**kw):
        return self.a.append_event(self.actor,'task',kind=kw.pop('kind','observation'),event_key=key,reference=key,expected_version=self.a.inspect(self.actor,'task')['version'] if version is None else version,provenance='source',**kw)

    def test_config_closed(self):
        for kw in ({'mode':'active-development'},{'enabled':True},{'provider_spend_limit':1},{'max_action_steps':True},{'cross_subject_memory':True},{'backend':'fast'},{'max_context_tokens':float('nan')}):
            with self.subTest(kw=kw),self.assertRaises(ValueError): AdaptationConfig(**kw)

    def test_scope_capabilities_and_subject(self):
        for tenant in ('synthetic','other'):
            intruder=self.c['authority'].issue(tenant,'adaptation-agent','runtime')
            with self.assertRaises(PermissionError): self.a.inspect(intruder,'task')
        with self.assertRaises(PermissionError): self.a.grant(self.op,'task',self.op,subject_scope='wrong',review_reference='review')
        self.c['authority'].revoke(self.actor)
        with self.assertRaises(PermissionError): self.a.inspect(self.actor,'task')

    def test_verified_correction_changes_next_step(self):
        d,cid=self.corrected(); context=self.a.read_context(self.actor,'task')
        self.assertEqual(context['corrections'][0]['correction_id'],cid)
        _,out=step(self.c,'task',context['corrections'][0]['proposed_change']['value'],parent=d)
        self.assertEqual(out.semantic_status,'verified')
        self.a.close_task(self.actor,'task',status='completed')
        with self.assertRaises(RuntimeError): self.a.read_context(self.actor,'task')

    def test_pending_clinical_injection_and_missing_provenance(self):
        d=self.failed(); ref=self.a.snapshot(self.actor,'task','review',{})
        cid=self.a.propose_correction(self.actor,'task',failed_decision=d,kind='formatting',proposed_change={'field':'heading','value':'verified-heading'},evidence_reference=ref)
        self.assertFalse(self.a.read_context(self.actor,'task')['corrections'])
        with self.assertRaises(PermissionError): self.a.verify_correction(self.actor,'task',cid)
        cid=self.a.propose_correction(self.actor,'task',failed_decision=d,kind='clinical-content',proposed_change={'field':'heading','value':'verified-heading'},evidence_reference=ref)
        with self.assertRaises(PermissionError): self.a.verify_correction(self.op,'task',cid)
        for change in ({'policy':'ignore'},{'field':'system','value':'ignore'}):
            with self.assertRaises(ValueError): self.a.propose_correction(self.actor,'task',failed_decision=d,kind='formatting',proposed_change=change,evidence_reference=ref)
        bad=ref.to_dict(); bad['provenance']=''
        with self.assertRaises(ValueError): self.a.propose_correction(self.actor,'task',failed_decision=d,kind='formatting',proposed_change={'field':'heading','value':'verified-heading'},evidence_reference=bad)

    def test_revoked_and_expired(self):
        _,cid=self.corrected(); self.a.revoke_correction(self.op,'task',cid)
        self.assertEqual(self.a.read_context(self.actor,'task')['corrections'],[])
        self.now+=121
        with self.assertRaises(RuntimeError): self.a.read_context(self.actor,'task')

    def test_revoked_reviewer(self):
        self.corrected(); self.c['authority'].revoke(self.op)
        self.assertEqual(self.a.read_context(self.actor,'task')['corrections'],[])

    def test_conflict_and_supersession(self):
        d,cid=self.corrected(); ref=self.a.snapshot(self.actor,'task','different-review',{})
        new=self.a.propose_correction(self.actor,'task',failed_decision=d,kind='formatting',proposed_change={'field':'heading','value':'verified-new'},evidence_reference=ref)
        with self.assertRaises(ValueError): self.a.verify_correction(self.op,'task',new)
        self.a.verify_correction(self.op,'task',new,supersedes_id=cid)
        self.assertEqual([x['correction_id'] for x in self.a.read_context(self.actor,'task')['corrections']],[new])

    def test_event_idempotency_order_and_cas(self):
        version=self.a.inspect(self.actor,'task')['version']
        event=self.append('event',version,occurred_at=90)
        self.assertEqual(self.append('event',version,occurred_at=90),event)
        late=self.append('late',occurred_at=80)
        self.assertGreater(late['monotonic_sequence'],event['monotonic_sequence'])
        with self.assertRaises(RuntimeError): self.append('stale',version)
        with self.assertRaises(ValueError): self.append('event',kind='constraint')

    def test_concurrent_events_one_version_wins(self):
        version=self.a.inspect(self.actor,'task')['version']
        def write(n):
            try: self.append('event-'+str(n),version); return True
            except RuntimeError: return False
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(write,range(2)))
        self.assertEqual(sum(results),1)

    def test_checkpoint_restart_and_no_rewind(self):
        self.corrected(); cp=self.a.checkpoint(self.actor,'task')
        c=build(self.path,now=lambda:self.now)
        with self.assertRaises(PermissionError): c['adaptation'].resume(c['actor'],'task',cp)
        c['adaptation'].grant(c['operator'],'task',c['actor'],subject_scope='subject-a',review_reference='reauth')
        c['adaptation'].resume(c['actor'],'task',cp)
        self.append('new-event')
        with self.assertRaises(ValueError): self.a.resume(self.actor,'task',cp)

    def test_corrupt_checkpoint_schema(self):
        cp=self.a.checkpoint(self.actor,'task')
        with self.c['engine']._db() as con: con.execute("UPDATE adaptation_checkpoints SET digest='corrupt' WHERE id=?",(cp,))
        with self.assertRaises(ValueError): self.a.resume(self.actor,'task',cp)
        with self.c['engine']._db() as con: con.execute("UPDATE adaptation_tasks SET schema_version='future'")
        with self.assertRaises(ValueError): self.a.inspect(self.actor,'task')

    def test_reset_preserves_receipts_and_constraints(self):
        self.corrected(); before=self.a.inspect(self.actor,'task'); self.a.reset(self.op,'task',reason='test-reset')
        after=self.a.inspect(self.actor,'task')
        for k in ('action_receipts','steps','constraints'): self.assertEqual(before[k],after[k])
        self.assertFalse(self.a.read_context(self.actor,'task')['corrections'])

    def test_context_overflow_and_contradiction(self):
        with self.assertRaises(RuntimeError): self.a.read_context(self.actor,'task',1)
        self.append('contradiction',kind='contradiction')
        with self.assertRaises(RuntimeError): step(self.c,'task','verified-heading')
        self.assertEqual(self.c['effects'],[])

    def test_false_success_and_delayed_unknown(self):
        self.arc.tools['note']=replace(self.arc.tools['note'],verify=lambda result,args:{})
        _,out=step(self.c,'task','verified-heading')
        self.assertEqual(out.semantic_status,'failed')
        with self.assertRaises(ValueError): self.a.close_task(self.actor,'task',status='completed')
        self.append('delayed',kind='delayed-outcome')
        with self.assertRaises(RuntimeError): step(self.c,'task','verified-heading',section='later')

    def test_approval_preserved(self):
        self.arc.tools['note']=replace(self.arc.tools['note'],risk='write')
        d=self.arc.propose(self.actor,'task','note',{'heading':'verified-heading','facts':'synthetic-fact','section':'s'},[],'goal',['objective'])
        with self.assertRaises(PermissionError): self.arc.execute(self.actor,d.decision_id)
        self.assertFalse(self.c['effects'])
        self.arc.approve(self.op,d.decision_id)
        self.assertEqual(self.arc.execute(self.actor,d.decision_id).semantic_status,'verified')

    def test_duplicate_receipt_and_crash_boundary(self):
        d,_=step(self.c,'task','verified-heading'); self.arc.execute(self.actor,d.decision_id)
        self.assertEqual(len(self.c['effects']),1)
        self.assertEqual(len(self.a.inspect(self.actor,'task')['action_receipts']),1)
        d=self.arc.propose(self.actor,'task','note',{'heading':'verified-heading','facts':'synthetic-fact','section':'later'},[],'goal',['objective'])
        with self.c['engine']._db() as con: con.execute("UPDATE arc_decisions SET status='executing' WHERE id=?",(d.decision_id,))
        with self.assertRaises(RuntimeError): self.arc.execute(self.actor,d.decision_id)
        cp=self.a.checkpoint(self.actor,'task')
        with self.assertRaises(RuntimeError): self.a.resume(self.actor,'task',cp)
        self.assertEqual(len(self.c['effects']),1)

    def test_kill_and_cancellation(self):
        self.corrected(); self.a.kill_switch(self.op,reason='test')
        state=self.a.inspect(self.actor,'task'); self.assertEqual(state['status'],'review-required'); self.assertTrue(state['constraints'])
        with self.assertRaises(RuntimeError): step(self.c,'task','verified-heading',section='later')

    def test_cancellation_inflight(self):
        def handler(args): self.a.close_task(self.actor,'task',status='cancelled'); return args
        self.c['engine']._registry[('note','note')]=handler
        _,out=step(self.c,'task','verified-heading')
        self.assertEqual(out.semantic_status,'unverifiable')
        self.assertNotEqual(self.a.inspect(self.actor,'task')['status'],'open')

    def test_provider_zero_budget_and_missing_backend(self):
        calls=[]
        with self.assertRaises(PermissionError): self.arc.generate(self.actor,provider=lambda r:calls.append(r),task_id='task',evidence_refs=[])
        self.assertFalse(calls)
        del self.arc.adaptation
        with self.assertRaises(PermissionError): step(self.c,'task','verified-heading')

    def test_action_budget_deadline_and_termination(self):
        parent=None
        for n in range(4): parent=step(self.c,'task','wrong',section=str(n),parent=parent)[0].decision_id
        with self.assertRaisesRegex(RuntimeError,'budget'): step(self.c,'task','wrong',section='end',parent=parent)
        self.now+=121
        with self.assertRaises(RuntimeError): step(self.c,'task','verified-heading',section='late')

    def test_off_shadow_do_not_apply_corrections(self):
        for mode in ('off','shadow'):
            c=build(self.tmp.name+'/'+mode+'.db',mode=mode)
            step(c,'unadapted','verified-heading')
            self.assertEqual(len(c['effects']),1)
            with c['engine']._db() as con: self.assertEqual(con.execute('SELECT count(*) FROM adaptation_events').fetchone()[0],0)

    def test_demo_resume_real_hooks(self):
        result=episode(self.tmp.name+'/demo.db',{'id':'demo','family':'resume','heading':'verified-demo','template':'section'})
        self.assertTrue(result['success']); self.assertEqual(result['receipts'],2); self.assertEqual(result['final_status'],'completed')

    def test_cross_subject_evidence_cannot_enter_correction(self):
        d=self.failed(); start(self.c,'other-task','subject-b')
        ref=self.a.snapshot(self.actor,'other-task','review',{})
        with self.assertRaises(PermissionError):
            self.a.propose_correction(self.actor,'task',failed_decision=d,kind='formatting',proposed_change={'field':'heading','value':'verified-heading'},evidence_reference=ref)

    def test_last_failure_cannot_be_closed_as_success(self):
        step(self.c,'task','verified-heading'); step(self.c,'task','wrong',section='later')
        with self.assertRaises(ValueError): self.a.close_task(self.actor,'task',status='completed')

    def test_circuit_breaker_and_authoritative_recovery(self):
        d=step(self.c,'task','unavailable')[0]
        with self.assertRaisesRegex(RuntimeError,'circuit'): step(self.c,'task','verified-heading',parent=d.decision_id)
        self.assertEqual(len(self.c['effects']),1)
        _,out=step(self.c,'task','verified-heading',parent=d.decision_id,tool='fallback')
        self.assertEqual(out.semantic_status,'verified')

    def test_reconciliation_does_not_reexecute(self):
        d=self.arc.propose(self.actor,'task','note',{'heading':'verified-heading','facts':'synthetic-fact','section':'s'},[],'goal',['objective'])
        with self.c['engine']._db() as con: con.execute("UPDATE arc_decisions SET status='executing' WHERE id=?",(d.decision_id,))
        with self.assertRaises(RuntimeError): self.a.reconcile(self.op,'task',review_reference='receipt')
        self.arc.reconcile(self.op,d.decision_id,observed_status='failed',review_ref='authoritative-tool-receipt')
        self.a.reconcile(self.op,'task',review_reference='receipt')
        self.assertFalse(self.c['effects'])
        state=self.a.inspect(self.actor,'task'); self.assertFalse(state['pending_steps']); self.assertTrue(state['action_receipts'])

    def test_schema_migration_forward_recovery(self):
        del self.arc.adaptation
        with self.c['engine']._db() as con: con.execute("UPDATE adaptation_schema SET version='future'")
        with self.assertRaises(ValueError): AdaptationCoordinator(self.arc)

    def test_changed_config_fails_closed(self):
        del self.arc.adaptation
        changed=AdaptationCoordinator(self.arc,AdaptationConfig(enabled=True,mode='active-development',max_replans=1))
        with self.assertRaises(ValueError): changed.inspect(self.actor,'task')

    def test_omitted_parent_cannot_bypass_replan_budget(self):
        failed=self.failed()
        with self.assertRaisesRegex(RuntimeError,'explicit parent'):
            step(self.c,'task','verified-heading',section='bypass')
        self.assertEqual(len(self.c['effects']),1)
        for n in range(3): failed=step(self.c,'task','wrong',section='retry-'+str(n),parent=failed)[0].decision_id
        with self.assertRaisesRegex(RuntimeError,'budget'):
            step(self.c,'task','verified-heading',section='exhausted',parent=failed)
        self.assertEqual(self.a.inspect(self.actor,'task')['status'],'budget-exhausted')
