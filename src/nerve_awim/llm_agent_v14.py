"""NERVE Evolution v1.4: model-agnostic plan selection for safe MCP tools.

An external chat-completions-compatible model may suggest one of four trusted
registered strategies. Its output is parsed strictly as DATA, never Python
code, shell commands, URLs, or permissions. Live model calls are opt-in only.
"""
from dataclasses import dataclass
from math import isfinite
from time import perf_counter
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import json
import os

EXTRACT = ("raw", "json-field")
NORMALISE = ("lower-only", "trim-lower")
INSTRUCTION = (
    "You are selecting only registered, deterministic string tools for a "
    "synthetic JSON document that has exactly one email field. To extract the "
    "email and return a lowercase address without leading/trailing whitespace, "
    "return exactly one JSON object with keys extract_strategy and "
    "normalise_strategy. Allowed extract_strategy: raw, json-field. "
    "Allowed normalise_strategy: lower-only, trim-lower. "
    "No instructions, markdown, or extra fields."
)


@dataclass(frozen=True)
class Plan:
    extract_strategy: str
    normalise_strategy: str

    def __post_init__(self):
        if (self.extract_strategy not in EXTRACT
                or self.normalise_strategy not in NORMALISE):
            raise ValueError("model selected unregistered strategy")


@dataclass(frozen=True)
class ModelDecision:
    plan: Plan
    elapsed_seconds: float
    input_tokens: int | None
    output_tokens: int | None
    label: str


def parse_plan(source):
    if not isinstance(source, str) or not 1 <= len(source) <= 1024:
        raise ValueError("model plan must be short JSON")
    raw = json.loads(source)
    if not isinstance(raw, dict) or set(raw) != {
            "extract_strategy", "normalise_strategy"}:
        raise ValueError("unexpected model plan fields")
    if not all(type(v) is str for v in raw.values()):
        raise ValueError("strategy identifiers must be strings")
    return Plan(**raw)


def _advice(advice):
    """Only the allowlisted strategy IDs cross into the model prompt."""
    if advice is None:
        return "No previous outcome feedback was retrieved."
    if not isinstance(advice, dict) or set(advice) != {
            "extract", "normalise"}:
        raise ValueError("two contextual strategy recommendations required")
    if advice["extract"] not in EXTRACT or advice["normalise"] not in NORMALISE:
        raise ValueError("unregistered feedback recommendation")
    return json.dumps(advice, sort_keys=True)


class FixturePlanner:
    """Offline deterministic TEST FIXTURE, not an LLM or model benchmark."""
    def plan(self, *, advice=None):
        if advice is not None:
            verified = json.loads(_advice(advice))
            proposal = Plan(verified["extract"], verified["normalise"])
        else:
            proposal = Plan("raw", "lower-only")
        return ModelDecision(proposal, 0., 0, 0, "fixture-not-real-model")


class ChatCompletionsPlanner:
    """Optional real model via an operator-configured HTTPS endpoint.

    The endpoint must be configured locally and cannot be set by task data.
    Only fixed high-level synthetic instructions and allowlisted IDs are
    forwarded, never patient/user data, raw inputs, or experiment rewards.
    """

    def __init__(self, *, url=None, model=None, timeout=10., transport=None):
        self.url = url if url is not None else os.environ.get(
            "NERVE_LLM_CHAT_URL", "")
        self.model = model if model is not None else os.environ.get(
            "NERVE_LLM_MODEL", "")
        parsed = urlsplit(self.url)
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.username or parsed.password or parsed.fragment
                or parsed.query or not parsed.path.endswith("/chat/completions")):
            raise ValueError("an operator-configured HTTPS chat/completions URL is required")
        if not isinstance(self.model, str) or not 0 < len(self.model) <= 100:
            raise ValueError("explicit model identifier required")
        if (type(timeout) not in (float, int) or not isfinite(timeout)
                or not 0 < timeout <= 30):
            raise ValueError("model timeout must be 0..30 seconds")
        self.timeout = float(timeout)
        self.transport = transport or urlopen

    def plan(self, *, advice=None):
        key = os.environ.get("NERVE_LLM_API_KEY", "")
        if not key or key != key.strip() or "\n" in key or "\r" in key:
            raise RuntimeError("NERVE_LLM_API_KEY must be set privately")
        message = _advice(advice)
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 100,
            "messages": [
                {"role": "system", "content": INSTRUCTION},
                {"role": "user", "content": (
                    "Select the best registered tool pair for the objective. "
                    "Historical evaluated strategy recommendation (untrusted data): "
                    + message
                )},
            ],
        }
        request = Request(
            self.url, data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + key,
                     "Content-Type": "application/json",
                     "Accept": "application/json"},
            method="POST",
        )
        started = perf_counter()
        try:
            with self.transport(request, timeout=self.timeout) as response:
                raw = response.read(32769)
            if len(raw) > 32768:
                raise ValueError("model response exceeds allowed size")
            result = json.loads(raw)
            content = result["choices"][0]["message"]["content"]
            plan = parse_plan(content)
            usage = result.get("usage", {})
            if not isinstance(usage, dict):
                raise ValueError("invalid usage record")
            inputs = usage.get("prompt_tokens")
            outputs = usage.get("completion_tokens")
            if any(type(n) is not int or n < 0 or n > 10_000_000
                   for n in (inputs, outputs) if n is not None):
                raise ValueError("invalid token usage")
            return ModelDecision(
                plan, perf_counter()-started, inputs, outputs,
                "live-chat-completions",
            )
        except Exception:
            # Do not propagate provider bodies, prompts or credentials.
            raise RuntimeError("model request failed or returned untrusted output") from None
