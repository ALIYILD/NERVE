import unittest
from nerve_awim.agents_v30 import Agent
from nerve_awim.collaboration_v31 import PredictiveCoordinator,EqualCapabilityBaseline,ContextMemory
from benchmarks.v31_benchmark import episode,benchmark
class CollaborationTests(unittest.TestCase):
    def agents(self):return [Agent("a","clear",.25),Agent("b","rough",.5)]
    def test_baseline_and_adaptive_same_first_prediction(self):
        agents=self.agents()
        a=PredictiveCoordinator(agents).predict("1","clear",0,1,"sensor")
        b=EqualCapabilityBaseline(agents).predict("1","clear",0,1,"sensor")
        self.assertEqual(a.next_state,b.next_state)
    def test_memory_only_after_feedback(self):
        c=PredictiveCoordinator(self.agents())
        self.assertFalse(c.predict("1","clear",0,1,"sensor").memory_used)
        c.observe("clear",0,1,.4,"sensor")
        self.assertTrue(c.predict("2","clear",0,1,"sensor").memory_used)
    def test_provenance(self):
        m=ContextMemory();m.remember("clear",.4,"device")
        self.assertEqual(m.retrieve("clear")[1],("device",))
    def test_zero_action_not_learnable(self):
        c=PredictiveCoordinator(self.agents());c.observe("clear",0,0,1,"sensor")
        self.assertIsNone(c.memory.retrieve("clear"))
    def test_repeatable(self):
        self.assertEqual(episode(5),episode(5))
    def test_equal_task_budget(self):
        self.assertEqual(benchmark(range(2))["results"]["tasks"],80)
if __name__=="__main__":unittest.main()
