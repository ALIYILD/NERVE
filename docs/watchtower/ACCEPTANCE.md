# Evidence-based Watchtower / Guardian acceptance

Implemented on isolated branch `feat/nerve-watchtower`, based on local NERVE commit `23d7900`. **This is a reviewable, locally verified control-plane implementation, not a production-ready deployment or universal shutdown claim.** Existing NERVE source, learning/adaptation settings and deployed services were not modified.

## Actual verification

| Check | Result | Evidence |
|---|---|---|
| Unmodified baseline | 1,124 tests passed | [baseline](evidence/baseline.log) |
| Existing NERVE regression | 1,124 tests passed | [regression](evidence/regression.log) |
| Safety suite | 78 tests passed | [test log](evidence/safety-tests.log) |
| Independent adversarial review | 13 attack tests passed; demonstrated defects repaired | [review](INDEPENDENT_REVIEW.md) |
| Passive CLI collector | Actual read-only SQLite aggregate collection, no source writes | [collector entrypoint](evidence/watchtower-entrypoint.json) |
| Guardian CLI on unprovisioned host | Correctly UNKNOWN, enforcement disabled | [service entrypoint](evidence/service-entrypoint.json) |
| External process demonstration | Real disposable TERM-ignoring child stopped, recreation refused, controlled restart, replay denied | [demo](evidence/disposable-demo.json) |
| Local runtime comparison | 12,000 correct NERVE AST inventories | [performance](evidence/performance.json) |

The single local demonstration measured about 25.6 ms from introducing the fixture invariant violation to verified child stop, and 29.7 ms to first fixture-channel acceptance. Both notification fixtures accepted all ten lifecycle messages. These are not real email/Telegram delivery measurements or a production SLA.

Across 12 paired local blocks, median AST call latency was 18.44 microseconds without collection and 18.94 microseconds with concurrent passive collection (2.71% change). This short synthetic-metadata CPU experiment does not establish production overhead, cost, clinical performance, false-positive rates or false-negative rates. The exact scenario tests establish their own expected outcomes only.

## Mandatory criteria and remaining gates

| Criterion | Evidence/status |
|---|---|
| Preserve normal NERVE behavior | Existing runtime untouched; 1,124 regressions pass |
| No critical regression | Local baseline and safety suites pass; live operation not exercised |
| Learning/adaptation continue | No new calls, approvals or dependencies on their execution paths |
| Usable telemetry | Tenant-scoped aggregate SQLite metadata; undiscovered/uninstrumented semantics UNKNOWN |
| Independent observer checks | Separate probes and external checker implemented; actual Linux/remote provisioning unverified |
| Verified critical containment | Real fixture hash violation and disposable process verified; systemd command/cgroup tests use injected runner |
| Prevent managed recreation | Durable latch/mask/start-block implementation; real disposable supervisor refusal; live reboot/escape tests pending |
| Telegram and email work with test credentials | **BLOCKED:** no test credentials/destinations; provider-contract and failure fixtures only |
| Actual shutdown independently checked | Real disposable child and injected cgroup scenarios; no production workload stopped |
| Human-only recovery | Signed pinned-RSA MFA HTTP test, freshness, scopes and replay verified; real owner IdP not provisioned |
| Agents cannot access emergency credentials | **BLOCKED deployment gate:** independent accounts/mounts/admin ownership not provisioned or penetration-tested |
| Monitoring failure never NORMAL | Staleness, missing signals, audit failure, false healthy aggregate and notification outage tests |
| State-changing actions audited | Hash-chained state ledger, external anchor, controller intent/result journal, notification intents |
| Recoverable | Controlled test restart and recontainment on failure; incomplete live checks deliberately deny recovery |
| Coverage gaps explicit | [Machine-readable inventory](COVERAGE.json), discovery and enforcement reports |

Automatic critical policies are deliberately narrow: fresh independent protected-file pin violations and supervisor-observed restart against a containment latch. Application text, LLM scores and ambiguous metadata anomalies cannot trigger shutdown. Other requested threat families require independently provisioned infrastructure signals; their absence is not treated as proof of safety.

Production recovery is deliberately unavailable with the example configuration: independent deployment provenance/execution permissions and complete cross-source coverage are missing. The core requires these mandatory signals and current Guardian integrity before restarting; the synthetic fixture explicitly supplies synthetic preflight results. Do not remove a failed check to activate production.

Additional outstanding gates: actual unit/cgroup/reboot and escape verification; IAM credential suspension, network egress and deployment-controller enforcement; remote/launchd/CI coverage; separate administration and external health escalation; owner TLS/IdP; off-host immutable audit archival and approved retention/deletion; long-duration performance; clinical dependency and safe-degradation review. Agent/root-equivalent compromise of the safety host is outside this boundary.

No live kill switch, provider notification, production installation, merge or deployment was performed. A draft PR is the delivery target. See [architecture](ARCHITECTURE.md), [threat model](THREAT_MODEL.md), [runbook](RUNBOOK.md) and [implementation plan](IMPLEMENTATION_PLAN.md).

## Notification shutdown follow-up

The safety suite now passes 66 tests. New failure tests establish bounded shutdown with a stalled dispatcher or provider, enqueue rejection after closing, UNKNOWN closing health, and persisted pending delivery recovery. No live provider calls were made. Prior baseline/regression and benchmark results above remain historical evidence; this follow-up changes only the independent notification package and its tests. All PR checks passed for the preceding commit; CI reruns for the follow-up commit.

## Exclusive notification ownership follow-up

The combined safety suite passes 70 tests, including 11 notification tests independently rerun by the alerts specialist. A persistent private sibling lock prevents overlapping notifier owners from racing delivery status updates. A real subprocess test verifies ownership is released on process exit. Initial database-inode locking failed against macOS SQLite locks; the final sibling-lock implementation passes the full suite. No runtime integration, production settings or live notification delivery changed.

## Configuration validation and safe report publication

The safety suite now passes 78 tests. Both deployment examples validate through the CLI without creating state or starting services. Invalid schemas are rejected before runtime side effects, including inventory exclusions, owner scope, alert configuration, duplicate source names, numeric bounds and ambiguous JSON. Pure schema validation does not establish actual path identity or production readiness. Independent review identified predictable report staging that could truncate a monitored input; exclusive random temporary files now preserve the real SQLite source in the regression test. Existing NERVE runtime code remains unchanged.
