"""NERVE AutoResearch v0.1 — bounded configuration experimentation.

Inspired by the experiment-selection methodology of karpathy/autoresearch,
not a fork or autonomous code-editing system. Evaluation is fixed in this
module; proposed configs cannot alter metrics, seeds or promotion rules.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import json,random,statistics,time

@dataclass(frozen=True)
class Candidate:
    name:str
    learning_rate:float
    def __post_init__(self):
        if not self.name or not 0<self.learning_rate<=.5:
            raise ValueError("invalid candidate")

TRAIN_SEEDS=tuple(range(10))
HOLDOUT_SEEDS=tuple(range(100,110))
TRAIN_STEPS=80

def evaluate(candidate,seeds):
    """Same changing scalar dynamics task for all candidate parameters."""
    scores=[]
    for seed in seeds:
        rng=random.Random(seed)
        estimate=.25;errors=[]
        for step in range(TRAIN_STEPS):
            true=.25 if step<40 else .47
            action=rng.choice((-1.,1.))
            measured=true*action+rng.gauss(0,.03)
            prediction=estimate*action
            if step>=40:errors.append(abs(prediction-measured))
            estimate+=candidate.learning_rate*(measured/action-estimate)
        scores.append(statistics.mean(errors))
    return statistics.mean(scores)

def research(candidates,baseline=Candidate("baseline",.02),tolerance=.00001):
    if not candidates:raise ValueError("no candidates")
    baseline_score=evaluate(baseline,TRAIN_SEEDS)
    rows=[]
    best=baseline
    best_score=baseline_score
    for candidate in candidates:
        score=evaluate(candidate,TRAIN_SEEDS)
        kept=score<best_score-tolerance
        rows.append({"name":candidate.name,"learning_rate":candidate.learning_rate,
            "validation_mae":score,"decision":"keep" if kept else "reject"})
        if kept:best,best_score=candidate,score
    # Holdout queried ONCE for final selected candidate and untouched baseline.
    return {"baseline":asdict(baseline),"baseline_validation_mae":baseline_score,
        "experiments":rows,"selected":asdict(best),
        "selected_validation_mae":best_score,
        "holdout":{"baseline_mae":evaluate(baseline,HOLDOUT_SEEDS),
                   "selected_mae":evaluate(best,HOLDOUT_SEEDS)},
        "warning":"Selection on fixed validation seeds can overfit. Holdout is reporting-only, never used for selection."}

def write_ledger(report,path):
    destination=Path(path)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open("a",encoding="utf-8") as f:
        f.write(json.dumps({"recorded_at":int(time.time()),**report},sort_keys=True)+"\n")

if __name__=="__main__":
    report=research([Candidate("slow",.01),Candidate("moderate",.06),
                     Candidate("fast",.15),Candidate("very-fast",.3)])
    print(json.dumps(report,indent=2,sort_keys=True))
