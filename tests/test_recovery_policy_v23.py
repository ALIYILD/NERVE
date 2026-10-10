import tempfile,unittest
from pathlib import Path
from nerve_awim.recovery_policy_v23 import RecoveryEvidenceEvaluator,JsonlAudit

class PolicyV23Tests(unittest.TestCase):
    def test_consistent(self):
        v=RecoveryEvidenceEvaluator().evaluate([
          {"timestamp":1,"position":0.1,"velocity":0.1},
          {"timestamp":2,"position":0.2,"velocity":0.2}])
        self.assertTrue(v.accepted)
    def test_conflict(self):
        v=RecoveryEvidenceEvaluator().evaluate([
          {"timestamp":1,"position":0.1,"velocity":0.1},
          {"timestamp":2,"position":0.2,"velocity":1.2}])
        self.assertEqual(v.reason,"contradictory_velocity")
    def test_duplicates(self):
        row={"timestamp":1,"position":0.1,"velocity":0.1}
        self.assertFalse(RecoveryEvidenceEvaluator().evaluate([row,row]).accepted)
    def test_audit_append_read(self):
        with tempfile.TemporaryDirectory() as d:
            a=JsonlAudit(Path(d)/"audit.jsonl")
            a.append("outage",1)
            a.append("review",1,{"accepted":False})
            self.assertEqual(len(a.read()),2)
    def test_audit_modified_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"audit.jsonl"
            a=JsonlAudit(p);a.append("outage",1)
            p.write_text(p.read_text().replace("outage","fake"))
            with self.assertRaises(ValueError):a.read()
if __name__=="__main__":unittest.main()
