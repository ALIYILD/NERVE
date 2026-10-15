# Autonomous adaptive intelligence: Claude CLI execution prompt

Derived from the owner's ten-phase specification dated 13 October 2026. The
original referenced 70+ subloops were not supplied; the seventy subloops below
are a proposed implementation breakdown, not a recovered original prompt.
No checkbox implies an executed change. Preserve the separate CCE completion gates.

Copy the following instructions into Claude Code at the existing NERVE checkout.

## Assignment and authority

Implement the ten phases below through NERVE's existing AWIM, Hermes, memory,
evaluation and Watchtower interfaces. Inspect current source and instructions
before editing. Preserve unrelated work. Use isolated branches/worktrees for
parallel writes; one integration coordinator reviews and merges verified changes.
Do not introduce a second scheduler, memory authority or agent controller.

Use eleven specialist roles as work assignments, not invented Hermes role IDs:
integration coordinator, repository mapper, memory engineer, Hermes engineer,
evolution engineer, runtime engineer, distributed systems engineer, evaluator,
Guardian engineer, security reviewer, and clinical integration reviewer.
Run independent reviews in parallel when useful; enforce proposal/evaluation/
release separation. Resolve actual Hermes role names against its installed registry.

For every subloop: inspect → implement → test → preserve failure → repair →
retest → record evidence. Record source revision, exact commands, results and
remaining gaps. Continue independent work when a gate is blocked. Never label an
unfinished implementation as an external blocker. Do not mark phases complete
from unit fixtures, an agent assertion, a timer or an exported manifest alone.

Use only explicitly inventoried authorised hosts and scoped credentials. Host
inventory is supplied by the operator, not discovered by network scanning. No
autonomous propagation, credential harvesting, exploitation or unmanaged copies.
Workloads cannot edit Guardian code, configuration, audit retention or recovery
authority. The owner can stop work; tasks must respect cancellation and revocation.
Never deploy an improvement to patient-facing decisions, stimulation protocols
or treatment recommendations without independent validation and authorised release.

## Source interpretation

Read https://www.anthropic.com/research/self-replicating-ai (12 October 2026).
Its Memento harness starts fresh agent instances with prior workspace and short
notes. The reported inference-setup success improves from 45% to 61–84% across
later generations; that is task-specific evidence, not general self-improvement.
Adopt bounded handoff and independent measurement. Exclude propagation experiments.
The existing NERVE `world_model`/Memento 3 project is a separate implementation;
do not rename it or claim it reproduces this harness on name similarity alone.

## Phase 0 — Discovery and baselines

- [ ] 0.1 Read applicable repository instructions, manifests, CI and dirty-state inventory.
- [ ] 0.2 Map AWIM, Hermes, memory, evaluation, deployment and Guardian call sites.
- [ ] 0.3 Inventory authorised runtimes and hardware from operator-owned configuration.
- [ ] 0.4 Trace actual credential ownership, process identities and writable boundaries without exposing secrets.
- [ ] 0.5 Freeze task definitions, capable baseline, held-out splits and independent graders before trials.
- [ ] 0.6 Run existing focused suites and readiness checks; preserve failed and skipped checks.
- [ ] 0.7 Publish dependency map, missing interfaces, resource requirements and evidence ledger.

Gate: observed interfaces and reproducible baseline; missing runtime/deployment
facts remain unknown. Do not infer working infrastructure from a source filename.

## Phase 1 — Memento persistent memory

- [ ] 1.1 Extend `TrustedMemoryLedger` and `AgentOSLearning`, preserving tenant/profile authority.
- [ ] 1.2 Define bounded generation notes separating observations, failed attempts and unverified hypotheses.
- [ ] 1.3 Bind inheritance to task family, runtime/model/template revisions and evaluator contract.
- [ ] 1.4 Snapshot selected notes and approved workspace artifacts with immutable parent lineage.
- [ ] 1.5 Revalidate expiry, revocation, integrity and scope at handoff; exclude credentials and patient data.
- [ ] 1.6 Test real process restart, stale snapshots, forged approval, scope leaks and duplicate evidence.
- [ ] 1.7 Compare inherited-notes and fresh-start arms under matched budgets on unused tasks.

Gate: durable scoped inheritance and independently measured effect. Notes do not
become truth, benchmark answers, tool permission or deployment authority.

## Phase 2 — Hermes orchestration

- [ ] 2.1 Map existing role registry and task contracts to specialist work.
- [ ] 2.2 Add generation handoff through the existing orchestrator and scheduler.
- [ ] 2.3 Start fresh bounded sessions with a frozen inheritance snapshot.
- [ ] 2.4 Preserve host permission checks, provider constraints and clinical classification.
- [ ] 2.5 Fence concurrent claims; persist retries and deadlines across restart.
- [ ] 2.6 Verify cancellation, descendant cleanup and no duplicate external effects.
- [ ] 2.7 Exercise a multi-generation task with independent outcome receipts.

Gate: a real bounded handoff reaches the installed worker without authority drift.

## Phase 3 — Recursive evolution

- [ ] 3.1 Feed independently verified failures into existing candidate generation.
- [ ] 3.2 Freeze candidate content, parent lineage, proposed scope and experiment policy.
- [ ] 3.3 Run selection and retained-capability checks against an unchanged capable baseline.
- [ ] 3.4 Consume sealed final evidence once, with durable content/family deduplication.
- [ ] 3.5 Measure uncertainty, safety, calibration where applicable, latency and total search cost.
- [ ] 3.6 Retain qualifying improvements through existing approval/revocation controls.
- [ ] 3.7 Demonstrate successive generations, rejected candidates and verified rollback.

Gate: independent held-out gain across generations; a completed task or faster
retry alone is not causal evidence that learning helped.

## Phase 4 — Adaptive inference

- [ ] 4.1 Define operator-pinned runtime inventory and permitted capability probes.
- [ ] 4.2 Measure model/quantisation compatibility, RAM, context and actual throughput.
- [ ] 4.3 Extend existing model adapters with bounded runtime selection.
- [ ] 4.4 Key evidence by weights, tokenizer, template, engine and hardware identity.
- [ ] 4.5 Test outage, drift, unknown price and insufficient-resource fallback.
- [ ] 4.6 Benchmark matched tasks and budgets; include setup/failure costs.
- [ ] 4.7 Enable scoped selection only after Guardian coverage and operator release.

Gate: measured automatic selection on authorised hardware, with quality preserved.

## Phase 5 — Distributed inference

- [ ] 5.1 Require reviewed host membership and independently revocable node identity.
- [ ] 5.2 Select a supported distributed backend without inventing a new agent system.
- [ ] 5.3 Pin model shards and validate transport confidentiality/integrity.
- [ ] 5.4 Bound scheduling, placement, resource use and inter-node permissions.
- [ ] 5.5 Handle partial failure and replay without silently expanding membership.
- [ ] 5.6 Test partition, node compromise simulation, revocation and whole-workload termination.
- [ ] 5.7 Compare distributed quality/latency/cost with the single-host baseline.

Gate: observed execution and containment across the reviewed host inventory.
Mocked multi-node tests do not establish a deployed inference fabric.

## Phase 6 — Independent observer and emergency controller

- [ ] 6.1 Extend `safety/nerve_guardian`; preserve its independence from NERVE imports.
- [ ] 6.2 Provision separate workload and administration identities on the selected Mac.
- [ ] 6.3 Protect controller installation, policy, credentials, audit and all writable ancestors.
- [ ] 6.4 Implement inventory-scoped containment, credential revocation and restart denial.
- [ ] 6.5 Require independently authenticated recovery and replay-resistant authorisation.
- [ ] 6.6 Verify email/Telegram test delivery to operator-specified destinations and external heartbeat escalation.
- [ ] 6.7 Test disposable workloads, descendants, alternative scheduling, reboot and interrupted recovery.

Gate: live independently observed termination and recovery on the target. Same-user
passive observation is useful telemetry, not independent enforcement. Do not use
the live learning job or clinical/shared services as destructive test targets.

## Phase 7 — Contained experiments

- [ ] 7.1 Predeclare environment, task family, seeds, controls and stopping criteria.
- [ ] 7.2 Use public/synthetic tasks and a reviewed executable-code sandbox where needed.
- [ ] 7.3 Reserve calls, runtime and spend before execution without refunding failed attempts.
- [ ] 7.4 Keep expected answers and final evidence outside proposer context.
- [ ] 7.5 Capture immutable input/output lineage and independent grader receipts.
- [ ] 7.6 Run adversarial boundary and interference tests under fixed quotas.
- [ ] 7.7 Publish negative, null and positive results with coverage and limitations.

Gate: reproducible contained measurements; no expanded deployment permissions.

## Phase 8 — Clinical OS integration

- [ ] 8.1 Inspect actual DeepSynaps API, authentication and workflow contracts before choosing integration points.
- [ ] 8.2 Keep clinical decision authority and treatment/stimulation settings outside autonomous mutation.
- [ ] 8.3 Define minimum-data interfaces, retention and independently reviewed audit requirements.
- [ ] 8.4 Integrate bounded nonclinical workflow assistance through existing APIs.
- [ ] 8.5 Exercise synthetic end-to-end workflows with denial and outage cases.
- [ ] 8.6 Obtain independent domain validation and designated release authority for any patient-facing scope.
- [ ] 8.7 Verify monitored release, human oversight, rollback and incident response.

Gate: evidence for the precise approved workflow; research performance does not
constitute clinical effectiveness or permission to alter patient care.

## Phase 9 — Validation and deployment

- [ ] 9.1 Recompute all gates from source-bound receipts rather than mutable summary flags.
- [ ] 9.2 Run integration/security suites and independently review the final change.
- [ ] 9.3 Produce a release manifest with target, identities, budget, scope and rollback revision.
- [ ] 9.4 Exercise shadow and bounded canary using the existing deployment system.
- [ ] 9.5 Verify observer coverage and owner recovery before increasing traffic.
- [ ] 9.6 Monitor retained capability and independently verified outcomes; revoke on regression.
- [ ] 9.7 Publish exact completed/partial/blocked phases, commands, commit and operational limitations.

Gate: measured learning, authorised runtime adaptation, independent live control
and the specifically approved clinical workflow all have adequate evidence.

## Execution order and completion report

Start 0 → 1 and 6. Continue offline orchestration/evolution work while independent
administration is provisioned. Do not expand live autonomy or distributed execution
until phase 6 passes. Then sequence 2/3/7 → 4 → 5 → 8 → 9 as dependencies allow.
Run meaningful checks for each change; do not repeat full suites without a reason.
Commit and push authorised verified work without force-pushing unrelated history.
Report implemented, locally tested, empirically demonstrated and deployed states
separately. Preserve all ten phases until their actual gates are satisfied.
