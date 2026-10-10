"""AutoResearch v0.9: controlled outage-tolerance experiment.

Measures goal/completion tradeoffs; does NOT authorise unsafe automatic recovery.
"""
import json
from .autoresearch_v04 import Proposal,evaluate,VALIDATION,REPORT_ONLY

def experiment():
    settings=(3,5,8,10,12)
    rows=[]
    for threshold in settings:
        proposal=Proposal("outage-"+str(threshold),threshold,.25)
        validation=evaluate(proposal,VALIDATION)
        rows.append({"max_missing":threshold,"validation":validation,
                     "meets_completion_95pct":validation["completion"]>=.95,
                     "no_abort":validation["abort"]==0})
    # Selection uses validation only and a strict absolute gate.
    eligible=[r for r in rows if r["meets_completion_95pct"] and r["no_abort"]
              and r["validation"]["violations"]==0]
    best=min(eligible,key=lambda r:r["validation"]["goal_penalized"]) if eligible else None
    holdout=evaluate(Proposal("report-only",best["max_missing"],.25),REPORT_ONLY) if best else None
    return {"candidates":rows,"eligible_candidate":best["max_missing"] if best else None,
            "report_only_holdout":holdout,
            "accepted":bool(best and holdout["completion"]>=.95 and holdout["abort"]==0
              and holdout["violations"]==0),
            "interpretation":"No autonomous restart: only outage threshold is explored under fixed strict gates."}

if __name__=="__main__":
    print(json.dumps(experiment(),indent=2,sort_keys=True))
