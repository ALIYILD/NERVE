"""Independent fixture derivation and adversarial reviewed-cohort controls.

All callbacks are local deterministic fakes; no provider calls are made.
"""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim import agentos_audit_evidence as oracle
from nerve_awim import agentos_audit_cohort as legacy
from nerve_awim.agentos_audit_fixtures import development_cases

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import agentos_cohort_registry as registry
import agentos_cohort_study as runner
import agentos_autoresearch as research


# Derived by inspecting source kinds, provenance, identity and time windows.
# These decisions/root IDs are NOT computed from the implementation oracle.
GOLD = {
    'request-conflict-and-echo': ('unknown', ['fail', 'pass']),
    'credential-transitive-laundering': ('unknown', []),
    'price-conflicting-directions': ('unknown', ['free', 'input-paid', 'output-paid']),
    'catalog-root-with-derived-disagreement': ('supported', ['listed']),
    'execution-rebound-request': ('supported', ['target-pass']),
    'credential-negative-consensus-and-projection': ('contradicted', ['missing-a', 'missing-b']),
    'catalog-model-join-fabrication': ('unknown', []),
    'execution-target-conflict-other-consensus': ('unknown', ['target-fail', 'target-pass']),
    'price-paid-consensus-free-projection': ('contradicted', ['input-paid', 'output-paid']),
    'credential-present-window-and-echo': ('supported', ['current-present']),
    'execution-negative-transitive-repair': ('contradicted', ['root-fail']),
    'catalog-conflict-with-derived-consensus': ('unknown', ['no', 'yes']),
    'price-root-and-provenance-inversion': ('supported', ['observed-free']),
    'credential-conflict-cross-identity-reconciliation': ('unknown', ['missing', 'present']),
    'execution-near-miss-provenance-bridge': ('unknown', []),
    'catalog-absence-despite-execution': ('contradicted', ['absent']),
}


def fixture():
    return json.loads((ROOT / 'docs/evidence/agentos-audit-composition-v2.json').read_text())


def review(data):
    return dict(manifest_sha256=registry.digest(data), reviewer='independent-test',
                method='Local regression fixture attestation, no native inference.',
                checks=dict(gold=True, novelty=True, split_separation=True))


class CohortIndependentReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.host = AgentOSLearning(Path(self.temp.name))
        self.data = fixture()
        self.calls = []
        self.inspections = 0
        self.mode = 'improve'

    def admit(self):
        registry.admit(self.host, self.data, review(self.data))
        return registry.get(self.host, self.data['id'])

    def native(self, host, profile, prompt, *, max_tokens=4096, inspect=False):
        if inspect:
            self.inspections += 1
            return dict(ok=True, requested_model='review/free:free')
        host.reserve_calls('hermes-free', 1, daily_limit=20)
        self.calls.append(prompt)
        if self.mode == 'crash':
            raise RuntimeError('Interrupted after reservation')
        payload = json.loads(prompt.splitlines()[-1])
        if isinstance(payload, list):
            value = {'lesson': 'Check all applicable independent observations; never count derived consensus.'}
        elif 'task' in payload:
            value = oracle.expected_decision(payload['task']['bundle'])
        else:
            value = {row['id']: oracle.expected_decision(row['bundle']) for row in payload['tasks']}
            if self.mode == 'improve' and payload['advice'] is None:
                for answer in value.values():
                    answer['decision'] = 'unknown' if answer['decision'] != 'unknown' else 'contradicted'
        return dict(ok=True, requested_model='wrong/free:free' if self.mode == 'drift' else 'review/free:free',
                    tools=0, max_tokens=max_tokens, max_iterations=2, timeout_seconds=90, value=value)

    def test_independently_derived_all_gold_and_canonical_disjointness(self):
        rows = [row for group in self.data['splits'].values() for row in group]
        self.assertEqual({r['id'].removeprefix('audit-v2-') for r in rows}, set(GOLD))
        for row in rows:
            decision, ids = GOLD[row['id'].removeprefix('audit-v2-')]
            sources = {s['id']: s for s in row['bundle']['sources']}
            citations = [dict(source_id=ident, fields=sorted(
                ['model', 'provider', 'observed_at'] + ['fields.' + k for k in sources[ident]['fields']])) for ident in ids]
            with self.subTest(case=row['id']):
                self.assertEqual(row['expected'], dict(decision=decision, citations=citations))
                self.assertEqual(oracle.expected_decision(row['bundle']), row['expected'])
        identities = {legacy.canonical_identity(r) for r in rows}
        prior = development_cases() + [r for group in legacy.cohort()['splits'].values() for r in group]
        self.assertEqual(len(identities), 16)
        self.assertFalse(identities & {legacy.canonical_identity(r) for r in prior})
        self.assertFalse({r['family'] for r in rows} & {r['family'] for r in prior})

    def test_admission_requires_exact_review_and_immutable_data(self):
        malformed = review(self.data)
        malformed['checks']['novelty'] = 1
        with self.assertRaises(ValueError):
            registry.admit(self.host, self.data, malformed)
        self.admit()
        for statement in ("UPDATE cohorts SET profile='other'", "DELETE FROM cohorts",
                          "UPDATE evidence SET family='other'", "DELETE FROM evidence"):
            with self.subTest(statement=statement), sqlite3.connect(registry.database(self.host)) as db:
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(statement)
        self.data['splits']['train'][0]['expected']['decision'] = 'supported'
        self.assertEqual(registry.get(self.host, self.data['id'])['data'], fixture())

    def test_reused_cohort_relabel_does_not_admit_new_evidence(self):
        self.admit()
        self.data['id'] = 'renamed-cohort'
        for rows in self.data['splits'].values():
            for row in rows:
                row['family'] += '-renamed'
                row['id'] += '-renamed'
        with self.assertRaisesRegex(ValueError, 'reused'):
            registry.admit(self.host, self.data, review(self.data))

    def test_inbox_admission_then_cohort_cannot_reuse_evidence(self):
        row = self.data['splits']['train'][0]
        task = {k: row[k] for k in ('id', 'family', 'bundle')}
        self.assertEqual(research.submit(self.host, task)['status'], 'queued')
        with self.assertRaisesRegex(ValueError, 'reused'):
            self.admit()

    def test_cohort_admission_then_inbox_cannot_reuse_evidence(self):
        self.admit()
        row = self.data['splits']['train'][0]
        task = {k: row[k] for k in ('id', 'family', 'bundle')}
        self.assertEqual(research.submit(self.host, task)['status'], 'reused_evidence')

    def test_cohort_and_shadow_cannot_share_cases_in_either_order(self):
        accepted = research.studies.study(self.host, self.native)
        self.assertEqual(accepted['status'], 'shadow_accepted')
        row = self.data['splits']['selection'][0]
        task = {k: row[k] for k in ('id', 'family', 'bundle')}
        self.admit()
        before = len(self.calls), self.inspections, runner.remaining(self.host)
        self.assertEqual(research.shadow.monitor(self.host, self.native, task)['status'], 'reused_evidence')
        self.assertEqual((len(self.calls), self.inspections, runner.remaining(self.host)), before)
        with tempfile.TemporaryDirectory() as temp:
            other = AgentOSLearning(Path(temp))
            self.assertEqual(research.studies.study(other, self.native)['status'], 'shadow_accepted')
            self.assertEqual(research.shadow.monitor(other, self.native, task)['status'], 'active')
            with self.assertRaisesRegex(ValueError, 'reused'):
                registry.admit(other, self.data, review(self.data))

    def test_legacy_and_registered_experiments_share_daily_budget(self):
        self.assertEqual(research.studies.study(self.host, self.native)['status'], 'shadow_accepted')
        self.assertEqual(runner.run(self.host, self.native, self.admit())['status'], 'shadow_accepted')
        self.assertEqual(runner.remaining(self.host), 4)
        with self.assertRaisesRegex(RuntimeError, 'daily call limit'):
            self.host.reserve_calls('hermes-free', 5, daily_limit=20)
        self.assertEqual(runner.remaining(self.host), 4)

    def test_seven_remaining_sessions_defer_without_exposure(self):
        entry = self.admit()
        self.host.reserve_calls('hermes-free', 13, daily_limit=20)
        result = runner.run(self.host, self.native, entry)
        self.assertEqual(result['status'], 'queued_budget')
        self.assertEqual((self.calls, self.inspections), ([], 0))
        self.assertEqual(runner.remaining(self.host), 7)
        self.assertFalse(runner.consumed(self.host, entry['id']))

    def test_proposal_only_sees_training_and_tie_skips_holdout(self):
        self.mode = 'perfect'
        result = runner.run(self.host, self.native, self.admit())
        self.assertEqual(result['status'], 'no_gain')
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(runner.remaining(self.host), 12)
        for row in self.data['splits']['train']:
            self.assertIn(row['id'], self.calls[1])
        for phase in ('selection', 'retention', 'final'):
            for row in self.data['splits'][phase]:
                self.assertNotIn(row['id'], self.calls[1])
                if phase != 'selection':
                    self.assertNotIn(row['id'], '\n'.join(self.calls))

    def test_crash_burns_reservations_and_evidence_without_replay(self):
        entry = self.admit()
        self.mode = 'crash'
        first = runner.run(self.host, self.native, entry)
        self.assertEqual(first['status'], 'failed')
        self.assertEqual(runner.remaining(self.host), 12)
        self.assertTrue(runner.consumed(self.host, entry['id']))
        self.assertEqual(runner.run(self.host, self.native, entry)['status'], 'no_fresh_tasks')
        self.assertEqual(len(self.calls), 1)
        with sqlite3.connect(runner.database(self.host)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 0)

    def test_model_drift_fails_closed(self):
        self.mode = 'drift'
        result = runner.run(self.host, self.native, self.admit())
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['activation_authorized'])
        self.assertEqual(len(self.calls), 1)

    def test_candidate_regrades_result_summary_and_binds_proposal(self):
        result = runner.run(self.host, self.native, self.admit())
        self.assertEqual(result['status'], 'shadow_accepted')
        sid = result['study_id']
        candidate = runner.candidate(self.host, sid)
        self.assertFalse(candidate['activation_authorized'])
        with sqlite3.connect(runner.database(self.host)) as db:
            encoded, lesson = db.execute('SELECT result,lesson FROM studies WHERE id=?', (sid,)).fetchone()
            forged = json.loads(encoded)
            forged['phases']['final']['wins'] = 999
            db.execute('UPDATE studies SET result=? WHERE id=?', (runner.encode(forged), sid))
        with self.assertRaises(ValueError):
            runner.candidate(self.host, sid)
        with sqlite3.connect(runner.database(self.host)) as db:
            db.execute('UPDATE studies SET result=?,lesson=? WHERE id=?', (encoded, lesson + ' Forged addition.', sid))
        with self.assertRaises(ValueError):
            runner.candidate(self.host, sid)

    def test_candidate_rejects_scope_and_source_snapshot_tampering(self):
        result = runner.run(self.host, self.native, self.admit())
        sid = result['study_id']
        target = self.host.directory / 'cohort-study-snapshots' / sid / 'cohort.json'
        original = target.read_text()
        modified = json.loads(original)
        modified['splits']['final'][0]['bundle']['sources'][0]['fields']['success'] = True
        target.write_text(json.dumps(modified))
        with self.assertRaises(ValueError):
            runner.candidate(self.host, sid)
        target.write_text(original)
        (target.parent / 'runner.py').write_text('tampered runner')
        with self.assertRaises(ValueError):
            runner.candidate(self.host, sid)

    def test_candidate_regrades_even_rehashed_corrupted_receipt(self):
        result = runner.run(self.host, self.native, self.admit())
        sid = result['study_id']
        with sqlite3.connect(runner.database(self.host)) as db:
            number, encoded = db.execute("SELECT number,receipt FROM receipts WHERE study=? AND phase='final' AND arm='lesson'", (sid,)).fetchone()
            receipt = json.loads(encoded)
            receipt['value'][self.data['splits']['final'][0]['id']]['decision'] = 'supported'
            # Simulate lower-level storage corruption beyond normal immutable API.
            db.execute('DROP TRIGGER receipts_no_update')
            db.execute('UPDATE receipts SET receipt=?,output_hash=? WHERE study=? AND number=?',
                       (runner.encode(receipt), runner.digest(receipt), sid, number))
        with self.assertRaises(ValueError):
            runner.candidate(self.host, sid)


if __name__ == '__main__':
    unittest.main()
