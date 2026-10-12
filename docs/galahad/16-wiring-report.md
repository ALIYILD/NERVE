# NERVE wiring report

Branch: `feature/galahad-persistent-memory`. Starting checkpoint: `274e1d00b97683a67a7351341889eef959cd99b3`. This report accompanies the next local integration commit (`git log -1 --format=%H`). No push, pull request, merge or deployment. Other worktrees and production/clinical databases untouched.

## Applied to existing NERVE entrypoints

`agent_bridge_v13.DemoAgentBridge` now accepts an optional host-bound session. Existing `run_pipeline`/`run_pipelines` consume approved strict-schema hints to select only already registered extraction/normalisation functions. The existing bounded worker still executes parallel jobs. Hints have an observable effect on the real untrained demo result; they are not unused context. Legacy behavior and output shape stay unchanged without the optional session.

`learn_mcp.create_server` passes the same optional session into that bridge and exposes three scoped tools. Its CLI now loads a trusted configuration and fixed subject with paired arguments. Actor/scope/approval/KV parameters are absent from tool schemas. The entire process remains trusted-local: existing legacy namespace tools are not transformed into remote multi-tenant authentication. Explicit `run_demo_agent_plan` stays a pure allowlisted-tool call, not implicit memory selection.

New runtime factory connects existing MemoryAuthority, TrustedMemoryLedger, PinnedOIDCVerifier and MemoryService with the gateway and bound sessions. Strict config, public-only JWKS and all grants/selected subject validate before database creation. New local HTTP launcher enforces loopback binding, bounded concurrent workers, socket inactivity limits and silent request logging. Operator config/JWKS are still required for a persistent local service; the example does not contain credentials.

New one-command synthetic demo exercises real signed HTTP, pending proposal exclusion, trusted fixture approval, existing agent execution, parallel tasks, new runtime/ledger reopen, patient-context denial and revocation. It uses temporary data/keys and removes them after completion. The official MCP smoke launches a separate real stdio server and exercises its tool discovery, query, proposal and agent execution.

Existing bounded evolution and external one-use holdout commands remain independently runnable host research workflows. No agent receives holdout evaluation authority, arbitrary code execution, model-training or promotion permissions.

## Evidence

- Final full suite with optional SDK installed: **992 tests passed in 109.431 seconds**, zero failures/errors/skips. Previous checkpoint951; added41 tests (agent13, MCP CLI13, runtime15).
- Official **MCP2.3.0** stdio smoke passed; three new tools discovered; approved query, pending exclusion and existing demo execution verified.
- Signed HTTP workflows passed with Null provider and unavailable Galahad provider. Both used ordinary prefill; Galahad availability and cache purge confirmation remained false.
- Syntax and whitespace checks passed. `pip check` reported no broken requirements.
- Optional local environment audit initially found11 vulnerability records in bootstrap pip21.2.3/setuptools57.4.0. Upgraded only the task venv to pip26.2.1/setuptools84.0.0; final scan of15 local distributions found zero known vulnerabilities. That scan excludes inherited system-site packages and is not a comprehensive system audit.
- Independent review fixes: invalid MCP subject rejected before ledger changes; CLI startup errors sanitised; deeply nested approved JSON now falls back instead of crashing. Existing malformed/foreign/revoked/conflicting hint tests, quota handling and data-minimised outcome tests pass.

Evidence files: `evidence/validation-wiring.json`, `mcp-wire.json`, `wired-null.json`, `wired-galahad-fallback.json`, `mcp-environment-audit.json`. This work measures functional integration, not a new performance advantage; earlier CPU benchmark values/methodology remain in their dated artifacts.

## Reproduce now

```sh
cd /Users/aliyildirim/nerve-galahad
PYTHONPATH=src .venv/bin/python scripts/memory_gateway_demo.py
PYTHONPATH=src .venv/bin/python scripts/memory_gateway_demo.py --provider galahad
PYTHONPATH=src .venv/bin/python scripts/memory_gateway_mcp_wire.py
.venv/bin/python scripts/verify_galahad.py baseline
```

For a fresh checkout, install `deploy/requirements-memory-synthetic.txt` in a virtual environment as described in README. The localhost workflows require permission to bind a temporary local server. The [runtime guide](15-runtime-wiring.md) includes strict configuration, independent host/service and MCP launch commands. No keys or bearer credentials need to be pasted into prompts or committed.

## Remaining limits

The wired agent is the existing synthetic registered-tool demo, not every NERVE model or specialist. Other agents can receive `BoundMemorySession` through trusted host code but are not silently rewired. WorldCore, external LLM providers and Clinical OS are not newly connected to model inference. The inference endpoint still returns501.

Galahad remains an unavailable admission adapter: actual connector execution, supported Linux/GPU/licence, KV identity enforcement, encrypted storage/deletion and durable tensor restoration need external verification and implementation. Selecting provider=galahad only demonstrates safe fallback. No performance, commercial-readiness or clinical validation claim.

Trusted local MCP is not a public network auth boundary. Ledger is plaintext research storage. Absolute upload deadlines/TLS/production supervision, distributed consent/revocation and formal clinical governance remain unvalidated. Pending outcomes contain fixed task/strategy/completion metadata only, with correctness unverified; no automatic promotion or live care actions.

## Files changed in this wiring checkpoint

Existing source: `src/nerve_awim/agent_bridge_v13.py`, `src/nerve_awim/learn_mcp.py`.

Added source: `memory_gateway/session.py`, `runtime.py`, `mcp_tools.py`.

Added executables: `scripts/serve_memory_gateway.py`, `memory_gateway_demo.py`, `memory_gateway_mcp_wire.py`.

Added tests: `tests/test_memory_agent_wiring.py`, `test_memory_gateway_mcp.py`, `test_memory_runtime.py`.

Configuration/tooling: `configs/memory-gateway.synthetic.example.json`, `deploy/requirements-memory-synthetic.txt`, `scripts/verify_galahad.py`, `.github/workflows/galahad-memory.yml`.

Documentation: README, updated Galahad agent/readiness/report pages, runtime guide, this report and five integration/audit evidence files. The ignored local `.venv` is not committed. Remote CI workflow execution remains unverified until a separately authorised push/PR.
