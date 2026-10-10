# NERVE Evolution v1.5 — Context-scoped agent learning research

## Overview

The v1.5 experiment evaluates one agent-planning interface on two
synthetic task formats: `json_email` and `plain_email`. Both use the same
four registered extraction/normalisation strategy pairs. The source
code never executes arbitrary generated Python or external commands.

Training episodes run all four registered plans on fixed, synthetic
training examples per format. The independent evaluator stores a 0/1
outcome score in local SQLite memory scoped by **agent and task format**.
Each arm then evaluates the same unseen inputs without writing
any new reward feedback. The tested model receives only the format
label and optionally a validated, allowlisted strategy recommendation.
**Raw inputs, expected answers and previously saved free-form text are
not transmitted to the remote model.**

## Repeatable studies

Install the official MCP Python SDK:

```bash
python -m pip install 'mcp==2.3.0'
export PYTHONPATH=src
```

Run a **capable, deterministic reference** that can choose correct tools
without any memory (both arms are expected to perform equally):

```bash
python scripts/agent_study_v15.py --seeds 2 --cases 3
```

Run a **deliberately limited** fixture that can benefit from feedback:

```bash
python scripts/agent_study_v15.py --limited-fixture --seeds 2 --cases 3
```

Run the full Chat Completions request/response parser through a fake
HTTP transport, with actual MCP stdio calls but **no paid model**:

```bash
python scripts/agent_study_v15.py --mock-api --seeds 2 --cases 3
```

The benchmark alternates AB/BA arm order across two or more seeds to
reduce order effects. The same registered capabilities, test cases,
decision counts, and tool stages are used for both arms. Training and
held-out input identifiers are disjoint. Individual wall-clock timing
is only indicative and not a proven speed advantage.

## Optional live model research (local only)

Only if you have a **new, privately provisioned** compatible provider
credential (never reuse a disclosed key), configure:

```bash
export NERVE_LLM_CHAT_URL='https://your-provider.example/v1/chat/completions'
export NERVE_LLM_MODEL='provider-model-id'
# Configure NERVE_LLM_API_KEY securely in this terminal / secret manager.
python scripts/agent_study_v15.py --live --seeds 1 --cases 2
```

With this command the harness sends **8 model requests**: one for each
arm/task combination across two formats and two held-out cases per
format. The fixed training stage runs locally through MCP. Live results
include paired task success, tool execution errors, mean end-to-end
wall time, model-reported processing time and prompt/completion tokens.
The endpoint must be HTTPS and is configured only by the operator.

## Scientific boundaries

- The capable fixture scores 100% both with and without memory in CI.
- The limited fixture improves after receiving synthetic feedback;
  it is intentionally a weak no-memory control.
- The capable model-protocol mock also scores 100% in both arms.
- **No live LLM accuracy, token-efficiency or speed improvement is claimed.**
- The evaluator tests only constructed, known tool choices, not open-ended
  reasoning, clinical tasks, world-model learning or new tool invention.
- The actual MCP server and registered tools run locally; no hosted
  multi-tenant authentication or distributed agent service is provided.
- Memory feedback is based on program-owned objective scoring, and
  unknown strategy names cannot become executable actions.
- The NERVE Jev integration is unrelated and remains fully optional.

Source: `src/nerve_awim/agent_study_v15.py` and
`scripts/agent_study_v15.py`.
