import unittest
from nerve_awim.regression_v15 import compare

class RegressionTests(unittest.TestCase):
    def test_prediction_win_goal_loss_is_not_improvement(self):
        result=compare({"goal_error":.16,"late_prediction_error":.08},
                       {"goal_error":.1,"late_prediction_error":.1})
        self.assertFalse(result["passes"])
    def test_both_metrics_improve(self):
        result=compare({"goal_error":.08,"late_prediction_error":.08},
                       {"goal_error":.1,"late_prediction_error":.1})
        self.assertTrue(result["passes"])
    def test_reject_missing(self):
        with self.assertRaises(ValueError):compare({},{"goal_error":.1,"late_prediction_error":.1})
if __name__=="__main__":unittest.main()
