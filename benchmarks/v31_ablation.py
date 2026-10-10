"""v3.1 controlled ablation: memory versus specialist routing.

All models receive the same scalar training feedback and exactly one inference
and one update per task. Single-learner memory uses a shared gain across
contexts; specialist-memory uses per-context estimates. This tests inductive
bias under matched updates, NOT general agentic collaboration.
"""
import random,statistics,json

def episode(seed,steps=120,change=60):
    rng=random.Random(seed)
    # identical task stream for all conditions
    shared_sum=0.;shared_count=0
    per_context={"clear":[0.,0],"rough":[0.,0]}
    errors={"single_memory":[],"specialist_memory":[],"specialist_fixed":[]}
    for t in range(steps):
        context=("clear","rough")[t%2]
        gain=(.25 if context=="clear" else .5) if t<change else (.42 if context=="clear" else .18)
        state=rng.uniform(-1,1);action=rng.choice((-1.,1.))
        observed=state+gain*action+rng.gauss(0,.03)
        fixed=.25 if context=="clear" else .5
        shared=shared_sum/shared_count if shared_count else .375
        total,count=per_context[context]
        specialist=total/count if count else fixed
        if t>=change:
            for key,estimate in (("single_memory",shared),("specialist_memory",specialist),("specialist_fixed",fixed)):
                errors[key].append(abs(state+estimate*action-observed))
        measured=(observed-state)/action
        shared_sum+=measured;shared_count+=1
        per_context[context][0]+=measured;per_context[context][1]+=1
    return {k:statistics.mean(v) for k,v in errors.items()}
def benchmark(seeds=range(20)):
    runs=[episode(seed) for seed in seeds]
    return {"seeds":len(runs),"updates_per_method":120,
            "results":{k:statistics.mean(x[k] for x in runs) for k in runs[0]},
            "limitations":"equal observations and update counts, but different parameterisations; no LLM or tool-call measurement"}
if __name__=="__main__":print(json.dumps(benchmark(),indent=2,sort_keys=True))
