# Cross-domain adaptation — 17 October 2026

The same `GoalOrchestrator` runs learn, propose, evaluate and adapt for
`scientific`, `perfflux-sandbox`, and `clinicalos-sandbox`. The existing
`goal_orchestrator.py` and `adaptation*.py` match 530591c byte for byte; exact hashes
are in `orchestration/w3-source-integrity.json`. No history rewrite or external
repository change was needed. The new SDK uses the goal supervisor and the new
outcome monitor/router; it does not claim to have exercised every existing
`AdaptationCoordinator` backend.

PerfFlux names the two fixture skills direct/cached-batch; Clinical OS names them
title/abstract retrieval. Each domain runs 100 synthetic dev items plus 1,200
recorded synthetic drift items, with explicit always-abstain and seeded-random
controls. Both have detections at 308/608/908 (delay 8), switches 312/512, switch-back
910 and one rollback 452. Verification completes 322/522/920. No model calls or GPU
spend are involved. These are contract demonstrations, not real workload timing,
real retrieval effectiveness or clinician-approved learning.

Bundles and SHA256/source manifests:

- `receipts/loop-demo-perfflux-sandbox-20261017/`
- `receipts/loop-demo-clinicalos-sandbox-20261017/`

Fresh-process replay results: `orchestration/w3-perfflux-replay.json` and
`orchestration/w3-clinicalos-replay.json`. The shared CPU crash recovery evidence is
`receipts/loop-restart-20261017/restart-proof.json`. Integration and boundaries are
in `docs/loop-sdk.md`. Real-world reward still requires Swapnil's PerfFlux workload
data and Loop 38 clinician sign-off. No external communication occurred.
