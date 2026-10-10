# NERVE Evolution Engine — integration roadmap

The objective is an open, model-agnostic research system that can learn from
verified outcomes, compare controlled agent variants, and refuse regressions.

## P0 implemented: local outcome-aware memory
`src/nerve_awim/evolution_v01.py` provides a MemRL-inspired, two-stage
strategy selection interface on top of NERVE Learn's SQLite experience store:
agent/context matching followed by explicit outcome-utility ranking. Only
rated memories are eligible. The underlying stored text is **untrusted data**.

This is an independent implementation inspired by:
- [MemRL](https://github.com/MemTensor/MemRL) (Zhang et al., 2026; arXiv:2601.03192)
- [Karpathy AutoResearch](https://github.com/karpathy/autoresearch)

Not an upstream MemRL import, not reinforcement-learning model training, and
not a validated retrieval-performance gain.

## Next stages
1. **P0:** Compare outcome-aware recall to simple recency and semantic
   retrieval with identical observations, context, scoring budgets and
   held-out tasks. Report negative outcomes.
2. **P0:** Integrate outcome score and provenance into the AutoResearch
   acceptance report; never promote a strategy solely because an LLM recommends it.
3. **P1:** Add optional GEPA-style prompt/strategy optimisation behind an
   adapter. Keep private test sets and independent deterministic metrics.
4. **P1:** Add optional Letta memory adapter; verify agent identity,
   privacy, data deletion and cross-session isolation first.
5. **P1:** Connect autoresearch-agent via an optional Hermes skill
   with sandboxed target-file allowlists, budget enforcement and PR review.
6. **P2:** Evaluate Darwin-style A/B variants against equivalent single-agent
   baselines, including latency, cost and safety regressions.

## Important boundaries
- NERVE core remains free from mandatory SaaS API keys.
- No third-party source code was copied for this first component.
- Do not store clinical records, secrets or user identifiers.
- Caller-provided agent IDs in NERVE Learn do not constitute authentication.
- Candidate memories cannot change system prompts, permissions, medical
  decisions or deployed code without independent human approval.

## Implemented: bounded parallel subagents

`src/nerve_awim/parallel_agents_v11.py` provides a capped
`ThreadPoolExecutor` for **trusted in-process** subagent handlers.
`evolution_cycle_v11.py` connects five independent roles:

- **Hypothesis agent** validates typed candidate proposals.
- **Memory agent** retrieves previously scored local candidate experiences.
- **Evaluation agents** run unchanged WorldCore benchmark metrics concurrently.
- **Safety agent** applies the evaluator-defined absolute reliability gate.
- **Review agent** rejects goal improvements with prediction/completion regressions.

Outcomes are collected in deterministic proposal order. Worker failures cause
the batch to fail closed, rather than publishing partial experimental results.
Memory may prioritise candidates but cannot weaken any threshold. Optional
`learn_from_evaluations=True` records **binary research-gate feedback**
for future prioritisation; it never modifies model weights, code, policies or
controllers. A failed candidate scores zero.

```bash
PYTHONPATH=src python benchmarks/v11_parallel_evolution.py
PYTHONPATH=src python benchmarks/v11_memory_effectiveness.py
```

## Measured memory benchmark — synthetic only

The 20-seed held-out Bernoulli simulation gives every strategy identical
training feedback and compares selecting strategies by observed utility with
selecting the most recently stored strategy. Results from CI
[run 38078967300](https://github.com/ALIYILD/NERVE/actions/runs/38078967300):

- Outcome-ranked memory success rate: **72.22%**
- Recency-only strategy success rate: **51.50%**
- Known-probability oracle: **73.28%**
- Memory-ranked strategy won on **19/20** seeds, with one tie.

This dataset is deliberately constructed with stable, context-specific
strategy success probabilities. The result verifies selection behaviour;
it does **not** establish real-world agent learning, performance speedup
or adaptive reasoning ability. It also does not compare against vector
retrieval or equivalent transformer-based memory systems.

## Interfaces and remaining research

`learn_mcp.py` now exposes optional `select_evaluated_strategy` over the
local MCP stdio server, alongside record/rate/recall functions. Its
caller-supplied agent IDs are not authentication; do not expose this local
server directly to untrusted remote clients.

Not implemented: independently running Hermes/Letta/GEPA/Darwin agents,
provider API adapters, process isolation, hard CPU/memory/time limits,
distributed consensus, semantic vector embeddings, private holdout sets,
or real medical-device and physical-AI validation.

Python threads can overlap I/O work, but **do not imply acceleration for
CPU-heavy Python tasks** because of interpreter scheduling and shared
resources. Benchmark timings are descriptive rather than guarantees.

## Evolution v1.2 — executable agent strategy feedback bridge

The new `agent_learning_v12.py` connects persistent NERVE Evolution
experience scores to **registered executable Python agent capabilities**.
A caller can register trusted handlers, submit typed `AgentTask` objects,
run multiple tasks through the existing bounded parallel worker pool, and
record independently evaluated `feedback` scores (0–1).

- The **utility** policy ranks available registered strategies by mean
  feedback across previously evaluated episodes.
- The **recency** comparator selects the latest registered evaluated
  strategy using the **same** training history.
- Stored strategy IDs are untrusted; unknown IDs **cannot** run as code.
- Agent and context namespaces are exact-matched for evaluated records.
- All batch choices occur before execution; test outputs are not
  automatically treated as training feedback.
- Recreating the coordinator with the same local SQLite path restores
  the strategy history (not Python callable objects).

```bash
PYTHONPATH=src python benchmarks/v12_executable_agents.py
```

The built-in executable benchmark runs real registered Python utilities for
email normalisation, numeric sorting and JSON extraction using constructed
inputs with deterministic, externally supplied expected outputs. Each policy
gets the same examples, observed feedback and task execution budget.
This is an offline **tool strategy-selection** test, not real LLM reasoning
or autonomous source-code learning. It cannot establish a runtime speedup
simply because threads execute concurrently, and the supplied reward
function is not cryptographically authenticated.

### Trusted caller example

```python
from nerve_awim.agent_learning_v12 import (
    AgentTask, RegisteredStrategy, FeedbackAgentCoordinator,
)
from nerve_awim.evolution_v01 import EvolutionMemory

memory = EvolutionMemory("local-evolution.sqlite")
agent = FeedbackAgentCoordinator(
    memory=memory,
    agent_id="research-agent",
    strategies=[
        RegisteredStrategy("basic", "normalise",
                           lambda text: text.lower()),
        RegisteredStrategy("trim", "normalise",
                           lambda text: text.strip().lower()),
    ],
)
agent.feedback(context="normalise", strategy_id="basic", reward=0.0)
agent.feedback(context="normalise", strategy_id="trim", reward=1.0)
output, = agent.run([AgentTask("demo", "normalise", "  EXAMPLE  ")])
assert output.value == "example"
```

Do not run untrusted model-generated Python handlers. Reward provenance and
human approval are application responsibilities; use the existing isolated
WorldCore gates for control-related proposals. This is an experimental public
integration that works without Jev, TypeSafe or any commercial API key.
