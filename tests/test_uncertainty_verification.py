from dataclasses import replace
import unittest
import test_uncertainty_ledger as fixture
from nerve_awim.uncertainty.verification import Verifier,ToolSpec
from nerve_awim.uncertainty.contracts import VerificationAttempt

class VerificationTests(unittest.TestCase):
    setUp=fixture.LedgerTests.setUp
    claim=fixture.LedgerTests.claim
    conflict=fixture.LedgerTests.conflict
    resolve=fixture.LedgerTests.resolve
    def verifier(self,handler):
        return Verifier(self.ledger,tools={'primary':ToolSpec(handler,lambda r:type(r) is dict and set(r)=={'query'},('source_disagreement',))})
    def test_successful_read_is_not_factual_resolution(self):
        c=self.conflict();calls=[]
        verifier=self.verifier(lambda request:calls.append(request) or {'outcome':'supports','evidence_refs':[{'source_ref':'source-one','source_revision':'v1'}]})
        out=verifier.check(self.actor,c.conflict_id,'primary',{'query':'known'})
        self.assertEqual(out['attempt']['outcome'],'supports');self.assertNotEqual(self.ledger.get_conflict(self.actor,c.conflict_id).status,'resolved')
        self.assertTrue(verifier.check(self.actor,c.conflict_id,'primary',{'query':'known'})['deduplicated']);self.assertEqual(len(calls),1)
        self.resolve(self.ledger.get_conflict(self.actor,c.conflict_id));self.assertEqual(self.ledger.get_conflict(self.actor,c.conflict_id).status,'resolved')
    def test_empty_read_no_credit_and_irreducible_budget_stop(self):
        c=self.conflict();v=self.verifier(lambda request:{'outcome':'supports','evidence_refs':[]})
        for n in range(3):self.assertEqual(v.check(self.actor,c.conflict_id,'primary',{'query':n})['boundary'],'unresolved_no_source')
        self.assertEqual(v.check(self.actor,c.conflict_id,'primary',{'query':4})['boundary'],'unresolved_budget')
        self.assertNotEqual(self.ledger.get_conflict(self.actor,c.conflict_id).status,'resolved')
    def test_failure_retry_preserves_budget(self):
        c=self.conflict();calls=[]
        def fail(request):calls.append(1);raise TimeoutError()
        v=self.verifier(fail)
        out=v.check(self.actor,c.conflict_id,'primary',{'query':1});self.assertEqual(out['boundary'],'verifier_unavailable')
        v.check(self.actor,c.conflict_id,'primary',{'query':1},retry_reason='transient_transport_failure')
        self.assertEqual(len(calls),2)
    def test_restart_unknown_reservation_never_repeats(self):
        c=self.conflict();calls=[];v=self.verifier(lambda r:calls.append(1) or {'outcome':'inconclusive','evidence_refs':[]})
        out=v.check(self.actor,c.conflict_id,'primary',{'query':1});attempt=VerificationAttempt(**out['attempt'])
        with self.engine._db() as con:con.execute('UPDATE uc_attempts SET record=? WHERE id=?',(replace(attempt,status='reserved').to_json(),attempt.attempt_id))
        self.assertEqual(v.resume(self.actor,attempt.attempt_id)['boundary'],'verifier_unavailable')
        self.assertEqual(v.check(self.actor,c.conflict_id,'primary',{'query':1})['boundary'],'verifier_unavailable');self.assertEqual(len(calls),1)
    def test_late_receipt_and_bad_destination_fail(self):
        c=self.conflict()
        def late(request):self.now+=31;return {'outcome':'supports','evidence_refs':[{'source_ref':'source-one','source_revision':'v1'}]}
        v=self.verifier(late);self.assertEqual(v.check(self.actor,c.conflict_id,'primary',{'query':1})['boundary'],'verifier_unavailable')
        with self.assertRaises(PermissionError):v.check(self.actor,c.conflict_id,'primary',{'url':'http://unapproved'})
    def test_paid_tool_and_raised_limits_rejected(self):
        with self.assertRaises(ValueError):ToolSpec(lambda x:x,lambda x:True,('source_disagreement',),cost=.01)
        with self.assertRaises(ValueError):Verifier(self.ledger,tools={},max_conflict=4)
    def test_wall_timeout_returns_and_late_worker_cannot_resolve_or_replay(self):
        import threading
        import time
        c=self.conflict();release=threading.Event();finished=threading.Event();calls=[]
        def slow(request):
            calls.append(1)
            release.wait(.5)
            finished.set()
            return {'outcome':'supports','evidence_refs':[{'source_ref':'source-one','source_revision':'v1'}]}
        v=Verifier(self.ledger,tools={'primary':ToolSpec(slow,lambda r:True,('source_disagreement',))},call_seconds=.025)
        try:
            started=time.monotonic();out=v.check(self.actor,c.conflict_id,'primary',{'query':1})
            self.assertLess(time.monotonic()-started,.3)
            self.assertEqual(out['attempt']['status'],'uncertain')
            repeated=v.check(self.actor,c.conflict_id,'primary',{'query':1},retry_reason='transient_transport_failure')
            self.assertEqual(repeated['boundary'],'verifier_unavailable');self.assertEqual(len(calls),1)
        finally:
            release.set();finished.wait(1)
        self.assertEqual(v.resume(self.actor,out['attempt']['attempt_id'])['attempt']['status'],'uncertain')
        self.assertNotEqual(self.ledger.get_conflict(self.actor,c.conflict_id).status,'resolved')
