from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from nerve_awim.governed_learning_v20 import LearningAuthority
from nerve_awim.world_model.contracts import Policy, Rule, canonical, digest, IntegrityError, StaleWorker
from nerve_awim.world_model.ledger import Ledger, migrate
from nerve_awim.world_model.demo import populate, run_demo
from nerve_awim.world_model.reflection import reflect
from nerve_awim.world_model.compiler import compile_rules
from nerve_awim.world_model.fidelity import assess
from nerve_awim.world_model.replay import replay
from nerve_awim.world_model.registry import Registry
from nerve_awim.world_model.coordinator import Coordinator
from nerve_awim.world_model.evaluator import Evaluator
from nerve_awim.world_model.planner import plan, validate_dispatch
from nerve_awim.world_model.sandbox import execute, arbitrary_python
from nerve_awim.world_model.adapters import observe_handoff, propose_memory, shadow
from nerve_awim.agentos_learning import AgentOSLearning


class WorldModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'research.db'
        migrate(self.path)
        self.auth = LearningAuthority()
        self.trainer = self.auth.issue('offline','demo','trainer')
        self.evaluator = self.auth.issue('offline','demo','evaluator')
        self.operator = self.auth.issue('offline','demo','operator')
        self.ledger = Ledger(self.path,self.auth)
        self.policy = Policy(enabled=True)

    def populated(self):
        populate(self.ledger,self.trainer,self.evaluator)
        rules = reflect(self.ledger.episodes(self.trainer))['rules']
        return rules,compile_rules(rules)

    def coordinator(self):
        return Coordinator(self.ledger,trainer=self.trainer,evaluator=self.evaluator,policy=self.policy)

    def test_strict_policy_finite_json_and_unknown_fields(self):
        for value in (float('nan'),float('inf'),{'x':float('-inf')}):
            with self.assertRaises(ValueError):
                canonical(value)
        with self.assertRaises(ValueError):
            Policy.load({**self.policy.to_dict(),'hidden':1})
        for value in (True,0,-1,10000):
            with self.assertRaises(ValueError):
                Policy(max_generations=value)
        with self.assertRaises(PermissionError):
            Policy(allow_clinical_actions=True)
        self.assertEqual(Policy.load(self.policy.to_dict()),self.policy)

    def test_migration_preserves_old_data_and_is_restartable(self):
        old = Path(self.temp.name)/'old.db'
        with sqlite3.connect(old) as db:
            db.execute('CREATE TABLE existing(value TEXT)')
            db.execute("INSERT INTO existing VALUES('preserved')")
        copy = Path(self.temp.name)/'copy.db'
        with sqlite3.connect(old) as source, sqlite3.connect(copy) as target:
            source.backup(target)
        migrate(copy)
        migrate(copy)
        with sqlite3.connect(copy) as db:
            self.assertEqual(db.execute('SELECT value FROM existing').fetchone()[0],'preserved')
        with sqlite3.connect(old) as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='wm_schema'").fetchone())

    def test_prediction_order_outcome_immutability_and_recovery(self):
        self.populated()
        before = self.ledger.episodes(self.trainer)
        after = Ledger(self.path,self.auth).episodes(self.trainer)
        self.assertEqual(before,after)
        row = before[0]['transitions'][0]
        self.assertLessEqual(row['predicted_at'],row['observed_at'])
        with self.assertRaises(IntegrityError):
            self.ledger.complete(self.trainer,row['id'],outcome={'stage':88},completion=False)
        with self.assertRaises(LookupError):
            self.ledger.complete(self.trainer,'unreserved',outcome={'stage':1},completion=False)
        with self.assertRaises(ValueError):
            self.ledger.reserve(self.trainer,transition_id='out_of_order',episode='train_workflow',sequence=8,
                                action='finish',previous={'stage':3},prediction=None)

    def test_concurrent_duplicates_have_one_receipt(self):
        self.ledger.episode(self.trainer,episode='ep',source='src',family='workflow',split='train',initial={'stage':0})
        def deliver(_):
            self.ledger.reserve(self.trainer,transition_id='t',episode='ep',sequence=0,action='prepare',previous={'stage':0},prediction=None)
            self.ledger.complete(self.trainer,'t',outcome={'stage':1},completion=False)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(deliver,range(12)))
        self.assertEqual(len(self.ledger.episodes(self.trainer)[0]['transitions']),1)

    def test_scopes_and_sealed_splits_are_denied(self):
        rules,program = self.populated()
        registry=Registry(self.ledger)
        model=registry.put(self.trainer,rules,program,self.policy)
        other=self.auth.issue('other','demo','trainer')
        with self.assertRaises(LookupError):
            registry.get(other,model)
        with self.assertRaises(PermissionError):
            self.ledger.episodes(self.trainer,'final')
        with self.assertRaises(PermissionError):
            reflect(self.ledger.episodes(self.evaluator,'final'))
        with self.assertRaises(ValueError):
            self.ledger.episode(self.trainer,episode='../x',source='x',family='x',split='train',initial={'x':1})

    def test_compiler_and_independent_fidelity_reject_bad_code(self):
        rules,program=self.populated()
        self.assertEqual(assess(rules,program)['status'],'pass')
        bad=deepcopy(program)
        bad['entries'][0]['after']={'stage':99}
        self.assertEqual(assess(rules,bad)['status'],'disagree')
        self.assertFalse(replay(bad,self.ledger.episodes(self.trainer))['replay_pass'])
        self.assertTrue(replay(program,self.ledger.episodes(self.trainer))['replay_pass'])
        rules[0]['status']='retracted'
        with self.assertRaises(ValueError):
            compile_rules(rules)

    def test_goal_mismatch_and_unknown_are_not_success(self):
        _,program=self.populated()
        bad=deepcopy(program)
        for entry in bad['entries']:
            entry['goal']=True
        result=replay(bad,self.ledger.episodes(self.trainer))
        self.assertFalse(result['replay_pass'])
        self.assertEqual(result['failures'][0]['reason'],'completion')
        self.assertEqual(execute(program,{'unseen':True},['prepare'])[0]['observation'],None)
        self.assertEqual(plan(program,{'unseen':True},['prepare'])['status'],'abstain')

    def test_code_and_rule_reflection_paths_differ(self):
        rules,_=self.populated()
        episodes=self.ledger.episodes(self.trainer)
        self.assertEqual(reflect(episodes)['decision'],'revise_rulebook')
        self.assertEqual(reflect(episodes,rules)['decision'],'repair_code')
        episodes[0]['transitions'][0]['status']='missing'
        self.assertEqual(reflect(episodes)['failure_class'],'missing_evidence')

    def test_registry_tampering_and_invented_evidence(self):
        rules,program=self.populated()
        registry=Registry(self.ledger)
        bad=deepcopy(rules)
        bad[0]['supporting_transition_ids']=['invented']
        with self.assertRaises(ValueError):
            registry.put(self.trainer,bad,program,self.policy)
        model=registry.put(self.trainer,rules,program,self.policy)
        with self.ledger.db() as db:
            db.execute("UPDATE wm_artifacts SET body='{}' WHERE id=?",(model,))
        with self.assertRaises(IntegrityError):
            registry.get(self.evaluator,model)

    def test_planner_rechecks_observation_and_budget(self):
        _,program=self.populated()
        decision=plan(program,{'stage':0},['prepare','validate','finish'])
        self.assertEqual(decision['actions'],['prepare','validate','finish'])
        self.assertEqual(validate_dispatch(decision,program,{'stage':0},['prepare'],1),'prepare')
        with self.assertRaises(PermissionError):
            validate_dispatch(decision,program,{'stage':1},['prepare'],1)
        with self.assertRaises(PermissionError):
            validate_dispatch(decision,program,{'stage':0},['prepare'],0)
        self.assertEqual(plan(program,{'stage':0},['prepare','validate','finish'],max_nodes=1)['reason'],'node_budget')

    def test_fencing_and_lease_competition(self):
        self.populated()
        service=self.coordinator()
        run=service.create()
        fence=service.claim(run,'worker1')
        with self.assertRaises(StaleWorker):
            service.claim(run,'worker2')
        with self.ledger.db() as db:
            db.execute('UPDATE wm_runs SET lease_until=0 WHERE id=?',(run,))
        newer=service.claim(run,'worker2')
        self.assertGreater(newer,fence)
        with self.assertRaises(StaleWorker):
            service.checkpoint(run,'worker1',fence,'reflect',{})

    def test_restart_every_checkpoint_retains_budget_and_final_nonreuse(self):
        self.populated()
        service=self.coordinator()
        run=service.create()
        budget=0
        for phase in ('capture','reflect','compile','verify','selection','freeze','final','register'):
            service=self.coordinator()
            current=service.resume(run,stop_after=phase)
            self.assertGreater(current['budget'],budget)
            budget=current['budget']
        self.assertEqual(current['phase'],'stopped')
        self.assertFalse(current['body']['eligibility'])
        self.assertEqual(service.resume(run)['budget'],budget)
        with self.assertRaises(IntegrityError):
            Evaluator(self.ledger).reserve_final(self.evaluator,'another_run')
        with self.assertRaises(IntegrityError):
            Evaluator(self.ledger).evaluate(self.evaluator,current['body']['model_id'],'final',run_id=run)

    def test_crash_after_final_consumption_never_reopens_holdout(self):
        self.populated()
        service=self.coordinator()
        run=service.create()
        state=service.resume(run,stop_after='freeze')
        Evaluator(self.ledger).evaluate(self.evaluator,state['body']['model_id'],'final',run_id=run)
        recovered=service.resume(run)
        self.assertEqual(recovered['body']['stop_reason'],'final_consumed_without_recoverable_report')

    def test_arbitrary_code_and_language_escape_probes_rejected(self):
        _,program=self.populated()
        for probe in ('__import__("os").system("id")','open("/etc/passwd")','while True: pass','socket.connect'):
            with self.assertRaises(NotImplementedError):
                arbitrary_python(probe)
            bad=deepcopy(program)
            bad['entries'][0]['action']=probe
            with self.assertRaises(ValueError):
                execute(bad,{'stage':0},['prepare'])
        with self.assertRaises(ValueError):
            execute(program,{'stage':0},['prepare']*101)

    def test_real_agentos_entrypoint_records_host_truth_pending_memory(self):
        host=AgentOSLearning(Path(self.temp.name)/'agentos')
        task={'id':'host_task','exit_code':1,'artifact_exists':True,'qa_passed':True,'memory_written':False}
        output={'status':'done','passed':True,'memory_saved':True}
        self.ledger.episode(self.trainer,episode='handoff',source='host_task',family='handoff',split='train',initial={'pending':True})
        receipt=observe_handoff(host,self.ledger,self.trainer,profile='demo',task=task,output=output,
                                transition_id='host_result',episode='handoff')
        self.assertFalse(receipt['host_receipt']['success'])
        row=self.ledger.episodes(self.trainer)[0]['transitions'][0]
        self.assertFalse(row['outcome']['passed'])
        rules=reflect(self.ledger.episodes(self.trainer))['rules']
        registry=Registry(self.ledger)
        model_id=registry.put(self.trainer,rules,compile_rules(rules),self.policy)
        model=registry.get(self.trainer,model_id)
        actor=host.actor('demo')
        memory=propose_memory(host.ledger,actor,model)
        self.assertEqual(host.ledger.status(actor,memory).status,'pending')

    def test_shadow_does_not_fabricate_unexecuted_outcome(self):
        _,program=self.populated()
        report=shadow(program,self.ledger.episodes(self.trainer)[0],'finish')
        self.assertEqual(report['external_actions'],0)
        self.assertIsNone(report['counterfactual_outcome'])
        self.assertEqual(report['counterfactual_status'],'unobserved')

    def test_cli_demo_and_denied_operator_black_box(self):
        db=Path(self.temp.name)/'cli.db'
        base=[sys.executable,'-m','nerve_awim.world_model.cli','--db',str(db)]
        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[2]/'src')}
        result=subprocess.run(base+['demo','--json'],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        report=json.loads(result.stdout)['result']
        self.assertFalse(report['eligibility'])
        result=subprocess.run(base+['promote','--model-id',report['model_id']],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,3)
        result=subprocess.run(base+['report','--run-id',report['run_id']],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['result']['phase'],'stopped')

    def test_simulated_rollback_is_atomic_and_survives_restart(self):
        from nerve_awim.world_model.release import SimulatedRelease
        rules,program=self.populated()
        registry=Registry(self.ledger)
        first=registry.put(self.trainer,rules,program,self.policy)
        registry.freeze(self.evaluator,first)
        second=registry.put(self.trainer,rules,program,self.policy,parent=first)
        registry.freeze(self.evaluator,second)
        releases=SimulatedRelease(self.ledger)
        config={'max_depth':5,'max_nodes':100}
        releases.authorize(self.operator,first,expected_generation=0,planner_config=config,reason='isolated demo baseline')
        releases.authorize(self.operator,second,expected_generation=1,planner_config=config,reason='isolated demo candidate')
        with self.assertRaises(StaleWorker):
            releases.authorize(self.operator,first,expected_generation=1,planner_config=config,reason='stale')
        with self.assertRaises(PermissionError):
            releases.authorize(self.trainer,first,expected_generation=2,planner_config=config,reason='untrusted')
        runtime=self.auth.issue('offline','demo','runtime')
        outcome=releases.monitor(runtime,expected_generation=2,observed_ok=False,elapsed_ms=1)
        self.assertEqual(outcome['status'],'simulated_rollback')
        recovered=SimulatedRelease(Ledger(self.path,self.auth)).status(self.operator)
        self.assertEqual(recovered['active'],first)
        self.assertEqual(recovered['generation'],3)
        body=json.loads(recovered['body'])
        self.assertEqual(body['active_bundle']['planner_config'],config)
        self.assertFalse(body['active_bundle']['deployment_authorized'])

    def test_population_disagreement_and_probe_resolves(self):
        from nerve_awim.world_model.population import select,disagreement
        rules,program=self.populated()
        left,right=deepcopy(program),deepcopy(program)
        extra={'rule_id':'probe_rule','before':{'stage':5},'action':'probe','after':{'stage':6},'goal':False}
        left['entries'].append(extra)
        right['entries'].append({**extra,'after':{'stage':7}})
        probes=[{'initial':{'stage':5},'action':'probe'}]
        selected=select([left,right],self.ledger.episodes(self.trainer),probes,seed=5)
        self.assertEqual(len(selected['members']),2)
        self.assertTrue(disagreement(selected['members'],{'stage':5},'probe')['disagrees'])
        self.ledger.episode(self.trainer,episode='probe',source='probe_source',family='workflow',split='train',initial={'stage':5})
        self.ledger.reserve(self.trainer,transition_id='probe_t',episode='probe',sequence=0,action='probe',previous={'stage':5},prediction=None)
        self.ledger.complete(self.trainer,'probe_t',outcome={'stage':6},completion=False)
        selected=select([left,right],self.ledger.episodes(self.trainer),probes,seed=5)
        self.assertEqual(len(selected['members']),1)
        self.assertEqual(selected['members'][0],left)

    def test_transfer_revocation_and_drift_fail_closed(self):
        from nerve_awim.world_model.retention import transferred_proposals,require_revision,tombstone_episode
        rules,program=self.populated()
        with self.assertRaises(PermissionError):
            transferred_proposals(rules)
        transferred=transferred_proposals(rules,permission=True)
        self.assertTrue(all(r['status']=='hypothesis' for r in transferred))
        with self.assertRaises(ValueError):
            compile_rules(transferred)
        registry=Registry(self.ledger)
        model=registry.put(self.trainer,rules,program,self.policy)
        with self.assertRaises(PermissionError):
            require_revision(registry.get(self.trainer,model),'changed')
        result=tombstone_episode(self.ledger,self.operator,'train_workflow')
        self.assertFalse(result['physical_erasure'])
        with self.assertRaises(IntegrityError):
            registry.get(self.trainer,model)

    def test_mcp_binding_does_not_accept_caller_tenant_or_operator_access(self):
        from nerve_awim.world_model.mcp import InspectionTools,register
        rules,program=self.populated()
        model=Registry(self.ledger).put(self.trainer,rules,program,self.policy)
        with self.assertRaises(PermissionError):
            InspectionTools(self.ledger,self.trainer)
        auditor=self.auth.issue('offline','demo','auditor')
        binding=InspectionTools(self.ledger,auditor)
        self.assertEqual(binding.inspect_model(model)['state'],'candidate')
        wrong=self.auth.issue('wrong','demo','auditor')
        with self.assertRaises(LookupError):
            InspectionTools(self.ledger,wrong).inspect_model(model)
        with self.assertRaises(TypeError):
            binding.inspect_model(model,tenant='wrong')

    def test_hidden_state_conflict_is_not_compiled(self):
        self.populated()
        self.ledger.episode(self.trainer,episode='hidden',source='hidden_source',family='workflow',split='train',initial={'stage':0})
        self.ledger.reserve(self.trainer,transition_id='hidden_t',episode='hidden',sequence=0,action='prepare',previous={'stage':0},prediction=None)
        self.ledger.complete(self.trainer,'hidden_t',outcome={'stage':9},completion=False)
        result=reflect(self.ledger.episodes(self.trainer))
        self.assertEqual(result['decision'],'retain')
        self.assertEqual(result['failure_class'],'hidden_state_or_environment_drift')

    def test_hermes_existing_module_bridge_keeps_final_out_of_request(self):
        from nerve_awim.hermes_learning import propose_world_rules
        rules,_=self.populated()
        seen=[]
        class Runtime:
            def execute(self,role,request,**scope):
                seen.append(request)
                return {'rules':rules}
        result=propose_world_rules(self.ledger,self.trainer,runtime=Runtime(),offline_fixture=True)
        self.assertFalse(result['eligibility'])
        self.assertTrue(all(e['split']=='train' for e in seen[0]['evidence']))
        with self.assertRaises(PermissionError):
            propose_world_rules(self.ledger,self.trainer,runtime=Runtime())
        rules[0]['supporting_transition_ids']=['final_answer']
        with self.assertRaises(ValueError):
            propose_world_rules(self.ledger,self.trainer,runtime=Runtime(),offline_fixture=True)

    def test_invalid_batch_ingestion_rolls_back_all_rows(self):
        base=[sys.executable,'-m','nerve_awim.world_model.cli','--db',str(self.path)]
        manifest={'schema_version':1,'episodes':[
            {'episode':'valid','source':'valid','family':'workflow','initial':{'stage':0},
             'transitions':[{'id':'valid_t','action':'prepare','outcome':{'stage':1},'completion':False}]},
            {'episode':'invalid','source':'invalid','family':'workflow','initial':{'stage':0},
             'transitions':[{'id':'invalid_t','action':'prepare','outcome':{'stage':1},'completion':'yes'}]}]}
        path=Path(self.temp.name)/'manifest.json'
        path.write_text(json.dumps(manifest))
        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[2]/'src')}
        result=subprocess.run(base+['ingest','--manifest',str(path)],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertEqual(self.ledger.episodes(self.trainer),[])

    def test_sensor_outage_uses_existing_runtime_without_safe_action_invention(self):
        from nerve_awim.observed_runtime_v29 import ObservedNerveRuntime
        from nerve_awim.world_model.adapters import sensor_observation
        class Verifier:
            def verify(self,token,now):
                return None
        runtime=ObservedNerveRuntime(verifier=Verifier(),issuer='https://synthetic.test',audience='nerve',
            secret=b'offline-fixture-not-a-real-secret-000',ledger_path=str(Path(self.temp.name)/'sensor.db'),
            max_missing=1,recovery_samples=2)
        runtime.sensor_missing()
        result=sensor_observation(runtime)
        self.assertEqual(result['status'],'unavailable')
        self.assertIsNone(result['action'])
        self.assertIsNone(result['prediction'])
        self.assertFalse(result['deterministic_replay_eligible'])

    def test_optional_mcp_real_stdio_inspection_binding(self):
        import importlib.util
        if importlib.util.find_spec('mcp') is None:
            self.skipTest('official MCP SDK absent')
        import asyncio
        from mcp import ClientSession,StdioServerParameters
        from mcp.client.stdio import stdio_client
        rules,program=self.populated()
        model=Registry(self.ledger).put(self.trainer,rules,program,self.policy)
        code='''import sys
from nerve_awim.governed_learning_v20 import LearningAuthority
from nerve_awim.world_model.ledger import Ledger
from nerve_awim.world_model.mcp import InspectionTools
from nerve_awim.learn_mcp import create_server
a=LearningAuthority()
l=Ledger(sys.argv[1],a)
b=InspectionTools(l,a.issue('offline','demo','auditor'))
create_server(sys.argv[2],world_model_binding=b).run()
'''
        async def exercise():
            params=StdioServerParameters(command=sys.executable,args=['-c',code,str(self.path),str(Path(self.temp.name)/'mcp.db')],
                env={'PYTHONPATH':str(Path(__file__).resolve().parents[2]/'src')})
            async with stdio_client(params) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    listed=await session.list_tools()
                    names={t.name for t in listed.tools}
                    self.assertIn('inspect_world_model',names)
                    self.assertFalse({'promote_world_model','authorize_canary','issue_authority'} & names)
                    result=await session.call_tool('inspect_world_model',{'model_id':model})
                    self.assertFalse(getattr(result,'is_error',getattr(result,'isError',False)))
                    result=await session.call_tool('inspect_world_model',{'model_id':'absent'})
                    self.assertTrue(getattr(result,'is_error',getattr(result,'isError',False)))
        asyncio.run(exercise())

    def test_resume_in_new_process_preserves_budget_and_model(self):
        self.populated()
        service=self.coordinator()
        run=service.create()
        before=service.resume(run,stop_after='compile')
        config=Path(self.temp.name)/'config.json'
        config.write_text(json.dumps(self.policy.to_dict()))
        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[2]/'src')}
        command=[sys.executable,'-m','nerve_awim.world_model.cli','--db',str(self.path),
                 'resume','--run-id',run,'--config',str(config)]
        result=subprocess.run(command,env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        after=json.loads(result.stdout)['result']
        self.assertEqual(after['phase'],'stopped')
        self.assertEqual(after['body']['model_id'],before['body']['model_id'])
        self.assertGreater(after['budget'],before['budget'])

    def test_json_boolean_is_not_numeric_observation(self):
        _,program=self.populated()
        prediction=execute(program,{'stage':False},['prepare'])[0]
        self.assertIsNone(prediction['observation'])
