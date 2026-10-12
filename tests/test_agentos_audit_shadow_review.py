"""Independent shadow monitor adversarial controls; no live model calls."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim import agentos_audit_evidence as oracle
from nerve_awim import agentos_audit_fixtures as fixtures

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'

def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

study = load('agentos_audit_study')
shadow = load('agentos_audit_shadow')


def fresh_task():
    bundle = {'schema': 'agentos-audit-evidence-v1', 'simulated': True,
              'claim': {'kind': 'catalog_listed', 'model': 'shadow/model', 'provider': 'simulated', 'at': 1000, 'max_age': 60},
              'sources': [{'id': 'root-' + str(i), 'kind': 'catalog', 'model': 'shadow/model', 'provider': 'simulated',
                           'observed_at': 990, 'derived_from': [], 'fields': {'listed': True}} for i in range(7)]}
    return {'id': 'shadow-case', 'family': 'shadow-seven-independent-roots', 'bundle': bundle}


class AuditShadowReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.host = AgentOSLearning(Path(self.temp.name))
        self.calls = []
        self.inspections = 0
        self.mode = 'perfect'

    def native(self, host, profile, prompt, max_tokens=4096, inspect=False):
        if inspect:
            self.inspections += 1
            return {'ok': True, 'requested_model': 'fake/free:free'}
        host.reserve_calls('hermes-free', 1, daily_limit=20)
        self.calls.append(prompt)
        data = json.loads(prompt.splitlines()[-1])
        if isinstance(data, list):
            value = {'lesson': 'Check authoritative source identity and freshness.'}
        elif 'tasks' in data:
            value = {t['id']: oracle.expected_decision(t['bundle']) for t in data['tasks']}
            if data['advice'] is None:
                for answer in value.values():
                    answer['decision'] = 'contradicted' if answer['decision'] != 'contradicted' else 'unknown'
        else:
            if self.mode == 'crash':
                raise RuntimeError('simulated monitoring interruption')
            value = oracle.expected_decision(data['task']['bundle'])
            if self.mode == 'loss' and data['advice'] is not None:
                value['decision'] = 'contradicted' if value['decision'] != 'contradicted' else 'unknown'
            if self.mode == 'unsupported' and data['advice'] is not None:
                value['decision'] = 'supported'
        return dict(ok=True, requested_model='drift/free:free' if self.mode == 'drift' else 'fake/free:free',
                    tools=0, max_tokens=max_tokens, max_iterations=2, timeout_seconds=90, value=value)

    def accepted(self):
        result = study.study(self.host, self.native)
        self.assertEqual(result['status'], 'shadow_accepted')
        self.calls.clear()
        self.inspections = 0
        return result['study_id']

    def test_no_candidate_makes_no_callbacks(self):
        result = shadow.monitor(self.host, self.native, fresh_task())
        self.assertEqual(result['status'], 'no_candidate')
        self.assertEqual((len(self.calls), self.inspections), (0, 0))

    def test_fresh_pair_is_shadow_only_and_canonical_replay_refused(self):
        self.accepted()
        task = fresh_task()
        result = shadow.monitor(self.host, self.native, task)
        self.assertEqual(result['status'], 'active')
        self.assertFalse(result['activation_authorized'])
        self.assertEqual(result['native_sessions'], 2)
        self.assertEqual(study.remaining(self.host), 10)
        task['id'] = 'cosmetically-renamed'
        task['family'] = 'cosmetically-renamed-family'
        self.assertEqual(shadow.monitor(self.host, self.native, task)['status'], 'reused_evidence')
        self.assertEqual(len(self.calls), 2)

    def test_paired_loss_immediately_revokes_and_stops_future_calls(self):
        self.accepted()
        self.mode = 'loss'
        result = shadow.monitor(self.host, self.native, fresh_task())
        self.assertEqual(result['status'], 'revoked')
        self.assertTrue(result['paired_loss'])
        self.assertFalse(result['activation_authorized'])
        self.assertEqual(shadow.monitor(self.host, self.native, fresh_task())['status'], 'revoked')
        self.assertEqual(len(self.calls), 2)

    def test_unsupported_positive_revokes(self):
        self.accepted()
        task = fresh_task()
        for source in task['bundle']['sources']:
            source['fields']['listed'] = False
        self.mode = 'unsupported'
        result = shadow.monitor(self.host, self.native, task)
        self.assertEqual(result['status'], 'revoked')
        self.assertTrue(result['unsupported_positive'])

    def test_budget_requires_two_remaining_sessions_without_inspection(self):
        self.accepted()
        self.host.reserve_calls('hermes-free', 11, daily_limit=20)
        result = shadow.monitor(self.host, self.native, fresh_task())
        self.assertEqual(result['status'], 'deferred_daily_budget')
        self.assertEqual((len(self.calls), self.inspections), (0, 0))
        self.assertEqual(study.remaining(self.host), 1)

    def test_old_candidate_expires_before_inference(self):
        sid = self.accepted()
        with sqlite3.connect(study.database(self.host)) as db:
            db.execute('UPDATE studies SET created=? WHERE id=?', (int(time.time()) - 30 * 86400 - 1, sid))
        result = shadow.monitor(self.host, self.native, fresh_task())
        self.assertEqual(result['status'], 'expired')
        self.assertEqual((len(self.calls), self.inspections), (0, 0))

    def test_revision_and_scope_changes_deny_candidate(self):
        sid = self.accepted()
        with sqlite3.connect(study.database(self.host)) as db:
            original = db.execute('SELECT revision,result FROM studies WHERE id=?', (sid,)).fetchone()
            db.execute('UPDATE studies SET revision=? WHERE id=?', ('wrong-revision', sid))
        self.assertEqual(shadow.monitor(self.host, self.native, fresh_task())['status'], 'no_candidate')
        changed = json.loads(original[1])
        changed['scope'] = 'wrong-scope'
        with sqlite3.connect(study.database(self.host)) as db:
            db.execute('UPDATE studies SET revision=?,result=? WHERE id=?', (original[0], json.dumps(changed), sid))
        self.assertEqual(shadow.monitor(self.host, self.native, fresh_task())['status'], 'no_candidate')
        self.assertEqual((len(self.calls), self.inspections), (0, 0))

    def test_model_drift_revokes_without_operational_activation(self):
        self.accepted()
        self.mode = 'drift'
        result = shadow.monitor(self.host, self.native, fresh_task())
        self.assertEqual(result['status'], 'revoked')
        self.assertFalse(result['activation_authorized'])
        self.assertEqual(len(self.calls), 1)

    def test_development_evidence_is_never_fresh(self):
        self.accepted()
        row = fixtures.development_cases()[0]
        task = {key: row[key] for key in ('id', 'family', 'bundle')}
        self.assertEqual(shadow.monitor(self.host, self.native, task)['status'], 'reused_evidence')
        self.assertEqual((len(self.calls), self.inspections), (0, 0))

    def test_reserved_family_cannot_be_reused_with_new_composition(self):
        self.accepted()
        task = fresh_task()
        task['family'] = fixtures.development_cases()[0]['family']
        self.assertEqual(shadow.monitor(self.host, self.native, task)['status'], 'reused_evidence')
        self.assertEqual((len(self.calls), self.inspections), (0, 0))

    def test_crash_consumes_evidence_and_revokes_no_replay(self):
        self.accepted()
        self.mode = 'crash'
        self.assertEqual(shadow.monitor(self.host, self.native, fresh_task())['status'], 'revoked')
        self.assertEqual(study.remaining(self.host), 10)
        self.assertEqual(shadow.monitor(self.host, self.native, fresh_task())['status'], 'revoked')
        self.assertEqual(len(self.calls), 1)
        with sqlite3.connect(shadow.database(self.host)) as db:
            self.assertEqual(db.execute('SELECT state FROM episodes').fetchone()[0], 'failed')


if __name__ == '__main__':
    unittest.main()
