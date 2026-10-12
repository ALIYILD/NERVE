# Watchtower / Guardian operations and recovery

## Local verification

Use a separate Python 3.12 environment with `safety/requirements.txt`. This package
has no NERVE runtime import and does not run on NERVE's task path.

```sh
PYTHONPATH=safety python -m unittest discover -s tests/watchtower -v
PYTHONPATH=safety python -m nerve_guardian demo --report /tmp/guardian-demo.json
PYTHONPATH=src:safety python scripts/verify_watchtower.py
```

The demo creates and removes its own sleeping child process, uses generated
synthetic owner principals, and sends notifications to in-memory fixtures. It
never selects an existing process, calls a real provider, installs a service or
activates the live controller. `SHUTDOWN_CONFIRMED` always concerns the explicitly
reported managed coverage, not all NERVE-related execution everywhere.

Two independent process entrypoints are available:

```sh
PYTHONPATH=safety python -m nerve_guardian watchtower --config /reviewed/watchtower.json --once
PYTHONPATH=safety python -m nerve_guardian service --config /reviewed/guardian.json --once
```

Omit `--once` for bounded polling daemons. Examples under `deploy/watchtower`
are inert and observe-only. Missing systemd, file pins, monitoring signals,
notification channels or source coverage produce UNKNOWN. They do not pause
NERVE's learning or claim a safe system. No service installation was performed.

## Independent deployment prerequisites

Install the immutable `safety` tree and its environment under an independently
administered `/opt/nerve-safety`, outside agent-readable credentials and writable
code. Provision separate Watchtower read-only source access, Guardian enforcement
identity, private state/anchor directories and an independent owner IdP. A second
checkout under the same developer account does not establish this separation.
Guardian must not share NERVE's deployment keys, containers, writable mounts,
MFA identities, secrets or self-update mechanisms.

The Watchtower user gets only reviewed read-only SQLite access and its own bounded
telemetry output directory. Guardian reads that untrusted report and measures
supervisor/cgroup and protected-file evidence independently. Configure each source
in both the collector and Guardian's tenant `telemetry_sources` allowlist. Never
copy full database contents, prompts, raw reasoning, credentials or clinical text
into telemetry. Aggregate counters prove observations of those tables only.

Populate a reviewed workload/dependency inventory. Clinical/shared units are
rejected. The pilot systemd template is the only checked-in deployment target;
launchd, CI, containers, remote workers, provider tokens and network egress remain
uncovered by this adapter. Do not arm until the actual topology, external IAM/
network containment, service ownership and clinical safe-degradation boundaries
are independently verified. See [coverage inventory](COVERAGE.json).

The controller persists a latch and unit start-block markers, records enforcement
intents/results, masks units persistently, stops them and checks both supervisor
state and descendant cgroup population. Deploy the matching start-block drop-in
and independently verify its path. A failed mask or unknown cgroup cannot be
reported as confirmed containment. Some locally installed unit layouts cannot be
masked without deployment changes; such failures remain PARTIAL_CONTAINMENT.
Live invocation additionally requires a root-controlled state hierarchy, `armed`
configuration and the explicit `--allow-live-enforcement` flag. This flag was not
used. It is an infrastructure administrator operation, never an agent tool.

Run the independent external check from a separately managed monitoring account
and scheduler, with no dependence on NERVE or Watchtower's self-report alone:

```sh
PYTHONPATH=safety python -m nerve_guardian.health --unit nerve-guardian.service --health-file /var/lib/nerve-guardian/state/guardian-health.json
```

It independently checks the supervisor and report freshness. Remote execution,
network partition detection and its escalation route require actual provisioning;
no external monitoring account or scheduler was installed.

## Owner portal and alert provisioning

Add `identity` to Guardian's private config with exact `issuer`, `audience`,
`public_key_files` mapping pinned `kid` to public-key file, optional `mfa_acr`
allowlist, and `owners` mapping human subject IDs to tenant IDs. Expose the
loopback portal only behind independently administered TLS and restricted owner
access. The UI accepts a bearer token issued by that IdP; no browser token storage,
proxy identity headers or Telegram replies are accepted. Token acquisition/refresh
and the human MFA ceremony are external prerequisites, not implemented by a demo.

Provision `notifications.telegram` with endpoint `https://api.telegram.org`,
`secret_path` to a Guardian-only 0600 secret-manager mount and authorised `recipient`
chat ID. Provision `notifications.email` with an approved HTTPS transactional
endpoint, `secret_path`, `recipient` address and `sender`. The adapter uses a
Resend-compatible request/receipt contract. Never paste keys into this repository.
Set `dashboard_url` to the independently secured portal. Test credentials and
owner destinations were not supplied, so actual provider delivery is unverified.

Alerts are nonblocking, independently retried per channel and durably deduplicated.
Provider acceptance is not proof of owner receipt. Exhausted retries, dead workers
or queue/storage loss report UNKNOWN; an external route must escalate a total
notification outage. Pending notification intents persist with the incident and
are re-enqueued after process restart. A crash after provider acceptance may
produce a duplicate message. Authentication failures produce bounded categorical
restart-denial alerts without recording submitted tokens or payloads.

## Incident and controlled recovery

1. Examine incident observations, pinned hashes, actions and coverage. If shutdown
   is partial, use the independently administered infrastructure console to handle
   uncovered paths. Never treat a successful stop request as verified shutdown.
2. Keep the incident stopped while investigating. The owner can invalidate pending
   approvals through **Keep stopped**. Preserve the state database, external anchor,
   controller latch, enforcement journal and outbox; export the authenticated audit.
3. Remediate the cause through a reviewed deployment. Request recovery using a new
   independent MFA authentication, incident ID and a bounded remediation reference.
4. Supply another fresh owner authentication for approval. Request and approval
   identifiers are one-use; authentication must be within 300 seconds. The service
   rechecks tenant ownership, audit integrity, complete fresh independent signals,
   deployed/protected artifacts, permissions and verified stopped state.
5. Any mandatory check failure denies restart. The bundled probe intentionally
   reports incomplete cross-source coverage, and execution-permission/deployment
   provenance attestations are not provisioned. **Production restart remains
   denied until those real independent checks are integrated.** Do not edit a
   fixture or delete an UNKNOWN signal to manufacture approval.
6. A failed/partial restart is contained again. Successful controlled startup is
   verified and the service samples at most one second apart for 15 minutes before
   returning to its configured interval. Alerts and audit records remain intact.

Audit-anchor mismatch, missing state or corruption requires independent forensic
review. Never recreate an empty database, delete a latch, unmask a service, or
trust an old backup as permission to restart. Preserve the damaged artifacts and
restore only a reviewed matching database/anchor pair with the controller still
latched. Reconcile its incident ID and enforcement journal before recovery. A
crash between audit commit and anchor replacement deliberately fails closed.
A simultaneous independently verified critical finding uses a separate emergency
receipt and containment path while primary audit storage is unavailable.

## Retention and limitations

In-memory telemetry has explicit capacity/age bounds (default 32 observations and
300 seconds); queue loss is visible. The current telemetry report replaces the
previous report. Incident/audit/enforcement/outbox history is retained for owner
review and never automatically pruned during an incident. Production requires
reviewed off-host immutable archival, retention/deletion schedules and endurance
validation. Full-chain audit verification grows with history; long-duration
production throughput has not been established. No claim of tamper resistance
against the safety administrator/root is made.

Protocol references: [systemd's official systemctl source documentation](https://github.com/systemd/systemd/blob/main/man/systemctl.xml),
[OpenID Connect Core](https://www.openid.net/specs/openid-connect-core-1_0.html),
[Telegram Bot API](https://core.telegram.org/bots/api), and
[transactional email request/receipt contract](https://resend.com/docs/api-reference/emails/send-email).
