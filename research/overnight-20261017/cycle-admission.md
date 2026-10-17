# W2 cycle admission

The runnable entrypoint is `scripts/overnight_cycle.py run --connection PATH`.
Use Python >=3.12 with the project's retention extra (`cryptography>=48,<49`).
The connection file is the fresh live pod-B SSH connection object, not the old
B01b connection or a holdout allocation. The runner pins pod5xndo7i7s5r9zn,
qwen2.5-coder:7b digest dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364,
Ollama0.40.5 and NVIDIA A40.

W0's current global inference revocation must be resolved by the coordinator.
The runner does not delete or override it. W0's scoped authorization is read from
`~/nerve-orchestration/W2-cycle-resume-authorization.json` and must contain:

- `authorized: true`, `identity_replay_passed: true`, canonical `model_digest`;
- current `program_sha256` and the exact fresh `connection` object;
- provider `pod_started_epoch`, observed `hourly_usd`, absolute `expires_epoch`;
- `base_compute_usd`, `base_model_calls`, and `resume_compute_cap_usd`.

All source and protected hashes are frozen by session registration. The session
refuses an existing private run directory, preventing ambiguous restart calls.
No model dispatch occurs while the shared revocation is present. The operator
must monitor the process, stop pod B after closure/failure, verify EXITED with a
fresh control-plane read, close the active spend interval and export final state.
The script owns the inference lock; it releases it in a finally block.

The standard six seams are implemented. Agent-node and substrate are optional
and are not admitted by this runner: no registered Hermes normaliser adapter
exists on pod B, and no substrate transition is registered. Neither is silently
substituted by a different model or endpoint. No development result is retention.
