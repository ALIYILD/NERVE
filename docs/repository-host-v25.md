# Authenticated repository shadow host v2.5

The [v2.6 extension](bound-repository-host-v26.md) now adds an optional, persisted
operator binding to trials and monitored promotion. The standalone entrypoint
uses that extended host; the unbound shadow behaviour below remains the default.

This pilot connects signed HTTP requests to the existing repository tool and
shadow-learning engine. It serves the capable AST inventory tool and gathers
independently judged evidence without changing its release. It is a loopback
service for a trusted host behind a TLS proxy, not a deployed public service or
Clinical OS integration. No external LLM calls, credentials or billing are used.

## Provision and run

Install `PyJWT[crypto]>=2.10,<3`. Provision a JSON configuration **outside the
repository**, containing the exact keys below. Supply your identity provider's
actual public RSA JWK set, issuer, audience and authorised subjects. The sample
has no usable signing key and cannot authenticate anyone as written.

```json
{
  "issuer": "https://YOUR-IDENTITY-PROVIDER",
  "audience": "nerve-repository-pilot",
  "jwks": {"keys": []},
  "grants": [
    {"subject": "YOUR-RUNTIME-SUBJECT", "tenant": "lab", "agent": "inventory",
     "roles": ["runtime"]},
    {"subject": "YOUR-AUDITOR-SUBJECT", "tenant": "lab", "agent": "inventory",
     "roles": ["auditor"]}
  ]
}
```

```bash
PYTHONPATH=src python scripts/serve_repository_host_v25.py \
  --config /secure/nerve-public-identity.json \
  --database /persistent/nerve-pilot.db --port 8765 --bootstrap
```

`--bootstrap` explicitly permits initialisation of missing configured scopes.
Omit it on subsequent starts. Scope creation is an offline host action; there is
no bootstrap HTTP route. Protect configuration and persistent storage from agent
writes. Use public JWKS only; no provider private signing keys belong here.
Changes to tool/judge semantics require a new reviewed contract/namespace, as in
v2.0. This host uses contract `repository-host-v25-tools-v1`.

The server listens only on `127.0.0.1`. An actual hosted pilot needs a TLS reverse
proxy, a provisioned IdP, supervision, firewall/rate limits, persistent disk and
backup/retention policy. Do not expose Python's reference WSGI server directly to
the internet. Header and connection limits are the proxy's responsibility. The
built-in server sets a five-second socket timeout and bounds JSON body size; it
does not provide process isolation or pre-empt a stuck handler.

## HTTP contract

Both endpoints require `Authorization: Bearer <signed JWT>`. The pinned verifier
checks RS256 signatures, key IDs, issuer, audience and token lifetime. The host
intersects the signed `roles` claim with its own principal grants. A runtime token
must contain `nerve-runtime`; an auditor token must contain `nerve-auditor`.
Tenant/agent selection comes entirely from configuration, never token custom
claims or request JSON. One subject maps to one scope; unknown subjects fail.

| Endpoint | Role | Request and result |
|---|---|---|
| `POST /v1/tasks` | runtime | JSON with exactly `task_id` and `source`; returns function names, immutable release/generation, strategy and shadow-mode metadata |
| `GET /v1/evidence` | auditor | Returns only the caller's scope's aggregate shadow evidence, queue counts and unknown cost (`null`) |

Example request body:

```json
{"task_id":"repo-file-001","source":"def top_level():\n    def nested(): pass\n"}
```

The result is `["top_level"]`. Submitted source is parsed, never imported or
executed. Task IDs follow the existing bounded identifier format. Bodies are
limited to 20,000 bytes; canonical task payloads remain limited to 16,384 bytes.
Ambiguous duplicate JSON fields, unknown fields, query strings and unexpected
content types are rejected. Error responses exclude tokens/source/exception text.
Responses are `no-store`; the CLI disables access logging. Configure proxy logs
to exclude credentials and source bodies too.

## Learning and release boundary

After sending a response, the single-process server drains up to eight queued
tasks per configured scope before accepting its next request. It judges the
actual output and then executes matched read-only training alternatives using
v2.1. Primary results do not wait for their own learning pass, although draining
can delay the next request. There is no remote training/drain endpoint.

Only aggregate outcomes, task identifiers/hashes and measured latency persist.
Raw inputs/outputs in the bounded in-memory queue are lost on restart. A full
queue drops learning observations while preserving the task result; evidence
reports expose dropped counts. The response's `queued_best_effort` is not a
durable acceptance guarantee. Identifiers/hashes are not anonymisation. Queue
and per-subject rate limits are process-local and reset on restart; they are not
cluster-wide quotas. Up to 64 principals and queue capacity 32 per scope are the
pilot defaults. One host process owns each database/queue deployment. The Linux
service command enforces this with a database-inode advisory lock; embedded API
users must provide their own single-owner lifecycle. See the operations guide.

The host pins the initial AST baseline release and generation zero. If an offline
operator changes that scope's deployment, subsequent tasks fail closed with 503;
a restart also refuses to silently adopt it. The snapshot check prevents a
changed route being served through the shadow endpoint. An already-started
baseline request can finish using its immutable original route snapshot.

There are no HTTP promotion, rollback, candidate, evaluator or operator APIs.
The v2.3/v2.4 trial and promotion-monitor controls remain trusted host APIs.
The [v2.6 binding](bound-repository-host-v26.md) now connects an explicitly
reviewed trial to this HTTP deployment; it exposes no remote control authority.
Use independent reserved holdouts and offline review before deployment changes.

## Verification and remaining work

Tests exercise real signed JWTs, HTTP over loopback, the standalone server and
restart persistence, cross-tenant denial, role intersection, expired/forged
credentials, schema/body bounds, source exclusion, queue overflow, replay
protection and refusal to adopt changed releases. Test-only signing keys are
created in memory; no identity-provider key is committed.

This verifies the adapter and transport using locally generated identities.
Actual IdP provisioning, public hosting, live task collection and independently
curated performance evidence remain pending. The strong AST baseline is not
claimed to improve merely because this service now collects evidence.
