import unittest
from nerve_awim.agents_v30 import Task,Agent,Coordinator,ProvenanceMemory
class AgentsV30Tests(unittest.TestCase):
    def test_capability_routing(self):
        c=Coordinator([Agent("a","vision",2),Agent("b","eeg",3)])
        r=c.dispatch(Task("1","eeg",2,"synthetic"))
        self.assertEqual((r.agent_id,r.value),("b",6))
    def test_missing_capability(self):
        with self.assertRaises(LookupError):
            Coordinator([Agent("a","vision",1)]).dispatch(Task("1","eeg",2,"sensor"))
    def test_provenance(self):
        m=ProvenanceMemory()
        c=Coordinator([Agent("a","eeg",1)],m)
        c.dispatch(Task("1","eeg",2,"device-1"))
        self.assertEqual(c.memory.retrieve("1").source,"device-1")
    def test_duplicate_output_rejected(self):
        c=Coordinator([Agent("a","eeg",1)])
        task=Task("1","eeg",1,"synthetic")
        c.dispatch(task)
        with self.assertRaises(ValueError):c.dispatch(task)
    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):Task("1","eeg",float("nan"),"sensor")
    def test_no_duplicate_agents(self):
        with self.assertRaises(ValueError):Coordinator([Agent("a","eeg",1),Agent("a","vision",1)])
if __name__=="__main__":unittest.main()
