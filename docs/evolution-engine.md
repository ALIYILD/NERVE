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
