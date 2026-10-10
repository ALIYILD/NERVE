# NERVE-AWIM — Adaptive World Intelligence Model

An open-source **research prototype** exploring sensor-driven world models, adaptive learning, state estimation, and safe planning.

**Status:** Experimental, simulation only. Not validated for real-world robotics or clinical decision-making.

## WorldCore v1.2 research release

The accompanying v1.2 package includes:
- Online parameter learning, adaptive routing and episodic memory experiments
- Nonlinear synthetic dynamics and unseen-regime evaluation
- Multi-step planning and closed-loop adaptive control
- Noisy, missing and delayed sensor observation experiments
- Timestamp-aware joint position/velocity estimation
- Reproducible synthetic benchmarks and 92 passing Python unit tests

The public repository currently includes a minimal core, the v1.2 delayed-observation filter, and a v1.3 integration module. The complete standalone v1.2 package is not yet imported. **Do not infer that unreleased integrations are present in this repository.** The planned Hermes, Jev, quantum-cloud and real-device adapters are not implemented in v1.2.

## Architecture

`Sensors → Perception → WorldCore → NERVE Decision Layer → Safe Action → Feedback → Evaluated Memory/Model Updates`

See the academic research proposal at https://deepsynaps.ai/blogs/nerve-awim-adaptive-world-intelligence-research and the [AI Lab model page](https://deepsynaps.ai/awim).

## Run the test suite

With Python 3.10+ and the source tree available:

```bash
PYTHONPATH=src python -m unittest discover -s tests -q
```

The standalone v1.2 archive was checked locally with **92 tests passed**. The public repository has a smaller test suite; see GitHub Actions for its actual status. These results are not external validation.

## Research principles

Report strong baselines, negative results, measurement uncertainties, model and hardware versions, deterministic seeds and failure modes. Keep patient information and credentials out of this public repository.

## Licence

Apache License 2.0. See `LICENSE`.

## Citation

NERVE-AWIM contributors (2026). *NERVE-AWIM: A Bio-Inspired Adaptive World Intelligence Architecture*. Research software and specification, DeepSynaps AI Lab.

## Security

Do not deploy this prototype to control medical or physical systems without independent assurance, access controls and hardware-level safety mechanisms.

## WorldCore v1.3 — experimental sensor-only MPC integration

The `integrated_v13.py` module combines the published timestamp-aware position/velocity filter with a bounded multi-step action planner and cautious online gain adaptation from consecutive timestamped velocity observations. It receives **observations only**; it does not receive hidden simulator state. Its uncertainty penalty is heuristic, not a calibrated safety guarantee.

Run `PYTHONPATH=src python -m unittest discover -s tests -v` and inspect the CI run for the actual public-repository result. The v1.3 module has not yet been benchmarked against v1.2 end-to-end, and real-world performance is unknown.

## v1.5 — Calibration and regression diagnostics

- `calibration_v15.py`: rolling absolute-error prediction intervals with test-before-update evaluation to prevent outcome leakage. Empirical coverage is measured; no distribution-free coverage guarantee is claimed under drift.
- `regression_v15.py`: two-metric research check that declines an improvement claim when goal tracking regresses despite lower prediction error.
- The v1.4 controller and its benchmarks remain unchanged as comparison baselines; neither v1.5 utility is yet integrated into the action policy.

Run all tests with `PYTHONPATH=src python -m unittest discover -s tests -v`. For measured performance, use the benchmark workflow outputs rather than assuming gains from new functionality.

## WorldCore v2.0: adaptive risk planning and sensor supervision

`worldcore_v20.py` connects the v1.9 coverage adaptor to candidate-action ranking and returns an explicit unavailable/infeasible result after persistent loss of observations. The new benchmark is `benchmarks/v20_benchmark.py` and runs in CI.

**Measured limitation (20 synthetic seeds, CI run 38073146982):** v2.0 aborted all 20 episodes during the forced sensor outage (mean 40.7 of 80 steps executed), while v1.7 continued. The final errors at different stopping times cannot be used to claim v2.0 is better or worse at full-horizon tracking. Prequential empirical coverage was approximately 81.1%, below the nominal 90% target. Zero constraint violations observed before abort are *not* evidence of safety.

Next experiments should implement a separately simulated, externally supervised recovery policy, report complete-episode task outcomes, and test a held-out sensor fault regime. Do not deploy to physical actuators or clinical devices.

## WorldCore v2.1 — supervised sensor recovery (simulation)

The `recovery_v21.py` module adds a lockout state machine: sensor loss → supervision required → fresh observation qualification → explicit approval → resumed decisions. The associated `benchmarks/v21_benchmark.py` experiment assumes an independent simulated supervisor applies zero control during lockout; **that assumption is not a real-world safe-stop mechanism**.

The 20-seed synthetic benchmark in GitHub Actions run 38073284167 showed a mean 14.05 withheld autonomous decisions, 1 approval-assisted recovery per run, mean final goal error 0.2253 and zero observed configured-envelope violations. These values do not establish physical safety, secure approval authentication, or generalised fault recovery. Human approval is modelled as an explicit boolean, not an authenticated operator identity. Hardware integration remains prohibited without external safety engineering and verification.

## WorldCore v2.3 — independent evidence and local audit

`recovery_policy_v23.py` adds an independent consistency evaluator for timestamped position/velocity recovery evidence and append-only JSONL audit recording with per-record SHA-256 digests. Five new tests cover consistent, contradictory and duplicate evidence, audit persistence and simple tamper detection. GitHub Actions run 38073534539 passed 81 tests.

**Important limitations:** these modules are separate from the v2.2 recovery controller and are not yet mandatory approval gates; local SHA-256 checksums are not authenticated signatures or tamper-evident chained storage. The identity fields in v2.2 remain unverified assertions. These components cannot be used as production authentication or physical safety controls.
