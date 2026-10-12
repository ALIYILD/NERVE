import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.agentos_learning import AgentOSLearning

spec = importlib.util.spec_from_file_location('autoresearch_test', Path(__file__).resolve().parents[1] / 'scripts/agentos_autoresearch.py')
loop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loop)


class AutoresearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.host = AgentOSLearning(Path(self.tmp.name) / 'state')
        self.calls = 0

    def native(self, host, profile, prompt, *, max_tokens, inspect=False):
        if inspect:
            return dict(ok=True, requested_model='model:free')
        self.calls += 1
        host.reserve_calls('hermes-free', 1, daily_limit=20)
        payload = json.loads(prompt.split('\n')[-1])
        if type(payload) is list:
            value = {'lesson': 'Require independent, fresh evidence.'}
        elif 'tasks' in payload:
            value = {r['id']: loop.shadow.oracle.expected_decision(r['bundle']) for r in payload['tasks']}
            if payload['advice'] is None:
                for answer in value.values():
                    answer['decision'] = 'contradicted' if answer['decision'] == 'supported' else 'supported'
        else:
            value = loop.shadow.oracle.expected_decision(payload['task']['bundle'])
        return dict(ok=True, requested_model='model:free', tools=0, max_tokens=4096, max_iterations=2, timeout_seconds=90, value=value)

    def task(self):
        return dict(id='fresh', family='fresh-family', bundle=dict(schema=loop.shadow.oracle.SCHEMA, simulated=True,
            claim=dict(kind='catalog_listed', model='m', provider='p', at=100, max_age=10),
            sources=[dict(id=str(i), kind='catalog', model='m', provider='p', observed_at=100, derived_from=[], fields=dict(listed=True)) for i in range(7)]))

    def test_paused_default_and_persistent_configuration(self):
        self.assertFalse(loop.status(self.host)['configured'])
        self.assertEqual(loop.tick(self.host, self.native)['status'], 'paused')
        loop.configure(self.host, True, 'custom')
        state = loop.configure(self.host, False)
        self.assertEqual(state['profile'], 'custom')
        self.assertTrue(state['configured'])
        self.assertEqual(self.calls, 0)

    def test_budget_wait_preserves_queue_and_never_calls_native(self):
        self.host.reserve_calls('hermes-free', 20, daily_limit=20)
        loop.configure(self.host, True)
        self.assertEqual(loop.tick(self.host, self.native)['result']['status'], 'queued_budget')
        before = json.loads((self.host.directory / 'pending-audit-study.json').read_text())
        self.assertEqual(loop.tick(self.host, self.native)['outcome'], 'wait')
        after = json.loads((self.host.directory / 'pending-audit-study.json').read_text())
        self.assertEqual(before, after)
        self.assertEqual(self.calls, 0)

    def test_accepted_study_exports_then_monitors_without_retraining(self):
        loop.configure(self.host, True)
        result = loop.tick(self.host, self.native)
        self.assertEqual(result['outcome'], 'keep')
        self.assertEqual(self.calls, 8)
        artifact = Path(result['result']['experimental_skill'])
        self.assertTrue(artifact.is_file())
        self.assertFalse(result['activation_authorized'])
        self.assertEqual(loop.tick(self.host, self.native)['result']['status'], 'awaiting_fresh_evidence')
        self.assertEqual(loop.submit(self.host, self.task())['status'], 'queued')
        self.assertEqual(loop.tick(self.host, self.native)['outcome'], 'keep')
        self.assertEqual(self.calls, 10)
        self.assertEqual(loop.tick(self.host, self.native)['result']['status'], 'awaiting_fresh_evidence')
        self.assertEqual(self.calls, 10)

    def test_renamed_task_cannot_reenter_inbox(self):
        task = self.task()
        self.assertEqual(loop.submit(self.host, task)['status'], 'queued')
        task['id'] = 'rename'; task['family'] = 'renamed'
        self.assertEqual(loop.submit(self.host, task)['status'], 'reused_evidence')

    def test_fixed_holdout_is_not_fresh_input(self):
        task = loop.shadow.cohort.cohort()['splits']['final'][0]
        task = {key: task[key] for key in ('id', 'family', 'bundle')}
        self.assertEqual(loop.submit(self.host, task)['status'], 'reused_evidence')

    def test_exhausted_study_no_inference(self):
        loop.configure(self.host, True)
        with patch.object(loop.studies, 'status', return_value=dict(status='rejected')):
            self.assertEqual(loop.tick(self.host, self.native)['result']['status'], 'awaiting_fresh_cohort')
        self.assertEqual(self.calls, 0)

    def test_event_ledger_immutable(self):
        loop.configure(self.host, True)
        self.host.reserve_calls('hermes-free', 20, daily_limit=20)
        loop.tick(self.host, self.native)
        with sqlite3.connect(loop.database(self.host)) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('DELETE FROM events')

    def test_interrupted_inbox_consumed_without_replay(self):
        loop.configure(self.host, True)
        loop.submit(self.host, self.task())
        with sqlite3.connect(loop.database(self.host)) as db:
            db.execute("UPDATE inbox SET state='running'")
        self.assertEqual(loop.tick(self.host, self.native)['outcome'], 'crash')
        self.assertEqual(loop.status(self.host)['inbox'], {'failed': 1})
        self.assertEqual(self.calls, 0)
