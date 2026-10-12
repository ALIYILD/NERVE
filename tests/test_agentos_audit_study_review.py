"""Independent red-team tests; native callbacks are deterministic local fakes."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim import agentos_audit_cohort as cohort
from nerve_awim import agentos_audit_evidence as oracle

spec = importlib.util.spec_from_file_location('audit_study_review_target', Path(__file__).resolve().parents[1] / 'scripts/agentos_audit_study.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class AuditStudyReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.host = AgentOSLearning(Path(self.temp.name))
        self.calls = []
        self.mode = 'perfect'

    def native(self, host, profile, prompt, max_tokens=4096, inspect=False):
        if inspect:
            return {'ok': True, 'requested_model': 'test/model:free'}
        host.reserve_calls('hermes-free', 1, daily_limit=20)
        self.calls.append(prompt)
        if self.mode == 'crash':
            raise RuntimeError('simulated failure after reservation')
        payload = json.loads(prompt.splitlines()[-1])
        if isinstance(payload, list):
            value = {'lesson': 'Apply identity, freshness and source-provenance checks.'}
        else:
            value = {task['id']: oracle.expected_decision(task['bundle']) for task in payload['tasks']}
            if self.mode == 'improve' and payload['advice'] is None:
                for answer in value.values():
                    answer['decision'] = 'contradicted' if answer['decision'] != 'contradicted' else 'unknown'
        return dict(ok=True, requested_model='different/model:free' if self.mode == 'drift' else 'test/model:free',
                    tools=0, max_tokens=max_tokens, max_iterations=2, timeout_seconds=90, value=value)

    def test_tie_prevents_holdout_and_proposal_sees_training_only(self):
        result = runner.study(self.host, self.native)
        self.assertEqual(result['status'], 'no_gain')
        self.assertEqual(result['native_sessions'], 4)
        self.assertEqual(set(result['phases']), {'selection'})
        self.assertFalse(result['activation_authorized'])
        self.assertEqual(runner.remaining(self.host), 12)
        splits = cohort.cohort()['splits']
        proposal = self.calls[1]
        for row in splits['train']:
            self.assertIn(row['id'], proposal)
        for phase in ('selection', 'retention', 'final'):
            for row in splits[phase]:
                self.assertNotIn(row['id'], proposal)
        for phase in ('retention', 'final'):
            for row in splits[phase]:
                self.assertNotIn(row['id'], '\n'.join(self.calls))

    def test_budget_shortage_queues_without_any_callback(self):
        self.host.reserve_calls('hermes-free', 13, daily_limit=20)
        def forbidden(*args, **kwargs):
            self.fail('callback must not run when only seven sessions remain')
        result = runner.study(self.host, forbidden)
        self.assertEqual(result['status'], 'queued_budget')
        self.assertEqual(result['remaining_sessions'], 7)
        self.assertEqual(runner.remaining(self.host), 7)

    def test_failure_reservations_and_evidence_cannot_be_replayed(self):
        self.mode = 'crash'
        failed = runner.study(self.host, self.native)
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(len(self.calls), 1)
        repeated = runner.study(self.host, self.native)
        self.assertEqual(repeated['status'], 'no_fresh_tasks')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(runner.remaining(self.host), 12)

    def test_model_drift_fails_and_cannot_activate(self):
        self.mode = 'drift'
        result = runner.study(self.host, self.native)
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['activation_authorized'])
        self.assertEqual(len(self.calls), 1)

    def test_apparent_improvement_is_shadow_only_and_eight_calls(self):
        self.mode = 'improve'
        result = runner.study(self.host, self.native)
        self.assertEqual(result['status'], 'shadow_accepted')
        self.assertEqual(result['native_sessions'], 8)
        self.assertFalse(result['activation_authorized'])
        self.assertEqual(runner.remaining(self.host), 12)
        self.assertEqual(set(result['phases']), {'selection', 'retention', 'final'})

    def test_family_rename_and_cosmetic_ids_do_not_refresh_composition(self):
        row = cohort.cohort()['splits']['train'][0]
        changed = deepcopy(row)
        changed['id'] = 'renamed-case'
        changed['family'] = 'renamed-family'
        rename = {s['id']: 'renamed-' + str(i) for i, s in enumerate(changed['bundle']['sources'])}
        for source in changed['bundle']['sources']:
            source['id'] = rename[source['id']]
            source['derived_from'] = [rename[i] for i in source['derived_from']]
        changed['bundle']['sources'].reverse()
        self.assertEqual(cohort.canonical_identity(row), cohort.canonical_identity(changed))

    def test_prepaid_slot_cannot_be_consumed_twice(self):
        def double_charge(host, profile, prompt, max_tokens=4096, inspect=False):
            if inspect:
                return {'ok': True, 'requested_model': 'test/model:free'}
            host.reserve_calls('hermes-free', 1, daily_limit=20)
            host.reserve_calls('hermes-free', 1, daily_limit=20)
            self.fail('second prepaid charge should fail')
        result = runner.study(self.host, double_charge)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(runner.remaining(self.host), 12)

    def test_interrupted_study_fails_without_reopening_evidence(self):
        self.mode = 'crash'
        first = runner.study(self.host, self.native)
        with sqlite3.connect(runner.database(self.host)) as db:
            db.execute("UPDATE studies SET status='running' WHERE id=?", (first['study_id'],))
        second = runner.study(self.host, self.native)
        self.assertEqual(second['status'], 'no_fresh_tasks')
        self.assertEqual(len(self.calls), 1)
        with sqlite3.connect(runner.database(self.host)) as db:
            self.assertEqual(db.execute('SELECT status FROM studies').fetchone()[0], 'failed')


if __name__ == '__main__':
    unittest.main()
