import tempfile
import unittest
from pathlib import Path

from nerve_awim.autoresearch_v04 import Proposal
from nerve_awim.evolution_v01 import EvolutionMemory
from nerve_awim.evolution_cycle_v11 import ParallelEvolutionCycle
from nerve_awim.jev_optional import JevAdvice


class FakeJev:
    def __init__(self, risk):
        self.risk = risk
        self.calls = 0

    def review(self, *, baseline, candidate):
        self.calls += 1
        self.last_payload = (baseline, candidate)
        return JevAdvice(self.risk, False, "jev-mock", .01, {})


class FailingJev:
    def review(self, *, baseline, candidate):
        raise RuntimeError("mock unavailable")


class JevCycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.memory = EvolutionMemory(Path(self.tmp.name) / "memory.sqlite")
        self.proposals = [
            Proposal("long", 8, .25),
            Proposal("short", 3, .25),
        ]

    def test_jev_advisory_cannot_override_rejection(self):
        fake = FakeJev(0.0)  # Jev says no risk, hard safety still rejects.
        report = ParallelEvolutionCycle(
            memory=self.memory, agent_id="researcher",
            jev_reviewer=fake, max_workers=3,
        ).run(self.proposals, context="WorldCore")
        self.assertTrue(report["optional_jev_review_enabled"])
        self.assertEqual(report["status"], "rejected")
        self.assertIsNone(report["selected"])
        self.assertEqual(fake.calls, 2)
        self.assertTrue(all(row["decision"] == "reject"
                            and row["jev_advice"]["regression_risk"] == 0.0
                            for row in report["trials"]))
        self.assertEqual(set(fake.last_payload[0]),
                         {"completion","abort","violations",
                          "goal_penalized","prediction_penalized"})

    def test_jev_failure_rejects_whole_batch(self):
        cycle = ParallelEvolutionCycle(
            memory=self.memory, agent_id="researcher",
            jev_reviewer=FailingJev(),
        )
        with self.assertRaises(RuntimeError):
            cycle.run(self.proposals, context="WorldCore")

    def test_disabled_mode_requires_no_api_key(self):
        report = ParallelEvolutionCycle(
            memory=self.memory, agent_id="researcher"
        ).run(self.proposals, context="WorldCore")
        self.assertFalse(report["optional_jev_review_enabled"])
        self.assertTrue(all(t["jev_advice"] is None
                            for t in report["trials"]))


if __name__ == "__main__":
    unittest.main()
