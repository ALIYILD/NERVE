# ARC local operator runbook

This implementation adds an explicitly invoked local workflow to NERVE's existing
Agent OS bridge. It does not start a new service, scheduler, provider router or
training daemon. Run commands from `/Users/aliyildirim/nerve-arc-handoff` with the
repository's Python environment. Core ARC commands use the standard library.

The general ARC runtime defaults to `off`; administrative inspection does not
enable execution. `arc-run` explicitly opts into the bounded local workflow with
full authorization and verification. A previously persisted `off` or `shadow`
mode takes precedence, including after restart. Clinical inputs below are
synthetic fixtures, and no external submission tool is registered.

## Start and verify a real local inventory

Use disposable state to reproduce this handoff without changing the running
Agent OS learning store:

```sh
ARC_STATE=$(mktemp -d /private/tmp/nerve-arc-demo.XXXXXX)
python3 scripts/agentos_bridge.py arc-run --state "$ARC_STATE" \
  --source src/nerve_awim/repository_agents_v20.py \
  --task-id inventory-demo --restart
python3 scripts/agentos_bridge.py arc-inspect --state "$ARC_STATE" \
  --task-id inventory-demo
```

Expected: action `inventory`, `verified: true`, `dispatches: 1`, and
`restart_same_outcome: true`. The existing AST parser inventories the real source;
a separate token parser verifies it. The source is never executed. The returned
`decision_id` identifies the persisted episode. Replay the recorded episode
without invoking a handler or provider:

```sh
python3 scripts/agentos_bridge.py arc-replay --state "$ARC_STATE" \
  --decision-id DECISION_ID_FROM_OUTPUT
```

`arc-inspect` returns redacted evidence IDs/versions, correlation ID, lifecycle,
transport/semantic status and criterion results. It does not print source code,
arguments, source contents, credentials or clinical identifiers. An API transport
success alone is not a verified task result.

## Synthetic clinical fixture

Create a fresh synthetic assessment using the current clock. Do not substitute
patient data or real clinical records:

```sh
python3 - "$ARC_STATE/clinical.json" <<'PY'
import json, sys, time
now = time.time()
fixture = {
    'workflow': 'clinical', 'synthetic': True, 'task_id': 'synthetic-referral',
    'assessment': {
        'assessment_id': 'synthetic-example', 'tenant_scope': 'synthetic',
        'captured_at': now - 60, 'valid_until': now + 3600,
        'findings': 'Synthetic assessment example', 'approved': True
    }
}
with open(sys.argv[1], 'w') as f:
    json.dump(fixture, f)
PY
python3 scripts/agentos_bridge.py arc-run --state "$ARC_STATE" \
  --task "$ARC_STATE/clinical.json"
```

Expected: `prepare-draft`, verified source fields/citations,
`review_state: awaiting_clinician_review`, `submitted: false`. This verifies draft
preparation only. Missing assessment (`"assessment": null`) requests information;
stale, future-dated, conflicting or unapproved evidence routes to review.
Wrong-tenant or inaccessible evidence is excluded before snapshots and results.

To reproduce missing evidence independently:

```sh
python3 - "$ARC_STATE/missing.json" <<'PY'
import json, sys
with open(sys.argv[1], 'w') as f:
    json.dump({'workflow': 'clinical', 'synthetic': True,
               'task_id': 'missing-assessment', 'assessment': None}, f)
PY
python3 scripts/agentos_bridge.py arc-run --state "$ARC_STATE" \
  --task "$ARC_STATE/missing.json"
```

Expected: `request-information`, unknown `assessment`, task `verified: false`.
Recording a correct clarification is not completing the original draft task.
The registered `no-action` tool likewise records explicit abstention; it does
not fabricate task completion.

No DeepSynaps referral API contract or authorized clinical environment was found
in this checkout. No real provider inference or real clinical API verification
was performed for this implementation. Clinical release activation is rejected
by the manifest interface and requires a separate appropriate review process.

## Frozen evaluation and bounded improvement

Use a separate state directory for the public synthetic smoke benchmark:

```sh
ARC_EVAL_STATE=$(mktemp -d /private/tmp/nerve-arc-eval.XXXXXX)
python3 scripts/agentos_bridge.py arc-improve --state "$ARC_EVAL_STATE" \
  --candidate-budget 3
python3 scripts/agentos_bridge.py arc-candidate-status --state "$ARC_EVAL_STATE"
python3 scripts/agentos_bridge.py arc-evaluate --state "$ARC_EVAL_STATE" \
  --report "$ARC_EVAL_STATE/benchmark.json"
```

Candidate generation/evaluation is limited to three versioned configurations
and at most one selection. It cannot rewrite authorization, evaluator, fixture
files, tools or budgets. Interrupted candidates stay recorded and consume their
reservation. Zero budget is a valid explicit exhausted run.

The 60-scenario suite uses development/validation/test family splits and reports
all three arms: existing governed dispatcher, structured decision without
semantic verification, and full verification. No model is trained. Clinical
baseline tasks use the new synthetic boundary with the existing dispatcher;
there was no historical clinical API baseline in NERVE.

The smoke fixtures and their release results are public and consumed. Re-running
in fresh storage reproduces an engineering check; it does not create a new
holdout or independent evidence. Obtain independently reviewed fresh families
before future promotion decisions. Synthetic fault-injection improvements do
not establish learned gain, clinical efficacy or general self-improvement.

## Shadow staging, review and rollback

The following commands stage a local inventory shadow manifest. Staging creates
no effect and no production activation. Promotion requires an explicit review
reference and a separately issued operator capability from the staging actor.

```sh
python3 scripts/agentos_bridge.py arc-release-status --state "$ARC_STATE"
python3 scripts/agentos_bridge.py arc-stage --state "$ARC_STATE" \
  --context inventory --arc-mode shadow --canary-limit 5
python3 scripts/agentos_bridge.py arc-promote --state "$ARC_STATE" \
  --manifest-id latest --review-ref local-shadow-review
python3 scripts/agentos_bridge.py arc-run --state "$ARC_STATE" \
  --source src/nerve_awim/repository_agents_v20.py --task-id inventory-shadow
python3 scripts/agentos_bridge.py arc-release-status --state "$ARC_STATE"
python3 scripts/agentos_bridge.py arc-rollback --state "$ARC_STATE" \
  --manifest-id latest --review-ref local-shadow-rollback
```

Expected shadow result: `status: shadow`, `dispatches: 0`, task `verified: false`.
`latest` selects the most recently staged or active manifest across contexts;
use the explicit manifest ID when several contexts have pending changes.

Rollback restores the recorded compatible mode and previous manifest/canary
usage. It cancels pending work and marks work already dispatched as uncertain;
it never deletes audit history or blindly retries an effect. This may restore
`enforce` after an explicitly opted-in local inventory run. Inspect release
status to confirm the recorded previous mode. Staged manifests are bound to the
reviewed governed release/generation and cannot authorize changed routes.

## Recovery and reconciliation

Repeat execution of a completed decision returns its durable outcome. A crash
or cancellation after dispatch leaves an uncertain execution; do not issue a
replacement write or infer success from an absent receipt. Inspect the episode,
check an independent result/status source, then record the reviewed disposition:

```sh
python3 scripts/agentos_bridge.py arc-inspect --state "$ARC_STATE" \
  --decision-id UNCERTAIN_DECISION_ID
python3 scripts/agentos_bridge.py arc-reconcile --state "$ARC_STATE" \
  --decision-id UNCERTAIN_DECISION_ID --observed-status failed \
  --review-ref independent-readback-review
```

Choose `succeeded`, `failed` or `cancelled` only from the actual reviewed
observation. Reconciliation records operator disposition; it does not invent
verification evidence or turn an unverifiable outcome into trusted learning.
The command rejects episodes that do not need reconciliation.

## Limits, failures and retention

- The shared bridge uses a nonblocking host lock: concurrent commands for the
  same state directory are rejected instead of spawning another worker. SQLite
  transactions protect durable transition and canary reservations.
- A task allows five decisions. Repeated no-progress replanning stops. Transient
  verification/readback gets at most two retries; uncertain writes are never
  retried automatically. Registered handlers must provide their own bounded I/O;
  this local factory uses parsers and synthetic in-process functions only.
- Structured provider generation allows one schema repair. Its native Hermes
  adapter is disabled by default and retains the existing free-model accounting,
  text-only tool restriction and timeouts. Existing native settings are a
  55-second runtime, 90-second parent timeout, two iterations and a shared
  20-session UTC daily cap. This CLI demonstration calls no provider. Provider
  outages or malformed output stop without unvalidated dispatch or paid fallback.
- Evidence normally expires after one hour; decisions after five minutes.
  Changed observation versions invalidate decisions and approvals. Reviewed
  guidance defaults to one day and has a maximum 30-day expiry. Rejected,
  expired, retracted or deleted guidance is excluded from retrieval.
- Execution/audit records have no automatic purge job in this implementation.
  Retain them for reconciliation and reproducibility; define an authorized
  storage-retention policy before using a real integration. Sensitive payloads
  must not be placed in ordinary logs. The CLI limits task files to 64 KiB and
  direct Python source to 12,000 bytes; the governed payload limit remains
  16 KiB.
- Validation rejection, stale evidence, approval wait, budget exhaustion,
  uncertain effect, dispatch and outcome events are inspectable with
  `arc-inspect`. Metric labels contain no patient/source payloads. Blocked CLI
  requests exit with code 2 and a redacted reason category; there is no silent
  fallback to an older unprotected executor.

## Enforcement coverage

Enabled workflows enter through `agentos_bridge.py arc-run`,
`arc_workflows.run_workflow`, `ArcRuntime` and the actual
`GovernedLearning.execute` boundary. Direct public dispatch into enabled
contexts is rejected without a valid decision permit. Public governed training
and evaluation and `ShadowLearning`, `CanaryLearning`, and `PromotionMonitor` alternative paths reject ARC-enabled
contexts instead of bypassing their decision controls. Persisted modes are
honored on restart. The CLI issues only the local synthetic tenant capability.

These historical paths are not automatically ARC-enabled: standalone simulation
controllers (`runtime_v28`, WorldCore), `DemoAgentBridge`/MCP tools,
`FeedbackAgentCoordinator`, `BoundedParallelAgents`, v30 agents, Hermes role
adapters, maintenance missions, audit/repository research runners, external
Agent OS dashboard workers and unrelated existing HTTP deployments. Their
existing authentication and protections remain separate. OIDC/grant-protected
HTTP hosts are not newly deployed by this work. The existing 900-second Agent
OS schedule has no new ARC job. Trusted private Python internals are not a
sandbox or external API security boundary.

Run the focused suite with:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_arc_*.py' -v
```

See the implementation completion report for the observed full regression gate,
benchmark denominators, adverse findings and remaining external blockers.
