# NERVE-AWIM — Adaptive World Intelligence Model

An open-source **research prototype** exploring sensor-driven world models, adaptive learning, state estimation, and safe planning.

**Status:** Experimental research: simulations and bounded repository/agent-tool experiments. Not validated for real-world robotics or clinical decision-making.

## Verified memory gateway: executable synthetic integration

The optional memory gateway now connects to the existing NERVE demo agent,
bounded parallel pipelines and NERVE Learn MCP. A host-owned configuration
builds the scoped ledger, pinned-OIDC HTTP service and restricted agent sessions.
Approved structured hints select existing allowlisted tools; outcomes remain
pending until separate host review. Legacy behavior is unchanged when disabled.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools
.venv/bin/python -m pip install -r deploy/requirements-memory-synthetic.txt
PYTHONPATH=src .venv/bin/python scripts/memory_gateway_demo.py
PYTHONPATH=src .venv/bin/python scripts/memory_gateway_demo.py --provider galahad
PYTHONPATH=src .venv/bin/python scripts/memory_gateway_mcp_wire.py
```

These commands use temporary synthetic stores and keys. They exercise signed
HTTP, approved/pending evidence, actual agent execution, parallel jobs, ledger
reopen, revocation and official MCP stdio. The Galahad option exercises ordinary
text fallback: **real persistent KV restoration is not enabled or verified**.
Nothing is deployed. See the [runtime and wiring guide](docs/galahad/15-runtime-wiring.md)
for configuration, local launch commands and remaining integration boundaries.

## v2.1 opt-in repository task shadow learning

The [v2.2 persistent pilot runner](docs/repository-pilot-v22.md) adds sealed study
manifests, pre-reserved holdouts, content-change checks and a reviewable rollout
recommendation across separate processes. It never activates a release.

The [v2.8 installation bundle](docs/pilot-installation-v28.md) packages the pilot
with a checksum manifest and Linux/Python dependency lock. A separate CI job
checks the extracted service in a clean venv, including signed HTTP and recovery.
This verifies installation mechanics; it does not deploy a public service.

The [v2.7 operations bundle](docs/host-operations-v27.md) adds authenticated
readiness, startup checks, non-overwriting SQLite backup/restore and a systemd
pilot template. Recovery preserves trial bindings and monitoring state; no live
host or identity provider is provisioned by the bundle.

The [v2.6 HTTP trial binding](docs/bound-repository-host-v26.md) connects the
signed task endpoint to an operator-approved trial and its post-promotion monitor.
Bindings persist across restarts, reject unrelated deployment changes and expose
trial/rollback evidence to scoped auditors. No remote operator API is exposed.

The [v2.5 authenticated repository host](docs/repository-host-v25.md) connects
pinned OIDC identities to scoped HTTP tasks and off-request-path shadow learning.
It serves the strong AST baseline, persists aggregate evidence, and exposes no
remote release controls. The loopback pilot is tested, not publicly deployed.

The [v2.4 promotion monitor](docs/promotion-monitor-v24.md) can be armed atomically
with operator-approved promotion. It checks fresh promoted results and restores
the previous release on failure, while respecting newer operator decisions.
Monitoring persists across restarts and requires the host controller entrypoint.

The [v2.3 canary controller](docs/canary-learning-v23.md) lets a trusted operator
approve limited trial traffic for a passed candidate. It checks candidate outputs,
automatically falls back on canary failures, and requires separate approval for
full promotion. This local API is tested with repository tasks; it is not wired to
a downstream clinical application or external LLM traffic.

The [shadow adapter](docs/shadow-task-learning-v21.md) now executes selected real
repository tasks with the active tool, then independently judges outputs and
trains alternative tool routes outside the request path. Aggregate outcomes and
release provenance persist across processes; source text is not stored. Measured
handler latency is reported; provider costs remain explicitly unknown.

The active AST tool is the strong fixed baseline. In the cross-process check,
both baseline and candidate score 5/5 on disjoint files, so the proposal is
rejected and no release changes. This is an executable research workflow, not a
live integration with a downstream clinical application or a claim of general
self-improvement.

```bash
PYTHONPATH=src python scripts/verify_shadow_v21.py
```

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

NERVE-AWIM contributors (2026). *NERVE-AWIM: A Bio-Inspired Adaptive World Intelligence Architecture*. Research software and specification.

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

## NERVE AutoResearch v0.2 — bounded proposal coordinator

`src/nerve_awim/autoresearch_v02.py` accepts typed `Proposal` objects constrained to a finite gain-learning-rate range, evaluates them on an immutable-in-code synthetic WorldCore-*adjacent* drift task, records keep/reject decisions, and writes a JSONL experiment ledger. A separate 30-seed holdout is reported after validation selection. The loop cannot edit Python source, launch subprocesses, alter safety policies or deploy model changes.

GitHub Actions run 38076802612 passed **150 tests**. The four-candidate demonstration selected gain learning rate **0.4** with holdout MAE **0.040716**, versus **0.223218** for the fixed rate 0.02. This is an easy synthetic drift-adaptation comparison, not a general-purpose self-improving AI demonstration. Repeatedly inspecting the same public holdout destroys its independence in future research. CPU/memory/time isolation and real WorldCore/agent-runtime integration are **not yet implemented**.

## NERVE AutoResearch v0.3 — cross-benchmark regression gate

`src/nerve_awim/autoresearch_v03.py` evaluates **existing** v3.1 memory-ablation, v3.2 multimodal and v3.3 nonlinear benchmarks. Candidates choose from a hardcoded unified or specialist architecture portfolio; no source editing or arbitrary execution is enabled. A candidate must improve at least one metric without regressing another to be promoted within the experimental report. An independent reporting-only seed set is evaluated after selection, and optional JSONL records retain accepted and rejected proposals.

GitHub Actions run 38077082868 passed **157 tests**. The specialist portfolio was rejected and the unified reference remained selected. These are synthetic benchmark outcomes, not evidence of autonomous code discovery, supervised robotics readiness or improvement in clinical outcomes. The suite contains different model parameterisations; do not interpret this as a comprehensive compute-matched agent comparison.

**Next:** invoke actual WorldCore closed-loop control in a protected evaluation runner, measure action cost and latency, and keep the report-only holdout sequestered for future experiments.

## NERVE AutoResearch v0.4 — actual WorldCore closed-loop evaluation

`src/nerve_awim/autoresearch_v04.py` instantiates the existing `WorldCoreV2` simulator controller and evaluates bounded `max_missing` and `risk_aversion` proposals against a fixed synthetic drifting plant, delayed observations, and prolonged sensor outage. Its research gate requires no increase in aborted episodes, no additional simulated constraint violations, no loss of completed steps, and no worsening of penalised prediction error before preferring lower penalised goal error. Uncompleted steps carry penalties, rather than being treated as success. Proposed configurations cannot edit controller code or the evaluator.

GitHub Actions run 38077206796 passed **163 tests**. The selected validation proposal increased `max_missing` from 5 to 8. Validation completion remained only **0.54375** on average and **all evaluated episodes aborted**. The reporting-only holdout completion was approximately **0.5475**. This is not deployment-safe or validated physical control. In particular, the current no-worse-than-baseline acceptance gate does **not** impose an absolute minimum completion threshold. A future release must require independent supervisor-reviewed safety thresholds and report experiments that fail them instead of promoting for deployment.

## NERVE AutoResearch v0.5 — absolute reliability thresholds

`src/nerve_awim/autoresearch_v05.py` introduces an evaluator-defined minimum of **95% episode completion**, **zero aborted episodes** and **zero constraint violations** before a WorldCore candidate is eligible even for *deployment review*. Candidates cannot override these thresholds. An improved synthetic score does not override a failed gate.

GitHub Actions run 38077317425 passed **167 tests**. The default WorldCore controller fails: holdout completion **0.51** on average, aborted fraction **1.0**, violations **0**. The official result is `eligible_for_deployment_review: false`. This does not certify any controller as safe, even if thresholds were met; external verification, human review, real hardware testing and appropriate regulation are still required.

## AutoResearch v0.6 — simulated recovery research check

`benchmarks/v06_recovery_research.py` and `tests/test_v06_recovery_research.py` exercise the existing `SupervisedWorldCore` recovery state machine. A sensor outage must suspend action; fresh observations must not cause automatic resumption without a separate approval; a positive simulated approval allows the state machine to resume. GitHub Actions run 38077915216 passed **170 tests**, including three new test cases and the CLI benchmark. The initial CI failure due to missing action timestamps was repaired in commit `ae6cd2d8`.

**Scope:** this is a narrow simulated state-transition test, not a full AutoResearch search loop. It does not test live identity authentication, HMAC recovery approvals, failure evidence adjudication, hardware control, latency, true recovery success, or clinical safety. Approval in this benchmark is a boolean simulation input only; production approval requires the separate identity-bound recovery interface.

## AutoResearch v0.7 — recovery authorisation regression tests

`tests/test_recovery_v07.py` adds five regression tests covering rejected simulated identities, wrong-incident approvals, inconsistent sensor observations, reused prior-incident approvals and a valid supervised resumption. GitHub Actions run 38078032977 passed **175 tests**. This is a deterministic unit-test expansion around the existing identity-bound recovery boundary, **not** yet a multi-condition autonomous research-search loop. No real identity provider, safety-certified hardware or live credentials are involved.

## AutoResearch v0.8 — aggregate evidence review

`src/nerve_awim/autoresearch_v08.py` brings together the existing WorldCore absolute reliability eligibility gate, simulated supervised recovery state-transition benchmark, and a wall-clock research execution budget. It explicitly reports both individual checks and a collective `all_checks_pass` outcome, without automatically deploying or approving any candidate.

GitHub Actions run 38078147124 passed **179 tests**, with a research report showing `runtime_budget: true`, `simulated_recovery_transitions: true`, but `controller_absolute_eligibility: false`. The aggregate verdict is **false**, due to inadequate completion and aborted episodes. The example measured roughly 0.15 seconds of wall-clock processing on GitHub CI, which is not a general hardware-independent performance claim. No actual resource isolation, live identity provider or production-safety certification is supplied.

## AutoResearch v0.9 — fixed-threshold outage search

`src/nerve_awim/autoresearch_v09.py` explores five bounded `max_missing` choices on the existing WorldCore synthetic outage benchmark, using the absolute completion and abort gates rather than relative goal error alone. GitHub Actions run 38078260043 passed **182 tests**. **No tested choice qualified**: even `max_missing=12` achieved only **59.375%** average validation completion and aborted episodes. `eligible_candidate` is null; no deployment or autonomous recovery is allowed. A bigger outage tolerance alone is not a resilient recovery mechanism. Next research should model post-outage fresh readings, independent approval and resumed operation without compromising controls.

## NERVE Evolution Engine v0.1 — outcome-scored strategy memory

The new `src/nerve_awim/evolution_v01.py` adds a **MemRL-inspired**, independently implemented two-stage strategy selector atop the existing local NERVE Learn store: context-scoped memory retrieval, then explicit feedback-utility ranking. Unrated memories are excluded; agent namespaces are kept separate at the storage-query level (caller-provided IDs are **not** authentication). No third-party implementation or cloud API was imported. See `docs/evolution-engine.md` for the MemRL, GEPA, Letta, Darwin and Hermes integration roadmap.

GitHub Actions run 38078447269 passed **188 full-suite tests**, followed by **6 focused Evolution tests**. This is not proof of improved agent outcomes or a real deployment of the upstream frameworks. The next benchmark must compare reward-based retrieval against an equally informed recency baseline with held-out tasks.


## Parallel NERVE Evolution agents — v1.1 research prototype

The new `parallel_agents_v11.py` and `evolution_cycle_v11.py` implement
bounded local concurrent workers in **five specialised roles**: research,
memory, evaluation, safety and review. Evaluations can run concurrently,
but decisions are collected deterministically and an independent WorldCore
reliability gate still rejects unsafe research candidates. The coordinator
does not run Hermes, external LLMs or arbitrary generated code.

```bash
PYTHONPATH=src python benchmarks/v11_parallel_evolution.py
PYTHONPATH=src python benchmarks/v11_memory_effectiveness.py
```

`learn_mcp.py` now also exposes `select_evaluated_strategy` to compatible
MCP clients. Optional experiment feedback can improve scheduling of later
research candidates, but **cannot change acceptance rules**.

In the 20-seed synthetic held-out memory benchmark, outcome-scored retrieval
achieved **72.22%** task success versus **51.50%** from recency-only retrieval
(oracle **73.28%**). This is a constructed Bernoulli-reward task, not a
real-agent learning validation. A CI check confirmed that serial and
parallel variants made the same rejection decisions; it did **not** establish
faster CPU execution. See `docs/evolution-engine.md` for all limitations.

## Optional TypeSafe AI Jev reviewer (off by default)

NERVE supports a small, independent Jev integration via `jev_optional.py`
and batched `jev_batch.py`. It uses the official TypeSafe System One
HTTPS endpoint for **advisory** research-result critique, while WorldCore's
deterministic safety and eligibility gates remain authoritative.

- Reads `TYPESAFE_API_KEY` only from the runtime environment; no key is stored in Git.
- Shares only five allowlisted synthetic benchmark aggregates, never raw medical records.
- Can batch up to six candidate-review questions in one TypeSafe request.
- Missing keys, malformed model answers and network errors fail closed.
- Optional: omitting the reviewer leaves NERVE fully model-agnostic.

Local single-request smoke test (from the same terminal where the key was exported):

```bash
export PYTHONPATH=src
python -m nerve_awim.jev_optional
```

See [`docs/jev-optional.md`](docs/jev-optional.md) for integration examples
and limits. CI uses mocked responses only; live Jev response, actual latency,
accuracy gains, and account access have not yet been verified.

## Jev advisory-vs-deterministic research comparison

`src/nerve_awim/jev_agreement_v12.py` provides a reproducible six-case
synthetic evaluation of advisory regression warnings against NERVE's
fixed deterministic benchmark and absolute reliability checks.

```bash
PYTHONPATH=src python -m nerve_awim.jev_agreement_v12
```

The **default** uses a deliberately imperfect fake reviewer, with no
network access or key requirement, so disagreement handling can be tested.
False positives, false negatives, per-case review decisions, latency and
token usage are recorded. No inference about real Jev accuracy is possible
from the mock scores. Human-review and deployment eligibility remain
independent of Jev's risk opinion.

With a **fresh** private TypeSafe credential, the optional manual GitHub
Actions workflow `jev-live.yml` offers `smoke` or `comparison` modes.
Each mode sends one batched synthetic API request when manually triggered
on protected `main`; routine CI is always credential-free and offline.
See `docs/jev-optional.md`.

## Evolution v1.2 — learning changes executable agent behaviour

`src/nerve_awim/agent_learning_v12.py` now combines local outcome-aware
SQLite memory with **explicitly registered Python strategy handlers**
and NERVE's bounded parallel-agent executor. The same experience history
supports a utility-mean policy and recency-only comparison. Unknown
strategy names in memories can **never** become executable code.

Use: `PYTHONPATH=src python benchmarks/v12_executable_agents.py`.

On 12 deterministic seeds, using three executable hand-authored task
categories and 72 matched held-out tasks per policy, outcome-aware
selection achieved **100%** exact-output success versus **58.33%**
recency-only selection. Training comprised 30 evaluated outcomes per
seed, shared by both policies. GitHub Actions run 38081097181 passed
**256 full-suite tests** and 6 additional focused Evolution checks.

**Limitations:** This synthetic task construction intentionally contains
correct and incorrect registered strategies. It is not evidence of real
LLM reasoning improvement, independently authenticated feedback, model
weight learning or faster execution. Test answers are not reused for
learning, and production authorisation remains separate from memories.
See `docs/evolution-engine.md` for a usage example and security boundaries.


## NERVE Evolution v1.3 — real MCP agent tool interoperability

The local NERVE Learn MCP server now supports **registered executable
strategy selection** as an additional optional demonstration. External
MCP clients can discover safe capabilities, train on internal verified
fixtures and execute a two-stage JSON-email pipeline through parallel
trusted workers. No external model API, API key or generated-code
execution is required.

Run the official MCP SDK 2.3 stdio integration test:

```bash
python -m pip install "mcp==2.3.0"
PYTHONPATH=src python scripts/mcp_wire_v13.py
```

Run the held-out multi-step benchmark:

```bash
PYTHONPATH=src python benchmarks/v13_external_mcp.py
```

GitHub Actions run [38082358322](https://github.com/ALIYILD/NERVE/actions/runs/38082358322)
passed **270 unit tests**, six focused Evolution tests, and a real SDK
stdio handshake with six tools discovered. In 12 synthetic seeded runs,
outcome-ranked selection achieved **100%** on 18 two-step evaluation tasks
per seed versus **0%** for a deliberately weak recency-only comparator;
a fixed-correct non-learning pipeline also achieved **100%**. This
demonstrates retrieval-guided selection of known tools, **not** general
AI-agent improvement, new tool learning or a speedup over a capable
baseline.

See [MCP setup and limitations](docs/nerve-learn-launch.md).
Caller-supplied agent namespaces are not authentication. Demo tools
are intentionally inert and should not be exposed as a public HTTP
multi-tenant service or used on regulated data.

## NERVE Evolution v1.4 — model-selected, memory-guided MCP tools

NERVE now includes a **provider-independent, opt-in model plan selector**
(`llm_agent_v14.py`) and a real MCP client evaluation harness
(`scripts/llm_mcp_v14.py`). A model proposes only allowlisted strategy
identifiers for the trusted JSON extraction and email normalisation demo;
the host refuses unknown identifiers, commands, insecure endpoints,
HTTP redirects and unauthorised feedback updates.

The reproducible offline comparison uses the same task cases and
decision/tool-call budget in both arms:

```bash
PYTHONPATH=src python scripts/llm_mcp_v14.py --cases 4
PYTHONPATH=src python scripts/llm_mcp_v14.py --mock-api --cases 4
```

Both run through the **real MCP 2.x stdio client** and server; the
first uses a deterministic planner fixture and the second uses a fake
chat-completions API with validated JSON/token parsing.
Live inference requires an operator-configured HTTPS provider URL,
model ID and private `NERVE_LLM_API_KEY` and is **not** exercised by CI.

These constructed tests establish **protocol compatibility and
control-flow integrity**, not improvement of actual LLM intelligence
or self-retraining. See [v1.4 research guide](docs/llm-agent-v14.md).

## Evolution v1.5 — Context-specific learning with matched agent controls

`agent_study_v15.py` adds format-scoped evaluation history and an
optional `FormatChatPlanner` for model-assisted decisions. Its real MCP
study runs on independent synthetic training and held-out examples in
two formats (`json_email`, `plain_email`), using exactly the same
registered capabilities, task inputs and decision/tool budgets in
both the no-memory and memory arms.

```bash
python -m pip install 'mcp==2.3.0'
PYTHONPATH=src python scripts/agent_study_v15.py --seeds 2 --cases 3
PYTHONPATH=src python scripts/agent_study_v15.py --limited-fixture --seeds 2 --cases 3
PYTHONPATH=src python scripts/agent_study_v15.py --mock-api --seeds 2 --cases 3
```

A **capable fixture** gets 100% with or without memory; a deliberately
limited fixture improves after receiving evaluated format-specific
recommendations. The mocked Chat Completions provider also solves
both conditions without real network inference. No live LLM benchmark
result is available and these tests do not prove learning-speed gains.

An optional [manual protected live workflow](.github/workflows/llm-study-v15.yml)
can run a bounded study using a fresh private model credential. Its
environment must be configured and reviewed independently.
See [v1.5 evaluation guide](docs/evolution-v15.md).

## Evolution v1.6 — paired evidence, uncertainty and failure accounting

The same-agent MCP experiment now scores **paired held-out tasks** across
memory and no-memory arms. `study_statistics_v16.py` reports per-format
and aggregate accuracy, discordant wins/losses, explicit task errors,
descriptive exact McNemar statistics and seed-cluster bootstrap
intervals only when at least five distinct seeds are available.

Model-planning errors are counted as failed tasks and remain in accuracy
denominators. Actual executed tool calls, model errors, reported token
usage and latency are recorded separately; no raw user inputs or
API credentials are included in the report. The statistical p-value is
**descriptive** because task pairs within seeds are dependent.

Try these credential-free commands after installing MCP 2.3:

```bash
PYTHONPATH=src python scripts/agent_study_v15.py --seeds 5 --cases 2
PYTHONPATH=src python scripts/agent_study_v15.py --failure-fixture --seeds 2 --cases 2
```

A capable offline planner still achieves the same accuracy with and
without memory; mock provider failures now remain visible instead
of being silently excluded. Five synthetic seed clusters are not a
powered, independent real-LLM study. **No real-model improvement,
speed advantage, clinical efficacy or physical-AI reliability claim**
has been established. See [v1.6 methodology](docs/evolution-v16.md).

## NERVE Evolution v1.7 — bounded recover-after-failure agents

`recovery_learning_v17.py` adds independently checked, two-attempt
execution to registered local agent strategies. Success is decided only
by a trusted evaluator; a failed handler may trigger one registered
fallback. Held-out runs never silently update experience memory.

```bash
PYTHONPATH=src python benchmarks/v17_recovery_agents.py
```

In 12 synthetic 27-task runs spanning email transformation, numeric
sorting and JSON extraction (including three unrecoverable tasks per
run), final completion was **88.89% for all three policies**.
Outcome-aware memory averaged **1.111 tool invocations per task**;
a less-informed no-memory fallback averaged **1.630**, while the
preconfigured fixed-correct control likewise averaged **1.111**.
This shows reduced wasted attempts versus a weak baseline, **not**
inherent multi-agent superiority or general self-improvement.

The local MCP stdio service now also provides
`run_bounded_recovery_demo`, a fixed-scenario training/retry test
with no user-provided code, judge, secrets or hardware operations.
The real official MCP SDK smoke test checks recovery alongside
tool discovery and multi-step agent execution.

See [v1.7 recovery research guide](docs/evolution-v17.md) for
protocol details, rejected failures and security limitations.

## Memory v1.8 — scoped verified ledger + optional Mem0/Obsidian pilot

New, **opt-in and not yet production-deployed** components:

- `memory_v18.py`: local trusted-host-issued capability contexts, exact
  tenant/agent scope, pending/approved/revoked/superseded status, expiry,
  evaluator identity, content hash, and hard deletion.
- `memory_retrieval_v18.py`: lexical baseline and an optional OSS Mem0
  **read-side semantic adapter**; every suggested ID is revalidated
  against the authoritative in-scope, approved and nonexpired SQL record.
- `obsidian_export_v18.py`: human-readable, one-way Markdown review
  preview for approved synthetic/public memories, not a live vault sync.
- Legacy unverified MCP `record_experience` and `rate_experience` writes
  are now **OFF by default**. Only fully trusted single-user local
  experimental clients should opt in with
  `NERVE_ENABLE_LEGACY_MCP_WRITES=1`. This flag is NOT remote auth.

Run the synthetic retrieval benchmark:

```bash
PYTHONPATH=src python benchmarks/v18_memory_retrieval.py
```

**Important:** this benchmark uses a curated semantic fixture, **not
actual Mem0**; no live embeddings, semantic accuracy gain or pgvector
service has been proven. No API keys or patient data are required.
The original SQLite agent demos remain compatible, but this new
security model is not a remote multi-tenant authentication system.

See [implementation and limitations](docs/memory-v18-implementation.md)
and [memory architecture decision](docs/memory-backend-decision-v18.md).

## NERVE recursive self-improvement research v1.9

An **AlphaEvolve-inspired, self-iterating research controller** now
runs data-only retrieval-configuration experiments in generations:
mutate bounded candidate recipes → independently evaluate training and
validation → reject privacy/scope violations and regressions → retain
the best evaluated genome → mutate again → check report-only holdout.

```bash
PYTHONPATH=src python -m nerve_awim.recursive_evolution_v19
PYTHONPATH=src python scripts/recursive_research_v19.py --seed 19 > first.json
PYTHONPATH=src python scripts/recursive_research_v19.py --resume first.json --seed 20 > next.json
```

The public [scheduled research workflow](.github/workflows/recursive-research.yml)
runs this bounded offline cycle **every six hours** on `main` when
GitHub Actions scheduling is enabled. It keeps a small **typed genome
checkpoint** in a separate 90-day GitHub Actions artifact (subject to repository
retention policy), with cache fallback. It re-evaluates previous winners
rather than trusting old fitness numbers, and publishes research JSON
artifacts for review. Its repository permissions are **read-only**;
there is no self-commit, auto-merge, model-key usage or deployment.

The test domain is a fixed, constructed memory-retrieval dataset,
**not** proof of broad self-improving intelligence. This is not the
Google AlphaEvolve service or LLM-generated code evolution. Future
source-code mutation would require an isolated sandbox, verified
evaluator provenance, independent holdouts and human-reviewed PRs.

A separate [artifact integration check](.github/workflows/research-persistence-ci.yml)
uses two fresh GitHub runners to verify upload, download, byte identity and resumed
exploration. Its synthetic CI artifacts never seed the scheduled research history.

See [loop architecture and schedule](docs/recursive-evolution-v19.md).

### Recursive WorldCore experiments (same schedule)

A second, independently gated generational track evolves **data-only**
WorldCore outage/risk settings through the existing fixed simulator:

```bash
PYTHONPATH=src python -m nerve_awim.worldcore_recursion_v19
```

Absolute completion, abort and violation gates, non-regression constraints
and a distinct holdout evaluation remain frozen. The scheduled workflow
generates a separate `worldcore-research.json` artifact; **no controller
setting is applied** to deployed NERVE, robots, or neuromodulation devices.

GitHub Actions scheduling is best-effort, not an always-on service.
Artifacts can expire and caches can be evicted. Checkpoints are written atomically,
checked for corruption, and reset when evaluator code changes. Prior selected
values are re-evaluated; old fitness and holdout scores are never checkpoint inputs.
Across restarted runs the search can explore all 35 allowed recipes, then reports
exhaustion instead of claiming further improvement. The fixed holdout is reused
for reporting and is not fresh independent evidence across runs. See `docs/recursive-evolution-v19.md`.


## Governed task-outcome learning v2.0

`governed_learning_v20.py` now learns routing decisions from actual registered
handler executions judged by a host-provisioned independent evaluator. It stores
scoped outcomes, freezes candidates, enforces one-use held-out evaluation, and
requires a separate operator capability for activation or rollback. Active routes
and audit history survive process restarts. No public release/write endpoint is
added and no production deployment is performed.

```bash
PYTHONPATH=src python benchmarks/v20_governed_repository_learning.py
```

On actual NERVE repository function-inventory tasks (four training files, eight
held-out files), the initial regex route scored **2/8**, the learned route **8/8**,
and a capable fixed AST tool also **8/8**. Approval changed the executed route;
rollback restored the original behaviour in an isolated temporary runtime.
This is tool-selection learning on a small public-code workload, not LLM weight
training or evidence of broad autonomous intelligence. The demo's operator is
simulated; remote authentication and live integration with a downstream clinical
application are not supplied.

See [host integration, evidence gates and boundaries](docs/governed-outcome-learning-v20.md).


## Bounded automatic memory adaptation (synthetic research)

The optional gateway runner now executes approved registered strategies, obtains
a trusted independent outcome evaluation and records utility feedback automatically.
Future episodes adapt to recent verified outcomes. Budgets, pending crash claims
and replay protection persist across restart; strict execution refuses absent or
invalid evidence. It does not train model weights or automatically approve new memories.

```sh
PYTHONPATH=src python scripts/memory_autoadapt_demo.py
```

The16-episode synthetic drift fixture changes its strategy without host-selected
routes or separate feedback calls. This is narrow registered-tool adaptation,
not general autonomous intelligence. See [execution, limits and evidence](docs/galahad/20-automatic-adaptation.md).

## Measuring improvements to NERVE itself

The self-study compares the current adaptive-memory policy with six registered
window/tie-breaking configurations, using validation-only selection and frozen
held-out probes. An opt-in least-recent tie policy addresses repeated-failure
lock-in; it does not grant access or automatically replace the current default.

```sh
PYTHONPATH=src python benchmarks/memory_self_improvement.py --output /tmp/nerve-self-study.json
```

The experiment uses actual registered synthetic tools, matched initial state,
fixed controls and explicit no-improvement outcomes. It is not model-weight
training or proof of real scientific discovery. See [protocol and measured results](docs/galahad/21-nerve-self-improvement.md).

### Bounded memory-policy research generations

The durable research loop evaluates a finite candidate grid, records rejected candidates, stops after two stalled generations, and freezes selection before one holdout evaluation. Its first run completed 4,700 synthetic tool executions and retained the current policy because no candidate passed every improvement gate. All 1,114 regression tests pass. This is local policy research; model weights and deployment remain unchanged. See [execution evidence and reproduction](docs/galahad/22-bounded-research-loop.md).

### Discounted feedback research

Optional per-observation discounting now weights old verified outcomes less heavily. The fresh v3 study executed 5,800 synthetic tool calls; recurrent validation improved for fast discounting, but training regressed, so the current policy was retained. See [primary-source rationale, evidence and reproduction](docs/galahad/23-discounted-feedback-research.md).

### Prospective online adaptation

A fixed discounted-feedback policy scored **84.33% versus 75.44%** for the existing learner across 2,048 fresh synthetic online episodes per arm, with no scenario regression. It is a candidate for review; defaults remain unchanged. The separate real local-model smoke attempt failed at the 30-second deadline. See [protocol, complete results and reproduction](docs/galahad/24-online-adaptation-and-local-model.md).

### Local model readiness diagnostics

The local inference adapter now provides sanitized host-side failure categories while retaining generic public errors. A separate preload/probe CLI identified an output-limit failure on the CPU model; no incomplete completion was accepted. [Evidence and reproduction](docs/galahad/25-local-runtime-readiness.md).

### Opt-in CPU inference research

A separate CPU research profile permits one request at a time, up to 128 output tokens and a 90-second socket timeout. One real pinned local-model request through the scoped gateway completed with the correct synthetic marker and source citation in 72.7 seconds. Standard defaults remain unchanged. See [measured evidence and reproduction](docs/galahad/26-cpu-research-inference.md).

### Matched real-model evidence study

Eight actual local CPU-model requests completed through the scoped memory gateway. Relevant evidence yielded all four expected codes, with citations in three responses; all four irrelevant controls incorrectly attributed a decoy code to the requested object. This exposes a grounding failure, not a successful learning result. The full suite passed 1,182 tests. See [protocol, responses and reproduction](docs/galahad/27-real-model-evidence-study.md).

### Autonomous research campaigns and grounding checks

A bounded host supervisor now runs campaign cycles, matched trials and outcome-feedback episodes with durable claims, source pins, child timeouts and an explicit stop deadline. It advances automatically without replaying consumed experiments. See [operation and limits](docs/galahad/28-autonomous-research-campaign.md). The optional [synthetic registry guard](docs/galahad/29-registry-grounding.md) checks entity/code/source associations; it is deterministic validation, not model training.

### Overnight outcome — 13 October 2026

The supervisor completed 32 cycles and 65,536 synthetic pipeline episodes. The candidate improved aggregate score but regressed on mixed tasks, so the baseline was retained. Actual process restarts preserved learned preferences in all 16 comparisons. The optional V2 registry guard passed eight fresh real-model cases; full regression passed 1,261 tests. See the [morning report, limits and reproduction](docs/galahad/32-morning-report.md).

### Online configuration selection

The bounded coordinator now selects typed memory policies using prospective training/validation streams and a one-use final comparison, with durable evidence for every trial. A real 11,264-episode run selected a candidate scoring 830/1,024 versus baseline 815/1,024, but rejected it for a mixed-regime regression. Full regression passed 1,280 tests. [Protocol, results and reproduction](docs/galahad/33-online-policy-selection.md).

The [registered research handoff](docs/galahad/34-registered-research-handoff.md) verifies the completed online-policy receipt before automatically running a bounded WorldCore study. Its first real CPU run completed 88 synthetic simulation episodes and found no deployable improvement; no policy or model was promoted.

The [automatic outage diagnosis](docs/galahad/35-outage-search-diagnosis.md) routes a verified WorldCore rejection to a bounded mechanism check. It identifies when the permitted parameter search cannot satisfy the fixed outage/completion contract and stops unmodified retries without relaxing safety gates.

[Sensor freshness enforcement](docs/galahad/36-sensor-freshness.md) prevents duplicate and historical packets from erasing elapsed outage time. The changed controller invalidates earlier current-source study receipts; historical evidence remains preserved, and no outage-recovery improvement is claimed.

The [prospective recovery/adaptation study](docs/galahad/37-recovery-adaptation-study.md) measured 173 online gain updates across 32 validation episodes. It rejected the adaptive candidate for goal/prediction regressions and preserved the unused final-evaluation streams. This demonstrates measured outcome gating, not a general self-improvement claim.

The [adaptation followup diagnostic](docs/galahad/38-adaptation-followup.md) consumes verified rejected studies and automatically reconciles paired objective-error contributions without rerunning plant or final-evaluation episodes.

[Opt-in consistent-dynamics and bounded-planning candidates](docs/galahad/39-consistent-dynamics-candidates.md) preserve historical filter gains during delayed replay and exercise deeper planning through the existing signed recovery boundary. They are development-tested candidates, not promoted improvements.

The [diagnosis-driven dynamics study](docs/galahad/40-dynamics-factorial-study.md) automatically tests registered candidates with matched planning controls, freezes selection, and preserves unused evaluation streams when training gates fail.

The [restartable research supervisor](docs/galahad/41-restartable-research-supervisor.md) connects receipt-verified research stages, resumes completed work without re-execution, and diagnoses identification coverage before requesting another registered experiment.

The [observation-evidence gain candidate](docs/galahad/42-evidence-window-candidate.md) adds timestamp-ordered, prior-regularized sensor learning with optional authorized-recovery evidence forgetting. It remains opt-in pending a prospective matched comparison.

The [registered evidence-window study](docs/galahad/43-evidence-window-study.md) consumes the verified identification diagnostic, audits learning directly from sensor/action evidence, and applies matched frozen/adaptive controls before conditional validation and final evaluation.

The [research outcome memory bridge](docs/galahad/44-research-outcome-memory.md) proposes verified experiment results to existing scoped memory, requires separate host review, and preserves negative findings across process restarts without promoting rejected candidates.

The [research memory planner](docs/galahad/45-research-memory-planning.md) consults independently validated, approved outcome memory to propose the next research step. It recognizes known rejections while preserving study consumption, revocation and independent promotion gates.

The [memory-guided research coordinator](docs/galahad/46-memory-guided-research-coordinator.md) dispatches a fixed diagnostic from a verified negative outcome, journals consumption, and reconciles completed results on restart. It stops for a new registered hypothesis without replaying experiments or promoting rejected candidates.

The [evidence-gated adaptation candidate](docs/galahad/47-evidence-gated-adaptation.md) retains its learned gain until a bounded sensor window supports a material change. An exact prediction-error audit separates state and gain terms; the candidate remains opt-in pending prospective comparison.

The [registered evidence-gated study](docs/galahad/48-evidence-gated-study.md) executed 128 fresh training episodes. Horizon-1 candidates improved on the existing adaptive control but regressed drift goal error against frozen gain; the loop retained the baseline and preserved validation/holdout streams.

The [authenticated actual-action observer](docs/galahad/49-actual-action-observer.md) advances a separate state estimate from confirmed external actions while control remains suspended. Missing action reports invalidate estimates; observation never authorizes recovery.

The [observer training replay](docs/galahad/50-observer-training-reanalysis.md) tests identical observation rules across 128 recorded trajectories. External-supervision predictions improve in every arm/regime, but drift controller-period errors worsen; unconditional substitution remains rejected.

The [phase-aware forecast study](docs/galahad/51-phase-aware-forecast-study.md) preserves controller predictions and selects the actual-action observer during external supervision. Its fixed rule passed all three stages across 512 fresh synthetic episodes, reducing final-holdout mean prediction error by 18.98%. This is a shadow-forecast result; actions were unchanged and no controller or model was promoted.

The [online forecast runtime](docs/galahad/52-online-forecast-runtime.md) connects that rule to an opt-in research wrapper with separately authenticated execution reports. Four development cases preserve original control trajectories and recovery events while matching replay forecasts. Missing execution evidence becomes unknown history; it cannot authorize recovery.
