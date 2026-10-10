# NERVE Memory v1.8 — verified local ledger and optional semantic-memory pilot

**Status:** Implemented research prototype, **not** a production memory migration. Existing `LearningStore` and local agent demos still use their historical SQLite schema. Real patient data, production tenant identity, model weights and safety policies are out of scope.

## What changed

1. `memory_v18.py`: new isolated SQLite ledger with **host-issued in-process capability contexts**. Reads/writes are scoped by tenant, agent and context. Entries require source ID, SHA-256 content digest, explicit independent host reviewer, approval state, optional numeric outcome, expiry and supersession. Revocation and hard deletion are available.
2. `memory_retrieval_v18.py`: pluggable lexical and optional `Mem0SemanticAdapter` read path. The local ledger is always authoritative: before returning an externally ranked ID, NERVE checks that it remains approved, unexpired and in the exact actor tenant/agent/context.
3. `learn_mcp.py`: generic legacy `record_experience` and `rate_experience` calls **default to disabled**. Local users relying on these experimental unauthenticated writes can opt in explicitly with `NERVE_ENABLE_LEGACY_MCP_WRITES=1`; this flag **is not authentication**. Existing read-only MCP methods and trusted fixed-fixture agent demonstrations continue to work.
4. `obsidian_export_v18.py`: a one-way, **in-memory Markdown review preview** for approved records. No Obsidian plugin, cloud API, file writes, bidirectional imports or automatic synchronisation are enabled.
5. `benchmarks/v18_memory_retrieval.py`: five small constructed research-memory families, five literal queries and five paraphrase queries. The optional semantic result fixture is deliberately answer-keyed; it is **not the Mem0 model**, so any apparent recall improvement is a demonstration of the adapter contract, not evidence of actual semantic understanding.

## Security model and precise limitations

- `MemoryAuthority.issue()` must only be invoked by trusted application code. A host-issued object is an **in-process capability, not a remotely authenticated identity**. Never expose capability issuance on MCP, HTTP or as an arbitrary model tool.
- This is local unencrypted SQLite storage. It does not yet provide signed evaluator certificates, durable audit history, user consent, enterprise RBAC, HIPAA/GDPR compliance, tenant-isolated remote hosting or robust PII detection. The explicit secret-text exclusion and Markdown masking are **best effort**, not clinical de-identification.
- `source_sha256` currently records the submitted content digest, not a cryptographically verified upstream document identity. The source ID and evaluator IDs are trusted host declarations and must be backed by an external provenance service for production.
- Generic legacy score/write APIs must remain disabled for untrusted clients. The fixed internal demo can still write evaluated local synthetic rewards.
- The optional Mem0 OSS adapter accepts an operator-injected `mem0.Memory` compatible client. It issues only `search(query,filters={"user_id": scoped_id},top_k=...)`, using the current OSS v3 filtering shape, and whitelists returned IDs against the live ledger. It does **not** automatically upload/index data to Mem0. Without an explicit, deletion-aware indexing plan, it is a read-side integration seam rather than an end-to-end semantic store.
- Mem0 OSS can be configured with local or third-party embedding/LLM backends. Validate local-only configuration and vendor data handling before transferring even approved memories.
- Obsidian exports are preview-only. Copied Markdown is a snapshot; updates/revocations will not delete old manually copied vault notes. Never export patient information or secrets.
- None of these components are authorised to execute arbitrary tools, modify NERVE policies or make clinical/robotic decisions.

## Local development

```bash
export PYTHONPATH=src
python -m unittest discover -s tests -p 'test_memory_v18.py' -v
python -m unittest discover -s tests -p 'test_memory_retrieval_v18.py' -v
python -m unittest discover -s tests -p 'test_mcp_write_gating_v18.py' -v
python -m unittest discover -s tests -p 'test_obsidian_export_v18.py' -v
python benchmarks/v18_memory_retrieval.py
```

All v1.8 core tests and the synthetic benchmark are dependency-free (standard Python 3.12 + SQLite). The existing CI job separately verifies the real MCP 2.3 stdio server. There is no paid TypeSafe, Mem0 or LLM invocation in ordinary CI.

## Trusted host example

```python
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_retrieval_v18 import SecureMemoryRetriever

authority = MemoryAuthority()
writer = authority.issue('test-tenant', 'test-agent', permissions=('propose', 'read'))
reviewer = authority.issue('test-tenant', 'test-agent', permissions=('approve', 'read', 'delete'))
ledger = TrustedMemoryLedger('local-test-memory.sqlite', authority)
mid = ledger.propose(writer, context='planning',
                     content='Numeric sorting succeeded on synthetic fixtures',
                     source_id='test-run-1')
# The trusted host explicitly verifies the real result before approval:
ledger.decide(reviewer, mid, approve=True, evaluator_id='test-judge', score=1.0)
hits = SecureMemoryRetriever(ledger).retrieve(
    writer, context='planning', query='numeric sorting', limit=3)
assert hits[0].memory_id == mid
```

## Optional Mem0 OSS search adapter

```python
# Only after independently installing and securely configuring Mem0 OSS:
# from mem0 import Memory
# memory_client = Memory.from_config(local_only_config)
# semantic = Mem0SemanticAdapter(memory_client)
# search = SecureMemoryRetriever(ledger, semantic=semantic)
# # The external Mem0 index must first contain matching reviewed memory IDs
# # in metadata. There is no automatic ingestion or deletion propagation.
```

Authoritative API references: [Mem0 OSS search](https://github.com/mem0ai/mem0/blob/main/docs/core-concepts/memory-operations/search.mdx), [Mem0 OSS API and authentication](https://github.com/mem0ai/mem0/blob/main/docs/open-source/features/rest-api.mdx).

## Next decision gates

1. Verify reviewer/evaluator identity with real server authentication and signed provenance before remote memory writes.
2. Build deletion-aware, redacted **approved-only** semantic index synchronisation; test revoke/delete, retries, duplicate ingestion and external embedder privacy.
3. Independently benchmark **actual** Mem0 OSS + local embeddings against SQL keyword/FTS/pgvector baselines with common seeded questions, paraphrases, temporal contradictions, prompts/poisoning and measured p50/p95 read/write latency.
4. Test an optional Postgres/pgvector service with tenant-isolated roles and verified server-side authorization. Do not promote SQLite capability objects to network authentication.
5. Gate Obsidian one-way export behind explicit human review and redaction/retention controls.

Tracking: [security issue #1](https://github.com/ALIYILD/NERVE/issues/1), [architecture/benchmarks issue #2](https://github.com/ALIYILD/NERVE/issues/2), [ADR-0018](memory-backend-decision-v18.md).
