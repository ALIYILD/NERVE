"""AutoResearch v0.4: bounded WorldCore closed-loop parameter evaluation.

The plant and sensor disturbances are fixed in evaluator code. Candidates only
control max_missing and risk_aversion, not seeds, metrics or abort penalties.
No arbitrary subprocess or code execution. Pure simulation, not safety evidence.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import json,random,statistics,math
from nerve_awim.worldcore_v20 import WorldCoreV2

VALIDATION=tuple(range(40,50))
REPORT_ONLY=tuple(range(400,410))
STEPS=80
@dataclass(frozen=True)
class Proposal:
    name:str
    max_missing:int
    risk_aversion:float
    def __post_init__(self):
        if (not isinstance(self.name,str) or not 0<len(self.name)<=48
                or type(self.max_missing) is not int or not 2<=self.max_missing<=12
                or not isinstance(self.risk_aversion,(float,int))
                or not math.isfinite(self.risk_aversion) or not 0<=self.risk_aversion<=2):
            raise ValueError("invalid candidate")

def episode(seed,proposal):
    rng=random.Random(seed)
    c=WorldCoreV2(max_missing=proposal.max_missing,
        risk_aversion=proposal.risk_aversion,safe_position=6,safe_velocity=2,
        min_samples=6,target=1.2,learning_rate=.08,estimator="drift",horizon=3,bound=6.)
    position=velocity=0.
    pending=[];goal=[];pred=[];violations=0;aborted=0
    for t in range(STEPS):
        due=[r for r in pending if r[0]<=t]
        pending=[r for r in pending if r[0]>t]
        if not due:c.miss()
        for _,timestamp,p,v in due:c.ingest(timestamp,position=p,velocity=v)
        try:action=c.act()
        except RuntimeError:
            aborted=1
            break
        gain=(.27,.48,.15,.4)[min(t//20,3)]
        velocity=.82*velocity+gain*action
        position+=velocity
        goal.append(abs(position-c.core.target))
        forecast=c.pending_predictions.get(t)
        if forecast is not None:pred.append(abs(forecast-velocity))
        violations+=int(abs(position)>6 or abs(velocity)>2)
        dropout=35<=t<50 or rng.random()<.12
        if not dropout:
            pending.append((t+2,t,position+rng.gauss(0,.03),velocity+rng.gauss(0,.025)))
    return {"completion":len(goal)/STEPS,"abort":aborted,"violations":violations,
        "goal_penalized":(sum(goal)+2*(STEPS-len(goal)))/STEPS,
        "prediction_penalized":(sum(pred)+2*(STEPS-len(pred)))/STEPS}

def evaluate(proposal,seeds):
    rows=[episode(s,proposal) for s in seeds]
    return {k:statistics.mean(r[k] for r in rows) for k in rows[0]}

def experiment(candidates,ledger_path=None):
    candidates=tuple(candidates)
    if not 1<=len(candidates)<=8 or len({c.name for c in candidates})!=len(candidates):
        raise ValueError("invalid candidate budget")
    baseline=Proposal("baseline",5,.25)
    base=evaluate(baseline,VALIDATION)
    best=baseline;current=base;trials=[]
    for candidate in candidates:
        metrics=evaluate(candidate,VALIDATION)
        # Constraint gates reject improved error obtained by premature abort.
        constraints=(metrics["abort"]<=current["abort"]+1e-12
          and metrics["violations"]<=current["violations"]+1e-12
          and metrics["completion"]>=current["completion"]-1e-12
          and metrics["prediction_penalized"]<=current["prediction_penalized"]+1e-12)
        improve=metrics["goal_penalized"]<current["goal_penalized"]-1e-5
        accepted=constraints and improve
        trials.append({"candidate":asdict(candidate),"metrics":metrics,
                       "decision":"keep" if accepted else "reject"})
        if accepted:best,current=candidate,metrics
    result={"baseline":base,"selected":asdict(best),"selected_validation":current,
      "trials":trials,"report_only_holdout":{"baseline":evaluate(baseline,REPORT_ONLY),
                                           "selected":evaluate(best,REPORT_ONLY)},
      "limitations":"Fixed synthetic WorldCore plant. Stopping is counted as lost completion, not success."}
    if ledger_path is not None:
        p=Path(ledger_path);p.parent.mkdir(parents=True,exist_ok=True)
        with p.open("a",encoding="utf-8") as out:
            out.write(json.dumps(result,sort_keys=True)+"\n")
    return result

if __name__=="__main__":
    print(json.dumps(experiment([Proposal("short-outage",3,.25),
     Proposal("long-outage",8,.25),Proposal("low-risk",5,.1),
     Proposal("high-risk",5,.6)]),indent=2,sort_keys=True))
