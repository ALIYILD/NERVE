"""CPU timeout budgeting with injected clocks/transport; no local server calls."""
import io
import unittest
from unittest.mock import Mock, patch

import test_cue_local_registry as fixtures

local = fixtures.local


class LocalTimeoutTests(unittest.TestCase):
    setUp = fixtures.LocalRegistryTests.setUp
    write_config = fixtures.LocalRegistryTests.write_config
    admission = fixtures.LocalRegistryTests.admission
    ready = fixtures.LocalRegistryTests.ready
    request = fixtures.LocalRegistryTests.request

    def setup_transport(self):
        registry = self.ready()
        job = registry['provider'].__self__
        transport = Mock(side_effect=lambda request, timeout: io.BytesIO(b'local response'))
        job.evaluation.transport = transport
        return job, transport

    def test_cpu_generation_can_wait_120_seconds_without_dividing_remaining_time(self):
        job, transport = self.setup_transport()
        with patch.object(local.time, 'monotonic', return_value=job.started + 5):
            adapter = job._consume('evaluation')
            self.assertEqual(adapter.timeout, 120.)
            with adapter.transport(object(), timeout=adapter.timeout) as response:
                self.assertEqual(response.read(), b'local response')
        self.assertEqual(transport.call_args.kwargs['timeout'], 120.)
        self.assertEqual(local._used(self.host), 1)
        self.assertEqual(job.calls, 1)
        # A timeout change must not alter the prompt, sampling or model binding.
        self.assertEqual(adapter.model_config, job.evaluation.model_config)
        self.assertEqual(adapter.options['response_contract'], local.CONTRACT)

    def test_each_http_request_receives_current_remaining_job_budget(self):
        job, transport = self.setup_transport()
        current = [job.started + 10]
        with patch.object(local.time, 'monotonic', side_effect=lambda: current[0]):
            adapter = job._consume('evaluation')
            for elapsed, expected in ((10, 120.), (530, 70.), (599.5, .5)):
                current[0] = job.started + elapsed
                with adapter.transport(object(), timeout=adapter.timeout) as response:
                    response.read()
                self.assertEqual(transport.call_args.kwargs['timeout'], expected)
            current[0] = job.started + 600
            calls = transport.call_count
            with self.assertRaises(TimeoutError):
                with adapter.transport(object(), timeout=adapter.timeout):
                    self.fail('expired job must not dispatch')
            self.assertEqual(transport.call_count, calls)
        self.assertEqual(local._used(self.host), 1)

    def test_response_crossing_deadline_is_closed_and_never_accepted(self):
        job, transport = self.setup_transport()
        current = [job.started + 590]
        response = io.BytesIO(b'late response')
        transport.side_effect = lambda request, timeout: response
        with patch.object(local.time, 'monotonic', side_effect=lambda: current[0]):
            adapter = job._consume('evaluation')
            self.assertEqual(adapter.timeout, 10.)
            with self.assertRaises(TimeoutError):
                with adapter.transport(object(), timeout=adapter.timeout) as stream:
                    stream.read()
                    current[0] = job.started + 601
            self.assertTrue(response.closed)
            with self.assertRaises(PermissionError):
                job._consume('evaluation')
        self.assertEqual(local._used(self.host), 1)

    def test_deadline_wrapper_installed_once_and_respects_smaller_timeout(self):
        job, transport = self.setup_transport()
        with patch.object(local.time, 'monotonic', return_value=job.started + 20):
            adapter = job._consume('evaluation')
            wrapper = adapter.transport
            job._consume('evaluation')
            self.assertIs(adapter.transport, wrapper)
            with adapter.transport(object(), timeout=15):
                pass
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(transport.call_args.kwargs['timeout'], 15.)
        self.assertEqual(local._used(self.host), 2)

    def test_postflight_completion_after_deadline_rejects_both_adapter_receipts(self):
        for kind in ('discovery', 'evaluation'):
            with self.subTest(kind=kind):
                registry = self.ready()
                job = registry['provider'].__self__
                current = [job.started + 10]
                original_call = fixtures.FakeAdapter.__call__
                def late_call(adapter, request):
                    receipt = original_call(adapter, request)
                    # Simulate artifact hashing/parsing after the final HTTP exit.
                    current[0] = job.started + local.MAX_JOB_SECONDS
                    return receipt
                before = local._used(self.host)
                with patch.object(local.time, 'monotonic', side_effect=lambda: current[0]), \
                     patch.object(fixtures.FakeAdapter, '__call__', late_call):
                    with self.assertRaisesRegex(TimeoutError, 'acceptance deadline'):
                        if kind == 'discovery':
                            registry['discovery_execute']('research', {'max_candidates': 1},
                                tenant='agentos-local', agent='qa-release', cost_cap_usd=0.)
                        else:
                            request, expected = self.request(registry)
                            registry['provider'](request)
                self.assertEqual(local._used(self.host), before + 1)
                self.assertIsNone(job.pending_judge)
                self.assertEqual(job.last_error, 'TimeoutError')

    def test_expired_admission_does_not_burn_another_call_or_dispatch(self):
        job, transport = self.setup_transport()
        with patch.object(local.time, 'monotonic', return_value=job.started + 601):
            with self.assertRaises(PermissionError):
                job._consume('evaluation')
        self.assertEqual(local._used(self.host), 0)
        transport.assert_not_called()


if __name__ == '__main__':
    unittest.main()
