"""v3.3 controlled nonlinear specialization vs unified learner experiment.

Same input stream, features, coefficients, updates, and parameter budget.
Two specialist models process context-specific nonlinear features. Unified
model uses the mathematically equivalent block-feature parameterization.
A true multi-agent advantage would require non-equivalent, cost-controlled
computation and is NOT expected here.
"""
import json, random, statistics, math

def features(x,y):
    return (x,y,x*y,x*x-y*y)

def episode(seed, steps=300, change=150, dropout=.2):
    rng=random.Random(seed)
    unified=[0.]*8
    specialist=[[0.]*4 for _ in range(2)]
    errors={"unified":[],"specialists":[],"single_linear":[]}
    basic=[0.,0.]
    for t in range(steps):
        context=t%2
        x,y=rng.uniform(-1,1),rng.uniform(-1,1)
        y_observed=y if rng.random()>=dropout else 0.
        f=features(x,y_observed)
        coefficient=([.6,-.2,.3,.15],[-.3,.7,-.2,.4])[context]
        if t>=change:
            coefficient=([.2,.3,-.4,.25],[.45,-.1,.3,-.15])[context]
        truth=sum(w*z for w,z in zip(coefficient,features(x,y)))+rng.gauss(0,.025)
        offset=context*4
        pred_u=sum(unified[offset+i]*f[i] for i in range(4))
        pred_s=sum(specialist[context][i]*f[i] for i in range(4))
        pred_b=basic[0]*x+basic[1]*y_observed
        if t>=change:
            for name,pred in (("unified",pred_u),("specialists",pred_s),
                              ("single_linear",pred_b)):
                errors[name].append(abs(pred-truth))
        for i,z in enumerate(f):
            unified[offset+i]+=.06*(truth-pred_u)*z
            specialist[context][i]+=.06*(truth-pred_s)*z
        basic[0]+=.06*(truth-pred_b)*x
        basic[1]+=.06*(truth-pred_b)*y_observed
    return {k:statistics.mean(v) for k,v in errors.items()}

def benchmark(seeds=range(20)):
    runs=[episode(seed) for seed in seeds]
    return {"seeds":len(runs),"nonlinear_parameter_budget":8,
            "results":{k:statistics.mean(r[k] for r in runs) for k in runs[0]},
            "interpretation":"Specialists and unified 8-parameter block model are algebraically equivalent; linear 2-parameter reference is less expressive."}
if __name__=="__main__":print(json.dumps(benchmark(),indent=2,sort_keys=True))
