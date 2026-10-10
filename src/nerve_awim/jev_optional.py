"""Optional TypeSafe Jev research review, no third-party dependency required.

Jev gives *advisory* typed decisions on synthetic aggregate metrics only.
The deterministic NERVE eligibility and recovery gates MUST run separately.
The key is read from TYPESAFE_API_KEY only when a request is made.
No API keys, source texts, patient records, or raw sensor values are sent.
"""
from dataclasses import dataclass
from math import isfinite
from time import perf_counter
from urllib.request import Request, urlopen
import json
import os

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
METRICS = frozenset((
    "completion", "abort", "violations", "goal_penalized",
    "prediction_penalized",
))


class JevUnavailable(RuntimeError):
    """Connection, configuration, or response validation failed."""


@dataclass(frozen=True)
class JevAdvice:
    risk_probability: float
    confidence_available: bool
    model: str
    elapsed_seconds: float
    token_usage: dict


def numeric_summary(metrics):
    """Allowlist only nonsensitive, aggregated, finite benchmark numbers."""
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be a mapping")
    if set(metrics) != METRICS:
        raise ValueError("unexpected metric fields: require fixed aggregates")
    output = {}
    for name in sorted(METRICS):
        number = metrics[name]
        if (isinstance(number, bool)
                or not isinstance(number, (float, int))
                or not isfinite(number)):
            raise ValueError("invalid metric: " + name)
        if number < 0:
            raise ValueError("negative metric: " + name)
        output[name] = float(number)
    if output["completion"] > 1 or output["abort"] > 1:
        raise ValueError("fraction must be 0..1")
    return output


class JevResearchReviewer:
    """Official System One REST client via stdlib HTTPS, opt-in per invocation.

    transport is an optional test seam accepting urllib.request.Request and
    timeout, returning a binary HTTP response/context manager.
    No retries by default: limits and billing should be operator-controlled.
    """

    def __init__(self, *, model="jev-latest", timeout=8.0, transport=None):
        if not isinstance(model, str) or model not in (
            "jev-latest", "jev-preview", "jev-1.13.0"
        ):
            raise ValueError("unsupported Jev model")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) \
                or not isfinite(timeout) or not 0 < timeout <= 30:
            raise ValueError("invalid request timeout")
        self.model = model
        self.timeout = float(timeout)
        self.transport = transport if transport is not None else urlopen

    def review(self, *, baseline, candidate):
        state = {
            "scope": "synthetic research benchmark aggregates only",
            "reference": numeric_summary(baseline),
            "candidate": numeric_summary(candidate),
        }
        # Noul is a risk *opinion*, not an authorisation or factual proof.
        payload = {
            "model": self.model,
            "state": state,
            "questions": {
                "regression_risk": {
                    "type": "noul",
                    "instructions": (
                        "Based only on these aggregate simulation metrics, "
                        "is there evidence the candidate may be worse than "
                        "the reference in completion, aborts, constraint "
                        "violations, goal error or prediction error?"
                    ),
                },
            },
        }
        key = os.environ.get("TYPESAFE_API_KEY", "")
        if not key or len(key.strip()) != len(key) or "\n" in key or "\r" in key:
            raise JevUnavailable("TYPESAFE_API_KEY is not configured")
        body = json.dumps(payload, allow_nan=False, separators=(",", ":")).encode()
        request = Request(
            ENDPOINT,
            data=body,
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        start = perf_counter()
        try:
            with self.transport(request, timeout=self.timeout) as response:
                # Limit response size to prevent accidental excessive buffering.
                raw = response.read(65537)
            if len(raw) > 65536:
                raise JevUnavailable("Jev response too large")
            data = json.loads(raw)
            answer = data["answers"]["regression_risk"]
            value = answer["noul"]
            if answer.get("type") != "noul" or isinstance(value, bool) \
                    or not isinstance(value, (float, int)) \
                    or not isfinite(value) or not 0 <= value <= 1:
                raise JevUnavailable("invalid typed Jev answer")
            model = data["model"]
            if not isinstance(model, str) or not model:
                raise JevUnavailable("invalid Jev model identity")
            usage = data.get("usage", {})
            if not isinstance(usage, dict):
                raise JevUnavailable("invalid Jev usage")
            sanitized = {}
            for field in ("input_tokens", "output_tokens"):
                n = usage.get(field)
                if type(n) is int and 0 <= n <= 10_000_000:
                    sanitized[field] = n
            return JevAdvice(
                risk_probability=float(value),
                confidence_available=False,  # Noul has no confidence field
                model=model,
                elapsed_seconds=perf_counter() - start,
                token_usage=sanitized,
            )
        except JevUnavailable:
            raise
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            # Never interpolate provider error responses or auth data in errors.
            raise JevUnavailable("TypeSafe Jev request failed or returned invalid data") from None


def demo():
    from .autoresearch_v04 import Proposal, evaluate, VALIDATION
    baseline = evaluate(Proposal("baseline", 5, .25), VALIDATION)
    alternative = evaluate(Proposal("longer-outage", 8, .25), VALIDATION)
    advice = JevResearchReviewer().review(baseline=baseline, candidate=alternative)
    # Print only approved aggregate advice, no keys or request body.
    return {
        "model": advice.model,
        "regression_risk": advice.risk_probability,
        "elapsed_seconds": round(advice.elapsed_seconds, 4),
        "usage": advice.token_usage,
        "deterministic_gates_still_required": True,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(demo(), indent=2))
    except JevUnavailable as exc:
        print("Jev smoke test unavailable: " + str(exc))
        raise SystemExit(2) from None
