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

## WorldCore v2.4 — evidence-gated recovery

The `EvidenceGatedRecovery` controller connects independent evidence consistency checks to incident-scoped supervisor approval. Recovery now requires at least two complete timestamped position/velocity records meeting configured consistency tolerances; incomplete, contradictory or stale records cannot authorise resumption. Replayed approval nonces remain rejected by the v2.2 layer. Tests: GitHub Actions run 38073646374 passed 85 tests.

**Research/security limits:** asserted supervisor role is not cryptographically authenticated; the evaluator checks consistency, not sensor truth or causal plausibility; audit events remain process-memory records; and the new recovery class is an opt-in research integration, not a production entry point. Do not connect to physical or medical devices.

## WorldCore v2.5 — signed simulated recovery authorisation

The opt-in `SignedRecovery` class (`recovery_v25.py`) requires an HMAC-SHA256 signed, incident-scoped approval with a principal, supervisor role, nonce and expiry. A SQLite ledger records approval events and persists used nonces across process instances. Five new tests cover valid signatures, forged signatures, expiry, legacy API bypass, and replay prevention with a reopened ledger. GitHub Actions run 38073760119 passed **90 tests**.

**Security boundaries:** A shared HMAC key does not authenticate a real human or establish independent authorisation; anybody holding that key could issue a valid token. There is no real identity provider, hardware key management, trusted time source, key rotation, transactional binding between all controller state and ledger writes, or tamper-resistant event storage. Do not publish secrets or connect this experimental controller to actual robotic or clinical equipment. Before production, use externally authenticated identities and independently engineered safety controls.

## WorldCore v2.6 — identity verification boundary

The opt-in `IdentityBoundRecovery` integrates an injected identity-verification interface with existing incident-specific signed approvals. Acceptance requires a verifier-provided subject, matching issuer and audience, unexpired identity, required `recovery-supervisor` role, and identity subject matching the signed approval principal. Inherited signing-only approval is denied to avoid bypassing the identity boundary. GitHub Actions run 38074351071 passed **97 tests**.

**Not production authentication:** the tests use a synthetic verifier that returns preconstructed identities. There is no live OAuth/OIDC provider, JWKS signature validation, issuer configuration hardening, operator MFA, revocation, or KMS integration in this prototype. The verifier is a trusted boundary whose real implementation must be independently security-reviewed. No physical or medical actuation should be connected.

## WorldCore v2.7 — OIDC verification adapter

`PinnedOIDCVerifier` in `oidc_v27.py` implements an offline, fail-closed RS256 JWT verifier using an explicitly provisioned JWKS and pinned HTTPS issuer, audience and algorithm. Claims validated include issuer, audience, subject, issued-at and expiration. The resulting `VerifiedIdentity` can be passed to the existing v2.6 identity-bound recovery interface. The CI workflow installs `PyJWT[crypto]` and uses locally generated RSA test keys. GitHub Actions run 38075175393 passed **103 tests**.

**This is not a live IdP integration.** Operator-provisioned keys must be obtained securely; key rotation, IdP discovery hardening, revocation, logout, identity assurance, MFA, secure clock sourcing, key custody and distributed audit policy remain outstanding. Do not trust arbitrary JWKS URLs or use these tools to control robots or medical devices without independent security and safety engineering.

## v2.8 — key rotation and consolidated research runtime

- `key_rotation_v28.py` allows an operator-authorised, fail-closed replacement of a pinned OIDC JWKS. The candidate verifier is constructed before it replaces the active verifier. It does **not** fetch or authenticate key sets from a live IdP; the caller must securely provision them.
- `runtime_v28.py` provides a narrow research entry point for sensor events, lockout, and identity-bound recovery approval, without granting AI agents authority to approve recovery.
- GitHub Actions run 38075358712 passed **108 tests** with the pinned-JWKS and unified-runtime tests included.

This is simulation-only work. The operator authorisation flag is itself an untrusted input unless an external control plane enforces it. Key rotation lacks distributed coordination and revocation; live OIDC integration and device safety certification remain out of scope.

## v2.9 — observable runtime and end-to-end recovery test

`telemetry_v29.py` introduces a bounded in-process event trace with strictly limited event categories and statuses, while `observed_runtime_v29.py` wraps the existing research runtime to log control, sensor and identity outcomes. The integration test simulates a missing sensor, a denied identity assertion, and an accepted supervisor approval. GitHub Actions run 38075485337 passed **111 tests**.

**Limitations:** no live identity-provider connection, distributed tracing, persistence, privacy/security certification or real actuator controls. In-memory trace records are ephemeral and are not a replacement for the durable incident ledger. Do not place patient data or secrets in telemetry events.

## v3.0 — typed multi-agent research foundation

`agents_v30.py` introduces validated task envelopes, deterministic capability routing, specialist processing stubs and a provenance-preserving in-memory result store. `benchmarks/v30_benchmark.py` compares coverage against one deliberately restricted specialist. GitHub Actions run 38075635069 passed **119 tests**; in the 100-task capability benchmark, the multi-specialist coordinator handled 100 supported task types and retained 100 source identifiers, whereas the EEG-only baseline could accept only 50 tasks.

**Interpretation:** this is coverage by design, *not* higher predictive accuracy, learning speed, LLM-agent functionality, Hermes integration or demonstrated world-model benefits. The next meaningful experiment must compare equivalent-capability, equivalent-budget baselines on held-out prediction and planning tasks.

## NERVE Learn — public agent developer preview

**Bring evaluated experience memory to existing AI agents without replacing their framework.**

- Local, opt-in SQLite memory, scoped by caller-supplied agent ID (not authentication).
- MCP tools to record an experience, retrieve past tasks, rate outcomes, and suggest candidate lessons.
- OpenClaw-compatible skill template at `skills/nerve-learn/SKILL.md`.
- Setup and security limitations in `docs/nerve-learn-launch.md`.

The prototype does **not** self-retrain LLM parameters, prove faster learning or automatically rewrite agent policies. Do not send secrets or private medical data to the store. Existing safety policies remain authoritative.

**Try it locally:**

```bash
python -m pip install 'mcp>=2,<3'
PYTHONPATH=src NERVE_LEARN_DB=./nerve-learn.db python -m nerve_awim.learn_mcp
```

ClawHub listing is a separate publication step and is **not yet verified**. Benchmarks against matched no-memory baselines are still required before claims of improved agent performance.

## v3.1 — typed prediction and contextual memory benchmark

The `collaboration_v31.py` module connects the deterministic typed-agent coordinator with a one-step scalar predictive transition and an explicit-context experience store. `benchmarks/v31_benchmark.py` compares the same specialist priors with and without prior observed feedback. GitHub Actions run 38075918098 passed **130 tests**. Across 20 deterministic synthetic seeds, late prediction MAE was **0.192123** with contextual feedback and **0.225480** without it (approximately 14.8% lower).

**Scientific limitation:** this is not yet integration with the existing multi-step WorldCore controller or a real Hermes runtime. The comparator has equal specialist capability but no equivalent learning/memory facility, so the experiment isolates feedback-memory benefit, **not a pure multi-agent benefit**. The next ablation should compare a single-agent learner with the same memory and compute budget, then measure planning reward, errors and latency. Research only; no physical actuation or clinical claims.

## v3.1 matched-feedback learning ablation

`benchmarks/v31_ablation.py` uses the same 120-task observations and one update per task to compare a shared single learner, per-context specialist learners, and fixed specialist priors. GitHub Actions run 38076064514 passed **133 tests**. Across 20 synthetic seeds, post-change mean absolute error was:

| Method | MAE |
| --- | ---: |
| Single learner with memory | 0.121099 |
| Specialist learners with memory | 0.171796 |
| Fixed specialists | 0.245548 |

**Negative result for the collaborative hypothesis:** the single shared learner outperformed the contextual specialists on this task. The methods use different parameterisations despite matched observations and update counts; compute overhead, multi-step WorldCore planning and agent communication are not measured. There is no basis yet to claim NERVE agents improve accuracy or speed over equivalent single learners. Preserve this result in future comparisons.

Next experiments should test partial observability, specialist information advantages, equal parameter budgets, cost/latency and task-level outcomes before any superiority claims.

## v3.2 — complementary multimodal sensor ablation

`benchmarks/v32_multimodal.py` compares a single-sensor learner, a single two-channel model, and a two-channel specialist-fusion formulation under the same deterministic 20-seed synthetic task stream and equal update counts. GitHub Actions run 38076241102 passed **137 tests**. Mean prediction MAE was **0.198922** with one sensor versus **0.069575** for both two-sensor formulations. Single fused and specialist fused predictions were *identical*, as expected from their mathematically equivalent linear updates.

**Interpretation:** added sensor access improves prediction for this constructed task; splitting equivalent computations into specialist modules does not. No inter-agent communication cost, real sensor data, partial-observation inference, WorldCore multi-step control improvement or physical safety advantage is demonstrated. The next useful experiment must test non-equivalent specialist reasoning against a comparably capable unified model under matched compute and inputs.

## v3.3 — nonlinear equivalent-capacity ablation

`benchmarks/v33_nonlinear.py` tests synthetic nonlinear sensor dynamics with abrupt parameter change and 20% second-channel dropout. A unified eight-parameter model and context-specific specialist models use equivalent block-feature gradient updates. The small two-parameter linear reference has less representational capacity. GitHub Actions run 38076403825 passed **140 tests**.

Measured late prediction MAE across 20 seeds: simple linear **0.159554**, unified nonlinear **0.208573**, specialist nonlinear **0.208573**. The equal-capacity models are algebraically equivalent, so the identical results are expected. Their poorer accuracy than the simple reference may reflect parameterisation and online adaptation under the chosen learning rate. No multi-agent coordination benefit is demonstrated. Real model runtime, communication overhead, token cost, and physical/clinical safety have not been benchmarked.

## NERVE AutoResearch v0.1 — bounded experiment loop

Inspired by [Andrej Karpathy's AutoResearch](https://github.com/karpathy/autoresearch), NERVE now has a constrained research cycle in `autoresearch_v01.py`: propose from predefined learning-rate candidates, evaluate on fixed validation seeds, keep or reject, and report once on untouched holdout seeds. Research rules: `research/program.md`; methodology: `docs/autoresearch-integration.md`.

Run with `PYTHONPATH=src python -m nerve_awim.autoresearch_v01`. CI run 38076632867 passed **145 tests**. The selected scalar-learning-rate candidate was 0.3, with holdout MAE **0.038390** versus **0.153064** for the default 0.02 baseline. These numbers are from a simple synthetic parameter-adaptation task, not from real agent collaboration, model-weight training, robotics, or clinical workflows.

**Research limitations:** candidates are predefined, code edits are not autonomous, evaluator isolation depends on source control, and the fixed benchmark can be overfit if reused repeatedly. Keep/reject only affects this experiment report, not production code or policy.
