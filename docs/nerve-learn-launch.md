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
single agent. The MCP server is tested with both mocked tool registration and the
**official MCP Python SDK 2.3.0** using a real subprocess/stdin/stdout MCP
client-server session. GitHub Actions run 38082358322 verified tool
discovery, trusted fixture training, single and parallel two-stage calls.

**Security:** `NERVE_DEMO_AGENT_ID` optionally configures one local
demo namespace at server startup. It is not a user authentication or
tenant isolation mechanism. Use stdio only for local trusted clients; do
not expose this demonstration as a multi-tenant HTTP service. Keep input
synthetic and never persist private clinical data or credentials.

## Real SDK interoperability (verified in CI)

NERVE supports the current MCP 2.x `MCPServer` API and retains a fallback
for older MCP 1.x `FastMCP` registration. The real, credential-free
stdio test is:

```bash
python -m pip install "mcp==2.3.0"
PYTHONPATH=src python scripts/mcp_wire_v13.py
```

A compatible local MCP host can launch the server with the following
configuration (replace the absolute paths with your own):

```json
{
  "mcpServers": {
    "nerve-learn": {
      "command": "python3",
      "args": ["-m", "nerve_awim.learn_mcp"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/NERVE/src",
        "NERVE_LEARN_DB": "/absolute/path/to/private/nerve-learn.sqlite",
        "NERVE_DEMO_AGENT_ID": "my-local-demo"
      }
    }
  }
}
```

The exact host configuration varies between OpenClaw, Claude clients, and
other MCP-compatible applications. The integration test verifies MCP
interoperability at the protocol level, **not** a published ClawHub listing
or verified installation in every third-party client.

The local demo remains inert: no filesystem mutation beyond the opted-in
SQLite experience store, no network access by demo handlers, no clinical
actions, and no automatic promotion of learned strategies to production.

## v1.8 security change — generic write tools default disabled

**Breaking hardening default:** The generic MCP methods
`record_experience` and `rate_experience` still appear in the tool
catalog, but they now reject calls unless the server operator starts a
**fully trusted, local, single-user research service** with
`NERVE_ENABLE_LEGACY_MCP_WRITES=1`. This is an intentional protection
against unverified caller-supplied numeric rewards influencing agent
strategy suggestions. The switch is **not authentication** and MUST
NOT be set on a public or shared network service.

Trusted built-in synthetic fixture training, evaluated agent experiments,
and local read-only memory tools are unaffected. The new
`memory_v18.py` verified local ledger is a separate research data path
and **is not exposed as public MCP tools** until authenticated identity,
verified feedback provenance, revocation/forget propagation, and
tenant controls are implemented.

For the optional Mem0 OSS read-only adapter, Obsidian-reviewed Markdown
preview, and SQL baseline, see
`docs/memory-v18-implementation.md`. No automatic migration is performed.
