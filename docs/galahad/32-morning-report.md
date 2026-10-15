# Morning report — 13 October 2026

The autonomous overnight campaign finished before its 07:00 London deadline. It executed all 32 cycles, 2,048 child trials and 65,536 synthetic pipeline episodes. The final process exited; it is no longer running. The code and results are local on `feature/galahad-persistent-memory`; no PR, push, deployment or clinical promotion occurred.

## What works and what remains incomplete

NERVE can autonomously execute registered synthetic tasks, independently judge their actual outputs, update scoped approved strategy preferences, preserve those preferences and consumed budgets through real process restarts, and reject a candidate that violates its no-regression gate. These are executable research paths. The overnight experiment deliberately resets learners between matched trials; the separate restart study demonstrates persistence across chunks of one stream.

The local language model still produces unsupported answers. An optional narrow registry guard now blocks the tested wrong-object answers and retains supported responses. Its repair is engineered deterministic validation, not a learned model-weight change. This does not establish a generally self-training model, open-ended scientific discovery or completed Galahad/Clinical OS integration.

## Measured outcomes

| Check | Actual result | Interpretation |
| --- | --- | --- |
| Full repository regression | 1,261 passed; zero failures/errors; 65.388 seconds | Includes new orchestration, grounding and restart tests |
| Overnight campaign | 32/32 cycles, 2,048/2,048 child trials, 65,536 episodes | Bounded orchestration completed without replaying failed claims |
| Verified feedback | 32,768 observations | Adaptive arms scored actual output before feedback; fixed arms did not learn |
| Existing adaptive baseline | 12,604/16,384 = 76.93% | Same tasks and primitive tool capabilities as candidate |
| Fixed discount candidate | 13,750/16,384 = 83.92% | Aggregate +6.99 points, but mixed-regime loss fails gate |
| Fixed lower / fixed trim controls | 8,127/16,384 / 8,257/16,384 | No-feedback controls, not language-model baselines |
| Candidate decision | Retain baseline | No default configuration was changed |
| Real-model guard V1 | Raw 2/8; guarded 6/8 strict contract matches | Four bad answers blocked; two supported comma-form answers unnecessarily rejected |
| Fresh real-model guard V2 | Raw 3/8; guarded 8/8 strict contract matches | Four controls abstained, four supported answers retained; one citation supplied |
| Cross-process learning | 16/16 exact equivalence checks; 80 child calls; 1,024 episodes | Strategies, outcomes, task hashes, feedback and budgets survived restarts |

The overnight candidate's scenario deltas were stationary 0/4,096, abrupt +192/4,096, recurrent +1,156/4,096, and mixed **−202/4,096** (−4.93 percentage points). Six individual cycles met the review gate and 26 did not; no cycle changed the frozen policy. Aggregate gain alone did not override the negative result.

## Methodology and evidence

The campaign preregistered seeds 10000–10127, four regimes, four fixed arms and 32 episodes per trial. Each episode executed two registered transformations. No model calls or generated source execution occurred in this campaign. Its recorded child wall times sum to 1,342.031 seconds; scheduled intervals and report I/O are additional. Those measurements do not establish model-inference speed, energy savings or monetary cost. This is public synthetic replication, not a sealed external holdout.

The two real-model studies used the pinned local `qwen2.5-coder:1.5b` CPU model, eight calls each, a fixed 128-output-token budget and 90-second socket timeout, with no retries. V2 changed the allowed punctuation form and used fresh cases. Its 8/8 result is a small, narrowly defined system test, not a general accuracy estimate or a same-case V1/V2 model comparison.

The restart experiment used seed 21001. Each of 16 regime/arm combinations compared one 32-episode subprocess with four eight-episode subprocesses sharing that arm's actual SQLite state. All 16 matched exactly; child wall times sum to 25.515 seconds. No model calls were involved.

Source hashes and SQLite/export consistency were verified after all three studies. Full campaign evidence is compressed losslessly; hashes are in its summary. Nothing was rescored to turn a failure into a pass.

- [Overnight summary and hashes](evidence/overnight-campaign-v1-summary.json), [complete campaign archive](evidence/overnight-campaign-v1.json.gz)
- [V1 raw/guarded model responses](evidence/grounded-registry-v1.json), [V2 raw/guarded model responses](evidence/grounded-registry-v2.json)
- [Restart evidence](evidence/restart-learning-v1.json), [final regression metadata](evidence/loop-cycle2-validation.json)
- [Historical launch and first-cycle snapshot](evidence/overnight-launch-v1.json)

The live campaign ledger and uncompressed final report remain at `/Users/aliyildirim/nerve-research-runs/overnight-20261013/`. Restart per-arm databases remain at `/private/tmp/nerve-restart-learning-v1/`; the report is archived in Git. Research data are entirely synthetic.

## Code, reuse and review

The coordinator reuses `AutomaticLearningRun`, `VerifiedOutcomeLearning`, `OutcomeMemoryRanker`, `DemoAgentBridge` and the existing online study. The guards reuse authoritative scoped gateway retrieval and local inference. New executable files are `memory_gateway/research_campaign.py`, `grounding.py`, `grounding_v2.py`, `restart_learning_study.py`, and their CLI scripts and tests. `scripts/verify_galahad.py` includes the new tests in CPU/security verification. README and the Galahad reports link the evidence.

Independent reviewers and coordinator checks found and repaired derivative lock-path collisions, unsafe fixed temporary export paths, stale deadline allowances and pre-existing study-directory writes. Tests cover consumed claims, source drift, timeouts, revocation, wrong-entity answers and false reward evidence. Model outputs cannot override these checks. Local operator-owned files and locks are not independently sealed custody or production remote authentication.

The campaign source checkpoint is `3970f2e6e2f20d9f1e04f5b8b22ccf1a24ac4dd5`; launch evidence is committed at `9651e44590670167bd40bc6e8b6aa3c62514b4a3`. `git rev-parse HEAD` identifies the subsequent repair/evidence checkpoint. Earlier raw evidence and guard V1 remain unchanged.

## Independent reproduction

```sh
cd /Users/aliyildirim/nerve-galahad
.venv/bin/python scripts/verify_galahad.py baseline
PYTHONPATH=src .venv/bin/python scripts/verify_restart_learning.py --directory /private/tmp/nerve-restart-reproduction
PYTHONPATH=src .venv/bin/python scripts/benchmark_grounded_registry_v2.py --database /private/tmp/nerve-grounding-reproduction.sqlite --run-id grounding-reproduction --output /private/tmp/nerve-grounding-reproduction.json --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
PYTHONPATH=src .venv/bin/python scripts/run_research_campaign.py --database /private/tmp/nerve-campaign-reproduction.sqlite --output /private/tmp/nerve-campaign-reproduction.json --run-id campaign-reproduction --deadline-utc 2026-10-14T06:00:00Z --stop-file /private/tmp/nerve-campaign-reproduction.STOP --cycles 32 --seeds-per-cycle 4 --first-seed 10000 --trial-timeout 60 --cycle-interval 0
```

Use unused output paths and a future UTC deadline. Repeating the published seeds is replication, not fresh holdout evidence. The model command needs the pinned installation and local loopback permission; full tests use temporary local HTTP servers and processes. Runtime scheduling can change measured durations.

## Remaining gates

Galahad GPU compatibility, commercial licence rights, real KV deposit/restore and restart restoration remain unverified. No model weights were trained. The guarded API remains opt-in and synthetic-only; conflicts outside retrieved records are not detected. Broad scientific task validation, production authentication/operations, patient-data governance and clinical deployment remain incomplete. The overnight outcome supports bounded research automation and persistent strategy learning, not a claim that the whole original plan is finished.
