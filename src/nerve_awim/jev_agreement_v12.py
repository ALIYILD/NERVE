"""Controlled Jev-versus-deterministic review benchmark (advisory only).

Six fixed synthetic cases, no patient data, credentials, source-code
execution, or automatic production authorisation. Offline mode uses a
labelled fixture reviewer to TEST agreement calculations, not to claim
real Jev model accuracy. Live mode is explicit opt-in.
"""
from dataclasses import dataclass
from math import isfinite
from time import perf_counter
import argparse
import json

from .autoresearch_v05 import eligibility
from .evolution_cycle_v11 import ParallelEvolutionCycle
from .jev_batch import JevBatchReviewer
from .jev_optional import JevAdvice, JevUnavailable, numeric_summary

BASELINE = {
    "completion": .96, "abort": 0., "violations": 0.,
    "goal_penalized": 1.0, "prediction_penalized": 1.0,
}
# Fully aggregate, constructed metrics. No free-form identifiers leave the
# machine; JevBatchReviewer sends only these numeric values in fixed order.
CASES = {
    "safer_goal": dict(completion=.98, abort=0., violations=0.,
                       goal_penalized=.80, prediction_penalized=.85),
    "no_change": dict(BASELINE),
    "lower_completion": dict(completion=.91, abort=0., violations=0.,
                             goal_penalized=.75, prediction_penalized=.80),
    "unexpected_abort": dict(completion=.96, abort=.1, violations=0.,
                             goal_penalized=.75, prediction_penalized=.80),
    "constraint_violation": dict(completion=.98, abort=0., violations=1.,
                                 goal_penalized=.65, prediction_penalized=.80),
    "prediction_regression": dict(completion=.98, abort=0., violations=0.,
                                  goal_penalized=.80, prediction_penalized=1.25),
}

def deterministic_assessment(candidate):
    reference = numeric_summary(BASELINE)
    metrics = numeric_summary(candidate)
    review = ParallelEvolutionCycle._review((metrics, reference))
    absolute = eligibility(metrics)
    # Primary agreement target: detection of metric regressions.
    deterioration = any((
        metrics["completion"] < reference["completion"],
        metrics["abort"] > reference["abort"],
        metrics["violations"] > reference["violations"],
        metrics["goal_penalized"] > reference["goal_penalized"],
        metrics["prediction_penalized"] > reference["prediction_penalized"],
    ))
    return {
        "regression_present": deterioration,
        "candidate_for_review": (
            absolute.eligible and review["no_regression"]
            and review["goal_improved"]
        ),
        "reasons": list(absolute.reasons),
    }

class SyntheticFixtureReviewer:
    """Test double, NOT Jev: intentional errors exercise confusion counts."""
    def review_many(self, *, baseline, candidates):
        if baseline != BASELINE:
            raise ValueError("fixture requires fixed baseline")
        result = {}
        for name in sorted(candidates):
            # Two illustrative misclassifications: both demonstrate that
            # third-party opinions cannot become independent safety facts.
            risk = {
                "safer_goal": .10, "no_change": .75,
                "lower_completion": .85, "unexpected_abort": .90,
                "constraint_violation": .15,
                "prediction_regression": .80,
            }[name]
            result[name] = JevAdvice(
                risk, False, "synthetic-fixture-not-jev",
                0., {"input_tokens": 0, "output_tokens": 0},
            )
        return result

def compare(reviewer):
    starting = perf_counter()
    decisions = {name: deterministic_assessment(metrics)
                 for name, metrics in CASES.items()}
    deterministic_seconds = perf_counter() - starting
    # Exactly one request when reviewer is a real JevBatchReviewer.
    predictions = reviewer.review_many(baseline=BASELINE, candidates=CASES)
    if not isinstance(predictions, dict) or set(predictions) != set(CASES):
        raise ValueError("incomplete advisory results")
    counters = {"true_positive": 0, "false_positive": 0,
                "true_negative": 0, "false_negative": 0}
    detail = []
    for name in sorted(CASES):
        decision = decisions[name]
        advice = predictions[name]
        risk = advice.risk_probability
        if (isinstance(risk,bool) or not isinstance(risk,(float,int))
                or not isfinite(risk) or not 0 <= risk <= 1):
            raise ValueError("invalid advisory regression risk")
        predicted = risk >= .5
        actual = decision["regression_present"]
        label = ("true_positive" if predicted and actual else
                 "false_positive" if predicted else
                 "false_negative" if actual else "true_negative")
        counters[label] += 1
        detail.append({
            "case": name, "deterministic_regression": actual,
            "model_risk": round(risk,6), "predicted_regression": predicted,
            "candidate_for_human_review": decision["candidate_for_review"],
            "match": predicted == actual,
        })
    first = predictions[sorted(CASES)[0]]
    return {
        "reviewer": first.model,
        "comparison_cases": len(CASES),
        "agreement_fraction": (
            counters["true_positive"] + counters["true_negative"]
        ) / len(CASES),
        "confusion": counters,
        "deterministic_wall_seconds": round(deterministic_seconds, 6),
        "model_request_elapsed_seconds": first.elapsed_seconds,
        "provider_tokens": first.token_usage,
        "cases": detail,
        "guardrail": "Jev results never change independent acceptance decisions.",
        "limitations": "Constructed cases. The fixture is NOT evidence of Jev accuracy or speed; live observations require a separate authenticated run.",
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description="NERVE Jev agreement test")
    parser.add_argument("--live", action="store_true",
                        help="one live batched TypeSafe request; requires a NEW private key")
    args = parser.parse_args(argv)
    reviewer = JevBatchReviewer(timeout=8) if args.live else SyntheticFixtureReviewer()
    try:
        result = compare(reviewer)
    except (JevUnavailable, ValueError):
        print("Jev comparison unavailable or validation failed.")
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
