import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope, MemoryRequest
from nerve_awim.memory_gateway.research_outcome_memory import ResearchOutcomeMemory
from nerve_awim.memory_gateway import research_outcome_memory as module

SOURCE='research-receipt:'+'a'*64
CONTENT='{"kind":"verified_synthetic_research_outcome","recommendation":"retain_baseline","candidate_promoted":false}'


class ResearchOutcomeMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'memory.sqlite'
        self.auth=MemoryAuthority()
        self.proposer=self.auth.issue('research','coordinator',permissions=('read','propose'))
        self.reviewer=self.auth.issue('research','coordinator',permissions=('read','approve','delete'))
        self.reader=self.auth.issue('research','coordinator',permissions=('read',))
        self.scope=MemoryScope('research','coordinator','synthetic-experiments')
        self.gateway=MemoryGateway(TrustedMemoryLedger(self.path,self.auth))
        self.bridge=ResearchOutcomeMemory(self.gateway)
        self.proof=patch.object(module,'verified_fact',return_value=(SOURCE,CONTENT)).start()
        self.addCleanup(patch.stopall)

    def propose(self):return self.bridge.propose(self.proposer,self.scope,'run','claims','supervisor')
    def review(self,mid,actor=None):return self.bridge.review(actor or self.reviewer,self.scope,mid,'run','claims','supervisor')
    def query(self):return self.gateway.retrieve(self.reader,MemoryRequest(self.scope,'retain_baseline'))

    def test_pending_then_verified_negative_fact_is_reusable_not_promoted(self):
        mid=self.propose()
        self.assertEqual(self.query().records,())
        self.assertEqual(self.review(mid)['status'],'approved')
        record=self.query().records[0]
        self.assertEqual(record.memory_id,mid)
        self.assertFalse(json.loads(record.content)['candidate_promoted'])
        self.assertIsNone(record.outcome_score)
        with self.assertRaises(ValueError):self.review(mid)

    def test_agents_cannot_review_or_use_combined_proposal_capability(self):
        mid=self.propose()
        with self.assertRaises(PermissionError):self.review(mid,self.proposer)
        combined=self.auth.issue('research','coordinator',permissions=('read','propose','approve'))
        with self.assertRaises(PermissionError):self.bridge.propose(combined,self.scope,'run','claims','supervisor')

    def test_tampered_and_invalid_receipts_cannot_be_approved(self):
        mid=self.propose()
        self.proof.return_value=(SOURCE,CONTENT+' ')
        with self.assertRaises(ValueError):self.review(mid)
        self.assertEqual(self.query().records,())
        self.proof.side_effect=ValueError('bad_receipt')
        with self.assertRaises(ValueError):self.propose()

    def test_restart_retrieval_and_consumption_survive_delete(self):
        mid=self.propose();self.review(mid)
        self.gateway=MemoryGateway(TrustedMemoryLedger(self.path,self.auth))
        self.bridge=ResearchOutcomeMemory(self.gateway)
        self.assertEqual(self.query().records[0].memory_id,mid)
        with self.assertRaisesRegex(ValueError,'already_consumed'):self.propose()
        self.gateway.delete(self.reviewer,mid,scope=self.scope)
        self.assertEqual(self.query().records,())
        with self.assertRaisesRegex(ValueError,'already_consumed'):self.propose()

    def test_scope_and_revocation_remain_authoritative(self):
        mid=self.propose();self.review(mid)
        foreign=self.auth.issue('other','coordinator',permissions=('read',))
        with self.assertRaises(PermissionError):self.gateway.retrieve(foreign,MemoryRequest(self.scope,'retain_baseline'))
        self.assertEqual(self.gateway.retrieve(self.reader,MemoryRequest(replace(self.scope,context='other'),'retain_baseline')).records,())
        self.gateway.revoke(self.reviewer,mid,scope=self.scope,evaluator_id='host')
        self.assertEqual(self.query().records,())
        with self.assertRaises(ValueError):self.review(mid)

    def test_proposal_failure_is_consumed(self):
        with patch.object(self.gateway,'propose',side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError):self.propose()
        with self.assertRaisesRegex(ValueError,'already_consumed'):self.propose()
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT status FROM research_memory_receipts_v1').fetchone()[0],'failed_consumed')

    def test_revocation_during_verification_cannot_write_or_approve(self):
        mid=self.propose()
        def revoke_reviewer(*args):
            self.auth.revoke(self.reviewer)
            return SOURCE,CONTENT
        self.proof.side_effect=revoke_reviewer
        with self.assertRaises(PermissionError):self.review(mid)
        self.assertEqual(self.query().records,())

    def test_orphan_pending_row_cannot_be_reviewed_or_reproposed(self):
        original=self.gateway.propose
        inserted=[]
        def interrupted(*args,**kwargs):
            inserted.append(original(*args,**kwargs))
            raise RuntimeError('interrupted_after_insert')
        with patch.object(self.gateway,'propose',side_effect=interrupted):
            with self.assertRaises(RuntimeError):self.propose()
        self.assertEqual(self.query().records,())
        with self.assertRaisesRegex(ValueError,'not_reviewable'):self.review(inserted[0])
        with self.assertRaisesRegex(ValueError,'already_consumed'):self.propose()


class VerifiedFactTests(unittest.TestCase):
    def test_invalid_source_receipt_is_not_summarized(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'report.json').write_text('{}')
            with patch.object(module.study,'validate_receipt',side_effect=ValueError('invalid_receipt')):
                with self.assertRaisesRegex(ValueError,'invalid_receipt'):
                    module.verified_fact(temp,'claims','supervisor')
    def test_json_reformatting_preserves_receipt_identity(self):
        report={'protocol':{'protocol':'fixture'},'episodes':128,'plant_steps':10240,
                'recommendation':'retain_baseline','selection':{'candidate':None,'evaluations':{'candidate':{'passed':False}}},
                'stages':{},'holdout_consumed':False}
        with tempfile.TemporaryDirectory() as temp, patch.object(module.study,'validate_receipt'):
            path=Path(temp)/'report.json'
            path.write_text(json.dumps(report))
            first=module.verified_fact(temp,'claims','supervisor')
            path.write_text(json.dumps(report,sort_keys=True,indent=4))
            self.assertEqual(module.verified_fact(temp,'claims','supervisor'),first)
            self.assertLessEqual(len(first[1]),2048)

    def test_snapshot_change_during_validation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'report.json';path.write_text('{}')
            with patch.object(module.study,'validate_receipt',side_effect=lambda *args:path.write_text('{"changed":true}')):
                with self.assertRaisesRegex(ValueError,'research_receipt_changed'):
                    module.verified_fact(temp,'claims','supervisor')
