# NERVE Cognitive Cue Engine: fifteen implementation loops

Specification date: 2026-10-12. This is an executable work plan, not a statement that every item is already complete. Pair it with the [architecture map](architecture.md), [reproduction protocol](reproduction.md) and [Claude CLI master prompt](claude-cli-prompt.md).

**Current implementation evidence:** see the [verification ledger](verification.md)
for completed local gates, partial work and external blockers. The detailed
checkboxes below preserve the original specification; the dated verification
ledger is the current status, not the initial tracking table.

## Evidence and completion rules

Every loop follows implement → test → inspect failures → repair → retest → record gate evidence. Keep a failed test's original output and the subsequent repair result. A loop is complete only when its stated gate has evidence. A source file proves implementation exists; it does not prove model improvement or deployment. Record external blockers with missing resource, attempted check, impact and concrete next action. Do independent work while another gate is blocked.

Initial discovery is documented in this plan. All other checkboxes remain open until the integration coordinator records observed evidence. The coordinator's final status report must distinguish software implemented, locally verified, empirically reproduced and externally deployed.

| Loop | Gate tracking at plan creation |
| --- | --- |
| 01 | Architecture inventory documented; coordinator review required |
| 02–14 | Pending implementation/integration verification |
| 15 | External staging target and approval evidence required |

## 01. Repository discovery and architecture mapping

- [ ] Inspect source, package/dependency files, CI, tests, documentation, deployment files and worktree changes. Identify actual orchestration, Hermes, JEV, provider, memory and learning interfaces.
- [ ] Record an architecture map, dependency inventory and decisions against exact source paths. Identify unsupported integrations explicitly.
- **Test:** Verify each referenced path and public symbol exists; compare diagrams with call sites. Inspect repository status before and after work so unrelated changes remain attributable.
- **Repair:** Replace speculative connections with observed interfaces or explicit requirements. Resolve contradictory versioned docs against current source.
- **Gate:** Coordinator accepts the map; no asserted integration lacks source evidence. [Discovery artifact](architecture.md).

## 02. Paper reproduction and reference baseline

- [ ] Pin paper version, author code, weights, tokenizer, datasets and grader. Resolve the documented proposal-count difference using named experimental variants.
- [ ] Prepare no-cue, selected-cue and available RL baseline manifests. Keep instruction prompting a separate arm.
- [ ] Execute a smoke run, then the frozen complete benchmark on a provisioned research host.
- **Test:** Validate manifest completeness, split isolation, rendered prefix bytes and coverage accounting. Independently grade sampled outputs; reproduce aggregate calculations from receipts.
- **Repair:** Investigate missing samples, tokenizer/template drift and grader disagreements. Rerun invalid experiments under new IDs; never discard poor outcomes.
- **Gate:** Complete matched baseline and cue runs with uncertainty, resource accounting and predeclared replication assessment. Local fixtures alone leave this gate open. [Protocol](reproduction.md).

## 03. Cognitive Cue Engine core

- [ ] Implement typed cue/provenance, model-profile, request and routing-result contracts within `nerve_awim`. Keep CCE optional and default disabled.
- [ ] Bind registry entries to immutable content, model/tokenizer/template revisions, domain, status and evidence references. Use existing memory authority and registered strategies where applicable.
- [ ] Represent no-cue as an explicit valid route. Reject unknown/extra fields and invalid numeric values.
- **Test:** Round trips, duplicate identity/content, version mismatch, malformed data, disabled operation, tenant/agent separation and mutation resistance.
- **Repair:** Fail closed on schema ambiguity; do not repair identity mismatches by silently normalizing cue bytes.
- **Gate:** Deterministic bounded registry and selection behavior with passing contract tests and no mandatory external dependency.

## 04. Cue discovery agents

- [ ] Support imported paper candidates and bounded host-driven proposal/search callbacks. Mark discovery source and algorithm accurately.
- [ ] Use existing Hermes research/skill-builder roles for candidate proposals. Keep host tests and expected answers outside agent context.
- [ ] Add candidate deduplication, explicit call/token caps and rejection reasons. Entropy or agreement may screen candidates, never authorize deployment.
- **Test:** Duplicate candidates, malformed agent JSON, lost provenance, quota exhaustion, injected approval claims and label leakage.
- **Repair:** Quarantine invalid proposals; retain baseline and error evidence. Do not retry beyond reserved budget.
- **Gate:** Discovery produces pending, source-linked candidates within budget. Real beam-search reproduction still depends on loop 02.

## 05. Model and tokenizer profiling

- [ ] Profile provider, exact model revision, tokenizer revision, prompt template, context window and supported prefix mechanism.
- [ ] Record boundary tokenization and distinguish native token prefill, instruction mode and unsupported mode. Never fabricate token IDs from character counts.
- [ ] Invalidate profile-dependent evidence on any identity change.
- **Test:** Leading whitespace/newlines, empty or oversized cues, tokenizer boundary changes, unsupported APIs, stale aliases and missing revisions.
- **Repair:** Return a visible no-cue fallback until a supported profile is verified; require new evidence after drift.
- **Gate:** Exact compatibility matching verified with host callbacks; actual model profiling requires real tokenizer/provider evidence.

## 06. Reasoning evaluation harness

- [ ] Implement paired baseline/candidate evaluation with host-owned independent graders and fixed task denominators.
- [ ] Separate training, selection, regression and one-time final holdout; retain per-problem and per-rollout identifiers.
- [ ] Report accuracy, uncertainty, extraction failure, safety, latency, usage and available costs. Preserve unknown cost/calibration explicitly.
- **Test:** Incorrect but unanimous outputs, missing answers, grader failure, provider failure, uneven coverage, duplicate content, invalid metrics and deterministic seeded summaries.
- **Repair:** Correct leakage/aggregation defects before reusing any evidence; consume a fresh final holdout after adaptive exposure.
- **Gate:** Recomputable paired reports and independent judge tests pass. Fixture accuracy is never reported as model accuracy.

## 07. Cue routing and inference integration

- [ ] Route only approved, compatible, in-scope cues through an explicit existing-host extension point. Preserve task classification and risk authority.
- [ ] Enforce enabled state, task domain, permission, budget, model profile and provider capability before invoking a cued strategy.
- [ ] Pass only bounded prefix metadata to a trusted completion adapter. Return decision provenance and fallback reason.
- **Test:** Disabled/unsupported/revoked/expired/mismatched cases, baseline fallback, unchanged user payload and policies, cancellation and adapter exceptions.
- **Repair:** Revert to registered baseline on safe failures; do not convert unsupported prefill to prompt instructions silently.
- **Gate:** End-to-end host/strategy fixture proves the cue reaches the intended boundary. Live provider support remains separately evidenced.

## 08. Hermes multi-agent integration

- [ ] Reuse pinned `HermesAgentRuntime`, its role allowlist, JSON validation, call quotas and existing proposal flow.
- [ ] Maintain proposal/evaluation/approval separation. Keep tools disabled and provider credentials in the trusted host.
- [ ] Do not invent reasoning, coding or clinical role names absent from the current registry; add roles only through a reviewed contract change when needed.
- **Test:** Correct role routing, fresh sessions, cleanup after failure, bounded outputs, unchanged evidence IDs and inability to activate a cue from agent JSON.
- **Repair:** Reject bad results and close runtime resources. Fix host isolation/configuration independently of CCE logic.
- **Gate:** Mocked contract integration passes; live Hermes operation requires the pinned isolated worker readiness evidence.

## 09. JEV evaluation and uncertainty

- [ ] Reuse optional advisory JEV integration with an explicit allowlisted aggregate schema appropriate to reasoning outcomes.
- [ ] Keep judge confidence, empirical calibration, answer agreement and JEV opinion distinct. Missing uncertainty must be reported as unavailable.
- [ ] Record disagreements between independent evaluation and advisory review without relaxing deterministic gates.
- **Test:** Disabled reviewer, missing credentials, malformed/nonfinite results, timeouts, schema mismatch, privacy boundary and advisory attempt to approve.
- **Repair:** Preserve deterministic verdict when advice is unavailable. Do not reinterpret existing world-model metrics as reasoning performance.
- **Gate:** Offline advisory contract and fail-closed promotion behavior pass; no unsupported calibration claim.

## 10. Memory and adaptive learning

- [ ] Use `TrustedMemoryLedger` for scoped pending proposals and evaluated status. Attach immutable cue/profile/experiment references.
- [ ] Record only host-judged outcomes and bounded nonsensitive metadata. Reuse approval, expiry and revocation behavior.
- [ ] Bind learning context to model/profile revisions; avoid contaminating evidence-handoff or repository-task contexts.
- **Test:** Cross-tenant reads, stale approvals, forged capabilities, restart persistence, duplicate outcomes, expiry, revoked memory and changed evaluation contracts.
- **Repair:** Revoke invalid evidence, preserve audit history and retain no-cue baseline; do not auto-approve replacement memories.
- **Gate:** Persistent scoped proposal-to-evaluation lifecycle passes and unapproved memory never becomes an active cue.

## 11. Clinical safety and security

- [ ] Make clinical/high-risk requests ineligible for research cue application by default. Host permissions and any clinician workflow remain authoritative.
- [ ] Validate bounded cue data; protect against role delimiters, injected authority claims, unsafe serialization, credential leakage and prompt provenance tampering.
- [ ] Keep network/model execution outside unit tests; generated code requires a reviewed sandbox. Use public/synthetic evaluation data.
- **Test:** Clinical and high-risk denial, forged approvals, task-text risk spoofing, tenant confusion, cue tampering, denial-of-service bounds and sensitive telemetry fields.
- **Repair:** Block the affected path, preserve baseline behavior and add a regression test for each demonstrated defect. A lexical cue filter alone is never a clinical assurance claim.
- **Gate:** Security regression suite passes; clinical deployment remains blocked without independent domain validation and clinician approval.

## 12. Performance and cost optimization

- [ ] Bound candidate count, calls, output tokens, elapsed time and concurrency. Avoid provider calls during mere route selection.
- [ ] If caching is needed, key by complete profile/cue/policy identity and scope. Invalidate after revocation or profile change.
- [ ] Measure baseline and CCE overhead plus generation cost in paired runs. Include failures and unsuccessful search costs.
- **Test:** Boundary budgets, retry accounting, unknown prices, cache isolation/invalidation and large candidate inputs.
- **Repair:** Reduce eligible candidate set or return baseline within policy; never weaken safety gates to meet latency targets.
- **Gate:** Local resource bounds pass; real performance/cost benefit requires measured provider/GPU evidence and declared targets.

## 13. Recursive improvement coordinator

- [ ] Connect outcomes → pending candidate → selection tests → sealed holdout → host approval using existing governed learning and bounded improvement interfaces.
- [ ] Protect baseline and previously accepted capabilities with regression tasks. Prevent final holdout recycling across iterations/processes.
- [ ] Keep independent operator authority for canary and release; implement stop, rollback and revision changes without a second controller.
- **Test:** No gain, negative gain, repeated candidates, exhausted budget, stale generation, unauthorized approval, restart and rollback races.
- **Repair:** Stop/reject the candidate, retain evidence and serve the last approved baseline. Never claim recursive improvement from a single favorable fixture.
- **Gate:** Bounded lifecycle demonstrates candidate rejection, explicit approval and rollback through existing controls.

## 14. API, observability and documentation

- [ ] Expose a narrow local Python API and offline CLI/report surface. Extend an authenticated existing host only if its task contract actually supports CCE.
- [ ] Emit version, cue/profile/evidence IDs, fallback reasons, counts and aggregate results; exclude raw task text, responses and credentials by default.
- [ ] Provide architecture, reproduction protocol, runnable examples, migration/rollback instructions and this complete master prompt.
- **Test:** CLI help/report schema, JSON serialization, redaction, imports without optional dependencies and documented example smoke runs.
- **Repair:** Correct stale commands and unsupported claims; separate fixture/live result labels and document failures honestly.
- **Gate:** Reviewable artifacts and tested local entrypoints exist; no implied remote API or hosted deployment.

## 15. Staging and controlled deployment

- [ ] Produce a release manifest containing source revision, test receipts, model/profile pins, selected cue, approval identity, scope, budgets, baseline and rollback target.
- [ ] Run offline → shadow → bounded canary → monitored promotion using the existing lifecycle. Require a provisioned target and applicable operator authorization.
- [ ] Exercise restart, recovery, key/identity binding and rollback before external traffic. Validate no unrelated release is overwritten.
- **Test:** Installation/readiness, disabled baseline parity, canary failure, stale approval, provider outage, budget exhaustion, rollback and monitoring persistence.
- **Repair:** Keep CCE disabled or restore prior release; preserve failed staging evidence. Never mark this loop complete from a local mock.
- **Gate:** Independently observed staging receipts and approved traffic scope. Clinical deployment has an additional independent assurance/clinician gate; it cannot be inferred from research staging.

## Parallel execution and integration

Use independent research/docs, engine and evaluation workers in disjoint files or isolated worktrees. The coordinator owns cross-cutting host integration and final verification. Workers return changed paths, contracts, tests actually run and blockers. Resolve contract disagreements before merging. The coordinator reviews each diff, runs targeted integration tests and the repository suite, then updates evidence status. Never count a worker's unverified assertion as a completion receipt.
