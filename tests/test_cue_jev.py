import json
import os
import unittest
from unittest.mock import patch

from nerve_awim.cue_cli import demo
from nerve_awim.cue_evaluation import EvaluationReport
from nerve_awim.cue_jev import CueJevReviewer
from nerve_awim.jev_optional import JevUnavailable


class Response:
    def __init__(self, value): self.value = value
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size): return json.dumps(self.value).encode()[:size]


class CueJevTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = demo()
        cls.report = EvaluationReport.from_dict(cls.result['evaluation']['report'])

    def test_offline_commissioning_cannot_approve_and_exports_pending_memory(self):
        self.assertEqual(self.result['provider_calls'], 0)
        self.assertFalse(self.result['evaluation']['decision']['eligible'])
        self.assertEqual(self.result['memory_status'], 'pending')
        self.assertFalse(self.result['selection']['selected'])

    def test_existing_transport_receives_only_numeric_aggregate_review(self):
        requests = []
        def transport(request, timeout):
            requests.append(json.loads(request.data))
            return Response({'model': 'jev-1.13.0', 'answers': {'regression_risk': {'type': 'noul', 'noul': .2}},
                             'usage': {'input_tokens': 10, 'output_tokens': 1}})
        reviewer = CueJevReviewer(transport=transport)
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only-key'}):
            advice = reviewer.review_cues(self.report, enabled=True)
        self.assertFalse(advice.confidence_available)
        self.assertEqual(advice.risk_probability, .2)
        self.assertNotIn(self.report.candidate_id, json.dumps(requests))
        self.assertEqual(set(requests[0]['state']), {'baseline', 'candidate', 'pairs', 'synthetic'})

    def test_opt_in_and_invalid_provider_response_fail_closed(self):
        reviewer = CueJevReviewer(transport=lambda *a, **k: Response({'answers': {}}))
        with self.assertRaises(PermissionError): reviewer.review_cues(self.report)
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only-key'}):
            with self.assertRaises(JevUnavailable): reviewer.review_cues(self.report, enabled=True)


if __name__ == '__main__': unittest.main()
