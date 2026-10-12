# CCE implementation and verification status

Verified 2026-10-12 from base `a4942ea`, initially in the isolated
`codex/cognitive-cue-engine-20261012` worktree. The follow-up adds
[installed-host wiring](host-integration.md) for application to the NERVE checkout.
The CCE publication excludes unrelated uncommitted adaptation changes. No live
cue has been enabled and no model or clinical deployment has been performed.

## Observed checks

| Check | Observed result |
| --- | --- |
| Complete Python suite after host wiring | **1,027 passed**, 35.928 seconds |
| CCE-specific suite | **82 passed**, including bounded cycle, independent receipts, persistent governance, bridge/native-worker wiring, Hermes and JEV contracts |
| Node checkpoint discovery | **7 passed** |
| `git diff --check` | Passed |
| Offline commissioning CLI | 30 paired tasks / 60 fixture calls, zero external provider calls; candidate rejected, no active cue, pending memory export |

Commands used:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -q
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_cue*.py' -q
node --test tests/test_checkpoint_discovery.cjs
PYTHONPATH=src python3 -m nerve_awim.cue_cli demo --output docs/cce/offline-demo.json
git diff --check
```

The full suite needs permission to invoke its existing nested macOS sandbox.
The initial restricted run had 36 failures and 60 errors, caused by unavailable
nested sandboxing and the starting commit's unconditional import of an absent
optional `adaptation` module. The ARC repair invokes that hook only when an
adaptation object is attached; attached-module errors still propagate. After this
repair and the required test permission, the final full suite passed. Existing
ARC action, approval and verification logic is otherwise unchanged.

Independent review also found and repaired persisted cue-version mutation and a
direct-experiment clinical-label bypass. Regression tests cover both. Later checks
cover executed cue/arm receipt binding, permanent study reservations, stale
inference configuration, expiring evidence, revoked approvals and durable rejection
after a failed study.

Host integration adds tested `cce-status`/inspection/revocation commands, separate
host-selection and worker-application receipts, uncued research controls, and
fresh-only feedback/memory export. The status command was exercised without any
provider call and reported `enabled: false`, `reason: not_configured`.

## Loop ledger

“Verified” below means the stated local software gate, not live model effectiveness
or clinical assurance. The complete objective is **not** claimed complete.

| Loop | Status | Evidence / outstanding work |
| --- | --- | --- |
| 01 Discovery | Verified | [Architecture inventory](architecture.md), real interfaces and dependency boundaries |
| 02 Paper reproduction | Blocked | [Pinned handoff manifest](reproduction-manifest.json); no GPU host, weights, dataset/grader pins or approved compute budget |
| 03 Core | Verified | Immutable registry and persistent version identity, profiles, no-cue routing; core and governance tests |
| 04 Discovery | Partial | Existing Hermes callback and bounded single-candidate cycle tested; author beam search/entropy screening not implemented in NERVE or reproduced |
| 05 Profiling | Partial | Exact model/tokenizer/template bindings and injected tokenizer checks tested; no downloaded real tokenizer or live provider capability probe |
| 06 Evaluation | Partial | Paired reports, exact parity, Brier/accuracy/safety/cost/mean+p95 latency, conservative interval and failure accounting tested; real benchmark extraction/grading and per-rollout token-use instrumentation still require the research adapter |
| 07 Routing | Verified | Actual Hermes instruction boundary tested; unsupported prefixes fall back; provider-specific native prefix transport remains outside this host contract |
| 08 Hermes | Verified | Existing roles, fresh sessions, JSON/no-tools guarantees, bounded telemetry and fail-closed policy errors tested with contract doubles |
| 09 JEV | Verified | Existing transport configuration, numeric aggregate-only requests and advisory probabilities tested; no live JEV call or measured calibration claim |
| 10 Memory | Verified | Existing authority/database/audit and pending trusted-memory export; cross-scope denial, persistence, expiry and outcome revocation |
| 11 Safety | Verified | Clinical/high-risk exclusion, permission gates, cue/receipt tampering and scoped approval tests; clinical deployment remains prohibited |
| 12 Performance/cost | Partial | Call/cost preflight caps, no-provider route selection and local timing measured; no real inference optimization or GPU/provider cost benefit demonstrated |
| 13 Recursive improvement | Partial | One proposal → selection → holdout → pending approval, rejection and baseline rollback tested; no continuous live host installation, retained-capability benchmark or production canary connection |
| 14 API/docs | Verified | Local Python APIs, offline CLI, runbook, full fifteen-loop specification and Claude Code prompt |
| 15 Staging/deployment | Blocked | No target, validated live profile, eligible live candidate or staged traffic approval receipt; no external deployment attempted |

## Measured fixture outcome

Both arithmetic fixture arms answered 30/30 tasks correctly. Their accuracy delta
was zero; descriptive McNemar p was 1.0. Synthetic evidence and no improvement
therefore prevented promotion. The latest local run also failed its latency
comparison. These results describe deterministic fixture plumbing only.

The [machine-readable demo receipt](offline-demo.json) includes the full paired
scores, rejection reasons, conservative uncertainty interval, local routing timing
and SHA256 hashes of the CCE source files. No raw task instructions, expected
answers or generated responses are stored there. Timing can vary between runs.

## Concrete handoff

1. Provision an approved GPU research host and budget; resolve missing immutable
   model/tokenizer/dataset/grader/container fields in the reproduction manifest.
2. Build and validate a native response-prefix adapter separately from the existing
   Hermes instruction adapter. Verify complete rendered prompt tokenization.
3. Execute the [source-backed protocol](reproduction.md), including no-cue and
   published cue arms and independent grading. Attach complete real receipts;
   unit fixtures cannot satisfy that gate.
4. Connect host-authenticated evaluator identities and content/family deduplication.
   Local identifiers and capability objects are not remote authentication.
5. If a live candidate qualifies, prepare an actual staging target and run the
   existing deployment review/canary process. Approval of a cue never grants tool,
   provider or clinician permissions. Keep the current no-cue deployment until
   those gates have evidence.

The [master Claude Code prompt](claude-cli-prompt.md) and [complete implementation
plan](implementation-plan.md) provide the continuation instructions. Missing
external evidence must stay visible rather than being replaced with simulated
success or a blanket “15/15 complete.”
