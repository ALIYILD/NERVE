"""Mocked transport, actual authoritative gateway, run journal and utility."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import scientific_model_learning as subject

DIGEST='d'*64


class ScientificModelLearningTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.calls=[]
        metadata=patch.object(subject,'metadata',return_value={'model':subject.MODEL,'digest':DIGEST})
        self.metadata=metadata.start();self.addCleanup(metadata.stop)
        preload=patch.object(subject,'preload',return_value={'wall_seconds':.1})
        self.preload=preload.start();self.addCleanup(preload.stop)
        transport=patch.object(subject.LocalInferenceAdapter,'_model_response',autospec=True,side_effect=self.respond)
        self.transport=transport.start();self.addCleanup(transport.stop)

    def respond(self,adapter,query,context):
        task_id=next(key for key,task in subject.tasks.TASKS.items() if query.endswith(task['query']))
        self.calls.append((adapter.strategy,task_id,query,context))
        with sqlite3.connect(self.root/'memory.sqlite') as db:
            claimed=db.execute('SELECT claimed FROM memory_automatic_runs_v1').fetchone()[0]
            pending=db.execute("SELECT COUNT(*) FROM memory_automatic_episodes_v1 WHERE status='pending'").fetchone()[0]
            report=json.loads(db.execute('SELECT report FROM scientific_model_runs_v1').fetchone()[0])
        self.assertEqual(claimed,len(self.calls));self.assertEqual(pending,1)
        self.assertEqual(report['inference_attempts'],len(self.calls))
        output=subject.tasks.TASKS[task_id]['expected'] if adapter.strategy=='checklist' else 'ABSTAIN'
        return output,dict(prompt_tokens=80,completion_tokens=12,total_tokens=92)

    def run_pilot(self):return subject.run(self.root,DIGEST)

    def test_eight_actual_adapter_calls_claimed_scored_and_persistently_ranked(self):
        report=self.run_pilot()
        self.assertEqual(report['status'],'complete',report)
        self.assertEqual(len(self.calls),8)
        self.assertEqual(self.metadata.call_count,2);self.preload.assert_called_once()
        self.assertEqual(report['ranking'][0]['strategy'],'checklist')
        self.assertEqual(report['ranking'][0]['observations'],4)
        self.assertEqual(report['ranking'][0]['training_utility'],5/6)
        self.assertEqual(report['summary']['always_abstain_control_correct_per_four_tasks'],2)
        self.assertEqual(report['baseline_strategy'],'direct')
        self.assertFalse(report['promotion_authorized'])

    def test_prompt_has_only_registered_prefix_query_evidence_without_answer_key(self):
        report=self.run_pilot();self.assertEqual(report['status'],'complete')
        for strategy,task_id,query,context in self.calls:
            self.assertEqual(query,subject.tasks.STRATEGIES[strategy]+'\n'+subject.tasks.TASKS[task_id]['query'])
            self.assertNotIn('"expected"',context)
            if subject.tasks.TASKS[task_id]['expected']!='ABSTAIN':
                self.assertNotIn(subject.tasks.TASKS[task_id]['expected'],query)
                self.assertNotIn(subject.tasks.TASKS[task_id]['expected'],context)
        for task_id in subject.tasks.TASKS:
            rows=[row for row in report['rows'] if row['task_id']==task_id]
            self.assertEqual(rows[0]['evidence_ids'],rows[1]['evidence_ids'])
            self.assertEqual(rows[0]['source_digest'],rows[1]['source_digest'])

    def test_complete_resume_no_model_metadata_or_preload_calls(self):
        report=self.run_pilot()
        with patch.object(subject,'metadata',side_effect=AssertionError('no metadata')),patch.object(subject,'preload',side_effect=AssertionError('no preload')),patch.object(subject.StrategyInference,'respond',side_effect=AssertionError('no model')):
            restarted=self.run_pilot()
        self.assertEqual(subject._json(report),subject._json(restarted))

    def test_real_fresh_process_resume_validates_utility_without_network(self):
        report=self.run_pilot();self.assertEqual(report['status'],'complete')
        code='''import json,sys
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_model_learning as s
with patch.object(s,'metadata',side_effect=AssertionError('network forbidden')),patch.object(s,'preload',side_effect=AssertionError('network forbidden')),patch.object(s.StrategyInference,'respond',side_effect=AssertionError('network forbidden')):
 print(json.dumps(s.run(sys.argv[1],sys.argv[2]),sort_keys=True))
'''
        process=subprocess.run([sys.executable,'-c',code,str(self.root),DIGEST],check=True,capture_output=True,text=True,timeout=30)
        self.assertEqual(subject._json(json.loads(process.stdout)),subject._json(report))

    def test_first_transport_failure_stops_and_remains_consumed(self):
        self.transport.side_effect=RuntimeError('transport unavailable')
        report=self.run_pilot()
        self.assertEqual(report['status'],'failed_consumed')
        self.assertEqual(report['inference_attempts'],1)
        self.assertTrue(report['feedback_invalidated'])
        with self.assertRaisesRegex(ValueError,'consumed'):self.run_pilot()
        self.assertEqual(self.transport.call_count,1)

    def test_wrong_model_digest_blocks_all_inference(self):
        self.metadata.return_value={'model':subject.MODEL,'digest':'a'*64}
        report=self.run_pilot()
        self.assertEqual(report['status'],'failed_consumed')
        self.transport.assert_not_called();self.preload.assert_not_called()

    def test_post_run_digest_change_quarantines_all_rewards(self):
        self.metadata.side_effect=[{'model':subject.MODEL,'digest':DIGEST},{'model':subject.MODEL,'digest':'a'*64}]
        report=self.run_pilot()
        self.assertEqual(report['status'],'failed_consumed')
        with sqlite3.connect(self.root/'memory.sqlite') as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM memory_utility WHERE status='judged'").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM memory_utility WHERE status='study_invalidated'").fetchone()[0],8)

    def test_source_change_after_dispatch_quarantines_prior_feedback(self):
        original=subject.sources; pins=original()
        def pins_now():return pins if len(self.calls)<2 else {**pins,'changed':'x'}
        with patch.object(subject,'sources',side_effect=pins_now):report=self.run_pilot()
        self.assertEqual(report['status'],'failed_consumed')
        self.assertEqual(len(self.calls),2)
        with sqlite3.connect(self.root/'memory.sqlite') as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM memory_utility WHERE status='judged'").fetchone()[0],0)

    def test_invalid_usage_stops_without_reward(self):
        self.transport.side_effect=lambda *args:('ABSTAIN',{'completion_tokens':1})
        report=self.run_pilot()
        self.assertEqual(report['status'],'failed_consumed')
        self.assertEqual(report['inference_attempts'],1)
        with sqlite3.connect(self.root/'memory.sqlite') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM memory_utility').fetchone()[0],0)

    def test_claim_and_feedback_tampering_prevents_completed_resume(self):
        self.assertEqual(self.run_pilot()['status'],'complete')
        with sqlite3.connect(self.root/'memory.sqlite') as db:
            db.execute("UPDATE memory_automatic_episodes_v1 SET status='pending' WHERE episode='science-0'")
        with self.assertRaisesRegex(ValueError,'persistent_episode_claim_changed'):self.run_pilot()

    def test_revoked_strategy_and_foreign_reader_cannot_credit_output(self):
        report=self.run_pilot();self.assertEqual(report['status'],'complete')
        gateway,learning,proposer,reviewer,reader=subject._state(self.root/'memory.sqlite')
        foreign=gateway.ledger.authority.issue('other','model-research',permissions=('read',))
        with self.assertRaises(PermissionError):
            subject.ScientificLearningRun(learning,foreign,self.root/'memory.sqlite',subject.REVISION,max_episodes=8,max_failures=8)
        gateway.revoke(reviewer,report['strategy_ids']['direct'],scope=subject.SCOPE,evaluator_id='revoked-test')
        with self.assertRaises(ValueError):self.run_pilot()

    def test_repeated_pair_claim_and_budget_are_enforced(self):
        self.assertEqual(self.run_pilot()['status'],'complete')
        gateway,learning,_,_,reader=subject._state(self.root/'memory.sqlite')
        runner=subject.ScientificLearningRun(learning,reader,self.root/'memory.sqlite',subject.REVISION,max_episodes=8,max_failures=8)
        with self.assertRaisesRegex(ValueError,'budget exhausted'):runner._claim('new-episode','anything')
        with self.assertRaises(ValueError):subject.run(self.root,'bad-digest')

    def test_interruption_preserves_consumption_and_quarantines_rewards(self):
        original=self.respond
        def interrupt(*args):
            if len(self.calls)==1:raise KeyboardInterrupt()
            return original(*args)
        self.transport.side_effect=interrupt
        with self.assertRaises(KeyboardInterrupt):self.run_pilot()
        with sqlite3.connect(self.root/'memory.sqlite') as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM memory_utility WHERE status='judged'").fetchone()[0],0)
            report=json.loads(db.execute('SELECT report FROM scientific_model_runs_v1').fetchone()[0])
        self.assertEqual(report['status'],'failed_consumed')
        with self.assertRaisesRegex(ValueError,'consumed'):self.run_pilot()

    def test_reopening_hard_interrupted_checkpoint_quarantines_without_calls(self):
        report=self.run_pilot();report['status']='running'
        subject._save(self.root/'memory.sqlite',report['protocol'],report)
        with patch.object(subject,'metadata',side_effect=AssertionError('no network')):
            with self.assertRaisesRegex(ValueError,'consumed'):self.run_pilot()
        with sqlite3.connect(self.root/'memory.sqlite') as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM memory_utility WHERE status='judged'").fetchone()[0],0)

    def test_missing_source_after_calls_still_quarantines_rewards(self):
        original=subject.sources
        def checked():
            if len(self.calls)>=2:raise FileNotFoundError('fixture source disappeared')
            return original()
        with patch.object(subject,'sources',side_effect=checked):report=self.run_pilot()
        self.assertEqual(report['status'],'failed_consumed')
        self.assertTrue(report['feedback_invalidated'])
        with sqlite3.connect(self.root/'memory.sqlite') as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM memory_utility WHERE status='judged'").fetchone()[0],0)


if __name__=='__main__':unittest.main()
