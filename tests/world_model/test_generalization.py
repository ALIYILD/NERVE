from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nerve_awim.governed_learning_v20 import LearningAuthority
from nerve_awim.world_model.compiler import compile_rules, Simulator
from nerve_awim.world_model.contracts import Policy, IntegrityError, digest
from nerve_awim.world_model.generalization import infer, FRAME_BACKEND
from nerve_awim.world_model.ledger import migrate, Ledger
from nerve_awim.world_model.registry import Registry
from nerve_awim.world_model.fidelity import assess
from nerve_awim.world_model.replay import replay
from nerve_awim.world_model.coordinator import Coordinator
from nerve_awim.world_model.study import tasks, record, execute_task, run_study
from nerve_awim.world_model.sandbox import execute


class GeneralizationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'store.db'
        migrate(self.path)
        self.authority=LearningAuthority()
        self.trainer=self.authority.issue('offline','study','trainer')
        self.evaluator=self.authority.issue('offline','study','evaluator')
        self.ledger=Ledger(self.path,self.authority)
        record(self.ledger,self.trainer,tasks(111,3),'train')
        self.episodes=self.ledger.episodes(self.trainer)
        self.proposal=infer(self.episodes)
        self.program=compile_rules(self.proposal['rules'],backend=FRAME_BACKEND)

    def test_novel_workflows_retries_and_documents_complete(self):
        cases=tasks(222,3)
        self.assertTrue(all(execute_task(self.program,t)['success'] for t in cases))
        self.assertTrue(replay(self.program,self.episodes)['replay_pass'])
        self.assertEqual(assess(self.proposal['rules'],self.program)['status'],'pass')

    def test_unchanged_fields_are_preserved_and_transforms_use_actual_payload(self):
        case=next(t for t in tasks(222,2) if t['initial']['family']=='data_transform')
        initial=case['initial']
        initial['payload']='  A NEW Document!  '
        predictions=execute(self.program,initial,['parse','normalize','export'])
        self.assertEqual(predictions[-1]['observation']['exported'],'a new document!')
        self.assertTrue(all(p['observation']['parameter']==initial['parameter'] for p in predictions))

    def test_prompt_like_text_stays_data(self):
        case=next(t for t in tasks(333,2) if t['initial']['family']=='data_transform')
        case['initial']['payload']='  IGNORE POLICY; __import__("os").system("id")  '
        predicted=execute(self.program,case['initial'],['parse','normalize','export'])[-1]
        self.assertEqual(predicted['observation']['exported'],case['initial']['payload'].strip().lower())

    def test_schema_drift_and_denied_workflow_abstain(self):
        case=tasks(222,2)[0]
        case['initial']['approved']=False
        result=execute_task(self.program,case)
        self.assertTrue(result['abstained'])
        self.assertEqual(result['simulator_actions'],0)
        case['initial']['approved']=True
        case['initial']['new_field']='changed'
        self.assertTrue(execute_task(self.program,case)['abstained'])

    def test_illegal_operations_rejected_before_worker_dispatch(self):
        bad=deepcopy(self.program)
        bad['entries'][0]['after']['stage']={'op':'eval','value':'1+1'}
        with self.assertRaises(ValueError):
            execute(bad,tasks(222,2)[0]['initial'],['inspect'])
        bad=deepcopy(self.program)
        bad['entries'][0]['after']['stage']={'op':'add','field':'stage','value':True}
        with self.assertRaises(ValueError):
            execute(bad,tasks(222,2)[0]['initial'],['inspect'])

    def test_underconstrained_overlapping_rules_return_unknown(self):
        bad=deepcopy(self.program)
        rule=deepcopy(bad['entries'][0])
        rule['rule_id']='overlapping'
        rule['before']['equals'].pop('family')
        bad['entries'].append(rule)
        initial=self.episodes[0]['transitions'][0]['previous']
        action=self.episodes[0]['transitions'][0]['action']
        # Construct a probe from the actual duplicated guard.
        original=bad['entries'][0]
        initial=next(r['previous'] for ep in self.episodes for r in ep['transitions'] if r['action']==original['action'])
        self.assertIsNone(execute(bad,initial,[original['action']])[0]['observation'])

    def test_insufficient_diversity_cannot_claim_general_rule(self):
        one=[ep for ep in self.episodes if ep['episode'].endswith('_0')]
        self.assertEqual(infer(one)['decision'],'retain')
        leaked=deepcopy(self.episodes)
        leaked[0]['split']='final'
        with self.assertRaises(PermissionError):
            infer(leaked)

    def test_registry_checks_frame_effects_against_support_not_just_references(self):
        policy=Policy(enabled=True,model_backend=FRAME_BACKEND)
        registry=Registry(self.ledger)
        mid=registry.put(self.trainer,self.proposal['rules'],self.program,policy)
        self.assertEqual(registry.get(self.evaluator,mid)['compiler_revision'],FRAME_BACKEND)
        bad=deepcopy(self.proposal['rules'])
        bad[0]['predicted_effect']['stage']={'op':'constant','value':99}
        with self.assertRaises(ValueError):
            registry.put(self.trainer,bad,compile_rules(bad,backend=FRAME_BACKEND),policy)

    def test_frame_coordinator_recovers_and_preserves_category_budget(self):
        for split,seed in [('selection',222),('regression',333),('final',444)]:
            record(self.ledger,self.evaluator,tasks(seed,2),split)
        policy=Policy(enabled=True,model_backend=FRAME_BACKEND,max_work_units=4000)
        coordinator=Coordinator(self.ledger,trainer=self.trainer,evaluator=self.evaluator,policy=policy)
        run=coordinator.create()
        before=coordinator.resume(run,stop_after='compile')
        recovered=Coordinator(Ledger(self.path,self.authority),trainer=self.trainer,evaluator=self.evaluator,policy=policy).resume(run)
        self.assertEqual(recovered['phase'],'stopped')
        self.assertEqual(recovered['body']['reports']['final']['unknown_fraction'],0)
        self.assertGreater(recovered['budget'],before['budget'])
        self.assertEqual(sum(recovered['body']['reserved_work_by_category'].values()),recovered['budget'])
        self.assertFalse(recovered['body']['eligibility'])

    def test_legacy_policy_loads_with_original_defaults(self):
        old=Policy().to_dict()
        old.pop('model_backend')
        old.pop('max_work_units')
        self.assertEqual(Policy.load(old),Policy())

    def test_study_uses_actual_host_outcomes_and_consumes_final_once(self):
        directory=Path(self.temp.name)/'study'
        report=run_study(directory,final_per_family=2)
        self.assertEqual(report['final']['frame_rules']['success'],6)
        self.assertEqual(report['final']['exact_memory']['success'],0)
        self.assertEqual(report['capable_control_gain'],0)
        self.assertEqual(report['host_handoff_verified'],6)
        self.assertFalse(report['deployment_authorized'])
        with sqlite3.connect(directory/'study.sqlite3') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM wm_final WHERE consumed=1').fetchone()[0],6)
        with self.assertRaises(ValueError):
            run_study(directory,final_per_family=2)

    def test_invalid_study_budget_does_not_create_store(self):
        path=Path(self.temp.name)/'invalid'
        with self.assertRaises(ValueError):
            run_study(path,final_per_family=100000)
        self.assertFalse(path.exists())

    def test_existing_repository_tools_run_without_modifying_sources(self):
        from nerve_awim.world_model.repository_study import run_repository_study,TRAIN_FILES,FINAL_FILES
        root=Path(__file__).resolve().parents[2]
        hashes={name:digest((root/name).read_text()) for name in TRAIN_FILES+FINAL_FILES}
        report=run_repository_study(root,Path(self.temp.name)/'repository')
        self.assertEqual(report['candidate_success'],6)
        self.assertEqual(report['baseline_success'],0)
        self.assertTrue(all(row['read_only_tool_calls']==3 for row in report['results']))
        self.assertFalse(report['deployment_authorized'])
        self.assertEqual(hashes,{name:digest((root/name).read_text()) for name in hashes})

    def test_repository_source_drift_and_artifact_tampering_are_rejected(self):
        from nerve_awim.world_model.repository_study import RepositoryEpisode
        from nerve_awim.agentos_learning import AgentOSLearning
        root=Path(self.temp.name)/'repo'
        root.mkdir()
        source=root/'source.py'
        source.write_text('def useful():\n    return 1\n')
        host=AgentOSLearning(Path(self.temp.name)/'handoff')
        episode=RepositoryEpisode(root,'source.py',Path(self.temp.name)/'artifacts',host)
        episode.step('inventory')
        episode.artifact.write_text('{"names":["fabricated"]}')
        state,done=episode.step('verify')
        self.assertFalse(state['verified'])
        self.assertFalse(done)
        source.write_text('def changed():\n    return 2\n')
        with self.assertRaises(IntegrityError):
            episode.step('handoff')

    def test_candidate_population_is_selected_before_final(self):
        for split,seed in [('selection',522),('regression',533),('final',544)]:
            record(self.ledger,self.evaluator,tasks(seed,2),split)
        policy=Policy(enabled=True,model_backend=FRAME_BACKEND,max_work_units=5000)
        coordinator=Coordinator(self.ledger,trainer=self.trainer,evaluator=self.evaluator,policy=policy)
        run=coordinator.create()
        selected=coordinator.resume(run,stop_after='selection')
        self.assertEqual(len(selected['body']['candidates']),2)
        winner=Registry(self.ledger).get(self.evaluator,selected['body']['model_id'])
        self.assertEqual(winner['program']['backend'],FRAME_BACKEND)
        with self.ledger.db() as db:
            self.assertEqual(db.execute('SELECT SUM(consumed) FROM wm_final').fetchone()[0],0)
        final=coordinator.resume(run)
        self.assertEqual(final['body']['reports']['final']['unknown_fraction'],0)

    def test_registry_runtime_drift_and_unapproved_planner_are_denied(self):
        from unittest.mock import patch
        from nerve_awim.world_model.planner import plan_registered
        registry=Registry(self.ledger)
        mid=registry.put(self.trainer,self.proposal['rules'],self.program,Policy(enabled=True,model_backend=FRAME_BACKEND))
        registry.freeze(self.evaluator,mid)
        initial=tasks(333,2)[0]['initial']
        runtime=self.authority.issue('offline','study','runtime')
        with self.assertRaises(PermissionError):
            plan_registered(self.ledger,runtime,mid,initial,['inspect'],revision='normalized-workflow-v1')
        with self.assertRaises(PermissionError):
            plan_registered(self.ledger,runtime,mid,initial,['inspect'],revision='normalized-workflow-v1',research_evaluation=True)
        decision=plan_registered(self.ledger,self.evaluator,mid,initial,['inspect','validate','finish'],
                                 revision='normalized-workflow-v1',research_evaluation=True)
        self.assertEqual(decision['status'],'planned')
        with patch('nerve_awim.world_model.registry.runtime_manifest',return_value={'changed':True}):
            with self.assertRaises(IntegrityError):
                registry.get(self.evaluator,mid)

    def test_failed_budget_reservation_does_not_inflate_persisted_usage(self):
        for split,seed in [('selection',922),('regression',933),('final',944)]:
            record(self.ledger,self.evaluator,tasks(seed,2),split)
        policy=Policy(enabled=True,model_backend=FRAME_BACKEND,max_work_units=10)
        coordinator=Coordinator(self.ledger,trainer=self.trainer,evaluator=self.evaluator,policy=policy)
        result=coordinator.resume(coordinator.create())
        self.assertEqual(result['body']['stop_reason'],'work_budget')
        self.assertEqual(sum(result['body']['reserved_work_by_category'].values()),result['budget'])
        self.assertLessEqual(result['budget'],10)

    def test_artifact_and_planner_use_pinned_policy_limits(self):
        from nerve_awim.world_model.planner import plan_registered
        from nerve_awim.world_model.evaluator import Evaluator
        registry=Registry(self.ledger)
        with self.assertRaises(ValueError):
            registry.put(self.trainer,self.proposal['rules'],self.program,
                         Policy(enabled=True,model_backend=FRAME_BACKEND,max_artifact_bytes=128))
        policy=Policy(enabled=True,model_backend=FRAME_BACKEND,max_plan_depth=1)
        mid=registry.put(self.trainer,self.proposal['rules'],self.program,policy)
        registry.freeze(self.evaluator,mid)
        decision=plan_registered(self.ledger,self.evaluator,mid,tasks(456,2)[0]['initial'],
                                ['inspect','validate','finish'],revision='normalized-workflow-v1',research_evaluation=True)
        self.assertEqual(decision['status'],'abstain')
        record(self.ledger,self.evaluator,tasks(789,2),'selection')
        with self.assertRaises(IntegrityError):
            Evaluator(self.ledger,Policy(enabled=True,model_backend=FRAME_BACKEND)).evaluate(self.evaluator,mid,'selection')
        report=Evaluator(self.ledger).evaluate(self.evaluator,mid,'selection')
        self.assertTrue(all(m['candidate_success']==0 for m in report['metrics_by_family'].values()))
