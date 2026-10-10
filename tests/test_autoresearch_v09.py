import unittest
from nerve_awim.autoresearch_v09 import experiment
class RecoverySearchTests(unittest.TestCase):
    def test_report(self):
        r=experiment()
        self.assertEqual(len(r["candidates"]),5)
    def test_no_unqualified_selection(self):
        r=experiment()
        if r["eligible_candidate"] is not None:
            item=next(x for x in r["candidates"] if x["max_missing"]==r["eligible_candidate"])
            self.assertTrue(item["meets_completion_95pct"])
            self.assertTrue(item["no_abort"])
    def test_deterministic(self):
        self.assertEqual(experiment(),experiment())
if __name__=="__main__":unittest.main()
