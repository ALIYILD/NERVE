import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from nerve_awim.memory_gateway.observability import (build_audit_event, prometheus_metrics,
    make_manifest, atomic_json, read_manifest, readiness, FAULT_CHECKS)
from nerve_awim.memory_gateway.contracts import MemoryMetrics
from dataclasses import asdict

spec = importlib.util.spec_from_file_location('memory_operations_fixture', Path(__file__).resolve().parents[1]/'scripts/memory_operations.py')
operations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operations)


class MemoryOperationsTests(unittest.TestCase):
    def manifests(self):
        return [make_manifest(gate, 'a'*40, 'b'*64,
            [{'name': name, 'passed': True, 'count': 1} for name in sorted(FAULT_CHECKS if gate == 'faults' else {'unittest_suite'})], .1)
            for gate in ('cpu', 'security', 'api', 'faults')]

    def ready(self, manifests, **kwargs):
        return readiness(manifests, revision='a'*40, source_sha256='b'*64, **kwargs)

    def test_audit_event_omits_payloads_scope_and_credentials(self):
        event = build_audit_event('scope_revoked', 'success')
        self.assertEqual(set(event), {'event', 'status', 'trace_id', 'created_at'})
        self.assertRegex(event['trace_id'], '^[0-9a-f]{32}$')
        self.assertNotEqual(event['trace_id'], build_audit_event('scope_revoked', 'success')['trace_id'])
        for name, status in [('patient-secret', 'success'), ('scope_deleted', 'bearer-token')]:
            with self.assertRaises(ValueError):
                build_audit_event(name, status)

    def test_metrics_are_exact_typed_counters_without_labels(self):
        values = asdict(MemoryMetrics(queries=3))
        output = prometheus_metrics(values)
        self.assertIn('nerve_memory_queries_total 3', output)
        self.assertNotIn('{', output)
        for bad in ({**values, 'tenant': 'sensitive'}, {**values, 'queries': True}, {**values, 'queries': -1}, {**values, 'queries': float('nan')}):
            with self.assertRaises(ValueError):
                prometheus_metrics(bad)

    def test_actual_fault_harness_reopen_quota_corruption_and_provider_failure(self):
        checks = operations.faults()
        self.assertEqual({c['name'] for c in checks}, FAULT_CHECKS)
        self.assertTrue(all(c['passed'] for c in checks), checks)

    def test_readiness_requires_complete_current_passing_evidence(self):
        rows = self.manifests()
        self.assertTrue(self.ready(rows)['cpu_research_ready'])
        self.assertFalse(self.ready(rows[:-1])['cpu_research_ready'])
        rows[0]['checks'][0]['passed'] = False
        self.assertEqual(self.ready(rows)['gates']['cpu'], 'failed')
        rows = self.manifests()
        rows[1]['revision'] = 'c'*40
        self.assertEqual(self.ready(rows)['gates']['security'], 'wrong_revision')
        rows[1]['revision'] = 'a'*40
        rows[1]['source_sha256'] = 'c'*64
        self.assertEqual(self.ready(rows)['gates']['security'], 'changed_worktree')

    def test_old_future_duplicate_and_incomplete_manifests_fail(self):
        rows = self.manifests()
        now = rows[0]['created_at']
        rows[0]['created_at'] = now - 86401
        rows[1]['created_at'] = now + 1
        report = self.ready(rows, now=now)
        self.assertEqual(report['gates']['cpu'], 'stale_or_future')
        self.assertEqual(report['gates']['security'], 'stale_or_future')
        with self.assertRaises(ValueError):
            self.ready([rows[0], rows[0]])
        rows = self.manifests()
        rows[-1]['checks'].pop()
        self.assertEqual(self.ready(rows)['gates']['faults'], 'incomplete_checks')

    def test_atomic_manifest_roundtrip_mode_and_strict_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'evidence.json'
            value = self.manifests()[0]
            atomic_json(path, value)
            self.assertEqual(read_manifest(path), value)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.write_text(json.dumps({**value, 'clinical_payload': 'bad'}))
            with self.assertRaises(ValueError):
                read_manifest(path)
            path.write_text('x'*65537)
            with self.assertRaises(ValueError):
                read_manifest(path)

    def test_cpu_pass_never_claims_clinical_or_gpu_deployment(self):
        report = self.ready(self.manifests())
        self.assertFalse(report['deployed'])
        self.assertIn('blocked', report['gpu_restore'])
        self.assertEqual(report['licence'], 'unverified')
        self.assertIn('prohibited', report['clinical'])

    def test_verification_rejects_skipped_required_tests(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        for summary, expected in [('OK (skipped=2)', False), ('OK (skipped=0)', True), ('OK', True)]:
            result = SimpleNamespace(returncode=0, stdout='', stderr='Ran 12 tests in 0.3s\n'+summary)
            with patch.object(operations.subprocess, 'run', return_value=result) as run:
                checks = operations.verify('api')
                self.assertEqual(run.call_args.kwargs['timeout'], 1800)
            self.assertEqual(checks[0]['passed'], expected)
            self.assertEqual(checks[0]['count'], 12)
