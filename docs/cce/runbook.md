# Cognitive Cue Engine operator runbook

CCE is an opt-in research extension of NERVE. It uses the existing `GovernedLearning`
authority, database and audit events, the existing Hermes runtime, and the existing
trusted memory ledger. It does not start another agent service or scheduler.

For the installed Agent OS bridge and its native Hermes worker, see the
[host wiring and operator commands](host-integration.md). The provider revision
attestation requirement remains in force after wiring.

## Local commissioning

From the repository root:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_cue*.py' -v
PYTHONPATH=src python3 -m nerve_awim.cue_cli demo --output /tmp/cce-demo.json
node --test tests/test_checkpoint_discovery.cjs
```

The demo uses deterministic arithmetic fixtures. It executes 60 fixture calls,
makes zero external provider calls, stores paired evidence in a temporary existing
NERVE ledger, rejects promotion and exports a pending memory record. It reports
local routing overhead, not model inference speed. Fixture costs of zero are
known because no provider is called; an unknown live cost must not become zero.

The demo output includes source-file hashes. Its database is temporary and is
removed at exit. It does not alter an installed host, credentials, provider quotas,
launch agents or production routes.

## Host integration

Create `GovernedCueCoordinator(existing_engine, enabled=False)` beside the existing
governed dispatcher. The coordinator is not an authentication endpoint: a trusted
host must issue and check the existing trainer/evaluator/operator/runtime/auditor
capabilities. Do not expose capability issuance, approval methods or SQL to agents.

1. Register a `ModelProfile` with exact provider, model revision, tokenizer revision,
   template revision and supported cue modes. An unspecified capability means no
   cue. Provider aliases and silently updated tokenizers require re-evaluation.
2. Pin a `ModelParity` inference configuration and disjoint `DatasetManifest`.
   The host must deduplicate example content and paraphrase families across all
   partitions and prior studies. IDs alone cannot prove semantic independence.
3. Call `reserve_study(trainer, manifest)` before discovery or spending. Reservation
   is permanent, including failed or interrupted studies. Recovery uses fresh data,
   not another attempt against an exposed holdout.
4. Obtain proposals through `discover_candidates(existing_runtime.execute, ...)`.
   It uses the existing Hermes research role and never receives holdout IDs or
   expected answers. Responses remain untrusted candidate text.
5. Construct a `Cue` for one model/task context. Call
   `propose(trainer, cue, profile, task_type, manifest, generator_id=..., model_config=...,
   reservation=...)`. The content and inference configuration become immutable.
6. Execute `run_experiment` with host-owned provider and independent judge
   callbacks. Explicit permission and low-risk nonclinical scope are required.
   Prefix and instruction requests are distinct; a provider must reject unsupported
   modes rather than emulate a prefix with an instruction. A complete provider
   receipt must echo the executed arm, cue digest, exact model and measured billing.
   Every remote callback must enforce its supplied cost cap, retries and timeout.
7. `evaluate(evaluator, candidate_id, pairs, evaluator_id=...)` validates the exact
   registered model, task, cue and partition and evaluates only once. The host must
   authenticate evaluator identities; strings and local receipts are not signatures.
8. Inspect `status(auditor, candidate_id)` and the existing engine audit stream.
   The screening gate requires at least 30 complete live pairs, a positive accuracy
   gain, descriptive paired p-value at most .05, no candidate safety failures, no
   worsening Brier/mean or p95 latency/mean cost, and independent acceptance. A
   conservative Hoeffding interval accompanies paired accuracy, conditional on
   independent task units; semantic duplicates violate that assumption. These are
   conservative software eligibility rules, not a clinical validation standard or
   a correction for repeated research comparisons.
9. A host operator may call `activate(..., expected_generation=..., reason=...)`
   only after review. Read the current generation with `route_status`. Approval
   expires within seven days, does not activate tool routes, and does not authorize
   clinical use. Staging and provider deployment remain separate operations.
10. Route with `select(runtime_actor, profile, task_type, permission_granted=...,
    clinical=..., risk=...)`. Host task classification is authoritative; never take
    risk or permission labels from model output. Disabled, unsupported, expired,
    unapproved, high-risk or clinical requests use no cue.

## Hermes transport

The actual extension point is `HermesAgentRuntime(..., cue_policy=..., cue_profile=...)`.
The profile must match the configured model/provider and use
`HERMES_CUE_TEMPLATE` (`hermes-json-instruction-v1`). Only instruction mode is
supported by this existing JSON text transport; assistant prefilling is not.

The host callback receives `(role, tenant=..., agent=...)`. It must resolve the
corresponding authenticated runtime actor and call the coordinator with the host's
permission and risk classification. Do not reuse an actor from a different scope.
Return the coordinator's `CueSelection`. Callback errors abort before provider
creation. Invalid, expired or prefix selections preserve the original request.
Returning a no-cue selection denies cue use only: it may still run the explicitly
enabled baseline runtime. A denial of inference execution must raise
`PermissionError` from the host policy before any provider call.

The original role restrictions, text-only/no-tools checks, session quota, isolated
history and strict JSON parsing remain in place. These checks do not replace an
OS sandbox or provider-side billing enforcement. Existing ARC permission and
clinical controls still govern any downstream tool action.

## JEV, feedback and memory

The existing AWIM host can invoke `run_cue_cycle` once per approved research
iteration. It reserves a fresh study before spending, requests one bounded Hermes
proposal, screens it on selection tasks and tests the finalist on untouched
holdout tasks. A successful cycle ends at `awaiting_approval`; it never calls
activation. Synthetic discovery/selection, missing billing, no gain or regression
stops the cycle. Failed reservations remain burned. Discovery must return a
`DiscoveryReceipt` with measured cost; configured adapters enforce the cap before
calling Hermes. This function adds no background scheduler or continuous paid loop.

`CueJevReviewer` reuses NERVE's `JevResearchReviewer` configuration and transport
contract. `review_cues(report, enabled=True)` sends only paired numeric aggregates.
It uses the existing private `TYPESAFE_API_KEY`; no key is written into artifacts.
Redirects are refused. No JEV response can approve or activate a cue. Noul supplies
a probability for the asked judgment, with no separate confidence field
([API](https://docs.typesafe.ai/api), [Noul](https://docs.typesafe.ai/primitives/noul)).

Call `feedback(evaluator, candidate, episode_id=..., safe=..., correct=...)` only
with independently observed outcomes. Any unsafe or incorrect outcome conservatively
revokes that cue and restores no-cue behavior. Duplicate episode IDs are rejected.
Positive outcomes cannot promote a cue. `revoke(operator, candidate, reason=...)`
is the explicit kill switch; stale callbacks must re-resolve current selection
before each new inference.

`export_memory` writes aggregate evidence to `TrustedMemoryLedger` as pending
episodic memory. It never copies raw tasks, generated answers or cue text into
memory. A memory approval cannot authorize cue deployment. Proposal generation
from later feedback must pass a fresh experiment and operator review.

## Rollback and remaining gates

Turn the host coordinator off or revoke its active cue to return to the baseline.
After a safety failure, do not re-approve the same cue version; create a new
candidate with fresh reserved data. Model, tokenizer, template or provider changes
also require fresh evidence. Review the existing `gl_events` CCE audit entries.

The [verification report](verification.md) records actual test results and blockers.
The [paper protocol](reproduction.md) requires a provisioned GPU research host,
pinned author code/weights/datasets, full paired runs and independent grading.
No hosted model benefit, clinical validity, live provider deployment or integration
with a production canary is established by local contract tests.
