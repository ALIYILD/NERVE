# ARC implementation progress

Base: `ca1e2d92608654ab5d88c2a5866037656caf4a29`; branch `main`; initial checkout clean.
The full supplied plan is preserved in [implementation-plan.txt](implementation-plan.txt).
Machine-readable resume state: [implementation-progress.json](implementation-progress.json).

## Integration mapping (loop 00)

| Responsibility | Existing implementation | Extension / coverage |
|---|---|---|
| Scoped host capabilities | `governed_learning_v20.LearningAuthority`, `LearningActor`; OIDC `identity_v26`, `oidc_v27` | Reuse host roles; no replacement identity service |
| Registered tools and dispatcher | `RegisteredStrategy`, `GovernedLearning.execute`, `_registry` | ARC guarded dispatch for explicitly enabled contexts |
| Durable store and release history | `GovernedLearning._db`, `gl_state`, `gl_releases`, `gl_events` | ARC tables in same SQLite store; no second memory database |
| Existing real local task | `repository_agents_v20.ast_inventory`, `token_inventory` | Actual read-only function inventory and independent verification |
| Scoped memory | `memory_v18`, `adaptive_memory`, governed outcome ledgers | Reviewed ARC episodes in existing governed store |
| Provider | `agentos_bridge.native`, Hermes isolated worker; `ChatCompletionsPlanner`; optional `jev_review` | Reuse configured bounded callback; deterministic offline fixture; no paid calls |
| Existing release controls | `GovernedLearning.activate/rollback`, canary v23, promotion monitor v24, bound host v26 | ARC mode/version manifest tied to existing operator capability and events |
| CLI / background cycle | `scripts/agentos_bridge.py`, 900-second local launch agent | Extend CLI; no new daemon or automatic production activation |
| HTTP | `RepositoryHost`, `BoundRepositoryHost`, `serve_repository_host_v25.py` | Existing OIDC/grants retained; ARC opt-in scope coverage documented |
| Clinical API | No clinical referral or DeepSynaps API contract in this checkout | Typed synthetic boundary only; external integration remains blocked |

### Entry-point inventory and boundary

The shared governed dispatcher is the enforcement target. Existing HTTP shadow/canary paths call registered handlers through `shadow_learning_v21`, `canary_learning_v23`, and `promotion_monitor_v24`; each must be inspected for bypass before claiming coverage. Older standalone simulation controllers (`runtime_v28`, WorldCore), `DemoAgentBridge.execute_plan`/MCP tools, `FeedbackAgentCoordinator`, `BoundedParallelAgents`, v30 agents, Hermes role adapter, Agent OS maintenance missions, audit/repository research runners, and external dashboard workers are independent historical execution paths. They are not automatically upgraded or clinically authorized by the new path. Existing protections remain enabled. Final coverage report will identify exact enforcement.

Network effects are isolated in configured provider adapters (`llm_agent_v14`, Jev optional/smoke/batch), Hermes transport (`agentos_bridge`, worker), maintenance metadata curl, OIDC verification and pilot HTTP utilities. GitHub recursive research cron and local Agent OS launch agent remain separate existing schedules, with no ARC jobs added.

Dependencies: Python standard library for core; existing optional `PyJWT[crypto]>=2.10,<3` for OIDC and pinned MCP for interoperability. No new dependency proposed. CONTRIBUTING requires Python unittest discovery and Node checkpoint tests. CI also runs research benchmarks and packaged-service checks; applicable existing gates will be retained and reported.

Research inspected: https://arxiv.org/html/2610.12386v1 and https://arc-robot-reasoning.github.io/. This implementation adapts action-grounded summaries and behavioral tests; it does not reproduce robot training or imply clinical efficacy.

## Loop ledger

All unblocked implementation loops completed. Final isolated aggregate regression: 961 Python tests and 7 Node tests passed. Full commands, limitations and resumable status are in the JSON ledger.

| Loop | Status | Evidence |
|---|---|---|
| 00 | passed | Clean baseline: 875 Python and 7 Node tests |
| 01 | passed | `test_arc_runtime.py` — Round trips, bad versions, scope, argument validation; additive schema migration tested separately. |
| 02 | passed | `test_arc_runtime.py; test_arc_review.py` — Hash/time snapshots, freshness and changed-evidence rejection; adversarial wording cannot authorize tools. |
| 03 | passed | `test_arc_provider.py; test_arc_runtime.py` — Existing native transport adapter, one repair, invented evidence/invalid output/outage blocked; valid proposal dispatched. |
| 04 | passed | `test_arc_runtime.py; test_arc_review.py` — Scoped capabilities, bound independent approval, tamper/expiry/bypass rejection at dispatch. |
| 05 | passed | `test_arc_runtime.py` — Concurrent deduplication, persisted intent, cancellation, restart and uncertain-write reconciliation. |
| 06 | passed | `test_arc_runtime.py` — Empty/partial outcomes, five-decision bound, two read retries, bounded backoff/deadline and no-progress stop. |
| 07 | passed | `test_arc_review.py; test_arc_runtime.py` — Scoped reviewed examples; expiry/retraction/deletion exclude guidance; audit provenance retained. |
| 08 | passed | `test_arc_workflows.py; test_arc_cli.py` — Actual AST inventory and independent token verification through GovernedLearning; real CLI receipt local-demo.json. |
| 09 | passed | `test_arc_workflows.py` — Typed synthetic boundary; missing/stale/conflicting/foreign facts; exact citations; no external submission. |
| 10 | passed | `test_arc_workflows.py; test_arc_review.py` — All six critical fact changes plus irrelevant/adversarial wording and false completion covered. |
| 11 | passed | `test_arc_evaluation.py` — 60 scenarios, family-disjoint 30/15/15; source/hash-bound reports and consumed holdout tracking. |
| 12 | passed | `test_arc_evaluation.py` — Three inert strategies, failure lineage, equivalent full/full comparison, regressive/tied candidates rejected; interruption/budget guards. |
| 13 | passed | `test_arc_review.py; test_arc_cli.py; test_arc_schema_migration.py` — Existing release-linked manifests, shadow no effects, independent review, bounded canary, compatible rollback preserves previous budget. |
| 14 | passed | `test_arc_cli.py; test_arc_review.py` — Existing CLI extended; scoped redacted inspection/replay, evaluation, candidates, release, reconciliation and rollback. |
| 15 | passed | 961 Python tests, 7 Node tests; migration, actual CLI receipts, source review and completion report |

Loops were implemented in parallel workstreams; this integrated checkpoint records their completed acceptance results. Existing baseline and focused gates were not weakened. External-provider and real-clinical verification remain explicitly unavailable, rather than represented as live tests.

Unrelated adaptation/configuration files appeared during implementation and are excluded from ARC commits.

## Final isolation checkpoint

Final checkout: `/Users/aliyildirim/nerve-arc-handoff`, branch `codex/arc-loops-00-15`, implementation commit `8f3e1d4`. Concurrent unrelated work changed the original checkout and introduced adaptation hooks during integration. That work was preserved in place; this isolated branch excludes its hooks and files. The full regression and benchmark receipts were rerun on the isolated ARC implementation. See [completion-report.md](completion-report.md) for final results, external blockers and reproduction commands.
