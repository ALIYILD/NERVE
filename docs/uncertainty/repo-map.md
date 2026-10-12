# Uncertainty integration discovery

Starting commit: `57074d9` (verified ARC handoff), branch `codex/uncertainty-integration`, isolated checkout `/Users/aliyildirim/nerve-uncertainty`. Initial tree clean. No applicable AGENTS.md found in the checkout or its user-directory parent. CONTRIBUTING requires Python unittest discovery and Node checkpoint tests. Core dependencies remain Python stdlib, with existing optional OIDC crypto and MCP SDK for interoperability tests.

## Baseline and existing boundaries

The exact starting implementation passed 961 Python tests (74.760s) and 7 Node checkpoint tests in the immediately preceding ARC handoff; `docs/arc/test-results.txt` records that evidence. No known baseline failures. Reuse this observed baseline instead of silently counting skipped checks as passes. Final integrated regression will rerun after changes.

| Boundary | Existing component | Planned extension |
|---|---|---|
| Host identity/permission | GovernedLearning LearningAuthority/LearningActor | Existing issued role capabilities; no remote authentication claim |
| SQLite and events | GovernedLearning._db, gl_events | Additive uncertainty tables in same store, explicit disposable migration |
| Decision execution | GovernedLearning.execute; ARC guard; shadow/canary/promotion alternative paths | Restrictive revision-bound uncertainty gate; never grants permission |
| Evidence and episodes | ARC immutable snapshots/outcomes, scoped memory_v18 | Claim/source links, reviewed uncertainty envelope and authoritative retrieval |
| Hermes handoff | hermes_learning.propose_and_evaluate | Mandatory scoped state across research -> skill builder -> evaluation |
| Agent OS memory/receipts | AgentOSLearning.recall/observe | Host adapter, preserve conflict IDs instead of trusting recalled text |
| Existing candidate/release | ARC bounded evaluator and manifests; improvement_loop | Additional conflict eligibility, preserve ledger on rollback |
| Memento workstream | Separate `/Users/aliyildirim/nerve-memento3` worktree, `world_model` package in progress | Wait for committed readiness; wire actual rulebook/planner/registry/coordinator |
| Task adaptation workstream | Separate `/Users/aliyildirim/nerve-review`, adaptation modules in progress | Wait for committed readiness; combine compatible runtime hooks and verify gates |

The other two windows currently have uncommitted changes. Do not copy live partially edited modules or claim combined verification before integrating completed commits. Their branches and source files remain untouched by this workstream. Uncertainty implementation proceeds independently while waiting.

Existing robot sensor-uncertainty modules and simulation controllers do not provide a persistent epistemic claim/conflict ledger. They remain distinct. Existing MCP, background workers and production deployments are not automatically enabled; final report must enumerate exact opt-in coverage and remaining unsupported entrypoints.

## Research boundary

Read the full supplied specification and inspected primary paper https://arxiv.org/html/2610.12360v1 and authors repository https://github.com/KaiserWhoLearns/EpistemicHumilityLLMAgents. The design treats bounded checking as an attempted investigation, never automatic factual resolution. No third-party code or dataset imported; no transferred performance claims or inferred hidden reasoning.

## Working order

20 contracts/ledger and 22 verification share a durable store; 21 propagation, 23 policy and 24 output share an authoritative adapter; 25 evaluation/CLI uses the same runtime. Maintain loop checkpoints and tests. Wait for other-window commits before Memento/adaptation merge, resolve hooks in this isolated tree, run combined acceptance/CI, retain unresolved blockers honestly. No live provider, patient/device actions or production deployment authorized by this handoff.
