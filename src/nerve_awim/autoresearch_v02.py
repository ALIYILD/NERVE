"""NERVE AutoResearch v0.2: fixed evaluator, typed candidate proposals and history.

Candidates may tune a bounded WorldCore-adjacent drift learning rate.
No arbitrary code evaluation or commands are supported. This runs locally,
does not promise OS-level sandboxing, and cannot promote production code.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import json,random,statistics,math,hashlib,time

VALIDATION_SEEDS=tuple(range(30))
HOLDOUT_SEEDS=tuple(range(1000,1030))

@dataclass(frozen=True)
class Proposal:
    proposal_id:str
    gain_lr:float
    reason:str
    def __post_init__(self):
        if (not isinstance(self.proposal_id,str) or not 0<len(self.proposal_id)<=64
            or not isinstance(self.reason,str) or not 0<len(self.reason)<=500
            or not isinstance(self.gain_lr,(float,int)) or isinstance(self.gain_lr,bool)
            or not math.isfinite(self.gain_lr) or not 0.001<=self.gain_lr<=.5):
            raise ValueError("invalid bounded proposal")

def worldcore_drift_score(gain_lr,seeds):
    """Synthetic one-dimensional sensor-feedback system with gain drift."""
    scores=[]
    for seed in seeds:
        rng=random.Random(seed)
        estimated=.25
        err=[]
        for t in range(100):
            true=.25 if t<50 else .60
            action=rng.choice((-1.,1.))
            observation=true*action+rng.gauss(0,.03)
            if t>=50:err.append(abs(estimated*action-observation))
            estimated+=gain_lr*((observation/action)-estimated)
        scores.append(statistics.mean(err))
    return statistics.mean(scores)

class ResearchCoordinator:
    def __init__(self, ledger_path, baseline_lr=.02, max_trials=8):
        if not 1<=max_trials<=100:raise ValueError("invalid budget")
        self.ledger_path=Path(ledger_path)
        self.baseline_lr=Proposal("baseline",baseline_lr,"fixed reference").gain_lr
        self.max_trials=max_trials
    def run(self,proposals):
        proposals=tuple(proposals)
        if not proposals or len(proposals)>self.max_trials:
            raise ValueError("candidate budget exceeded")
        if len({p.proposal_id for p in proposals})!=len(proposals):
            raise ValueError("duplicate proposal IDs")
        best=Proposal("baseline",self.baseline_lr,"fixed reference")
        reference=worldcore_drift_score(best.gain_lr,VALIDATION_SEEDS)
        best_score=reference
        history=[]
        for proposal in proposals:
            score=worldcore_drift_score(proposal.gain_lr,VALIDATION_SEEDS)
            keep=score<best_score-1e-5
            history.append({"candidate":asdict(proposal),"validation_mae":score,
                            "decision":"keep" if keep else "reject"})
            if keep:best,best_score=proposal,score
        report={"experiment":"worldcore_drift_v02","baseline_validation_mae":reference,
            "trials":history,"selected":asdict(best),"selected_validation_mae":best_score,
            "holdout_baseline_mae":worldcore_drift_score(self.baseline_lr,HOLDOUT_SEEDS),
            "holdout_selected_mae":worldcore_drift_score(best.gain_lr,HOLDOUT_SEEDS),
            "evaluation_id":hashlib.sha256(str((VALIDATION_SEEDS,HOLDOUT_SEEDS)).encode()).hexdigest(),
            "warning":"Synthetic benchmark only; holdout cannot be used for further candidate selection"}
        self.ledger_path.parent.mkdir(parents=True,exist_ok=True)
        with self.ledger_path.open("a",encoding="utf-8") as f:
            f.write(json.dumps(report,sort_keys=True)+"\n")
        return report

def demo():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        return ResearchCoordinator(Path(tmp)/"ledger.jsonl").run([
            Proposal("conservative",.01,"slower gain update"),
            Proposal("balanced",.06,"moderate update"),
            Proposal("rapid",.2,"rapid update"),
            Proposal("aggressive",.4,"test large updates")])
if __name__=="__main__":print(json.dumps(demo(),indent=2,sort_keys=True))
