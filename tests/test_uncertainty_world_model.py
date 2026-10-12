"""Real Memento registry, coordinator, planner and rollback integration."""
import tempfile
import unittest
from nerve_awim.governed_learning_v20 import GovernedLearning,LearningAuthority
from nerve_awim.agent_learning_v12 import RegisteredStrategy
from nerve_awim.uncertainty.contracts import Claim
from nerve_awim.uncertainty.ledger import Ledger,StaleRevision
from nerve_awim.uncertainty.world_model_adapter import WorldModelUncertainty
from nerve_awim.world_model.ledger import Ledger as WorldLedger,migrate
from nerve_awim.world_model.demo import populate
from nerve_awim.world_model.reflection import reflect
from nerve_awim.world_model.compiler import compile_rules
from nerve_awim.world_model.registry import Registry
from nerve_awim.world_model.coordinator import Coordinator
from nerve_awim.world_model.contracts import Policy
from nerve_awim.world_model.release import SimulatedRelease

class WorldUncertaintyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=self.tmp.name+'/combined.db';self.auth=LearningAuthority()
        self.runtime=self.auth.issue('tenant','agent','runtime');self.operator=self.auth.issue('tenant','agent','operator');self.trainer=self.auth.issue('tenant','agent','trainer');self.evaluator=self.auth.issue('tenant','agent','evaluator')
        self.engine=GovernedLearning(self.path,authority=self.auth,strategies=[RegisteredStrategy('read','read',lambda a:a)],judge=lambda t,v:True,contract_revision='test',baseline_routes={'read':'read'})
        self.engine.bootstrap(self.operator);self.ledger=Ledger(self.engine);migrate(self.path);self.world=WorldLedger(self.path,self.auth)
        self.adapter=WorldModelUncertainty(self.ledger,self.world);self.adapter.enable(self.operator,mode='enforce')
        populate(self.world,self.trainer,self.evaluator)
        self.rules=reflect(self.world.episodes(self.trainer))['rules'];self.policy=Policy(enabled=True);self.registry=Registry(self.world)
        self.add('base',True)
        for rule in self.rules:self.adapter.bind_rule(self.operator,task_id='task',rule_id=rule['rule_id'],claim_ids=['base'],review_ref='host-reviewed')
        self.model=self.registry.put(self.trainer,self.rules,compile_rules(self.rules),self.policy)
    def add(self,cid,value,task='task'):
        source=self.ledger.register_source(self.runtime,'source-'+cid,{'cid':cid,'value':value})
        self.ledger.add_claim(self.runtime,Claim(cid,'tenant',task,'record','status',value,**source))
    def conflict(self):
        self.add('other',False);return self.ledger.detect(self.runtime,'task')[0]
    def test_conflict_blocks_actual_registry_freeze_and_release(self):
        self.registry.freeze(self.evaluator,self.model)
        conflict=self.conflict()
        with self.assertRaises(PermissionError):self.registry.freeze(self.evaluator,self.model)
        with self.assertRaises(PermissionError):SimulatedRelease(self.world).authorize(self.operator,self.model,expected_generation=0,planner_config={'max_depth':5,'max_nodes':100},reason='test')
        report=self.adapter.rulebook(self.runtime,self.model)
        self.assertIn(conflict.conflict_id,report['uncertainty']['conflict_ids']);self.assertIn('hypothesis_disputed',report['text'])
    def test_bare_world_restart_cannot_omit_persisted_guard(self):
        restarted=WorldLedger(self.path,self.auth)
        with self.assertRaises(PermissionError):Registry(restarted).freeze(self.evaluator,self.model)
    def test_unknown_and_expired_rule_prerequisites_cannot_freeze(self):
        for ident,value,end in [('unknown',None,None),('expired',True,1.0)]:
            with self.subTest(ident=ident):
                source=self.ledger.register_source(self.runtime,'source-'+ident,{'value':value})
                self.ledger.add_claim(self.runtime,Claim(ident,'tenant',ident,'record','status',value,valid_to=end,**source))
                rule={**self.rules[0],'rule_id':ident+'-rule'}
                self.adapter.bind_rule(self.operator,task_id=ident,rule_id=rule['rule_id'],claim_ids=[ident],review_ref='host-review')
                model=self.registry.put(self.trainer,[rule],compile_rules([rule]),self.policy)
                self.assertEqual(self.adapter.report(self.runtime,[rule])['rules'][0]['status'],'unavailable')
                with self.assertRaises(PermissionError):self.registry.freeze(self.evaluator,model)
    def test_independent_rule_candidate_can_freeze(self):
        self.conflict();self.add('independent',True,task='other-task')
        # Rules are canonical IDs, so select an existing rule under a new reviewed
        # identity while preserving its actual observed Memento evidence links.
        rule={**self.rules[0],'rule_id':'independent-rule'}
        self.adapter.bind_rule(self.operator,task_id='other-task',rule_id=rule['rule_id'],claim_ids=['independent'],review_ref='independent-review')
        model=self.registry.put(self.trainer,[rule],compile_rules([rule]),self.policy)
        self.assertEqual(self.registry.freeze(self.evaluator,model),model)
    def test_plan_requires_frozen_and_dispatch_rechecks_revision(self):
        episode=self.world.episodes(self.trainer)[0];initial=episode['initial'];actions=sorted(set(r['action'] for r in self.rules))
        with self.assertRaises(PermissionError):self.adapter.plan(self.runtime,self.model,initial,actions)
        self.registry.freeze(self.evaluator,self.model);decision=self.adapter.plan(self.runtime,self.model,initial,actions)
        self.assertTrue(decision['simulation_only']);self.assertFalse(decision['deployment_authorized'])
        self.add('unrelated',True)
        with self.assertRaises(StaleRevision):self.adapter.validate_dispatch(self.runtime,decision,initial,actions,5)
    def test_real_coordinator_checkpoint_preserves_conflict_after_restart(self):
        conflict=self.conflict();coordinator=Coordinator(self.world,trainer=self.trainer,evaluator=self.evaluator,policy=self.policy)
        run=coordinator.create();coordinator.resume(run,stop_after='compile')
        state=coordinator.status(run);self.assertIn(conflict.conflict_id,state['body']['uncertainty']['conflict_ids'])
        resumed=Coordinator(self.world,trainer=self.trainer,evaluator=self.evaluator,policy=self.policy).resume(run)
        self.assertEqual(resumed['phase'],'stopped');self.assertFalse(resumed['body'].get('eligibility',True));self.assertIn(conflict.conflict_id,resumed['body']['uncertainty']['conflict_ids'])
        self.assertEqual(self.registry.get(self.evaluator,resumed['body']['model_id'])['state'],'candidate')
    def test_simulated_rollback_preserves_new_conflict_and_history(self):
        self.registry.freeze(self.evaluator,self.model);release=SimulatedRelease(self.world)
        state=release.authorize(self.operator,self.model,expected_generation=0,planner_config={'max_depth':5,'max_nodes':100},reason='offline-review')
        conflict=self.conflict();revision=self.ledger.revision(self.runtime,'task');events=self.ledger.events(self.runtime,'task')
        release.monitor(self.runtime,expected_generation=state['generation'],observed_ok=False,elapsed_ms=1)
        self.assertEqual(self.ledger.revision(self.runtime,'task'),revision);self.assertEqual(self.ledger.events(self.runtime,'task'),events)
        self.assertEqual(self.ledger.open_conflicts(self.runtime,'task')[0].conflict_id,conflict.conflict_id)
    def test_rule_binding_and_activation_roles(self):
        with self.assertRaises(PermissionError):self.adapter.enable(self.runtime,mode='off')
        with self.assertRaises(PermissionError):self.adapter.bind_rule(self.runtime,task_id='task',rule_id='new',claim_ids=['base'],review_ref='untrusted')
        self.add('other',False)
        with self.assertRaises(PermissionError):self.adapter.bind_rule(self.operator,task_id='task',rule_id=self.rules[0]['rule_id'],claim_ids=['other'],review_ref='changed')
    def test_actual_hermes_world_proposer_carries_server_conflicts(self):
        from nerve_awim.hermes_learning import propose_world_rules
        conflict=self.conflict();requests=[];rules=self.rules
        class ScriptedRuntime:
            def execute(self,role,request,**scope):requests.append(request);return {'rules':rules}
        result=propose_world_rules(self.world,self.trainer,runtime=ScriptedRuntime(),offline_fixture=True)
        self.assertIn(conflict.conflict_id,requests[0]['uncertainty']['conflict_ids'])
        self.assertIn(conflict.conflict_id,result['uncertainty']['conflict_ids']);self.assertFalse(result['eligibility'])
        bare=WorldLedger(self.path,self.auth)
        with self.assertRaises(PermissionError):propose_world_rules(bare,self.trainer,runtime=ScriptedRuntime(),offline_fixture=True)
        self.assertEqual(len(requests),1)
    def test_new_conflict_suspends_even_when_simulated_outcome_reports_success(self):
        self.registry.freeze(self.evaluator,self.model);release=SimulatedRelease(self.world)
        state=release.authorize(self.operator,self.model,expected_generation=0,planner_config={'max_depth':5,'max_nodes':100},reason='offline-review')
        self.conflict()
        result=release.monitor(self.runtime,expected_generation=state['generation'],observed_ok=True,elapsed_ms=1)
        self.assertNotEqual(result['status'],'simulated_pass');self.assertIsNone(release.status(self.operator)['active'])
        self.assertEqual(len(self.ledger.open_conflicts(self.runtime,'task')),1)
