"""Real predecessor and coordinator claims; model and child dispatch are fixtures."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_format_research_coordinator as coordinator

smoke=coordinator.smoke
DIGEST='d'*64
REAL_CHILD_RUN=coordinator.study.run
REAL_CHILD_VALIDATE=coordinator.study.validate_receipt


def child_report():
    rows=[]
    for task in ('supported','unit_mismatch'):
        for constrained in (False,True):
            output=(smoke.canonical(smoke.EXPECTED) if task=='supported' else smoke.canonical(smoke.execution.ABSTAIN)) if constrained else 'Some prose'
            rows.append(dict(task_id=task,constrained=constrained,response={'raw_output':output},
                score=dict(schema_valid=constrained,format_valid=constrained,strict_correct=constrained)))
    return dict(status='complete',rows=rows)


class ScientificFormatResearchCoordinatorTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.parent=self.base/'smoke';self.parent_journal=self.base/'smoke.sqlite'
        self.root=self.base/'coordinator';self.journal=self.base/'coordinator.sqlite'
        self.child=self.base/'study';self.child_journal=self.base/'study.sqlite'
        def response(config,query,evidence,*,authorize,constrained):
            value=smoke.execution.execute(config,query,evidence,lambda request:'The mass is 32.6 mg.',authorize=authorize)
            return dict(value,model=smoke.pilot.MODEL,origin=smoke.pilot.ORIGIN,constrained=False,
                usage={'prompt_tokens':10,'completion_tokens':10,'total_tokens':20})
        with patch.object(smoke,'metadata',return_value={'model':smoke.pilot.MODEL,'digest':DIGEST}),patch.object(smoke,'runtime_version',return_value='fixture'),patch.object(smoke,'preload',return_value={}),patch.object(smoke.transport,'run',side_effect=response):
            result=smoke.run(self.parent,DIGEST,self.parent_journal)
        self.assertEqual(result['status'],'complete');self.assertFalse(result['score']['format_valid'])
        self.report=child_report()
        dispatcher=patch.object(coordinator.study,'run',side_effect=self.dispatch)
        self.dispatcher=dispatcher.start();self.addCleanup(dispatcher.stop)
        validator=patch.object(coordinator.study,'validate_receipt',side_effect=self.validate)
        self.validator=validator.start();self.addCleanup(validator.stop)
        no_parent=patch.object(smoke,'run',side_effect=AssertionError('read only predecessor'))
        no_parent.start();self.addCleanup(no_parent.stop)

    def dispatch(self,directory,digest,journal):
        with sqlite3.connect(self.journal) as db:
            self.assertEqual(db.execute('SELECT status FROM format_research').fetchone()[0],'claimed')
        Path(directory).mkdir(mode=0o700)
        return deepcopy(self.report)

    def validate(self,directory,digest,journal):
        if not Path(directory).is_dir():raise ValueError('no completed child')
        return deepcopy(self.report)

    def run_coordinator(self):
        return coordinator.run(self.root,self.journal,self.parent,self.parent_journal,self.child,self.child_journal,DIGEST)

    def test_fixed_graph_claims_before_dispatch_and_restart_is_readonly(self):
        paths=[self.parent/'claim.sqlite',self.parent/'report.json',self.parent_journal]
        before={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in paths}
        result=self.run_coordinator()
        self.assertEqual(result['status'],'candidate_requires_independent_evaluation')
        self.assertFalse(result['efficacy_established']);self.assertFalse(result['promotion_authorized'])
        self.assertFalse(result['goal_achieved'])
        path=self.root/'report.json';published=(path.read_bytes(),path.stat().st_mtime_ns)
        self.assertEqual(self.run_coordinator(),result);self.assertEqual(self.dispatcher.call_count,1)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),published)
        self.assertEqual({str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in paths},before)

    def test_missing_parent_never_creates_or_dispatches(self):
        (self.parent/'claim.sqlite').unlink()
        with self.assertRaises(OSError):self.run_coordinator()
        self.dispatcher.assert_not_called();self.assertFalse(self.root.exists())

    def test_tampered_predecessor_publication_rejected(self):
        (self.parent/'report.json').write_text('{}')
        with self.assertRaises(ValueError):self.run_coordinator()
        self.dispatcher.assert_not_called()

    def test_child_failure_is_terminal_and_no_retry(self):
        self.dispatcher.side_effect=TimeoutError('fixture')
        result=self.run_coordinator();self.assertEqual(result['status'],'blocked')
        self.assertEqual(self.run_coordinator(),result);self.assertEqual(self.dispatcher.call_count,1)

    def test_missing_child_after_completion_never_dispatches_again(self):
        self.run_coordinator();self.child.rmdir()
        with self.assertRaises(ValueError):self.run_coordinator()
        self.assertEqual(self.dispatcher.call_count,1)

    def test_interrupted_claim_does_not_dispatch_on_resume(self):
        self.dispatcher.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.run_coordinator()
        with self.assertRaises(ValueError):self.run_coordinator()
        self.assertEqual(self.dispatcher.call_count,1)

    def test_shared_claim_prevents_different_coordinator_path(self):
        self.run_coordinator();self.root=self.base/'other'
        with self.assertRaises(ValueError):self.run_coordinator()
        self.assertEqual(self.dispatcher.call_count,1)

    def test_missing_claim_journal_never_recreated(self):
        self.run_coordinator();self.journal.unlink()
        with self.assertRaises(ValueError):self.run_coordinator()
        self.assertFalse(self.journal.exists());self.assertEqual(self.dispatcher.call_count,1)

    def test_no_gain_retains_baseline(self):
        for row in self.report['rows']:
            row['score']={'schema_valid':False,'format_valid':False,'strict_correct':False}
            row['response']['raw_output']='Some prose'
        result=self.run_coordinator();self.assertEqual(result['status'],'retain_baseline')

    def test_new_wrong_answer_rejects_format_gain(self):
        report=child_report()
        for row in report['rows']:
            if row['task_id']=='unit_mismatch' and row['constrained']:
                row['response']['raw_output']=smoke.canonical(smoke.EXPECTED);row['score']['strict_correct']=False
            if row['task_id']=='supported' and not row['constrained']:
                row['score']['strict_correct']=True
        self.assertEqual(coordinator.decision(report)['next_action'],'retain_baseline')

    def test_rehashed_terminal_safety_tamper_rejected(self):
        original=self.run_coordinator()
        for key,value in [('promotion_authorized',True),('new_model_call_budget',True),('status','retain_baseline')]:
            report=deepcopy(original);report[key]=value;encoded=coordinator.canonical(report)
            with sqlite3.connect(self.journal) as db:
                db.execute('UPDATE format_research SET report=?,digest=?',(encoded,sha256(encoded.encode()).hexdigest()))
            (self.root/'report.json').write_text(encoded+'\n')
            with self.assertRaisesRegex(ValueError,'terminal_receipt_changed'):self.run_coordinator()
        self.assertEqual(self.dispatcher.call_count,1)

    def test_rehashed_failed_safety_tamper_rejected(self):
        self.dispatcher.side_effect=TimeoutError('fixture')
        report=self.run_coordinator();report['efficacy_established']=True;encoded=coordinator.canonical(report)
        with sqlite3.connect(self.journal) as db:
            db.execute('UPDATE format_research SET report=?,digest=?',(encoded,sha256(encoded.encode()).hexdigest()))
        (self.root/'report.json').write_text(encoded+'\n')
        with self.assertRaisesRegex(ValueError,'terminal_receipt_changed'):self.run_coordinator()
        self.assertEqual(self.dispatcher.call_count,1)

    def test_real_child_claims_and_receipt_validator_with_mocked_model(self):
        child=coordinator.study;calls=[]
        def respond(config,query,evidence,*,authorize,constrained):
            calls.append((query,constrained))
            task=next(t for t in child.tasks().values() if t['query']==query)
            output=coordinator.canonical(task['expected']) if constrained else 'Some prose'
            result=smoke.execution.execute(config,query,evidence,lambda payload:output,authorize=authorize)
            return dict(result,model=smoke.pilot.MODEL,origin=smoke.pilot.ORIGIN,constrained=constrained,
                usage={'prompt_tokens':10,'completion_tokens':10,'total_tokens':20})
        with patch.object(child,'run',side_effect=REAL_CHILD_RUN),patch.object(child,'validate_receipt',side_effect=REAL_CHILD_VALIDATE),patch.object(child,'metadata',return_value={'model':smoke.pilot.MODEL,'digest':DIGEST}),patch.object(child,'runtime_version',return_value='fixture'),patch.object(child,'preload',return_value={}),patch.object(child.transport,'run',side_effect=respond):
            result=self.run_coordinator();self.assertEqual(result['status'],'candidate_requires_independent_evaluation',result)
            self.assertEqual(self.run_coordinator(),result)
        self.assertEqual(len(calls),4)

    def test_private_output_and_distinct_paths(self):
        self.root.mkdir(mode=0o755)
        with self.assertRaises(ValueError):self.run_coordinator()
        self.dispatcher.assert_not_called()
        with self.assertRaises(ValueError):coordinator.run(self.parent,self.journal,self.parent,self.parent_journal,self.child,self.child_journal,DIGEST)

    def test_changed_sources_prevent_publish(self):
        original=coordinator.sources()
        with patch.object(coordinator,'sources',side_effect=[original,{'changed':'f'*64}]):
            with self.assertRaisesRegex(ValueError,'inputs_changed'):self.run_coordinator()
        self.assertFalse((self.root/'report.json').exists())
        # A consumed claimed graph may only validate, never dispatch again.
        self.run_coordinator();self.assertEqual(self.dispatcher.call_count,1)


if __name__=='__main__':unittest.main()
