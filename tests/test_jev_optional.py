import io
import json
import unittest
from unittest.mock import patch

from nerve_awim.jev_optional import (
    ENDPOINT, JevResearchReviewer, JevUnavailable, numeric_summary
)


METRICS = {
    "completion": .75, "abort": .1, "violations": 0,
    "goal_penalized": 1.0, "prediction_penalized": .8,
}


class FakeHTTPResponse:
    def __init__(self, value):
        self.stream = io.BytesIO(json.dumps(value).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.stream.read(size)


class JevAdapterTests(unittest.TestCase):
    def setUp(self):
        self.sent = []

        def fake_http(request, timeout):
            self.sent.append((request, timeout))
            return FakeHTTPResponse({
                "model": "jev-1.13.0",
                "answers": {"regression_risk": {"type": "noul", "noul": .28}},
                "usage": {"input_tokens": 24, "output_tokens": 7},
            })
        self.fake_http = fake_http

    def test_optional_adapter_correct_official_wire_format(self):
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "mock-test-only"}, clear=True):
            result = JevResearchReviewer(transport=self.fake_http).review(
                baseline=METRICS, candidate=METRICS
            )
        self.assertEqual(result.risk_probability, .28)
        self.assertEqual(result.token_usage["input_tokens"], 24)
        request, timeout = self.sent[0]
        self.assertEqual(request.full_url, ENDPOINT)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer mock-test-only")
        body = json.loads(request.data)
        self.assertEqual(body["model"], "jev-latest")
        self.assertEqual(body["questions"]["regression_risk"]["type"], "noul")
        self.assertEqual(body["state"]["candidate"]["completion"], .75)
        self.assertNotIn("mock-test-only", request.data.decode())
        self.assertGreater(timeout, 0)

    def test_missing_key_fails_without_transport(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(JevUnavailable):
                JevResearchReviewer(transport=self.fake_http).review(
                    baseline=METRICS, candidate=METRICS
                )
        self.assertEqual(self.sent, [])

    def test_untrusted_metrics_never_transmitted(self):
        fields = dict(METRICS, patient_name="never-send")
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "fake"}, clear=True):
            with self.assertRaises(ValueError):
                JevResearchReviewer(transport=self.fake_http).review(
                    baseline=fields, candidate=METRICS
                )
        self.assertEqual(self.sent, [])

    def test_nan_rejected(self):
        fields = dict(METRICS, completion=float("nan"))
        with self.assertRaises(ValueError):
            numeric_summary(fields)

    def test_bad_typed_answer_rejected(self):
        def malformed(request, timeout):
            return FakeHTTPResponse({
                "model": "jev-latest",
                "answers": {"regression_risk": {"type": "noul", "noul": 1.7}},
            })
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "fake"}, clear=True):
            with self.assertRaises(JevUnavailable):
                JevResearchReviewer(transport=malformed).review(
                    baseline=METRICS, candidate=METRICS
                )

    def test_transport_failures_are_sanitized(self):
        def broken(request, timeout):
            raise OSError("api key mock-secret-value")
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "fake"}, clear=True):
            with self.assertRaises(JevUnavailable) as caught:
                JevResearchReviewer(transport=broken).review(
                    baseline=METRICS, candidate=METRICS
                )
        self.assertNotIn("mock-secret-value", str(caught.exception))

    def test_unapproved_model_rejected(self):
        with self.assertRaises(ValueError):
            JevResearchReviewer(model="attacker-model")


if __name__ == "__main__":
    unittest.main()
