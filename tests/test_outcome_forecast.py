import unittest
from nerve_awim.outcome_forecast import forecast_outcomes, summarize_outcomes


def events(values):
    return [dict(id=str(i), observed_at=i, success=v) for i, v in enumerate(values)]


class OutcomeForecastTests(unittest.TestCase):
    def test_learning_drift_and_controls(self):
        before = forecast_outcomes(events([True] * 60))
        after = forecast_outcomes(events([True] * 60 + [False] * 60))
        self.assertGreater(before['next_success_estimate'], .9)
        self.assertLess(after['next_success_estimate'], .1)
        self.assertLess(after['brier']['adaptive'], after['brier']['frozen'])
        self.assertLess(after['brier']['adaptive'], after['brier']['expanding'])

    def test_no_future_outcome_leakage(self):
        first = forecast_outcomes(events([True] * 25 + [False]))
        second = forecast_outcomes(events([True] * 26))
        self.assertEqual(first['predictions'][-1]['adaptive'], second['predictions'][-1]['adaptive'])
        self.assertNotEqual(first['next_success_estimate'], second['next_success_estimate'])

    def test_duplicates_do_not_manufacture_learning(self):
        rows = events([True, False] * 30)
        original = forecast_outcomes(rows)
        repeated = forecast_outcomes(rows + rows)
        for key in ('state_digest', 'observations', 'brier', 'next_success_estimate'):
            self.assertEqual(original[key], repeated[key])
        with self.assertRaises(ValueError):
            forecast_outcomes(rows + [dict(rows[0], success=False)])

    def test_same_time_and_missing(self):
        rows = events([True] * 20)
        rows += [dict(id='a',observed_at=30,success=False),dict(id='b',observed_at=30,success=True)]
        result = forecast_outcomes(rows)
        self.assertEqual(result['predictions'][-1]['adaptive'],result['predictions'][-2]['adaptive'])
        unknown = forecast_outcomes(events([None] * 30))
        self.assertEqual(unknown['observations'], 0)
        self.assertIsNone(unknown['brier']['adaptive'])

    def test_bad_values_and_metadata_view(self):
        for value in (1, 'success', float('nan')):
            with self.assertRaises(ValueError): forecast_outcomes(events([value]))
        with self.assertRaises(ValueError): forecast_outcomes([dict(id='a', observed_at=float('inf'),success=True)])
        self.assertNotIn('predictions', summarize_outcomes(events([True] * 30)))
