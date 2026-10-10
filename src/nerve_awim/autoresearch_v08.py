"""v0.8 aggregate research gate: evidence, reliability and execution budgets.

Benchmark-only. Never promotes candidate changes or approves hardware operation.
"""
from dataclasses import dataclass
from time import perf_counter
import json
from .autoresearch_v05 import experiment as controller_experiment
from .autoresearch_v04 import Proposal
from benchmarks.v06_recovery_research import benchmark as recovery_benchmark

@dataclass(frozen=True)
class ReviewThresholds:
    max_wall_seconds:float=15.0

def evaluate(thresholds=ReviewThresholds()):
    start=perf_counter()
    control=controller_experiment([Proposal("long-outage",8,.25)])
    recovery=recovery_benchmark()
    elapsed=perf_counter()-start
    checks={
      "controller_absolute_eligibility":control["eligible_for_deployment_review"],
      "simulated_recovery_transitions":recovery["passed"],
      "runtime_budget":elapsed<=thresholds.max_wall_seconds}
    return {"checks":checks,"all_checks_pass":all(checks.values()),
      "elapsed_seconds":elapsed,"controller_rejection_reasons":control["holdout_rejection_reasons"],
      "scope":"Research-only. No production promotion or safety certification."}
if __name__=="__main__":
    report=evaluate()
    print(json.dumps(report,indent=2,sort_keys=True))
    # Failure of eligibility is an expected research finding, not a CI crash.
