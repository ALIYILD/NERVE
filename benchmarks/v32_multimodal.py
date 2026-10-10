"""NERVE v3.2 complementary-sensor ablation, synthetic and reproducible.

Compares a fusion of two specialist estimates against an equivalently informed
single linear predictor. Includes deterministic missing-modality faults.
This does not use a deployed multi-agent runtime or real sensors.
"""
import json,random,statistics

def episode(seed, steps=200, missing=.25):
    rng=random.Random(seed)
    shared=[0.,0.]; specialist=[0.,0.]
    errors={"single_fused":[],"specialist_fused":[],"single_sensor":[]}
    missed=0
    for t in range(steps):
        x=rng.uniform(-1,1); y=rng.uniform(-1,1)
        target=0.7*x-0.4*y+rng.gauss(0,.02)
        available=rng.random()>=missing
        if not available:missed+=1
        xx=x; yy=y if available else 0.
        fused_pred=shared[0]*xx+shared[1]*yy
        specialist_pred=specialist[0]*xx+specialist[1]*yy
        single_sensor_pred=shared[0]*xx
        if t>=80:
            errors["single_fused"].append(abs(fused_pred-target))
            errors["specialist_fused"].append(abs(specialist_pred-target))
            errors["single_sensor"].append(abs(single_sensor_pred-target))
        # Identical squared-error SGD, same information and update budget.
        e=fused_pred-target
        shared[0]-=.1*e*xx;shared[1]-=.1*e*yy
        e2=specialist_pred-target
        specialist[0]-=.1*e2*xx;specialist[1]-=.1*e2*yy
    return {**{k:statistics.mean(v) for k,v in errors.items()},"missing":missed}
def benchmark(seeds=range(20)):
    rows=[episode(s) for s in seeds]
    return {"seeds":len(rows),"results":{k:statistics.mean(r[k] for r in rows) for k in rows[0]},
       "notes":"single fused and specialists are intentionally mathematically equivalent under equal inputs"}
if __name__=="__main__":print(json.dumps(benchmark(),indent=2,sort_keys=True))
