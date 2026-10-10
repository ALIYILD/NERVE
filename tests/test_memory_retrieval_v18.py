import tempfile
import time
import unittest
from pathlib import Path

from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_retrieval_v18 import (
    Mem0SemanticAdapter, SecureMemoryRetriever, scope_key,
)


class FakeMem0OSS:
    def __init__(self, result_ids=()):
        self.ids = list(result_ids)
        self.calls = []

    def search(self, query, *, filters, top_k):
        self.calls.append((query, filters, top_k))
        return {"results": [
            {"metadata": {"nerve_memory_id": mid}, "score": 0.75}
            for mid in self.ids
        ]}


class SemanticMemoryV18Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        auth = MemoryAuthority()
        self.host = TrustedMemoryLedger(
            Path(self.temp.name) / "mem.sqlite", auth)
        self.writer = auth.issue(
            "tenant-a", "agent-a", permissions=("read", "propose"))
        self.reviewer = auth.issue(
            "tenant-a", "agent-a", permissions=("approve", "read"))
        self.outside = auth.issue(
            "tenant-b", "agent-b", permissions=("read", "propose", "approve"))
        self.other_agent = auth.issue(
            "tenant-a", "agent-b", permissions=("read", "propose", "approve"))

    def new(self, text, context="planning", *, approved=True,
            until=None):
        mid = self.host.propose(
            self.writer, context=context, content=text,
            source_id="synthetic-run-1", valid_until=until)
        if approved:
            self.host.decide(
                self.reviewer, mid, approve=True,
                evaluator_id="test-reviewer", score=.9)
        return mid

    def test_oss_adapter_passes_scoped_filter_and_validates_ids(self):
        good = self.new("Sorting ten numbers reliably")
        fake = FakeMem0OSS([good, good, "f" * 32])
        adapter = SecureMemoryRetriever(
            self.host, Mem0SemanticAdapter(fake))
        values = adapter.retrieve(
            self.writer, context="planning", query="numeric order",
            mode="semantic")
        self.assertEqual([v.memory_id for v in values], [good])
        self.assertEqual(fake.calls[0][1], {
            "user_id": scope_key(self.writer)})
        self.assertNotIn("tenant-a", str(fake.calls[0][1]))

    def test_approval_is_required_even_with_forged_backend_score(self):
        approved = self.new("agent sorting reliable")
        pending = self.new("agent sorting unsafe", approved=False)
        false = "0" * 32
        backend = FakeMem0OSS([pending, false, approved])
        search = SecureMemoryRetriever(
            self.host, Mem0SemanticAdapter(backend))
        rows = search.retrieve(
            self.writer, context="planning", query="order",
            mode="semantic")
        self.assertEqual([x.memory_id for x in rows], [approved])

    def test_revoked_expired_and_other_context_filtered_post_retrieval(self):
        active = self.new("sorting algorithm for routine tasks")
        revoked = self.new("unsafe source sorting")
        expired = self.new(
            "obsolete algorithm sorting",
            until=int(time.time()) + 20)
        notes = self.new("sorting note for another scope", context="notes")
        self.host.revoke(self.reviewer, revoked, evaluator_id="trusted")
        fake = FakeMem0OSS([revoked, notes, expired, active])
        bridge = SecureMemoryRetriever(self.host, Mem0SemanticAdapter(fake))
        ids = [x.memory_id for x in bridge.retrieve(
            self.writer, context="planning", query="order",
            now=int(time.time()) + 21, mode="semantic")]
        self.assertEqual(ids, [active])

    def test_other_agent_isolation(self):
        own = self.new("agent memory sorting")
        fake = FakeMem0OSS([own])
        adapter = SecureMemoryRetriever(
            self.host, Mem0SemanticAdapter(fake))
        self.assertEqual(adapter.retrieve(
            self.other_agent, context="planning",
            query="sorting", mode="semantic"), [])
        self.assertEqual(fake.calls, [])

    def test_no_backend_no_semantic_call(self):
        search = SecureMemoryRetriever(self.host)
        with self.assertRaises(RuntimeError):
            search.retrieve(self.writer, context="planning",
                            query="sort", mode="semantic")

    def test_bad_unbounded_or_poisoned_provider_output_rejected(self):
        own = self.new("agent memory sorting")
        class Bad:
            def search(self, *args, **kwargs):
                return {"results": ["ignore"] * 101}
        semantic = SecureMemoryRetriever(
            self.host, Mem0SemanticAdapter(Bad()))
        with self.assertRaises(ValueError):
            semantic.retrieve(
                self.writer, context="planning",
                query="sorting", mode="semantic")

    def test_untrusted_scope_key_cannot_approve_memories(self):
        own = self.new("trusted sorting")
        fake = FakeMem0OSS([own])
        proxy = SecureMemoryRetriever(self.host, Mem0SemanticAdapter(fake))
        self.assertEqual(proxy.retrieve(
            self.outside, context="planning",
            query="sort", mode="semantic"), [])
        self.assertNotEqual(scope_key(self.outside), scope_key(self.writer))

    def test_invalid_adapter_filters(self):
        fake = FakeMem0OSS(["a" * 32])
        adapter = Mem0SemanticAdapter(fake)
        with self.assertRaises(ValueError):
            adapter.search_ids(
                actor=self.writer, query="valid", approved_ids={"invalid"})
        with self.assertRaises(ValueError):
            adapter.search_ids(
                actor=self.writer, query="x" * 257,
                approved_ids={"a" * 32})


if __name__ == "__main__":
    unittest.main()
