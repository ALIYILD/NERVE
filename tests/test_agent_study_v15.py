import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nerve_awim.agent_study_v15 import (
    CapableFixturePlanner, FormatChatPlanner, FormatExperience,
    LimitedFixturePlanner, Plan,
)
from nerve_awim.evolution_v01 import EvolutionMemory
from scripts.agent_study_v15 import make_task, mock_provider, MockResponse


class V15UnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.memory = FormatExperience(
            EvolutionMemory(Path(self.tmp.name) / "study.sqlite"),
            agent_id="research-test")

    def test_context_specific_reward_selects_different_tools(self):
        self.memory.record("json_email", Plan("json-field", "trim-lower"), 1.0)
        self.memory.record("json_email", Plan("raw", "trim-lower"), 0.0)
        self.memory.record("plain_email", Plan("raw", "trim-lower"), 1.0)
        self.memory.record("plain_email", Plan("json-field", "trim-lower"), 0.0)
        self.assertEqual(
            self.memory.recommendation("json_email"),
            Plan("json-field", "trim-lower"))
        self.assertEqual(
            self.memory.recommendation("plain_email"),
            Plan("raw", "trim-lower"))

    def test_no_feedback_is_not_auto_training(self):
        self.assertIsNone(self.memory.recommendation("json_email"))
        self.assertEqual(CapableFixturePlanner().plan_for(
            "json_email").plan, Plan("json-field", "trim-lower"))

    def test_reject_unregistered_memory(self):
        self.memory.memory.record(
            "research-test", "format:json_email", "shell|exec", 1.0)
        self.assertIsNone(self.memory.recommendation("json_email"))

    def test_reject_invalid_training_inputs(self):
        with self.assertRaises(ValueError):
            self.memory.record("unknown", Plan("raw", "trim-lower"), 1.)
        with self.assertRaises(ValueError):
            self.memory.record("json_email", Plan("raw", "trim-lower"),
                               float("nan"))
        with self.assertRaises(ValueError):
            self.memory.record("json_email", Plan("raw", "trim-lower"), True)

    def test_limited_fixture_uses_guidance(self):
        planner = LimitedFixturePlanner()
        self.assertEqual(planner.plan_for("json_email").plan,
                         Plan("raw", "lower-only"))
        self.assertEqual(planner.plan_for(
            "json_email", advice=Plan("json-field", "trim-lower")).plan,
            Plan("json-field", "trim-lower"))

    def test_model_http_sends_no_task_data_or_keys(self):
        captured = []
        def transport(request, timeout):
            captured.append(json.loads(request.data))
            return MockResponse({
                "choices": [{"message": {
                    "content": json.dumps({
                        "extract_strategy": "json-field",
                        "normalise_strategy": "trim-lower",
                    })
                }}],
                "usage": {"prompt_tokens": 55, "completion_tokens": 12}
            })
        with patch.dict(os.environ, {"NERVE_LLM_API_KEY": "private-test-token"},
                        clear=True):
            planner = FormatChatPlanner(
                url="https://example.invalid/v1/chat/completions",
                model="local-stub", transport=transport)
            response = planner.plan_for(
                "json_email", advice=Plan("json-field", "trim-lower"))
        self.assertEqual(response.plan, Plan("json-field", "trim-lower"))
        self.assertEqual(response.input_tokens, 55)
        serialized = json.dumps(captured)
        self.assertNotIn("private-test-token", serialized)
        self.assertNotIn("heldout", serialized)
        self.assertIn("format: json_email.", serialized)

    def test_missing_private_key_rejected_without_network(self):
        calls = []
        def transport(*args, **kwargs):
            calls.append(args)
            return None
        with patch.dict(os.environ, {}, clear=True):
            planner = FormatChatPlanner(
                url="https://example.invalid/v1/chat/completions",
                model="stub", transport=transport)
            with self.assertRaises(RuntimeError):
                planner.plan_for("plain_email")
        self.assertEqual(calls, [])

    def test_task_generator_isolates_training_and_holdout(self):
        a, _ = make_task("json_email", 3, 2, training=True)
        b, _ = make_task("json_email", 3, 2, training=False)
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
