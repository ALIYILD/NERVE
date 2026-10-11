import sqlite3
import tempfile
from pathlib import Path
import unittest
from nerve_awim.claude_pilot import ClaudePilot, PilotError, RESERVATION, error_category
from scripts.claude_learning_pilot import dataset, run


class ClaudePilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name)/'budget.sqlite')

    def response(self, key, body):
        self.assertEqual(body['model'], 'claude-sonnet-4-6')
        self.assertEqual(body['max_tokens'], 1024)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute("SELECT reserved FROM calls WHERE status='pending'").fetchone()[0], RESERVATION)
        return {'usage': {'input_tokens': 100, 'output_tokens': 10},
                'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': 'ok'}]}

    def test_reserve_before_send_and_settle_confirmed_usage(self):
        client = ClaudePilot(self.path, 'fake-test-key', send=self.response)
        self.assertEqual(client.complete('system', 'input'), 'ok')
        self.assertEqual(client.report()['accounted_usd'], .00045)
        self.assertEqual(client.report()['uncertain_calls'], 0)

    def test_uncertain_request_retains_reservation_and_stops(self):
        def fail(*args):
            raise TimeoutError('sensitive provider error')
        client = ClaudePilot(self.path, 'fake-test-key', send=fail)
        with self.assertRaises(PilotError) as error:
            client.complete('s', 'p')
        self.assertNotIn('sensitive', str(error.exception))
        self.assertEqual(client.report()['accounted_usd'], RESERVATION/1e6)
        with self.assertRaises(PilotError):
            client.complete('s', 'p')
        self.assertEqual(client.report()['calls'], 1)

    def test_budget_rejects_before_send(self):
        client = ClaudePilot(self.path, 'fake', send=lambda *args: self.fail('overspend'))
        with sqlite3.connect(self.path) as con:
            con.execute("INSERT INTO calls(reserved,status) VALUES(8000000,'pending')")
        with self.assertRaises(PilotError):
            client.complete('s', 'p')

    def test_ledger_cannot_be_reset(self):
        ClaudePilot(self.path, 'fake')
        with self.assertRaises(FileExistsError):
            ClaudePilot(self.path, 'fake')

    def test_unexpected_usage_retains_reservation(self):
        client = ClaudePilot(self.path, 'fake', send=lambda *args: {'usage': {'input_tokens': -1, 'output_tokens': 3}})
        with self.assertRaises(PilotError):
            client.complete('s', 'p')
        self.assertEqual(client.report()['uncertain_calls'], 1)

    def test_missing_key_never_creates_ledger(self):
        with self.assertRaises(PilotError):
            ClaudePilot(self.path, '')
        self.assertFalse(Path(self.path).exists())

    def test_pilot_dry_run_with_capable_parser(self):
        import ast
        import json
        class Local:
            def complete(self, system, prompt):
                if system.startswith('Propose'):
                    return json.dumps({'lesson': 'Inspect only the direct module body.'})
                source = json.loads(prompt)['source']
                return json.dumps([n.name for n in ast.parse(source).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))])
        report = run(Local(), 'test-seed')
        self.assertEqual(report['status'], 'no_verified_improvement')
        self.assertEqual(report['proposal_calls'], 10)
        self.assertEqual(report['prediction_calls'], 10)

    def test_dataset_independent_splits_and_seed(self):
        a = sum(dataset('a'), [])
        b = sum(dataset('b'), [])
        self.assertEqual(len({e.task['source'] for e in a + b}), 26)

    def test_carried_reservation_counts_towards_same_ten_dollars(self):
        client = ClaudePilot(self.path, 'fake', prior_reserved=8_000_000,
                             send=lambda *args: self.fail('overspend'))
        with self.assertRaises(PilotError):
            client.complete('s', 'p')
        self.assertEqual(client.report()['accounted_usd'], 8)

    def test_error_category_never_echoes_provider_text(self):
        self.assertEqual(error_category('{"error":{"message":"Your credit balance is too low SECRET"}}'),
                         'insufficient_api_credit')
        self.assertEqual(error_category('SECRET'), 'unclassified')
