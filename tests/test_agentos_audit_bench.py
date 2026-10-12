from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('audit_bench', Path(__file__).resolve().parents[1] / 'scripts/agentos_audit_bench.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class AuditBenchTests(unittest.TestCase):
    def test_gold_controls_pass_but_constant_unknown_does_not(self):
        manifest = bench.build_manifest()
        gold = {case['id']: case['expected'] for case in manifest['cases']}
        report = bench.grade(manifest, gold)
        self.assertEqual(report['passed'], report['total'])
        self.assertGreater(report['supported_claims_total'], 0)
        unknown = dict.fromkeys(gold, {'decision': 'unknown', 'citations': []})
        failed = bench.grade(manifest, unknown)
        self.assertLess(failed['passed'], failed['total'])
        self.assertFalse(report['promotion_authorized'])

    def test_label_without_citations_does_not_pass(self):
        manifest = bench.build_manifest()
        stripped = {case['id']: {'decision': case['expected']['decision'], 'citations': []}
                    for case in manifest['cases']}
        result = bench.grade(manifest, stripped)
        self.assertLess(result['passed'], result['total'])
        self.assertTrue(any(c['category'] == 'citation_mismatch' for c in result['checks']))

    def test_added_or_missing_batch_items_fail(self):
        manifest = bench.build_manifest()
        gold = {case['id']: case['expected'] for case in manifest['cases']}
        for answers in ({}, [], dict(gold, extra={})):
            report = bench.grade(manifest, answers)
            self.assertFalse(report['valid_batch'])
            self.assertEqual(report['passed'], 0)

    def test_tampering_cannot_be_authorized_by_rehash(self):
        manifest = bench.build_manifest()
        modified = deepcopy(manifest)
        modified['cases'][0]['expected']['decision'] = 'supported'
        with self.assertRaises(ValueError):
            bench.validate_manifest(modified)
        modified['manifest_sha256'] = bench.digest({k: v for k, v in modified.items() if k != 'manifest_sha256'})
        with self.assertRaisesRegex(ValueError, 'reviewed development controls'):
            bench.validate_manifest(modified)

    def test_revision_change_fails_closed(self):
        manifest = bench.build_manifest()
        manifest['oracle_revision'] = 'old-oracle'
        manifest['manifest_sha256'] = bench.digest({k: v for k, v in manifest.items() if k != 'manifest_sha256'})
        with self.assertRaisesRegex(ValueError, 'revision changed'):
            bench.validate_manifest(manifest)

    def test_rehashed_boolean_integer_substitution_is_rejected(self):
        manifest = bench.build_manifest()
        manifest['cases'][0]['bundle']['simulated'] = 1
        manifest['manifest_sha256'] = bench.digest({k: v for k, v in manifest.items() if k != 'manifest_sha256'})
        with self.assertRaisesRegex(ValueError, 'reviewed development controls'):
            bench.validate_manifest(manifest)

    def test_exclusive_write_and_strict_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'receipt.json'
            bench.save_new(target, {'saved': True})
            before = target.read_bytes()
            with self.assertRaises(FileExistsError):
                bench.save_new(target, {'saved': False})
            self.assertEqual(target.read_bytes(), before)
            for text in ('{"same":1,"same":2}', '{"number":NaN}'):
                target.write_text(text)
                with self.assertRaises(ValueError):
                    bench.read_json(target)


if __name__ == '__main__':
    unittest.main()
