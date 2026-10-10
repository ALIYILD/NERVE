"""Paired v1.7 benchmark: ungated, v1.6 threshold, v1.7 risk aware.

Each seed reuses exogenous noise draws; trajectories differ by actions.
Infeasible plans are counted, not silently converted to a safe action.
"""
import json,random,statistics
from nerve_awim.calibrated_v16 import CalibratedController
from nerve_awim.risk_v17 import RiskAwareController

def episode(seed,mode,steps=80):
    rng=random.Random(seed)
    opts=dict(min_samples=6,target=1.2,learning_rate=.08,estimator="drift",horizon=3,bound=6.0)
    if mode=="risk":
        c=RiskAwareController(risk_aversion=.25,safe_position=6,safe_velocity=2,**opts)
    else:
        c=CalibratedController(radius_limit=.15 if mode=="gate" else 1e8,**opts)
    position=velocity=0.
    queue=[]
    goal=[];errors=[];violations=0;infeasible=0
    for t in range(steps):
        due=[x for x in queue if x[0]<=t]
        queue=[x for x in queue if x[0]>t]
        for _,ts,p,v in due:c.ingest(ts,position=p,velocity=v)
        try: action=c.act()
        except RuntimeError:
            # Abort this episode instead of assuming that zero action is safe.
            infeasible+=1
            break
        gain=(.27,.48,.15,.4)[min(t//20,3)]
        velocity=.82*velocity+gain*action
        position+=velocity
        violations+=int(abs(position)>6 or abs(velocity)>2)
        goal.append(abs(position-c.core.target))
        errors.append(abs(c.pending_predictions[t]-velocity))
        if rng.random()>=.12:
            queue.append((t+2,t,position+rng.gauss(0,.03),velocity+rng.gauss(0,.025)))
    return {"final_goal_error":goal[-1] if goal else None,
            "late_goal_error":statistics.mean(goal[20:]) if len(goal)>20 else None,
            "late_prediction_error":statistics.mean(errors[20:]) if len(errors)>20 else None,
            "constraint_violations":violations,"infeasible_episodes":infeasible,
            "completed_steps":len(goal)}
def benchmark(seeds=range(20)):
    result={}
    for mode in ("ungated","gate","risk"):
        runs=[episode(seed,mode) for seed in seeds]
        keys=runs[0]
        result[mode]={k:(statistics.mean(v[k] for v in runs if v[k] is not None)
                   if any(v[k] is not None for v in runs) else None) for k in keys}
    return {"seeds":len(seeds),"results":result,
            "disclaimer":"synthetic results; heuristic intervals and safety envelopes are not validated"}
if __name__=="__main__":print(json.dumps(benchmark(),indent=2,sort_keys=True))
