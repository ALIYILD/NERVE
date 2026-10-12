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

00 in_progress — discovery recorded; baseline Python running; Node checkpoint suite 7/7 passed.
01–15 pending — assigned coherent runtime, workflow and evaluation workstreams. No acceptance claimed yet.

00 passed — baseline875 Python tests and7 Node tests passed; no pre-existing failure. Core runtime01–07, workflows08–10 and evaluation11–12 in progress.
