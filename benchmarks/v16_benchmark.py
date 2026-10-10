"""Paired synthetic v1.6 uncertainty-gating experiment.

This is an exploratory diagnostic, not a performance claim.
Both controllers observe identical generated noise from each seed, but their
actions generate different trajectories. Reports action hold frequency as well
as goal and prediction errors. Re-running produces the same values.
"""
import json, random, statistics
from nerve_awim.calibrated_v16 import CalibratedController

def episode(seed, radius_limit, steps=80):
    rng=random.Random(seed)
    c=CalibratedController(radius_limit=radius_limit,min_samples=6,target=1.2,
                           learning_rate=.08,estimator="drift",horizon=3,bound=6.0)
    position=velocity=0.0
    queue=[]
    goal_errors=[]
    prediction_errors=[]
    for t in range(steps):
        ready=[x for x in queue if x[0]<=t]
        queue=[x for x in queue if x[0]>t]
        for _,ts,p,v in ready:
            c.ingest(ts,position=p,velocity=v)
        action=c.act()
        gain=(.27,.48,.15,.4)[min(t//20,3)]
        velocity=.82*velocity+gain*action
        position+=velocity
        goal_errors.append(abs(position-c.core.target))
        forecast=c.pending_predictions[t]
        prediction_errors.append(abs(forecast-velocity))
        if rng.random()>=.12:
            queue.append((t+2,t,position+rng.gauss(0,.03),velocity+rng.gauss(0,.025)))
    return {"final_goal_error":goal_errors[-1],
            "late_goal_error":statistics.mean(goal_errors[20:]),
            "late_prediction_error":statistics.mean(prediction_errors[20:]),
            "blocked_actions":c.blocked}

def benchmark(seeds=range(20)):
    results={}
    for name,limit in (("ungated",1e8),("uncertainty_gated",.15)):
        runs=[episode(seed,limit) for seed in seeds]
        results[name]={k:statistics.mean(x[k] for x in runs) for k in runs[0]}
    return {"seeds":len(seeds),"results":results,"notes":"synthetic heuristic; no guaranteed coverage or control safety"}

if __name__=="__main__":
    print(json.dumps(benchmark(),indent=2,sort_keys=True))
