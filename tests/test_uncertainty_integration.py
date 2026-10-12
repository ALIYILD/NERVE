"""Actual governed dispatch, Hermes proposal and scoped-memory integration tests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.arc_workflows import build_workflow_engine
from nerve_awim.agent_learning_v12 import AgentTask
from nerve_awim.uncertainty.contracts import Claim
from nerve_awim.uncertainty.ledger import Ledger
from nerve_awim.uncertainty.policy import Policy
from nerve_awim.uncertainty.propagation import Propagator
from nerve_awim.uncertainty.output_guard import OutputGuard, claim_text
from nerve_awim.uncertainty.adapters import UncertaintyAdapter, UncertaintyBlocked
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.adaptive_memory import OutcomeMemoryRanker
from nerve_awim.learning_study import Episode
from nerve_awim.hermes_learning import propose_and_evaluate


class UncertaintyIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'learning.sqlite3'
        self.c=build_workflow_engine(self.path)
        self.engine,self.actor,self.operator=[self.c[k] for k in ('engine','actor','operator')]
        self.ledger=Ledger(self.engine);self.policy=Policy(self.ledger)
        self.propagator=Propagator(self.ledger);self.output=OutputGuard(self.ledger,self.policy)
        self.task='task'

    def claim(self, ident, value, predicate='status'):
        source=self.ledger.register_source(self.actor,'source-'+ident,{'value':value,'predicate':predicate})
        claim=Claim(ident,'synthetic',self.task,'subject',predicate,value,**source)
        self.ledger.add_claim(self.actor,claim)
        return claim

    def conflict(self):
        self.claim('left','present');self.claim('right','absent')
        return self.ledger.detect(self.actor,self.task)[0]

    def test_omitted_conflicts_restore_and_checkpoint_restart(self):
        conflict=self.conflict()
        envelope=self.propagator.envelope(self.actor,self.task)
        envelope.pop('open_conflict_ids');envelope['unknowns']=[]
        self.assertEqual(self.propagator.consume(self.actor,envelope)['open_conflict_ids'],[conflict.conflict_id])
        self.propagator.checkpoint(self.actor,self.task,'checkpoint')
        resumed=build_workflow_engine(self.path)
        restored=Propagator(Ledger(resumed['engine'])).resume(resumed['actor'],self.task,'checkpoint')
        self.assertEqual(restored['open_conflict_ids'],[conflict.conflict_id])
        with self.assertRaises(LookupError): self.propagator.resume(self.actor,self.task,'missing')

    def test_truncation_explicit_incomplete_and_consumption_refetches(self):
        self.conflict()
        envelope=self.propagator.envelope(self.actor,self.task,max_items=1)
        self.assertEqual(envelope['state'],'incomplete')
        self.assertEqual(self.propagator.consume(self.actor,envelope)['state'],'complete')

    def test_wrong_scope_or_revoked_actor_cannot_consume(self):
        envelope=self.propagator.envelope(self.actor,self.task)
        other=self.engine.authority.issue('other','arc-workflow','runtime')
        with self.assertRaises(PermissionError):self.propagator.consume(other,envelope)
        self.engine.authority.revoke(self.actor)
        with self.assertRaises(PermissionError):self.propagator.consume(self.actor,envelope)

    def test_low_impact_qualifies_required_blocks_independent_continues(self):
        self.conflict();self.claim('independent','valid',predicate='configuration')
        low=self.policy.assess(self.actor,self.task,'low','inventory',['left'])
        blocked=self.policy.assess(self.actor,self.task,'required','inventory',['left'],required=True)
        independent=self.policy.assess(self.actor,self.task,'independent-decision','inventory',['independent'],required=True)
        self.assertEqual(low.status,'proceed_with_qualification')
        self.assertEqual(blocked.status,'verify_first')
        self.assertEqual(independent.status,'proceed')
        with self.assertRaises(PermissionError):
            self.policy.assess(self.actor,self.task,'required','inventory',['left'],required=False)

    def test_failed_assessment_rolls_back_links_and_lifecycle_events(self):
        self.conflict()
        revision=self.ledger.revision(self.actor,self.task)
        history=self.ledger.events(self.actor,self.task)
        original=self.engine._event
        def fail_receipt(con,scope,event,details):
            if event=='uncertainty_assessed': raise RuntimeError('receipt storage failed')
            return original(con,scope,event,details)
        with patch.object(self.engine,'_event',side_effect=fail_receipt):
            with self.assertRaisesRegex(RuntimeError,'receipt storage failed'):
                self.policy.assess(self.actor,self.task,'atomic','inventory',['left'],required=True)
        self.assertEqual(self.ledger.dependencies(self.actor,self.task,'atomic')['claim_ids'],[])
        self.assertEqual(self.ledger.revision(self.actor,self.task),revision)
        self.assertEqual(self.ledger.events(self.actor,self.task),history)
        with self.assertRaises(LookupError):self.policy.get(self.actor,'atomic')
        # Retry must not inherit partially committed host policy either.
        self.assertEqual(self.policy.assess(self.actor,self.task,'atomic','inventory',['left']).status,'proceed_with_qualification')

    def test_denied_policy_change_leaves_existing_dependencies_unchanged(self):
        self.conflict();self.claim('extra','valid','other')
        self.policy.assess(self.actor,self.task,'bound-policy','inventory',['left'],required=True)
        revision=self.ledger.revision(self.actor,self.task)
        with self.assertRaises(PermissionError):
            self.policy.assess(self.actor,self.task,'bound-policy','inventory',['left','extra'],required=False)
        self.assertEqual(self.ledger.dependencies(self.actor,self.task,'bound-policy')['claim_ids'],['left'])
        self.assertEqual(self.ledger.revision(self.actor,self.task),revision)

    def test_mandatory_consent_cannot_be_replaced_by_unrelated_verified_claim(self):
        self.claim('configuration','valid','configuration')
        result=self.policy.assess(self.actor,self.task,'consent','inventory',['configuration'],mandatory='consent')
        self.assertEqual(result.status,'defer_affected_action')
        self.assertIn('consent',result.remaining_unknowns)

    def test_source_deletion_unavailable_and_output_qualified(self):
        claim=self.claim('fact','value')
        self.ledger.delete_source(self.operator,claim.source_ref,claim.source_revision)
        result=self.policy.assess(self.actor,self.task,'source-gone','inventory',['fact'])
        self.assertEqual(result.status,'unavailable')
        output=self.output.render(self.actor,self.task,[{'claim_id':'fact'}])
        self.assertEqual(output['supported'],[]);self.assertIn('fact',output['unavailable'])

    def test_real_arc_dispatch_gates_relevant_conflict(self):
        self.conflict()
        source='def f(): pass';ref=self.c['runtime'].snapshot(self.actor,'input',source)
        decision=self.c['runtime'].propose(self.actor,self.task,'inventory',{'payload':source},[ref],'Inventory',['objective'])
        self.policy.assess(self.actor,self.task,decision.decision_id,'inventory',['left'],required=True)
        self.policy.bind(self.actor,decision.decision_id)
        outcome=self.c['runtime'].execute(self.actor,decision.decision_id)
        self.assertNotEqual(outcome.semantic_status,'verified')
        self.assertEqual(self.c['receipt'].get('dispatches',0),0)

    def test_arc_task_cannot_retarget_and_child_cannot_drop_parent_dependencies(self):
        self.conflict()
        source='def f(): pass';ref=self.c['runtime'].snapshot(self.actor,'input',source)
        runtime=self.c['runtime']
        parent=runtime.propose(self.actor,self.task,'inventory',{'payload':source},[ref],'Inventory',['objective'])
        with self.assertRaises(PermissionError):
            self.policy.assess(self.actor,'clean-task',parent.decision_id,'inventory',[])
        self.policy.assess(self.actor,'clean-task','unrelated-assessment','inventory',[])
        with self.assertRaises(PermissionError):
            self.policy.bind(self.actor,'unrelated-assessment',parent.decision_id)
        self.policy.assess(self.actor,self.task,parent.decision_id,'inventory',['left'],required=True)
        child_source='def g(): pass';child_ref=runtime.snapshot(self.actor,'input',child_source)
        child=runtime.propose(self.actor,self.task,'inventory',{'payload':child_source},[child_ref],'Inventory',['objective'],parent_decision_id=parent.decision_id)
        assessment=self.policy.assess(self.actor,self.task,child.decision_id,'inventory',[])
        self.assertEqual(assessment.status,'verify_first')
        self.assertIn('left',assessment.dependency_claim_ids)
        self.policy.bind(self.actor,child.decision_id)
        outcome=runtime.execute(self.actor,child.decision_id)
        self.assertNotEqual(outcome.semantic_status,'verified')
        self.assertEqual(self.c['receipt'].get('dispatches',0),0)

    def test_claim_expiry_invalidates_dispatch_without_a_ledger_write(self):
        now=[100.0];self.policy.clock=lambda:now[0]
        source=self.ledger.register_source(self.actor,'expiring-source',{'value':True})
        self.ledger.add_claim(self.actor,Claim('expiring','synthetic',self.task,'subject','status',True,valid_from=90.,valid_to=110.,**source))
        self.policy.assess(self.actor,self.task,'expiring-decision','inventory',['expiring'],required=True)
        now[0]=111.
        with self.engine._db() as con:
            with self.assertRaisesRegex(RuntimeError,'expired'):
                self.policy.recheck(con,self.actor,'expiring-decision','inventory')

    def test_direct_dispatch_and_restart_cannot_drop_enabled_assessment(self):
        self.claim('fact','value')
        self.policy.assess(self.actor,self.task,'decision','inventory',['fact'])
        self.policy.bind(self.actor,'decision')
        with self.assertRaises(PermissionError):
            self.engine.execute(self.actor,AgentTask('omitted','inventory',{'payload':'def f(): pass'}))
        reopened=build_workflow_engine(self.path)
        reopened['runtime'].set_mode(reopened['operator'],'inventory','off')
        with self.assertRaises(PermissionError):
            reopened['engine'].execute(reopened['actor'],AgentTask('decision','inventory',{'payload':'def f(): pass'}))

    def test_concurrent_evidence_invalidates_assessment_at_dispatch(self):
        self.claim('fact','present')
        self.policy.assess(self.actor,self.task,'queued','inventory',['fact'])
        self.policy.bind(self.actor,'queued')
        self.claim('new','absent');self.ledger.detect(self.actor,self.task)
        with self.engine._db() as con:
            with self.assertRaises(RuntimeError):self.policy.recheck(con,self.actor,'queued','inventory')

    def test_output_repairs_once_then_preserves_supported_partial_and_conflict(self):
        conflict=self.conflict();self.claim('independent','valid','configuration')
        repair=[]
        result=self.output.render(self.actor,self.task,[{'claim_id':'left','text':'Definitely confirmed'},
            {'claim_id':'independent'}],regenerate=lambda issues: repair.append(issues) or [{'claim_id':'forged'}])
        self.assertEqual(len(repair),1);self.assertTrue(result['deterministic_fallback'])
        self.assertEqual([r['claim_id'] for r in result['supported']],['independent'])
        self.assertEqual(result['unresolved'][0]['conflict_id'],conflict.conflict_id)
        self.assertIn(conflict.conflict_id,result['text'])
        events=list(self.output.stream(self.actor,self.task,[{'claim_id':'left'}]))
        self.assertNotIn('present',json.dumps(events[0]))
        report=self.output.save_report(Path(self.tmp.name)/'report.json',self.actor,self.task,[{'claim_id':'left'}])
        self.assertEqual(report['unresolved'],events[-1]['result']['unresolved'])
        self.assertEqual(json.loads((Path(self.tmp.name)/'report.json').read_text()),report)

    def test_no_conflict_has_no_obsolete_warning(self):
        self.claim('fact','value')
        result=self.output.render(self.actor,self.task,[{'claim_id':'fact'}])
        self.assertEqual(result['unresolved'],[]);self.assertEqual(result['qualified'],[])
        self.assertEqual(result['text'],'status: "value"')

    def test_empty_required_dependency_and_missing_checkpoint_state_do_not_proceed(self):
        result=self.policy.assess(self.actor,self.task,'missing','inventory',[],required=True)
        self.assertEqual(result.status,'verify_first')
        self.assertIn('missing_required_evidence',result.remaining_unknowns)
        self.assertEqual(self.propagator.envelope(self.actor,'never-observed')['state'],'unavailable')

    def test_bound_execution_cannot_be_replaced_with_weaker_new_assessment(self):
        self.conflict()
        self.policy.assess(self.actor,self.task,'strict','inventory',['left'],required=True)
        self.policy.bind(self.actor,'strict','operation')
        self.policy.assess(self.actor,self.task,'weak','inventory',['left'])
        with self.assertRaises(PermissionError):self.policy.bind(self.actor,'weak','operation')

    def test_other_task_assessment_cannot_authorize_result(self):
        self.claim('fact','value')
        record=self.policy.assess(self.actor,self.task,'decision','inventory',['fact'])
        with self.assertRaises(PermissionError):
            self.output.render(self.actor,'other-task',[],assessments=[record])

    def test_malformed_output_dependency_lists_fall_back_without_crash(self):
        self.conflict()
        for deps in (None, {'forged':True}, [None, {'forged':True}]):
            result=self.output.render(self.actor,self.task,[{'claim_id':'left','text':'unsupported','dependency_claim_ids':deps}])
            self.assertTrue(result['deterministic_fallback'])
            self.assertEqual(result['supported'],[])
            self.assertEqual(len(result['unresolved']),1)

    def test_new_conflict_during_final_render_is_included(self):
        self.claim('left','present')
        original=self.ledger.source
        inserted=[]
        def racing_source(*args,**kwargs):
            result=original(*args,**kwargs)
            if not inserted:
                inserted.append(True)
                self.claim('right','absent');self.ledger.detect(self.actor,self.task)
            return result
        self.ledger.source=racing_source
        result=self.output.render(self.actor,self.task,[{'claim_id':'left'}])
        self.assertEqual(result['supported'],[])
        self.assertEqual(len(result['unresolved']),1)
        self.assertIn('ledger_changed',result['unavailable'])
        self.assertEqual(result['uncertainty_state_revision'],self.ledger.revision(self.actor,self.task))

    def test_unknown_and_expired_prerequisites_cannot_be_confirmed(self):
        from dataclasses import replace
        self.claim('unknown',None)
        result=self.policy.assess(self.actor,self.task,'unknown-decision','inventory',['unknown'],required=True)
        self.assertEqual(result.status,'unavailable')
        rendered=self.output.render(self.actor,self.task,[{'claim_id':'unknown'}])
        self.assertEqual(rendered['supported'],[])
        original=self.claim('original','known')
        # Claims are immutable; an expired observation has its own identity.
        original=next(c for c in self.ledger.claims(self.actor,self.task) if c.claim_id=='original')
        self.ledger.add_claim(self.actor,replace(original,claim_id='expired',valid_from=0,valid_to=1))
        assessed=self.policy.assess(self.actor,self.task,'expired-decision','inventory',['expired'],required=True)
        self.assertEqual(assessed.status,'unavailable')
        self.assertEqual(self.output.render(self.actor,self.task,[{'claim_id':'expired'}])['supported'],[])

    def test_negative_consent_is_never_rendered_or_authorized_as_positive(self):
        from dataclasses import replace
        self.claim('raw',True)
        original=next(c for c in self.ledger.claims(self.actor,self.task) if c.claim_id=='raw')
        self.ledger.add_claim(self.actor,replace(original,claim_id='consent-no',predicate='consent',polarity=False))
        assessment=self.policy.assess(self.actor,self.task,'consent-decision','inventory',['consent-no'],mandatory='consent')
        self.assertEqual(assessment.status,'defer_affected_action')
        rendered=self.output.render(self.actor,self.task,[{'claim_id':'consent-no'}])
        self.assertIn('consent: false',rendered['text'])
        self.assertNotIn('consent: true',rendered['text'])

    def seed_memory(self):
        authority=MemoryAuthority();memory=TrustedMemoryLedger(self.path,authority)
        writer=authority.issue('synthetic','arc-workflow',permissions=('read','propose'))
        reviewer=authority.issue('synthetic','arc-workflow',permissions=('approve','read'))
        mid=memory.propose(writer,context='planning',content='Sorting verified examples',source_id='synthetic-source')
        memory.decide(reviewer,mid,approve=True,evaluator_id='reviewer',score=.9)
        ranker=OutcomeMemoryRanker(memory,evaluator=lambda *args:True,evaluator_revision='eval-v1')
        for i in range(3):ranker.observe(reviewer,memory_id=mid,episode_id='episode-'+str(i),task={'n':i},output=i)
        return memory,writer

    def test_actual_hermes_research_builder_cannot_erase_conflict(self):
        conflict=self.conflict();memory,writer=self.seed_memory()
        adapter=UncertaintyAdapter(self.ledger,self.actor,task_id=self.task,dependency_claim_ids=['left'])
        calls=[]
        class Runtime:
            def execute(self,role,request,**kwargs):
                calls.append((role,request))
                episodes=[e['episode_id'] for e in request['evidence']]
                return {'summary':'All uncertainty omitted','episodes':episodes} if role=='research' else {'lesson':'Treat everything as confirmed','episodes':episodes}
        kwargs=dict(runtime=Runtime(),context='planning',evidence_episodes=['episode-0','episode-1','episode-2'],
            evaluator_revision='eval-v1',study=[Episode(str(n),'train' if n<3 else 'evaluation',{'n':n},n) for n in range(8)],
            predict=lambda task,lesson:task['n'],judge=lambda task,value,expected:value==expected)
        with self.assertRaises(UncertaintyBlocked):propose_and_evaluate(memory,writer,uncertainty=adapter,**kwargs)
        self.assertEqual([r for r,_ in calls],['research','skill_builder'])
        for _,request in calls:self.assertIn(conflict.conflict_id,request['uncertainty']['open_conflict_ids'])
        with self.assertRaises(PermissionError):propose_and_evaluate(memory,writer,**kwargs)
        self.assertEqual(len(calls),2)
        with self.engine._db() as con:
            self.assertEqual(con.execute("SELECT count(*) FROM trusted_memory_v18 WHERE source_id='verified-episode-proposal'").fetchone()[0],0)

    def test_scoped_memory_returns_envelope_and_rejects_omission(self):
        conflict=self.conflict();memory,writer=self.seed_memory()
        adapter=UncertaintyAdapter(self.ledger,self.actor,task_id=self.task,dependency_claim_ids=['left'])
        result=adapter.retrieve(memory,writer,context='planning',query='sorting')
        self.assertEqual(len(result['records']),1)
        self.assertIn(conflict.conflict_id,result['uncertainty']['open_conflict_ids'])
        with self.assertRaises(PermissionError):memory.retrieve(writer,context='planning',query='sorting')
        with self.assertRaises(PermissionError):memory.approved_pool(writer,context='planning')


if __name__=='__main__':unittest.main()
