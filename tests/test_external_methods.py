import copy
import json
from pathlib import Path
import tempfile
import unittest

from nerve_awim.external_methods.contracts import register, route, validate_patch, canonical, digest
from nerve_awim.external_methods.gate import Gate, IntegrityError
from nerve_awim.external_methods.evidence import ResponseCache, Archive, RepairPlanner, SkillLibrary, skill_record, probe_status, review_readiness
from nerve_awim.external_methods.evaluator import diagnose, verify_domain, score
from nerve_awim.external_methods.workflow import simulation_registration
from nerve_awim.external_methods.runner import evaluate, robustness_verdict


class ExternalMethodsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.key = b'x' * 32
        self.gate = Gate(self.root/'gate', key=self.key)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.gate.close)

    def registration(self, index=0, **gate):
        r = simulation_registration(index, alpha=.01)
        r['gate'].update(gate)
        return r

    def outcome(self, r, item, win=True, **kw):
        self.gate.claim(r['study_id'], item, 'synthetic')
        values = dict(candidate=win, incumbent=not win, controls={'always_abstain': not win, 'random': not win},
                      violations=[], measured_capacity=r['capacity'])
        values.update(kw)
        self.gate.record(r['study_id'], item, **values)

    def test_wallet_exhaustion_before_allocation(self):
        for i in range(5): self.gate.start(self.registration(i))
        head = self.gate.ledger_head()
        with self.assertRaisesRegex(PermissionError, 'wallet_exhausted'): self.gate.start(self.registration(5))
        self.assertEqual(head, self.gate.ledger_head())

    def test_live_holdout_never_enabled(self):
        r = self.registration(); r['bank']['split'] = 'holdout'
        with self.assertRaises(PermissionError): self.gate.start(r)

    def test_anytime_win_and_restart(self):
        r = self.registration(); self.gate.start(r)
        for i in range(12): self.outcome(r, str(i))
        before = canonical(self.gate.report(r['study_id']))
        other = Gate(self.root/'gate', key=self.key)
        self.addCleanup(other.close)
        self.assertEqual(before, canonical(other.report(r['study_id'])))
        self.assertEqual('exploratory_only', other.report(r['study_id'])['verdict'])
        self.assertEqual('cached', other.claim(r['study_id'], '0', 'synthetic'))
        self.assertFalse(other.report(r['study_id'])['promotion_authorized'])

    def test_crash_claim_never_repeats_inference(self):
        r = self.registration(); self.gate.start(r)
        self.assertEqual('dispatch_once', self.gate.claim(r['study_id'], 'a', 'synthetic'))
        self.assertEqual('incomplete_infrastructure', self.gate.claim(r['study_id'], 'a', 'synthetic'))
        with self.assertRaises(PermissionError): self.gate.claim(r['study_id'], 'b', 'synthetic')
        self.assertEqual(0, self.gate.report(r['study_id'])['items'])

    def test_tampering_detected(self):
        r = self.registration(); self.gate.start(r); self.outcome(r, 'a')
        self.gate.db.execute("UPDATE events SET body='{}' WHERE seq=4")
        with self.assertRaises(IntegrityError): self.gate.report(r['study_id'])

    def test_truncated_history_detected(self):
        r = self.registration(); self.gate.start(r); self.outcome(r, 'a')
        self.gate.db.execute('DELETE FROM events WHERE seq=4')
        with self.assertRaises(IntegrityError): self.gate.report(r['study_id'])

    def test_external_writer_tampering_detected(self):
        import sqlite3
        r = self.registration(); self.gate.start(r)
        with sqlite3.connect(self.root/'gate/gate.sqlite') as db:
            db.execute("UPDATE events SET body='{}' WHERE seq=2")
        with self.assertRaises(IntegrityError): self.gate.report(r['study_id'])

    def test_all_controls_must_be_beaten(self):
        r = self.registration(item_budget=12); self.gate.start(r)
        for i in range(12): self.outcome(r, str(i), controls={'always_abstain': True, 'random': False})
        self.assertEqual('insufficient_power', self.gate.report(r['study_id'])['verdict'])

    def test_futility(self):
        r = self.registration(); self.gate.start(r)
        for i in range(5): self.outcome(r, str(i), win=False)
        self.assertEqual('reject_futility', self.gate.report(r['study_id'])['verdict'])

    def test_changed_registration_and_outcome_refused(self):
        r = self.registration(); self.gate.start(r); self.outcome(r, 'a')
        changed = copy.deepcopy(r); changed['gate']['bet'] = .25
        with self.assertRaises(IntegrityError): self.gate.start(changed)
        with self.assertRaises(IntegrityError): self.outcome(r, 'a', win=False)

    def test_exposed_item_not_reused(self):
        a, b = self.registration(0), self.registration(1)
        self.gate.start(a); self.outcome(a, 'a'); self.gate.start(b)
        with self.assertRaisesRegex(PermissionError, 'already_allocated'): self.gate.claim(b['study_id'], 'a', 'synthetic')

    def test_ties_and_budget(self):
        r = self.registration(item_budget=2); self.gate.start(r)
        for i in range(2): self.outcome(r, str(i), incumbent=True, controls={'always_abstain': True, 'random': True})
        result = self.gate.report(r['study_id'])
        self.assertEqual('insufficient_power', result['verdict'])
        self.assertEqual(0, result['log_e']['incumbent'])

    def test_domain_and_capacity_veto(self):
        r = self.registration(); self.gate.start(r); self.outcome(r, 'a', violations=['bad_source'])
        self.assertEqual('verifier_veto', self.gate.report(r['study_id'])['verdict'])
        r = self.registration(1); self.gate.start(r)
        cap = dict(r['capacity'], model_calls=1); self.outcome(r, 'b', measured_capacity=cap)
        self.assertEqual('capacity_declaration_mismatch', self.gate.report(r['study_id'])['verdict'])

    def test_plateau_and_capacity_adjustment(self):
        r = self.registration(minimum_net_wins=20); self.gate.start(r)
        for i in range(12): self.outcome(r, str(i))
        self.assertEqual('plateau', self.gate.report(r['study_id'])['verdict'])
        r = self.registration(1); r['capacity'] = dict(r['capacity'], model_calls=1); r['prices']['model_calls'] = 2
        self.gate.start(r)
        for i in range(12): self.outcome(r, 'b'+str(i))
        self.assertEqual('gain_not_capacity_adjusted', self.gate.report(r['study_id'])['verdict'])

    def test_registration_rejects_incomplete_and_nonfinite(self):
        r = self.registration(); del r['pilot_history']
        with self.assertRaises(ValueError): register(r)
        r = self.registration(); r['gate']['alpha'] = float('nan')
        with self.assertRaises(ValueError): register(r)
        r = self.registration(); r['robustness']['stateful'] = True
        with self.assertRaises(ValueError): register(r)
        r = self.registration(); r['bank']['fresh_items'] = False
        with self.assertRaises(ValueError): register(r)

    def test_data_seams_rotation_and_walls(self):
        with self.assertRaises(ValueError): validate_patch({'seam': 'prompt-fragment', 'patch': {'text': 'x', 'import': 'os'}})
        with self.assertRaises(ValueError): validate_patch({'seam': 'code', 'patch': {'exec': 'x'}})
        result = route({'wrong_value': 10, 'new_unknown': 1}, {'wrong_value:prompt-fragment': 3}, 3)
        self.assertEqual('retrieval-order', result['seam']); self.assertEqual(['new_unknown'], result['walls'])

    def test_diagnosis_and_domain_are_independent(self):
        task = {'query': "What is sample A's mass in mg?", 'evidence': [
            {'content': 'Sample A has mass 3 mg.', 'source_id': 'a', 'current': True},
            {'content': 'Sample B has mass 4 mg.', 'source_id': 'b', 'current': True}]}
        out = dict(status='answer', entity='B', measurement='mass', value='4', unit='mg', source_id='b')
        self.assertIn('decoy_selected', diagnose(task, out))
        self.assertIn('source_query_mismatch', verify_domain(task, out))
        self.assertFalse(score(task, out))
        self.assertEqual(['abstention_rule_missing'], verify_domain(task, {'status': 'abstain'}))

    def test_cache_integrity_and_holdout_manifest_privacy(self):
        cache = ResponseCache(self.root/'cache', split='holdout')
        request = dict(model_digest='a', prompt='private', params={}, replicate=0)
        key = cache.put(request, 'secret')
        self.assertEqual('secret', cache.get(key)['response'])
        self.assertNotIn(key, canonical(cache.manifest()))
        with self.assertRaises(ValueError): cache.put(request, 'changed')
        (cache.root/(key+'.json')).write_text('{}')
        with self.assertRaises((KeyError, ValueError)): cache.get(key)

    def test_archive_reeligibility_and_lesson(self):
        archive = Archive(self.root/'archive.sqlite'); self.addCleanup(archive.db.close)
        identity = archive.retain('c', bank='b', model='m', incumbent='i', study='s', verdict='rejected', lesson='a hypothesis')
        self.assertFalse(archive.eligible(identity, bank='b', model='m', incumbent='i')['eligible'])
        self.assertEqual(['incumbent'], archive.eligible(identity, bank='b', model='m', incumbent='j')['changed'])

    def test_probes_and_review_fail_closed(self):
        self.assertEqual('white-box: unavailable', probe_status()['status'])
        result = probe_status(model_parameters=7_000_000_000, gpu=True, toolkit_reviewed=True,
            validation=dict(preregistered=True, held_out_dev=True, steering_confirmed=True, tier_c_signed=True,
                            predictive_power=.5, threshold=.9))
        self.assertEqual('retired', result['status'])
        self.assertIn('human_signature', review_readiness('A', {})['missing'])

    def test_wired_runner_replay_has_zero_calls(self):
        tasks = [dict(task_id=str(i), split='synthetic', stratum='synthetic',
            query="What is sample A's mass in mg?", evidence=[dict(content='Sample A has mass 3 mg.', source_id='a', current=True)]) for i in range(15)]
        r = self.registration(); r['bank']['manifest'] = digest(tasks)
        calls = []
        def evaluator(request):
            calls.append(request)
            return dict(candidate=dict(status='answer', entity='A', measurement='mass', value='3', unit='mg', source_id='a'),
                incumbent={'status': 'abstain'}, always_abstain={'status': 'abstain'}, random={'status': 'abstain'},
                capacity=r['capacity'], latency=1, usage={}, abstention_rule=None)
        first = evaluate(r, tasks, self.root/'run', key=self.key, evaluator=evaluator)
        count = len(calls)
        second = evaluate(r, tasks, self.root/'run', key=self.key, evaluator=evaluator)
        self.assertEqual(count, len(calls)); self.assertEqual(canonical(first), canonical(second))
        self.assertEqual('exploratory_only', first['gate']['verdict'])

    def test_runner_crash_after_cache_recovers_without_inference(self):
        from unittest.mock import patch
        tasks = [dict(task_id='a', split='synthetic', stratum='synthetic',
            query="What is sample A's mass in mg?", evidence=[dict(content='Sample A has mass 3 mg.', source_id='a', current=True)])]
        r = self.registration(item_budget=1); r['bank']['manifest'] = digest(tasks)
        response = dict(candidate={'status': 'abstain'}, incumbent={'status': 'abstain'}, always_abstain={'status': 'abstain'},
            random={'status': 'abstain'}, capacity=r['capacity'], latency=1, usage={}, abstention_rule='evidence_required')
        with patch.object(Gate, 'record', side_effect=RuntimeError('simulated_crash')):
            with self.assertRaises(RuntimeError): evaluate(r, tasks, self.root/'run', key=self.key, evaluator=lambda _: response)
        def no_call(_): raise AssertionError('repeated inference')
        result = evaluate(r, tasks, self.root/'run', key=self.key, evaluator=no_call)
        self.assertEqual(1, result['gate']['items'])

    def test_order_reversal_blocks_claim(self):
        self.assertEqual('order_dependent', robustness_verdict([{'seed': 1, 'gain': .2}, {'seed': 2, 'gain': -.1}], [1,2])['status'])
        self.assertEqual('incomplete', robustness_verdict([{'seed': 1, 'gain': .2}], [1,2])['status'])

    def test_persistent_attempt_budget_and_skill_usage(self):
        planner = RepairPlanner(self.root/'repairs.sqlite', budget=1)
        self.addCleanup(planner.db.close)
        first = planner.propose('a', {'wrong_value': 1})
        self.assertEqual('prompt-fragment', first['seam'])
        self.assertEqual(first, planner.propose('a', {'wrong_value': 1}))
        self.assertEqual('retrieval-order', planner.propose('b', {'wrong_value': 1})['seam'])
        self.assertEqual('attempt_budget_exhausted', planner.propose('c', {'wrong_value': 1})['status'])
        library = SkillLibrary(self.root/'skills.sqlite'); self.addCleanup(library.db.close)
        record = skill_record(skill_id='s', version=1, patch=first['patch'], description='test',
            evidence_bundle='e', capacity_delta={}, signed_by='human-review-fixture')
        identity = library.add(record, 'wrong_value')
        self.assertEqual([record], library.retrieve('prompt-fragment', 'wrong_value'))
        self.assertEqual([], library.retrieve('abstention-rule', 'wrong_value'))
        self.assertEqual(1, library.record_usage(identity, 'e1', 'success')['selected'])
        self.assertEqual(1, library.record_usage(identity, 'e1', 'success')['selected'])
        with self.assertRaises(ValueError): library.record_usage(identity, 'e1', 'failure')

    def test_sealed_cli_input_is_refused_before_read(self):
        import subprocess
        import sys
        command = [sys.executable, str(Path(__file__).resolve().parents[1]/'scripts/run_external_methods.py'),
            'audit-v3', '--receipt', '/does-not-exist', '--development', '/sealed-holdout.json', '--output', str(self.root/'out')]
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('sealed_input_disabled', result.stderr)
        self.assertFalse((self.root/'out').exists())


if __name__ == '__main__': unittest.main()
