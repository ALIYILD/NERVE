"""Actual governed candidate/canary routes cannot omit opt-in uncertainty evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from nerve_awim.agent_learning_v12 import AgentTask
from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.repository_agents_v20 import CONTEXT, REPOSITORY_STRATEGIES, repository_judge
from nerve_awim.canary_learning_v23 import CanaryLearning
from nerve_awim.uncertainty.release import ReleaseEligibility
from nerve_awim.uncertainty import evaluation


class UncertaintyReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'state.sqlite3'
        self.auth=LearningAuthority();self.actors={r:self.auth.issue(evaluation._tenant(),'agent',r)
            for r in ('trainer','evaluator','operator','runtime','auditor')}
        self.engine=GovernedLearning(self.path,authority=self.auth,strategies=REPOSITORY_STRATEGIES,
            judge=repository_judge,contract_revision='release-test-v1',baseline_routes={CONTEXT:'regex-inventory'})
        self.initial=self.engine.bootstrap(self.actors['operator'])
        for n in range(3):self.engine.learn_from_task(self.actors['trainer'],self.task(n))
        self.candidate=self.engine.freeze_candidate(self.actors['trainer'])
        result=self.engine.evaluate_candidate(self.actors['evaluator'],self.candidate,[self.task(n) for n in range(3,8)])
        self.assertEqual(result['status'],'passed')
        self.gate=ReleaseEligibility(self.engine)

    @staticmethod
    def task(n):
        return AgentTask('task-'+str(n),CONTEXT,f'# synthetic {n}\ndef top_{n}():\n    def nested(): pass\n')

    def activate(self):
        return self.engine.activate(self.actors['operator'],self.candidate,expected_generation=0,reason='review')

    def receipt(self, *, tenant=None, eligible=False):
        # Explicit adversarial stored-receipt fixture, not benchmark evidence.
        _,manifest=evaluation.load_suite();revision=evaluation.code_revision();run='test-run'
        final={'run_id':run,'split':'sealed-final','revision':revision,'dataset_sha256':manifest['dataset_sha256'],
               'policy':manifest['policy'],'eligibility':{'eligible':eligible,'mode':'enforce' if eligible else 'shadow'}}
        with evaluation._db(self.path) as con:
            con.execute('INSERT INTO ue_runs VALUES(?,?,?,?,?,?,NULL,?)',
                (run,tenant or evaluation._tenant(),revision,manifest['dataset_sha256'],evaluation.digest(manifest['policy']),'complete',json.dumps(final)))
        return run

    def test_unrelated_off_scope_keeps_existing_holdout_authorization(self):
        self.assertEqual(self.activate()['generation'],1)

    def test_enabled_missing_report_blocks_real_activation_and_canary(self):
        self.gate.enable(self.actors['operator'],CONTEXT)
        with self.assertRaises(PermissionError):self.activate()
        with self.assertRaises(PermissionError):
            CanaryLearning(self.engine).start(self.actors['operator'],self.candidate,expected_generation=0,reason='review')
        self.assertEqual(self.engine.status(self.actors['operator'])['generation'],0)

    def test_host_stored_inconclusive_report_cannot_promote(self):
        run=self.receipt()
        self.gate.bind(self.actors['evaluator'],self.candidate,run)
        with self.assertRaises(PermissionError):self.activate()
        self.assertFalse(evaluation.eligibility(self.path,run)['eligible'])

    def test_forged_eligible_flag_cannot_promote(self):
        run=self.receipt(eligible=True)
        self.gate.bind(self.actors['evaluator'],self.candidate,run)
        with self.assertRaises(PermissionError):self.activate()

    def test_mutated_or_stale_bound_receipt_denied(self):
        run=self.receipt();self.gate.bind(self.actors['evaluator'],self.candidate,run)
        with self.engine._db() as con:
            row=con.execute('SELECT final FROM ue_runs WHERE id=?',(run,)).fetchone()
            final=json.loads(row['final']);final['tampered']='new'
            con.execute('UPDATE ue_runs SET final=? WHERE id=?',(json.dumps(final),run))
        with self.assertRaises(ValueError):self.activate()
        with self.engine._db() as con:con.execute("UPDATE ue_runs SET revision='stale' WHERE id=?",(run,))
        with self.assertRaises(ValueError):self.activate()

    def test_report_scope_and_binding_role_cannot_be_forged(self):
        run=self.receipt(tenant='other')
        with self.assertRaises(PermissionError):self.gate.bind(self.actors['evaluator'],self.candidate,run)
        with self.assertRaises(PermissionError):self.gate.bind(self.actors['runtime'],self.candidate,run)
        with self.assertRaises(PermissionError):self.gate.enable(self.actors['runtime'],CONTEXT)

    def test_enabling_after_canary_start_stops_candidate_traffic(self):
        canary=CanaryLearning(self.engine)
        ident=canary.start(self.actors['operator'],self.candidate,expected_generation=0,reason='review',percent=25,required_successes=5)
        self.gate.enable(self.actors['operator'],CONTEXT)
        result=canary.execute(self.actors['runtime'],ident,self.task(50))
        self.assertEqual(result['strategy'],'regex-inventory')
        self.assertEqual(canary.report(self.actors['auditor'],ident)['phase'],'stopped')

    def test_uncertainty_only_context_blocks_public_alternative_dispatch_paths(self):
        from nerve_awim.uncertainty.ledger import Ledger
        from nerve_awim.uncertainty.contracts import Claim
        from nerve_awim.uncertainty.policy import Policy
        from nerve_awim.shadow_learning_v21 import ShadowLearning
        canary=CanaryLearning(self.engine)
        ident=canary.start(self.actors['operator'],self.candidate,expected_generation=0,reason='review')
        ledger=Ledger(self.engine)
        source=ledger.register_source(self.actors['runtime'],'source',{'value':True})
        ledger.add_claim(self.actors['runtime'],Claim('claim',evaluation._tenant(),'uncertainty-task','code','valid',True,**source))
        policy=Policy(ledger)
        policy.assess(self.actors['runtime'],'uncertainty-task','bound','ast-inventory',['claim'])
        policy.bind(self.actors['runtime'],'bound')
        self.assertIsNone(getattr(self.engine,'_arc_guard',None))
        with self.assertRaises(PermissionError):self.engine.learn_from_task(self.actors['trainer'],self.task(100))
        with self.assertRaises(PermissionError):
            self.engine.evaluate_candidate(self.actors['evaluator'],self.candidate,[self.task(n) for n in range(101,106)])
        shadow=ShadowLearning(self.engine,runtime=self.actors['runtime'],trainer=self.actors['trainer'])
        with self.assertRaises(PermissionError):shadow.execute(self.task(200))
        with self.assertRaises(PermissionError):canary.execute(self.actors['runtime'],ident,self.task(201))
        with self.engine._db() as con:
            self.assertEqual(con.execute("SELECT count(*) FROM gl_tasks WHERE task_id IN ('task-100','task-200','task-201')").fetchone()[0],0)

    def test_monitor_rolls_back_if_uncertainty_evidence_becomes_required(self):
        from hashlib import sha256
        canary=CanaryLearning(self.engine)
        ident=canary.start(self.actors['operator'],self.candidate,expected_generation=0,reason='review',percent=25,required_successes=5)
        hits=0
        for n in range(100,1000):
            task=self.task(n);_,fingerprint=self.engine._task(task)
            if int(sha256((ident+':'+fingerprint).encode()).hexdigest(),16)%100<25:
                canary.execute(self.actors['runtime'],ident,task);hits+=1
                if hits==5:break
        self.assertEqual(hits,5)
        canary.promote(self.actors['operator'],ident,expected_generation=0,reason='review',monitor_latency_ms=10000)
        self.gate.enable(self.actors['operator'],CONTEXT)
        result=canary.execute(self.actors['runtime'],ident,self.task(2000))
        self.assertEqual(result['strategy'],'regex-inventory')
        self.assertEqual(result['monitor']['reason'],'uncertainty_ineligible')
        self.assertEqual(self.engine.status(self.actors['operator'])['active_release'],self.initial['active_release'])

    def test_rollback_preserves_gate_and_conflict_tables(self):
        active=self.activate()
        self.gate.enable(self.actors['operator'],CONTEXT)
        rolled=self.engine.rollback(self.actors['operator'],self.initial['active_release'],expected_generation=active['generation'],reason='rollback')
        self.assertEqual(rolled['routes'][CONTEXT],'regex-inventory')
        with self.engine._db() as con:self.assertEqual(con.execute('SELECT count(*) FROM uc_release_scopes').fetchone()[0],1)


if __name__=='__main__':unittest.main()
