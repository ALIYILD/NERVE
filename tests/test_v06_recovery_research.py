import unittest
from benchmarks.v06_recovery_research import benchmark, trial


class RecoveryResearchTests(unittest.TestCase):
    def test_suspension_and_manual_recovery(self):
        result = trial(True)
        self.assertTrue(result['suspended'])
        self.assertTrue(result['awaiting'])
        self.assertTrue(result['resumed'])

    def test_no_approval_does_not_resume(self):
        self.assertFalse(trial(False)['resumed'])

    def test_full_report(self):
        self.assertTrue(benchmark()['passed'])
