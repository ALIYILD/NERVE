# NERVE Evolution v1.4 — LLM agent + MCP evaluation harness

## What is implemented

NERVE offers a fixed, safe two-stage demonstration: extract an `email` field
from a synthetic JSON document, then normalise the address. An agent planner
chooses two **registered** strategy IDs; MCP executes those tools, never
model-supplied scripts, file operations or arbitrary commands.

The v1.4 harness compares **the same planner and task set**, with and
without previously evaluated NERVE experience recommendations. Both arms
get exactly one planner decision and two registered tool stages per task.
Model calls, task success, wall time and reported model token usage are
collected separately. Held-out task results are **never** saved as feedback.

## Run offline, without keys

```bash
python -m pip install 'mcp==2.3.0'
PYTHONPATH=src python scripts/llm_mcp_v14.py --cases 4
PYTHONPATH=src python scripts/llm_mcp_v14.py --mock-api --cases 4
```

The first command uses an explicitly labelled deterministic fixture,
not an LLM. The second runs the **real Chat Completions request/response
parser against a fake in-process HTTP transport**, through an actual MCP
SDK stdio client and server. Neither command makes a paid model request.

The fixture is intentionally weak without memory and accurate with
memory; this must **not** be treated as evidence that NERVE improves
reasoning, speed or token efficiency for capable real-world agents.

## Optional real provider test

Configure your own provider's compatible Chat Completions endpoint and
model **privately on your workstation**, using a fresh credential:

```bash
export NERVE_LLM_CHAT_URL='https://your-provider.example/v1/chat/completions'
export NERVE_LLM_MODEL='your-compatible-model-id'
# Set NERVE_LLM_API_KEY privately in the same terminal (do not paste it into chat).
PYTHONPATH=src python scripts/llm_mcp_v14.py --live --cases 2
```

External inference is **opt-in only**: the script never calls a provider
unless `--live` is supplied. All models receive only fixed synthetic task
objectives and allowlisted prior strategy IDs; no actual email payloads,
private patient data, medical records or prior conversations are sent.
Unknown tool IDs, extra JSON fields, malformed model responses, HTTP
redirects and insecure model endpoint URLs are rejected.

Model and endpoint availability, token billing and accuracy vary by
provider and have **not** been verified by CI. CI uses offline fixture
and mocked HTTP responses only.

## Research caveats

- No real model benchmark results have been produced yet.
- There is no automated weight training, human identity verification,
  clinical decision making, robot control or automatic skill deployment.
- The benchmark uses one deliberately small artificial task family; a
  capable LLM without memory may solve it just as well.
- A stronger follow-up will compare matched model costs and held-out
  task families, including negative and unsafe-outcome cases.
- Only a locally trusted MCP stdio client may access the demonstration;
  namespace IDs are not tenant authentication.

See `docs/nerve-learn-launch.md` for MCP server configuration.
