# Independent infrastructure enforcement

Implemented as a separately deployed Python package under `safety/`, with no
imports from NERVE. The systemd adapter is disabled by default. Nothing in this
change installs a service, touches a production process or grants credentials.

## Discovered host and boundaries

`deploy/nerve-repository-pilot.service` runs as `nerve`, restarts on failure and
uses a private persistent store. `docs/host-operations-v27.md` requires root-owned
application code and independently provisioned identity/TLS; it explicitly does
not provision a downstream clinical integration or external model traffic.
The repository documents Hermes adapters and development commands, but a single
systemd pilot service cannot establish their actual deployment coverage. Shared
hosts, databases and clinical dependencies must not be inferred from filenames.

## Concrete controller contract

`SystemdController(inventory, state_dir, enabled=False, runner=None)` accepts an
administrator-reviewed mapping from tenant to `ManagedUnit` objects. Literal
`.service` names only; no glob, shell, arbitrary arguments or paths. Duplicate
cross-tenant assignments, clinical/shared units and observer units are rejected.
The inventory is configuration, not proof that a unit is dedicated: deployment
review must establish that fact and protect all configuration/code ancestors.

`contain(tenant, incident_id)` fsyncs persistent block markers and a scoped
incident latch before issuing bounded fixed-argv `systemctl mask` and `stop`.
`verify(tenant)` independently reads system manager properties and, when present,
cgroup-v2 `cgroup.events` including descendant population. Success requires every
listed unit inactive/failed, MainPID zero, empty cgroup and persistent masked
state. Missing/malformed/unreadable signals fail verification. An inactive unit
with no control group is verified from the manager's zero PID and inactive state.
The return object has `actions`, `verified`, `coverage`, and explicit `gaps`.

`restart(tenant, incident_id)` is an internal privileged operation, **not an
authentication mechanism**. Only the separately authenticated owner incident
service may call it after MFA/fresh authentication, single-use authorisation and
preflight checks. An incident string is not a bearer credential. Restart unmasks
only scoped units, removes their persistent block markers, starts in inventory
order and verifies active state. A failed operation recontains the tenant. The
owner's audit service must capture every returned action and reconcile interrupted
calls. Controller calls are serialised with an OS file lock; monitoring should
sample outside restart transactions to avoid interpreting authorised transitions
as restart attacks. Process activity is not application readiness.

## Deployment prerequisites — not performed

1. Deploy a reviewed, immutable safety artifact under a separate administration
   identity. Agents must have no root, sudo/systemctl/polkit management authority,
   ability to alter the inventory, systemd units, safety code or ancestor paths,
   or access to owner/private notification credentials. Root compromise is outside
   the protection this controller can provide.
2. Create root-owned mode-0700 state and blocks directories on durable local
   storage. No network/shared database is assumed. Inventory and code hashes are
   pinned outside the agent checkout; no safety service imports mutable NERVE code.
3. Review dependencies and exclude any clinical/shared units. Install managed
   service definitions in the distribution's vendor unit directory and confirm
   persistent masking works. `systemctl mask` can fail for unit files already
   occupying `/etc/systemd/system`; this adapter never force-overwrites them.
4. Install the reviewed per-service condition drop-in from
   `deploy/watchtower/nerve-repository-pilot.guardian.conf.example`. It prevents
   start when the durable block marker exists, including reboot and controller
   crashes after marker creation. Masking independently prevents activation after
   successful containment. Test the effective `KillMode=control-group` and ensure
   the workload cannot escape its cgroup. Conditions do not stop already running
   processes; mask/stop and independent verification are still necessary.
5. Deploy the authenticated control service and read-only sensor separately.
   `nerve-guardian.service.example` is deliberately non-runnable (`/usr/bin/false`)
   and has no install target: it is a hardening starting point, not a claimed
   working daemon. Wire a reviewed fixed entrypoint and independent external
   heartbeat before enabling. Never expose a raw systemd-control endpoint.
6. Before live enablement, test disposable systemd units on the target Linux host,
   including reboot, signal-resistant descendants, concurrent incidents, mask
   failure, restart failure and privileged boundary attacks. No live validation
   has occurred in this macOS development environment.

Authoritative systemd semantics: [systemctl upstream documentation](https://github.com/systemd/systemd/blob/main/man/systemctl.xml).

## Read-only Guardian evidence

`InfrastructureProbe.sample(tenant)` reports independent source, kind, timestamp,
status and metadata-only evidence. It measures systemd state, compares configured
protected-file SHA-256 hashes and measures observer heartbeat file freshness.
A measured mismatch with an administrator-pinned hash produces
`protected_file_changed`; observed execution or loss of masking while latched
produces `unauthorized_restart`. The parent deterministic policy must bind those
signals to reviewed critical invariants before containment.

Absent/stale/future heartbeat, unavailable files and unobservable process state
are UNKNOWN. A fresh heartbeat does **not** prove ingestion completeness; missing
cross-source counts and unmanaged-process discovery are always reported UNKNOWN.
Heartbeat contents and agent risk claims are not trusted. Agent-readable output
contains no file contents. Heartbeat writers must not have access to safety policy
or enforcement authority. Independent filesystem timestamps alone cannot detect
an attacker who controls that heartbeat writer and keeps it fresh.

## Verified coverage and remaining gaps

| Capability | Implementation / evidence |
| --- | --- |
| Scoped service stop, persistent mask, restart | Real systemd adapter; injected command tests only |
| Durable blocked start after reboot | Persistent marker + reviewed systemd condition template; target-host test pending |
| Process stop/recreation refusal | Real disposable Python child under isolated test supervisor |
| cgroup descendant verification | Injected cgroup-v2 files; target-host test pending |
| Root/admin versus agent isolation | Required deployment boundary; not provisioned or verified locally |
| Container/cluster stop, cloud IAM revoke, network deny | Not implemented or covered |
| Deployment controller and external tools | Not controlled; live deployment remains blocked pending inventory |
| Cross-host replicas and unmonitored processes | Unknown; no universal shutdown claim |
| Clinical dependency safety | Explicit exclusion; actual deployment dependency inventory still required |

Twelve automated tests passed with
`PYTHONPATH=safety python3 -m unittest discover -s tests/watchtower -p test_infrastructure.py -v`.
They cover real disposable process termination, persistent test-supervisor mask
and controller reconstruction, wrong incident rejection, disabled controller,
invalid/shared/clinical/cross-scope inventory, mask failure, timeout UNKNOWN,
populated descendant cgroup rejection, failed restart recontainment, modified or
missing protected files, stale heartbeat and observed unauthorised restart.
No production shutdown, real systemd enforcement, IAM revocation, email or
Telegram delivery was performed by these tests.


Additional review hardened controller versus parent lock separation, rejected
unprotected root ancestors for live controller state, validated bounded latch
records with no symlink reads, and made protected-file reads bounded regular-file
reads without following symlinks. Tests additionally exercise missing systemd
units, missing/escaping cgroups, restart timeouts and conflicting incident latches.
Protected per-tenant `.actions.jsonl` records fsynced action intents before each
systemd change and outcomes afterwards. An interrupted intent is deliberately
ambiguous and must be reconciled through `verify`; it is not a successful action.
This recovery journal supplements the parent incident audit and requires a
reviewed retention/export policy; it is not tamper-proof against administrators.
