# Restartable research coordinator and identification diagnostic

`research_supervisor.py` connects four registered stages: recovery study → objective-mismatch diagnosis → dynamics candidate study → identification-coverage diagnosis. It dispatches a missing eligible stage, validates its receipt and continues automatically. Existing complete stages are adopted only after their source pins, provenance, journals and shared claims reconcile. The public entry point is `scripts/run_research_supervisor.py`.

The graph has at most four nodes. It stops for independent review if a study returns a successful candidate, or requests a new registered experiment when its research catalogue is exhausted. A rejected experiment is a completed research result, not permission to rerun it. `goal_achieved` and deployment remain false. This does not constitute an indefinitely self-extending experiment generator or general self-improving intelligence.

## Restart semantics

The coordinator requires explicit stage directories and shared claim-ledger paths. It never silently creates replacement claim ledgers by changing only its own output directory. Its protocol binds these paths, the registered graph and all relevant source hashes. A nonblocking OS file lock prevents concurrent runners in the same coordinator directory.

Each node is durably claimed before dispatch. On restart, a claimed node is reconciled only if a complete valid receipt exists. Missing/partial results become `failed_consumed`, and an explicit failure is never dispatched again. Completed receipts must retain their recorded digest. Corrupt status values, changed paths/source pins and modified completed artifacts fail closed. A source change requires a separately reviewed coordinator generation; it does not authorize replaying the old datasets.

An existing valid external receipt can be adopted even if another coordinator originally produced it. The original dataset ledgers still enforce consumption across directory names. Operator deletion/replacement of journals or ledgers is outside this local research protection. This is a local CPU coordinator using Unix file locks, not a remotely authenticated service or distributed scheduler.

## Identification diagnostic

The final subloop consumes the complete factorial training roster, verifies every trace, and groups all steps into 48 fixed regime/arm/20-step windows with separate controller-phase strata. It counts sensor presence, acceptance/routes, action source, online updates and zero-update steps, and reports gain, goal and prediction errors. True plant gain is used only for retrospective scoring; it is never fed back to control or learning.

Zero updates do not necessarily mean a stale or defective estimator: frozen arms intentionally do not learn, and adaptive arms require usable adjacent sensor pairs with a nonzero action. Phase strata describe associations and do not establish the cause of a regression. Validation and final-evaluation outcomes are excluded from this diagnostic.

## Reproduction and resume

```sh
cd /Users/aliyildirim/nerve-galahad
PYTHONPATH=src .venv/bin/python scripts/run_research_supervisor.py \
  --directory /private/tmp/nerve-research-supervisor-v1 \
  --recovery /private/tmp/nerve-recovery-adaptation-v1 \
  --recovery-claims /private/tmp/nerve-recovery-adaptation-claims.sqlite \
  --diagnosis /private/tmp/nerve-adaptation-followup-reviewed \
  --diagnosis-claims /private/tmp/nerve-adaptation-followup-reviewed-claims.sqlite \
  --factorial /private/tmp/nerve-dynamics-factorial-v1 \
  --factorial-claims /private/tmp/nerve-dynamics-factorial-claims.sqlite
```

The identical command resumes by verification and does not rerun completed stages. For a fresh execution, pass missing registered stage directories and the intended explicit shared ledgers; consumed datasets remain refused. The supervisor does not modify existing gates or generate unrestricted commands/source code.

## Actual run and restart evidence

The real supervisor adopted three verified completed stages and executed the missing identification diagnostic. It finished all four nodes, returned `new_registered_experiment_required`, and dispatched **zero new plant episodes**. The diagnostic exhaustively accounted for 96 training episodes / 7,680 steps: 953 gain updates, 6,727 zero-update steps, 6,396 controller steps and 1,284 externally commanded steps.

In the drift regime's steps 40–59, the four adaptive arms had only 8–10 fitting updates across eight episodes each. Mean absolute gain errors were 0.210098–0.229327, versus 0.12 for both frozen controls. This identifies an observation-coverage and retained-dynamics question; it is not causal proof that resetting or learning faster would improve control. Ground truth was used only in this retrospective diagnostic.

A second invocation in a **fresh Python process** completed by reconciliation. SHA-256 snapshots of all nine tracked predecessor reports, study journals, claim ledgers and the diagnostic report were unchanged. No completed experiment was rerun. This demonstrates ordinary process restart with durable completed evidence; it is not a live-kill test of every possible interruption point. Unit tests separately exercise interrupted claims and partial-receipt rejection.

- [Coordinator report and source pins](evidence/research-supervisor-v1.json)
- [Identification diagnostic with all windows and phase strata](evidence/identification-diagnostic-v1.json)
- [Fresh-process resume hashes](evidence/research-supervisor-resume.json)

Final verification: **1,405 repository tests passed in 179.330 seconds**, with zero failures/errors. Fourteen new targeted tests cover diagnostic arithmetic and exclusion of later outcomes, node claims, adoption, fresh resume, corruption, partial receipts, process locks and review stops. Independent review validated the intended predecessor chain without rerunning experiments. [Validation record](evidence/research-supervisor-validation.json).
