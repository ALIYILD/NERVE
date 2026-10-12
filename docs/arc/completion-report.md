# ARC implementation completion report

Date: 2026-10-12. Scope: loops 00–15 of the supplied handoff, preserved in [implementation-plan.txt](implementation-plan.txt).

Base commit: `ca1e2d92608654ab5d88c2a5866037656caf4a29`.
Final implementation commit: `8f3e1d4851a5e0dc10a41cf80ccf124524e56fbe` (documentation receipts follow in a separate commit).
Branch: `codex/arc-loops-00-15`; checkout: `/Users/aliyildirim/nerve-arc-handoff`.
Evaluated source fingerprint: `4e5fb0e64f7e6c2d8bbfbb365ea3e0082586c988711f6283cc980b23961df5b0`.
Dataset SHA-256: `a40a58c2fbb80ec685d161c558638682644cb8243162f94344343e4283e3cc26`.

## Delivered behavior

NERVE now has an opt-in evidence/decision/outcome layer on its actual governed dispatcher. Immutable scoped snapshots bind validated actions and independent approvals; changed facts, stale evidence, tampering and bypass attempts fail closed. Durable intent, deduplication, cancellation, bounded readback retries, deadline checks and reconciliation prevent blind replay of uncertain effects. Deterministic verification distinguishes transport success from completed objectives. Only independently reviewed, unexpired, unretracted episodes become scoped reusable guidance.

The real local vertical slice parses Python function inventories with the existing AST tool and independently checks them with the existing token verifier. The typed synthetic referral adapter requests missing information, excludes forbidden/foreign evidence, routes contradictions/staleness to review, and prepares source-cited drafts with `submitted: false`. No external submission tool exists.

Three bounded offline strategy candidates can be evaluated against a fixed full-verification comparator. Release-linked manifests separately version schema, prompt, model, policy and strategy; shadow mode, independent review, canary reservations and compatible rollback extend the existing release store. Existing CLI commands expose inspection, audit replay, evaluation, candidate status, reconciliation and rollback. No new scheduler, orchestrator, provider router or external memory database was added.

## Paths and enforcement coverage

- Contracts/evidence/runtime: `src/nerve_awim/arc_contracts.py`, `arc_execution.py`.
- Shared execution boundary: `governed_learning_v20.py`. Raw dispatch without an ARC permit is rejected for enabled contexts, including a bare engine reopened against persisted enforcement.
- Public alternative paths: `shadow_learning_v21.py`, `canary_learning_v23.py`, `promotion_monitor_v24.py`, governed training and candidate evaluation reject ARC-enabled contexts instead of bypassing the guard.
- Provider: `arc_provider.py` wraps the existing host-supplied native Hermes transport with opt-in, bounded structured generation; it does not choose a new provider or spending mechanism.
- Actual workflows: `arc_workflows.py`; evaluation: `arc_evaluation.py`; release/inspection: `arc_operations.py`.
- CLI: existing `scripts/agentos_bridge.py` delegates ARC commands to `arc_cli.py` before unrelated Agent OS recovery/publishing work.

General runtime default is **off**. `arc-run` is explicit opt-in to the bounded local workflow; persisted mode wins after restart. Admin inspection/staging does not enable unused contexts. No production deployment, running dashboard, existing HTTP host or background ARC job was activated.

Standalone simulation/world controllers, MCP/DemoAgentBridge, feedback/parallel/v30 agents, Hermes role adapters, maintenance missions, audit/repository autoresearch workers and external dashboard workers are **not automatically ARC-enabled**. Their existing controls remain separate. Private Python internals and host-issued local CLI capabilities are trusted host interfaces, not a new remote security sandbox. The initial registered effects are local reads and synthetic drafting; external idempotency/status APIs are not claimed.

## Acceptance evidence

The per-loop commands, files, status and limitations are recorded in [implementation-progress.json](implementation-progress.json) and its [readable ledger](implementation-progress.md). Tests cover schema round trips/migration; freshness and changed observations; generated output/repair; scope/approval/bypass; duplicate/crash/cancellation; partial/empty/readback/deadline outcomes; reviewed memory isolation/deletion; real local and synthetic clinical workflows; all critical fact-sensitive pairs; candidate mutation/budget/interruption; staged canary rollback; and process-level CLI behavior.

The original clean baseline passed **875 Python tests and 7 Node tests**. The shared checkout later passed 982 Python tests, but concurrent unrelated adaptation development changed its branch and sources. That shared result is superseded by the isolated final regression recorded below. We preserved the other work, reconstructed only the ARC integration in a separate worktree, and regenerated benchmark and CLI receipts there. No unrelated adaptation or research files are included in this branch.

**Final isolated checks: 961 Python tests passed in 74.760 seconds; 7 Node checkpoint tests passed.** This includes 86 ARC tests, including additive schema migration, plus the 875-test original regression suite. No tests were skipped or disabled. Commands: `PYTHONPATH=src python3 -m unittest discover -s tests` and `node --test tests/test_checkpoint_discovery.cjs`. Captured receipt: [test-results.txt](test-results.txt).

Actual CLI receipts: [local-demo.json](local-demo.json). A real source inventory completes, restart returns the same outcome with one dispatch, inspection is redacted, audit replay has no effects, a shadow release dispatches zero handlers, rollback restores the recorded off mode, and the synthetic draft verifies without submission. The migration test creates historical governed task/outcome/release/event rows and an older manifest schema, proves historical rows survive unchanged, then promotes and rolls back the migrated manifest.

No new dependencies were introduced. Diff whitespace and credential-pattern checks passed. Fixtures are synthetic; no patient data, credentials or hidden reasoning traces were added.

## Benchmark evidence and adverse results

Frozen suite: **60 scenarios**, split **30 development / 15 validation / 15 test**, with 20 disjoint scenario families and three correlated variants per family. This is public synthetic software regression evidence. The baseline is the existing governed dispatcher applied to equivalent local/synthetic tasks; it is not a historical clinical product baseline. Model selection is deterministic and paid inference cost is **$0**.

| Test metric | Existing dispatcher | Structured only | Full verification |
|---|---:|---:|---:|
| Correct task-level behavior | 12/15 | 12/15 | 15/15 |
| Unsupported completion | 3/15 | 3/15 | 0/15 |
| Policy violations | 0/15 | 0/15 | 0/15 |
| Correct abstention | 9/9 | 9/9 | 9/9 |
| Restart recovery | 0/3 | 3/3 | 3/3 |
| Irrelevant wording stability | 5/5 families | 5/5 families | 5/5 families |
| Expected action correctness | 15/15 | 15/15 | 15/15 |

baseline: total test latency 0.2850s; descriptive task Wilson95 interval 0.548–0.930.
structured: total test latency 0.4447s; descriptive task Wilson95 interval 0.548–0.930.
full: total test latency 0.4567s; descriptive task Wilson95 interval 0.796–1.000.

These intervals do not establish population-level performance because within-family cases are correlated. Validation correctness was 9/15, 9/15 and 15/15 respectively; development was 30/30 in every arm. Exact single-fact counterfactual tests are separate from the report's action-correctness proxy.

**No learned candidate improvement was demonstrated.** All three candidates were rejected: default and evidence-first tie the full-verification comparator; conservative has nine validation task-level regressions. No candidate was selected or promoted. Independent review fixed a misleading structured-vs-full candidate comparison, excluded correct abstentions from failure evidence, made policy checks independent of self-reported permission, and preserved prior canary usage on rollback. The corrected reports include these adverse findings; thresholds were not relaxed.

The three-arm gain demonstrates the implemented semantic verification behavior on injected absent-result cases. It does not demonstrate online learning, model training, clinical efficacy or production readiness. The exposed suite is consumed for tuning; reruns in fresh storage are diagnostic reproductions, not fresh holdouts. See [benchmark receipt](smoke-v1-report.json), [candidate receipt](candidates-v1-report.json), and [evaluation protocol](evaluation.md).

## Verification boundaries and remaining blockers

| Capability | Observed status / requirement |
|---|---|
| Local parser, shared dispatcher, SQLite persistence and CLI | Real execution verified |
| Hermes/native provider adapter | Offline injected-transport tests passed; no live inference run. Existing UTC daily allocation was already reserved; no paid fallback used |
| DeepSynaps referral API | No usable contract/integration environment found; typed synthetic boundary implemented. Requires authorized API contract/environment for live verification |
| Candidate improvement | All candidates rejected; new failure evidence and independently reviewed fresh families needed before another promotion claim |
| Production/clinical activation | Not authorized by this handoff and not performed; requires domain review and deployment-specific operational validation |
| Model training | Optional later work; not launched or required for this milestone |

Future network handlers must enforce their own I/O timeouts and implement supported idempotency/status lookups. Runtime deadline checks bound admission and reject late verification; they cannot interrupt an arbitrary synchronous callback. Audit retention has no new automatic purge job; reusable guidance expires/retracts/deletes in the shared store, with no external derived index created. A real integration needs its authorized retention policy. These limits are explicit rather than replaced by mocked live claims.

## Reproduction and rollback

```sh
cd /Users/aliyildirim/nerve-arc-handoff
PYTHONPATH=src python3 -m unittest discover -s tests
node --test tests/test_checkpoint_discovery.cjs
ARC_STATE=$(mktemp -d /private/tmp/nerve-arc-reproduce.XXXXXX)
python3 scripts/agentos_bridge.py arc-run --state "$ARC_STATE" \
  --source src/nerve_awim/repository_agents_v20.py --task-id local-demo --restart
python3 scripts/agentos_bridge.py arc-run --state "$ARC_STATE" --task docs/arc/referral-demo.json
python3 scripts/agentos_bridge.py arc-inspect --state "$ARC_STATE" --task-id local-demo
ARC_EVAL_STATE=$(mktemp -d /private/tmp/nerve-arc-eval.XXXXXX)
python3 scripts/agentos_bridge.py arc-improve --state "$ARC_EVAL_STATE" --candidate-budget 3
python3 scripts/agentos_bridge.py arc-evaluate --state "$ARC_EVAL_STATE" --report "$ARC_EVAL_STATE/report.json"
python3 scripts/agentos_bridge.py arc-candidate-status --state "$ARC_EVAL_STATE"
```

After staging/reviewing a local experimental manifest, restore its recorded compatible mode with:

```sh
python3 scripts/agentos_bridge.py arc-rollback --state "$ARC_STATE" \
  --manifest-id latest --review-ref local-rollback-review
```

This command requires an active manifest; use its explicit ID when multiple contexts exist. It preserves audit history, restores previous canary reservations, cancels pending work and marks in-flight work uncertain. Full staging, side-effect-free replay, uncertain-effect reconciliation, configuration defaults, timeout/backpressure and retention commands are in [runbook.md](runbook.md).
