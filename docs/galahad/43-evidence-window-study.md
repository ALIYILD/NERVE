# Registered evidence-window comparison

The new study consumes the completed restartable supervisor's identification diagnostic. It verifies the complete four-node predecessor graph, source pins, report digests and SQLite journals before any candidate episode is dispatched. The existing supervisor generation remains immutable; this registered continuation is invoked by `scripts/run_evidence_window_study.py`, not automatically added to the old graph catalogue.

## Frozen candidate set and gates

Eight arms run on paired stationary/drift environments: frozen gain at horizons 1/3; existing adaptive consistent-filter gain at horizons 1/3; evidence-window retain and forget policies at horizons 1/3. Candidate window=16 and prior weight=4 are fixed. No prior/window sweep occurs.

Training seeds 38001–38008 run all eight arms: 128 episodes. Each evidence-window candidate must pass unchanged recovery gates against the original frozen horizon-1 baseline, a frozen control with matched planning depth, and the existing adaptive consistent-filter control with matched depth. Every comparison requires zero envelope violations, no loss of active steps, no increase in external commands, goal error or prediction error in either regime (tolerance 1e-12), actual learning updates, and summed regime goal gain >1e-5.

Training selects the eligible candidate with greatest summed goal gain against frozen horizon 1; lexical arm name breaks ties. Selection is durably frozen before validation seeds 39001–39008. Only that candidate and its unique controls proceed. Final seeds 40001–40016 are used once only after validation passes. Failure stops the study without trying a runner-up. Maximum: 320 episodes / 25,600 physical steps; a horizon-1 winner uses fewer distinct controls. Child limits are 30 seconds, with a 1,200-second episode-execution budget excluding initial provenance/setup and final reconciliation.

All claims precede execution. Failed trials/studies remain consumed, and the shared dataset identity ignores arm/protocol renaming. Source changes fail closed. Operator replacement/deletion of ledgers is outside the local replay protection. A passing study returns only a review candidate; no deployment or automatic promotion occurs.

## Learning evidence

Each candidate episode records its fitting window, processed transition IDs, gain, variance statistic and recovery-reset counter before every action. The validator reconstructs those values from noisy sensor velocities, recorded actions and authorized recovery events. It also checks each step's update count against the reconstructed transition-consumption count. Ground-truth plant values are used only for the existing trace's physical/error checks, never to reconstruct fitting evidence.

The worker is restricted to a dedicated single-threaded child because it temporarily binds the registered runtime and planner instrumentation inside that process. Every exit restores those bindings. Actual deeper-planner iterator yields and episode wall time are recorded. These are additional enumeration work and local execution timing, not total cost, equal-compute controls or representative speedup evidence.

## Reproduce

```sh
cd /Users/aliyildirim/nerve-galahad
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_evidence_window*.py' -v
PYTHONPATH=src .venv/bin/python scripts/run_evidence_window_study.py \
  --directory /private/tmp/nerve-evidence-window-study-v1 \
  --claims /private/tmp/nerve-evidence-window-study-claims.sqlite \
  --supervisor-directory /private/tmp/nerve-research-supervisor-v1
```

Consumed runs refuse restart under a renamed output using the same shared claims. Read-only receipt validation is available as `evidence_window_study.validate_receipt(directory, claims, supervisor_directory)`.

## Measured result

**Retain baseline.** All 128 training episodes / 10,240 physical steps completed, with 1,398 recorded gain updates and zero recorded envelope violations. No candidate passed every gate. The frozen selection is empty; **no validation or holdout episodes ran**. Independent receipt review confirmed the same result without rerunning episodes.

Eight paired seeds per regime; mean absolute errors:

| Arm | Stationary goal | Drift goal | Stationary prediction | Drift prediction |
| --- | ---: | ---: | ---: | ---: |
| frozen_h1 | 0.153757 | 0.158900 | 0.009733 | 0.029406 |
| frozen_h3 | 0.118259 | 0.180309 | 0.008981 | 0.042521 |
| adaptive_consistent_h1 | 0.154605 | 0.156555 | 0.009875 | 0.023208 |
| adaptive_consistent_h3 | 0.134852 | 0.185855 | 0.011582 | 0.034264 |
| evidence_retain_h1 | 0.153959 | 0.152645 | 0.010145 | 0.025365 |
| evidence_retain_h3 | 0.135214 | 0.188870 | 0.011820 | 0.038486 |
| evidence_forget_h1 | 0.154568 | 0.154368 | 0.010210 | 0.027349 |
| evidence_forget_h3 | 0.135132 | 0.190277 | 0.011803 | 0.038203 |

The retain-window horizon-1 candidate improved summed regime goal error by 0.006052 against frozen horizon 1 and by 0.004555 against the matched existing adaptive control. It nevertheless regressed stationary goal and prediction error against frozen control, and prediction error in both regimes against the adaptive control. Horizon-3 candidates regressed drift goal error. Aggregate gains therefore do not establish an eligible learning improvement.

Measured work (16 episodes per arm; timing excludes child startup/coordinator work):

| Arm | Total episode seconds | Additional horizon-3 sequences |
| --- | ---: | ---: |
| frozen_h1 | 1.100380 | 0 |
| frozen_h3 | 1.325796 | 28674 |
| adaptive_consistent_h1 | 1.097582 | 0 |
| adaptive_consistent_h3 | 1.350814 | 28674 |
| evidence_retain_h1 | 1.134719 | 0 |
| evidence_retain_h3 | 1.356807 | 28674 |
| evidence_forget_h1 | 1.181341 | 0 |
| evidence_forget_h3 | 1.544882 | 28674 |

These local CPU measurements establish neither representative speedup nor financial savings. The full test suite started after the experiment completed.

- [Full compressed evidence](evidence/evidence-window-study-v1.json.gz)
- [Frozen protocol, comparisons, work, environment and artifact hash](evidence/evidence-window-study-v1-summary.json)

A further candidate requires a new preregistered hypothesis. The unused validation and final streams must remain separate from diagnostic tuning, and this rejection does not justify relaxing the existing gates. No candidate was promoted, no neural weights were trained, and no clinical deployment occurred.

Final verification: **1,429 repository tests passed in 176.725 seconds**, with zero failures/errors. The targeted evidence-window suite passed all 24 tests before prospective execution. Independent postrun review reconciled source pins, the supervisor predecessor, 128 complete training journal rows, the empty frozen selection and the shared claim; no episodes were rerun. [Validation record](evidence/evidence-window-study-validation.json).
