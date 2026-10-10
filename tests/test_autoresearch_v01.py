import json,tempfile,unittest
from pathlib import Path
from nerve_awim.autoresearch_v01 import Candidate,evaluate,research,write_ledger,TRAIN_SEEDS
class AutoResearchTests(unittest.TestCase):
    def test_reproducible(self):
        a=Candidate("a",.1)
        self.assertEqual(evaluate(a,TRAIN_SEEDS),evaluate(a,TRAIN_SEEDS))
    def test_bad_candidate(self):
        with self.assertRaises(ValueError):Candidate("unsafe",1)
    def test_keep_reject_decisions(self):
        report=research([Candidate("slow",.01),Candidate("fast",.2)])
        self.assertEqual(len(report["experiments"]),2)
        self.assertIn(report["selected"]["name"],("baseline","slow","fast"))
    def test_holdout_not_used_for_ranking(self):
        report=research([Candidate("a",.05)])
        self.assertIn("holdout",report)
        self.assertNotIn("holdout_mae",report["experiments"][0])
    def test_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"results.jsonl"
            write_ledger(research([Candidate("a",.1)]),p)
            self.assertEqual(len(p.read_text().splitlines()),1)
            self.assertIn("selected",json.loads(p.read_text()))
if __name__=="__main__":unittest.main()
