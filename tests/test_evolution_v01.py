import tempfile
import unittest
from pathlib import Path
from nerve_awim.evolution_v01 import EvolutionMemory

class EvolutionMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.memory=EvolutionMemory(Path(self.tmp.name)/"experiences.db")
    def test_reinforcement_changes_selection(self):
        low=self.memory.record("agent","planning","approach A",.2)
        high=self.memory.record("agent","planning","approach B",.9)
        self.assertEqual(self.memory.select("agent","planning")[0].experience_id,high)
        self.memory.reward("agent",low,1.0)
        self.assertEqual(self.memory.select("agent","planning")[0].experience_id,low)
    def test_unrated_excluded(self):
        self.memory.record("agent","planning","unrated")
        self.assertEqual(self.memory.select("agent","planning"),[])
    def test_agent_isolation(self):
        self.memory.record("agent-a","planning","private",1)
        self.assertEqual(self.memory.select("agent-b","planning"),[])
    def test_context_isolation(self):
        self.memory.record("agent","vision","vision strategy",1)
        self.assertEqual(self.memory.select("agent","EEG"),[])
    def test_invalid_reward(self):
        identifier=self.memory.record("agent","planning","strategy")
        with self.assertRaises(ValueError):
            self.memory.reward("agent",identifier,float("nan"))
    def test_utility_threshold(self):
        self.memory.record("agent","planning","weak",.3)
        self.memory.record("agent","planning","strong",.9)
        self.assertEqual(len(self.memory.select("agent","planning",minimum_utility=.8)),1)

if __name__=="__main__":
    unittest.main()
