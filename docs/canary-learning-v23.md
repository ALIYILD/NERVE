# Bounded canary routing v2.3

`CanaryLearning` adds an opt-in trial stage between a passed held-out evaluation
and full operator-approved activation. It currently supports one task context per
tenant/agent scope and trusted pure/read-only handlers. It is a local host API,
not a downstream clinical application integration, remote authentication service
or process sandbox.

## Host workflow

```python
from nerve_awim.canary_learning_v23 import CanaryLearning

canary = CanaryLearning(engine)
trial = canary.start(
    operator_actor, passed_candidate_id,
    expected_generation=0, reason="review-123",
    percent=5, required_successes=20, latency_ms=1000,
)
result = canary.execute(runtime_actor, trial, fresh_task)
report = canary.report(auditor_actor, trial)

# After phase becomes "ready", a separate operator decision is required:
# canary.promote(operator_actor, trial, expected_generation=0, reason="review-124")

# At any point before promotion:
# canary.stop(operator_actor, trial, reason="operator-stop")

# After promotion, the existing engine.rollback() accepts report["base_release"]
# with the then-current generation and an explicit operator review reference.
```

The operator must approve a candidate that passed held-out evaluation against the
current generation. The baseline remains the globally active release throughout
the trial. A trial version is not registered as a globally approved release or
rollback target until promotion. The strong baseline repository pilot has so far
produced no strictly better candidate, so its proposals cannot enter this stage.

## Sampling and monitoring

The approved sampling percentage is 1–25%, default 5%. A stable hash of the random
trial ID and canonical task content assigns a cohort. This is an expected sample
fraction, not a guaranteed percentage in small batches, nor protection against a
caller deliberately crafting inputs to target a cohort. The host controls inputs.
Unselected tasks use the active baseline normally.

Selected tasks must be unused in the scope: prior training/holdout/canary tasks and
pre-reserved holdouts cannot become canary observations. Such requests still get
the baseline result, but cannot inflate trial counts. Canary observations do not
write training rewards and cannot later enter training under another task ID with
identical content.

Exactly one candidate attempt may be in flight per trial. Other concurrent requests
use the baseline. Each candidate result is independently judged before delivery.
Handler errors, judge exceptions or non-boolean answers, rejected outputs, and
exceeded latency budgets stop the trial and fall back to the current baseline.
An operator stop or changed active generation during execution also suppresses
the candidate result. Already delivered results cannot be recalled.

The latency measurement includes candidate execution and judging. The budget is
checked **after completion**; it cannot interrupt a hung handler or judge. The
trusted host must supply process/time/resource limits. A baseline failure still
propagates to the caller. Database failures fail closed by surfacing an error;
they are not silently converted to apparently successful telemetry.

After the approved number of successful fresh candidate tasks (5–1000, default
20), the trial moves to `ready` and further traffic uses the baseline until an
operator promotes it. No traffic-percentage increase or full activation occurs
automatically. The bound limits candidate invocations: one failure stops early,
otherwise the approved success count ends the trial. Failed trials cannot restart
with the same candidate ID. A new candidate requires a new freeze, fresh held-out
evaluation and operator approval; statistically independent evidence is still a
host responsibility.

## Persistence, roles and rollback

Trial configuration, outcome categories, measured latency, version identifiers and
audit events persist in SQLite. No input payloads, outputs or exception text are
stored by the controller. IDs/hashes are not anonymisation. A crash during a
candidate attempt leaves a `pending` row: a restarted controller serves baseline
traffic and refuses promotion. The operator must stop the interrupted trial; there
is no replay or silent timeout-based reset.

Only operator capabilities can start, stop or promote. Runtime capabilities can
execute and auditors/evaluators/operators can inspect reports. These are the
existing host-issued local object capabilities, not proof of human identity or
organisational separation. Raw host/database access remains trusted.

Promotion atomically changes the active release and generation. The existing
operator-controlled rollback restores a prior approved release. By default automatic fallback
is a **canary-stage** feature. The optional [v2.4 monitor](promotion-monitor-v24.md)
adds persistent post-promotion checks and automatic rollback when explicitly armed
with `monitor_latency_ms` during promotion. Other trusted v2.0 operator APIs remain
available, so the host must enforce its chosen deployment policy at its entrypoint.

## Evidence and limits

```bash
PYTHONPATH=src python scripts/verify_canary_v23.py
```

The verifier uses actual repository files, an intentionally weaker regex baseline,
fixed test-only trial IDs, and an injected independent-judge failure. It proves
that a passed candidate can serve a sampled task and that a subsequent regression
stops candidate traffic, serves baseline output and preserves the active release.
It does not prove performance improvement over the capable AST baseline. Unit
tests additionally exercise successful completion, explicit promotion, rollback,
role isolation, interruption and in-flight stop behavior.

This is a mechanical rollout gate, not a statistical superiority test. There are
no paired baseline quality measurements or cost comparisons in the canary itself;
held-out quality evidence is prerequisite. Costs remain unknown (`null`). A real
deployment still needs independently curated data, authenticated host integration,
provider billing, production resource limits and appropriate operational criteria.
No live service is deployed or recurring job scheduled by this change.
