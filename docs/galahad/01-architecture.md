# Architecture decision: additive synthetic memory gateway

Status: implemented locally; real KV connector admission blocked. Baseline ca1e2d92608654ab5d88c2a5866037656caf4a29, feature/galahad-persistent-memory. Existing source files remain unchanged.

Dependency graph: host-pinned OIDC and offline grants → MemoryService → MemoryGateway → SecureMemoryRetriever → TrustedMemoryLedger → MemoryAuthority. Optional KV provider reports capabilities and compatibility; it does not supply knowledge or grant access. GatewayMemoryObjective → existing RecursiveEvolutionLoop evaluates data-only weights. No agent executor was added.

Ownership: coordinator owns contracts/gateway/integration; provider specialist owns compatibility/provider/preflight; API specialist owns service/client/OpenAPI/security; audit specialist owns repository audit/evaluation/benchmarks. Independent provider specialist reviewed integration and reproduced three bugs before fixes. Files did not overlap.

ADR 1: reuse exact tenant/agent/context ledger scopes, deriving a context digest offline from application, user, clinic, patient and session. This sacrifices broad cross-agent sharing for an auditable existing authority. Sharing needs separately issued host grants, never cache availability.

ADR 2: CPU-first text-only prefill, no invented Galahad deposit/restore methods. Verified upstream connector configuration is documented; unknown compatibility always prevents restoration. Even installed packages do not open runtime admission.

ADR 3: preserve existing pending/approved/rejected/superseded/revoked states and approval capability. There is no public approval endpoint. Evidence is encoded as JSON data, not instructions. This does not solve downstream prompt injection.

ADR 4: trusted host service; SQLite quota triggers cover concurrent database writers, while service rate limits and host capability revocation remain process-local rather than durable network grants. No clinical data, automatic promotion, remote shell or deployment.
