# NERVE ADR-0018 — Memory backend evaluation (10 October 2026)

**Status:** Proposed; no production backend switch authorised. **Decision:** Keep NERVE's own typed, source-linked memory contract as the system of record. Preserve local SQLite for developer/test runs; prefer **PostgreSQL + pgvector** for a future secured service, with optional semantic and temporal memory adapters. Obsidian is a reviewed Markdown view/export, not the authoritative engine. Jev is an optional bounded relevance/conflict scorer, not a data store or security authority.

## Why

NERVE is a provider-independent, open-source multi-agent research coordinator. Choosing Obsidian, Letta, Mem0, Cognee, or Graphiti as its sole source of truth would make agent identity, data locality, security and clinical-use boundaries dependent on a single vendor architecture.

- **Obsidian (obsidianmd/obsidian-api)**: Markdown vault / plugin SDK, ideal for human-curated, explorable memories, not a concurrent authenticated remote agent memory database.
- **Mem0 OSS (mem0ai/mem0)**: best near-term drop-in **semantic memory adapter** for NERVE. Configurable self-hosted LLM, embedder, retrieval and PostgreSQL/pgvector; distinguish OSS features from proprietary managed Graph Memory.
- **Letta Agent SDK / MemFS (letta-ai/letta-agent-sdk)**: promising persistent agent identity, git-backed Markdown context and reflection; integrate only as an optional agent harness, not a dependency for Hermes/OpenClaw/MCP users.
- **Graphiti (getzep/graphiti)**: optional temporal entity/relationship graph for changing world states and provenance-heavy multimodal research, after basic security and recall correctness.
- **Cognee (topoteretes/cognee)**: alternative self-hosted semantic+graph memory worth testing, not selected by headlines or unreplicated vendor benchmarks.
- **Jev (TypeSafe AI)**: fast typed advisor for memory relevance, contradiction triage and candidate promotion review; a separate deterministic policy must authorise memory writes/agent actions.
- **pgvector (pgvector/pgvector)**: embeds vector search in existing PostgreSQL infrastructure, with text search, metadata filters and HNSW/IVFFlat when justified; use exact filtered retrieval as baseline.

Primary research links:
- https://github.com/obsidianmd/obsidian-api
- https://github.com/mem0ai/mem0/blob/main/docs/open-source/configuration.mdx
- https://github.com/letta-ai/letta-agent-sdk
- https://github.com/getzep/graphiti
- https://github.com/topoteretes/cognee
- https://github.com/pgvector/pgvector
- https://typesafe.ai/blog/introducing-system-one-models-and-jev
- https://genai.owasp.org/2026/05/13/memory-is-a-feature-it-is-also-an-attack-surface/

## Code audit (observed as of 10 October 2026)

1. **Trust boundary**: `src/nerve_awim/learn_mcp.py` exposes `record_experience` and `rate_experience` with caller-supplied `agent_id`. The agent ID is a namespace, not an authenticated principal. The service is currently local stdio only; deploying it over network without authentication could allow memory poisoning and cross-tenant access.
2. **No score provenance**: `learn_v31.py` stores `task,outcome,score,created_at` but not evaluator signature, original observation/source hash, approval, revision history or confidence; arbitrary MCP score writes could become ranked recommendations.
3. **Weak retrieval**: `LearningStore.recall` uses literal substring of task names, sorts by individual score, and caps at 20; `EvolutionMemory.select` chooses from that shortlist. Paraphrases and entity/time relationships are missed; utility is not aggregated over all outcomes.
4. **History cap**: `rated_history` returns the 500 latest rated records (up to 1000 configurable) rather than a systematic stratified sample; old-but-important lessons may disappear from selection.
5. **No lifecycle**: no expiry, contradiction/supersession, deletion/forgetting, consent, redaction or verified memory-promotion state.
6. **Performance unknown**: no retrieval recall/precision, p95 latency at scale, concurrent SQLite writer stress, cost/token budget, injection resistance or hard-negative memory benchmarks.
7. **No sensitive-record safeguards**: do not use the public repo or Obsidian vault as a store for medical/patient information.

These are architectural and public-code observations, **not proof of a remotely exploitable deployment vulnerability**. The documented MCP transport is local stdio.

## Proposed v1.8 layered model

- **Working memory**: bounded current context / active reasoning state; ephemeral and not automatically promoted.
- **Episodic memory**: append-only, event sourced observations and independently verified outcomes; tenant/agent/run IDs and provenance on each record.
- **Semantic memory**: de-identified accepted facts/skills with hybrid keyword + vector retrieval, exact policy filters and citeable source references.
- **Procedural memory**: reviewed skill/tool policies, immutable registered capability IDs; no text-to-code execution.
- **Temporal memory**: optional Graphiti-backed fact graph, effective/expiry timestamps, superseded/conflicting relationships.
- **Human review**: approved and redacted Markdown summaries exported to an Obsidian-compatible vault, one-way by default. No automatic bidirectional trust of Markdown instructions.
- **Fast judge**: optional Jev or another typed judge for triage/rerank only, independently evaluated before use.

Data flow: `agent/sensor observation → classify/redact → append event → evaluate against sources → approve → generate searchable summaries & embeddings → hybrid retrieve with permissions → optional judge rerank → apply tool policy → record observed outcomes`.

## Interface proposal

`MemoryBackend` methods: `record_episode`, `propose_fact`, `approve_or_revoke`, `retrieve(context, actor, purpose, time, top_k)`, `record_verified_outcome`, `forget`, `export_reviewed_markdown`. All writes/reads return opaque IDs, provenance, tenancy/privacy scope and status.

Schema fields (minimum): `memory_id`, `tenant_id`, `agent_id`, `run_id`, `memory_type`, `source_id`, `source_hash`, `redaction_class`, `observed_at`, `valid_from`, `valid_until`, `status`, `evaluator_id`, `outcome_score`, `confidence`, `created_at`, `supersedes_id`, `delete_at`. Text and embeddings in access-controlled stores; secrets never written.

## Phased engineering plan

**P0 — Security & compatibility first:** keep old code on local stdio, gate trusted-scoring/feedback APIs behind a real caller boundary before any remote exposure; explicit migration tests; support signed/verified evaluator outcomes and memory provenance. Add deletion, poison/PII exclusion, and per-agent permissions.

**P1 — Baselines:** SQL keyword/FTS + contextual utility, fixed holdouts, freshness/supersession. Include simple fixed-memory or no-memory reference. Benchmark correctness and concurrency before adding LLM extraction.

**P2 — Semantic pilot:** plugin interface for self-hosted Mem0 OSS/pgvector and local embeddings; no mandatory SaaS or managed graph. Compare exact, BM25, hybrid BM25+vector, Mem0, on common tasks and cost budgets.

**P3 — Temporal pilot:** Graphiti/Cognee graph backend only if temporal queries and multi-hop benchmarks justify runtime and cost. Test contradiction and time-sensitive retrieval, no training leakage.

**P4 — Human review UI:** one-way redacted Obsidian Markdown export for reviewed memories; no raw patient data or secrets; review diffs before re-import and enforce policy.

**P5 — Jev optional judge:** rank or triage retrieved memories under explicit latency/budget constraints; compare against deterministic rankers; final tool, memory-write and clinical decisions never delegated.

## Exit/acceptance criteria

- 100% denial of cross-tenant reads/writes in the test matrix; agent-supplied IDs alone never grant privileges.
- No unsourced or unverified scored memory becomes a trusted policy, action, or skill; hostile Markdown cannot override instructions.
- Test data for contradiction, temporal updates, stale/expired facts, forgetting/deletion, malformed embeddings and metadata injection.
- Publish at least 5 independent task families, multiple seeds, cost and p50/p95 read/write latency, token count, recall@k, precision@k, and downstream task accuracy; assess performance against matched no-memory and correctly configured baselines.
- Local tests/CI require no paid provider, real patient data or TypeSafe API key. Review licensing, retention, GDPR/data-protection obligations before any healthcare deployment.

**Decision pending:** validate a small, independent Mem0 + pgvector prototype and a pure SQL hybrid-search baseline before committing to an external memory stack. No automatic migration of existing SQLite experience rows and no change to current production systems.
