import tempfile,unittest
from pathlib import Path
from nerve_awim.learn_v31 import LearningStore
class LearnTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=LearningStore(Path(self.tmp.name)/"memory.db")
    def test_record_and_recall(self):
        eid=self.store.record("agent-a","summarise paper","successful")
        self.assertEqual(self.store.recall("agent-a","paper")[0].experience_id,eid)
    def test_namespace_isolation(self):
        eid=self.store.record("agent-a","summarise paper","ok")
        self.assertEqual(self.store.recall("agent-b","paper"),[])
        with self.assertRaises(LookupError):self.store.feedback("agent-b",eid,1)
    def test_rating_and_suggestion(self):
        eid=self.store.record("agent-a","task one","use retrieval")
        self.assertEqual(self.store.suggest("agent-a","task"),[])
        self.store.feedback("agent-a",eid,.95)
        self.assertEqual(len(self.store.suggest("agent-a","task")),1)
    def test_invalid_score(self):
        eid=self.store.record("agent-a","task","result")
        with self.assertRaises(ValueError):self.store.feedback("agent-a",eid,1.5)
    def test_literal_query(self):
        self.store.record("agent-a","100% useful","result")
        self.assertEqual(self.store.recall("agent-a","%")[0].task,"100% useful")
if __name__=="__main__":unittest.main()
