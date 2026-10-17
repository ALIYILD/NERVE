import tempfile
import unittest
import json
from datetime import datetime, timezone
from unittest.mock import patch
from pathlib import Path
from overnight_supervision_accounting import count_attempts, pod_failure_state


class AccountingTests(unittest.TestCase):
    def test_conductor_retires_only_failed_pod_without_mutating_other_lock(self):
        import overnight_conductor as conductor
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime(2026, 10, 17, 0, 0, tzinfo=timezone.utc)
            def save(name, value):
                (root / name).write_text(json.dumps(value))
            save('integrity-baseline.json', {'paths': {}})
            save('pods.json', {'observed_at': now.isoformat(), 'pods': [
                {'id': pod, 'status': 'RUNNING', 'hourly_usd': .59} for pod in ('A', 'B')]})
            save('spend.json', {'model_calls': 15, 'intervals': []})
            save('pod-A.lock', {'pod_id': 'A'})
            save('pod-B.lock', {'pod_id': 'B'})
            rows = [dict(event='end', loop='study', pod_id='A', time=str(i), verdict='incomplete_infrastructure') for i in range(2)]
            (root / 'ledger.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with patch.object(conductor, 'count_attempts', return_value=12):
                result = conductor.inspect(root, root, now=now)
            self.assertEqual(result['actions'], [{'id': 'A', 'action': 'stop'}])
            self.assertEqual(result['model_calls'], 15)
            self.assertFalse((root / 'pod-A.lock').exists())
            self.assertTrue((root / 'pod-B.lock').exists())
            self.assertFalse(result['shutdown_verified'])

    def test_all_families_and_registered_roots_with_alias_deduplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for family in ('A01', 'B01', 'L4', 'L5'):
                path = root / ('overnight-20261017-' + family)
                path.mkdir()
                (path / 'claim-000-0.json').write_text('{}')
                (path / 'claim-000-1.json').write_text('{}')
            extra = root / 'separate-study'
            extra.mkdir()
            (extra / 'claim-001-0.json').write_text('{}')
            self.assertEqual(count_attempts(root, [extra, extra.resolve()]), 9)
            with self.assertRaises(ValueError):
                count_attempts(root, [root / 'missing'])

    def test_other_pods_do_not_reset_and_retirement_is_sticky(self):
        def event(pod, verdict, time):
            return dict(event='end', pod_id=pod, verdict=verdict, time=time, loop='test')
        first = event('A', 'incomplete_infrastructure', '1')
        events = [first, first, event('B', 'passed', '2')]
        self.assertEqual(pod_failure_state(events)['retired_pods'], [])
        events += [event('A', 'incomplete_infrastructure', '3'), event('A', 'passed', '4')]
        self.assertEqual(pod_failure_state(events)['retired_pods'], ['A'])

    def test_cpu_failure_is_not_a_pod_failure_and_success_resets(self):
        events = [dict(event='end', pod_id='A', verdict='incomplete_infrastructure', time='1', pod_failure=False),
                  dict(event='end', pod_id='A', verdict='incomplete_infrastructure', time='2'),
                  dict(event='end', pod_id='A', verdict='kept', time='3'),
                  dict(event='end', pod_id='A', verdict='incomplete_infrastructure', time='4')]
        self.assertEqual(pod_failure_state(events), {'consecutive_failures': {'A': 1}, 'retired_pods': []})


if __name__ == '__main__':
    unittest.main()
