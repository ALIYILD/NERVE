# Synthetic operations runbook

Use Python 3.10+ locally; repository CI uses 3.12 and PyJWT[crypto]. Keep Galahad optional. Use only synthetic fixtures; no real patient records or production databases. Reference alert rules and exported metrics are supplied as local artifacts, not a deployed monitoring service.

## Verification and evidence-based readiness

The existing `scripts/verify_galahad.py` runs fixed test groups. `scripts/memory_operations.py` wraps those actual commands and records strict, bounded, atomic JSON manifests containing counts, success, time, Git revision and a SHA256 fingerprint of source/scripts/tests/deployment/workflow files. The fingerprint catches uncommitted changes. Raw subprocess output, source text, credentials and local paths are not written to manifests. Each subprocess is bounded to 300 seconds. Run from repository root:

```sh
PYTHONPATH=src python3 scripts/memory_operations.py verify --gate cpu --output /tmp/nerve-cpu.json
PYTHONPATH=src python3 scripts/memory_operations.py verify --gate security --output /tmp/nerve-security.json
PYTHONPATH=src python3 scripts/memory_operations.py verify --gate api --output /tmp/nerve-api.json
PYTHONPATH=src python3 scripts/memory_operations.py faults --output /tmp/nerve-faults.json
PYTHONPATH=src python3 scripts/memory_operations.py readiness --evidence /tmp/nerve-cpu.json /tmp/nerve-security.json /tmp/nerve-api.json /tmp/nerve-faults.json
```

Run after source changes stop. Loopback HTTP tests may require an approved unsandboxed run. Readiness passes the **CPU research gate only** when all four gate manifests pass, are complete, match the current revision and source fingerprint, and are no more than 24 hours old. Missing, duplicate, failed, stale, future-dated or changed-source evidence cannot produce readiness. Return code 0 means CPU research evidence is ready; 2 means not ready. GPU restoration, licensing, shadow/canary deployment and clinical governance remain separate unmet gates. The previous static readiness command is not evidence of passing these gates.

Manifests are trusted local operator evidence, not signed attestations. A malicious host can fabricate files or alter the verifier; source custody and review remain necessary. Atomic writes use a same-directory temporary file, fsync and replacement, mode 0600. This provides local write integrity and does not claim encryption, durable backup or tamper-resistant audit retention.

## Fault and lifecycle checks

The executable fault command creates only temporary SQLite stores. It checks gateway reopen with approved data, durable scope quota rejection, failed provider invalidation followed by successful exclusion of revoked evidence, missing database health without silently recreating it, and corrupt-database denial. These are real CPU SQLite operations and an explicitly simulated unavailable KV provider. It is not a GPU restore, encryption-key, disk-full or connector-crash test.

Existing gateway tests additionally cover checksum mismatch, unavailable ranking, capability revocation, wrong context and stale records. Existing lifecycle tests exercise interrupted uncommitted writers and quota recovery. Real encrypted KV restart, full NVMe, key mismatch, eviction and physical erasure require independently supported runtime infrastructure. Never call semantic-ledger restart proof of durable KV restoration.

Scope quotas constrain concurrent processes sharing the gateway-owned database; incompatible persisted quota settings fail on reopen. A TLS reverse proxy must enforce upload/read deadlines, header/body bounds, connection limits and sanitised access logging. The WSGI server remains synthetic-only, and concurrent worker capacity is necessary to avoid one stalled upload occupying the only worker. Do not expose the research process directly on the Internet.

## Metrics and alerts

The gateway already owns counters; `observability.prometheus_metrics` exports only its exact typed nonnegative counters as label-free Prometheus text. No second counter store is created. Obtain counters through the authorised scoped gateway/service, then use:

```sh
PYTHONPATH=src python3 scripts/memory_operations.py metrics --counters /tmp/authorised-counters.json
```

Unknown fields, booleans, negative or unbounded values are rejected. Exported text contains no plaintext tenant, patient, source, query, credential or scope labels. Aggregation and access control belong to the trusted host. Counters reset with the current gateway process; do not interpret them as durable audit history.

`deploy/memory-alerts.yml` is an undeployed Prometheus rule reference for invalidation and retrieval failures. No dashboard or alert receiver is provisioned. Investigate rising failures; preserve authorised approved-text fallback. Failed purge remains unconfirmed until independently verified and must never be described as erasure.

The lifecycle integration can call `build_audit_event(event,status)` for allowlisted metadata with a random UUID4 trace identifier and timestamp. Export contains no scope, payload, record ID or credential. The coordinator's durable policy store owns persistence and authorisation; the helper itself does not persist, encrypt or authenticate events. Host-created UUID correlation is not caller identity. Source/scope deletion audit and backup erasure remain different properties.

Rollback: stop the optional synthetic memory host and omit its configuration. Preserve the existing NERVE safety gates. Reverting a backup can resurrect source rows or authorisations; reconcile current durable revocations and externally governed retention before reuse. No automatic production rollback, model deployment or clinical promotion occurs.
