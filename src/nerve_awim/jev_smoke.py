"""One-shot *local* Jev connectivity test with synthetic benchmark aggregates.

Run in the terminal holding TYPESAFE_API_KEY:
    PYTHONPATH=src python -m nerve_awim.jev_smoke

Makes one external TypeSafe request. Never prints or persists the key, raw
HTTP responses, personal data, or any input beyond fixed synthetic numbers.
"""
import json
import os

from .jev_batch import JevBatchReviewer
from .jev_optional import JevUnavailable

REFERENCE = {
    "completion": 0.82,
    "abort": 0.12,
    "violations": 0.0,
    "goal_penalized": 1.20,
    "prediction_penalized": 0.85,
}
CANDIDATES = {
    "case_a": {
        "completion": 0.87, "abort": 0.09, "violations": 0.0,
        "goal_penalized": 1.05, "prediction_penalized": 0.80,
    },
    "case_b": {
        "completion": 0.65, "abort": 0.22, "violations": 1.0,
        "goal_penalized": 0.95, "prediction_penalized": 0.90,
    },
}


def run_smoke(reviewer=None):
    """Return only validated, nonsensitive summary fields."""
    engine = reviewer if reviewer is not None else JevBatchReviewer(timeout=8)
    outputs = engine.review_many(baseline=REFERENCE, candidates=CANDIDATES)
    if set(outputs) != set(CANDIDATES):
        raise JevUnavailable("incomplete Jev smoke test response")
    return {
        "connected": True,
        "model": outputs["case_a"].model,
        "batched_questions": len(outputs),
        "regression_risks": {
            name: round(outputs[name].risk_probability, 6)
            for name in sorted(outputs)
        },
        "request_elapsed_seconds": round(outputs["case_a"].elapsed_seconds, 4),
        "token_usage": outputs["case_a"].token_usage,
        "warning": "Advisory judgment on synthetic aggregates only.",
    }


def main():
    if not os.environ.get("TYPESAFE_API_KEY"):
        print("No TYPESAFE_API_KEY in this terminal. No request sent.")
        return 2
    try:
        result = run_smoke()
    except JevUnavailable as exc:
        # Exception text is sanitized by the API adapter.
        print("Jev connection test failed:", str(exc))
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
