"""NERVE parallel Evolution Cycle: research, memory, benchmark, safety, review.

This is a deterministic in-process subagent orchestration demonstration, not
Hermes/LLM execution or a production control plane. Candidate hints can
prioritise experiment order; they NEVER override objective safety gates.
"""
from dataclasses import asdict
import json
from pathlib import Path

from .parallel_agents_v11 import AgentJob, BoundedParallelAgents
from .evolution_v01 import EvolutionMemory
from .autoresearch_v04 import Proposal, VALIDATION, REPORT_ONLY, evaluate
from .autoresearch_v05 import eligibility


class ParallelEvolutionCycle:
    def __init__(self, *, memory: EvolutionMemory, agent_id: str,
                 max_workers: int = 4, ledger_path=None,
                 learn_from_evaluations: bool = False,
                 jev_reviewer=None):
        if not agent_id or not isinstance(agent_id, str):
            raise ValueError("research agent identity required")
        if not isinstance(learn_from_evaluations, bool):
            raise ValueError("learning switch must be explicit boolean")
        self.memory = memory
        self.learn_from_evaluations = learn_from_evaluations
        self.agent_id = agent_id
        self.jev_reviewer = jev_reviewer
        self.ledger_path = Path(ledger_path) if ledger_path is not None else None
        self.workers = BoundedParallelAgents({
            "research": self._research,
            "memory": self._remember,
            "evaluate": self._evaluate,
            "review": self._review,
            "safety": eligibility,
            **({"jev": self._jev_review} if jev_reviewer is not None else {}),
        }, max_workers=max_workers)

    def _jev_review(self, payload):
        reference, candidate = payload
        return self.jev_reviewer.review(baseline=reference, candidate=candidate)

    def _research(self, proposals):
        candidates = tuple(proposals)
        if not 1 <= len(candidates) <= 6:
            raise ValueError("candidate budget exceeded")
        if not all(isinstance(p, Proposal) for p in candidates):
            raise TypeError("only typed candidate configurations allowed")
        if len({p.name for p in candidates}) != len(candidates):
            raise ValueError("duplicate candidates")
        if "baseline" in {p.name for p in candidates}:
            raise ValueError("baseline is reserved")
        return candidates

    def _remember(self, context):
        return self.memory.select(self.agent_id, context, limit=6)

    @staticmethod
    def _evaluate(proposal):
        return evaluate(proposal, VALIDATION)

    @staticmethod
    def _review(payload):
        candidate, reference = payload
        allowed = (
            candidate["abort"] <= reference["abort"] + 1e-12
            and candidate["violations"] <= reference["violations"] + 1e-12
            and candidate["completion"] >= reference["completion"] - 1e-12
            and candidate["prediction_penalized"] <=
                reference["prediction_penalized"] + 1e-12
        )
        improvement = (candidate["goal_penalized"] <
                       reference["goal_penalized"] - 1e-5)
        return {"no_regression": allowed, "goal_improved": improvement}

    def run(self, proposals, *, context: str):
        if not isinstance(context, str) or not 0 < len(context) <= 256:
            raise ValueError("valid context required")
        # Different specialist subagents genuinely execute concurrently.
        research, memory = self.workers.run([
            AgentJob("hypothesis", "research", tuple(proposals)),
            AgentJob("experience", "memory", context),
        ])
        candidates = research.output
        ratings = {item.outcome: item.utility for item in memory.output}
        # Memory is advisory: it may prioritise work, not choose a winner.
        prioritised = sorted(candidates,
                             key=lambda p: (-ratings.get(p.name, .5), p.name))
        baseline = Proposal("baseline", 5, .25)
        evaluated = self.workers.run([
            AgentJob("baseline", "evaluate", baseline),
            *[AgentJob(p.name, "evaluate", p) for p in prioritised],
        ])
        measurements = {result.job_id: result.output for result in evaluated}
        policy_jobs = []
        for proposal in prioritised:
            policy_jobs.append(AgentJob("safety:" + proposal.name, "safety",
                                        measurements[proposal.name]))
            policy_jobs.append(AgentJob("review:" + proposal.name, "review",
                                        (measurements[proposal.name],
                                         measurements["baseline"])))
        policy_results = {out.job_id: out.output
                          for out in self.workers.run(policy_jobs)}
        # Optional external Jev critique, sent only after objective metrics
        # exist. Always advisory; provider failures reject the whole batch.
        jev_reviews = {}
        if self.jev_reviewer is not None:
            if callable(getattr(self.jev_reviewer, "review_many", None)):
                # The TypeSafe client can evaluate independent typed questions
                # in one API call. Only numeric synthetic summaries are sent.
                batch = self.jev_reviewer.review_many(
                    baseline=measurements["baseline"],
                    candidates={p.name: measurements[p.name] for p in prioritised}
                )
                if set(batch) != {p.name for p in prioritised}:
                    raise RuntimeError("Jev batch omitted candidate results")
                jev_reviews = {"jev:" + name: review
                               for name, review in batch.items()}
            else:
                responses = self.workers.run([
                    AgentJob("jev:" + p.name, "jev",
                             (measurements["baseline"], measurements[p.name]))
                    for p in prioritised
                ])
                jev_reviews = {result.job_id: result.output
                               for result in responses}
        trials = []
        eligible = []
        for proposal in prioritised:
            score = measurements[proposal.name]
            gate = policy_results["safety:" + proposal.name]
            review = policy_results["review:" + proposal.name]
            accepted = gate.eligible and all(review.values())
            trials.append({
                "candidate": asdict(proposal),
                "validation": score,
                "research_review": review,
                "absolute_eligibility": gate.eligible,
                "rejection_reasons": list(gate.reasons),
                "decision": "candidate_for_review" if accepted else "reject",
                "jev_advice": ({
                    "regression_risk": jev_reviews["jev:" + proposal.name].risk_probability,
                    "model": jev_reviews["jev:" + proposal.name].model,
                    "elapsed_seconds": jev_reviews["jev:" + proposal.name].elapsed_seconds,
                    "usage": jev_reviews["jev:" + proposal.name].token_usage,
                } if self.jev_reviewer is not None else None),
            })
            if accepted:
                eligible.append((score["goal_penalized"], proposal.name,
                                 proposal))
        chosen = min(eligible)[2] if eligible else None
        # Holdout is reported only when validation independently qualifies;
        # it does not influence candidate selection.
        holdout = evaluate(chosen, REPORT_ONLY) if chosen else None
        report = {
            "status": "candidate_for_human_review" if chosen is not None
                      and eligibility(holdout).eligible else "rejected",
            "selected": asdict(chosen) if chosen else None,
            "baseline_validation": measurements["baseline"],
            "trials": trials,
            "memory_advice_count": len(memory.output),
            "parallel_worker_limit": self.workers.max_workers,
            "optional_jev_review_enabled": self.jev_reviewer is not None,
            "holdout_report_only": holdout,
            "scope": "Synthetic experiments. No deployment or policy changes.",
        }
        # Deterministic, bounded research feedback may influence experiment
        # PRIORITY on later runs; it never changes the independent evaluator.
        # Failed candidates are scored zero. Unknown candidates are neutral.
        if self.learn_from_evaluations:
            for trial in trials:
                self.memory.record(
                    self.agent_id, context, trial["candidate"]["name"],
                    1.0 if trial["decision"] == "candidate_for_review" else 0.0,
                )
        report["research_feedback_recorded"] = len(trials) if self.learn_from_evaluations else 0
        if self.ledger_path is not None:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with self.ledger_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(report, sort_keys=True) + "\n")
        return report
