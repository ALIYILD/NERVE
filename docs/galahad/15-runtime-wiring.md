# Executable NERVE memory wiring

This opt-in integration connects the existing NERVE demo agent, its bounded parallel worker, Learn MCP and the authenticated memory HTTP service to one verified gateway. It is synthetic research software. Other NERVE agents retain their existing behavior; WorldCore/device/clinical models are not newly wired to an inference runtime.

## Run the complete checks

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools
.venv/bin/python -m pip install -r deploy/requirements-memory-synthetic.txt
PYTHONPATH=src .venv/bin/python scripts/memory_gateway_demo.py
PYTHONPATH=src .venv/bin/python scripts/memory_gateway_demo.py --provider galahad
PYTHONPATH=src .venv/bin/python scripts/memory_gateway_mcp_wire.py
.venv/bin/python scripts/verify_galahad.py cpu
```

The demo creates temporary signing keys, public JWKS, host configuration and stores, starts an authenticated loopback server, proposes a pending strategy hint, verifies it is excluded, approves the exact fixed fixture through the trusted host, runs the existing agent and parallel jobs, reopens the ledger, denies another patient fixture and revokes the source. All temporary resources are removed. The private key remains in process memory; reports contain aggregate results only.

The MCP smoke launches the real `nerve_awim.learn_mcp` process using the official SDK, discovers the three new tools, retrieves approved evidence, verifies pending proposals stay unavailable and runs the existing demo tool with the same bound session. It exits nonzero if unavailable or any assertion fails. It is not a fake SDK transport.

`--provider galahad` configures the unavailable provider and verifies normal approved-text fallback. Provider availability and runtime KV restoration remain false; failed cache purge is reported false. This does not install/activate Galahad or run model inference.

## Host configuration and local service

Start from `configs/memory-gateway.synthetic.example.json`. Copy it to a private research directory and supply an operator-provisioned **public** RSA JWKS file. The example is not provisioned with credentials or a signing key. Issuer/audience must match externally issued JWTs. Config and JWKS are bounded, duplicate-free strict JSON; private RSA components are rejected. All grants and an optional requested MCP subject validate before ledger creation. Paths are resolved relative to the config file.

The strict schema has version1, synthetic_only=true, ledger_path, provider(null/galahad), max_records_per_scope, oidc(issuer/audience/jwks_path) and grants. Each grant fixes subject, tenant_id, agent_id, application, user, clinic_id, patient_id, session_id and reader/writer/admin roles. Subject roles must also appear as signed nerve-memory-reader/writer/admin roles for HTTP. Caller fields cannot replace the grant scope.

```sh
PYTHONPATH=src .venv/bin/python scripts/serve_memory_gateway.py --config /private/research/runtime.json --check
PYTHONPATH=src .venv/bin/python scripts/serve_memory_gateway.py --config /private/research/runtime.json --host 127.0.0.1 --port 8766
```

`--check` initializes the configured synthetic ledger and quota policy but does not listen. Readiness can report the text service ready while provider restoration is blocked. The server binds only literal loopback addresses, limits active workers and enforces socket inactivity timeouts. Request logging is suppressed. These are local hosting controls, not production TLS, absolute upload deadlines or external clinical deployment approval.

The Python `MemoryClient` accepts externally obtained bearer tokens and only HTTPS by default. Tests explicitly allow loopback HTTP. Admin HTTP operations revoke/delete existing records; no approval endpoint is exposed. Store quotas persist in SQLite and conflicting restart configuration fails. The existing ledger remains plaintext.

## Trusted local MCP launch

```sh
NERVE_LEARN_DB=/private/research/legacy.sqlite PYTHONPATH=src .venv/bin/python -m nerve_awim.learn_mcp --memory-config /private/research/runtime.json --memory-subject synthetic-clinician
```

The two memory arguments are mandatory together. The **trusted process launcher** chooses the configured subject; it is not a tool argument. This is local stdio trust, not remote bearer authentication. Do not expose the process to mutually untrusted users. Existing legacy MCP tools still use caller-supplied agent namespaces for their unverified research store. Their permissions have not become tenant authentication merely because scoped tools are present.

New tools: `verified_memory_query(query,limit)`, `propose_verified_experience(content,source_id)` and `verified_memory_health()`. No tenant/agent/context override, approve, evaluator, cache-management or shell parameters. Proposals remain pending. The same host-bound session is passed to existing `run_demo_agent_pipeline` and `run_demo_agent_pipelines`. Legacy behavior is unchanged without the optional session. The explicit `run_demo_agent_plan` remains a pure allowlisted-tool operation and intentionally does not select memory hints.

## Agent behavior

Approved content influences the existing demo only when it exactly matches:

```json
{"schema":"nerve-demo-strategy-v1","task":"email-normalization","extract":"json-field","normalise":"trim-lower"}
```

Both strategy identifiers must already exist in the fixed registry. A single consistent approved hint selects those registered functions through the existing `execute_plan`; it does not execute stored code or instructions. Pending, revoked and foreign records cannot participate. Malformed/duplicate/deeply nested data is ignored; conflicting valid hints use the existing default policy. Revoked session access fails closed. No claim is made that approved hints are generally optimal.

Outputs expose source provenance and whether a hint was used. An agent may propose an outcome containing fixed task category, strategy identifiers and execution-completed metadata. It includes no input email, task identifier, output text or reward; correctness is explicitly unverified. Read-only sessions do not propose. A storage/quota failure returns the deterministic result with outcome_memory.status=not_recorded, while a permission failure propagates. Independent review/approval stays in trusted host code.

## Remaining boundaries

No arbitrary stored instructions, registry changes, model-weight updates, automatic release promotion, real patient data or clinical decisions. The existing external holdout and bounded experiment commands remain separate host-run research operations; the new agent cannot consume holdouts through MCP. Galahad GPU compatibility/licence/runtime identity/encrypted deletion and actual restart restoration remain unverified. No branch is merged or service deployed by these commands.
