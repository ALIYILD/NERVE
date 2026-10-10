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
