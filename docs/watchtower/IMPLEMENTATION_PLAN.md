# Implementation and acceptance plan

1. Discover runtime/deployment/clinical boundaries and baseline tests.
2. Implement standalone bounded read-only collector and anomaly baseline.
3. Implement separately sourced Guardian probes and allowlisted external controller.
4. Implement durable incident, audit, containment verification and replay-safe restart state machine.
5. Implement independent MFA portal, operational dashboard and parallel notification outbox.
6. Integrate disabled-by-default service/config templates and safe synthetic demonstration.
7. Run independent adversarial review, regression tests and measured local performance/latencies.
8. Publish evidence, explicit uncovered infrastructure and recovery runbook; prepare review PR without merge/deployment.

Specialist ownership uses isolated worktrees: discovery/telemetry/behavior, infrastructure/Guardian probes, IAM/notifications/dashboard, and root incident integration. Discovery auditor subsequently reviews shutdown/restart independently. No implementation agent receives production credentials.

Acceptance distinguishes implemented code, local fixture verification, real subprocess enforcement, Linux systemd verification, real MFA issuer, live Telegram/email delivery, deployment administration separation and production approval. Missing credentials/infrastructure block only dependent checks; no simulated result counts as live evidence.
