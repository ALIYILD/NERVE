# Diagnosis-driven dynamics selection study

The executable coordinator in `dynamics_factorial_study.py` consumes the verified adaptation diagnosis and automatically runs the registered candidate-selection subloops. The CLI requires both predecessor receipt paths and their shared claim ledgers. It cannot substitute unverified agent text for the prerequisite diagnosis.

## Frozen protocol

Six arms are registered before execution: frozen gain at horizons 1 and 3; adaptive gain with the legacy filter at horizons 1 and 3; adaptive gain with consistent filter propagation at horizons 1 and 3. Frozen consistent-filter variants are omitted only after complete smoke-episode equivalence tests at both depths. This is a controlled synthetic comparison, not a statistical factorial effect estimate.

Training seeds 35001–35008 run all six arms in stationary and drifting regimes (96 episodes). Each adaptive candidate must pass the unchanged recovery-study gates against both the original frozen horizon-1 baseline and a frozen baseline of its own planning depth. In each regime, envelope violations must be zero, active steps cannot fall, and external commands, goal error and prediction error cannot rise (tolerance 1e-12). Each comparison requires summed regime goal gain greater than 1e-5 and actual online updates. Additional search alone therefore cannot satisfy the matched-learning comparison.

The eligible candidate with highest summed goal gain against the primary baseline wins, with lexical arm-name tie breaking. Its identity and all training comparisons are persisted before validation. Validation seeds 36001–36008 run only that candidate and its unique controls (at most 48 episodes). Final seeds 37001–37016 run only after validation passes (at most 96 episodes). No runner-up is tried after rejection and no parameter search occurs beyond the frozen six arms. Maximum budget: 240 episodes / 19,200 physical steps. No improvement is a valid terminal result.

Each child gets at most 30 seconds and the remaining portion of a 900-second episode-execution budget. Initial provenance/setup and final reconciliation lie outside that episode budget. Every trial is claimed before execution; a timeout, invalid trace or source change consumes the study. Shared claims key the seed splits, scenarios and plant independently of candidate/protocol labels. Operator deletion or replacement of ledgers remains outside this replay protection.

The worker reuses the original episode implementation and opt-in runtime through restored process-local bindings inside a dedicated single-threaded child. Trace arithmetic, signed synthetic recovery, candidate identity, observed duration and actual deeper-planner iterator yields are validated. Sequence counts describe additional horizon-3 enumeration, excluding the shared first-step chooser and filter computation. Episode wall time excludes child startup and coordinator validation. Neither is a claim of total financial cost or compute-equivalent superiority.

The coordinator preserves the baseline unless final gates pass, and even then returns only `candidate_for_review`. It does not promote models, train neural weights, persist gains across episodes, deploy clinical decisions or certify physical safety.

## Reproduction

```sh
cd /Users/aliyildirim/nerve-galahad
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_dynamics_factorial*.py' -v
PYTHONPATH=src .venv/bin/python scripts/run_dynamics_factorial.py \
  --directory /private/tmp/nerve-dynamics-factorial-v1 \
  --claims /private/tmp/nerve-dynamics-factorial-claims.sqlite \
  --diagnosis /private/tmp/nerve-adaptation-followup-reviewed \
  --predecessor /private/tmp/nerve-recovery-adaptation-v1 \
  --study-claims /private/tmp/nerve-recovery-adaptation-claims.sqlite \
  --followup-claims /private/tmp/nerve-adaptation-followup-reviewed-claims.sqlite
```

Existing run directories and consumed datasets are refused. Reanalysis should use receipt validation; a separately labelled replication ledger represents reuse of published data, not fresh independent evidence.

## Measured result

**Retain baseline.** The real run completed all 96 training episodes / 7,680 physical steps and recorded 953 online gain updates, zero envelope violations and one successful supervised recovery in every episode. No candidate passed the training comparisons, so **zero validation or final-evaluation episodes ran**. These unused streams must not be treated as passed or probed during tuning.

Mean absolute goal error, eight paired seeds per regime:

| Arm | Stationary | Drift |
| --- | ---: | ---: |
| Frozen, horizon 1 | 0.167405 | 0.178247 |
| Frozen, horizon 3 | 0.145710 | 0.163954 |
| Adaptive legacy, horizon 1 | 0.167472 | 0.185570 |
| Adaptive legacy, horizon 3 | 0.145872 | 0.171468 |
| Adaptive consistent, horizon 1 | 0.164138 | 0.179382 |
| Adaptive consistent, horizon 3 | 0.145872 | 0.167766 |

The horizon-3 consistent candidate reduced summed goal error by 0.032013 against the original one-step baseline, but its prediction errors regressed. Against the matched frozen horizon-3 control, its summed goal error was worse by 0.003974. Consequently, improved planning cannot be reported as a demonstrated learning gain. The consistent filter improved some descriptive comparisons against the adaptive legacy filter; it did not establish an eligible candidate.

Each arm had 16 training episodes and averaged 66.625 active steps plus 13.375 explicitly externally commanded steps. Each horizon-3 arm enumerated 28,782 additional planning sequences. Observed total episode times were 0.381s frozen h1, 0.446s frozen h3, 0.378s adaptive legacy h1, 0.449s adaptive legacy h3, 0.389s adaptive consistent h1, and 0.451s adaptive consistent h3. These short local CPU timings are descriptive and exclude process startup/coordinator work; they establish no representative speedup or monetary saving. The full regression suite started after the study ended.

- [Full compressed trace evidence](evidence/dynamics-factorial-v1.json.gz)
- [Protocol, comparisons, measured work, environment and raw artifact hash](evidence/dynamics-factorial-v1-summary.json)

The next research task is to explain why noisy within-episode gain updates fail to beat the matched frozen controller, using consumed training traces for diagnosis. Any subsequent candidate must be prospectively registered; this result does not authorize changing the gates or repeatedly tuning on untouched evaluation streams.

Final engineering verification: **1,391 repository tests passed in 90.714 seconds**, with zero failures/errors. Independent receipt review reconciled all 96 complete training rows, the frozen selection, current source pins and both predecessor receipts; no episodes were rerun. [Validation record](evidence/dynamics-factorial-validation.json).
