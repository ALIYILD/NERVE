# Same-Mac Guardian setup

The owner selected the existing Mac. Do not move NERVE to Linux or another host.
The installed passive Watchtower stays active while implementation and
provisioning proceed. The existing learning schedule stays unchanged until its
replacement passes compatibility and containment tests.

## Local readiness check

```sh
PYTHONPATH=safety python -m nerve_guardian macos-preflight
```

This command reads bounded local metadata and reports prerequisites. It does not
create users, install jobs, stop processes, send alerts or read secret values.
Exit code 2 means not ready. An optional `--report` writes the report to the
requested location. File existence and ownership checks are evidence of those
facts only; they cannot establish administrator independence or usable recovery.

## Required account boundary

| Role | Access | Current status |
|---|---|---|
| Owner | Separate administrator access and fresh MFA for recovery | Not provisioned/verified |
| NERVE worker | Dedicated non-admin service account; no interactive login, sudo or Guardian credentials | Current workload uses the owner's developer account |
| Passive Watchtower | Read-only approved source metadata; own report directory | Running under developer account; evidence remains untrusted |
| Guardian | Protected installation/configuration and control of the dedicated worker identity | Not installed |

The proposed protected installation is `/Library/Application Support/NERVE-Guardian`.
Guardian's eventual root-owned LaunchDaemon belongs in `/Library/LaunchDaemons`.
These paths are a provisioning plan, not evidence that those resources exist.
Do not grant NERVE the owner's password, sudo authorization, MFA session or alert
provider keys. Safety code must be outside NERVE's writable learning workspace.

## Implementation and cutover sequence

1. Establish the independent owner/admin and restricted NERVE service identity.
2. Map the current worker's HOME, Hermes, data and credential dependencies. Grant
   only required access; do not copy the owner's full home or keychain.
3. Implement the macOS controller against that boundary. A wrapper around
   `launchctl disable` or `bootout` for the current user job is insufficient:
   the same user could create another job or run Python manually.
4. Verify durable containment, dedicated-user descendant termination, blocked
   alternate scheduling, recovery replay rejection and reboot behavior in an
   isolated test workload. Never use the existing learning job as a kill test.
5. Provision owner MFA and dedicated Telegram/email credentials. Verify real
   test delivery and recovery with independently held credentials.
6. Validate existing learning behavior under the restricted identity before an
   explicit schedule cutover. Keep a reviewed rollback path.
7. Activate automatic containment only after all mandatory checks pass.

The macOS enforcement adapter and this cutover remain incomplete. Passing the
existing unit tests or starting a root process does not make them complete.

## Information still needed from the owner

- Existing independent administrator account, or confirmation it is not provisioned.
- Existing MFA identity provider, or confirmation it is not provisioned.
- Telegram owner chat ID and dedicated token's secure file location.
- Email recipient, provider, verified sender and credential file location.

Provide locations and identifiers only, not passwords or token values in chat.
Selecting this Mac resolves the deployment destination; it does not supply these
credentials or establish the required identity separation.
