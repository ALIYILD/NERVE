"""Mocked transport and development fixtures; no real model or holdout reads."""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_compact_dev_study as s
from nerve_awim.memory_gateway import scientific_task_bank as bank

DIGEST='d'*64


class CompactDevStudyTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.run_dir=self.root/'run';self.journal=self.root/'claims.sqlite';self.bank_dir=self.root/'bank';self.bank_dir.mkdir()
        self.tasks=[bank._item(bytes.fromhex('a'*64),'dev',stratum,index) for stratum in s.STRATA for index in range(20)]
        self.tasks.sort(key=lambda row:(sha256(f'{s.SEED}:order:{row["task_id"]}'.encode()).hexdigest(),row['task_id']))
        (self.bank_dir/'dev.json').write_text(json.dumps(self.tasks));(self.bank_dir/'manifest.json').write_text('fixture manifest')
        (self.bank_dir/'dev.json').chmod(0o600);(self.bank_dir/'manifest.json').chmod(0o600)
        self.pin=s._digest(self.bank_dir/'manifest.json')
        self.proposal=dict(candidate=dict(s.grammar.candidates.SPACE['conflict_check']),candidate_sha256='c'*64,hypothesis_sha256='b'*64,
                           hypothesis={'mutation':'conflict_check'})
        self.binding=dict(bank_manifest_sha256=self.pin,development_sha256=s._digest(self.bank_dir/'dev.json'),screening_sha256='e'*64,
                          hypothesis_sha256='b'*64,candidate_sha256='c'*64,excluded_prior_input_sha256=[])
        self.inputs=dict(bank_directory=str(self.bank_dir),bank_manifest_sha256=self.pin,screening_directory=str(self.root/'screen'),
                         registration_directory=str(self.root/'registered'),history_directory=str(self.root/'history'))
        self.calls=[]
        for name,value in [('sources',{'fixture.py':'f'*64,'src/nerve_awim/memory_gateway/scientific_compact_dev_transport.py':'e'*64}),('_host_inputs',(self.tasks,self.proposal,self.binding)),
                           ('metadata',{'model':s.pilot.MODEL,'digest':DIGEST}),('runtime_version','0.9.1'),('preload',{'wall_seconds':.1})]:
            p=patch.object(s,name,return_value=value);setattr(self,name,p.start());self.addCleanup(p.stop)
        p=patch.object(s.transport,'run',side_effect=self.respond);self.model=p.start();self.addCleanup(p.stop)

    def run_study(self):return s.run(self.run_dir,DIGEST,self.journal,**self.inputs)

    def respond(self,prepared,*,authorize):
        authorize()
        task=next(row for row in self.tasks if row['query']==prepared['query'])
        with sqlite3.connect(self.run_dir/'claim.sqlite') as db:
            claim=db.execute('SELECT ordinal,task,arm,status FROM calls ORDER BY ordinal DESC LIMIT 1').fetchone()
            report=json.loads(db.execute('SELECT report FROM study').fetchone()[0])
        self.calls.append((task['task_id'],claim[2]))
        self.assertEqual(claim[0],len(self.calls)-1);self.assertEqual(claim[3],'claimed')
        self.assertEqual(report['model_attempts'],len(self.calls))
        self.assertNotIn('expected',prepared);self.assertNotIn('stratum',prepared);self.assertNotIn('split',prepared)
        self.assertTrue(all(set(record)==s.grammar.FIELDS for record in prepared['evidence']))
        raw='ABSTAIN'
        if claim[2]=='candidate' and task['expected']['status']=='answer':
            alias=next(a for a,f in prepared['aliases'].items() if f['source_id']==task['expected']['source_id'])
            raw=f'{task["expected"]["value"]}|{task["expected"]["unit"]}|{alias}'
        authorize()
        return dict(raw_output=raw,usage=dict(prompt_tokens=120,completion_tokens=8,total_tokens=128),
            model=s.pilot.MODEL,origin=s.pilot.ORIGIN,model_calls=1,model_sampling_seed=s.SEED,input_sha256=prepared['input_sha256'],
            prompt_limit_verified=True,prompt_limit_verification='runtime_usage_after_call',max_prompt_tokens=150,
            review_required=True,synthetic_only=True,model_weights_trained=False)

    def test_full_fixed_four_arm_study_and_actual_usage(self):
        report=self.run_study();self.assertEqual(report['status'],'complete',report.get('failure'))
        self.assertEqual(len(report['rows']),240);self.assertEqual(len(self.calls),100)
        self.assertEqual(sum(arm=='baseline' for _,arm in self.calls),60);self.assertEqual(sum(arm=='candidate' for _,arm in self.calls),40)
        self.assertEqual(report['summary']['measured_tokens']['prompt_tokens'],12000)
        self.assertEqual(report['summary']['verdict'],'candidate_requires_review')
        self.assertFalse(report['promotion_authorized']);self.assertFalse(report['holdout_accessed'])
        self.assertEqual(report['summary']['generalization_verdict'],'insufficient_power')
        self.assertEqual(self.metadata.call_count,2);self.assertEqual(self.runtime_version.call_count,2);self.preload.assert_called_once()
        for arm in report['summary']['arms']:
            self.assertEqual(arm['count'],60)
            self.assertEqual({st:values['count'] for st,values in arm['strata'].items()},dict.fromkeys(s.STRATA,20))
        for row in report['rows']:
            if row['arm'] in ('always_abstain','random') or row['route']=='candidate_conflict_rule':
                self.assertEqual(row['model_calls'],0);self.assertIsNone(row['usage'])

    def test_terminal_resume_no_calls_stable_export(self):
        report=self.run_study();path=self.run_dir/'report.json';before=path.read_bytes();mtime=path.stat().st_mtime_ns
        self.model.side_effect=AssertionError('no model');self.metadata.side_effect=AssertionError('no metadata')
        resumed=s.validate_receipt(self.run_dir,DIGEST,self.journal,**self.inputs)
        self.assertEqual(s.canonical(report),s.canonical(resumed));self.assertEqual(before,path.read_bytes());self.assertEqual(mtime,path.stat().st_mtime_ns)

    def test_prompt_overbudget_preserves_unscored_response_stops_and_consumes(self):
        self.model.side_effect=s.transport.PromptBudgetExceeded('raw over budget',dict(prompt_tokens=151,completion_tokens=8,total_tokens=159))
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed')
        self.assertEqual(report['model_attempts'],1);self.assertEqual(self.model.call_count,1)
        self.assertEqual(report['over_budget_response']['raw_output'],'raw over budget')
        self.assertNotIn('score',report['over_budget_response'])
        self.assertEqual(s.canonical(self.run_study()),s.canonical(report));self.assertEqual(self.model.call_count,1)

    def test_interruption_and_missing_receipt_never_restart_dispatch(self):
        with self.assertRaises(ValueError):s.validate_receipt(self.run_dir,DIGEST,self.journal,**self.inputs)
        self.model.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.run_study()
        self.assertEqual(self.run_study()['status'],'failed_consumed');self.assertEqual(self.model.call_count,1)

    def test_input_paths_cannot_overlap_output_or_claim_journal(self):
        with self.assertRaisesRegex(ValueError,'separate_study'):
            s.run(self.bank_dir/'nested',DIGEST,self.journal,**self.inputs)
        self.model.assert_not_called()
        self.assertFalse((self.bank_dir/'nested').exists())

    def test_same_compact_model_payload_for_both_policies(self):
        task=next(row for row in self.tasks if row['stratum']=='supported-measurement')
        first=s.transport.prepare(task['query'],task['evidence'])
        second=s.transport.prepare(task['query'],task['evidence'])
        self.assertEqual(s.canonical(first),s.canonical(second))
        unit=next(row for row in self.tasks if row['stratum']=='unit-mismatch')
        prepared=s.transport.prepare(unit['query'],unit['evidence'])
        alias,record=next(iter(prepared['aliases'].items()))
        raw=f'{record["value"]}|{record["unit"]}|{alias}'
        self.assertEqual(s.transport.decode(raw,prepared)['unit'],'g')
        self.assertFalse(s.score(raw,unit,prepared)['strict_correct'])

    def test_unknown_output_fails_format_without_repair(self):
        task=self.tasks[0];prepared=s.transport.prepare(task['query'],task['evidence'])
        self.assertEqual(s.score('answer is ABSTAIN',task,prepared),dict(format_valid=False,strict_correct=False))
        random=s._random_raw(task,prepared)
        self.assertEqual(random,s._random_raw(task,prepared))

    def test_candidate_route_uses_evidence_not_stratum_answer_or_split(self):
        task=next(row for row in self.tasks if row['stratum']=='conflict')
        changed=dict(task,stratum='supported-measurement',expected={'status':'answer'},split='anything')
        self.assertEqual(s._route(changed,'candidate'),'candidate_conflict_rule')
        self.assertEqual(s._route(changed,'baseline'),'model')

    def test_metadata_mismatch_blocks_all_calls(self):
        self.metadata.return_value={'model':s.pilot.MODEL,'digest':'e'*64}
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed');self.model.assert_not_called()

    def test_external_replay_and_claim_tamper_refused(self):
        self.run_study()
        with self.assertRaises((ValueError,sqlite3.IntegrityError)):
            s.run(self.root/'other',DIGEST,self.journal,**self.inputs)
        with sqlite3.connect(self.run_dir/'claim.sqlite') as db:db.execute("UPDATE calls SET status='claimed' WHERE ordinal=0")
        with self.assertRaises(ValueError):s.validate_receipt(self.run_dir,DIGEST,self.journal,**self.inputs)

    def test_raw_score_control_tamper_rejected_even_rehashed(self):
        self.run_study()
        with sqlite3.connect(self.run_dir/'claim.sqlite') as db:
            report=json.loads(db.execute('SELECT report FROM study').fetchone()[0])
            row=next(r for r in report['rows'] if r['arm']=='random');row['raw_output']='forged'
            raw=s.canonical(report);db.execute('UPDATE study SET report=?,digest=?',(raw,sha256(raw.encode()).hexdigest()))
        with self.assertRaises(ValueError):s.validate_receipt(self.run_dir,DIGEST,self.journal,**self.inputs)

    def test_holdout_status_and_seed_never_touched_by_host_loader(self):
        screen=self.root/'screen';screen.mkdir();screened={'status':'screened','decision':{'allowed':[self.proposal]}}
        (screen/'report.json').write_text(json.dumps(screened));(screen/'report.json').chmod(0o600)
        class Bank:
            def __init__(self,*args,**kwargs):pass
            def development(inner,actor):return self.tasks
            def status(inner):raise AssertionError('must not inspect holdout via status')
            def holdout(inner,*args):raise AssertionError('holdout forbidden')
        original=s._host_inputs
        # The patched function from setUp has no evaluator access. Re-load the
        # original function saved before patching to inspect actual loader logic.
        with patch.object(s,'ScientificTaskBank',Bank),patch.object(s.screening,'run',return_value=screened):
            rows,proposal,binding=HOST_INPUTS(**self.inputs)
        self.assertEqual(len(rows),60);self.assertEqual({r['split'] for r in rows},{'dev'})
        expected=[]
        for st in s.STRATA:
            expected.extend(sorted([r for r in self.tasks if r['stratum']==st],key=lambda r:(sha256(f'{s.SEED}:{r["task_id"]}'.encode()).hexdigest(),r['task_id']))[:20])
        self.assertEqual({r['task_id'] for r in rows},{r['task_id'] for r in expected})

    def test_failed_summary_and_predispatch_counters_rejected(self):
        self.model.side_effect=RuntimeError('fixture transport failure')
        original=self.run_study()
        for update in ({'summary':{}},{'metadata_attempts':0},{'version_attempts':0},
                       {'version_before':'bad version'},{'preload':{'wall_seconds':float('inf')}}):
            report=dict(original,**update)
            with sqlite3.connect(self.run_dir/'claim.sqlite') as db:
                with self.assertRaises(ValueError):s._validate(db,report,original['protocol'],self.tasks)

    def test_returned_model_seed_mismatch_consumes_once(self):
        def changed(prepared,**kwargs):
            response=self.respond(prepared,**kwargs);response['model_sampling_seed']=0;return response
        self.model.side_effect=changed
        report=self.run_study()
        self.assertEqual(report['status'],'failed_consumed');self.assertNotIn('summary',report)
        self.assertEqual(report['model_attempts'],1);self.assertEqual(self.model.call_count,1)

    def test_returned_model_identity_mismatch_consumes_once(self):
        def changed(prepared,**kwargs):
            response=self.respond(prepared,**kwargs);response['model']='another';return response
        self.model.side_effect=changed
        self.assertEqual(self.run_study()['status'],'failed_consumed');self.assertEqual(self.model.call_count,1)

    def test_policy_hash_binds_transport_source_and_resume_protocol(self):
        pins=dict(self.sources.return_value)
        first=s._policies(self.proposal,DIGEST,pins)
        pins['src/nerve_awim/memory_gateway/scientific_compact_dev_transport.py']='a'*64
        self.assertTrue(all(first[a]!=s._policies(self.proposal,DIGEST,pins)[a] for a in s.ARMS))
        self.model.side_effect=RuntimeError('fixture');self.run_study()
        self.sources.return_value=pins
        with self.assertRaises(ValueError):s.validate_receipt(self.run_dir,DIGEST,self.journal,**self.inputs)
        self.assertEqual(self.model.call_count,1)

    def test_readonly_validator_rejects_running_without_mutation(self):
        self.model.side_effect=RuntimeError('fixture');self.run_study()
        path=self.run_dir/'claim.sqlite'
        with sqlite3.connect(path) as db:
            report=json.loads(db.execute('SELECT report FROM study').fetchone()[0]);report['status']='running';report.pop('failure')
            raw=s.canonical(report);db.execute('UPDATE study SET report=?,digest=?',(raw,sha256(raw.encode()).hexdigest()))
        before=path.read_bytes();publication=(self.run_dir/'report.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'existing_terminal_receipt_required'):
            s.validate_receipt(self.run_dir,DIGEST,self.journal,**self.inputs)
        self.assertEqual(path.read_bytes(),before);self.assertEqual((self.run_dir/'report.json').read_bytes(),publication)
        self.assertEqual(self.model.call_count,1)

    def test_cli_open_guard_blocks_only_fixture_holdout_and_seed(self):
        fixture=self.root/'guard-bank';fixture.mkdir()
        blocked=[fixture/'holdout.json',Path(str(fixture)+'.seed')]
        allowed=fixture/'dev.json'
        for path in blocked+[allowed]:path.write_text('synthetic fixture')
        code="""
import runpy,sys,types
stub=types.ModuleType('nerve_awim.memory_gateway.scientific_compact_dev_study')
stub.run=lambda *args,**kwargs:None
sys.modules[stub.__name__]=stub
namespace=runpy.run_path(sys.argv[1])
result=namespace['install_development_file_guard'](sys.argv[2])
assert result['enabled'] is True
for name in (sys.argv[2]+'/holdout.json',sys.argv[2]+'.seed'):
    try:
        open(name).read()
    except PermissionError as error:
        assert str(error)=='development_only_file_guard'
    else:
        raise AssertionError('protected fixture was opened')
assert open(sys.argv[2]+'/dev.json').read()=='synthetic fixture'
"""
        result=subprocess.run([sys.executable,'-c',code,str(s.pilot.ROOT/'scripts/run_scientific_compact_dev_study.py'),str(fixture)],
                              capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)


HOST_INPUTS=s._host_inputs
if __name__=='__main__':unittest.main()
