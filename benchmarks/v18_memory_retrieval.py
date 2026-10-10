"""Synthetic NERVE memory retrieval comparison: SQL lexical vs Mem0-shaped stub.

The semantic adapter is a deterministic fixture, not the actual Mem0 model.
Reports retrieval accuracy and local latency only for hand-authored examples.
No paid models, embedding providers, external network or private data.
"""
import json
import statistics
import tempfile
from pathlib import Path
from time import perf_counter

from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_retrieval_v18 import (
    SecureMemoryRetriever, Mem0SemanticAdapter,
)

FAMILIES = (
    ("numerical sorting integers ascending", "sorting integers", "order numbers"),
    ("optical measurement drift calibration", "measurement drift",
     "recalibrate light sensors"),
    ("review citations study evidence", "review citations",
     "verify bibliography"),
    ("network connectivity outage recovery", "network outage",
     "restore communication"),
    ("calendar event scheduling reminder", "event scheduling",
     "book appointment"),
)


class CuratedSemanticFixture:
    """Illustrative semantic-like ranking map; definitely not Mem0/embeddings."""

    def __init__(self, answer_ids):
        self.answer_ids = dict(answer_ids)
        self.calls = 0

    def search(self, query, *, filters, top_k):
        self.calls += 1
        correct = self.answer_ids.get(query)
        if correct is None:
            return {"results": []}
        return {"results": [{
            "metadata": {"nerve_memory_id": correct},
            "score": .9,
        }]}


def _latency_ms(items, q):
    measured = sorted(items)
    if not measured:
        raise ValueError("no latency observations")
    index = min(len(measured) - 1, int((len(measured) - 1) * q))
    return round(1000 * measured[index], 4)


def benchmark():
    with tempfile.TemporaryDirectory() as directory:
        authority = MemoryAuthority()
        writer = authority.issue(
            "benchmark", "memory-agent", permissions=("propose", "read"))
        reviewer = authority.issue(
            "benchmark", "memory-agent", permissions=("read", "approve"))
        other = authority.issue(
            "other-tenant", "memory-agent",
            permissions=("read",))
        ledger = TrustedMemoryLedger(
            Path(directory) / "retrieval.sqlite", authority
        )
        answer_ids = {}
        queries = []
        for i, (body, exact, paraphrase) in enumerate(FAMILIES):
            memory_id = ledger.propose(
                writer, context="research", content=body,
                source_id="synthetic-source-" + str(i))
            ledger.decide(
                reviewer, memory_id, approve=True,
                evaluator_id="independent-fixture", score=1.0)
            for query in (exact, paraphrase):
                answer_ids[query] = memory_id
                queries.append((query, memory_id, query == exact))
        provider = CuratedSemanticFixture(answer_ids)
        gateway = SecureMemoryRetriever(
            ledger, semantic=Mem0SemanticAdapter(provider)
        )
        measured = {}
        for mode in ("lexical", "semantic"):
            successes = {"exact": 0, "paraphrase": 0}
            timing = []
            for query, expected, is_exact in queries:
                start = perf_counter()
                found = gateway.retrieve(
                    writer, context="research", query=query,
                    mode=mode, limit=1
                )
                timing.append(perf_counter() - start)
                successes["exact" if is_exact else "paraphrase"] += int(
                    bool(found and found[0].memory_id == expected)
                )
            measured[mode] = {
                "recall_at_1": sum(successes.values()) / len(queries),
                "exact_recall_at_1": successes["exact"] / len(FAMILIES),
                "paraphrase_recall_at_1": successes["paraphrase"] / len(FAMILIES),
                "p50_local_ms": _latency_ms(timing, .5),
                "p95_local_ms": _latency_ms(timing, .95),
            }
        # Cross-tenant requests must not even invoke the optional provider.
        prior = provider.calls
        forbidden = gateway.retrieve(
            other, context="research", query="sorting integers",
            mode="semantic", limit=1,
        )
        return {
            "families": len(FAMILIES),
            "queries": len(queries),
            "results": measured,
            "cross_tenant_results": len(forbidden),
            "cross_tenant_provider_calls": provider.calls - prior,
            "trust_contract": "only exact-scope approved ledger IDs are returned",
            "disclaimer": (
                "Semantic provider is an answer-keyed fixture, NOT Mem0 OSS. "
                "Differences in recall are constructed. Timing is only local "
                "test overhead, not actual embedder/vector/database latency. "
                "No real-world accuracy, speed or safety claims."
            ),
        }


if __name__ == "__main__":
    print(json.dumps(benchmark(), sort_keys=True, indent=2))
