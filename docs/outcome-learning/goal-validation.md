# Goal orchestration validation — 2026-10-15

- NERVE: 1,447 Python tests run; 1,446 passed, one skipped. Full unittest discovery with the existing local-socket and nested-sandbox permissions. The outer restricted-sandbox run failed existing sandbox fixtures; the unrestricted rerun passed.
- PerfFlux: 69 tests passed covering the new goal process test, outcome learning, fleet agents/integration, and the existing adaptive delivery orchestrator. Verified after integrating current upstream main.
- Clinical OS: new offline goal subprocess test passed after integrating current upstream main. This change does not touch the backend API or patient workflows.
- Both host source manifests verified byte-for-byte against NERVE. Each host used separate processes for study, adoption, monitoring, and completed-goal replay.
- Existing Agent OS bridge `goal-run` and `python -m nerve_awim goal status` passed on the same checkpoint.
- PerfFlux changed test lint and formatting checks passed.

The clinical and PerfFlux synthetic studies each recorded 12/12 final successes against 0/12 for the limited starting strategy and 12/12 for the capable control. Retention: 8/8 before and after. Monitoring: 12/12. Isolated corrupted-output probes triggered versioned rollback and executed the previous strategy. This proves the bounded mechanism on these fixtures, not clinical efficacy or real GPU savings.
