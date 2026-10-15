"""Durable dispatch invariants; diagnostics and receipt verification are isolated."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope
from nerve_awim.memory_gateway import memory_research_coordinator as coordinator
from nerve_awim.memory_gateway.research_memory_planner import ResearchPlan


class MemoryResearchCoordinatorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base/'coordinator'
        self.journal = self.base/'journal.sqlite'
        self.study = self.base/'study'
        self.study.mkdir()
        self.report = {'training': {'recommendation': 'retain_baseline'}}
        self.study.joinpath('report.json').write_text(json.dumps(self.report))
        digest = sha256(coordinator._json(self.report).encode()).hexdigest()
        self.auth = MemoryAuthority()
        self.scope = MemoryScope('research', 'coordinator', 'experiments')
        self.reader = self.auth.issue('research', 'coordinator', permissions=('read',))
        self.gateway = MemoryGateway(TrustedMemoryLedger(self.base/'memory.sqlite', self.auth))
        self.plan = ResearchPlan('diagnose_rejection_and_register_new_hypothesis',
                                 digest, 'retain_baseline', 'memory-fixture')
        self.planner = self.start_patch(coordinator.ResearchMemoryPlanner, 'plan',
                                       side_effect=self.authorized_plan)
        self.diagnose = self.start_patch(coordinator.diagnostic, 'diagnose',
                                        return_value={'next_action': 'register_new_hypothesis'})
        self.sources = self.start_patch(coordinator, '_sources',
                                       return_value={'fixture.py': 'a'*64})

    def start_patch(self, target, name, **kwargs):
        patcher = patch.object(target, name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def authorized_plan(self, reader, scope, *args):
        self.gateway._require(reader, scope, 'read')
        return self.plan

    def run_coordinator(self, **kwargs):
        options = dict(directory=self.root, journal=self.journal,
                       study_directory=self.study, study_claims=self.base/'study-claims.sqlite',
                       supervisor_directory=self.base/'supervisor')
        options.update(kwargs)
        return coordinator.run(self.gateway, self.reader, self.scope, **options)

    def status(self):
        with sqlite3.connect(self.journal) as db:
            return db.execute('SELECT status FROM memory_research_runs_v1').fetchone()[0]

    def set_status(self, value):
        with sqlite3.connect(self.journal) as db:
            db.execute('UPDATE memory_research_runs_v1 SET status=?', (value,))

    def test_claim_is_committed_before_diagnostic_and_no_promotion(self):
        def inspect(report):
            self.assertEqual(self.status(), 'claimed')
            self.assertEqual(report, self.report)
            return {'next_action': 'register_new_hypothesis'}
        self.diagnose.side_effect = inspect
        result = self.run_coordinator()
        self.assertEqual(self.status(), 'complete')
        self.assertEqual(result['new_episodes'], 0)
        self.assertFalse(result['promotion_authorized'])
        self.assertFalse(result['goal_achieved'])
        self.assertEqual(self.planner.call_count, 2)

    def test_completed_resume_recomputes_without_rewriting_artifact(self):
        first = self.run_coordinator()
        artifact = self.root/'report.json'
        before = artifact.stat().st_mtime_ns, artifact.read_bytes()
        self.assertEqual(self.run_coordinator(), first)
        self.assertEqual((artifact.stat().st_mtime_ns, artifact.read_bytes()), before)
        self.assertEqual(self.diagnose.call_count, 2)

    def test_claimed_complete_evidence_is_reconciled(self):
        first = self.run_coordinator()
        self.set_status('claimed')
        artifact = self.root/'report.json'
        before = artifact.stat().st_mtime_ns
        self.assertEqual(self.run_coordinator(), first)
        self.assertEqual(self.status(), 'complete')
        self.assertEqual(artifact.stat().st_mtime_ns, before)

    def test_incomplete_claim_never_recreates_missing_evidence(self):
        self.run_coordinator()
        self.set_status('claimed')
        artifact = self.root/'report.json'
        artifact.unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_coordinator()
        self.assertFalse(artifact.exists())
        self.assertEqual(self.status(), 'failed_consumed')
        calls = self.diagnose.call_count
        with self.assertRaisesRegex(RuntimeError, 'failed_consumed'):
            self.run_coordinator()
        self.assertEqual(self.diagnose.call_count, calls)

    def test_diagnostic_failure_is_consumed(self):
        self.diagnose.side_effect = ValueError('diagnostic fixture failure')
        with self.assertRaisesRegex(ValueError, 'fixture failure'):
            self.run_coordinator()
        self.assertEqual(self.status(), 'failed_consumed')
        self.diagnose.side_effect = None
        with self.assertRaisesRegex(RuntimeError, 'failed_consumed'):
            self.run_coordinator()
        self.assertEqual(self.diagnose.call_count, 1)

    def test_location_change_cannot_replay_consumed_receipt(self):
        self.run_coordinator()
        with self.assertRaisesRegex(ValueError, 'protocol_or_location_changed'):
            self.run_coordinator(directory=self.base/'renamed')
        self.assertEqual(self.diagnose.call_count, 1)

    def test_source_protocol_change_cannot_replay_consumed_receipt(self):
        self.run_coordinator()
        self.sources.return_value = {'fixture.py': 'b'*64}
        with self.assertRaisesRegex(ValueError, 'protocol_or_location_changed'):
            self.run_coordinator()
        self.assertEqual(self.diagnose.call_count, 1)

    def test_altered_artifact_is_consumed_failure(self):
        self.run_coordinator()
        (self.root/'report.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'artifact_changed'):
            self.run_coordinator()
        self.assertEqual(self.status(), 'failed_consumed')
        self.assertEqual((self.root/'report.json').read_text(), '{}')

    def test_missing_or_revoked_memory_advice_never_dispatches(self):
        self.plan = replace(self.plan, action='verify_and_record_outcome', memory_id=None)
        result = self.run_coordinator()
        self.assertEqual(result['status'], 'waiting_for_verified_rejection')
        self.diagnose.assert_not_called()
        self.assertFalse(self.journal.exists())
        self.assertFalse(self.root.exists())

    def test_reader_revoked_before_run_never_dispatches(self):
        self.auth.revoke(self.reader)
        with self.assertRaises(PermissionError):
            self.run_coordinator()
        self.diagnose.assert_not_called()
        self.assertFalse(self.journal.exists())

    def test_authority_revoked_during_work_prevents_publication(self):
        def revoke(report):
            self.auth.revoke(self.reader)
            return {'next_action': 'register_new_hypothesis'}
        self.diagnose.side_effect = revoke
        with self.assertRaises(PermissionError):
            self.run_coordinator()
        self.assertEqual(self.status(), 'failed_consumed')
        self.assertFalse((self.root/'report.json').exists())

    def test_memory_revoked_during_work_prevents_publication(self):
        def revoke(report):
            self.plan = replace(self.plan, action='verify_and_record_outcome', memory_id=None)
            return {'next_action': 'register_new_hypothesis'}
        self.diagnose.side_effect = revoke
        with self.assertRaisesRegex(ValueError, 'planning_authority_or_source_changed'):
            self.run_coordinator()
        self.assertEqual(self.status(), 'failed_consumed')
        self.assertFalse((self.root/'report.json').exists())

    def test_concurrent_root_lock_rejects_without_claim(self):
        self.root.mkdir()
        with coordinator._exclusive(self.root):
            with self.assertRaisesRegex(RuntimeError, 'already_running'):
                self.run_coordinator()
        self.diagnose.assert_not_called()
        self.assertFalse(self.journal.exists())

    def test_study_changed_after_plan_fails_before_diagnostic(self):
        (self.study/'report.json').write_text('{"altered":true}')
        with self.assertRaisesRegex(ValueError, 'study_changed_after_planning'):
            self.run_coordinator()
        self.diagnose.assert_not_called()
        self.assertEqual(self.status(), 'failed_consumed')

    def test_sources_changed_during_diagnostic_prevent_publication(self):
        self.sources.side_effect = [{'fixture.py': 'a'*64}, {'fixture.py': 'b'*64}]
        with self.assertRaisesRegex(ValueError, 'planning_authority_or_source_changed'):
            self.run_coordinator()
        self.assertFalse((self.root/'report.json').exists())

    def test_symlink_output_root_is_rejected(self):
        target = self.base/'elsewhere'
        target.mkdir()
        self.root.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink_coordinator_root'):
            self.run_coordinator()
        self.diagnose.assert_not_called()
        self.assertFalse(self.journal.exists())
