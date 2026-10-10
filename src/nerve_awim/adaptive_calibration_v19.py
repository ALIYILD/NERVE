"""v1.9 online calibration diagnostics with outage awareness.

The radius is scaled using *past* prequential coverage only. Missed observations
are tracked separately. Does not guarantee 90% marginal coverage under drift.
"""
from .coverage_v18 import CoverageAuditor

class AdaptiveCoverageAuditor(CoverageAuditor):
    def __init__(self,target=.9,window=100,minimum=8,adapt_rate=.1,
                 min_scale=.5,max_scale=4):
        super().__init__(target,window,minimum)
        if not 0<adapt_rate<=1 or not 0<min_scale<=max_scale:
            raise ValueError("invalid adaptive calibration settings")
        self.scale=1.
        self.adapt_rate=adapt_rate
        self.min_scale=min_scale
        self.max_scale=max_scale
        self.consecutive_missing=0
        self.failure_alerts=0
    def record(self,prediction,observation):
        if observation is None:
            self.consecutive_missing+=1
            if self.consecutive_missing==5:self.failure_alerts+=1
            self.unavailable+=1
            return
        self.consecutive_missing=0
        interval=self.calibrator.interval(prediction)
        if interval is not None:
            radius=self.calibrator.radius()*self.scale
            hit=abs(observation-prediction)<=radius
            self.issued+=1
            self.covered+=int(hit)
            self.width+=2*radius
            # Adaptive multiplicative correction; updated only after scoring.
            self.scale=max(self.min_scale,min(self.max_scale,
                self.scale*(1+self.adapt_rate*((1 if not hit else 0)-
                                                (1-self.calibrator.coverage)))))
        self.calibrator.update(prediction,observation)
        self.observed+=1
