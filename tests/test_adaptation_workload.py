from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from nerve_awim.adaptation_workload import load, validate
from nerve_awim.auto_adaptation_goal import build, dataset


def manifest(domain='clinical_os'):
    return {'schema': 'nerve-adaptation-workload-v1', 'goal_id': 'external-replay',
        'domain': domain, 'scope': 'authorized-local-replay',
        'provenance': {'source_ref': 'synthetic-test', 'labeler_ref': 'fixture-judge', 'data_kind': 'synthetic'},
        'target': {'min_gain': .1, 'min_monitor_accuracy': 1., 'min_switches': 2, 'max_evaluation_calls': 32},
        'phases': [{s: dataset(domain, p, s, 8 if s == 'monitor' else 4)
                    for s in ('observe', 'selection', 'retained', 'monitor')} for p in range(3)]}


class WorkloadTests(unittest.TestCase):
    def test_external_goal_uses_declared_scope_targets_and_resume(self):
        for domain in ('clinical_os', 'perfflux'):
            value = manifest(domain)
            with tempfile.TemporaryDirectory() as root:
                goal = build(root, (domain,), workload=value)
                partial = goal.run(max_ticks=9)
                self.assertEqual(partial['status'], 'active')
                final = build(root, (domain,), workload=value).run()
                self.assertEqual(final['status'], 'complete')
                report = next(iter(final['tasks'][-1]['receipt']['domains'].values()))
                self.assertEqual(report['adaptive_hits'], 28)
                self.assertTrue(report['target_met'])
                self.assertFalse(report['provenance_independently_attested'])
                self.assertEqual(build(root, (domain,), workload=value).run(), final)

    def test_target_or_dataset_changes_cannot_resume(self):
        value = manifest()
        with tempfile.TemporaryDirectory() as root:
            build(root, ('clinical_os',), workload=value).tick()
            modified = deepcopy(value)
            modified['target']['min_gain'] = .2
            with self.assertRaises(ValueError):
                build(root, ('clinical_os',), workload=modified)
            modified = deepcopy(value)
            modified['provenance']['source_ref'] = 'another-source'
            with self.assertRaises(ValueError):
                build(root, ('clinical_os',), workload=modified)

    def test_budget_is_checked_before_candidate_calls(self):
        value = manifest()
        value['target']['max_evaluation_calls'] = 0
        with tempfile.TemporaryDirectory() as root:
            result = build(root, ('clinical_os',), workload=value).run()
            self.assertEqual(result['status'], 'blocked')
            evaluations = [t['receipt']['evaluation'] for t in result['tasks'] if t['id'].endswith(':evaluate')]
            self.assertEqual(sum(r.get('calls', 0) for r in evaluations), 0)
            self.assertIn('evaluation_budget_exhausted', str(evaluations))

    def test_unachieved_target_cannot_complete_parent(self):
        value = manifest()
        value['target']['min_gain'] = .9
        with tempfile.TemporaryDirectory() as root:
            result = build(root, ('clinical_os',), workload=value).run()
            self.assertEqual(result['status'], 'blocked')
            verifier = next(t for t in result['tasks'] if t['id'].endswith(':verify-recovery'))
            self.assertFalse(verifier['receipt']['target_met'])

    def test_cross_partition_duplicate_rejected(self):
        value = manifest()
        value['phases'][1]['selection'][0] = deepcopy(value['phases'][0]['observe'][0])
        with self.assertRaises(ValueError):
            validate(value)

    def test_invalid_labels_and_domain_rejected_before_checkpoint(self):
        value = manifest('perfflux')
        value['phases'][0]['observe'][0]['expected']['digests'][0] = 'incorrect'
        with self.assertRaises(ValueError):
            validate(value)
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                build(root, ('perfflux',), workload=manifest())
            self.assertFalse((Path(root)/'goal.json').exists())

    def test_manifest_budget_duplicate_keys_and_invalid_targets(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'workload.json'
            path.write_text('{"schema": "a", "schema": "b"}')
            with self.assertRaises(ValueError):
                load(path)
            path.write_bytes(b'x' * 1_000_001)
            with self.assertRaises(ValueError):
                load(path)
            value = manifest()
            path.write_text(json.dumps(value))
            self.assertEqual(load(path), value)
        for field, number in (('min_gain', float('nan')), ('min_switches', True), ('max_evaluation_calls', 65)):
            value = manifest()
            value['target'][field] = number
            with self.assertRaises(ValueError):
                validate(value)

    def test_patient_provenance_and_unknown_fields_rejected(self):
        value = manifest()
        value['provenance']['data_kind'] = 'patient'
        with self.assertRaises(ValueError):
            validate(value)
        value = manifest()
        value['production_authorized'] = True
        with self.assertRaises(ValueError):
            validate(value)

    def test_validation_copies_manifest_and_hash_is_key_order_independent(self):
        value = manifest()
        result, digest = validate(value)
        self.assertEqual(digest, validate(dict(reversed(list(value.items()))))[1])
        result['goal_id'] = 'changed'
        self.assertEqual(value['goal_id'], 'external-replay')
