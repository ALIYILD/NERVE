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
from nerve_awim.memory_gateway import scientific_gpu_dev_study as s
from nerve_awim.memory_gateway import scientific_task_bank as bank

DIGEST='d'*64


class GPUDevelopmentStudyTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.run_dir=self.root/'run';self.journal=self.root/'claims.sqlite';self.bank_dir=self.root/'bank';self.bank_dir.mkdir()
        self.tasks=[bank._item(bytes.fromhex('a'*64),'dev',stratum,index) for stratum in s.STRATA for index in range(20)]
        self.tasks.sort(key=lambda row:(sha256(f'{s.SEED}:order:{row["task_id"]}'.encode()).hexdigest(),row['task_id']))
        (self.bank_dir/'dev.json').write_text(json.dumps(self.tasks));(self.bank_dir/'manifest.json').write_text('fixture manifest')
        (self.bank_dir/'dev.json').chmod(0o600);(self.bank_dir/'manifest.json').chmod(0o600)
        self.pin=s._digest(self.bank_dir/'manifest.json')
        self.proposal={'policy':'candidate_v3'}
        self.binding=dict(bank_manifest_sha256=self.pin,development_sha256=s._digest(self.bank_dir/'dev.json'))
        self.inputs=dict(bank_directory=str(self.bank_dir),bank_manifest_sha256=self.pin,design_directory=str(self.root/'calibration'))
        self.calls=[]
        for name,value in [('sources',{'fixture.py':'f'*64}),('_host_inputs',(self.tasks,self.proposal,self.binding)),
                           ('metadata',{'model':s.transport.MODEL,'digest':DIGEST}),('runtime_version','0.9.1'),('preload',{'wall_seconds':.1})]:
            p=patch.object(s,name,return_value=value);setattr(self,name,p.start());self.addCleanup(p.stop)
        p=patch.object(s.transport,'run',side_effect=self.respond);self.model=p.start();self.addCleanup(p.stop)

    def run_study(self):return s.run(self.run_dir,DIGEST,self.journal,**self.inputs)

    def respond(self,prepared,*,authorize,timeout_seconds):
        self.assertEqual(timeout_seconds,30)
        authorize()
        task=next(row for row in self.tasks if row['query']==prepared['query'])
        with sqlite3.connect(self.run_dir/'claim.sqlite') as db:
            claim=db.execute('SELECT ordinal,task,arm,status FROM calls ORDER BY ordinal DESC LIMIT 1').fetchone()
            report=json.loads(db.execute('SELECT report FROM study').fetchone()[0])
        self.calls.append((task['task_id'],claim[2]))
        self.assertEqual(claim[0],len(self.calls)-1);self.assertEqual(claim[3],'claimed')
        self.assertEqual(report['model_attempts'],len(self.calls))
        self.assertNotIn('expected',prepared);self.assertNotIn('stratum',prepared);self.assertNotIn('split',prepared)
        self.assertTrue(all(set(record)==s.transport.grammar.FIELDS for record in prepared['evidence']))
        raw=json.dumps(dict(status='abstain',entity='',measurement='',value='',unit='',source_id='')) if claim[2]=='baseline' else 'ABSTAIN'
        if claim[2]=='candidate' and task['expected']['status']=='answer':
            alias=next(a for a,f in prepared['aliases'].items() if f['source_id']==task['expected']['source_id'])
            raw=json.dumps({'value':float(task['expected']['value']),'unit':task['expected']['unit'],'source_id':alias})
        authorize()
        return dict(raw_output=raw,finish_reason='stop',usage=dict(prompt_tokens=120,completion_tokens=8,total_tokens=128),
            model=s.transport.MODEL,origin=s.transport.ORIGIN,model_calls=1,model_sampling_seed=s.SEED,input_sha256=prepared['input_sha256'],
            prompt_limit_verified=True,prompt_limit_verification='runtime_usage_after_call',max_prompt_tokens=150,
            review_required=True,synthetic_only=True,model_weights_trained=False)


    def test_registered400_rows160_calls_and_no_dispatch_verification(self):
        p=s.register(self.run_dir,DIGEST,self.journal,**self.inputs)
        self.model.assert_not_called();self.assertEqual(len(p['schedule']),400)
        report=self.run_study();self.assertEqual(report['status'],'complete',report.get('failure'))
        self.assertEqual(len(report['rows']),400);self.assertEqual(self.model.call_count,160)
        self.assertEqual(sum(a=='baseline' for _,a in self.calls),100);self.assertEqual(sum(a=='candidate' for _,a in self.calls),60)
        self.assertTrue(report['summary']['prospective_gate_passed'])
        self.assertFalse(report['promotion_authorized']);self.assertFalse(report['holdout_accessed'])
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in (self.run_dir/'report.json',self.run_dir/'claim.sqlite',self.run_dir/'preregistration.json')}
        self.assertTrue(s.canonical(s.validate_receipt(self.run_dir,DIGEST,self.journal,**self.inputs))==s.canonical(report))
        self.assertTrue(s.canonical(self.run_study())==s.canonical(report));self.assertEqual(self.model.call_count,160)
        self.assertEqual({p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before},before)
        row=next(r for r in report['rows'] if r['arm']=='random');row['raw_output']='not copied'
        raw=s.canonical(report)
        with sqlite3.connect(self.run_dir/'claim.sqlite') as db:db.execute('UPDATE study SET report=?,digest=?',(raw,sha256(raw.encode()).hexdigest()))
        with self.assertRaises(ValueError):self.run_study()
        self.assertEqual(self.model.call_count,160)

    def test_failure_consumes_and_never_emits_verdict(self):
        self.model.side_effect=TimeoutError('fixture')
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed');self.assertNotIn('summary',report)
        self.assertEqual(self.model.call_count,1);self.assertTrue(s.canonical(self.run_study())==s.canonical(report));self.assertEqual(self.model.call_count,1)

    def test_missing_readonly_receipt_does_not_create(self):
        with self.assertRaises(ValueError):s.validate_receipt(self.run_dir,DIGEST,self.journal,**self.inputs)
        self.assertFalse(self.run_dir.exists());self.model.assert_not_called()

    def test_decimal_scoring_and_abstention_components(self):
        task=next(t for t in self.tasks if t['stratum']=='supported-measurement');p=s.prepared_for(task,'candidate')
        alias=next(a for a,f in p['aliases'].items() if f['source_id']==task['expected']['source_id'])
        raw=json.dumps({'value':float(task['expected']['value']),'unit':'mg','source_id':alias})
        score=s.score(raw,task,p);self.assertTrue(score['strict_correct']);self.assertTrue(score['provenance_correct'])
        task=next(t for t in self.tasks if t['stratum']=='conflict');score=s.score('ABSTAIN',task,s.prepared_for(task,'candidate'))
        self.assertTrue(score['strict_correct']);self.assertIsNone(score['value_correct']);self.assertTrue(score['abstention_correct'])
        task=next(t for t in self.tasks if t['stratum']=='entity-decoy');p=s.prepared_for(task,'candidate')
        wrong=next(a for a,f in p['aliases'].items() if f['source_id']!=task['expected']['source_id'])
        result=s.score(json.dumps({'value':float(task['expected']['value']),'unit':'mg','source_id':wrong}),task,p)
        self.assertTrue(result['value_correct']);self.assertTrue(result['unit_correct']);self.assertFalse(result['provenance_correct']);self.assertFalse(result['strict_correct'])

    def test_missing_design_stops_before_claim(self):
        with self.assertRaises(FileNotFoundError):HOST_INPUTS(self.bank_dir,self.pin,self.root/'missing-design')
        self.model.assert_not_called()

    def test_strong_baseline_rejects_nonnumeric_and_rewards_valid_answer(self):
        task=next(t for t in self.tasks if t['stratum']=='supported-measurement')
        prepared=s.prepared_for(task,'baseline')
        self.assertTrue(s.score(json.dumps(task['expected']),task,prepared)['strict_correct'])
        bad=dict(task['expected'],value='not-a-number')
        self.assertFalse(s.score(json.dumps(bad),task,prepared)['strict_correct'])

    def test_component_errors_do_not_erase_other_fields(self):
        task=next(t for t in self.tasks if t['stratum']=='supported-measurement');p=s.prepared_for(task,'candidate')
        alias=next(a for a,f in p['aliases'].items() if f['source_id']==task['expected']['source_id'])
        value={'value':float(task['expected']['value']),'unit':'mg','source_id':'unknown'}
        result=s.score(json.dumps(value),task,p)
        self.assertEqual([result[k] for k in ('value_correct','unit_correct','provenance_correct','strict_correct')],[True,True,False,False])
        value['source_id']=alias;value['extra']=True;result=s.score(json.dumps(value),task,p)
        self.assertTrue(result['provenance_correct']);self.assertFalse(result['strict_correct']);self.assertFalse(result['schema_valid'])
        self.assertFalse(s.score('['*1200+'0'+']'*1200,task,p)['strict_correct'])

    def test_private_and_shared_claim_paths(self):
        self.run_dir.mkdir(mode=0o755)
        with self.assertRaises(ValueError):s.register(self.run_dir,DIGEST,self.journal,**self.inputs)
        self.model.assert_not_called()

    def test_original_three_strata_selection_and_real_dev_only_bank(self):
        real=self.root/'realbank';pin=bank.build(real,host_seed='b'*64)['manifest_sha256']
        calibration=self.root/'cal';calibration.mkdir(mode=0o700);(calibration/'study-context.json').write_text(json.dumps(dict(kind='exploratory_gpu_development',model=s.transport.MODEL,baseline=s.transport.BASELINE_VERSION,candidate='candidate_v3',holdout_authorized=False,promotion_authorized=False,pilot_history='fixture')));(calibration/'study-context.json').chmod(0o600)
        original=bank._read
        def read(path,limit):
            if Path(path).name=='holdout.json':raise AssertionError('holdout opened')
            return original(path,limit)
        with patch.object(bank,'_read',side_effect=read),patch.object(s.policy_gate,'adjudicate',return_value={}),patch.object(s.policy_gate,'authorize',side_effect=lambda policy,*args,purpose='proposal':dict(status='allowed',policy=policy,purpose=purpose,inference_authorized=False,promotion_authorized=False)),patch.object(s.policy_gate,'register_proposal',return_value={'policy':'candidate_v3','permission':{'status':'allowed'},'promotion_authorized':False}):
            # Call original function, not the fixture patch.
            tasks,_,_=HOST_INPUTS(real,pin,calibration)
        self.assertEqual(len(tasks),100)
        self.assertEqual({st:sum(t['stratum']==st for t in tasks) for st in s.STRATA},{st:20 for st in s.STRATA})
        for st in s.STRATA[:3]:
            pool=[bank._item(bytes.fromhex('b'*64),'dev',st,i) for i in range(100)]
            # Registry allocation is balanced100 DEV per stratum.
            pool.sort(key=lambda t:(sha256(f'{s.SEED}:{t["task_id"]}'.encode()).hexdigest(),t['task_id']))
            self.assertEqual({t['task_id'] for t in tasks if t['stratum']==st},{t['task_id'] for t in pool[:20]})

HOST_INPUTS=s._host_inputs
if __name__=='__main__':unittest.main()
