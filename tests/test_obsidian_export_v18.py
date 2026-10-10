import tempfile
import time
import unittest
from pathlib import Path

from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.obsidian_export_v18 import render_reviewed_markdown


class ObsidianPreviewV18Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        auth = MemoryAuthority()
        self.ledger = TrustedMemoryLedger(
            Path(self.temp.name) / "m.sqlite", auth)
        self.author = auth.issue("tenant", "agent",
                                 permissions=("read", "propose"))
        self.reviewer = auth.issue("tenant", "agent",
                                   permissions=("read", "approve"))
        self.other = auth.issue("other-tenant", "agent",
                                permissions=("read",))
        self.now = int(time.time())

    def create(self, content, *, approved=True, until=None):
        mid = self.ledger.propose(
            self.author, context="learning", content=content,
            source_id="public-simulated-source", valid_until=until)
        if approved:
            self.ledger.decide(
                self.reviewer, mid, approve=True,
                evaluator_id="trusted-reviewer", score=.8)
        return mid

    def test_preview_only_contains_approved_visible_records(self):
        good = self.create("Approved tool selection notes")
        self.create("Pending tool selection notes", approved=False)
        content = render_reviewed_markdown(
            self.ledger, self.reviewer, context="learning")
        self.assertIn(good, content)
        self.assertIn("Approved tool selection notes", content)
        self.assertNotIn("Pending tool selection notes", content)
        self.assertIn("not an instruction source", content.lower())

    def test_privacy_scope_and_revocation(self):
        mid = self.create("Validated semantic retrieval")
        self.assertNotIn(mid, render_reviewed_markdown(
            self.ledger, self.other, context="learning"))
        self.ledger.revoke(self.reviewer, mid,
                           evaluator_id="trusted-reviewer")
        self.assertNotIn(mid, render_reviewed_markdown(
            self.ledger, self.reviewer, context="learning"))

    def test_expired_memory_not_exported(self):
        mid = self.create(
            "Old episodic memory", until=self.now + 10)
        self.assertNotIn(mid, render_reviewed_markdown(
            self.ledger, self.author, context="learning",
            now=self.now + 11))

    def test_markdown_escapes_links_and_secret_like_data(self):
        self.create(
            "Link [click](https://example.invalid/demo) with "
            "contact demo@example.org and <script>alert(1)</script>"
        )
        markdown = render_reviewed_markdown(
            self.ledger, self.reviewer, context="learning")
        self.assertNotIn("https://example.invalid", markdown)
        self.assertNotIn("demo@example.org", markdown)
        self.assertNotIn("<script>", markdown)
        self.assertIn("&lt;script&gt;", markdown)
        self.assertIn("[email redacted]", markdown)

    def test_invalid_limit_rejected(self):
        with self.assertRaises(ValueError):
            render_reviewed_markdown(
                self.ledger, self.author, context="learning", limit=200)


if __name__ == "__main__":
    unittest.main()
