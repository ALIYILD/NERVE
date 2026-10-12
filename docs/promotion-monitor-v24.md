# Monitoring after promotion v2.4

The optional persistent monitor extends the v2.3 canary controller. A trusted
operator can promote a successful trial and arm its monitor **in the same SQLite
transaction**, authorising rollback to that trial's previous approved release.

```python
controller.promote(operator, trial, expected_generation=0,
                   reason='review-124', monitor_latency_ms=1000)
# Keep using this entrypoint after promotion:
result = controller.execute(runtime, trial, fresh_task)
report = controller.monitor.report(auditor, trial)
# Explicit stop restores the previous release if this generation is still active:
controller.monitor.stop(operator, trial, expected_generation=1, reason='review-125')
```

Omitting `monitor_latency_ms` preserves the existing unmonitored promotion API.
The trusted host must route all relevant requests through the controller and
retain the trial ID across restarts. Direct `engine.execute()` bypasses monitoring.
A new deployment needs its own approved trial and the corresponding handle; an
old superseded handle is not a router for monitoring newer deployments. Existing
operator activation/rollback APIs remain available.

Every fresh eligible promoted invocation is judged before delivery. Rejected
outputs, handler exceptions, judge exceptions/non-boolean answers and latency
budget overruns trigger an atomic rollback and a new generation. The current
request then executes the restored route. A newer operator decision takes
precedence: it is never overwritten by an older in-flight monitor. Success does
not disable monitoring, expand permissions or train the system.

Only one monitored attempt can be in flight. Concurrent requests, repeated tasks,
training/evaluation tasks and reserved holdouts use the pinned previous release;
they do not receive unchecked promoted output or inflate evidence. Consequently,
this is a conservative local monitored deployment, not a guarantee that 100% of
requests use the promoted route. A crash leaving a pending attempt continues to
serve the prior route after restart until an operator stops the monitor. There is
no automatic replay or timeout-based unlock. Monitoring observations cannot be
reused for training under a different ID with the same exact payload.

SQLite persists outcome categories, latency, task IDs/hashes, release identifiers,
configuration and audit events. Payloads, outputs and exception messages are not
stored here; identifiers are not anonymisation. Contract/tenant/agent checks use
the existing host-issued local capabilities. Host/database access is trusted.

The latency budget includes handler execution and judging and is checked after
completion. It cannot interrupt hung code. Production process/resource deadlines,
authenticated callers, monitoring retention, provider billing and downstream
clinical application integration remain host work. Baseline failures and database
failures propagate;
the prior approved route is not guaranteed correct. Already delivered results
cannot be recalled. Handlers must be pure/read-only because fallback can execute
a second strategy. This first-failure rule is an operational guard, not a
statistical drift detector or evidence of superiority over a strong baseline.

Tests cover persistence, checked delivery, automatic rollback, concurrent fallback,
interrupted attempts, source/error exclusion, holdout isolation, role and tenant
checks, evaluator/handler/latency failures and operator decisions during execution.
No live clinical traffic or external model calls are connected by this change.
