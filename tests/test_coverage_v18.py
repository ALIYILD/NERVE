import unittest
from nerve_awim.coverage_v18 import CoverageAuditor

class CoverageV18Tests(unittest.TestCase):
    def test_outage_not_counted_as_covered(self):
        a=CoverageAuditor(minimum=2)
        a.record(0,1);a.record(0,1);a.record(0,None)
        r=a.report()
        self.assertEqual((r.observed,r.unavailable,r.interval_issued),(2,1,0))
    def test_prequential_excludes_current_error(self):
        a=CoverageAuditor(minimum=2)
        a.record(0,0);a.record(0,0);a.record(0,10)
        r=a.report()
        self.assertEqual(r.interval_issued,1)
        self.assertEqual(r.covered,0)
    def test_warmup(self):
        a=CoverageAuditor(minimum=3)
        a.record(0,1)
        self.assertIsNone(a.report().empirical_coverage)
    def test_repeatable_report(self):
        a=CoverageAuditor(minimum=2)
        for x in [1,2,3,None,4]:a.record(0,x)
        self.assertEqual(a.report(),a.report())
if __name__=="__main__":unittest.main()
