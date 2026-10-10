import tempfile,unittest,json
from pathlib import Path
from nerve_awim.autoresearch_v02 import Proposal,ResearchCoordinator,demo
class CoordinatorTests(unittest.TestCase):
    def test_reproducible(self):
        self.assertEqual(demo()["holdout_selected_mae"],demo()["holdout_selected_mae"])
    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):Proposal("x",float("nan"),"bad")
    def test_budget(self):
        with tempfile.TemporaryDirectory() as d:
            c=ResearchCoordinator(Path(d)/"log",max_trials=1)
            with self.assertRaises(ValueError):
                c.run([Proposal("a",.1,"a"),Proposal("b",.2,"b")])
    def test_persistent_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"log.jsonl"
            c=ResearchCoordinator(p)
            c.run([Proposal("a",.1,"test")])
            self.assertEqual(len(p.read_text().splitlines()),1)
            self.assertEqual(json.loads(p.read_text())["experiment"],"worldcore_drift_v02")
    def test_duplicate_id(self):
        with tempfile.TemporaryDirectory() as d:
            c=ResearchCoordinator(Path(d)/"log")
            with self.assertRaises(ValueError):
                c.run([Proposal("a",.1,"a"),Proposal("a",.2,"b")])
if __name__=="__main__":unittest.main()
