"""Guardrails for manual only, secret-protected model evaluation."""
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "llm-study-v15.yml"


class V15WorkflowSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text(encoding="utf-8")

    def test_manual_only(self):
        self.assertIn("on:\n  workflow_dispatch:", self.text)
        for automatic in ("  push:", "  pull_request:", "  schedule:"):
            self.assertNotIn(automatic, self.text)

    def test_protected_environment_and_read_only_scope(self):
        self.assertIn("environment: llm-research-live", self.text)
        self.assertIn("github.repository == 'ALIYILD/NERVE'", self.text)
        self.assertIn("github.ref == 'refs/heads/main'", self.text)
        self.assertIn("permissions:\n  contents: read", self.text)
        self.assertIn("persist-credentials: false", self.text)

    def test_key_secret_only_and_bounded_benchmark(self):
        self.assertIn(
            "NERVE_LLM_API_KEY: " + "$" + "{{ secrets.NERVE_LLM_API_KEY }}",
            self.text
        )
        self.assertIn("--live --seeds 1 --cases 2", self.text)
        self.assertNotIn("set -x", self.text)
        self.assertNotIn("printenv", self.text)
        self.assertNotIn("curl ", self.text)
        self.assertIn("timeout-minutes: 5", self.text)


if __name__ == "__main__":
    unittest.main()
