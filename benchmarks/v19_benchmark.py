"""Comparison of fixed and adaptive prequential coverage during a sensor outage.

Exactly the same synthetic prediction/observation stream is delivered to
each auditor. This is a calibration diagnostic, not a control benchmark.
"""
import json, random, statistics
from nerve_awim.coverage_v18 import CoverageAuditor
from nerve_awim.adaptive_calibration_v19 import AdaptiveCoverageAuditor

def episode(seed,mode,steps=100):
    rng=random.Random(seed)
    audit=AdaptiveCoverageAuditor(minimum=8) if mode=="adaptive" else CoverageAuditor(minimum=8)
    for t in range(steps):
        prediction=0.0
        missing=(35<=t<50) or rng.random()<.12
        observation=None if missing else rng.gauss(0,.06 if t<40 else .16)
        audit.record(prediction,observation)
    r=audit.report()
    return {"empirical_coverage":r.empirical_coverage,
            "mean_width":r.mean_width,
            "outages":r.unavailable,
            "alerts":getattr(audit,"failure_alerts",0)}
def benchmark(seeds=range(20)):
    results={}
    for mode in ("fixed","adaptive"):
        runs=[episode(seed,mode) for seed in seeds]
        results[mode]={k:statistics.mean(x[k] for x in runs) for k in runs[0]}
    return {"seeds":len(seeds),"target_coverage":.9,"results":results,
            "disclaimer":"synthetic dependent streams; no distribution-free guarantee"}
if __name__=="__main__":print(json.dumps(benchmark(),indent=2,sort_keys=True))
