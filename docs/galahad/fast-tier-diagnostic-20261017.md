# Fast-tier timeout diagnosis and isolated initialization correction

The registered fast tier has outgrown its timing profile. Its manifest was measured with 2,044 discovered tests; the current checkout discovers 2,803, including 2,282 fast tests. Eighty-two newly included fast modules contain 735 tests. The original automatic inclusion rule is unchanged.

The CPU-only baseline profile completed all 2,803 tests in 935.45 suite seconds. Its current fast-test subset alone took **457.31 seconds**, excluding discovery/runner overhead, against the unchanged **180-second** fast deadline. This is diagnostic timing, not a successful verification: the restricted execution environment produced 36 failure entries, two errors and 147 skips. The failures/errors were confined to five modules using macOS sandbox or loopback HTTP fixtures. An exclusive rerun of those modules outside the command sandbox completed **42 tests: 35 passed and seven skipped**. The initial failed profile remains preserved and is not relabeled as passing.

## Dominant fast modules in the baseline profile

| Module | Measured test seconds |
|---|---:|
| scientific compact dev study | 59.03 |
| candidate-v3 study | 53.07 |
| world-model generalization | 47.07 |
| ARC evaluation | 41.73 |
| world model | 15.93 |
| substrate calibration | 14.58 |

These timings explain why correcting ARC alone cannot establish that the whole fast tier fits its cap. No test was removed, skipped by a new rule, reassigned or given a longer fast deadline.

## Isolated code change

`arc_execution.py` and `governed_learning_v20.py` now start an explicit transaction inside their initialization SQL scripts. Their existing connection contexts commit successful schema initialization and roll it back on failure. This groups each schema into one durable transaction rather than individually committing its DDL statements. Durability settings, evaluation case counts, separate per-arm stores and decision rules are unchanged.

New tests inject an authorization failure after the first CREATE and verify rollback preserves existing data; exercise concurrent constructors against one database; and verify reopening retains the complete schema. **All 115 targeted regression tests pass**, covering the new checks, governed learning and the ARC runtime, workflows, evaluations and CLI.

The change lives on `overnight/w0-fast-tier`, separate from the canonical worktree. Neither changed source is in the current gate protected manifest, but both appear in historical retained-study source maps. Code inspection confirms the retained-skill consumer checks those maps against its recorded `frozen_checkout`, which this change does not alter. Historical receipts are preserved. Normal ARC source revision checks still apply; this change does not authorize resuming a recorded study under different source hashes.

## Measurement and coordination

The follow-up comparison uses the same 13 ARC evaluation tests, interpreter and exclusive test lock in baseline / patch / patch / baseline order. All four runs passed. Baseline wall times were 29.086 and 25.826 seconds; patched times were 17.104 and 16.327 seconds. Means were **27.456 seconds baseline versus 16.716 seconds patched**, a **39.12% reduction**. This is a small exploratory timing comparison, not a promotion experiment. Both changed-source hashes remained stable within each run. A separate input snapshot binds both commits plus identical ARC test/evaluation/workflow hashes; it was captured after the first comparison log appeared, and every recorded input hash still matched after completion. No retrospective claim of full pre-registration is made.

One diagnostic retry mistakenly launched after lock acquisition failed. The overlap was recorded in the shared ledger, and neither that retry nor the overlapping fast run is accepted as exclusive timing evidence. The subsequent runner acquires the lock internally before launching any child, returns without execution when busy, and releases only the lock with its own token. The other window launched a clean fast-tier retry; the comparison waits behind it.

Baseline timing, discovery counts and the overlap incident are preserved with hashes in [the evidence summary](evidence/fast-tier-diagnostic-20261017/summary.json). No model calls, pod mutations, signing, retention or activation occurred in this diagnostic work. Registry/trust, the verifier and protected tier manifest are unchanged. The broader integration gate remains blocked; these focused checks are not a substitute for it.

Independent read-only review found no blocking issue in the transaction patch. All 80 protected baseline hashes match in this worktree. The other window’s subsequent clean fast retry exited124 after180.37seconds; integration and inference admission remain blocked. This patch is committed separately for review, not merged into the active orchestrator branch.
