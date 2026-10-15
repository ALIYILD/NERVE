# Agent integration

The MemoryGateway is a trusted-host facade. Agents receive neither MemoryAuthority nor provider management primitives. Existing parallel workers, agent registries and advisory JEV remain independent. No new agent executor or shell interface is added.

NERVE Learn MCP now accepts an optional host-issued `BoundMemorySession` through `create_server(db_path, memory_session=session)`. Without that argument, tool registration and the default-disabled legacy write behaviour remain unchanged. The trusted host constructs the session from an existing gateway, actor and scope; MCP never issues capabilities or accepts caller-selected tenant, agent or clinical context.

The optional tools are:

- `verified_memory_query(query, limit=5)`: bounded approved-evidence retrieval in the host-bound scope.
- `propose_verified_experience(content, source_id)`: creates a pending experience, requiring independent host review before reuse.
- `verified_memory_health()`: reports availability through the bound session.

The tool name `propose_verified_experience` does not mean an agent can verify its own proposal. There is no approval, revocation administration, cache identity, KV restoration or provider-management tool. Exact session class validation rejects arbitrary duck-typed objects. Queries are capped at 256 characters and 20 results; proposed text at 2,048 characters and source identifiers at 96 characters, with existing ledger validation authoritative. Evidence remains untrusted data, never system instructions.

The host independently approves or rejects proposed records through the existing ledger/gateway review process. Revoked records stop appearing in subsequent tool queries; capability revocation blocks the tools. This optional local MCP integration is not network authentication. A remote deployment still needs the independently authenticated MemoryService boundary and externally governed host grants.

Tests in `test_memory_gateway_mcp.py` exercise fake SDK registration against real sessions, gateway and SQLite records, including pending-to-approved-to-revoked lifecycle, capability revocation, bounded input, absent identity/approval schemas and disabled defaults. Registration fixtures are distinct from real wire verification. The separately installed official SDK now also passes the stdio smoke described below.

The intended host cycle is identity → fixed scope → gateway context → existing specialist → independent review → proposed memory. Model inference, automatic attachment to every legacy agent, shared KV caches and live Clinical OS integration remain outside this local integration. Synthetic responses require review. JEV has no path to override permissions.

The same injected session also reaches the existing `DemoAgentBridge` created by NERVE Learn. Existing `run_demo_agent_pipeline`/pipeline tools therefore execute the bridge's approved-memory path and propose pending outcome observations when authorised. With no session, the original return shape and strategy selection remain unchanged. Eight new MCP tests and five existing MCP regression tests pass; the demo tests assert injection of the exact same session instance and executable outcome proposals through existing tools.

The module is also executable with an operator-owned configuration:

```sh
PYTHONPATH=src python3 -m nerve_awim.learn_mcp --memory-config /operator/memory-runtime.json --memory-subject configured-subject
```

Both arguments are mandatory together. The subject selects a session from the trusted runtime configuration; it is a local process-launch choice, never an MCP caller claim. Unknown subjects and invalid configurations abort startup. Running `python3 -m nerve_awim.learn_mcp` without arguments preserves the previous default. The launcher does not accept an agent-provided tenant, patient context or key.

`scripts/memory_gateway_mcp_wire.py` exercises the official SDK over stdio using a temporary operator configuration, ephemeral RSA public key, approved synthetic strategy hint and fresh SQLite stores. It checks actual tool discovery, bounded schemas, pending-record exclusion, and the existing demo's consumption of the approved hint and pending outcome proposal. A 30-second timeout bounds the smoke; missing SDK returns an explicit blocked result with nonzero exit. Eleven registration/CLI tests and five existing MCP regressions pass locally.

Verified locally with `.venv/bin/python` and official `mcp==2.3.0`: the real stdio smoke passed all three tool registrations, approved evidence query, pending proposal exclusion, existing demo approved-hint consumption and pending outcome recording. The smoke does not test network MCP transport, remote identity or clinical workflows. KV restoration remains disabled.

The optional verified-memory session does **not** authenticate every legacy MCP tool. Existing agent-ID arguments remain local namespaces. The server remains a trusted local stdio process, and its older tools retain their documented local trust assumptions. In particular, `run_demo_agent_plan` intentionally executes explicitly named, registered pure-string tools without memory selection; this existing path is not a memory-backed recommendation or privileged capability. Bind remote identities through the separate authenticated service, not by exposing this entire legacy tool collection as an authenticated API.

Launcher subject eligibility is checked by the runtime loader before ledger creation. Expected configuration, SQLite, dependency and server startup errors return a generic diagnostic without exception paths or tokens. Process interrupts remain interrupts.
