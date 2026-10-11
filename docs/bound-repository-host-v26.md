# Operator-bound HTTP trials v2.6

The authenticated repository service now connects to the existing canary and
post-promotion monitor. The default remains AST-baseline shadow collection. A
trusted host operator can persist a scope-to-trial binding, after which the same
signed task endpoint follows that trial's reviewed lifecycle. Nothing is publicly
deployed by this change. The current real AST baseline has no demonstrated
strictly better candidate; the rollout drill uses explicit test fault fixtures.

## Bind an independently reviewed trial

Prepare training, freeze, fresh held-out evaluation and a passed candidate using
the existing v2.0/v2.2 APIs. The candidate must satisfy the existing quality gate.
Start a v2.3 trial with an operator capability, sampling and success limits.
Then bind it to the HTTP scope through the offline command:

```bash
PYTHONPATH=src python scripts/bind_repository_trial_v26.py \
  --database /persistent/nerve-pilot.db --tenant lab --agent inventory \
  --canary REVIEWED_TRIAL_ID --expected-generation 0 --expected-version 0 \
  --reason review-126
```

This is an OS/host-trusted operator command, not remote authentication or proof of
independent human review. It issues only a local operator capability in the
existing scope. Protect database/configuration/CLI access from runtime agents.
`expected-version=0` means no binding exists. Later replacements require the
current binding version; both that version and the active generation are checked
in one write transaction. The command persists the binding and an audit event;
it does not start a trial, promote it, edit its sampling percentage or bootstrap
a scope. There is no HTTP bind/operator route and clients cannot choose a trial.

The API equivalent is:

```python
from nerve_awim.bound_repository_host_v26 import HostDeployments

deployments = HostDeployments(engine)
binding = deployments.bind(operator, trial,
    expected_generation=0, expected_version=0, reason='review-126')
# Once the trial is ready, make a separate reviewed promotion:
deployments.controller.promote(operator, trial,
    expected_generation=0, reason='review-127', monitor_latency_ms=1000)
```

The standalone `serve_repository_host_v25.py` entrypoint now constructs
`BoundRepositoryHost`. Existing identity configuration and URLs remain valid.
A running instance reads persistent bindings on every request; no restart is
required to bind or advance its trial. Existing v2.5 unbound scopes remain
baseline-only. The host contract revision is unchanged because the registered
tool and independent evaluator semantics have not changed.

## Permitted lifecycle

| Persistent trial state | HTTP task behaviour |
|---|---|
| Unbound initial baseline | AST baseline plus best-effort shadow collection |
| Active approved trial | Existing bounded sampling and independent output checks |
| Ready for review | Original baseline until separate promotion |
| Stopped trial | Original baseline; no automatic retry |
| Promoted with active monitor | Independently checked promoted tasks; previous route for busy, duplicate or reserved tasks |
| Monitor-owned rollback | Restored baseline at the monitor's next generation |
| Unmonitored promotion, unrelated generation change, superseded monitor | 503; no silent adoption |

A stopped trial cannot be newly bound. Rebinding to a new eligible trial requires
another operator decision and a fresh binding version. An already-bound stopped
trial can continue serving its unchanged baseline. To stop a promoted deployment
and continue HTTP traffic on the baseline, use `controller.monitor.stop()` with
the current generation; an arbitrary legacy rollback changes the deployment
outside the binding and intentionally requires review before routing resumes.
There is no automatic rebinding or removal of the deployment policy.

Guards validate the persisted binding and allowed release/generation within
routing transactions. A changed binding or unrelated release detected during a
candidate attempt suppresses its response. The HTTP layer also checks before
delivering controlled results. These checks are not cancellation: an already
started pure/read-only handler may finish; already-delivered responses cannot be
recalled. A race can leave a pending outcome rather than mark it completed;
existing stop/review recovery rules apply. A rejected request returns a generic
503, never an unchecked result from the replacement deployment.

## Learning and evidence

Controlled traffic does not enqueue shadow training. Pending shadow observations
are discarded when the host observes a binding, and further shadow claims are
guarded against concurrent binding. Already-claimed learning work may finish.
Trial/monitor task claims retain the existing duplicate and holdout protections.
Output checks, failure categories, latency, release versions and binding audit
events persist; source text and exception messages do not.

`GET /v1/evidence` remains auditor-only and scope-specific. In controlled mode it
returns the binding version, current routing eligibility, trial report, optional
monitor report and earlier shadow aggregates. The component reports are
observational snapshots, not a single atomic ledger read. An invalid deployment
can still be inspected by an authorised auditor. Reports do not confer permission
to activate anything.

## Verification and limits

Tests use signed tokens and the real standalone HTTP server. The drill serves a
checked promoted result, encounters a nested-function case that the regex tool
gets wrong, returns the AST baseline and persists rollback across a server
restart. To make that candidate eligible, setup deliberately faults the baseline
on earlier test tasks. This proves transport/control behaviour, not that regex
improves on the real AST tool or that NERVE has learned a new capability.

Additional tests cover stale binding approvals, tenant/role boundaries, duplicate
and reserved tasks, waiting for promotion, pending-monitor recovery, latency
failure, operator stops, rebinding and unrelated rollback during execution.

The v2.5 loopback/proxy/IdP requirements and v2.4 pure-handler/time-budget limits
still apply. Real identity provisioning, public hosting, live Clinical OS
traffic, external-model providers/billing and production resource isolation remain
unconnected. No approval, provider secret or public service is created here.
