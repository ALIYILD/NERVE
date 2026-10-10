"""Paired fixed-budget comparison of contextual feedback versus identical experts.

Both methods have precisely the same two capabilities, specialist priors,
number of evaluation tasks, and exogenous observations. Only one uses
past feedback. Performance advantage is not assumed.
"""
import json,random,statistics
from nerve_awim.agents_v30 import Agent
from nerve_awim.collaboration_v31 import PredictiveCoordinator,EqualCapabilityBaseline

def episode(seed,steps=80,change=40):
    rng=random.Random(seed)
    agents=(Agent("a","clear",.25),Agent("b","rough",.5))
    adaptive=PredictiveCoordinator(agents)
    fixed=EqualCapabilityBaseline(agents)
    err_a=[];err_b=[];used=0
    for t in range(steps):
        context="clear" if t%2==0 else "rough"
        # Hidden context-specific gain shifts at a predetermined step.
        gain=(.25 if context=="clear" else .5) if t<change else (.4 if context=="clear" else .2)
        state=rng.uniform(-1,1);action=rng.choice((-1.,1.))
        observed=state+gain*action+rng.gauss(0,.02)
        a=adaptive.predict(str(t),context,state,action,"simulated")
        b=fixed.predict(str(t),context,state,action,"simulated")
        if t>=change:
            err_a.append(abs(a.next_state-observed))
            err_b.append(abs(b.next_state-observed))
        used+=int(a.memory_used)
        adaptive.observe(context,state,action,observed,"simulated")
    return {"adaptive_mae":statistics.mean(err_a),"baseline_mae":statistics.mean(err_b),
            "memory_used":used,"tasks":steps}
def benchmark(seeds=range(20)):
    runs=[episode(seed) for seed in seeds]
    return {"seeds":len(runs),"results":{k:statistics.mean(x[k] for x in runs) for k in runs[0]},
      "note":"Same specialist priors; only contextual feedback differs. Synthetic scalar dynamics."}
if __name__=="__main__":print(json.dumps(benchmark(),indent=2,sort_keys=True))
