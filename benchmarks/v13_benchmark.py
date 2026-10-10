"""Reproducible synthetic benchmark for sensor-only v1.3 adaptive MPC.

Run: PYTHONPATH=src python benchmarks/v13_benchmark.py
Only sensor observations enter the controllers. Truth is retained solely by
the simulator and scoring. Results vary across seeds; no superiority assumed.
"""
import json, math, random, statistics
from nerve_awim.integrated_v13 import SensorOnlyController

def experiment(seed, adaptive, steps=60, change=30, delay=2, dropout=0.12):
    rng=random.Random(seed)
    controller=SensorOnlyController(target=1.2,learning_rate=.08 if adaptive else 0.0000001,
                                    horizon=3, bound=6.0)
    position=velocity=0.0
    pending=[]
    position_errors=[]
    velocity_errors=[]
    prediction_errors=[]
    for t in range(steps):
        due=[item for item in pending if item[0]<=t]
        pending=[item for item in pending if item[0]>t]
        for _,timestamp,p,v in due:
            controller.ingest(timestamp,position=p,velocity=v)
        estimate=controller.filter.state
        velocity_errors.append(abs(estimate.velocity-velocity))
        decision=controller.act()
        gain=.27 if t<change else .48
        velocity=.82*velocity+gain*decision.action
        position+=velocity
        prediction_errors.append(abs(decision.predicted_velocity-velocity))
        position_errors.append(abs(position-controller.target))
        if rng.random()>=dropout:
            pending.append((t+delay,t,position+rng.gauss(0,.03),
                            velocity+rng.gauss(0,.025)))
    return dict(goal_error=position_errors[-1],
                late_goal_error=statistics.mean(position_errors[change:]),
                late_prediction_error=statistics.mean(prediction_errors[change:]),
                late_state_error=statistics.mean(velocity_errors[change:]))

def benchmark(seeds=range(20)):
    adaptive=[experiment(seed,True) for seed in seeds]
    frozen=[experiment(seed,False) for seed in seeds]
    metrics=adaptive[0].keys()
    return {"config":{"seeds":len(adaptive),"steps":60,"change_step":30,"delay":2,"dropout":0.12},
            "adaptive":{m:statistics.mean(x[m] for x in adaptive) for m in metrics},
            "frozen":{m:statistics.mean(x[m] for x in frozen) for m in metrics}}
if __name__=="__main__":print(json.dumps(benchmark(),indent=2,sort_keys=True))
