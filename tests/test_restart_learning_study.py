from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import restart_learning_study as restart


def fixture(directory,scenario,arm,start,count):
    fixed = arm.startswith('fixed_')
    strategy = 'trim-lower' if arm in ('candidate','fixed_trim') else 'lower-only'
    cases = restart.study._cases(restart.SEED,scenario)[start:start+count]
    outcomes = [trim==(strategy=='trim-lower') for _,trim in cases]
    return {'scenario':scenario,'arm':arm,'start':start,'count':count,'outcomes':outcomes,
            'strategies':[strategy]*count,'hits':sum(outcomes),'feedback_before':0 if fixed else start,
            'feedback_after':0 if fixed else start+count,'consumed':0 if fixed else start+count,
            'payload_sha256':[restart.study._digest(task) for task,_ in cases]}


class RestartLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_complete_matched_budget_and_report(self):
        report=restart._run(self.root,fixture)
        self.assertEqual(report['status'],'complete')
        self.assertEqual(len(report['calls']),80)
        self.assertEqual(report['completed_pipeline_episodes'],1024)
        self.assertEqual(report['claimed_pipeline_episodes'],1024)
        self.assertEqual(len(report['comparisons']),16)
        self.assertTrue(all(r['equivalent'] for r in report['comparisons']))
        self.assertEqual(json.loads((self.root/'report.json').read_text()),report)
        with self.assertRaises(ValueError): restart._run(self.root,fixture)

    def test_claim_precedes_failure_no_retry(self):
        def fail(*args):
            with sqlite3.connect(self.root/'study.sqlite') as db:
                report=json.loads(db.execute('SELECT report FROM study').fetchone()[0])
            self.assertEqual(report['calls'][0]['status'],'pending')
            self.assertEqual(report['claimed_pipeline_episodes'],32)
            raise TimeoutError('secret')
        report=restart._run(self.root,fail)
        self.assertEqual(report['status'],'failed_consumed')
        self.assertEqual(report['error'],'child_timeout')
        self.assertEqual(report['completed_pipeline_episodes'],0)
        self.assertEqual(len(report['calls']),1)
        self.assertNotIn('secret',json.dumps(report))
        self.assertNotIn('comparisons',report)

    def test_false_reward_rejected(self):
        def bad(*args):
            row=fixture(*args)
            row['outcomes'][0]=not row['outcomes'][0]
            row['hits']=sum(row['outcomes'])
            return row
        report=restart._run(self.root,bad)
        self.assertEqual(report['status'],'failed_consumed')
        self.assertEqual(report['completed_pipeline_episodes'],0)

    def test_drift_consumes_evidence(self):
        original=restart._hashes
        calls=[0]
        def hashes(protocol):
            calls[0]+=1
            result=original(protocol)
            if calls[0]==2: result['restart_learning_study.py']='changed'
            return result
        with patch.object(restart,'_hashes',side_effect=hashes): report=restart._run(self.root,fixture)
        self.assertEqual(report['status'],'failed_consumed')
        self.assertEqual(report['completed_pipeline_episodes'],0)

    def test_restart_divergence_reported_as_failure(self):
        def divergent(directory,scenario,arm,start,count):
            row=fixture(directory,scenario,arm,start,count)
            if count==8 and arm=='candidate':
                row['strategies']=['lower-only']*count
                row['outcomes']=[not trim for _,trim in restart.study._cases(restart.SEED,scenario)[start:start+count]]
                row['hits']=sum(row['outcomes'])
            return row
        report=restart._run(self.root,divergent)
        self.assertEqual(report['status'],'equivalence_failed')
        self.assertFalse(all(row['equivalent'] for row in report['comparisons']))

    def test_real_process_chunks_persist_utility_and_budget(self):
        folder=self.root/'real'
        a=restart._execute(folder,'abrupt','candidate',0,8)
        b=restart._execute(folder,'abrupt','candidate',8,8)
        restart._validate(a,'abrupt','candidate',0,8)
        restart._validate(b,'abrupt','candidate',8,8)
        self.assertEqual(a['feedback_after'],b['feedback_before'])
        self.assertEqual(b['consumed'],16)
        with self.assertRaises(RuntimeError): restart._execute(folder,'abrupt','candidate',8,8)

    def test_revoked_source_not_reapproved(self):
        folder=self.root/'revoked'
        restart._chunk(folder,'stationary','baseline',0,8)
        with sqlite3.connect(folder/'memory.sqlite') as db:
            db.execute("UPDATE trusted_memory_v18 SET status='rejected'")
        with self.assertRaisesRegex(ValueError,'revoked'): restart._chunk(folder,'stationary','baseline',8,8)
        with sqlite3.connect(folder/'memory.sqlite') as db:
            self.assertEqual({r[0] for r in db.execute('SELECT status FROM trusted_memory_v18')},{'rejected'})

    def test_corrupt_source_not_repaired(self):
        folder=self.root/'corrupt'
        restart._chunk(folder,'stationary','baseline',0,8)
        with sqlite3.connect(folder/'memory.sqlite') as db:
            db.execute("UPDATE trusted_memory_v18 SET content='changed'")
        with self.assertRaisesRegex(ValueError,'corrupt'): restart._chunk(folder,'stationary','baseline',8,8)

    def test_existing_database_is_not_modified(self):
        path=self.root/'study.sqlite'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE unrelated(value TEXT)')
            db.execute("INSERT INTO unrelated VALUES ('keep')")
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'fresh empty'):
            restart._run(self.root,fixture)
        self.assertEqual(path.read_bytes(),before)

    def test_precreated_stage_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            stage=self.root/'stationary-baseline-continuous'
            stage.symlink_to(outside,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'fresh empty'):
                restart._run(self.root,fixture)
            self.assertEqual(list(Path(outside).iterdir()),[])
            self.assertFalse((self.root/'study.sqlite').exists())

    def test_bad_identity_and_budget_rejected(self):
        row=fixture(None,'stationary','baseline',0,8)
        for key,value in (('arm','candidate'),('consumed',0),('outcomes',[True]),('payload_sha256',[])):
            with self.subTest(key=key), self.assertRaises(ValueError):
                restart._validate({**row,key:value},'stationary','baseline',0,8)


if __name__=='__main__': unittest.main()
