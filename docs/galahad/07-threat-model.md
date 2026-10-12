# Synthetic memory threat model

Trust boundaries: operator-pinned OIDC keys and offline subject grants → WSGI service → host-issued memory capability → authoritative v1.8 ledger → optional KV provider. Agents and request JSON cannot issue capabilities or approve records. This is local research software; no deployed identity provider or clinical accreditation is claimed.

| Threat | Implemented control / evidence | Remaining boundary |
|---|---|---|
| Forged identity / tenant escalation | Existing RS256 `PinnedOIDCVerifier`; signed role AND host grant; tenant/agent cannot be supplied in request | Operator must provision/rotate keys and grants; no online token revocation |
| Cross-patient / clinic / session context | Exact offline MemoryScope; canonical SHA256 context includes application, user, clinic, patient, session; request patient/clinic must match grant | Operators must bind grants correctly; no real patient registry integration |
| Revoked/expired/poisoned evidence | v1.8 approval, revocation, expiry and final authoritative recheck; feedback always pending | Reviewer must assess source correctness and malicious instructions |
| Agent privilege escalation | No public approve, capability-issue, raw KV, or candidate-promotion operation | Trusted same-process Python code is privileged |
| Wrong-model KV / cross-tenant reuse | Restore admission closed pending verified runtime; identity compatibility is fail-closed | Real Galahad key enforcement and multi-tenant connector isolation blocked |
| Stale source / failed invalidation | Scoped revoke/delete; provider invalidation status returned | Physical KV erase, snapshots, replicas and backups unverified |
| Raw payload in telemetry | Gateway metrics expose counts only; generic errors; no request-body logging | Reverse proxy and infrastructure logs must be reviewed separately |
| Cache growth / request floods | 12 KB request limit, 64 principals, per-principal request rate, bounded retrieval | Persistent DB quota, distributed rate limiting and slow-client protection require infrastructure |
| Disk theft / encryption key mismatch | No clinical data permitted; KV provider disabled | SQLite plaintext; no KMS, encrypted durable store, backup restore or erasure proof |
| Prompt injection persistence | Pending proposal, offline approval, evidence JSON boundary, no executable agent output | Delimiting is not a complete prompt-injection defence; no clinical inference endpoint |
| Service outage / connector failure | Sanitised failure, approved text fallback; security errors never become unscoped fallback | Hardware faults, failover and deployment TLS not verified |
| Credentials exfiltrated by client redirect | Reference client disables redirects; HTTPS unless explicit loopback HTTP | Operators obtain bearer credentials outside this project |

Tests use freshly generated RSA keys and synthetic text. `test_memory_service.py` covers signature/issuer/audience/expiry failures, scope overrides, unauthenticated body handling, role intersection, grant revocation, body/rate limits, pending feedback, administrative context isolation and provenance. Gateway/provider suites cover their separate boundaries. No finite test suite proves absence of all leakage.

Production gates remain blocked: transport TLS validation, approved encryption/key management, security monitoring, durable user consent and identity lifecycle, storage quotas, independent penetration testing, software supply-chain review, backup/deletion evidence and clinical governance. No mandatory security decision is delegated to JEV or an agent.
