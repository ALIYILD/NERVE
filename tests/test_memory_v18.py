import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from nerve_awim.memory_v18 import (
    MemoryActor, MemoryAuthority, TrustedMemoryLedger,
)


class TrustedMemoryV18Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.authority = MemoryAuthority()
        self.ledger = TrustedMemoryLedger(
            Path(self.temp.name) / "trusted.sqlite", self.authority)
        self.writer = self.authority.issue("clinic-a", "agent-a",
                                           permissions=("propose", "read"))
        self.reviewer = self.authority.issue(
            "clinic-a", "agent-a", permissions=("approve", "read", "delete"))
        self.other = self.authority.issue(
            "clinic-b", "agent-a",
            permissions=("read", "propose", "approve", "delete"))
        self.other_agent = self.authority.issue(
            "clinic-a", "agent-b",
            permissions=("read", "propose", "approve", "delete"))

    def _approved(self, content="agent selects numeric sorting",
                  context="planning", until=None):
        mid = self.ledger.propose(
            self.writer, context=context, content=content,
            source_id="synthetic-run-1", valid_until=until)
        self.ledger.decide(
            self.reviewer, mid, approve=True,
            evaluator_id="trusted-evaluator", score=1.0)
        return mid

    def test_pending_excluded_until_trusted_review(self):
        mid = self.ledger.propose(
            self.writer, context="planning",
            content="numeric sort helps tool planning",
            source_id="synthetic-run-1")
        self.assertEqual(
            self.ledger.retrieve(self.writer, context="planning", query="sort"), [])
        with self.assertRaises(PermissionError):
            self.ledger.decide(
                self.writer, mid, approve=True, evaluator_id="me", score=1.)
        self.ledger.decide(
            self.reviewer, mid, approve=True,
            evaluator_id="independent", score=.9)
        matches = self.ledger.retrieve(
            self.writer, context="planning", query="sort")
        self.assertEqual([m.memory_id for m in matches], [mid])
        self.assertEqual(matches[0].evaluator_id, "independent")
        self.assertEqual(len(matches[0].source_sha256), 64)

    def test_cross_tenant_and_cross_agent_access_denied(self):
        mid = self._approved()
        for actor in (self.other, self.other_agent):
            self.assertEqual(
                self.ledger.retrieve(actor, context="planning", query="sorting"), [])
            with self.assertRaises(LookupError):
                self.ledger.status(actor, mid)
            with self.assertRaises(LookupError):
                self.ledger.decide(
                    actor, mid, approve=False, evaluator_id="evaluator")
            with self.assertRaises(LookupError):
                self.ledger.forget(actor, mid)

    def test_forged_context_and_unissued_capability_denied(self):
        mid = self._approved()
        forged = MemoryActor(
            "clinic-a", "agent-a", frozenset(("read",)),
            self.writer._capability
        )
        with self.assertRaises(PermissionError):
            self.ledger.retrieve(
                forged, context="planning", query="sorting")
        with self.assertRaises(PermissionError):
            self.ledger.status(forged, mid)
        self.authority.revoke(self.writer)
        with self.assertRaises(PermissionError):
            self.ledger.retrieve(
                self.writer, context="planning", query="sorting")

    def test_invalid_feedback_is_rejected(self):
        mid = self.ledger.propose(
            self.writer, context="planning",
            content="sort numbers correctly", source_id="run-1")
        for value in (True, -1.0, 1.1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.ledger.decide(
                    self.reviewer, mid, approve=True,
                    evaluator_id="reviewer", score=value)
        self.ledger.decide(
            self.reviewer, mid, approve=True,
            evaluator_id="reviewer", score=.8)
        with self.assertRaises(ValueError):
            self.ledger.decide(
                self.reviewer, mid, approve=True,
                evaluator_id="reviewer", score=.9)

    def test_revocation_supersession_and_forgetting(self):
        first = self._approved("numeric sorting provides better results")
        second = self.ledger.propose(
            self.writer, context="planning",
            content="numeric sorting superseded by validated priority",
            source_id="synthetic-run-2", supersedes_id=first)
        self.assertEqual(self.ledger.status(self.reviewer, first).status,
                         "approved")
        self.ledger.decide(
            self.reviewer, second, approve=True,
            evaluator_id="reviewer", score=1.)
        self.assertEqual(self.ledger.status(self.reviewer, first).status,
                         "superseded")
        self.assertEqual(
            [m.memory_id for m in self.ledger.retrieve(
                self.reviewer, context="planning", query="numeric")], [second])
        self.ledger.revoke(self.reviewer, second, evaluator_id="reviewer")
        self.assertEqual(self.ledger.retrieve(
            self.reviewer, context="planning", query="numeric"), [])
        self.ledger.forget(self.reviewer, second)
        with self.assertRaises(LookupError):
            self.ledger.status(self.reviewer, second)

    def test_expiry_suppresses_old_memory(self):
        future = int(time.time()) + 100
        self._approved("agent tool schedule changed", until=future)
        self.assertEqual(len(self.ledger.retrieve(
            self.writer, context="planning", query="schedule",
            now=future - 1)), 1)
        self.assertEqual(self.ledger.retrieve(
            self.writer, context="planning", query="schedule",
            now=future), [])
        self.assertEqual(self.ledger.approved_pool(
            self.writer, context="planning", now=future), [])

    def test_secret_exclusion_is_explicitly_best_effort(self):
        for content in (
            "password = p4ssw0rd",
            "-----BEGIN PRIVATE KEY-----",
            "apikey_" + "a" * 40,
        ):
            with self.assertRaises(ValueError):
                self.ledger.propose(
                    self.writer, context="planning",
                    content=content, source_id="synthetic-run-1")

    def test_status_and_pool_scope(self):
        mid = self._approved("tool select numeric sorting")
        self._approved("personal notebook task", context="notes")
        self.assertEqual(
            [m.memory_id for m in self.ledger.approved_pool(
                self.writer, context="planning")], [mid])
        self.assertEqual(self.ledger.status(self.reviewer, mid).status,
                         "approved")

    def test_rejected_memory_is_not_promotable(self):
        mid = self.ledger.propose(
            self.writer, context="planning",
            content="unsupported policy", source_id="synthetic-run-1")
        self.ledger.decide(
            self.reviewer, mid, approve=False, evaluator_id="reviewer")
        self.assertEqual(self.ledger.status(self.reviewer, mid).status,
                         "rejected")
        with self.assertRaises(ValueError):
            self.ledger.decide(
                self.reviewer, mid, approve=True,
                evaluator_id="reviewer", score=1.)
        self.assertEqual(
            self.ledger.retrieve(
                self.writer, context="planning", query="policy"), [])

    def test_scope_and_validation_errors(self):
        with self.assertRaises(ValueError):
            self.authority.issue("tenant with spaces", "agent")
        with self.assertRaises(ValueError):
            self.ledger.propose(
                self.writer, context="planning", content="secret",
                source_id="bad source ID")
        with self.assertRaises(ValueError):
            self.ledger.retrieve(
                self.writer, context="planning", query="sorting", limit=0)
        with self.assertRaises(PermissionError):
            self.ledger.forget(
                self.writer, "0" * 32)


if __name__ == "__main__":
    unittest.main()
