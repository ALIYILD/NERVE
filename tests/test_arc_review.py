"""Independent adversarial acceptance review of ARC boundaries and release state."""
import json
from pathlib import Path
import tempfile
import unittest
from nerve_awim.agent_learning_v12 import AgentTask
from nerve_awim.arc_contracts import SCHEMA
from nerve_awim.arc_operations import ArcOperations
from nerve_awim.arc_workflows import build_workflow_engine


class ArcIndependentReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'state.sqlite3'
        self.c = build_workflow_engine(self.path, now=1000)
        self.runtime, self.actor, self.operator, self.engine = [self.c[k] for k in ('runtime','actor','operator','engine')]
        self.ops = ArcOperations(self.runtime)
        self.reviewer = self.engine.authority.issue('synthetic', 'arc-workflow', 'operator')

    def decision(self, task='task', approval=False):
        source = 'def observed(): pass'
        ref = self.runtime.snapshot(self.actor, 'input', source)
        return self.runtime.propose(self.actor, task, 'inventory', {'payload':source}, [ref], 'Inventory', ['objective'], approval_required=approval)

    def manifest(self, mode='enforce', limit=1):
        versions = dict(schema=SCHEMA, prompt='arc-v1', model='deterministic-v1',
                        policy=self.engine.contract, strategy='inventory')
        ident = self.ops.stage(self.operator, context='inventory', mode=mode, versions=versions, canary_limit=limit)
        self.ops.promote(self.reviewer, ident, review='independent-offline-review')
        return ident

    def test_cross_scope_generated_arguments_do_not_dispatch(self):
        source = 'def observed(): pass'
        ref = self.runtime.snapshot(self.actor, 'input', source)
        calls=[]
        def provider(request):
            calls.append(request)
            return {'tool':'inventory','arguments':{'payload':'def forged(): pass'},
                    'goal':'Inventory','completion_criteria':['objective'],'evidence_ids':['input'],
                    'unknowns':[],'rationale':'The secret source belongs to another tenant'}
        with self.assertRaises(ValueError):
            self.runtime.generate(self.actor, provider=provider, task_id='generated', evidence_refs=[ref])
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.c['receipt'].get('dispatches',0), 0)
        self.assertEqual(self.ops.inspect(self.operator), [])

    def test_changed_observation_invalidates_approved_arguments(self):
        decision = self.decision(approval=True)
        self.runtime.approve(self.operator, decision.decision_id)
        self.runtime.snapshot(self.actor,'input','def changed(): pass')
        with self.assertRaises(ValueError):
            self.runtime.execute(self.actor, decision.decision_id)
        self.assertEqual(self.c['receipt'].get('dispatches',0), 0)

    def test_public_dispatcher_cannot_bypass_enforced_context(self):
        with self.assertRaises(PermissionError):
            self.engine.execute(self.actor, AgentTask('direct','inventory',{'payload':'def f(): pass'}))
        self.assertEqual(self.c['receipt'].get('dispatches',0),0)

    def test_restarted_factory_preserves_shadow(self):
        self.runtime.set_mode(self.operator,'inventory','shadow')
        resumed = build_workflow_engine(self.path, now=1000)
        ref = resumed['runtime'].snapshot(resumed['actor'],'input','def f(): pass')
        decision = resumed['runtime'].propose(resumed['actor'],'resumed','inventory',{'payload':'def f(): pass'},[ref],'Inventory',['objective'])
        result = resumed['runtime'].execute(resumed['actor'], decision.decision_id)
        self.assertEqual(result['status'],'shadow')
        self.assertEqual(resumed['receipt'].get('dispatches',0),0)

    def test_cancellation_during_handler_remains_uncertain_in_audit(self):
        decision = self.decision()
        original = self.engine._registry[('inventory','inventory')]
        def cancel_during_handler(payload):
            value = original(payload)
            self.runtime.cancel(self.operator,decision.decision_id)
            return value
        self.engine._registry[('inventory','inventory')] = cancel_during_handler
        outcome = self.runtime.execute(self.actor, decision.decision_id)
        self.assertEqual(outcome.semantic_status,'unverifiable')
        self.assertEqual(self.runtime.inspect(self.actor,decision.decision_id)['decision']['status'],'uncertain')
        events = self.engine.audit(self.operator)
        event = [e for e in events if e['event']=='arc_outcome'][-1]
        self.assertEqual(event['details']['semantic_status'], outcome.semantic_status)

    def test_rejected_expired_retracted_deleted_memory_excluded(self):
        decision=self.decision()
        self.runtime.execute(self.actor,decision.decision_id)
        self.runtime.review(self.operator,decision.decision_id,label='rejected')
        self.assertEqual(self.runtime.memories(self.actor,domain='nonclinical'),[])
        self.runtime.review(self.operator,decision.decision_id,label='accepted',expires_in=1)
        self.runtime.clock=lambda:1002
        self.assertEqual(self.runtime.memories(self.actor,domain='nonclinical'),[])
        self.runtime.clock=lambda:1000
        self.runtime.retract(self.operator,decision.decision_id)
        self.assertEqual(self.runtime.memories(self.actor,domain='nonclinical'),[])
        self.runtime.delete_memory(self.operator,decision.decision_id)
        self.assertEqual(self.runtime.memories(self.actor,domain='nonclinical'),[])
        self.assertEqual(self.runtime.inspect(self.actor,decision.decision_id)['decision']['status'],'succeeded')

    def test_rollback_restores_previous_canary_constraint(self):
        first=self.manifest('enforce',limit=1)
        first_decision=self.decision('first')
        self.assertEqual(self.runtime.execute(self.actor,first_decision.decision_id).semantic_status,'verified')
        second=self.manifest('shadow',limit=1)
        self.ops.rollback(self.reviewer,second,review='restore-previous-release')
        next_decision=self.decision('next')
        outcome=self.runtime.execute(self.actor,next_decision.decision_id)
        self.assertNotEqual(outcome.semantic_status,'verified')
        self.assertEqual(self.c['receipt'].get('dispatches',0),1)

    def test_changed_governed_release_invalidates_active_manifest(self):
        self.manifest('enforce', limit=3)
        with self.engine._db() as con:
            state = self.engine._state(con, ('synthetic', 'arc-workflow'))
            con.execute("INSERT INTO gl_releases SELECT ?,tenant,agent,contract,routes,candidate FROM gl_releases WHERE id=?",
                        ('known-good-compatible', state['active']))
        self.engine.rollback(self.operator, 'known-good-compatible', expected_generation=0, reason='reviewed-test-rollback')
        decision = self.decision('release-changed')
        outcome = self.runtime.execute(self.actor, decision.decision_id)
        self.assertNotEqual(outcome.semantic_status, 'verified')
        self.assertEqual(self.c['receipt'].get('dispatches', 0), 0)

    def test_scope_and_domain_isolate_reviewed_guidance(self):
        decision = self.decision()
        self.runtime.execute(self.actor, decision.decision_id)
        self.runtime.review(self.operator, decision.decision_id, label='accepted')
        self.assertEqual(len(self.runtime.memories(self.actor, domain='nonclinical')), 1)
        self.assertEqual(self.runtime.memories(self.actor, domain='synthetic-clinical'), [])
        outsider = self.engine.authority.issue('other', 'arc-workflow', 'runtime')
        self.assertEqual(self.runtime.memories(outsider, domain='nonclinical'), [])
        with self.assertRaises(PermissionError):
            self.ops.replay(outsider, decision.decision_id)

    def test_completed_decision_cannot_be_relabelled_cancelled(self):
        decision = self.decision()
        self.runtime.execute(self.actor, decision.decision_id)
        with self.assertRaises(ValueError):
            self.runtime.cancel(self.operator, decision.decision_id)
        self.assertEqual(self.runtime.inspect(self.actor, decision.decision_id)['decision']['status'], 'succeeded')

    def test_replay_redacts_arguments_and_has_no_effect(self):
        decision=self.decision()
        self.runtime.execute(self.actor,decision.decision_id)
        before=self.c['receipt']['dispatches']
        record=self.ops.replay(self.operator,decision.decision_id)
        self.assertFalse(record['effects'])
        self.assertNotIn('def observed',json.dumps(record))
        self.assertEqual(self.c['receipt']['dispatches'],before)

    def test_clinical_enforce_release_is_not_authorized_by_synthetic_demos(self):
        versions=dict(schema=SCHEMA,prompt='p',model='m',policy=self.engine.contract,strategy='prepare-draft')
        with self.assertRaises(PermissionError):
            self.ops.stage(self.operator,context='prepare-draft',mode='enforce',versions=versions)


if __name__=='__main__': unittest.main()
