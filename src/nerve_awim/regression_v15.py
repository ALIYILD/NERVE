"""Regression evaluation for benchmark comparisons.

Research metrics are informational, not automated deployment approval.
A candidate passes only when goal and prediction error are within configured
relative regression tolerances. No synthetic result implies real-world safety.
"""
from math import isfinite

def compare(candidate, baseline, *, max_goal_regression=0.05, max_prediction_regression=0.05):
    required=("goal_error","late_prediction_error")
    if any(k not in candidate or k not in baseline for k in required):
        raise ValueError("missing benchmark metric")
    if min(max_goal_regression,max_prediction_regression)<0:
        raise ValueError("negative regression tolerance")
    details={}
    for metric,tolerance in (("goal_error",max_goal_regression),
                             ("late_prediction_error",max_prediction_regression)):
        a,b=candidate[metric],baseline[metric]
        if not all(isfinite(v) and v>=0 for v in (a,b)):
            raise ValueError("invalid benchmark metric")
        allowed=b*(1+tolerance)+1e-12
        details[metric]={"candidate":a,"baseline":b,
                         "passes":a<=allowed,
                         "difference":a-b}
    return {"passes":all(v["passes"] for v in details.values()),"metrics":details}
