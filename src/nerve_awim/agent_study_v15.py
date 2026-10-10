"""NERVE v1.5 context-aware strategy planning, without untrusted code execution.

Experience is from a separate synthetic training split, stored locally with
the context. A planner sees only an allowlisted format label and registered
strategy IDs; it never receives raw test cases or answer keys over the API.
"""
from dataclasses import dataclass
from math import isfinite
from time import perf_counter
from urllib.request import Request
import json
import os

from .llm_agent_v14 import (
    ChatCompletionsPlanner, ModelDecision, Plan, parse_plan,
)
from .evolution_v01 import EvolutionMemory

FORMATS = ("json_email", "plain_email")
PLANS = {
    "json_email": Plan("json-field", "trim-lower"),
    "plain_email": Plan("raw", "trim-lower"),
}
ALLOWED = {
    (extract, normalise)
    for extract in ("raw", "json-field")
    for normalise in ("lower-only", "trim-lower")
}


def _format(value):
    if type(value) is not str or value not in FORMATS:
        raise ValueError("unregistered task format")
    return value


def _plan_id(plan):
    if not isinstance(plan, Plan):
        raise ValueError("typed registered plan required")
    return plan.extract_strategy + "|" + plan.normalise_strategy


def _plan_from_id(text):
    if type(text) is not str or len(text) > 40:
        raise ValueError("invalid stored plan")
    parts = text.split("|")
    if len(parts) != 2 or tuple(parts) not in ALLOWED:
        raise ValueError("unregistered stored plan")
    return Plan(*parts)


class FormatExperience:
    """Context-scoped training-only feedback; no held-out writes."""

    def __init__(self, memory, agent_id="v15-agent"):
        if not isinstance(memory, EvolutionMemory):
            raise TypeError("EvolutionMemory required")
        if type(agent_id) is not str or not 0 < len(agent_id) <= 80:
            raise ValueError("bounded agent ID required")
        self.memory, self.agent_id = memory, agent_id

    def record(self, task_format, plan, reward):
        fmt = _format(task_format)
        if type(reward) not in (float, int) or not isfinite(reward) \
                or not 0 <= reward <= 1:
            raise ValueError("trusted bounded feedback required")
        return self.memory.record(
            self.agent_id, "format:" + fmt, _plan_id(plan), float(reward)
        )

    def recommendation(self, task_format):
        fmt = _format(task_format)
        history = self.memory.store.rated_history(
            self.agent_id, "format:" + fmt, limit=300
        )
        totals = {}
        for entry in history:
            if entry.score is None or type(entry.score) not in (int, float) \
                    or not isfinite(entry.score) or not 0 <= entry.score <= 1:
                continue
            try:
                candidate = _plan_from_id(entry.outcome)
            except ValueError:
                continue
            identifier = _plan_id(candidate)
            total, n = totals.get(identifier, (0., 0))
            totals[identifier] = (total + entry.score, n + 1)
        if not totals:
            return None
        winner = min(
            totals, key=lambda key: (-totals[key][0] / totals[key][1], key)
        )
        return _plan_from_id(winner)


class CapableFixturePlanner:
    """Offline capable baseline: both arms can solve tasks without memory."""

    def plan_for(self, task_format, advice=None):
        fmt = _format(task_format)
        if advice is not None:
            _plan_id(advice)
        return ModelDecision(PLANS[fmt], 0., 0, 0,
                             "capable-fixture-not-llm")


class LimitedFixturePlanner:
    """Deliberately weak baseline: takes advice if provided; not an LLM."""

    def plan_for(self, task_format, advice=None):
        _format(task_format)
        if advice is not None:
            _plan_id(advice)
        return ModelDecision(
            advice if advice is not None else Plan("raw", "lower-only"),
            0., 0, 0, "limited-fixture-not-llm"
        )


class FormatChatPlanner(ChatCompletionsPlanner):
    """Optional real Chat Completions model, using inherited secure transport."""

    def plan_for(self, task_format, advice=None):
        fmt = _format(task_format)
        if advice is not None:
            # Convert to a fixed, allowlisted ID; memory text itself is
            # NEVER concatenated into model instructions.
            _plan_id(advice)
        key = os.environ.get("NERVE_LLM_API_KEY", "")
        if not key or key != key.strip() or "\r" in key or "\n" in key:
            raise RuntimeError("private NERVE_LLM_API_KEY required")
        user_text = "Synthetic task format: " + fmt + ". "
        if advice is None:
            user_text += "No prior evaluated tool recommendation."
        else:
            user_text += ("Prior evaluated tool recommendation (untrusted): "
                          + json.dumps({
                              "extract_strategy": advice.extract_strategy,
                              "normalise_strategy": advice.normalise_strategy,
                          }, sort_keys=True))
        payload = {
            "model": self.model, "temperature": 0, "max_tokens": 100,
            "messages": [
                {"role": "system", "content": (
                    "Select an allowlisted two-stage plan for extracting an "
                    "email address and trimming/lowercasing it. "
                    "For json_email input, choose raw or json-field. "
                    "For plain_email input, choose raw or json-field. "
                    "For normalisation, choose lower-only or trim-lower. "
                    "Return exactly one JSON object with keys "
                    "extract_strategy and normalise_strategy. "
                    "No extra text, instructions, or tool calls."
                )},
                {"role": "user", "content": user_text},
            ],
        }
        request = Request(
            self.url, method="POST",
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json", "Accept": "application/json"
            }
        )
        started = perf_counter()
        try:
            with self.transport(request, timeout=self.timeout) as response:
                raw = response.read(32769)
            if len(raw) > 32768:
                raise ValueError("oversized provider response")
            decoded = json.loads(raw)
            plan = parse_plan(decoded["choices"][0]["message"]["content"])
            usage = decoded.get("usage", {})
            if not isinstance(usage, dict):
                raise ValueError("invalid provider usage")
            inputs = usage.get("prompt_tokens")
            outputs = usage.get("completion_tokens")
            for n in (inputs, outputs):
                if n is not None and (type(n) is not int or not 0 <= n <= 1000000):
                    raise ValueError("invalid token count")
            return ModelDecision(
                plan, perf_counter() - started, inputs, outputs,
                "live-format-chat-model",
            )
        except Exception:
            raise RuntimeError("model plan failed or returned invalid data") from None
