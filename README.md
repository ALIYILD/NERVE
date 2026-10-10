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
