# Live deployment status

Status: **passive local observation running; full Guardian protection NOT READY**.

The actual NERVE learning workload is a macOS user launchd job,
`com.aliyildirim.nerve.learning`, running `scripts/agentos_bridge.py cycle`
from the existing `nerve-review` checkout every 900 seconds. Its last recorded
exit status was zero. Its plist, schedule and source were not changed.

A separate login service, `com.aliyildirim.nerve.watchtower`, now runs a copied
release `65151a7` under the existing Python 3.10 interpreter. Files are under
`~/.local/share/nerve-watchtower`; configuration and directories are private to
the current user. It restarts after failure and starts on login. This is **not**
an independently administered Guardian account or a boot-time system daemon.
The agent account can modify these files, so evidence is application-untrusted.

The collector reads `~/.agentic-os/nerve/learning.sqlite3` using read-only SQLite,
a 100 ms query budget and a 15-second poll interval plus bounded collection wait.
It exports only counts from `trusted_memory_v18` filtered by `tenant_id` and
`memory_utility` filtered by `tenant`, for `agentos-local`. These are row totals,
not proof of learning activity, correctness or completeness. Both observed counts
were zero during the smoke test; this does not establish inactivity or safety.
Other tables lacking tenant scope are excluded. No raw memory, prompts, patient
records, credentials or provider calls are collected.

Verification: Python 3.10 telemetry suite 12 passed; full safety suite 80 passed;
launchd reported a live collector PID; report timestamps advanced; no queue drops;
empty stderr; installed release hashes matched; source database and sidecars were
unchanged across the one-shot live collection. See
[evidence](evidence/live-passive-observer.json). That file is point-in-time evidence,
not a current health guarantee. Current report:
`~/.local/share/nerve-watchtower/state/telemetry.json`.

## Operations

```sh
launchctl list com.aliyildirim.nerve.watchtower
cat ~/.local/share/nerve-watchtower/state/telemetry.json
```

To stop only this passive monitor, use `launchctl bootout` against the exact
installed Watchtower plist in `~/Library/LaunchAgents/`. The distinct
`com.aliyildirim.nerve.learning` service must remain untouched. No NERVE restart
or shutdown test was performed.

## Required before automatic protection

- Choose the actual independent administration boundary: migrate managed workloads
  to the supported Linux/systemd controller, or implement and independently verify
  a macOS/root launchd controller. Existing Linux enforcement cannot control this job.
- Provision safety-owned immutable code, private credentials and audit storage
  unavailable to the agent identity; a same-user checkout is insufficient.
- Configure independent owner MFA/TLS, exact subject and tenant bindings, and
  verified restart preconditions. Current unprovisioned checks deliberately deny recovery.
- Provision dedicated Telegram/email provider credentials and destinations, verify
  test delivery, and independently monitor delivery and Guardian health.
- Inventory unmanaged workers, deployment paths, network/IAM authority and clinical
  dependencies. Current coverage is explicitly incomplete.

The owner selected this Mac. Independent account, MFA and secret-location details remain pending. Do not
paste secret values into chat. No automatic containment, independent Guardian,
owner recovery portal or live alerts have been enabled by this deployment.

## Full-readiness audit

All PR checks passed for 103f05a. The passive report remained fresh with no drops.
This host has neither /usr/bin/systemctl nor an independent /opt/nerve-safety
installation or /etc/nerve-guardian/config.json. Both existing workloads run
under the developer account. A user-domain launchd disable/bootout operation
cannot prevent that same identity from manually starting Python or creating
another job. It is not an adequate emergency boundary.

The preservation-oriented next step is a dedicated restricted NERVE service
account with reviewed HOME/Hermes and data access, root-owned runtime and job
definitions, and an independently administered Guardian. A macOS-specific
controller must verify the dedicated identity's descendants, persistent restart
blocking and controlled human recovery. Compatibility and containment tests must
pass in isolated infrastructure before moving the existing learning schedule.
This adapter and identity migration are not implemented by a launchctl wrapper.

Live startup now rejects unsupported operating systems/missing systemctl before
state creation, even when invoked as root. It also rejects missing owner MFA
configuration, missing email/Telegram channels or tenants without recovery owners.
These are necessary prerequisites, not proof of external authority or successful
provider delivery. The current safety suite passes 82 tests.

## Same-Mac setup selected

The destination is fixed to this Mac. See [local setup](MACOS_SETUP.md) and the [read-only preflight result](evidence/macos-preflight.json). The CLI reports NOT_READY with exit code 2 and does not mutate services or read credentials. The existing learning job and live passive collector remain unchanged.
