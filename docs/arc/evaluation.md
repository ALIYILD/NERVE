# ARC offline evaluation and bounded candidates

`nerve_awim.arc_evaluation` extends the workflow store with `arc_evaluation_runs`, `arc_improvement_development`, and `arc_improvement_candidates`. It invokes `arc_workflows.run_workflow` through the existing GovernedLearning dispatcher. It does not start a scheduler, launch a provider, or activate a release.

The frozen `smoke-v1.json` contains 60 synthetic cases: 30 development, 15 validation, and 15 test. Twenty scenario families have three within-family variations each; family names and composition rules do not cross splits. Validation and test deliberately hold out combinations of shared primitives. They are not 60 independent clinical cases, and the public fixtures are not secret from developers. The manifest and pinned SHA-256 reject changed cases. Thresholds and candidate count were frozen before arm comparisons. A fresh independently reviewed holdout is required for a subsequent promotion decision.

The three arms share inputs, tool implementations, budgets, deterministic selection and local stores:

- Baseline calls the pre-existing GovernedLearning dispatcher and uses its transport result as completion, without ARC decision enforcement.
- Structured creates and authorizes a decision, with an explicitly labelled transport-only verification ablation.
- Full uses structured authorization and independent deterministic semantic checks.

Baseline and structured require the explicit host-only `offline_evaluation=True` parameter. Each task and arm gets a separate disposable database. This prevents cross-arm memory contamination, and generated decision/outcome identifiers are retained in report rows. Workflows never execute supplied Python source, contact a clinical API, or submit a referral.

The report records action correctness, verified objectives, unsupported success, policy violations, correct abstention, restart recovery, within-family wording stability, task-level action sensitivity, latency and zero paid cost. Exact single-fact paired behavior has separate workflow tests. Wilson intervals are descriptive only because variants within a family are correlated. No confidence interval here supports a clinical or population-level claim.

Candidate generation receives actual failed development outcomes only; correct clarification or review abstentions do not count as failures. With no failure evidence it returns without generating candidates. The first implementation supports three inert task strategies: default, conservative, and evidence-first. All candidates use full verification against the same full-verification default strategy. Default and evidence-first tie and are rejected for no gain; the implementation ablation is never used as candidate improvement evidence. Definitions bind the base revision, dataset, hypothesis, observed failure IDs and exact changed configuration. No candidate code, tool, evaluator, policy, credential or budget input is accepted. Validation may reject candidates; at most the first passing candidate is selected for the single release comparison. The deliberately conservative strategy must fail when it loses valid objective completions. Candidate execution is a trusted local registered-handler harness, not an arbitrary-code sandbox.

Claims are written before evaluation. An exclusive file lock prevents overlapping runners. A crash consumes a candidate slot; resume marks it interrupted and never replays that slot. A release comparison consumes the locked test set before the first test execution. A completed rerun returns the stored receipt without executing tasks. An interrupted release or changed evaluator cannot reuse the consumed holdout. Copying or deleting the local database defeats this local protocol; this is not a remotely attested experiment system.

Reproduce using a disposable store (Python module API; the main CLI exposes the same functions):

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_arc_evaluation.py' -v
PYTHONPATH=src python3 -c 'from nerve_awim.arc_evaluation import run_candidates; print(run_candidates("/private/tmp/nerve-arc-eval.sqlite3"))'
PYTHONPATH=src python3 -c 'from nerve_awim.arc_evaluation import run_benchmark; print(run_benchmark("/private/tmp/nerve-arc-eval.sqlite3", report_path="/private/tmp/nerve-arc-report.json")["metrics"])'
```

No promotion, production integration, patient-data access, paid inference, or model weight update is performed. The experimental release default remains off regardless of these synthetic results.

The committed smoke and candidate receipts were last regenerated in the isolated ARC handoff worktree against source revision `4e5fb0e64f7e6c2d8bbfbb365ea3e0082586c988711f6283cc980b23961df5b0`. This rerun reproduced the existing exposed suite for integration diagnostics; it did not provide a fresh holdout or select an improvement candidate.
