# Version 1 synthetic memory service

Implemented: `memory_gateway/service.py` exposes a WSGI application using the existing operator-pinned `PinnedOIDCVerifier`. `openapi.json` is the versioned route/request/error contract; `memory_gateway/client.py` is a Python reference client. Nothing is deployed.

The host creates `MemoryAuthority` actors offline, constructs `MemoryScope` through `synthetic_scope`, then binds each authenticated subject to one `MemoryGrant`. Scope includes tenant/agent and a canonical hash of application, user, clinic, patient and session. The service never reads tenant/agent/permissions from caller JSON. Caller patient and clinic values must exactly match the offline grant. The host is responsible for constructing the matching scope and clinic/patient grant; service configuration is trusted and never supplied by a request. Different session/user contexts require distinct grants and contexts; multi-context dispatch is deliberately not implicit.

Roles must exist both in the configured grant (`reader`, `writer`, `admin`) and the signed JWT (`nerve-memory-reader`, `nerve-memory-writer`, `nerve-memory-admin`). JWTs require the pinned issuer/audience, supported RS256 key, subject, issued-at and expiry. Actor revocation is checked on every request, including health. Configured grant changes currently require host restart. JWT revocation before expiry requires external identity lifecycle controls.

| Route | Role | Behaviour |
|---|---|---|
| GET /v1/memory/capabilities | reader | Synthetic-only capability metadata |
| GET /v1/memory/health | reader | Gateway/provider readiness |
| GET /v1/memory/metrics | admin | Counters only for the granted scope |
| POST /v1/memory/query | reader | Approved evidence and provenance; review required |
| POST /v1/memory/experiences | writer | Pending episodic proposal |
| POST /v1/memory/feedback | writer | Pending episodic proposal, never approval or score mutation |
| POST /v1/memory/revoke | admin | Revoke one exact-scope record; invalidation status |
| DELETE /v1/memory/records/{id} | admin | Delete one exact-scope local record; invalidation status |
| POST /v1/inference/respond | reader | Optional bounded local-model synthesis; 501 when unconfigured |
| POST /v1/memory/scopes/revoke | admin | Durable exact-scope revocation |
| DELETE /v1/memory/scopes/current | admin | Scoped local deletion; revocation tombstone retained |

Every POST/DELETE requires `clinic_id` and `patient_id`. Query additionally requires `query` (1–256 characters) and `limit` (1–20). Experiences/feedback require `content` (1–2048 characters) and `source_id`; revoke requires `memory_id`. Delete requires only the two scope fields. Unknown/duplicate fields, incomplete bodies and nonfinite JSON are rejected. JWT authentication occurs before body reads. The service lock protects only atomic per-principal rate accounting; it is never held during client reads, JWT verification or gateway/provider I/O. After a body read, token expiry and actor capability are checked again before parsing or taking action. A stalled authenticated upload therefore cannot monopolise the service lock. The hosting WSGI server still needs concurrent workers and enforced upload deadlines; application code cannot cancel arbitrary blocking input streams. Errors contain stable generic identifiers, no payloads or tracebacks; responses use `Cache-Control: no-store`. Administrative actions still require the relevant host-issued read/approve/delete permissions.

Example synthetic query:

```json
{"clinic_id":"synthetic-clinic","patient_id":"synthetic-patient","query":"fixture","limit":5}
```

Example client (obtain credentials through your separately configured IdP; never hardcode them):

```python
from nerve_awim.memory_gateway.client import MemoryClient
client = MemoryClient("https://your-operator-memory-host.example", token)
result = client.query(clinic_id="synthetic-clinic", patient_id="synthetic-patient", query="fixture")
assert result["review_required"] is True
```

The client accepts HTTPS origins or explicitly enabled loopback HTTP, disables redirects to prevent bearer forwarding and bounds response size/timeout. Run the WSGI application behind a trusted TLS reverse proxy with timeouts, request limits and scrubbed access logs. No public deployment script or automatic service launch is provided.

Independent verification: `PYTHONPATH=src python3 -m unittest discover -s tests -p test_memory_service.py -v`. Tests execute signed JWT requests against the real WSGI boundary and verify pending → offline approval → evidence retrieval → revoke/delete. Keys and stores are temporary. Optional synthetic inference is described below; retrieved evidence and generated text are never a diagnosis or treatment recommendation.

```mermaid
flowchart LR
    C[Synthetic client] --> T[Operator TLS proxy: deployment gate]
    T --> S[MemoryService: pinned OIDC + offline grant]
    S --> G[MemoryGateway: exact scope]
    G --> L[v1.8 verified ledger]
    G --> K[Optional KV provider: restore blocked]
    S --> R[Evidence + provenance + review required]
```


## Optional local inference

The default remains disabled (HTTP 501). A trusted host may add this exact optional config before starting the runtime:

```json
"inference": {
  "base_url": "http://127.0.0.1:8000",
  "model": "operator-selected-model",
  "max_output_tokens": 256,
  "timeout_seconds": 10
}
```

The host must separately run a compatible local `/v1/chat/completions` endpoint. Only literal loopback HTTP origins with explicit ports are accepted; no DNS hostnames, remote URLs, credentials, redirects or environment HTTP proxies. Config validates before ledger creation. This code does not download or launch models, install GPU runtimes, or claim a real model was exercised by fixture tests.

Configured `/v1/inference/respond` accepts exactly `clinic_id`, `patient_id`, `query`, `limit`. It authenticates and retrieves approved scoped evidence first. With no approved evidence it abstains without a network call. Otherwise the adapter sends fixed system instructions and a separate JSON data message containing the query and evidence, using the host-selected model. Token budget is capped at 2048, response at 64 KiB/16384 output characters, and socket timeout at 30 seconds. Four simultaneous calls maximum; three transport/contract failures open a 30-second circuit; no retries. These are socket inactivity timeouts, not a proof of a hard wall-clock deadline against a deliberately trickling server.

The response must name the exact configured model, use assistant text, and finish normally; tool/function calls, unexpected models, truncated/unknown completion states, oversized content and invalid usage counters are rejected. The adapter rechecks authoritative sources and capability after network completion; changed/revoked/expired/deleted sources discard the generated output. The service also rechecks token expiry and durable scope authorization. Responses include evidence/provenance, model, available provider-reported token counts, `review_required=true`, `synthetic_only=true`, `kv_status="prefill"` and `persistent_kv_restored=false`.

Returned text is untrusted and is never executed or used for clinical actions. System/data separation is not complete prompt-injection protection. The exact model-name check detects routing mistakes; it does not attest model weights or establish KV compatibility. The synthetic HTTP fixtures in `test_memory_inference.py` test the runtime contract, not real model quality, GPU performance or persistent cache behavior.

Scope administrators can revoke the entire configured context via `/v1/memory/scopes/revoke` and delete its local records via `/v1/memory/scopes/current`; both require only the exact clinic/patient pair and the signed plus configured admin role. Revocation blocks ordinary queries and metadata access across restart. Administrative deletion remains available after revocation and never clears the durable tombstone or claims backup erasure.
