"""Fixture receipt validation plus real authoritative memory/journal operations."""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope
from nerve_awim.memory_gateway import forecast_research_coordinator as subject

CONTENT = json.dumps({'kind': 'verified_forecast_research_outcome', 'receipt_sha256': 'a'*64,
                      'candidate_promoted': False}, sort_keys=True)
SOURCE = 'forecast-receipt:'+'a'*64
PINS = {'fixture': 'fixed'}


class Interrupted(BaseException): pass


class ForecastCoordinatorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.scope = MemoryScope('tenant', 'agent', 'research')
        self.authority = MemoryAuthority()
        self.proposer = self.actor(('read', 'propose'))
        self.reader = self.actor(('read',))
        self.reviewer = self.actor(('read', 'approve'))
        self.admin = self.actor(('read', 'approve', 'delete'))
        self.gateway = MemoryGateway(TrustedMemoryLedger(self.root/'memory.sqlite', self.authority))
        self.evidence = {key: str(self.root/key) for key in
                         ('directory', 'claims', 'predecessor_path', 'online_artifact', 'online_summary')}
        self.evidence['source_paths'] = {'study': str(self.root/'original')}
        self.kwargs = dict(directory=self.root/'output', journal=self.root/'journal.sqlite', evidence=self.evidence)
        validator = patch.object(subject.memory, 'verified_fact', return_value=(SOURCE, CONTENT))
        self.validator = validator.start(); self.addCleanup(validator.stop)
        pins = patch.object(subject, '_sources', return_value=PINS)
        self.pins = pins.start(); self.addCleanup(pins.stop)

    def actor(self, permissions):
        return self.authority.issue(self.scope.tenant_id, self.scope.agent_id, permissions=permissions)

    def run_coordinator(self):
        return subject.run(self.gateway, self.proposer, self.reader, self.scope, **self.kwargs)

    def approve(self, memory_id):
        subject.memory.ForecastOutcomeMemory(self.gateway).review(self.reviewer, self.scope,
                                                                 memory_id, **self.evidence)

    def complete(self):
        pending = self.run_coordinator(); self.approve(pending['memory_id'])
        return self.run_coordinator()

    def status(self):
        with sqlite3.connect(self.kwargs['journal']) as db:
            return db.execute('SELECT status FROM forecast_research_runs_v1').fetchone()[0]

    def test_pending_wait_then_separate_review_then_stable_resume(self):
        pending = self.run_coordinator()
        self.assertEqual(pending['status'], 'waiting_for_fact_review')
        self.assertFalse((self.root/'output/report.json').exists())
        with patch.object(subject.memory.ForecastOutcomeMemory, 'propose', side_effect=AssertionError('duplicate proposal')):
            self.assertEqual(self.run_coordinator(), pending)
        self.approve(pending['memory_id'])
        result = self.run_coordinator()
        self.assertEqual(result['status'], 'forecast_only_review_required')
        path = self.root/'output/report.json'; before = (path.read_bytes(), path.stat().st_mtime_ns)
        self.assertEqual(self.run_coordinator(), result)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        for flag in ('promotion_authorized', 'control_policy_change_authorized', 'model_weights_trained', 'goal_achieved'):
            self.assertIs(result[flag], False)
        self.assertEqual(result['new_episodes'], 0)

    def test_real_fresh_process_resume_preserves_artifact_and_proposal_count(self):
        expected = self.complete()
        path = self.root/'output/report.json'; before = (path.read_bytes(), path.stat().st_mtime_ns)
        fixture = self.root/'fixture.json'
        fixture.write_text(json.dumps({'root': str(self.root), 'evidence': self.evidence,
                                       'content': CONTENT, 'source': SOURCE}))
        code = '''import json,sys
from pathlib import Path
from unittest.mock import patch
from nerve_awim.memory_v18 import MemoryAuthority,TrustedMemoryLedger
from nerve_awim.memory_gateway import MemoryGateway,MemoryScope
from nerve_awim.memory_gateway import forecast_research_coordinator as c
f=json.loads(Path(sys.argv[1]).read_text()); root=Path(f['root'])
a=MemoryAuthority(); s=MemoryScope('tenant','agent','research')
p=a.issue('tenant','agent',permissions=('read','propose')); r=a.issue('tenant','agent',permissions=('read',))
g=MemoryGateway(TrustedMemoryLedger(root/'memory.sqlite',a))
with patch.object(c.memory,'verified_fact',return_value=(f['source'],f['content'])), patch.object(c,'_sources',return_value={'fixture':'fixed'}), patch.object(c.memory.ForecastOutcomeMemory,'propose',side_effect=AssertionError('must not propose')):
 print(json.dumps(c.run(g,p,r,s,directory=root/'output',journal=root/'journal.sqlite',evidence=f['evidence'])))
'''
        process = subprocess.run([sys.executable, '-c', code, str(fixture)],
                                 capture_output=True, text=True, check=True, timeout=30)
        self.assertEqual(json.loads(process.stdout), expected)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_durable_claim_precedes_proposal_and_reconciles_completed_crash(self):
        original = subject.memory.ForecastOutcomeMemory.propose
        def crash(bridge, *args, **kwargs):
            self.assertEqual(self.status(), 'claimed')
            original(bridge, *args, **kwargs)
            raise Interrupted()
        with patch.object(subject.memory.ForecastOutcomeMemory, 'propose', new=crash):
            with self.assertRaises(Interrupted): self.run_coordinator()
        with patch.object(subject.memory.ForecastOutcomeMemory, 'propose', side_effect=AssertionError('must reconcile')):
            self.assertEqual(self.run_coordinator()['status'], 'waiting_for_fact_review')

    def test_crash_before_memory_claim_is_consumed_not_retried(self):
        with patch.object(subject.memory.ForecastOutcomeMemory, 'propose', side_effect=Interrupted()):
            with self.assertRaises(Interrupted): self.run_coordinator()
        with self.assertRaisesRegex(ValueError, 'without_complete_claim'): self.run_coordinator()
        self.assertEqual(self.status(), 'failed_consumed')
        with self.assertRaisesRegex(RuntimeError, 'failed_consumed'): self.run_coordinator()

    def test_completed_artifact_reconciles_after_publish_crash_without_rewriting(self):
        pending = self.run_coordinator(); self.approve(pending['memory_id'])
        original = subject._publish
        def crash(*args): original(*args); raise Interrupted()
        with patch.object(subject, '_publish', side_effect=crash):
            with self.assertRaises(Interrupted): self.run_coordinator()
        path = self.root/'output/report.json'; before = (path.read_bytes(), path.stat().st_mtime_ns)
        self.assertEqual(self.run_coordinator()['status'], 'forecast_only_review_required')
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_ordinary_failure_remains_consumed(self):
        with patch.object(subject.memory.ForecastOutcomeMemory, 'propose', side_effect=RuntimeError('storage failed')):
            with self.assertRaisesRegex(RuntimeError, 'storage failed'): self.run_coordinator()
        self.assertEqual(self.status(), 'failed_consumed')
        with self.assertRaisesRegex(RuntimeError, 'failed_consumed'): self.run_coordinator()

    def test_expired_record_cannot_resume(self):
        result = self.complete(); mid = result['memory_id']
        with sqlite3.connect(self.gateway.ledger.path) as db:
            db.execute('UPDATE trusted_memory_v18 SET valid_until=0 WHERE memory_id=?', (mid,))
        with self.assertRaisesRegex(ValueError, 'approved_forecast_fact_required'): self.run_coordinator()
        self.assertEqual(self.status(), 'failed_consumed')

    def test_revocation_denies_packet_even_after_completed_journal(self):
        result = self.complete()
        self.gateway.revoke(self.admin, result['memory_id'], scope=self.scope, evaluator_id='trusted-revoke')
        with self.assertRaisesRegex(ValueError, 'claimed_memory_fact_changed'): self.run_coordinator()

    def test_deletion_preserves_consumed_claim_and_does_not_repropose(self):
        result = self.complete()
        self.gateway.delete(self.admin, result['memory_id'], scope=self.scope)
        with self.assertRaises(LookupError): self.run_coordinator()
        self.assertEqual(subject.memory.ForecastOutcomeMemory(self.gateway).claim(self.reader,self.scope,SOURCE),
                         ('proposed', result['memory_id']))

    def test_wrong_evaluator_is_not_approved_fact(self):
        pending = self.run_coordinator()
        self.gateway.decide(self.reviewer, pending['memory_id'], scope=self.scope,
                            approve=True, evaluator_id='untrusted-review')
        with self.assertRaisesRegex(ValueError, 'approved_forecast_fact_required'): self.run_coordinator()

    def test_changed_config_pins_and_artifact_rejected(self):
        self.complete()
        self.pins.return_value = {'fixture': 'changed'}
        with self.assertRaisesRegex(ValueError, 'consumed_protocol_or_location_changed'): self.run_coordinator()
        self.pins.return_value = PINS
        path = self.root/'output/report.json'; path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'forecast_review_artifact_changed'): self.run_coordinator()

    def test_missing_completed_artifact_is_not_silently_rebuilt(self):
        self.complete(); (self.root/'output/report.json').unlink()
        with self.assertRaisesRegex(ValueError, 'completed_review_artifact_missing'): self.run_coordinator()

    def test_foreign_or_approval_capability_cannot_create_coordinator(self):
        self.proposer = self.actor(('read', 'propose', 'approve'))
        with self.assertRaises(PermissionError): self.run_coordinator()
        self.proposer = self.actor(('read', 'propose'))
        self.reader = self.authority.issue('foreign', 'agent', permissions=('read',))
        with self.assertRaises(PermissionError): self.run_coordinator()
        self.assertFalse((self.root/'journal.sqlite').exists())

    def test_rejected_pending_fact_cannot_advance(self):
        pending = self.run_coordinator()
        self.gateway.decide(self.reviewer, pending['memory_id'], scope=self.scope,
                            approve=False, evaluator_id='trusted-reject')
        with self.assertRaisesRegex(ValueError, 'claimed_memory_fact_changed'): self.run_coordinator()

    def test_incomplete_bridge_claim_is_never_reproposed(self):
        self.run_coordinator()
        with sqlite3.connect(self.gateway.ledger.path) as db:
            db.execute("UPDATE forecast_memory_receipts_v1 SET status='claimed',memory_id=NULL")
        with patch.object(subject.memory.ForecastOutcomeMemory, 'propose', side_effect=AssertionError('no retries')):
            with self.assertRaisesRegex(ValueError, 'incomplete_memory_claim_consumed'): self.run_coordinator()
        self.assertEqual(self.status(), 'failed_consumed')

    def test_changed_exact_pending_fact_fails_before_any_review_packet(self):
        pending = self.run_coordinator()
        changed = CONTENT+' '
        with sqlite3.connect(self.gateway.ledger.path) as db:
            db.execute('UPDATE trusted_memory_v18 SET content=?,source_sha256=? WHERE memory_id=?',
                       (changed, sha256(changed.encode()).hexdigest(), pending['memory_id']))
        with self.assertRaisesRegex(ValueError, 'claimed_memory_fact_changed'): self.run_coordinator()
        self.assertFalse((self.root/'output/report.json').exists())

    def test_source_drift_during_proposal_is_consumed(self):
        self.pins.side_effect = [PINS, {'fixture': 'changed'}]
        with self.assertRaisesRegex(ValueError, 'coordinator_source_changed'): self.run_coordinator()
        self.assertEqual(self.status(), 'failed_consumed')


if __name__ == '__main__': unittest.main()
