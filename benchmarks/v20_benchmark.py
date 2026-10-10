"""v2.0 paired synthetic outage benchmark; no hardware safety guarantee."""
import json,random,statistics
from nerve_awim.risk_v17 import RiskAwareController
from nerve_awim.worldcore_v20 import WorldCoreV2

def episode(seed, version="v20",steps=80):
    rng=random.Random(seed)
    settings=dict(risk_aversion=.25,safe_position=6,safe_velocity=2,
                  min_samples=6,target=1.2,learning_rate=.08,
                  estimator="drift",horizon=3,bound=6.)
    c=WorldCoreV2(max_missing=5,**settings) if version=="v20" else RiskAwareController(**settings)
    position=velocity=0.
    pending=[]; errors=[];violations=0;aborted=0
    for t in range(steps):
        due=[r for r in pending if r[0]<=t]
        pending=[r for r in pending if r[0]>t]
        if version=="v20" and not due:c.miss()
        for _,timestamp,p,v in due:c.ingest(timestamp,position=p,velocity=v)
        try:
            action=c.act()
        except RuntimeError:
            aborted=1;break
        gain=(.27,.48,.15,.4)[min(t//20,3)]
        velocity=.82*velocity+gain*action
        position+=velocity
        errors.append(abs(position-c.core.target))
        violations+=int(abs(position)>6 or abs(velocity)>2)
        dropout=(35<=t<50) or rng.random()<.12
        if not dropout:
            pending.append((t+2,t,position+rng.gauss(0,.03),velocity+rng.gauss(0,.025)))
    return {"completed_steps":len(errors),"aborted":aborted,
            "final_goal_error":errors[-1] if errors else None,
            "violations":violations,
            "empirical_coverage":c.auditor.report().empirical_coverage if version=="v20" else None}
def benchmark(seeds=range(20)):
    result={}
    for method in ("v17","v20"):
        runs=[episode(seed,method) for seed in seeds]
        result[method]={key:(statistics.mean(r[key] for r in runs if r[key] is not None)
            if any(r[key] is not None for r in runs) else None) for key in runs[0]}
    return {"seeds":len(seeds),"results":result,"note":"aborted episodes are not successful or safe completion"}
if __name__=="__main__":print(json.dumps(benchmark(),indent=2,sort_keys=True))
