"""Host diagnostics remain bounded and never expose provider messages."""
import io
import json
import socket
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from nerve_awim.memory_gateway.inference import InferenceUnavailable, LocalInferenceAdapter


class InferenceDiagnosticsTests(unittest.TestCase):
    def adapter(self, **kwargs):
        return LocalInferenceAdapter(base_url='http://127.0.0.1:9001', model='fixture', **kwargs)

    def assert_failure(self, adapter, reason):
        with self.assertRaises(InferenceUnavailable) as caught:
            adapter._model_response('synthetic', 'synthetic evidence')
        error = caught.exception
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(error.reason, reason)
        self.assertEqual(str(error), 'inference_unavailable')
        self.assertEqual(error.args, ('inference_unavailable',))
        self.assertNotIn('SECRET', repr(error))
        self.assertTrue(error.__suppress_context__ or reason in ('capacity', 'circuit_open'))
        return error

    def test_transport_classification_never_copies_messages(self):
        cases = [(socket.timeout('SECRET'), 'timeout'),
                 (URLError(socket.timeout('SECRET')), 'timeout'),
                 (URLError('SECRET timeout'), 'transport'),
                 (HTTPError('http://SECRET', 504, 'SECRET', {}, None), 'transport'),
                 (OSError('SECRET'), 'transport'),
                 (RuntimeError('SECRET'), 'transport')]
        for failure, reason in cases:
            with self.subTest(kind=type(failure).__name__, reason=reason):
                adapter = self.adapter()
                with patch.object(adapter._opener, 'open', side_effect=failure):
                    self.assert_failure(adapter, reason)
                self.assertEqual(adapter._failures, 1)
                self.assertTrue(adapter._slots.acquire(blocking=False))
                adapter._slots.release()

    def test_invalid_json_shape_and_budget_are_invalid_response(self):
        valid = {'model': 'fixture', 'choices': [{'finish_reason': 'stop',
                 'message': {'role': 'assistant', 'content': 'synthetic'}}]}
        cases = [b'SECRET', b'\xff', b'[]', b'x' * 65537,
                 json.dumps({**valid, 'model': 'SECRET'}).encode(),
                 json.dumps({**valid, 'usage': {'completion_tokens': 257}}).encode()]
        for raw in cases:
            with self.subTest(size=len(raw)):
                adapter = self.adapter()
                with patch.object(adapter._opener, 'open', return_value=io.BytesIO(raw)):
                    self.assert_failure(adapter, 'invalid_response')

    def test_circuit_open_then_recovery_preserves_cooldown(self):
        adapter = self.adapter()
        with patch('nerve_awim.memory_gateway.inference.time.monotonic', return_value=100), \
                patch.object(adapter._opener, 'open', side_effect=socket.timeout('SECRET')) as call:
            for _ in range(3):
                self.assert_failure(adapter, 'timeout')
            self.assert_failure(adapter, 'circuit_open')
            self.assertEqual(call.call_count, 3)
        with patch('nerve_awim.memory_gateway.inference.time.monotonic', return_value=130), \
                patch.object(adapter._opener, 'open', side_effect=URLError('SECRET')) as call:
            self.assert_failure(adapter, 'transport')
            call.assert_called_once()
            self.assertEqual(adapter._failures, 1)

    def test_capacity_does_not_open_circuit_or_call_provider(self):
        adapter = self.adapter()
        for _ in range(4):
            self.assertTrue(adapter._slots.acquire(blocking=False))
        try:
            with patch.object(adapter._opener, 'open') as call:
                self.assert_failure(adapter, 'capacity')
                call.assert_not_called()
            self.assertEqual(adapter._failures, 0)
            self.assertIsNone(adapter._opened_at)
        finally:
            for _ in range(4):
                adapter._slots.release()

    def test_default_and_maximum_deadlines_unchanged(self):
        for fields, expected in (({}, 10.0), ({'timeout_seconds': 30}, 30.0)):
            adapter = self.adapter(**fields)
            with patch.object(adapter._opener, 'open', side_effect=socket.timeout()) as call:
                self.assert_failure(adapter, 'timeout')
                self.assertEqual(call.call_args.kwargs['timeout'], expected)
        for invalid in (0, 31, float('nan'), True):
            with self.assertRaises(ValueError):
                self.adapter(timeout_seconds=invalid)

    def test_arbitrary_failure_reason_is_rejected_without_echo(self):
        with self.assertRaisesRegex(ValueError, '^invalid inference failure reason$'):
            InferenceUnavailable('SECRET')

    def test_static_validation_details_never_echo_provider_data(self):
        valid = {'model': 'fixture', 'choices': [{'finish_reason': 'stop',
                 'message': {'role': 'assistant', 'content': 'synthetic'}}]}
        choice = valid['choices'][0]
        def response(**changes):
            return json.dumps({**valid, **changes}).encode()
        def changed_choice(**changes):
            return response(choices=[{**choice, **changes}])
        def changed_message(**changes):
            return changed_choice(message={**choice['message'], **changes})
        cases = [(b'x' * 65537, 'response_size'), (b'SECRET', 'completion_shape'),
                 (b'\xff', 'completion_shape'), (b'[]', 'completion_shape'),
                 (response(choices=['SECRET']), 'completion_shape'),
                 (response(model='SECRET'), 'model_mismatch'),
                 (changed_choice(finish_reason='length'), 'output_limit'),
                 (changed_choice(finish_reason='SECRET'), 'finish_reason'),
                 (changed_choice(message='SECRET'), 'message_shape'),
                 (changed_message(role='SECRET'), 'message_shape'),
                 (changed_message(function_call={'name': 'SECRET'}), 'tool_call'),
                 (changed_message(tool_calls=['SECRET']), 'tool_call'),
                 (changed_message(content=['SECRET']), 'content'),
                 (changed_message(content=''), 'content'),
                 (response(usage='SECRET'), 'usage'),
                 (response(usage={'prompt_tokens': 'SECRET'}), 'usage'),
                 (response(usage={'completion_tokens': 257}), 'output_limit')]
        for raw, detail in cases:
            with self.subTest(detail=detail):
                adapter = self.adapter()
                with patch.object(adapter._opener, 'open', return_value=io.BytesIO(raw)):
                    error = self.assert_failure(adapter, 'invalid_response')
                self.assertEqual(error.detail, detail)
                self.assertNotIn('SECRET', repr(vars(error)))

    def test_detail_allowlist_and_reason_binding(self):
        for reason, detail in (('invalid_response', 'SECRET'), ('timeout', 'output_limit'),
                               ('invalid_response', [])):
            with self.subTest(reason=reason), self.assertRaisesRegex(
                    ValueError, '^invalid inference failure detail$'):
                InferenceUnavailable(reason, detail)
        self.assertIsNone(InferenceUnavailable('timeout').detail)


if __name__ == '__main__':
    unittest.main()
