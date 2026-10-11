"""Routing drills use a deliberately faulty test-only AST baseline.

They exercise eligible-release mechanics, not superiority over the real AST tool.
"""
from hashlib import sha256
import unittest
from unittest.mock import patch
import test_repository_host_v25 as fixtures

from nerve_awim.agent_learning_v12 import AgentTask
from nerve_awim.repository_agents_v20 import CONTEXT
from scripts.serve_repository_host_v25 import build_host


@unittest.skipIf(fixtures.jwt is None, 'PyJWT[crypto] required')
class BoundHostTests(unittest.TestCase):
    token = fixtures.HostTests.token
    request = fixtures.HostTests.request

    @classmethod
    def setUpClass(cls):
        fixtures.HostTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.HostTests.setUp(self)
        self.engine = self.host.engine
        self.actors = {r: self.engine.authority.issue('a', 'repo', r)
                       for r in ('operator', 'trainer', 'evaluator', 'runtime', 'auditor')}
        self.base = self.engine.status(self.actors['operator'])['active_release']
        # Explicit test fault creates a candidate eligible for the routing drill.
        self.engine._registry[(CONTEXT, 'ast-inventory')] = lambda _: []
        for n in range(3):
            self.engine.learn_from_task(self.actors['trainer'], self.task(n))
        self.candidate = self.candidate_at(3)
        self.controller = self.host.deployments.controller
        self.trial = self.controller.start(self.actors['operator'], self.candidate,
            expected_generation=0, reason='test-trial', percent=25, required_successes=5)

    def task(self, n):
        return AgentTask(f'bound-{n}', CONTEXT, f'# PRIVATE-SOURCE-{n}\ndef fn_{n}(): pass')

    def candidate_at(self, start):
        candidate = self.engine.freeze_candidate(self.actors['trainer'])
        result = self.engine.evaluate_candidate(self.actors['evaluator'], candidate,
                                                [self.task(n) for n in range(start, start + 5)])
        self.assertEqual(result['status'], 'passed')
        return candidate

    def bind(self):
        return self.host.deployments.bind(self.actors['operator'], self.trial,
            expected_generation=0, expected_version=0, reason='test-binding')

    def selected(self, start, yes=True):
        for n in range(start, start+10000):
            task = self.task(n)
            _, digest = self.engine._task(task)
            if (int(sha256((self.trial+':'+digest).encode()).hexdigest(), 16) % 100 < 25) == yes:
                return task
        self.fail('no sample')

    def send(self, task):
        return self.request({'task_id': task.task_id, 'source': task.payload})

    def ready(self):
        self.bind()
        for n in range(5):
            status, result, _ = self.send(self.selected(100+n*10000))
            self.assertEqual(status, 200)
            self.assertTrue(result['canary']['used'])
        self.assertEqual(self.controller.report(self.actors['auditor'], self.trial)['phase'], 'ready')

    def promote(self):
        self.ready()
        self.controller.promote(self.actors['operator'], self.trial, expected_generation=0,
                                reason='test-promotion', monitor_latency_ms=1000)

    def test_scoped_binding_role_generation_and_version(self):
        with self.assertRaises(PermissionError):
            self.host.deployments.bind(self.actors['runtime'], self.trial,
                expected_generation=0, expected_version=0, reason='denied')
        for generation, version in ((1, 0), (0, 1)):
            with self.assertRaises(ValueError):
                self.host.deployments.bind(self.actors['operator'], self.trial,
                    expected_generation=generation, expected_version=version, reason='stale')
        other = self.engine.authority.issue('b', 'repo', 'operator')
        with self.assertRaises(LookupError):
            self.host.deployments.bind(other, self.trial, expected_generation=0, expected_version=0, reason='wrong-tenant')
        self.assertEqual(self.bind()['version'], 1)
        with self.assertRaises(ValueError):
            self.bind()

    def test_http_samples_and_does_not_train(self):
        self.bind()
        baseline = self.send(self.selected(100, False))[1]
        candidate = self.send(self.selected(200))[1]
        self.assertEqual(baseline['release'], self.base)
        self.assertEqual(candidate['strategy'], 'regex-inventory')
        self.assertEqual(candidate['mode'], 'controlled')
        self.assertEqual(candidate['learning'], 'not_collected_for_training')
        self.assertEqual(self.host.adapters[('a', 'repo')].pending, 0)
        report = self.request(path='/v1/evidence', method='GET')[1]
        self.assertEqual(report['trial']['outcomes'], {'passed': 1})
        self.assertTrue(report['routing_eligible'])
        self.assertEqual(self.request(path='/v1/evidence', method='GET', token=self.token(sub='bob'))[1]['mode'], 'shadow')

    def test_monitor_failure_rolls_back_through_http_and_survives_restart(self):
        self.promote()
        status, result, _ = self.send(self.task(999999))
        self.assertEqual(status, 200)
        self.assertTrue(result['monitor']['used'])
        self.engine.judge = lambda *_: False
        status, result, _ = self.send(self.task(999998))
        self.assertEqual(status, 200)
        self.assertEqual(result['monitor']['reason'], 'quality_failure')
        self.assertEqual(result['release'], self.base)
        self.assertEqual(result['generation'], 2)
        self.host = build_host(self.config, self.db)
        status, result, _ = self.send(self.task(999997))
        self.assertEqual(status, 200)
        self.assertEqual(result['release'], self.base)
        report = self.request(path='/v1/evidence', method='GET')[1]
        self.assertTrue(report['routing_eligible'])
        self.assertEqual(report['monitor']['outcomes'], {'passed': 1, 'quality_failure': 1})
        self.assertNotIn(b'PRIVATE-SOURCE', self.db.read_bytes())

    def test_ready_waits_and_unmonitored_promotion_is_not_served(self):
        self.ready()
        self.assertEqual(self.send(self.task(999999))[1]['release'], self.base)
        self.controller.promote(self.actors['operator'], self.trial, expected_generation=0, reason='unmonitored')
        self.assertEqual(self.send(self.task(999998))[0], 503)
        with self.assertRaises(LookupError):
            build_host(self.config, self.db)

    def test_stopped_trial_continues_baseline(self):
        self.bind()
        self.controller.stop(self.actors['operator'], self.trial, reason='operator-stop')
        result = self.send(self.task(999999))[1]
        self.assertEqual(result['release'], self.base)
        self.assertEqual(result['canary']['reason'], 'stopped')

    def test_inflight_monitor_operator_stop_returns_baseline(self):
        self.promote()
        original = self.engine._registry[(CONTEXT, 'regex-inventory')]
        def stopped(source):
            self.controller.monitor.stop(self.actors['operator'], self.trial,
                expected_generation=1, reason='stop-inflight')
            return original(source)
        self.engine._registry[(CONTEXT, 'regex-inventory')] = stopped
        status, result, _ = self.send(self.task(999999))
        self.assertEqual(status, 200)
        self.assertEqual(result['release'], self.base)
        self.assertEqual(result['generation'], 2)

    def test_unrelated_rollback_during_attempt_fails_closed(self):
        self.promote()
        original = self.engine._registry[(CONTEXT, 'regex-inventory')]
        def changed(source):
            self.engine.rollback(self.actors['operator'], self.base, expected_generation=1, reason='external-change')
            return original(source)
        self.engine._registry[(CONTEXT, 'regex-inventory')] = changed
        self.assertEqual(self.send(self.task(999999))[0], 503)
        self.assertEqual(self.engine.status(self.actors['auditor'])['generation'], 2)
        report = self.request(path='/v1/evidence', method='GET')[1]
        self.assertFalse(report['routing_eligible'])

    def test_rebinding_during_attempt_suppresses_old_response(self):
        self.bind()
        next_candidate = self.candidate_at(500000)
        original = self.engine._registry[(CONTEXT, 'regex-inventory')]
        def changed(source):
            self.controller.stop(self.actors['operator'], self.trial, reason='replace-trial')
            trial = self.controller.start(self.actors['operator'], next_candidate, expected_generation=0,
                                           reason='new-trial', percent=25, required_successes=5)
            self.host.deployments.bind(self.actors['operator'], trial, expected_generation=0,
                                       expected_version=1, reason='new-binding')
            return original(source)
        self.engine._registry[(CONTEXT, 'regex-inventory')] = changed
        self.assertEqual(self.send(self.selected(100))[0], 503)
        report = self.request(path='/v1/evidence', method='GET')[1]
        self.assertEqual(report['binding_version'], 2)
        self.assertTrue(report['routing_eligible'])

    def test_pending_shadow_is_discarded_on_binding(self):
        self.send(self.task(999999))
        self.assertEqual(self.host.adapters[('a', 'repo')].pending, 1)
        self.bind()
        self.assertEqual(self.host.drain()[('a', 'repo')]['discarded_after_binding'], 1)
        self.assertEqual(self.engine.status(self.actors['auditor'])['task_counts']['train'], 3)

    def test_duplicate_and_reserved_monitor_tasks_use_prior_route(self):
        self.promote()
        task = self.task(999999)
        self.send(task)
        result = self.send(task)[1]
        self.assertEqual(result['release'], self.base)
        self.assertEqual(result['monitor']['reason'], 'not_fresh_or_reserved')
        reserved = self.task(999998)
        _, digest = self.engine._task(reserved)
        with self.engine._db() as con:
            con.execute('INSERT INTO gl_holdout_reservations VALUES(?,?,?,?)', ('a', 'repo', reserved.task_id, digest))
        self.assertEqual(self.send(reserved)[1]['release'], self.base)

    def test_offline_bind_command_persists_without_activating(self):
        import os
        import subprocess
        import sys
        run = subprocess.run([sys.executable, 'scripts/bind_repository_trial_v26.py',
            '--database', str(self.db), '--tenant', 'a', '--agent', 'repo', '--canary', self.trial,
            '--expected-generation', '0', '--expected-version', '0', '--reason', 'cli-test'],
            env={**os.environ, 'PYTHONPATH': 'src'}, text=True, capture_output=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.engine.status(self.actors['auditor'])['generation'], 0)
        self.assertEqual(self.host.deployments.snapshot(('a', 'repo'))['version'], 1)
        self.assertEqual(self.send(self.selected(100))[0], 200)

    def test_pending_monitor_after_restart_uses_prior_route(self):
        self.promote()
        with self.engine._db() as con:
            con.execute('INSERT INTO gl_promotion_outcomes VALUES(?,?,?,NULL)', (self.trial, 'crashed', 'pending'))
        self.host = build_host(self.config, self.db)
        result = self.send(self.task(999999))[1]
        self.assertEqual(result['release'], self.base)
        self.assertEqual(result['monitor']['reason'], 'pending_attempt')

    def test_latency_failure_through_http(self):
        self.promote()
        with patch('nerve_awim.promotion_monitor_v24.perf_counter', side_effect=(0, 2)):
            result = self.send(self.task(999999))[1]
        self.assertEqual(result['monitor']['reason'], 'latency_failure')
        self.assertEqual(result['release'], self.base)

    def test_no_http_binding_authority(self):
        self.assertEqual(self.request(path='/v1/bind')[0], 404)
        self.assertEqual(self.request({'task_id': 'bad', 'source': 'pass', 'canary': self.trial})[0], 400)

    def test_standalone_http_promotion_rollback_restart(self):
        import json
        import os
        from pathlib import Path
        import select
        import socket
        import subprocess
        import sys
        from urllib.request import Request, urlopen
        self.promote()
        config = Path(self.temp.name) / 'public-config.json'
        config.write_text(json.dumps(self.config))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        def stop(process):
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)
        def start():
            process = subprocess.Popen([sys.executable, 'scripts/serve_repository_host_v25.py',
                '--config', str(config), '--database', str(self.db), '--port', str(port)],
                env={**os.environ, 'PYTHONPATH': 'src'}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                ready, _, _ = select.select([process.stdout], [], [], 10)
                self.assertTrue(ready, 'startup timed out')
                self.assertIn('listening on 127.0.0.1', process.stdout.readline())
                return process
            except BaseException:
                stop(process)
                raise
        def call(path, body=None):
            request = Request(f'http://127.0.0.1:{port}'+path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+self.token()})
            with urlopen(request, timeout=5) as response:
                return json.load(response)
        process = start()
        try:
            good = call('/v1/tasks', {'task_id': 'wire-good', 'source': 'def visible(): pass'})
            self.assertTrue(good['monitor']['used'])
            # Real token judge rejects regex's nested-function inclusion.
            failed = call('/v1/tasks', {'task_id': 'wire-regression',
                'source': 'def outer():\n    def nested(): pass'})
            self.assertEqual(failed['monitor']['reason'], 'quality_failure')
            self.assertEqual(failed['value'], ['outer'])
            self.assertEqual(failed['release'], self.base)
            self.assertEqual(failed['generation'], 2)
        finally:
            stop(process)
        process = start()
        try:
            evidence = call('/v1/evidence')
            self.assertTrue(evidence['routing_eligible'])
            self.assertEqual(evidence['monitor']['phase'], 'rolled_back')
            value = call('/v1/tasks', {'task_id': 'wire-restarted', 'source': 'def restarted(): pass'})
            self.assertEqual(value['release'], self.base)
            self.assertEqual(value['value'], ['restarted'])
        finally:
            stop(process)
