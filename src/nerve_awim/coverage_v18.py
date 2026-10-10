"""v1.8 audit of sequential uncertainty intervals and sensor outages.

Prequential diagnostics: the interval is checked before the corresponding
observation can update it. Outages are counted separately; missing observations
are NEVER interpreted as covered outcomes.
"""
from dataclasses import dataclass
from .calibration_v15 import RollingErrorInterval

@dataclass(frozen=True)
class CoverageReport:
    observed: int
    unavailable: int
    interval_issued: int
    covered: int
    empirical_coverage: float | None
    mean_width: float | None

class CoverageAuditor:
    def __init__(self, target=0.9, window=100, minimum=8):
        self.calibrator=RollingErrorInterval(target,window,minimum)
        self.observed=0
        self.unavailable=0
        self.issued=0
        self.covered=0
        self.width=0.0
    def record(self, prediction, observation):
        if observation is None:
            self.unavailable+=1
            return
        interval=self.calibrator.interval(prediction)
        if interval is not None:
            self.issued+=1
            self.covered+=int(interval[0]<=observation<=interval[1])
            self.width+=interval[1]-interval[0]
        self.calibrator.update(prediction,observation)
        self.observed+=1
    def report(self):
        return CoverageReport(self.observed,self.unavailable,self.issued,
            self.covered,self.covered/self.issued if self.issued else None,
            self.width/self.issued if self.issued else None)
