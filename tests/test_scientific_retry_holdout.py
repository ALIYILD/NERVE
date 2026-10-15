import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO
from types import SimpleNamespace
from urllib.request import Request
from urllib.error import URLError,HTTPError
from nerve_awim.memory_gateway import scientific_retry_transport as t
from nerve_awim.memory_gateway import scientific_v3_holdout_v2 as h
from nerve_awim.memory_gateway import scientific_task_bank as bank


def database(path):
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE requests(row_index INTEGER PRIMARY KEY,request_sha TEXT,envelope TEXT)')
    db.execute('CREATE TABLE attempts(row_index INTEGER,attempt INTEGER,request_sha TEXT,status TEXT,timeout REAL,elapsed REAL,PRIMARY KEY(row_index,attempt))')
    return db


class RetryTests(unittest.TestCase):
    def test_timeouts_from_recorded_dev(self):
        p=t.policy()
        self.assertEqual(p['per_attempt_timeout_seconds']['baseline'],53.59400160302175)
        self.assertEqual(p['per_attempt_timeout_seconds']['candidate'],83.22454607987311)
        self.assertEqual(p['max_attempts_per_logical_call'],3)

    def test_retry_exact_bytes_and_durable_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            db=database(Path(directory)/'db');seen=[]
            class Opener:
                def open(self,req,*,timeout):
                    seen.append(t.envelope(req))
                    self_assert=db.execute("SELECT COUNT(*) FROM attempts WHERE status='claimed'").fetchone()[0]
                    if self_assert!=1:raise AssertionError('journal before dispatch')
                    if len(seen)<3:raise URLError(TimeoutError('fixture timeout'))
                    return BytesIO(b'{"success":true}')
            opener=t.RetryOpener(Opener(),db,0,83.22454607987311,lambda:None,directory)
            req=Request('http://127.0.0.1:11434/v1/chat/completions',data=b'{"seed":20261015}',headers={'Content-Type':'application/json'},method='POST')
            with opener.open(req,timeout=30) as response:self.assertEqual(response.read(),b'{"success":true}')
            self.assertEqual(seen,[seen[0]]*3)
            self.assertEqual([r[0] for r in db.execute('SELECT status FROM attempts ORDER BY attempt')],['timeout','timeout','complete'])
            db.close()

    def test_no_fourth_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            db=database(Path(directory)/'db')
            class Opener:
                def open(self,*args,**kw):raise TimeoutError('fixture')
            o=t.RetryOpener(Opener(),db,0,53.59400160302175,lambda:None,directory)
            with self.assertRaises(TimeoutError):o.open(Request('http://127.0.0.1/',data=b'x'),timeout=30)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],3)
            db.close()

    def test_read_timeout_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            db=database(Path(directory)/'db');calls=[]
            class Bad(BytesIO):
                def read(self,*args):raise TimeoutError('read')
            class Opener:
                def open(self,*args,**kw):
                    calls.append(1);return Bad() if len(calls)==1 else BytesIO(b'ok')
            with t.RetryOpener(Opener(),db,0,60,lambda:None,directory).open(Request('http://127.0.0.1/',data=b'x'),timeout=30) as response:
                self.assertEqual(response.read(),b'ok')
            self.assertEqual(len(calls),2);db.close()

    def test_non_timeout_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            db=database(Path(directory)/'db')
            class Opener:
                def open(self,*args,**kw):raise HTTPError('http://127.0.0.1',500,'fixture',{},None)
            with self.assertRaises(HTTPError):
                t.RetryOpener(Opener(),db,0,60,lambda:None,directory).open(Request('http://127.0.0.1/',data=b'x'),timeout=30)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],1);db.close()

    def test_infrastructure_distinct_and_admission_fail_closed(self):
        self.assertEqual(h.aggregate([],complete=False)['verdict'],'incomplete_infrastructure')
        base=dict(status='complete',logical_model_calls=160,attempts=160,timeouts=0,competing_workload_observed=False)
        self.assertTrue(h.dry_ready(base))
        for field,value in [('status','failed_consumed'),('logical_model_calls',159),('attempts',161),('timeouts',1),('competing_workload_observed',True)]:
            self.assertFalse(h.dry_ready(dict(base,**{field:value})))

    def test_observation_detects_competing_process(self):
        raw='PID PPID %CPU COMM\n1 0 0 /sbin/launchd\n9001 1 40 /usr/local/bin/git\n9002 1 30 /Applications/Ollama.app/ollama\n9003 1 20 /System/WindowServer\n9004 1 40 /System/Virtualization/com.apple.Virtualization.VirtualMachine\n'
        with patch.object(h.subprocess,'check_output',return_value=raw):
            result=h.observe()
        self.assertFalse(result['qualifies']);self.assertEqual([r['name'] for r in result['competing_processes']],['git','com.apple.Virtualization.VirtualMachine'])

    def test_full_dry_harness_and_no_retry_qualification(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);b=root/'bank';parts=root/'parts';dry=root/'dry'
            built=bank.build(b,host_seed='cd'*32)
            with patch.object(h.old,'MANIFEST_PIN',built['manifest_sha256']):h.old.register(parts,b)
            development=json.loads((b/'dev.json').read_text())
            tasks=[]
            for s in h.old.STRATA:tasks.extend([r for r in development if r['stratum']==s][:20])
            idle=dict(qualifies=True,competing_processes=[],rule='fixture')
            with patch.object(h,'observe',return_value=idle),patch.object(h.dev,'_host_inputs',return_value=(tasks,{},{})):
                p=h.register(dry,kind='dry',partition_directory=parts,calibration_directory=root)
            model={'model':h.dev.pilot.MODEL,'digest':p['transport']['model_digest']}
            real=t.run
            def wrapper(prepared,**kw):
                if prepared['arm']=='baseline':raw='ABSTAIN'
                else:
                    alias,fact=next((a,r) for a,r in prepared['aliases'].items() if r['entity'].startswith('N') and r['measurement']=='mass' and r['unit']=='mg')
                    raw=json.dumps(dict(value=float(fact['value']),unit='mg',source_id=alias))
                wire=json.dumps(dict(model=model['model'],choices=[dict(finish_reason='stop',message=dict(role='assistant',content=raw))],usage=dict(prompt_tokens=80,completion_tokens=20,total_tokens=100))).encode()
                class Opener:
                    def open(self,request,*,timeout):return BytesIO(wire)
                with patch.object(h.dev.transport.calibration,'_adapter',return_value=SimpleNamespace(_opener=Opener())):
                    return real(prepared,**kw)
            with patch.object(h,'observe',return_value=idle),patch.object(h.dev,'metadata',return_value=model),patch.object(h.dev,'runtime_version',return_value='fixture'),patch.object(h.dev,'preload',return_value={'wall_seconds':0}),patch.object(t,'run',side_effect=wrapper):
                result=h.run(dry)
            self.assertTrue(result['slice2_admission_passed']);self.assertEqual(result['attempts'],160);self.assertEqual(result['timeouts'],0)
            self.assertEqual(h.verify(dry),result)
            with self.assertRaises(ValueError):h.run(dry)
            with patch.object(h,'observe',return_value=idle):
                registered=h.register(root/'slice2',kind='slice2',partition_directory=parts,calibration_directory=root,dry_directory=dry)
            self.assertEqual(registered['kind'],'slice2')
            self.assertEqual((parts/'slice2.json').stat().st_mode & 0o777,0)
            self.assertNotIn('private_tasks',result)


if __name__=='__main__':unittest.main()
