import tempfile,unittest
from pathlib import Path
from nerve_awim.autoresearch_v04 import Proposal,episode,evaluate,experiment
class AutoResearchV04Tests(unittest.TestCase):
    def test_repeatable(self):
        a=Proposal("a",5,.25)
        self.assertEqual(episode(3,a),episode(3,a))
    def test_invalid_outage(self):
        with self.assertRaises(ValueError):Proposal("bad",0,.25)
    def test_invalid_risk(self):
        with self.assertRaises(ValueError):Proposal("bad",5,float("nan"))
    def test_bounded_trials(self):
        with self.assertRaises(ValueError):
            experiment([Proposal(str(i),5,.25) for i in range(9)])
    def test_abort_penalty(self):
        r=episode(3,Proposal("short",3,.25))
        self.assertGreaterEqual(r["goal_penalized"],0)
        self.assertLessEqual(r["completion"],1)
    def test_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"runs.jsonl"
            experiment([Proposal("candidate",8,.25)],p)
            self.assertEqual(len(p.read_text().splitlines()),1)
if __name__=="__main__":unittest.main()
