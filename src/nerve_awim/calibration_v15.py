"""Prequential rolling prediction intervals for NERVE-AWIM research.

Only previously resolved prediction errors enter the calibrator. The interval
is a rolling empirical absolute-error quantile, NOT a finite-sample conformal
guarantee under shifting, dependent time-series observations.
"""
from collections import deque
from math import isfinite, ceil

class RollingErrorInterval:
    def __init__(self, coverage=0.9, window=100, minimum=8):
        if not 0<coverage<1 or window<2 or minimum<1 or minimum>window:
            raise ValueError("invalid calibration settings")
        self.coverage=coverage
        self.minimum=minimum
        self.errors=deque(maxlen=window)
    def update(self, predicted, observed):
        if not all(isfinite(v) for v in (predicted,observed)):
            raise ValueError("nonfinite prediction or observation")
        self.errors.append(abs(predicted-observed))
    def radius(self):
        if len(self.errors)<self.minimum:return None
        sorted_errors=sorted(self.errors)
        index=min(len(sorted_errors)-1,max(0,ceil(self.coverage*len(sorted_errors))-1))
        return sorted_errors[index]
    def interval(self, prediction):
        if not isfinite(prediction):raise ValueError("nonfinite prediction")
        r=self.radius()
        return None if r is None else (prediction-r,prediction+r)
    def summary(self):
        return {"count":len(self.errors),"radius":self.radius(),"target_coverage":self.coverage}

def evaluate_intervals(pairs, coverage=.9, window=100, minimum=8):
    """Test-before-update evaluation; current outcome cannot calibrate itself."""
    model=RollingErrorInterval(coverage,window,minimum)
    covered=issued=0
    width_sum=0.
    for prediction,observation in pairs:
        interval=model.interval(prediction)
        if interval is not None:
            issued+=1
            covered+=interval[0]<=observation<=interval[1]
            width_sum+=interval[1]-interval[0]
        model.update(prediction,observation)
    return {"issued":issued,"empirical_coverage":covered/issued if issued else None,
            "mean_interval_width":width_sum/issued if issued else None,
            "target_coverage":coverage}
