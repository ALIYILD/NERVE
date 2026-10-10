import io
import json
import os
import unittest
from unittest.mock import patch

from nerve_awim.llm_agent_v14 import (
    ChatCompletionsPlanner, FixturePlanner, Plan, parse_plan
)


class FakeResponse:
    def __init__(self, data):
        self.data = io.BytesIO(json.dumps(data).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, amount):
        return self.data.read(amount)


class ModelPlanningV14Tests(unittest.TestCase):
    def test_fixture_uses_only_known_ids(self):
        base = FixturePlanner().plan().plan
        guided = FixturePlanner().plan(
            advice={"extract": "json-field", "normalise": "trim-lower"}).plan
        self.assertEqual(base, Plan("raw", "lower-only"))
        self.assertEqual(guided, Plan("json-field", "trim-lower"))

    def test_strict_json_rejects_commands_extra_fields_and_unknown_ids(self):
        for answer in (
            '{"extract_strategy":"raw","normalise_strategy":"echo"}',
            '{"extract_strategy":"raw","normalise_strategy":"lower-only","exec":"x"}',
            "not json",
            '{"extract_strategy":1,"normalise_strategy":"trim-lower"}',
        ):
            with self.assertRaises((ValueError, json.JSONDecodeError)):
                parse_plan(answer)

    def test_live_client_does_not_send_task_inputs_or_credentials_in_body(self):
        requests = []

        def http(request, timeout):
            requests.append(request)
            return FakeResponse({
                "choices": [{"message": {"content": json.dumps({
                    "extract_strategy": "json-field",
                    "normalise_strategy": "trim-lower"
                })}}],
                "usage": {"prompt_tokens": 52, "completion_tokens": 18}
            })
        with patch.dict(os.environ, {"NERVE_LLM_API_KEY": "fake-test-key"}, clear=True):
            planner = ChatCompletionsPlanner(
                url="https://example.test/v1/chat/completions",
                model="test-model", transport=http,
            )
            answer = planner.plan(advice={
                "extract": "json-field", "normalise": "trim-lower"})
        self.assertEqual(answer.plan, Plan("json-field", "trim-lower"))
        self.assertEqual(answer.input_tokens, 52)
        self.assertEqual(len(requests), 1)
        body = requests[0].data.decode()
        self.assertNotIn("fake-test-key", body)
        self.assertNotIn("USER@EXAMPLE", body)
        self.assertIn("json-field", body)

    def test_forged_tool_names_fail_before_model_network(self):
        requests = []
        def forbidden(req, timeout):
            requests.append(req)
            raise AssertionError("network should not be used")
        with patch.dict(os.environ, {"NERVE_LLM_API_KEY": "test"}, clear=True):
            planner = ChatCompletionsPlanner(
                url="https://example.test/v1/chat/completions",
                model="test", transport=forbidden)
            with self.assertRaises(ValueError):
                planner.plan(advice={
                    "extract": "arbitrary-script",
                    "normalise": "trim-lower",
                })
        self.assertEqual(requests, [])

    def test_no_key_aborts_without_network(self):
        requests = []
        def forbidden(req, timeout):
            requests.append(req)
            return None
        with patch.dict(os.environ, {}, clear=True):
            planner = ChatCompletionsPlanner(
                url="https://example.test/v1/chat/completions",
                model="test", transport=forbidden)
            with self.assertRaises(RuntimeError):
                planner.plan()
        self.assertEqual(requests, [])

    def test_block_insecure_provider_endpoints(self):
        for url in (
            "http://external.test/v1/chat/completions",
            "https://user:password@example.test/v1/chat/completions",
            "https://example.test/v1/chat/completions?secret=1",
            "file:///tmp/chat/completions",
        ):
            with self.assertRaises(ValueError):
                ChatCompletionsPlanner(url=url, model="model")

    def test_malformed_live_answer_rejected_without_echo(self):
        def http(request, timeout):
            return FakeResponse({
                "choices": [{"message": {"content": "not a JSON plan"}}]
            })
        with patch.dict(os.environ, {"NERVE_LLM_API_KEY": "hidden"}, clear=True):
            planner = ChatCompletionsPlanner(
                url="https://example.test/v1/chat/completions",
                model="test", transport=http,
            )
            with self.assertRaisesRegex(RuntimeError, "model request failed"):
                planner.plan()


if __name__ == "__main__":
    unittest.main()
