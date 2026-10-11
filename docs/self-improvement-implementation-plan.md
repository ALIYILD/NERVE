# Self-learning, adaptation and improvement: implementation plan

11 October 2026. Companion: [research review](self-improvement-research-2026-10.md).
Status below distinguishes implemented foundations from connected live capabilities.

| Stage | Applied in this repository | Remaining acceptance gate |
|---|---|---|
| Experience-based memory | Scoped independently judged utility and recent-window reranking | No demonstrated real-agent performance gain; not live-enabled |
| Chronological measurement | `learning_study.py`: separate train/evaluation, duplicate rejection, three arms, paired wins/losses, prediction timing | Realistic independently controlled data, multiple seeds, uncertainty intervals and provider cost |
| Skill consolidation | `skill_proposals.py`: one-call host generator interface, strict output schema, pending procedural lesson plus 3–20 successful episode references, atomic storage and exact retry deduplication | Real-model generator adapter, semantic deduplication, independent lesson testing, review and expiry policy |
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

Skill proposals are always pending. Text can be host-supplied or returned by the
host-configured `generate_skill_proposal(..., generator=...)` callback. The callback
receives only approved source-memory snippets and successful episode references;
raw task/output transcripts were never stored and cannot be reconstructed here.
It must return exactly `lesson` and the unchanged ordered `episodes` list. Read
and proposal capabilities are required, and current evidence is rechecked after
the callback. Its generated text is never executed or automatically approved.

Proposal creation and provenance attachment now share one SQLite transaction.
A failed link write rolls back both. An exact pending lesson/evidence/revision
retry reuses its existing ID; this is not semantic deduplication or generator-call
deduplication. A successful source episode does not prove its lesson is correct.
Review must recheck linked evidence, freshness and lesson quality. Existing old
orphan proposals are not repaired or approved automatically.

The interface makes one generator call per invocation. It does not provide a hard
runtime timeout, monetary budget or process sandbox. A provider-neutral adapter
is available, but no external provider is installed or invoked: the host must separately provision and
authorize any external transmission and enforce call/time/cost limits. Local
fixtures test integration mechanics, not actual LLM lesson quality.

### Model adapter and fresh lesson comparison

`skill_model.LessonModelAdapter(complete=transport, model=model_id,
enabled=True, max_calls=1)` can be passed as `generator` to
`generate_skill_proposal`. It defaults to disabled. The trusted transport accepts
one dictionary (`model`, `system`, JSON `input`, `max_output_tokens`,
`timeout_seconds`) and returns JSON text. It must implement those timeout/token
limits and enforce provider/data/spending policy itself. There is deliberately
no default endpoint, credential lookup, retry or external transmission.

The adapter reserves its thread-safe process-local call quota before transport;
failed calls consume quota. It bounds input/response size, rejects duplicate JSON
keys and validates the exact lesson/evidence schema. This is not a durable
spending cap, hard transport timeout or prompt-injection sandbox.

`skill_validation.evaluate_lesson` compares baseline and lesson predictions on
the evaluation tail of a validated `Episode` stream. Declare every development
and selection task in its training prefix. Exact task overlap is rejected before
prediction, call count is preflighted, arm order alternates, and predictors never
receive expected answers or judge results. Reports expose paired wins/losses and
never approve memory or activate deployment. Exceptions abort without a partial
success report. Host callbacks must have independent/stateless execution; this
helper cannot enforce isolation, semantic disjointness, historical nonreuse,
provider cost or multiple-seed generalization. No real-model quality result has
been produced. A reviewed dataset, protected provider configuration and spending
authorization remain necessary for the live experiment.

Recipe selection is exhaustive bounded offline comparison, **not GEPA installed**,
not mutation/crossover and not autonomous prompt generation. The first recipe is
the incumbent. Selection improvement is not final-test improvement. Recipe strings
are never executed by the selector; a future host adapter must validate strategies
against its own registry. Call budgets are counts, not hard callback timeouts or
monetary spending controls. Evaluator failure aborts selection.

## Next actions, in order

### Bounded improvement loop (implemented)

`improvement_loop.run_improvement_loop(training, selection, final, propose=...,
predict=..., judge=...)` defaults to ten iterations and rejects larger runs.
Provide at least three training, five selection and five final `Episode` objects;
training phases must be `train`, both other partitions `evaluation`. IDs and exact
task payloads must be disjoint across all partitions. The predictor receives only
task and lesson (or `None` for baseline). The proposer sees training examples,
the incumbent and selection history, never final tasks or final results.

Each distinct proposed lesson is compared with the incumbent. Keep requires at
least one paired win and zero observed losses; otherwise the incumbent remains.
Exact duplicate lessons skip evaluation. At the iteration limit the selected
lesson is frozen and tested once against the original baseline on final tasks.
No candidate means no final test is necessary. A final tie, loss or lack of gain
reports `no_verified_improvement`; positive gains without losses report only
`observed_final_gain`, not statistical proof or release authorization.

Prediction-call allowance is preflighted for the entire worst-case run. Proposal
calls are limited by iterations. Callbacks are trusted and must independently
enforce real model costs/timeouts and execution isolation. Exceptions abort;
there is no automatic retry, daemon, durable resume, cross-run holdout registry,
code self-modification or clinical deployment. Reusing the final set in another
run would contaminate it; hosts must provide genuinely new final data. Local
tests run the ten-step mechanics, including no-gain and failed-final scenarios;
they are not real-model learning evidence.

### Remaining live experiment prerequisites

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
