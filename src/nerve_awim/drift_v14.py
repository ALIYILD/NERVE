"""Experimental drift-aware, uncertainty-weighted online scalar gain estimation.

Uses *only timestamped sensor pairs and actions*, never simulator true state.
Each transition is consumed at most once, even when delayed observations arrive.
The innovation statistic is heuristic, not a calibrated posterior probability.
"""
from math import isfinite

class DriftAwareGain:
    def __init__(self, initial=0.27, base_rate=0.08, threshold=0.12):
        if not 0.01<=initial<=1 or not 0<base_rate<=1 or threshold<=0:
            raise ValueError("invalid estimator parameters")
        self.gain=initial
        self.base_rate=base_rate
        self.threshold=threshold
        self.variance=0.05
        self.drift_count=0
        self.processed=set()
    def update(self, timestamp, action, previous_velocity, velocity, retention=0.82):
        if timestamp in self.processed:return False
        if action not in (-1,1) or not all(isfinite(x) for x in (previous_velocity,velocity,retention)):
            return False
        sample=(velocity-retention*previous_velocity)/action
        if not isfinite(sample) or not -0.3<=sample<=1.3:return False
        innovation=sample-self.gain
        drift=abs(innovation)>self.threshold
        if drift:self.drift_count+=1
        # Increase adaptation on strong evidence of a regime shift. The
        # uncertainty proxy prevents tiny fluctuations driving large updates.
        rate=min(0.5,self.base_rate*(3 if drift else 1)/(1+2*self.variance))
        self.gain=max(0.01,min(1.0,self.gain+rate*innovation))
        self.variance=max(0.0001,min(1.0,0.9*self.variance+0.1*innovation**2))
        self.processed.add(timestamp)
        return True
