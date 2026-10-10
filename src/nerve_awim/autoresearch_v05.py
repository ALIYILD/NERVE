"""v0.5 independent absolute research eligibility gate.

Research candidates are not authorised for deployment. Thresholds are
fixed by evaluator code, not supplied by experimental proposals.
"""
from dataclasses import dataclass
import json
from .autoresearch_v04 import Proposal, evaluate, VALIDATION, REPORT_ONLY

MIN_COMPLETION=0.95
MAX_ABORT_FRACTION=0.0
MAX_VIOLATIONS=0.0

@dataclass(frozen=True)
class Eligibility:
    eligible:bool
    reasons:tuple[str,...]

def eligibility(metrics):
    reasons=[]
    if metrics["completion"]<MIN_COMPLETION:reasons.append("completion_below_absolute_minimum")
    if metrics["abort"]>MAX_ABORT_FRACTION:reasons.append("episode_abort_detected")
    if metrics["violations"]>MAX_VIOLATIONS:reasons.append("constraint_violation_detected")
    return Eligibility(not reasons,tuple(reasons))

def experiment(candidates):
    candidates=tuple(candidates)
    if not 1<=len(candidates)<=8 or len({c.name for c in candidates})!=len(candidates):
        raise ValueError("invalid experiment budget")
    baseline=Proposal("baseline",5,.25)
    base=evaluate(baseline,VALIDATION)
    best=baseline; best_score=base["goal_penalized"]
    trials=[]
    for candidate in candidates:
        m=evaluate(candidate,VALIDATION)
        check=eligibility(m)
        better=check.eligible and m["goal_penalized"]<best_score-1e-5
        trials.append({"candidate":candidate.name,"validation":m,
            "eligible_for_review":check.eligible,"reasons":list(check.reasons),
            "research_decision":"retain" if better else "reject"})
        if better:best,best_score=candidate,m["goal_penalized"]
    final=evaluate(best,REPORT_ONLY)
    final_gate=eligibility(final)
    return {"research_baseline":base,"candidate_results":trials,
       "selected_for_research":best.name,
       "holdout_metrics":final,
       "eligible_for_deployment_review":final_gate.eligible,
       "holdout_rejection_reasons":list(final_gate.reasons),
       "disclaimer":"Eligibility for review is not safety certification or permission to deploy."}
if __name__=="__main__":
    print(json.dumps(experiment([Proposal("long-outage",8,.25),
        Proposal("short-outage",3,.25)]),indent=2,sort_keys=True))
