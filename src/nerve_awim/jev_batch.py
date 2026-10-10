"""Batched Jev critiques for parallel NERVE research candidates.

One TypeSafe System One HTTPS request carries independent Noul questions,
avoiding a separate network round-trip for every candidate. No safety gate
depends on these advisory model probabilities.
"""
from math import isfinite
from time import perf_counter
from urllib.request import Request
import json
import os

from .jev_optional import (
    ENDPOINT, JevAdvice, JevResearchReviewer, JevUnavailable, numeric_summary
)


class JevBatchReviewer(JevResearchReviewer):
    def review_many(self, *, baseline, candidates):
        if not isinstance(candidates, dict) or not 1 <= len(candidates) <= 6:
            raise ValueError("one to six bounded candidates required")
        if not all(isinstance(key, str) and 0 < len(key) <= 48
                   for key in candidates):
            raise ValueError("invalid candidate identifiers")
        names = sorted(candidates)
        state = {
            "scope": "synthetic WorldCore benchmark aggregates only",
            "baseline": numeric_summary(baseline),
            # Candidate identifiers remain local: no user-provided free text.
            "candidates": [numeric_summary(candidates[key]) for key in names],
        }
        questions = {
            "q" + str(index): {
                "type": "noul",
                "instructions": (
                    "Compared to state.baseline, does state.candidates["
                    + str(index)
                    + "] indicate any possible regression in completion, "
                    "aborts, constraint violations, prediction or goal error?"
                ),
            } for index in range(len(names))
        }
        key = os.environ.get("TYPESAFE_API_KEY", "")
        if not key or key != key.strip() or "\n" in key or "\r" in key:
            raise JevUnavailable("TYPESAFE_API_KEY is not configured")
        data = json.dumps(
            {"model": self.model, "state": state, "questions": questions},
            allow_nan=False, separators=(",", ":"),
        ).encode()
        request = Request(ENDPOINT, data=data, method="POST", headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        start = perf_counter()
        try:
            with self.transport(request, timeout=self.timeout) as response:
                raw = response.read(65537)
            if len(raw) > 65536:
                raise JevUnavailable("Jev response too large")
            message = json.loads(raw)
            model = message["model"]
            answers = message["answers"]
            if not isinstance(model, str) or not model \
                    or not isinstance(answers, dict):
                raise JevUnavailable("invalid Jev answer metadata")
            if set(answers) != set(questions):
                raise JevUnavailable("Jev did not answer all questions")
            usage = message.get("usage", {})
            if not isinstance(usage, dict):
                raise JevUnavailable("invalid Jev usage")
            sanitized = {
                field: usage[field]
                for field in ("input_tokens", "output_tokens")
                if type(usage.get(field)) is int
                and 0 <= usage[field] <= 10_000_000
            }
            duration = perf_counter() - start
            output = {}
            for index, name in enumerate(names):
                answer = answers["q" + str(index)]
                value = answer["noul"]
                if answer.get("type") != "noul" or type(value) not in (int, float) \
                        or not isfinite(value) or not 0 <= value <= 1:
                    raise JevUnavailable("invalid typed Jev answer")
                output[name] = JevAdvice(
                    float(value), False, model, duration, sanitized
                )
            return output
        except JevUnavailable:
            raise
        except (OSError, ValueError, TypeError, KeyError):
            raise JevUnavailable("TypeSafe Jev batch request failed or returned invalid data") from None
