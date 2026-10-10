"""Provider-independent read-only memory retrieval facade (v1.8).

No external backend is allowed to make a memory authoritative. Mem0 is
optional and receives ONLY an operator-approved synthetic/public query.
Each semantic result is rechecked against the local approved ledger;
missing/forged IDs, revoked/expired records and other agent namespaces
are discarded. No automatic provider write/synchronisation is performed.
"""
from hashlib import sha256
from math import isfinite
import re


def scope_key(actor):
    """Opaque deterministic scope for the optional OSS Mem0 user_id filter."""
    return "nerve-" + sha256(
        (actor.tenant_id + "\0" + actor.agent_id).encode()
    ).hexdigest()


class Mem0SemanticAdapter:
    """Inject an actual Mem0 OSS Memory instance via client=memory.

    Docs: https://github.com/mem0ai/mem0/blob/main/docs/core-concepts/memory-operations/search.mdx
    This adapter deliberately does NOT depend on the hosted Mem0 platform.
    """

    def __init__(self, client):
        if not callable(getattr(client, "search", None)):
            raise TypeError("Mem0 OSS client with search() required")
        self.client = client

    def search_ids(self, *, actor, query, approved_ids, limit=10):
        if type(query) is not str or not 1 <= len(query) <= 256:
            raise ValueError("bounded memory query required")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("bounded search limit required")
        approved_ids = frozenset(approved_ids)
        if len(approved_ids) > 1000 or not all(
            type(mid) is str and re.fullmatch("[0-9a-f]{32}", mid)
            for mid in approved_ids
        ):
            raise ValueError("approved ID pool is invalid")
        if not approved_ids:
            return []
        results = self.client.search(
            query,
            filters={"user_id": scope_key(actor)},
            top_k=min(100, max(limit * 5, 10)),
        )
        # OSS versions return either list[dict] or {"results": list}.
        if isinstance(results, dict):
            results = results.get("results")
        if not isinstance(results, list) or len(results) > 100:
            raise ValueError("invalid or unbounded provider results")
        found = []
        seen = set()
        for item in results:
            if type(item) is not dict:
                continue
            meta = item.get("metadata")
            if type(meta) is not dict:
                continue
            mid = meta.get("nerve_memory_id")
            score = item.get("score", 0.0)
            if (mid not in approved_ids or mid in seen
                    or type(score) not in (int, float)
                    or not isfinite(score)):
                continue
            seen.add(mid)
            found.append((mid, float(score)))
        found.sort(key=lambda row: (-row[1], row[0]))
        return [mid for mid, _ in found[:limit]]


class SecureMemoryRetriever:
    """Authoritative ledger + optional advisory external semantic search."""

    def __init__(self, ledger, semantic=None):
        self.ledger = ledger
        self.semantic = semantic

    def retrieve(self, actor, *, context, query, limit=5, mode="lexical",
                 now=None):
        if mode not in ("lexical", "semantic"):
            raise ValueError("unknown retrieval mode")
        if type(query) is not str or not 1 <= len(query) <= 256:
            raise ValueError("bounded nonempty query required")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("bounded limit required")
        if mode == "lexical":
            return self.ledger.retrieve(
                actor, context=context, query=query, limit=limit, now=now
            )
        if self.semantic is None:
            raise RuntimeError("semantic backend is not enabled")
        # First verify actor and policy, then reveal limited approved IDs
        # to the optional backend. Its claimed content/status is NEVER used.
        pool = self.ledger.approved_pool(
            actor, context=context, now=now, limit=1000
        )
        allowed = {item.memory_id: item for item in pool}
        ids = self.semantic.search_ids(
            actor=actor, query=query, approved_ids=allowed, limit=limit
        )
        # This final mapping enforces exact ledger provenance/status.
        return [allowed[mid] for mid in ids if mid in allowed]
