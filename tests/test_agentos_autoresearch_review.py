"""Independent checks of durable orchestration; all inference is simulated."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim import agentos_audit_evidence as oracle

spec = importlib.util.spec_from_file_location('autoresearch_review', Path(__file__).resolve().parents[1] / 'scripts/agentos_autoresearch.py')
research = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)


class AutoresearchReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.host = AgentOSLearning(Path(self.tmp.name) / 'state')
        research.configure(self.host, True)
        self.calls = 0

    def seed(self):
        def fake(host, profile, prompt, *, max_tokens, inspect=False):
            if inspect:
                return dict(ok=True, requested_model='model:free')
            host.reserve_calls('hermes-free', 1, daily_limit=20)
            payload = json.loads(prompt.split('\n')[-1])
            if isinstance(payload, list):
                value = {'lesson': 'Check independent source evidence.'}
            else:
                value = {r['id']: oracle.expected_decision(r['bundle']) for r in payload['tasks']}
                if payload['advice'] is None:
                    for answer in value.values():
                        answer['decision'] = 'contradicted' if answer['decision'] == 'supported' else 'supported'
            return dict(ok=True, requested_model='model:free', tools=0, max_tokens=4096, max_iterations=2, timeout_seconds=90, value=value)
        result = research.studies.study(self.host, fake)
        self.assertEqual(result['status'], 'shadow_accepted')
        return result['study_id']

    def task(self):
        return dict(id='review-new', family='review-family', bundle=dict(schema=oracle.SCHEMA, simulated=True,
            claim=dict(kind='catalog_listed', model='m', provider='p', at=100, max_age=10),
            sources=[dict(id='s'+str(i), kind='catalog', model='m', provider='p', observed_at=100,
                          derived_from=[], fields=dict(listed=True)) for i in range(7)]))

    def forbidden(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError('No native calls expected')

    def test_snapshot_tamper_cannot_export_or_run_skill(self):
        sid = self.seed()
        (self.host.directory/'audit-study-snapshots'/sid/'oracle.py').write_text('modified')
        research.submit(self.host, self.task())
        result = research.tick(self.host, self.forbidden)
        self.assertEqual(result['result']['status'], 'awaiting_fresh_cohort')
        self.assertEqual(self.calls, 0)
        self.assertFalse((self.host.directory/'autoresearch-skills'/sid/'SKILL.md').exists())

    def test_paused_tick_preserves_pending_task_and_budget(self):
        self.seed()
        research.submit(self.host, self.task())
        research.configure(self.host, False)
        before = research.studies.remaining(self.host)
        self.assertEqual(research.tick(self.host, self.forbidden)['status'], 'paused')
        self.assertEqual(research.status(self.host)['inbox'], {'pending': 1})
        self.assertEqual(research.studies.remaining(self.host), before)
        self.assertEqual(self.calls, 0)

    def test_cosmetic_rewrite_is_not_new_evidence(self):
        task = self.task()
        self.assertEqual(research.submit(self.host, task)['status'], 'queued')
        task['id'] = 'other-id'
        task['family'] = 'other-family'
        task['bundle']['sources'].reverse()
        self.assertEqual(research.submit(self.host, task)['status'], 'reused_evidence')
        self.assertEqual(research.status(self.host)['inbox'], {'pending': 1})

    def test_crash_marked_inbox_is_never_replayed(self):
        self.seed()
        research.submit(self.host, self.task())
        with sqlite3.connect(research.database(self.host)) as db:
            db.execute("UPDATE inbox SET state='running'")
        result = research.tick(self.host, self.forbidden)
        self.assertEqual(result['outcome'], 'crash')
        self.assertEqual(research.status(self.host)['inbox'], {'failed': 1})
        research.tick(self.host, self.forbidden)
        self.assertEqual(self.calls, 0)
        self.assertEqual(research.submit(self.host, self.task())['status'], 'reused_evidence')

    def test_tampered_export_blocks_monitor_without_spending(self):
        sid = self.seed()
        research.tick(self.host, self.forbidden)
        artifact = self.host.directory/'autoresearch-skills'/sid/'SKILL.md'
        artifact.write_text('unverified advice')
        research.submit(self.host, self.task())
        before = research.studies.remaining(self.host)
        result = research.tick(self.host, self.forbidden)
        self.assertEqual(result['result']['status'], 'artifact_integrity_error')
        self.assertEqual(research.studies.remaining(self.host), before)
        self.assertEqual(research.status(self.host)['inbox'], {'pending': 1})
        self.assertEqual(self.calls, 0)

    def test_interrupted_study_marked_failed_without_calls_or_reuse(self):
        sid = self.seed()
        with sqlite3.connect(research.studies.database(self.host)) as db:
            before = db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0]
            db.execute("UPDATE studies SET status='running' WHERE id=?", (sid,))
        self.assertEqual(research.tick(self.host, self.forbidden)['outcome'], 'crash')
        with sqlite3.connect(research.studies.database(self.host)) as db:
            self.assertEqual(db.execute('SELECT status FROM studies WHERE id=?', (sid,)).fetchone()[0], 'failed')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0], before)
        self.assertEqual(research.tick(self.host, self.forbidden)['result']['status'], 'awaiting_fresh_cohort')
        self.assertEqual(self.calls, 0)

    def test_revocation_updates_export_eligibility_in_same_tick(self):
        sid = self.seed()
        research.tick(self.host, self.forbidden)
        artifact = self.host.directory/'autoresearch-skills'/sid/'eligibility.json'
        self.assertTrue(artifact.exists())
        research.submit(self.host, self.task())
        def failed_native(host, profile, prompt, *, max_tokens, inspect=False):
            if inspect:
                return dict(ok=True, requested_model='model:free')
            host.reserve_calls('hermes-free', 1, daily_limit=20)
            raise RuntimeError('simulated inference failure')
        self.assertEqual(research.tick(self.host, failed_native)['result']['status'], 'revoked')
        self.assertEqual(json.loads(artifact.read_text())['status'], 'revoked')
        self.assertFalse(json.loads(artifact.read_text())['activation_authorized'])
