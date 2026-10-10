import threading
import unittest
from nerve_awim.parallel_agents_v11 import (
    AgentJob, BoundedParallelAgents,
)


class ParallelAgentsTests(unittest.TestCase):
    def test_deterministic_merge_order(self):
        pool = BoundedParallelAgents({"evaluation": lambda x: x * 2}, max_workers=3)
        results = pool.run([
            AgentJob("third", "evaluation", 3),
            AgentJob("first", "evaluation", 1),
            AgentJob("second", "evaluation", 2),
        ])
        self.assertEqual([r.job_id for r in results], ["third", "first", "second"])
        self.assertEqual([r.output for r in results], [6, 2, 4])

    def test_workers_actually_overlap(self):
        rendezvous = threading.Barrier(2, timeout=5)
        def worker(payload):
            rendezvous.wait()
            return payload
        pool = BoundedParallelAgents({"test": worker}, max_workers=2)
        outcomes = pool.run([AgentJob("a", "test", 1), AgentJob("b", "test", 2)])
        self.assertEqual([x.output for x in outcomes], [1, 2])

    def test_errors_fail_closed(self):
        def failing(value):
            if value == "bad":
                raise ValueError("invalid result")
            return "ok"
        pool = BoundedParallelAgents({"evaluation": failing})
        with self.assertRaisesRegex(RuntimeError, "batch rejected"):
            pool.run([AgentJob("a", "evaluation", "good"),
                      AgentJob("b", "evaluation", "bad")])

    def test_unknown_role_rejected(self):
        pool = BoundedParallelAgents({"memory": lambda x: x})
        with self.assertRaises(ValueError):
            pool.run([AgentJob("one", "untrusted", "payload")])

    def test_duplicate_jobs_rejected(self):
        pool = BoundedParallelAgents({"memory": lambda x: x})
        with self.assertRaises(ValueError):
            pool.run([AgentJob("a", "memory", 1), AgentJob("a", "memory", 2)])

    def test_budget_enforced(self):
        pool = BoundedParallelAgents({"memory": lambda x: x}, max_jobs=1)
        with self.assertRaises(ValueError):
            pool.run([AgentJob("a", "memory", 1), AgentJob("b", "memory", 2)])

    def test_none_output_is_failure(self):
        pool = BoundedParallelAgents({"memory": lambda x: None})
        with self.assertRaises(RuntimeError):
            pool.run([AgentJob("a", "memory", 1)])


if __name__ == "__main__":
    unittest.main()
