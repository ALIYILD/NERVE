"""Static guardrails around the optional privileged Jev workflow.

These tests cannot validate GitHub account-level reviewers or secret settings.
"""
from pathlib import Path
import unittest

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github" / "workflows" / "jev-live.yml"
)


class ProtectedJevWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.yaml = WORKFLOW.read_text(encoding="utf-8")

    def test_only_manual_trigger(self):
        self.assertIn("on:\n  workflow_dispatch:", self.yaml)
        self.assertNotIn("  push:", self.yaml)
        self.assertNotIn("  pull_request:", self.yaml)
        self.assertNotIn("  schedule:", self.yaml)

    def test_only_approved_main_and_repository(self):
        self.assertIn("github.repository == 'ALIYILD/NERVE'", self.yaml)
        self.assertIn("github.ref == 'refs/heads/main'", self.yaml)
        self.assertIn("environment: typesafe-live", self.yaml)

    def test_secret_context_only_and_no_command_arguments(self):
        self.assertIn("TYPESAFE_API_KEY: " + "$" + "{{ secrets.TYPESAFE_API_KEY }}",
                      self.yaml)
        self.assertIn("python -m nerve_awim.jev_smoke", self.yaml)
        self.assertNotIn("--key", self.yaml)
        self.assertNotIn("env |", self.yaml)
        self.assertNotIn("printenv", self.yaml)
        self.assertNotIn("set -x", self.yaml)

    def test_manual_mode_is_fixed_choice(self):
        self.assertIn("type: choice", self.yaml)
        self.assertIn("default: smoke", self.yaml)
        self.assertIn("if: inputs.mode == 'smoke'", self.yaml)
        self.assertIn("if: inputs.mode == 'comparison'", self.yaml)
        self.assertIn("python -m nerve_awim.jev_agreement_v12 --live", self.yaml)
        self.assertEqual(self.yaml.count("python -m nerve_awim.jev_smoke"), 1)

    def test_principle_of_least_privilege(self):
        self.assertIn("permissions:\n  contents: read", self.yaml)
        self.assertIn("persist-credentials: false", self.yaml)
        self.assertIn("timeout-minutes: 3", self.yaml)


if __name__ == "__main__":
    unittest.main()
