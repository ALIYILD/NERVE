import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nerve_awim.autoresearch_v04 import Proposal
from nerve_awim.evolution_v01 import EvolutionMemory
from nerve_awim.evolution_cycle_v11 import ParallelEvolutionCycle
from nerve_awim.jev_batch import JevBatchReviewer
from nerve_awim.jev_optional import JevUnavailable

METRICS = {
    "completion": .5, "abort": 1, "violations": 0,
    "goal_penalized": 1.0, "prediction_penalized": .9,
}


class Response:
    def __init__(self, value):
        self.data = io.BytesIO(json.dumps(value).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, n):
        return self.data.read(n)


class JevBatchTests(unittest.TestCase):
    def test_one_api_request_for_two_agents(self):
        calls = []

        def transport(request, timeout):
            calls.append(json.loads(request.data))
            return Response({
                "model": "jev-1.13.0",
                "answers": {
                    "q0": {"type": "noul", "noul": .02},
                    "q1": {"type": "noul", "noul": .82},
                },
                "usage": {"input_tokens": 20, "output_tokens": 6},
            })

        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "fake-key"}, clear=True):
            result = JevBatchReviewer(transport=transport).review_many(
                baseline=METRICS,
                candidates={"long": METRICS, "short": METRICS},
            )
        self.assertEqual(len(calls), 1)
        self.assertEqual(set(calls[0]["questions"]), {"q0", "q1"})
        self.assertEqual(result["long"].risk_probability, .02)
        self.assertEqual(result["short"].risk_probability, .82)
        self.assertNotIn("long", json.dumps(calls[0]))
        self.assertNotIn("fake-key", json.dumps(calls[0]))

    def test_missing_batch_answer_rejected(self):
        def transport(request, timeout):
            return Response({
                "model": "jev-1.13.0",
                "answers": {"q0": {"type": "noul", "noul": .2}},
            })
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "fake"}, clear=True):
            with self.assertRaises(JevUnavailable):
                JevBatchReviewer(transport=transport).review_many(
                    baseline=METRICS,
                    candidates={"one": METRICS, "two": METRICS},
                )

    def test_no_key_no_request(self):
        def no_network(request, timeout):
            raise AssertionError("unexpected network request")
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(JevUnavailable):
                JevBatchReviewer(transport=no_network).review_many(
                    baseline=METRICS, candidates={"one": METRICS},
                )

    def test_cycle_uses_batch_and_still_rejects(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = EvolutionMemory(Path(folder) / "memory.sqlite")
            calls = []
            def transport(request, timeout):
                request_body = json.loads(request.data)
                calls.append(request_body)
                return Response({
                    "model": "jev-1.13.0",
                    "answers": {
                        q: {"type": "noul", "noul": 0.0}
                        for q in request_body["questions"]
                    },
                })
            reviewer = JevBatchReviewer(transport=transport)
            with patch.dict("os.environ", {"TYPESAFE_API_KEY": "fake"}, clear=True):
                outcome = ParallelEvolutionCycle(
                    memory=memory, agent_id="researcher",
                    jev_reviewer=reviewer,
                ).run(
                    [Proposal("long", 8, .25), Proposal("short", 3, .25)],
                    context="WorldCore",
                )
            self.assertEqual(len(calls), 1)
            self.assertEqual(outcome["status"], "rejected")
            self.assertEqual(outcome["selected"], None)
            self.assertTrue(all(row["jev_advice"]["regression_risk"] == 0.0
                                for row in outcome["trials"]))


if __name__ == "__main__":
    unittest.main()
