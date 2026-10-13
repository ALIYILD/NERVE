# Prospective recovery and online-gain comparison

This registered coordinator measures whether the repaired controller's online dynamics learning helps, rather than inferring improvement from successful recovery. It executes a recovery preflight, then paired validation episodes, and opens final evaluation only if the frozen validation gates pass. The run is terminal; no background experiment remains active.

The two arms differ only in dynamics-gain learning rate: frozen gain (`0`) versus online gain (`0.08`). Both use the existing lagged filter, adaptive calibration, risk policy, explicit recovery observations and signed supervisory approval. Learning occurs within an episode and survives its recovery reseed; it does not persist across seeds or train language-model weights.

## Protocol

Each episode has 80 physical simulation steps. Both arms receive identical pre-generated noise/dropout schedules for each seed, including a forced 15-step sensor blackout. Only noisy observations reach the controller. Predictions are formed before the physical step and scored against the subsequent velocity. Every step contributes goal and prediction error, including explicit external zero-input commands when the controller is unavailable. Those commands are simulated interventions, not certified safe actions or controller availability.

This is a new recovery experiment with one-step sensor delivery, distinct from the earlier two-step-delivery WorldCore study. Stationary plant gain is 0.27; drift gain changes every 20 steps through 0.27, 0.48, 0.15 and 0.40. Validation uses seeds 33001–33008 across both regimes and arms (32 episodes). Final evaluation reserves seeds 34001–34016 (64 more episodes), giving a maximum of 96 episodes / 7,680 steps. No parameter tuning occurs within this fixed-hypothesis study.

Every regime must have zero candidate envelope violations, nondecreasing controller-active steps, and nonincreasing external commands, goal error and prediction error. Numerical tolerance is 1e-12. The sum of regime goal-error improvements must exceed 1e-5, and actual online updates must be exercised. Final evaluation uses the same gates. Failure is a valid result and does not authorize promotion.

Each episode has a durable pre-execution claim and a 30-second child limit. A shared SQLite dataset claim blocks repeats under renamed output directories using that ledger. Deleting/replacing operator-controlled ledgers is not prevented. Trace validation, including under optimized Python, recomputes disturbances, physics, forecasts, errors and summaries; receipt verification reconciles exports, preflight, journal, decisions and shared claims without rerunning the plant.

## Measured validation result

**Retain baseline.** All 32 episodes / 2,560 physical steps completed. The adaptive arm made **173 actual gain updates**. Each arm averaged 66.75 controller-active steps and 13.25 externally commanded steps per episode, with one successful supervised recovery and zero observed envelope violations.

| Regime and metric | Frozen gain | Online gain |
| --- | ---: | ---: |
| Stationary mean absolute goal error | 0.144736 | 0.144621 |
| Stationary mean absolute prediction error | 0.006797 | 0.007151 |
| Drift mean absolute goal error | 0.158252 | 0.166723 |
| Drift mean absolute prediction error | 0.028614 | 0.026355 |

Prediction improved under drift while goal tracking worsened; stationary prediction also regressed. The sum of regime goal gains was **−0.008357**. Validation therefore failed and **no final-evaluation seed was executed**. These are descriptive results from eight paired seeds per regime, not a statistical demonstration of broad competence. Full paired deltas remain in the report.

The preflight uses an explicitly mocked identity provider. Actual controller execution and local signed-approval checking run, but the study is not a production authentication or physical-safety evaluation. Per-episode approval ledgers are temporary; the study's claims and measured traces are durably retained. No latency, monetary-cost, GPU or real Galahad advantage is claimed.

- [Complete compressed trace report](evidence/recovery-adaptation-v1.json.gz)
- [Protocol, paired deltas, summaries and artifact hashes](evidence/recovery-adaptation-v1-summary.json)

## Engineering verification

The full repository suite passed **1,357 tests in 110.799 seconds**, with zero failures or errors; the two new modules contributed 18 passing tests. Independent review reconciled the current source pins, preflight, shared claim, journal and archived report without rerunning episodes. It confirmed the rejection and absence of final-evaluation calls. [Validation record](evidence/recovery-adaptation-validation.json).

## Reproduction

```sh
cd /Users/aliyildirim/nerve-galahad
.venv/bin/python scripts/verify_galahad.py baseline
PYTHONPATH=src .venv/bin/python scripts/run_recovery_adaptation.py \
  --directory /private/tmp/nerve-recovery-adaptation-replication \
  --claims /private/tmp/nerve-recovery-adaptation-replication-claims.sqlite
```

A separate ledger here explicitly denotes replication of published validation data, not new evidence. The original authoritative claim ledger is `/private/tmp/nerve-recovery-adaptation-claims.sqlite`; it refuses reuse of the consumed dataset even if the output directory is renamed. Independent receipt verification uses `recovery_adaptation_study.validate_receipt(directory, claim_database)`.

The next research issue is objective alignment: lower prediction error did not produce better control. Any followup should prospectively test that mismatch with a frozen candidate schema and fresh evaluation contract. The unused final streams must not be described as passed or repeatedly probed while tuning.
