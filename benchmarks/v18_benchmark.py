"""v1.8 abrupt sensor-outage stress test (synthetic).

Policy trajectories and exogenous sensor noise are generated separately for
each seed. Only resolved observations count in empirical interval coverage.
No calibrated guarantees under distribution shift are implied.
"""
import json, random, statistics
from nerve_awim.risk_v17 import RiskAwareController
from nerve_awim.coverage_v18 import CoverageAuditor

def episode(seed, outage=True, steps=80):
    rng=random.Random(seed)
    c=RiskAwareController(risk_aversion=.25,safe_position=6,safe_velocity=2,
        min_samples=6,target=1.2,learning_rate=.08,estimator="drift",horizon=3,bound=6.0)
    auditor=CoverageAuditor(minimum=6)
    position=velocity=0.0
    pending=[]
    goal_errors=[]
    violations=0
    infeasible=0
    for t in range(steps):
        due=[item for item in pending if item[0]<=t]
        pending=[item for item in pending if item[0]>t]
        for _,timestamp,p,v in due:
            prediction=c.pending_predictions.get(timestamp)
            c.ingest(timestamp,position=p,velocity=v)
            if prediction is not None:
                auditor.record(prediction,v)
        try:
            action=c.act()
        except RuntimeError:
            infeasible=1
            break
        gain=(.27,.48,.15,.4)[min(t//20,3)]
        velocity=.82*velocity+gain*action
        position+=velocity
        violations+=int(abs(position)>6 or abs(velocity)>2)
        goal_errors.append(abs(position-c.core.target))
        dropped=(outage and 35<=t<50) or rng.random()<.12
        if dropped:
            auditor.record(c.pending_predictions[t],None)
        else:
            pending.append((t+2,t,position+rng.gauss(0,.03),
                            velocity+rng.gauss(0,.025)))
    report=auditor.report()
    return {"final_goal_error":goal_errors[-1] if goal_errors else None,
        "late_goal_error":statistics.mean(goal_errors[20:]) if len(goal_errors)>20 else None,
        "empirical_coverage":report.empirical_coverage,
        "mean_interval_width":report.mean_width,
        "observed":report.observed,"outages":report.unavailable,
        "intervals_issued":report.interval_issued,
        "violations":violations,"infeasible":infeasible,
        "completed_steps":len(goal_errors)}

def benchmark(seeds=range(20)):
    results={}
    for label,outage in (("normal",False),("abrupt_outage",True)):
        runs=[episode(seed,outage) for seed in seeds]
        results[label]={key:(statistics.mean(r[key] for r in runs if r[key] is not None)
            if any(r[key] is not None for r in runs) else None) for key in runs[0]}
    return {"seeds":len(seeds),"outage_interval":[35,50],
        "results":results,"limitations":"synthetic, retrospective interval coverage; no formal safety guarantees"}
if __name__=="__main__":
    print(json.dumps(benchmark(),indent=2,sort_keys=True))
