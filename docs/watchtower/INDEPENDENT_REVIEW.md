# Independent implementation review

Review scope: the separately deployed `safety/nerve_guardian` package, repository integration boundaries, local audit/incident state, systemd controller/probe adapters, owner authentication and notification/admin interfaces. Review was performed by a separate specialist from the primary incident/controller implementation authors. This is engineering review, not independent organizational certification or production authorization.

## Review method

Read-only source review examined `core.py`, `store.py`, `infrastructure.py`, `probes.py`, `auth.py`, `notifications.py`, `web.py`, `__main__.py` and `demo.py`. The specialist contributed adversarial tests in an isolated worktree; the primary implementer owns implementation fixes. Tests exercise actual temporary SQLite files and protected-anchor mismatch, while supervisor/probe objects are injected test doubles. The disposable-child demonstration is distinct from Linux systemd enforcement, a live IdP, provider delivery or OS privilege separation.

## Findings and remediation evidence

The initial 11 adversarial tests identified three failures: critical observations displayed NORMAL in observe-only mode, WARNING observations displayed NORMAL, and visibility alarms overwrote another tenant's alarm. Implementation now aggregates observed risk independently of enforcement state and includes tenant identity in notification keys.

Source review additionally identified missing mandatory restart signal coverage, loss of alerting when the primary audit store fails, missing dashboard links and notification-health visibility. The implementation now requires fresh protected-file, observer-heartbeat, workload, execution-permission and deployment-provenance signals before and after restart; independent audit-failure alarms use the notification channel directly, and verified critical evidence may invoke an externally recorded emergency containment path. Missing proof still denies restart.

The final pass added two regressions: switching a persisted observe-only critical incident into armed mode must actually contain it; malicious counter names in an application-owned report must not pass through to the dashboard. It also detected an exception-classification regression: catching OSError around state callbacks incorrectly converted PermissionError into audit corruption. All three final-pass findings were remediated and the independent tests rerun successfully.

## Claims supported by the adversarial tests

- Untrusted or stale critical claims cannot trigger containment.
- Cross-tenant, missing-MFA and reused-authentication restart requests are denied.
- Partial containment and UNKNOWN recovery evidence cannot authorize restart.
- Altered state and mismatched external audit anchors fail closed, including reopening after a simulated database-commit/anchor-update crash window.
- Observe-only risk remains accurately represented; persistent critical incidents can enter containment after explicit independent activation.
- Tenant-specific visibility alerts remain distinct; raw report counter names cannot leak through the metadata adapter.

## Remaining production gates

No production unit was stopped or restarted. The systemd adapter's injected-runner tests do not establish live cgroup, mask, reboot, alternative-launcher or deployment-controller enforcement. Existing application-level adaptation kill switches remain separate from external controls.

No actual owner identity provider, MFA session, trusted ingress, secret-manager integration, Telegram delivery or email delivery was provisioned in this work. Signed-token and provider fixtures establish software contracts only. Python `Principal` objects are trusted in-process adapter outputs; OS and network isolation must prevent NERVE agents from invoking internal service APIs or accessing safety code, keys and state.

The production infrastructure probe explicitly reports incomplete coverage and lacks live execution-permission/deployment-provenance assurance. Accordingly live recovery stays denied; it must not be enabled by removing mandatory checks. Infrastructure accounts, remote workers, CI research scheduling, external tools/network/IAM and clinical/shared dependencies remain outside verified shutdown coverage.

Audit protection depends on a separately protected anchor and independently administered storage. Hash chains do not resist an attacker who controls both the database and its anchor. The commit/anchor crash window intentionally requires operator recovery; no automatic repair from untrusted state is authorized. Long-lived audit/outbox retention, full-chain verification cost and operational restore procedures need staging endurance evidence.

The controller must run outside NERVE's writable/delegated boundary. Root-level source/configuration compromise is not addressed by library label checks. External monitoring must watch Guardian itself and notification delivery failures from another administrative boundary.

## Verification

Final independent adversarial run: **13 tests passed** against the integrated main worktree after remediation (Python 3.10, 0.243 seconds):

```sh
PYTHONPATH=/Users/aliyildirim/NERVE-watchtower/safety python3 -m unittest discover -s tests/watchtower -p test_independent_review.py -v
```

The initial telemetry specialist suite separately passed 10 tests for actual read-only SQLite collection, tenant joins, poisoned views, missing sources, bounded queue behavior and advisory analysis. Repository-wide regression and combined safety-suite totals belong to the primary implementation report.

No unresolved failing assertion remains in this specialist test set. This is approval of the reviewed local software evidence for a reviewable feature branch, not production acceptance or complete safety coverage.
