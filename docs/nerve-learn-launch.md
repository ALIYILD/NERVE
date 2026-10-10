# NERVE Learn — public developer preview

An open-source, local-first experience and feedback service for external agents.

## Try locally

Install the project and the official MCP SDK in an isolated environment:

```bash
pip install "mcp>=2,<3"
PYTHONPATH=src NERVE_LEARN_DB=./nerve-learn.db python -m nerve_awim.learn_mcp
```

Connect the process as a **stdio MCP server** in a compatible host. Install `skills/nerve-learn/SKILL.md` in an OpenClaw workspace if desired.

### What v0 supports
- Agent-specific experience storage
- Explicit outcome feedback
- Literal task retrieval
- High-scoring candidate lesson suggestions
- Local SQLite persistence

### What it does not support
- Model-weight learning or provable speedups
- Federated knowledge sharing
- Secure multi-tenant hosted access
- Automatic modification of agent code or instructions
- Encrypted storage, policy-grade human authorisation, or production privacy guarantees

Do not expose the stdio server directly to untrusted remote users. The caller-supplied agent ID is a convenience namespace, **not authentication**.

## Distribution

Publish the skill through ClawHub after review using `clawhub skill publish ./skills/nerve-learn --slug nerve-learn --name "NERVE Learn"`. This step requires ClawHub account authorisation and has not yet occurred.

## Suggested first evaluation

Compare the same agent on repeated tasks with and without opt-in retrieval. Measure success, error rate, hallucinations, elapsed time, token consumption and user satisfaction using identical tasks and budgets. Publish negative as well as positive results.


## Outcome-aware strategy selection and parallel research

The MCP stdio server now also registers `select_evaluated_strategy(agent_id,
context,limit)`, which ranks previously scored experiences from the local
NERVE Learn SQLite database. Output is **untrusted advice**, not an instruction,
system prompt or permission to call external tools.

Developers may run the parallel Evolution research benchmark locally:

```bash
PYTHONPATH=src python benchmarks/v11_parallel_evolution.py
PYTHONPATH=src python benchmarks/v11_memory_effectiveness.py
```

This uses only local Python code and synthetic WorldCore scenarios; an
optional `mcp` package is needed only to launch the external stdio MCP host.
The parallel research coordinator cannot be invoked remotely through the MCP
server and does not support distributed agent workers or automatic deployment.

Agent IDs supplied by callers are not secure authentication. Keep the local
service private until there is real identity, tenant isolation and appropriate
data-protection engineering.

## Evolution v1.3 — Executable agent demo through MCP

`learn_mcp.py` now exposes five additional demo tools for compatible
local MCP clients, alongside the existing memory tools:

- `list_demo_agent_capabilities()` — discover the two fixed safe contexts;
- `train_demo_agent_on_fixtures()` — score known built-in Python handlers
  against trusted program-owned examples, without caller-supplied rewards;
- `choose_demo_agent_strategy(context,policy)` — recommend an allowlisted
  strategy using `utility` or `recency` feedback selection;
- `run_demo_agent_pipeline(task_id,email_document,policy)` — execute a
  two-stage JSON-field extraction and email-normalisation pipeline;
- `run_demo_agent_pipelines(tasks,policy)` — concurrently execute up to
  16 independent pipelines with deterministic result order.

The input is a JSON string containing exactly the `email` key. For example:

```json
{"email": "  USER@EXAMPLE.ORG  "}
```

After calling `train_demo_agent_on_fixtures()`,
`run_demo_agent_pipeline("t1", "{\"email\": \"  USER@EXAMPLE.ORG  \"}")`
returns `user@example.org` when using the trained `utility` policy.
The training samples are fixed. Returned strategy names are looked up only
in an explicit static registry of pure Python string functions. **No
model-generated code, unrestricted tools, shell commands, credentials,
clinical devices or API calls are executed.**

To run the independent benchmark:

```bash
PYTHONPATH=src python benchmarks/v13_external_mcp.py
```

The experiment compares utility-based selection, recency-only selection
and an explicitly **fixed-correct** non-learning pipeline on the same
synthetic held-out inputs. The fixed-correct control is essential: strategy
memory must not be advertised as inherently superior to a well-configured
single agent. The built-in MCP API is currently covered with mocked MCP
registration and actual Python handler execution; end-to-end external
client/SDK protocol interoperability must still be validated separately.

**Security:** `NERVE_DEMO_AGENT_ID` optionally configures one local
demo namespace at server startup. It is not a user authentication or
tenant isolation mechanism. Use stdio only for local trusted clients; do
not expose this demonstration as a multi-tenant HTTP service. Keep input
synthetic and never persist private clinical data or credentials.
