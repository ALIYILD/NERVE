"""Orchestration contracts with fake inference and a host-owned fake judge.

These tests spend no provider credits and execute no generated repair code.
"""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from nerve_awim.agentos_experiments import RepositoryExperiments

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/agentos_repository.py'
SPEC = importlib.util.spec_from_file_location('nerve_test_repository_runner', SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
REAL_REVISION = runner.revision


class RepositoryRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.host = SimpleNamespace(directory=self.root/'state')
        self.host.directory.mkdir()
        self.vault = self.root/'vault'
        self.groups = {phase:[dict(id=phase+'-'+str(i), family=phase+'-family-'+str(i),
                                  source='source '+phase+' '+str(i), requirements='repair '+phase,
                                  hidden_answer='NEVER_INCLUDE_PRIVATE_CHECK_'+phase)
                              for i in range(count)]
                       for phase,count in (('train',2),('selection',3),('retention',3),('final',3))}
        self.calls = []
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(runner,'cohorts',return_value={'v1':runner.bench}))
        self.stack.enter_context(patch.object(runner.bench,'dataset',return_value=self.groups))
        self.stack.enter_context(patch.object(runner.bench,'public_task',side_effect=self.public))
        self.stack.enter_context(patch.object(runner.bench,'reference_solution',return_value={'code':'REFERENCE'},create=True))
        self.stack.enter_context(patch.object(runner.bench,'evaluate',side_effect=self.judge))
        self.stack.enter_context(patch.object(runner,'revision',return_value='judge-fixture-v1'))

    @staticmethod
    def public(task):
        return {k:v for k,v in task.items() if k!='hidden_answer'}

    @staticmethod
    def judge(task, output):
        return dict(passed=output=={'code':'PASS'} or output=={'code':'REFERENCE'}, category='judged')

    def native(self, *, mode='gain', drift_phase=None, token_mismatch=False):
        def invoke(host,profile,prompt,**kwargs):
            if kwargs.get('inspect'):
                self.assertEqual(prompt,'')
                return {'requested_model':'fake-free'}
            self.calls.append(dict(profile=profile,prompt=prompt,kwargs=kwargs))
            self.assertEqual(kwargs['max_tokens'],runner.BUDGET['max_tokens'])
            metadata=dict(requested_model='fake-free', max_tokens=runner.BUDGET['max_tokens'],
                          max_iterations=runner.BUDGET['max_iterations'],
                          timeout_seconds=runner.BUDGET['timeout_seconds'], native_hermes=True)
            if prompt.startswith('Extract one concise'):
                return dict(metadata,value={'lesson':'Check exact types and boundary conditions.'})
            tasks=json.loads(prompt.split('\nTasks: ',1)[1])
            phase=tasks[0]['id'].split('-')[0]
            advice='Evaluated procedural advice' in prompt
            if drift_phase==phase:
                metadata['requested_model']='changed-model'
            if token_mismatch and phase=='selection':
                metadata['max_tokens']=128
            values={}
            for task in tasks:
                passed=(mode=='tie' or phase=='retention' or advice)
                if mode=='retention_loss' and phase=='retention' and advice:
                    passed=False
                values[task['id']]={'code':'PASS' if passed else 'FAIL'}
            return dict(metadata,value=values)
        return invoke

    def experiment(self):
        return RepositoryExperiments(self.host.directory/'repository-learning.sqlite3')

    def phase_calls(self):
        return [json.loads(c['prompt'].split('\nTasks: ',1)[1])[0]['id'].split('-')[0]
                for c in self.calls if '\nTasks: ' in c['prompt']]

    def test_proposer_gets_training_only_and_matched_arm_budgets(self):
        receipt=runner.study(self.host,self.native(), 'qa',self.vault)
        snapshot=self.host.directory/'study-inputs'/receipt['id']
        self.assertTrue((snapshot/'judge.py').is_file())
        manifest=json.loads((snapshot/'manifest.json').read_text())
        self.assertEqual(len(manifest['tasks']),11)
        self.assertNotIn('NEVER_INCLUDE_PRIVATE_CHECK',json.dumps(manifest))
        proposal=next(c for c in self.calls if c['prompt'].startswith('Extract one concise'))
        self.assertEqual(proposal['profile'],'nina-memory-librarian')
        training=json.loads(proposal['prompt'].split('\n',1)[1])
        self.assertEqual({x['task']['id'] for x in training},{'train-0','train-1'})
        self.assertNotIn('NEVER_INCLUDE_PRIVATE_CHECK',proposal['prompt'])
        for phase in ('selection','retention','final'):
            self.assertNotIn(phase+'-',proposal['prompt'])
            arms=[s for s in receipt['native_sessions'] if s['phase']==phase]
            self.assertEqual({a['arm'] for a in arms},{'baseline','lesson'})
            self.assertEqual({a['requested_model'] for a in arms},{'fake-free'})
            self.assertTrue(all(a['budget']==runner.BUDGET for a in arms))
        self.assertEqual(receipt['result']['status'],'observed_gain')

    def test_no_gain_stops_before_retention_and_final(self):
        receipt=runner.study(self.host,self.native(mode='tie'),'qa',self.vault)
        self.assertEqual(receipt['result']['status'],'no_gain')
        self.assertEqual(self.phase_calls().count('selection'),2)
        self.assertNotIn('retention',self.phase_calls())
        self.assertNotIn('final',self.phase_calls())
        self.assertIsNone(self.experiment().recall('qa','fake-free','judge-fixture-v1'))
        self.assertEqual(self.experiment().summary()['status'],'no_verified_improvement')

    def test_gain_promotes_scoped_advice_and_keeps_repair_artifacts(self):
        receipt=runner.study(self.host,self.native(),'qa',self.vault)
        lesson=self.experiment().recall('qa','fake-free','judge-fixture-v1')
        self.assertEqual(lesson['id'],receipt['result']['lesson_id'])
        self.assertEqual(receipt['result']['final']['wins'],3)
        self.assertEqual(len(receipt['artifacts']),20)
        saved=json.loads((self.host.directory/'latest-repository-study.json').read_text())
        self.assertEqual(saved['id'],receipt['id'])
        self.assertTrue((self.vault/'Journal/nerve'/f"{receipt['id']}.json").exists())

    def test_retention_regression_blocks_final_and_promotion(self):
        receipt=runner.study(self.host,self.native(mode='retention_loss'),'qa',self.vault)
        self.assertEqual(receipt['result']['status'],'no_gain')
        self.assertEqual(receipt['result']['retention']['losses'],3)
        self.assertNotIn('final',self.phase_calls())
        self.assertEqual(self.experiment().summary()['active_lessons'],0)

    def test_model_drift_aborts_with_durable_failed_partial_receipts(self):
        with self.assertRaisesRegex(RuntimeError,'model changed'):
            runner.study(self.host,self.native(drift_phase='selection'),'qa',self.vault)
        self.assertEqual(self.experiment().summary()['status'],'failed')
        saved=json.loads((self.host.directory/'latest-repository-study.json').read_text())
        self.assertEqual(saved['result']['status'],'failed')
        self.assertEqual({a['phase'] for a in saved['artifacts']},{'train'})
        with sqlite3.connect(self.experiment().path) as db:
            event=json.loads(db.execute("SELECT payload FROM events WHERE kind='failed'").fetchone()[0])
        self.assertEqual(len(event['results']),2)
        self.assertTrue(all(r['arm']=='baseline' for r in event['results']))
        self.assertNotIn('final',self.phase_calls())

    def test_token_budget_mismatch_aborts_before_scoring_selection(self):
        with self.assertRaisesRegex(RuntimeError,'budget mismatch'):
            runner.study(self.host,self.native(token_mismatch=True),'qa',self.vault)
        self.assertEqual(self.experiment().summary()['status'],'failed')
        self.assertEqual(self.experiment().summary()['active_lessons'],0)

    def test_failed_study_cannot_recycle_reserved_holdouts(self):
        with self.assertRaises(RuntimeError):
            runner.study(self.host,self.native(drift_phase='selection'),'qa',self.vault)
        self.calls.clear()
        receipt=runner.study(self.host,self.native(),'qa',self.vault)
        self.assertEqual(receipt['result']['status'],'no_fresh_tasks')
        self.assertEqual(self.calls,[])
        self.assertEqual(self.experiment().summary()['status'],'failed')

    def test_progress_callback_failure_is_recorded_as_failed(self):
        def broken_progress():
            raise RuntimeError('dashboard update unavailable')
        with self.assertRaises(RuntimeError):
            runner.study(self.host,self.native(),'qa',self.vault,progress=broken_progress)
        self.assertEqual(self.experiment().summary()['status'],'failed')
        self.assertEqual(self.calls,[])

    def test_reference_preflight_fails_before_native_inference_or_reservation(self):
        with patch.object(runner.bench,'evaluate',return_value={'passed':False,'category':'sandbox_unavailable'}):
            with self.assertRaisesRegex(RuntimeError,'preflight'):
                runner.study(self.host,self.native(),'qa',self.vault)
        self.assertEqual(self.calls,[])
        self.assertEqual(self.experiment().summary()['status'],'not_run')

    def test_replay_monitoring_observes_once_and_rolls_back_paired_regression(self):
        runner.study(self.host,self.native(),'qa',self.vault)
        lesson=self.experiment().recall('qa','fake-free','judge-fixture-v1')
        def regressed(host,profile,prompt,**kwargs):
            if kwargs.get('inspect'):
                return {'requested_model':'fake-free'}
            tasks=json.loads(prompt.split('\nTasks: ',1)[1])
            advice='Evaluated procedural advice' in prompt
            return dict(requested_model='fake-free',max_tokens=runner.BUDGET['max_tokens'],
                        max_iterations=runner.BUDGET['max_iterations'],timeout_seconds=runner.BUDGET['timeout_seconds'],
                        value={t['id']:{'code':'FAIL' if advice else 'PASS'} for t in tasks})
        result=runner.run(self.host,regressed,'qa','final-0')
        self.assertEqual(result['lesson_id'],lesson['id'])
        self.assertTrue(result['monitor']['rollback'])
        self.assertIsNone(self.experiment().recall('qa','fake-free','judge-fixture-v1'))
        second=runner.run(self.host,regressed,'qa','final-0')
        self.assertIsNone(second['lesson_id'])
        self.assertEqual(self.experiment().summary()['rollbacks'],1)

    def second_cohort(self):
        groups={phase:[dict(task,id=task['id']+'-v2',family=task['family']+'-v2')
                       for task in tasks] for phase,tasks in self.groups.items()}
        source=self.root/'cohort.py'
        source.write_text('# independent cohort source\n')
        return SimpleNamespace(dataset=lambda:groups,__file__=str(source))

    def test_changed_contract_and_id_cannot_recycle_function_families(self):
        runner.study(self.host,self.native(mode='tie'),'qa',self.vault)
        for tasks in self.groups.values():
            for task in tasks:
                task['id']+='-renamed'
                task['requirements']+=' changed contract'
        self.calls.clear()
        result=runner.study(self.host,self.native(),'qa',self.vault)
        self.assertEqual(result['result']['status'],'no_fresh_tasks')
        self.assertEqual(self.calls,[])

    def test_automatic_second_cohort_snapshot_then_exhaustion(self):
        runner.study(self.host,self.native(mode='tie'),'qa',self.vault)
        second=self.second_cohort()
        with patch.object(runner,'cohorts',return_value={'v1':runner.bench,'v2':second}):
            result=runner.study(self.host,self.native(mode='tie'),'qa',self.vault)
            self.assertEqual(result['cohort'],'v2')
            snapshot=self.host.directory/'study-inputs'/result['id']
            self.assertEqual((snapshot/'cohort.py').read_bytes(),Path(second.__file__).read_bytes())
            self.assertEqual(json.loads((snapshot/'manifest.json').read_text())['cohort'],'v2')
            self.calls.clear()
            exhausted=runner.study(self.host,self.native(),'qa',self.vault)
            self.assertEqual(exhausted['result']['status'],'no_fresh_tasks')
            self.assertEqual(self.calls,[])

    def test_revision_binds_second_cohort_source_and_v1_manifest(self):
        from hashlib import sha256
        second=self.second_cohort()
        with patch.object(runner,'cohorts',return_value={'v1':runner.bench,'v2':second}):
            original=REAL_REVISION('v2')
            v1=REAL_REVISION('v1')
            self.assertNotEqual(v1,sha256(Path(runner.bench.__file__).read_bytes()).hexdigest())
            self.groups['train'][0]['source']='changed v1 extracted target'
            self.assertNotEqual(v1,REAL_REVISION('v1'))
            v1=REAL_REVISION('v1')
            self.groups['train'][0]['revision']='changed v1 helper revision'
            self.assertNotEqual(v1,REAL_REVISION('v1'))
            Path(second.__file__).write_text('# modified independent cohort source\n')
            self.assertNotEqual(original,REAL_REVISION('v2'))

    def test_revision_binds_dynamic_public_target_and_helper_revision(self):
        second=self.second_cohort()
        with patch.object(runner,'cohorts',return_value={'v1':runner.bench,'v2':second}):
            original=REAL_REVISION('v2')
            second.dataset()['train'][0]['source']='updated dynamic repository target'
            changed_target=REAL_REVISION('v2')
            self.assertNotEqual(original,changed_target)
            second.dataset()['train'][0]['revision']='updated-target-and-helper-digest'
            self.assertNotEqual(changed_target,REAL_REVISION('v2'))

    def test_run_uses_selected_cohort_revision_and_rejects_ambiguous_id(self):
        second=self.second_cohort()
        with patch.object(runner,'cohorts',return_value={'v1':runner.bench,'v2':second}), \
             patch.object(runner,'revision',side_effect=lambda c:'judge-'+c):
            result=runner.run(self.host,self.native(mode='tie'),'qa','train-0-v2')
            self.assertEqual(result['cohort'],'v2')
            self.assertEqual(result['judge_revision'],'judge-v2')
            with self.assertRaises(ValueError):
                runner.run(self.host,self.native(),'qa','train-0-v2',cohort='v1')

    def test_exhausted_automatic_cohorts_clear_same_profile_pending(self):
        runner.study(self.host,self.native(mode='tie'),'qa',self.vault)
        pending=self.host.directory/'pending-repository-study.json'
        pending.write_text(json.dumps({'profile':'qa','cohort':'v1'}))
        result=runner.study(self.host,self.native(),'qa',self.vault)
        self.assertEqual(result['result']['status'],'no_fresh_tasks')
        self.assertFalse(pending.exists())

    def test_insufficient_budget_queues_without_reserving_or_inference(self):
        self.host.path=self.root/'calls.sqlite3'
        day=runner.time.strftime('%Y-%m-%d',runner.time.gmtime())
        with sqlite3.connect(self.host.path) as db:
            db.execute('CREATE TABLE nerve_calls(day TEXT, provider TEXT)')
            db.executemany('INSERT INTO nerve_calls VALUES(?,?)',[(day,'hermes-free')]*13)
        result=runner.study(self.host,self.native(),'qa',self.vault)
        self.assertEqual(result['result'],{'status':'deferred_daily_budget',
                                          'required_sessions':8,'remaining_sessions':7})
        self.assertEqual(self.calls,[])
        self.assertEqual(self.experiment().summary()['status'],'not_run')
        pending=self.host.directory/'pending-repository-study.json'
        self.assertEqual(json.loads(pending.read_text())['cohort'],'v1')
        with sqlite3.connect(self.experiment().path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],0)
        with sqlite3.connect(self.host.path) as db:
            db.execute("UPDATE nerve_calls SET day='2000-01-01'")
        result=runner.study(self.host,self.native(mode='tie'),'qa',self.vault,cohort='v1')
        self.assertEqual(result['result']['status'],'no_gain')
        self.assertFalse(pending.exists())


if __name__=='__main__':
    unittest.main()
