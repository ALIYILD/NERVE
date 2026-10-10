import tempfile
import unittest
from pathlib import Path
from nerve_awim.autoresearch_v04 import Proposal
from nerve_awim.evolution_v01 import EvolutionMemory
from nerve_awim.evolution_cycle_v11 import ParallelEvolutionCycle


class ParallelEvolutionCycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.memory = EvolutionMemory(Path(self.tmp.name) / "memory.db")
        self.path = Path(self.tmp.name) / "report.jsonl"
        self.loop = ParallelEvolutionCycle(
            memory=self.memory, agent_id="researcher",
            max_workers=4, ledger_path=self.path)

    def proposals(self):
        return (Proposal("short", 3, .25), Proposal("long", 8, .25))

    def test_reliable_rejection(self):
        report = self.loop.run(self.proposals(), context="WorldCore")
        self.assertEqual(report["status"], "rejected")
        self.assertIsNone(report["selected"])
        self.assertIsNone(report["holdout_report_only"])
        self.assertTrue(all(not row["absolute_eligibility"]
                            for row in report["trials"]))
        self.assertEqual(len(self.path.read_text().splitlines()), 1)

    def test_evaluated_memory_prioritises_only(self):
        self.memory.record("researcher", "WorldCore", "long", .99)
        self.memory.record("researcher", "WorldCore", "short", .2)
        report = self.loop.run(self.proposals(), context="WorldCore")
        self.assertEqual(report["trials"][0]["candidate"]["name"], "long")
        self.assertEqual(report["memory_advice_count"], 2)
        self.assertIsNone(report["selected"])

    def test_unrated_memory_ignored(self):
        self.memory.record("researcher", "WorldCore", "long")
        report = self.loop.run(self.proposals(), context="WorldCore")
        self.assertEqual(report["memory_advice_count"], 0)

    def test_other_agent_memory_isolated(self):
        self.memory.record("other", "WorldCore", "long", 1)
        report = self.loop.run(self.proposals(), context="WorldCore")
        self.assertEqual(report["memory_advice_count"], 0)

    def test_duplicate_candidates_fail_before_ledger(self):
        with self.assertRaises(RuntimeError):
            self.loop.run([Proposal("same", 3, .25),
                           Proposal("same", 8, .25)], context="WorldCore")
        self.assertFalse(self.path.exists())

    def test_worker_single_mode_same_rejection(self):
        parallel = self.loop.run(self.proposals(), context="WorldCore")
        serial = ParallelEvolutionCycle(
            memory=self.memory, agent_id="researcher", max_workers=1
        ).run(self.proposals(), context="WorldCore")
        self.assertEqual(parallel["status"], serial["status"])
        self.assertEqual(parallel["baseline_validation"],
                         serial["baseline_validation"])

    def test_validation_cannot_change_by_memory(self):
        baseline = self.loop.run(self.proposals(), context="WorldCore")
        self.memory.record("researcher", "WorldCore", "short", 1)
        changed = self.loop.run(self.proposals(), context="WorldCore")
        scores = lambda report: {
            x["candidate"]["name"]: x["validation"] for x in report["trials"]
        }
        self.assertEqual(scores(baseline), scores(changed))


if __name__ == "__main__":
    unittest.main()
