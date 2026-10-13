"""NERVE v1.9 second track: bounded recursive WorldCore research experiments.

Mutates only trusted typed simulation parameters. WorldCore's evaluator,
plant, fixed validation/holdout seeds and absolute eligibility gates are
not influenced by any candidate. No auto code changes or controller deploy.
"""
from copy import deepcopy
from math import isfinite
from random import Random

from .autoresearch_v04 import Proposal, VALIDATION, REPORT_ONLY, evaluate
from .autoresearch_v05 import eligibility
from .parallel_agents_v11 import AgentJob, BoundedParallelAgents


class WorldCoreResearchEvolution:
    def __init__(self, *, generations=3, offspring=3, seed=25,
                 evaluator=evaluate, validation_seeds=VALIDATION,
                 holdout_seeds=REPORT_ONLY, on_selection=None):
        if type(generations) is not int or not 1 <= generations <= 5:
            raise ValueError("bounded number of generations required")
        if type(offspring) is not int or not 1 <= offspring <= 5:
            raise ValueError("bounded offspring required")
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError("reproducible integer seed required")
        if not callable(evaluator):
            raise ValueError("trusted simulation evaluator required")
        for seeds in (validation_seeds, holdout_seeds):
            if (type(seeds) is not tuple or not 1 <= len(seeds) <= 64
                    or any(type(s) is not int or not 0 <= s < 2**32 for s in seeds)
                    or len(set(seeds)) != len(seeds)):
                raise ValueError("bounded unique integer seed tuples required")
        if set(validation_seeds) & set(holdout_seeds):
            raise ValueError("validation and holdout must be disjoint")
        if on_selection is not None and not callable(on_selection):
            raise ValueError("trusted selection hook required")
        self.validation_seeds = validation_seeds
        self.holdout_seeds = holdout_seeds
        self.on_selection = on_selection
        self.generations = generations
        self.offspring = offspring
        self.seed = seed
        self.evaluator = evaluator
        self.workers = BoundedParallelAgents(
            {"simulate": self._score}, max_workers=4, max_jobs=16,
        )

    def _score(self, proposal):
        if type(proposal) is not Proposal:
            raise TypeError("only typed simulation candidates are allowed")
        return self.evaluator(proposal, self.validation_seeds)

    @staticmethod
    def mutation(parent, randomizer, name):
        delta_max, delta_risk = randomizer.choice((
            (1, 0.0), (2, 0.0), (-1, 0.0),
            (0, .05), (0, -.05), (0, .2), (0, -.2),
            (1, .05), (-1, -.05),
        ))
        return Proposal(
            name,
            max(2, min(12, parent.max_missing + delta_max)),
            round(max(0., min(2., parent.risk_aversion + delta_risk)), 3),
        )

    @staticmethod
    def _metrics_ok(metrics):
        return type(metrics) is dict and set(metrics) == {
            "completion", "abort", "violations",
            "goal_penalized", "prediction_penalized",
        } and all(
            type(v) in (int, float) and isfinite(v) and v >= 0
            for v in metrics.values()
        ) and metrics["completion"] <= 1 and metrics["abort"] <= 1

    @classmethod
    def _nonregression(cls, candidate, parent):
        if not cls._metrics_ok(candidate) or not cls._metrics_ok(parent):
            raise ValueError("invalid frozen evaluator metrics")
        return (
            candidate["completion"] >= parent["completion"] - 1e-12
            and candidate["abort"] <= parent["abort"] + 1e-12
            and candidate["violations"] <= parent["violations"] + 1e-12
            and candidate["prediction_penalized"] <=
                parent["prediction_penalized"] + 1e-12
        )

    def run(self):
        rng = Random(self.seed)
        best = Proposal("baseline", 5, .25)
        baseline = self._score(best)
        if not self._metrics_ok(baseline):
            raise ValueError("unsafe baseline result from evaluator")
        best_metrics = baseline
        seen = {(best.max_missing, best.risk_aversion)}
        generations = []
        for generation in range(1, self.generations + 1):
            proposals = []
            for trial in range(self.offspring * 8):
                candidate = self.mutation(
                    best, rng, "g" + str(generation) + "-" + str(trial))
                if type(candidate) is not Proposal:
                    raise TypeError("mutation must return a typed WorldCore proposal")
                key = (candidate.max_missing, candidate.risk_aversion)
                if key in seen:
                    continue
                seen.add(key)
                proposals.append(candidate)
                if len(proposals) >= self.offspring:
                    break
            if not proposals:
                break
            metrics = self.workers.run([
                AgentJob(p.name, "simulate", p) for p in proposals
            ])
            eligible = []
            rows = []
            for proposal, measured in zip(proposals, metrics):
                value = measured.output
                if not self._metrics_ok(value):
                    raise ValueError("invalid candidate evaluator output")
                absolute = eligibility(value)
                nonregression = self._nonregression(value, best_metrics)
                better = value["goal_penalized"] < (
                    best_metrics["goal_penalized"] - 1e-5
                )
                allowed = absolute.eligible and nonregression and better
                rows.append({
                    "genome": {
                        "max_missing": proposal.max_missing,
                        "risk_aversion": proposal.risk_aversion,
                    },
                    "validation": value,
                    "absolute_eligible": absolute.eligible,
                    "rejection_reasons": list(absolute.reasons),
                    "no_regression": nonregression,
                    "strict_goal_improvement": better,
                    "candidate_for_research": allowed,
                })
                if allowed:
                    eligible.append((value["goal_penalized"],
                                     proposal, value))
            if eligible:
                _, best, best_metrics = min(
                    eligible, key=lambda x: (x[0], x[1].max_missing,
                                             x[1].risk_aversion)
                )
            generations.append({
                "generation": generation, "candidates": rows,
                "selected": (
                    {"max_missing": best.max_missing,
                     "risk_aversion": best.risk_aversion}
                    if eligible else None
                ),
            })

        # Independent report-only holdout, never sampled by the mutation
        # operator or used to pick candidate generations.
        if self.on_selection is not None:
            self.on_selection(deepcopy({
                "selected_recipe": {"max_missing": best.max_missing,
                                    "risk_aversion": best.risk_aversion},
                "selected_validation": best_metrics, "lineage": generations,
            }))
        base_holdout = self.evaluator(
            Proposal("baseline-report-only", 5, .25), self.holdout_seeds)
        chosen_holdout = self.evaluator(
            Proposal("candidate-report-only", best.max_missing,
                     best.risk_aversion), self.holdout_seeds)
        if not self._metrics_ok(base_holdout) or not self._metrics_ok(chosen_holdout):
            raise ValueError("invalid holdout metrics")
        absolute_holdout = eligibility(chosen_holdout)
        holdout_gain = (chosen_holdout["goal_penalized"]
                        < base_holdout["goal_penalized"] - 1e-5)
        holdout_pass = (holdout_gain and absolute_holdout.eligible
                        and self._nonregression(chosen_holdout, base_holdout))
        improved = (best.max_missing, best.risk_aversion) != (5, .25)
        return {
            "study_protocol": "nerve-worldcore-recursive-v19",
            "status": ("candidate_for_human_review"
                       if improved and holdout_pass
                       else "no_deployable_improvement"),
            "baseline_validation": baseline,
            "selected_validation": best_metrics,
            "selected_recipe": {
                "max_missing": best.max_missing,
                "risk_aversion": best.risk_aversion,
            },
            "baseline_holdout": base_holdout,
            "report_only_holdout": chosen_holdout,
            "holdout_strict_goal_improvement": holdout_gain,
            "holdout_absolute_eligible": absolute_holdout.eligible,
            "holdout_rejection_reasons": list(absolute_holdout.reasons),
            "generations_run": len(generations),
            "candidate_count": len(seen) - 1,
            "lineage": generations,
            "scope": "Synthetic WorldCore parameter experiments only. No source patches, actuation, auto-merge or deployment.",
        }


if __name__ == "__main__":
    import json
    print(json.dumps(WorldCoreResearchEvolution().run(),
                     indent=2, sort_keys=True))
