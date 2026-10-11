# Self-learning, adaptation and improvement: implementation plan

11 October 2026. Companion: [research review](self-improvement-research-2026-10.md).
Status below distinguishes implemented foundations from connected live capabilities.

| Stage | Applied in this repository | Remaining acceptance gate |
|---|---|---|
| Experience-based memory | Scoped independently judged utility and recent-window reranking | No demonstrated real-agent performance gain; not live-enabled |
| Chronological measurement | `learning_study.py`: separate train/evaluation, duplicate rejection, three arms, paired wins/losses, prediction timing | Realistic independently controlled data, multiple seeds, uncertainty intervals and provider cost |
| Skill consolidation | `skill_proposals.py`: pending procedural lesson plus 3–20 successful episode references; scope/revision/status checks | Lesson generation, semantic deduplication, independent lesson testing, review and expiry policy |
| Prompt/tool selection | `recipe_selection.py`: bounded matched boolean evaluation of data-only candidates, incumbent wins ties, no deployment authorization | LLM/GEPA proposal adapter, allowlisted executable tools, fresh final evaluation, budget attestation |
| Release control | Existing governed learning, shadow collection, operator approval, canaries and rollback | Explicit connection of the new memory/recipe components to reviewed nonclinical host trials |
| Code evolution | Not enabled | Isolated execution environment, secret/network exclusion, resource limits, independent tests and reviewed PRs |
| Deployment | Packaged pilot and installation/recovery checks exist | Target-server access, identity configuration, TLS and target-host verification |

## Applied executable checks

```bash
PYTHONPATH=src python -m unittest discover -s tests -q
PYTHONPATH=src python scripts/adaptive_memory_study.py
```

The smoke study creates independent local stores for no-memory, lexical-memory
and adaptive-memory arms. It exercises actual approved memory retrieval and
adaptive feedback across six training tasks, then ten new evaluation tasks.
Expected answers go only to the judge, not the predictor. Evaluation never calls
the learning callback. The deterministic capable sorting control solves the tasks
without memory: all arms score 10/10. This is an honest no-gain fixture, not a
claim that memory improves reasoning or an LLM benchmark. There are no model calls.
Latency is measured but fixed arm order and a tiny sample cannot establish speed
benefit. Provider cost remains unknown, not a fabricated zero.

The generic study runner trusts host callbacks and independent state construction.
It is not a process sandbox or an enforcement layer for arbitrary agent code.
Task hashes prevent exact duplicates, not semantic near-duplicates. The host must
freeze datasets independently and prevent evaluation tasks entering other learners.

Skill proposals are always pending. Their text is host-supplied, not automatically
extracted from transcripts. A successful source episode does not prove its lesson
is correct. Review must recheck linked evidence, freshness and lesson quality.
Proposal creation and provenance attachment are separate transactions: if attaching
links fails, an unapproved orphan proposal may remain and must not be approved.

Recipe selection is exhaustive bounded offline comparison, **not GEPA installed**,
not mutation/crossover and not autonomous prompt generation. The first recipe is
the incumbent. Selection improvement is not final-test improvement. Recipe strings
are never executed by the selector; a future host adapter must validate strategies
against its own registry. Call budgets are counts, not hard callback timeouts or
monetary spending controls. Evaluator failure aborts selection.

## Next actions, in order

1. Provision a fresh limited-purpose model credential through the protected
   research environment, with explicit task/data handling and spending limits.
   Never use historical disclosed/revoked keys.
2. Supply independently reviewed nonclinical task streams with chronological
   train/selection/final partitions and a retained regression suite.
3. Implement and compare capable baseline/model adapters using identical tools,
   inference budgets and task splits. Repeat across seeds; report failures and
   no-improvement outcomes. Freeze the winning recipe before fresh final testing.
4. Add lesson generation and independent skill validation; review proposals before
   retrieval. Add retention and deduplication before scaling evidence storage.
5. Connect a passing candidate to the existing operator-approved shadow/canary
   lifecycle; measure drift, forgetting, cost, latency and rollback behavior.
6. Only then consider isolated source-code proposal experiments. No clinical
   protocol, device control, permission or evaluator modification is authorized
   by an agent's own reward or reflection.

No live clinical system, external model, public endpoint or server was modified.
These foundations are not a completed general recursive self-improving agent.
