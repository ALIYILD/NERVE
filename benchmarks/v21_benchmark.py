"""Synthetic supervised sensor-recovery experiment, no physical actuation.

An independent simulation supervisor supplies explicit approval after enough
new observations. Episode aborts on infeasibility; withheld decisions are not
silently treated as safe zero-action choices.
"""
import json,random,statistics
from nerve_awim.recovery_v21 import SupervisedWorldCore
def episode(seed,steps=80):
    rng=random.Random(seed)
    c=SupervisedWorldCore(max_missing=5,recovery_samples=3,
        risk_aversion=.25,safe_position=6,safe_velocity=2,
        min_samples=6,target=1.2,learning_rate=.08,estimator="drift",horizon=3,bound=6.)
    position=velocity=0.
    queue=[];goals=[];violations=0;withheld=0;approvals=0
    for t in range(steps):
        due=[item for item in queue if item[0]<=t]
        queue=[item for item in queue if item[0]>t]
        if not due:c.miss()
        for _,ts,p,v in due:c.ingest(ts,position=p,velocity=v)
        if c.phase=="awaiting_approval":
            if c.approve_recovery(True):approvals+=1
        result=c.decide()
        if result.action is None:
            withheld+=1
            # When unavailable an external supervisor holds the simulated
            # plant at its last observed position. This is an explicit
            # benchmark assumption, NOT a physically safe fallback.
            action=0
            c.core.filter.step(0)  # record supervised simulated transition
        else:action=result.action
        gain=(.27,.48,.15,.4)[min(t//20,3)]
        velocity=.82*velocity+gain*action
        position+=velocity
        violations+=int(abs(position)>6 or abs(velocity)>2)
        goals.append(abs(position-c.core.target))
        if not (35<=t<50) and rng.random()>=.12:
            queue.append((t+2,t,position+rng.gauss(0,.03),velocity+rng.gauss(0,.025)))
    return {"final_goal_error":goals[-1],"late_goal_error":statistics.mean(goals[20:]),
        "withheld":withheld,"approved_recoveries":approvals,"constraint_violations":violations}
def benchmark(seeds=range(20)):
    runs=[episode(seed) for seed in seeds]
    return {"seeds":len(runs),"results":{k:statistics.mean(x[k] for x in runs) for k in runs[0]},
            "limitation":"External simulation supervisor applies zero control and authorises recovery; neither action is proven safe."}
if __name__=="__main__":print(json.dumps(benchmark(),indent=2,sort_keys=True))
