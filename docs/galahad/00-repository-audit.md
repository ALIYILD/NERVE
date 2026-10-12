# Repository audit — NERVE persistent memory

Inspected 12 October 2026 at base `ca1e2d92608654ab5d88c2a5866037656caf4a29`, branch `feature/galahad-persistent-memory`. Initial worktree clean. This is a separate implementation checkout; existing work is preserved. No production configuration, clinical store, external inference or real patient data was used.

## Environment and discovery

Local interpreter: Python 3.10.0; Darwin 25.5.0 x86_64. Existing main CI uses Python 3.12 on Ubuntu, installs `PyJWT[crypto]>=2.10,<3`, then runs unittest discovery and synthetic benchmarks. Repository has no pyproject/setup packaging declaration; imports use `PYTHONPATH=src`. Optional MCP, Mem0, OIDC, JEV and external agents are installed/injected independently. `deploy/requirements-pilot.txt` and its Linux lock cover the existing authenticated pilot. Existing `.github/workflows/security-coverage.yml` covers dependency/security checks. No AGENTS.md exists in this checkout.

Structural inventory: `src/nerve_awim/` contains versioned research/controller, memory, agent, host, identity and learning modules; `tests/` uses stdlib unittest; `benchmarks/` contains deterministic synthetic studies; `scripts/` contains opt-in research and host commands; `integrations/agentos/` contains external Agent OS integration; `research/` and `docs/` preserve study evidence. `.github/workflows/` includes tests, optional live JEV/LLM, recursive research, checkpoint persistence, security coverage and pilot installation. `deploy/nerve-repository-pilot.service` is an existing hardened loopback-oriented systemd pilot, not a memory service deployment.

## Capability matrix

| Capability | Existing location | Functional evidence | Gaps | Integration action | Risk |
|---|---|---|---|---|---|
| VERIFIED scoped verified memory | memory_v18.py | SQLite proposed/approved/rejected/revoked records; authority require checks in every operation; expiry, forget and status | Tenant/agent scope only; process-local capability authority, no network identity | Gateway wraps ledger, preserving approvals and revocation | Context scope and cache must not bypass ledger |
| VERIFIED lexical retrieval | memory_retrieval_v18.py | SecureMemoryRetriever delegates lexical to ledger | No embedding model | Reuse authoritative retrieval | Relevance does not imply factual truth |
| PARTIAL semantic retrieval | memory_retrieval_v18.py | Mem0 adapter filters scoped approved IDs and ignores provider content | Real Mem0 not installed/validated here | Optional advisory adapter | External provider/query disclosure |
| VERIFIED bounded outcome ranking | adaptive_memory.py | OutcomeMemoryRanker uses host evaluator; deduplicated episodes; rechecks approval after evaluation | Synthetic/public use only; heuristic utility | Reuse, do not create competing reward authority | Causal improvement unproven |
| VERIFIED bounded recursion | recursive_evolution_v19.py | Fixed RetrievalGenome and EvalScore; train/validation gates; final selected/baseline holdout; lineage | Fixed tiny public fixture; no sealed external holdout, no KV objective | Add gateway objective to existing loop | Holdout can be overfit across studies |
| VERIFIED governed promotion | governed_learning_v20.py; shadow_learning_v21.py; canary_learning_v23.py | Separate role authority, frozen candidates, explicit activation, rollback and monitored canary | Research repository tasks, not memory service | Keep unchanged; do not auto-promote | Clinical applicability absent |
| VERIFIED parallel workers | parallel_agents_v11.py | Trusted role map, bounded jobs/workers, ThreadPoolExecutor, failed-batch rejection | No hard timeout or process sandbox | Reuse trusted handlers only | Trusted worker can hang |
| MOCKED general specialists | agents_v30.py; collaboration_v31.py | Typed tasks and provenance; deterministic specialist stubs | No actual clinical reasoning | No duplicate agent fleet | Must not claim clinical capability |
| PARTIAL MCP | learn_mcp.py | Optional SDK; legacy writes disabled by default; inert tool registry | Agent IDs are namespaces, not authenticated principals | Keep existing MCP unchanged | Exposing privileged tools would be unsafe |
| VERIFIED identity component | oidc_v27.py; repository_host_v25.py | Pinned RS256 JWKS, issuer/audience/expiry; independent configured subject grants, roles and limits | No deployed IdP/revocation service; repository host is not memory API | Reuse verifier and host boundary patterns | Must bind clinical context independently |
| VERIFIED research control | worldcore_v20.py; worldcore_recursion_v19.py; runtime_v28.py | Simulated reliability and recovery gates | Not hardware/medical safety | Keep independent from memory | No clinical/actuator deployment |
| PARTIAL advisory JEV | jev_optional.py | Bounded aggregate review, deterministic gates independent | Optional external service not called | Preserve advisory-only role | Model review is not authorisation |
| VERIFIED metadata telemetry | telemetry_v29.py; observed_runtime_v29.py | Bounded event trace and summaries | No persistent memory dashboards | Separate sanitised gateway metrics | Identifiers can themselves disclose context |
| MISSING persistent KV | no existing Galahad connector | No package/hardware/runtime evidence | No verified runtime keying, encryption, restore or deletion | Optional fail-closed provider seam and preflight | Proprietary compatibility/licensing and isolation |
| MISSING Clinical OS memory API | no existing memory HTTP service | Existing task/evidence/readiness host only | Patient/application scope, service contract and clinical validation absent | Synthetic-only separately authenticated service | No live clinical authority |
| PARTIAL deployment/recovery | deploy/; store_recovery_v27.py; pilot_bundle_v28.py | Repository pilot config, backup checks and host tooling | No memory-service deployment or KV operational evidence | Do not alter existing deployments | Backups/erasure require separate verification |

## Call graph and ownership boundaries

`untrusted client -> independent identity verification + configured host grants -> gateway scope/context policy -> SecureMemoryRetriever -> TrustedMemoryLedger -> MemoryAuthority`.

Optional KV eligibility occurs only after fresh approved retrieval and fully known identity. Provider availability is never evidence authorisation. Unknown compatibility causes ordinary approved-text fallback. KV runtime interfaces are owned by the provider workstream, not inferred by gateway/API callers.

`trusted research coordinator -> RecursiveEvolutionLoop -> fixed gateway objective -> approved source pool -> fixed scorer`; evaluation returns `EvalScore`. Preserve fixed candidate schema and train/validation separation; final holdout compares selected and baseline once per study. No execution of generated code, deployment, evaluator mutation or client-supplied rewards.

Implementation ownership is non-overlapping: coordinator owns gateway/contracts/policy/retrieval and API integration; provider specialist owns provider adapters and compatibility tests; audit/evaluation specialist owns this audit and bounded evaluation evidence; security reviewer examines boundaries without parallel edits. Dependencies: audit/baseline first; contracts before provider/gateway integration; gateway before objective/API end-to-end testing; all evidence before release claims.

## Baseline evidence

Started before implementation: `PYTHONPATH=src python3 -m unittest discover -s tests -q`; results recorded below when process completes. The command preserves exact output at `/private/tmp/nerve-galahad-baseline.log` for this machine.

`node --test tests/test_checkpoint_discovery.cjs`: **7 passed, 0 failed**, approximately 1.054 s.

`PYTHONPATH=src python3 benchmarks/v18_memory_retrieval.py`: 10 queries across 5 families. Lexical recall@1 0.5 (exact 1.0; paraphrase 0.0); semantic fixture recall@1 1.0 (answer-keyed mock, not Mem0). Lexical local p50/p95 1.2845/1.7153 ms; semantic fixture 1.4951/1.8331 ms. Cross-tenant provider calls/results both 0. Timing is synthetic local harness overhead under concurrent baseline execution, not inference or GPU performance.

Existing further reproducible commands include `PYTHONPATH=src python3 scripts/adaptive_memory_study.py`, `PYTHONPATH=src python3 scripts/offline_learning_suite.py`, `PYTHONPATH=src python3 -m nerve_awim.recursive_evolution_v19`, and the explicit benchmark list in `.github/workflows/tests.yml`. Optional live workflows were not invoked.

Initial full suite completed before implementation: **875 tests in 85.610 s; 36 subtest failures, 3 errors**. All reported failures are existing AgentOS kernel sandbox probes reporting `sandbox_unavailable`; the three host errors are `PermissionError: Operation not permitted` binding loopback HTTP sockets. These are execution-environment blockers, not passing tests. An approved unsandboxed rerun was started to verify that attribution. Focused existing memory/retrieval suite: **18 passed in 0.156 s**.

Approved unsandboxed rerun: **875 tests passed in 52.565 s**, 0 failures/errors (`/private/tmp/nerve-galahad-baseline-unsandboxed.log`). This establishes the pre-change full baseline and confirms the restricted-run failures were environmental. Focused existing recursion: **29 passed in 3.696 s**. Main CI's Python 3.12/Linux environment remains separately reproducible; local success is Python 3.10/macOS evidence.
