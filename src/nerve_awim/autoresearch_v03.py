"""Research portfolio gate for existing NERVE synthetic benchmarks.

This does not execute generated code, change live agents, or unlock holdout
data. Validation compares reproducible, existing benchmark implementations.
"""
from dataclasses import dataclass
from pathlib import Path
import json, math
from benchmarks.v31_ablation import episode as memory_episode
from benchmarks.v32_multimodal import episode as sensory_episode
from benchmarks.v33_nonlinear import episode as nonlinear_episode

SUITES = (
    ("memory", memory_episode, "single_memory", "specialist_memory"),
    ("sensory", sensory_episode, "single_fused", "specialist_fused"),
    ("nonlinear", nonlinear_episode, "unified", "specialists"),
)
VALIDATION_SEEDS = tuple(range(20, 30))
REPORT_SEEDS = tuple(range(300, 310))

@dataclass(frozen=True)
class ResearchProposal:
    proposal_id: str
    architecture: str
    def __post_init__(self):
        if not self.proposal_id or len(self.proposal_id) > 64:
            raise ValueError("invalid proposal ID")
        if self.architecture not in ("unified", "specialist"):
            raise ValueError("architecture not allowlisted")

def evaluate(proposal, seeds):
    results = {}
    for name, episode, unified_key, specialist_key in SUITES:
        metric = unified_key if proposal.architecture == "unified" else specialist_key
        values = [episode(s)[metric] for s in seeds]
        if not values or not all(math.isfinite(v) and v >= 0 for v in values):
            raise ValueError("invalid evaluation")
        results[name] = sum(values) / len(values)
    return results

def experiment(proposals, ledger_path=None, max_trials=4, tolerance=1e-9):
    proposals = tuple(proposals)
    if not 1 <= len(proposals) <= max_trials or len({p.proposal_id for p in proposals}) != len(proposals):
        raise ValueError("invalid proposal count or duplicate ID")
    reference = ResearchProposal("reference", "unified")
    original = evaluate(reference, VALIDATION_SEEDS)
    best, best_metrics = reference, original
    trials = []
    for proposal in proposals:
        metrics = evaluate(proposal, VALIDATION_SEEDS)
        # Every benchmark must be at least as good: do not bury regressions
        # inside a favourable aggregate score.
        no_regression = all(metrics[k] <= best_metrics[k] + tolerance for k in original)
        improvement = any(metrics[k] < best_metrics[k] - tolerance for k in original)
        accepted = no_regression and improvement
        trials.append({"proposal_id": proposal.proposal_id, "architecture": proposal.architecture,
                       "validation": metrics, "decision": "keep" if accepted else "reject"})
        if accepted:
            best, best_metrics = proposal, metrics
    result = {"reference": original, "trials": trials,
              "selected": best.architecture, "selected_validation": best_metrics,
              "report_only_holdout": {"reference": evaluate(reference, REPORT_SEEDS),
                                      "selected": evaluate(best, REPORT_SEEDS)},
              "limitations": "Existing synthetic benchmarks; no compute parity proof, real WorldCore control, or agent network execution."}
    if ledger_path is not None:
        path = Path(ledger_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, sort_keys=True) + "\n")
    return result

def demo():
    return experiment([ResearchProposal("specialist-network", "specialist"),
                       ResearchProposal("single-learner", "unified")])

if __name__ == "__main__":
    print(json.dumps(demo(), indent=2, sort_keys=True))
