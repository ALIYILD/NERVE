"""Schedule and repository safety constraints for recursive research."""
from pathlib import Path
import unittest

WORKFLOW = (Path(__file__).resolve().parents[1]
            / ".github" / "workflows" / "recursive-research.yml")


class RecursiveScheduleV19Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_or_scheduled_only(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertIn("schedule:", self.workflow)
        self.assertIn("cron: '17 */6 * * *'", self.workflow)
        self.assertNotIn("  push:", self.workflow)
        self.assertNotIn("  pull_request:", self.workflow)

    def test_read_only_no_deploy_or_push(self):
        self.assertIn("permissions:\n  contents: read", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertIn("timeout-minutes: 8", self.workflow)
        self.assertIn("github.ref == 'refs/heads/main'", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        self.assertNotIn("git push", self.workflow)
        self.assertNotIn("gh pr create", self.workflow)
        self.assertNotIn("TYPESAFE_API_KEY", self.workflow)

    def test_population_checkpoints_and_revalidation(self):
        self.assertIn("actions/cache@v4", self.workflow)
        self.assertIn("nerve-v19-", self.workflow)
        self.assertIn("--resume research-state/evolution.json", self.workflow)
        self.assertIn("scripts/recursive_research_v19.py", self.workflow)
        self.assertIn("candidates_evaluated", self.workflow)
        self.assertIn("cross_tenant_leaks", self.workflow)
        self.assertIn("worldcore_recursion_v19.py", self.workflow)
        self.assertIn("worldcore-research.json", self.workflow)
        self.assertIn("holdout_absolute_eligible", self.workflow)
        self.assertIn("research-output/*.json", self.workflow)
        self.assertIn("cp research-output/recursive-research.json research-state/evolution.json", self.workflow)
        self.assertIn("actions/upload-artifact@v4", self.workflow)
        self.assertIn("retention-days: 7", self.workflow)


if __name__ == "__main__":
    unittest.main()
