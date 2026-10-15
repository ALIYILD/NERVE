# Learned strategy preferences across process restarts

Earlier tests reopened NERVE's learner and SQLite state within one process. This experiment checks actual process boundaries while preserving the existing host authority, independent evaluator and episode budget semantics.

## Frozen experiment

Seed 21001 supplies 32 synthetic tool tasks for each of four regimes: stationary, abrupt, recurrent and mixed. Four arms use the existing baseline, discounted candidate and two fixed no-learning controls. Each arm/regime runs twice: once in one 32-episode child process, and once in four successive eight-episode child processes. The second mode preserves its memory database, agent database and run identifier across child exits. Each new process issues fresh host capabilities; authentication objects are never serialized.

The parent freezes source hashes and durably claims every child before starting it. Maximum work is 80 child calls / 1,024 pipeline episodes / 2,048 primitive tool invocations, with a 60-second timeout per child and no retries. The two approved synthetic strategy memories are created only for the initial chunk. Subsequent chunks reject missing, revoked or corrupt source state rather than recreating or reapproving it.

For each of 16 regime/arm comparisons, acceptance requires exact equality of task hashes, selected strategies, boolean outcomes, final feedback count and consumed episode budget between uninterrupted and restarted execution. Adaptive arms must have 32 observations and 32 consumed episodes; fixed controls write no feedback. The host recomputes fixture correctness independently of claimed scores.

This tests storage and execution continuity of learned strategy preferences. It does not show that the base model trained itself, that one policy dominates all regimes, or that scientific or clinical decisions are validated. Each arm is isolated, with a fresh store; only successive chunks within that arm share learned state.

## Results

Completed **80/80 child calls and 1,024/1,024 pipeline episodes**. All **16/16 regime/arm comparisons were exactly equivalent** across uninterrupted and restarted execution, including strategy choices, outcomes, task hashes, feedback counts and consumed budgets. Adaptive histories accumulated through all four restarted chunks rather than resetting. [Full evidence](evidence/restart-learning-v1.json).

Measured child wall time totaled 25.515 seconds. No model calls, network calls or clinical data were involved. Source hashes and SQLite/export consistency were rechecked after execution. The 11 focused tests include real spawned processes, revocation/corruption rejection, replay prevention, false-reward rejection and protection of existing database/symlink paths. Final full regression: **1,261 tests passed**, zero failures/errors, 65.388 seconds.

This result establishes restart equivalence for the fixed synthetic fixture. It is not a policy promotion: on this seed the candidate scored 18/32 in the mixed regime against baseline 22/32, despite improving abrupt and recurrent scores. Retain the separate no-regression gate.

## Reproduction

```sh
PYTHONPATH=src .venv/bin/python scripts/verify_restart_learning.py \
  --directory /private/tmp/nerve-restart-learning-v1
```

Use a new empty study directory. Its `study.sqlite` stores durable parent claims, `report.json` is the atomic exported report, and subdirectories retain the actual per-arm memory/agent databases. Preserve failures; a consumed study is not resumed or replayed. This experiment reuses the existing learning and automatic execution modules without changing the already-running overnight campaign.
