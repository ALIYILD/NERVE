# Hosted-pilot operations v2.7

This bundle adds scoped readiness, startup validation, supervised-service settings
and non-overwriting backup/restore. It does not provision an identity provider,
TLS endpoint, VM, Clinical OS connection or model provider. No system service is
installed or started by the repository change.

## Readiness and startup checks

`GET /v1/readiness` uses the same signed JWT and configured `auditor` grant as
`/v1/evidence`. It checks SQLite integrity and the requesting scope's current
release/binding. It never runs a task, claims a sample, learns, promotes or unlocks
an interrupted attempt. No unauthenticated health URL is added.

| Response | Meaning |
|---|---|
| 200, `ready: true`, `degraded: false` | The configured scope can serve its approved route |
| 200, `ready: true`, `degraded: true` | A pending trial/monitor attempt requires review; requests still receive the prior route |
| 503, `ready: false` | Database or deployment checks failed; details remain private |
| 401 / 403 | Authentication or auditor authorisation failed |

The readiness response is a point-in-time read, not a guarantee that the next
request succeeds or a check of disk capacity, TLS, IdP reachability, external
models or clinical validity. `quick_check` scans the database; keep polling
frequency modest. A tenant's unrelated deployment problem does not expose its
state to another tenant, although database integrity is shared.

Run an offline startup check with the real public identity configuration and an
existing database:

```bash
PYTHONPATH=src python scripts/serve_repository_host_v25.py \
  --config /etc/nerve/identity.json --database /var/lib/nerve/pilot.db --check
```

This constructs the host and validates all configured scopes without opening a
listening socket. It may initialise missing schema tables using the normal host
constructor; it does not bootstrap missing scopes, execute tasks or change
releases. Missing database files are rejected before opening SQLite. Startup
errors omit config contents and stack traces. A pending monitor is degraded but
can start safely on the baseline; a mismatched deployment refuses startup.

## Supervised Linux pilot

Use a reviewed checkout at `/opt/nerve`, a Python 3.12 virtual environment at
`/opt/nerve/.venv`, and install `deploy/requirements-pilot.txt`. Resolve and retain
the dependency versions used by your deployment; the file is a compatible range,
not a reproducible lockfile. Provision a dedicated `nerve` service user/group.
Keep application files root-owned and non-writable by that user.

Provision `/etc/nerve/identity.json` using the v2.5 schema, your actual pinned
public JWKS, issuer, audience and subject grants. Keep it readable by `nerve`
and writable only by administrators. Do not store private IdP signing keys here.
Create `/var/lib/nerve` owned by `nerve`, mode 0700, before first initialisation.

Initialise missing scopes explicitly by running the normal server once as
`nerve` with `--bootstrap`, then stop it with Ctrl-C. Alternatively use the
trusted `build_host(config, database, bootstrap=True)` API in an offline
provisioning script. The service template deliberately never bootstraps on restart.
Run `--check` as `nerve` before enabling the service.

Review and install `deploy/nerve-repository-pilot.service` in your systemd unit
directory. Its fixed paths must match your installation. Then run your normal
`systemctl daemon-reload` and `systemctl enable --now nerve-repository-pilot`
operations. These commands have not been run on your host by this change.

The template uses a dedicated account, a private persistent state directory,
restrictive file permissions, a read-only system view, process/memory limits,
restart-on-failure and startup validation. It still binds only to loopback port
8765. Configure a TLS reverse proxy with connection/header/body limits; do not
expose the Python reference WSGI listener publicly. No DNS name is assumed.

SIGTERM now requests a graceful stop after the current request/drain operation.
Systemd's 15-second stop budget can terminate hung work, which may leave a pending
attempt. Such attempts remain blocked after restart and require operator review.
This is not per-request process isolation. The service template was checked by
`systemd-analyze verify` using the available local Python executable; installation
and runtime isolation on the target host still require verification.

## Backup and recovery

Use SQLite's online backup API rather than copying only the main file of a
running WAL-mode database. Every destination must be a **new path** in an
existing directory. Files are created with mode 0600 and published atomically
with no overwrite, including when another writer races to create the destination.

```bash
PYTHONPATH=src python scripts/manage_repository_store_v27.py backup \
  --source /var/lib/nerve/pilot.db --destination /secure-backups/nerve-001.db

PYTHONPATH=src python scripts/manage_repository_store_v27.py verify \
  --source /secure-backups/nerve-001.db

# Stop traffic/service before selecting a recovered store.
PYTHONPATH=src python scripts/manage_repository_store_v27.py restore \
  --source /secure-backups/nerve-001.db --destination /var/lib/nerve/recovered-001.db
```

Backup and restore share the same consistent copy/verify operation. Restore does
not replace the live database or edit service configuration. Verify checks SQLite
integrity and required host tables, not whether approvals are still operationally
appropriate. Run host `--check` against the recovered file, compare its generation
and audit history with your latest deployment record, and explicitly select it
in the stopped service's configuration before resuming traffic. Do not run both
old and restored stores as the same live scope.

A snapshot can contain approvals or bindings that were revoked after backup.
Restoring it can resurrect that old state; a backup is not authority to redeploy
it. Review snapshot freshness and reconcile subsequent decisions before service
restart. Keep snapshots in trusted storage with access controls and retention;
0600 permissions are not encryption. Identity configuration, IdP revocation
state and application binaries are outside the database backup.

Interrupted copies before publication are removed. If a failure happens after
publication (for example directory-sync failure), a newly created destination
may remain and should be inspected; pre-existing files are never overwritten.
The backup progress callback bounds copying attempts, but verification and OS
filesystem operations are not a hard overall deadline.

## Verification evidence

Tests cover signed/scoped readiness, startup checks, sanitised errors, consistent
WAL backups, exact evidence recovery, permissions, refusal to overwrite,
corruption/foreign-schema rejection, interruption cleanup and publication races.
A separate drill restores a promoted trial into a new database, retains its
binding and then verifies automatic rollback. It uses the same test-only eligible
candidate fixture as v2.6; it is not performance evidence over the real AST tool.

Systemd reference: https://github.com/systemd/systemd/blob/main/man/systemd.service.xml
