NERVE currently has several independent execution paths and application-owned safety flags, but no independently administered emergency control plane. This adds a separate `safety/nerve_guardian` package for passive metadata collection, independent infrastructure checks, scoped containment, durable incident evidence and human-controlled recovery. Existing NERVE runtime, learning and adaptation code is unchanged from the discovered local baseline.

The implementation includes separate Watchtower/Guardian entrypoints, an external Guardian health checker, a systemd allowlist controller with persistent masks/latches and cgroup verification, a signed-MFA owner portal with 15 evidence/UNKNOWN panels, and parallel Telegram/email adapters with durable deduplication and bounded retries. Application anomalies and LLM scores cannot authorize containment. Incomplete recovery checks deny restart.

Validation:
- 1,124 existing NERVE tests passed before and after implementation.
- 70 safety tests passed, including 13 independent adversarial tests and a signed-MFA HTTP recovery/replay test.
- A real disposable TERM-ignoring child was stopped, prevented from recreating, and restarted through the controlled fixture flow.
- 12,000 actual AST inventories remained correct during the bounded local passive-collection comparison; median change was approximately +2.7%. This is not a production performance guarantee.

This remains a draft. Live enforcement is disabled and no production settings, services, messages, merge or deployment were changed. Live systemd/reboot/escape validation, independent administration, IAM/network/deployment enforcement, real IdP/MFA, Telegram/email test credentials, external escalation, clinical dependency review and production retention/endurance remain acceptance gates. Example configuration deliberately cannot authorize production restart while mandatory signals are missing. Fixture notification acceptance is not real provider delivery.

See `docs/watchtower/ACCEPTANCE.md`, `INDEPENDENT_REVIEW.md`, `COVERAGE.json` and `RUNBOOK.md` for exact evidence, known gaps and recovery instructions.

Branch context: development started from locally present commit `23d7900` (existing CCE readiness wiring), one inherited commit beyond the remote integration branch at discovery. That pre-existing commit is preserved, not authored as Watchtower work. This PR targets the prior NERVE integration branch to keep it separate from production/main.

Notification lifecycle follow-ups enforce bounded shutdown and exclusive outbox ownership, with tests for stalled providers, process-exit recovery, path aliases and partial worker startup failure.
