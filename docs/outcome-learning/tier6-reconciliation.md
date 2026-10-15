# Orchestrator reconciliation with Tier 6

Reference implementation: `feature/galahad-persistent-memory`, inspected at
`cb65c81`. This reconciliation does not declare the Tier 6 roadmap complete.
The orchestrator is a coordinator of existing authorities, not another evaluator,
experience database, release controller, or source of clinical reward.

## Concept mapping and canonical stores

| Orchestrator concept | Tier 6 authority | Canonical record; reconciliation |
|---|---|---|
| Goal | Loop 40: registered hypothesis, frozen study and acceptance rule | Galahad study protocol in `claim.sqlite` and external single-use claim journal. Orchestrator `registration.json`/`goal.json` track execution and references only; they cannot change the study, control floor or verdict. |
| Evaluate | Loop 40 selection gate | `scientific_candidate_v3_study.validate_receipt` reconstructs the dev protocol, every score, controls and `_summary` gate from the consumed receipt. `claim.sqlite` is the study ledger; byte-matched `report.json` is its published evidence. The orchestrator must not call its own retrieval/hash scorer or substitute accuracy thresholds. |
| Switch | Loop 42 shadow/canary allocation after the required Loop 40/41 review path | The governed runtime/skill authority, not an orchestrator checkpoint. The roadmap's full clinical shadow/canary path is not established by the sandbox implementation. No Tier 6 runtime switch or store mutation is authorized in this run. |
| Monitor | Loop 42.1–42.3; observations feed Loop 37 | Canonical scoped episode journal plus governed runtime receipts when those integrations exist. Sandbox monitoring receipts are test artifacts, not signed clinical outcomes or evidence of completion of Loop 42. |
| Rollback | Loop 42.3 | Governed runtime policy state and its restart-safe journal are authoritative. A sandbox `active_strategy` field cannot restore or override a Tier 6 deployed policy. This run does not enter that path. |
| Detect-change | Loop 43.3 (AWIM extension); may request Loop 40 reevaluation, with Loop 42.3 handling deployment regression | Reads scoped Loop 37 evidence; detector state is derived. `docs/galahad/65-experience-store-awim.md` explicitly tracks 43.3 as remaining work beyond the saved 36–45 plan. The four-observation sandbox detector is not a completed Tier 6 drift-sensing implementation. |
| Outcome record | Loop 37 Experience Store | `memory_gateway/experience_store.py` append-only, capability-scoped `experiences.sqlite` is canonical for imported episodes. `ExperienceStoreV2` specifically handles format-probe records; it is not a universal v3 importer. Raw v3 outcomes remain canonical in their validated study ledger/report until an authorized importer supports them. JSONL exports and orchestrator summaries are projections, not second stores of truth. |

There is no universal interchangeable SQLite store. **Loop 37 owns durable
episodes; Loop 40 owns scientific study claims and selection evidence; the
governed runtime owns activation/rollback.** The orchestrator owns only scheduling
and checkpoint metadata. This run does not import or rewrite v3 outcomes, create
rewards, change active policies, or silently invent a Loop 42 store.

Sources: Galahad `docs/galahad/plans/nerve-self-learning-loops-36-45.md`
(Loops 37, 40, 42), `docs/galahad/65-experience-store-awim.md` (43.3 and journal
boundaries), and `docs/galahad/76-policy-scoped-abstention-v3.md` (current dev gate).

## Identity correction and registered goal

`01c5346e707c54689f73e64a0b25238a76864f628d5e51c2b770e16d140c8179`
is the saved **Tier 6 plan** SHA-256, not the task-bank manifest. It is retained
as the goal's plan binding. The actual v3 study bank-manifest SHA-256 is
`e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6`.
The registered dev roster digest is
`9fcedd8027a4bbace580f5752e5aeee6f653d75e7cf5d022feac683375acc089`.
The two identities must not be relabeled as one another.

Register exactly one reconciliation goal against that bank's **dev** split and
the existing 100-item v3 roster. The incumbent is the frozen
`compact_with_abstain` development baseline—not an assertion about production's
active policy. Controls are `always_abstain`, seeded `random`, and `baseline`.
The canonical target floor is Galahad's preregistered rule: candidate strict
correctness must exceed all three controls, with no stratum regression against
baseline. No orchestration-specific gain threshold is applied.

Evaluate by revalidating the completed dev study through its existing public
`validate_receipt` API. This reconstructs the gate, rather than trusting copied
summary numbers or launching another 160-call experiment. A passing dev verdict
means **candidate selected for review**, not promotion. Generalization remains
`insufficient_power`; the full Loop 40 holdout/CI requirement is outside this run.

## Boundaries of this run

**Discovery deviation:** the initial repository-wide `rg` search traversed
documentation/evidence paths, including holdout-related reports present in the
Galahad worktree. This was broader than the requested boundary. No task-bank
holdout or private seed file was opened. Subsequent inspection used named dev
sources only; the evaluation worker explicitly denied holdout/seed paths.
The evaluation is dev-only, but this work must not be represented as perfectly
isolated from all holdout-related artifacts during initial discovery.

- No task-bank `holdout()` or `status()` calls; no holdout or seed-file opens.
- No new inference, metadata, preload, subprocess, or network calls in the gate worker.
- Only the public dev `validate_receipt` entrypoint is invoked. Its transitive
  historical verification helpers may replay existing registration/import checks;
  they do not execute a new study, import new records, or activate a policy.
- Existing dev evidence is checked for byte and modification-time preservation.
- Galahad's unrelated working-tree edits and holdout artifacts are untouched.

## Executed result

One goal is registered in
`/Users/aliyildirim/nerve-research-runs/orchestrator-tier6-dev-reconciliation`.
Its single `evaluate` subloop delegates to the canonical Galahad dev verifier in
an isolated Python worker. The goal's control floor is the original study rule.
The worker forbids network/subprocess dispatch and holdout/seed opens. It opens
canonical SQLite databases read-only, makes transient in-memory copies for legacy
idempotent schema initialization, and verifies those copies are logically unchanged.
This is a compatibility boundary around the verifier, not a replacement scorer.

The first attempt blocked on a read-only SQLite initialization statement before
returning a verdict. That checkpoint is preserved as `first-attempt-blocked.json`.
The same goal was explicitly reconciled for one compatibility retry; no second
goal or study was registered and no inference was repeated.

**Selection: candidate v3 over the frozen incumbent, for review only.** The gate
returned `candidate_requires_review`, with `generalization_verdict=insufficient_power`.

| Canonical gate arm | Strict correct / dev tasks |
|---|---:|
| Candidate v3 | 99/100 |
| Incumbent (`baseline`, compact-with-abstain) | 40/100 |
| Always-abstain | 40/100 |
| Seeded random | 29/100 |

There are 59 paired strict-score gains, zero paired losses, and 41 ties; no
stratum loses strict correctness against the incumbent. The candidate still
answers one entity-decoy item incorrectly where the incumbent abstained. The
pass must not be described as absence of harmful-answer risk or clinical efficacy.

The existing published dev report SHA-256 is
`ae24bfac8beb3fe37e3eb61efda5c8e2e5e9ac761e5a2b4c785e3acc7d9feea7`.
Verification checked 36 canonical files without changing bytes or modification
times, and 1,559 transient SQLite connections without logical changes. New model
calls: **0**. Task-bank holdout access: **none**. Promotion and production activation:
**not authorized and not performed**. This is reuse and validation of the
completed dev evidence, not a fresh independent experiment.

Reproduce (a completed goal returns its checkpoint without rerunning evaluation):

```sh
python3 scripts/reconcile_tier6_goal.py \
  --galahad-root /Users/aliyildirim/nerve-galahad \
  --research-root /Users/aliyildirim/nerve-research-runs \
  --state /Users/aliyildirim/nerve-research-runs/orchestrator-tier6-dev-reconciliation
```

The adjacent `tier6-goal-registration.json` and `tier6-evaluation-receipt.json`
are exported coordination/evaluation references. Canonical scientific outcomes
remain in the Galahad ledger and byte-matched study report described above.
