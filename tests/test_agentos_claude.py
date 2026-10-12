import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from nerve_awim.agentos_claude import BUDGET, RESERVATION, ClaudeReviewer, MODEL, PilotError


def response(**changes):
    return dict(model=MODEL, usage=dict(input_tokens=100, output_tokens=10),
                stop_reason='end_turn', content=[dict(type='text', text='Review complete.')]) | changes


class ClaudeReviewerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'review.sqlite3'

    def reviewer(self, send=lambda *args: response(), key='test-only-key'):
        return ClaudeReviewer(self.path, key, send=send)

    def test_missing_key_can_report_but_never_reserves_or_calls(self):
        reviewer = self.reviewer(key=None, send=lambda *args: self.fail('must not send'))
        self.assertEqual(reviewer.report()['budget_usd'], 25)
        with self.assertRaises(PilotError):
            reviewer.complete('system', 'prompt')
        self.assertEqual(reviewer.report()['calls'], 0)

    def test_reserves_before_transport_then_settles_and_retains_across_restart(self):
        def send(key, body):
            self.assertEqual(key, 'test-only-key')
            self.assertEqual(set(body), {'model', 'system', 'messages', 'max_tokens', 'service_tier'})
            self.assertEqual(body['service_tier'], 'standard_only')
            self.assertEqual(body['max_tokens'], 1024)
            pending = ClaudeReviewer(self.path).report()
            self.assertEqual(pending['accounted_usd'], 3.01536)
            self.assertEqual(pending['uncertain_calls'], 1)
            return response()
        self.assertEqual(self.reviewer(send).complete('system', 'prompt'), 'Review complete.')
        report = ClaudeReviewer(self.path).report()
        self.assertEqual(report['calls'], 1)
        self.assertEqual(report['accounted_usd'], .00045)
        self.assertEqual(report['confirmed_usage_cost_usd'], .00045)
        self.assertEqual(report['uncertain_calls'], 0)

    def test_provider_errors_are_sanitized_and_failure_is_durable(self):
        def send(*args):
            raise ValueError('secret-api-key and sensitive prompt')
        reviewer = self.reviewer(send)
        with self.assertRaises(PilotError) as error:
            reviewer.complete('system', 'prompt')
        self.assertNotIn('secret', str(error.exception))
        restarted = self.reviewer(lambda *args: self.fail('no retry'))
        with self.assertRaises(PilotError):
            restarted.complete('system', 'prompt')
        report = restarted.report()
        self.assertEqual(report['accounted_usd'], RESERVATION/1e6)
        self.assertEqual(report['confirmed_usage_cost_usd'], 0)
        self.assertEqual(report['uncertain_calls'], 1)
        self.assertEqual(report['calls'], 1)

    def test_pending_crashed_call_blocks_restart_without_refund(self):
        reviewer = self.reviewer()
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO reviewer_calls(reserved,status) VALUES(?,'pending')", (RESERVATION,))
        with self.assertRaises(PilotError):
            self.reviewer(lambda *args: self.fail('no retry')).complete('system', 'prompt')
        self.assertEqual(reviewer.report()['accounted_usd'], RESERVATION/1e6)

    def test_concurrent_calls_cannot_spend_same_reservation(self):
        entered, release = threading.Event(), threading.Event()
        def send(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test timeout')
            return response()
        first, second = self.reviewer(send), self.reviewer(lambda *args: self.fail('parallel send'))
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(first.complete, 'system', 'prompt')
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(PilotError):
                    second.complete('system', 'prompt')
            finally:
                release.set()
            self.assertEqual(pending.result(), 'Review complete.')
        self.assertEqual(first.report()['calls'], 1)

    def test_budget_cap_and_call_limit_survive_restart(self):
        reviewer = self.reviewer(lambda *args: response(usage=dict(input_tokens=1_000_000, output_tokens=1024)))
        for _ in range(8):
            reviewer.complete('system', 'prompt')
        with self.assertRaises(PilotError):
            self.reviewer(lambda *args: self.fail('over budget')).complete('system', 'prompt')
        self.assertEqual(reviewer.report()['accounted_usd'], 8 * RESERVATION/1e6)
        self.assertLessEqual(reviewer.report()['accounted_usd'], 25)

    def test_120_call_cap_even_with_zero_usage(self):
        reviewer = self.reviewer(lambda *args: response(usage=dict(input_tokens=0, output_tokens=0)))
        for _ in range(120):
            reviewer.complete('system', 'prompt')
        with self.assertRaises(PilotError):
            self.reviewer(lambda *args: self.fail('call limit')).complete('system', 'prompt')
        self.assertEqual(reviewer.report()['calls'], 120)

    def test_unexpected_billing_and_incomplete_output_remain_uncertain(self):
        invalid = [
            response(model='different-model'),
            response(usage=dict(input_tokens=True, output_tokens=1)),
            response(usage=dict(input_tokens=1_000_001, output_tokens=1)),
            response(usage=dict(input_tokens=1, output_tokens=1025)),
            response(usage=dict(input_tokens=1, output_tokens=1, cache_creation_input_tokens=1)),
            response(usage=dict(input_tokens=1, output_tokens=1, server_tool_use=dict(web_search_requests=1))),
            response(usage=dict(input_tokens=1, output_tokens=1, new_billable_feature=5)),
            response(usage=dict(input_tokens=1, output_tokens=1, service_tier='priority')),
            response(stop_reason='max_tokens'),
            response(content=[dict(type='tool_use', text='not text')]),
        ]
        for index, item in enumerate(invalid):
            with self.subTest(index=index):
                reviewer = ClaudeReviewer(Path(self.tmp.name)/('invalid-'+str(index)), 'test', send=lambda *a: item)
                with self.assertRaises(PilotError):
                    reviewer.complete('system', 'prompt')
                self.assertEqual(reviewer.report()['accounted_usd'], RESERVATION/1e6)
                self.assertEqual(reviewer.report()['uncertain_calls'], 1)

    def test_request_bound_checked_before_reservation(self):
        reviewer = self.reviewer(lambda *args: self.fail('oversize send'))
        with self.assertRaises(PilotError):
            reviewer.complete('system', 'x'*24001)
        self.assertEqual(reviewer.report()['calls'], 0)
