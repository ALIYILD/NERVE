"""Actual governed dispatch, Hermes proposal and scoped-memory integration tests."""
import json
from pathlib import Path
import tempfile
import unittest

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
        decision=self.c['runtime'].propose(self.actor,'arc-task','inventory',{'payload':source},[ref],'Inventory',['objective'])
        self.policy.assess(self.actor,self.task,decision.decision_id,'inventory',['left'],required=True)
        self.policy.bind(self.actor,decision.decision_id)
        outcome=self.c['runtime'].execute(self.actor,decision.decision_id)
        self.assertNotEqual(outcome.semantic_status,'verified')
        self.assertEqual(self.c['receipt'].get('dispatches',0),0)

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
