import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.agentos_learning import AgentOSLearning

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import agentos_cohort_registry as registry
import agentos_autoresearch as loop


class CohortRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.host = AgentOSLearning(Path(self.tmp.name))
        self.data = json.loads((ROOT / 'docs/evidence/agentos-audit-composition-v2.json').read_text())

    def review(self, data=None):
        return dict(manifest_sha256=registry.digest(data or self.data), reviewer='test-reviewer',
                    method='Test-only attestation', checks=dict(gold=True, novelty=True, split_separation=True))

    def test_admission_is_immutable_and_bound_to_review_and_profile(self):
        result = registry.admit(self.host, self.data, self.review())
        self.assertEqual(result['cases'], 16)
        self.assertEqual(registry.admit(self.host, self.data, self.review())['status'], 'already_registered')
        with self.assertRaises(ValueError):
            registry.admit(self.host, self.data, self.review(), profile='other')
        with sqlite3.connect(registry.database(self.host)) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('DELETE FROM cohorts')
        self.assertEqual(registry.get(self.host, self.data['id'])['data'], self.data)

    def test_review_must_be_explicit_exact_and_match_manifest(self):
        for field, value in (('manifest_sha256', 'bad'), ('checks', dict(gold=1, novelty=True, split_separation=True))):
            review = self.review(); review[field] = value
            with self.assertRaises(ValueError):
                registry.admit(self.host, self.data, review)
        data = copy.deepcopy(self.data); data['splits']['train'][0]['expected']['decision'] = 'supported'
        with self.assertRaises(ValueError):
            registry.admit(self.host, data, self.review(data))

    def test_monitoring_intake_and_cohort_intake_share_evidence_reservations(self):
        row = self.data['splits']['final'][0]
        task = {k: row[k] for k in ('id', 'family', 'bundle')}
        self.assertEqual(loop.submit(self.host, task)['status'], 'queued')
        with self.assertRaisesRegex(ValueError, 'reused evidence'):
            registry.admit(self.host, self.data, self.review())

    def test_registered_cases_cannot_be_submitted_as_shadow_tasks(self):
        registry.admit(self.host, self.data, self.review())
        row = self.data['splits']['final'][0]
        task = {k: row[k] for k in ('id', 'family', 'bundle')}
        task['id'] = 'rename'; task['family'] = 'rename'
        self.assertEqual(loop.submit(self.host, task)['status'], 'reused_evidence')

    def test_evaluator_drift_blocks_registered_data(self):
        registry.admit(self.host, self.data, self.review())
        with patch.object(registry.oracle, 'evaluator_revision', return_value='changed'):
            with self.assertRaisesRegex(ValueError, 'drift'):
                registry.get(self.host, self.data['id'])

    def test_legacy_queue_has_priority_and_next_cohort_defers_without_inference(self):
        registry.admit(self.host, self.data, self.review())
        self.host.reserve_calls('hermes-free', 20, daily_limit=20)
        loop.configure(self.host, True)
        native = unittest.mock.Mock(side_effect=AssertionError('budget exhausted'))
        first = loop.tick(self.host, native)
        self.assertEqual(first['kind'], 'study')
        queue = (self.host.directory / 'pending-audit-study.json').read_bytes()
        with patch.object(loop.studies, 'status', return_value={'status': 'no_gain'}):
            second = loop.tick(self.host, native)
        self.assertEqual(second['kind'], 'reviewed_cohort')
        self.assertEqual(second['result']['status'], 'queued_budget')
        self.assertEqual((self.host.directory / 'pending-audit-study.json').read_bytes(), queue)
        native.assert_not_called()

    def test_scheduler_advances_to_new_cohort_and_revalidates_export(self):
        registry.admit(self.host, self.data, self.review())
        loop.configure(self.host, True)
        calls = []
        def native(host, profile, prompt, *, max_tokens, inspect=False):
            if inspect:
                return dict(ok=True, requested_model='model:free')
            host.reserve_calls('hermes-free', 1, daily_limit=20)
            calls.append(prompt)
            payload = json.loads(prompt.split('\n')[-1])
            if type(payload) is list:
                value = {'lesson': 'Check independent roots and cite every applicable observation.'}
            else:
                value = {r['id']: registry.oracle.expected_decision(r['bundle']) for r in payload['tasks']}
                if payload['advice'] is None:
                    for answer in value.values():
                        answer['decision'] = 'contradicted' if answer['decision'] == 'supported' else 'supported'
            return dict(ok=True, requested_model='model:free', tools=0, max_tokens=4096,
                        max_iterations=2, timeout_seconds=90, value=value)
        first = loop.tick(self.host, native)
        self.assertEqual(first['kind'], 'study')
        second = loop.tick(self.host, native)
        self.assertEqual(second['kind'], 'reviewed_cohort')
        self.assertEqual(second['outcome'], 'keep')
        self.assertEqual(len(calls), 16)
        artifact = Path(second['result']['experimental_skill'])
        eligibility = artifact.parent / 'eligibility.json'
        self.assertEqual(json.loads(eligibility.read_text())['status'], 'experimental_unmonitored')
        with patch.object(loop.cohort_runner, 'verify_candidate', side_effect=ValueError('drift')):
            loop.tick(self.host, native)
        self.assertEqual(json.loads(eligibility.read_text())['status'], 'ineligible')
        self.assertEqual(len(calls), 16)
