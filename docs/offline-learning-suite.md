# Offline learning and retention suite

Run `PYTHONPATH=src python scripts/offline_learning_suite.py`. No credentials,
network calls, generated-code execution or model downloads are needed. CI runs
the suite in addition to the existing unit tests.

Five task families: numeric sorting, stable deduplication, JSON extraction,
direct module-level Python function extraction and CSV parsing. Expected outputs
are explicitly authored fixture values, checked against deterministic standard
library predictors. Splits contain four training, eight selection, five retained
regression and six final tasks. CSV appears only in final testing. It is already
implemented in the capable predictor, so success is not acquisition of a new
skill. The fixture is public and small, not a private realistic benchmark.

`run_improvement_loop(..., regression=episodes)` now optionally checks each
selection-improving candidate on a separate retained suite against the original
baseline. Any paired loss rejects the candidate before replacing the incumbent.
When an incumbent exists, a second retained-suite comparison also protects its
acquired capabilities. Matching the original baseline is not sufficient if the
candidate forgets something learned in an earlier iteration. The worst-case
budget includes both comparisons. Each history entry reports both results.
Regression tasks participate in exact-overlap checks and worst-case prediction
budget preflight. They are also included in the exclusion prefix for final
testing. The proposer sees aggregate retention results, so these tasks are
development feedback, never final holdout evidence. Existing callers that omit
the retained suite behave as before. Neither this check nor its reports grant
deployment or memory approval.

A failed final test now clears `selected_lesson`. `selection_winner` retains the
pre-final candidate for audit only; it must not be treated as approved or ready
for use. A final tie also clears selection. This is report-level rejection, not
a production rollback: no deployment or ledger approval happens in this loop.

Two ten-proposal deterministic scenarios are exercised:

- Capable control: correct baseline and candidate; no manufactured improvement.
- Controlled repair: an intentionally broken sorting baseline is repaired by a
  prewritten strategy. A first candidate introduces an explicit retained-Python
  regression and is rejected; the next preserves retained behavior and is kept.
  Any final gain in this scenario is a designed fixture outcome, not AI learning.

Exact duplicate proposals skip evaluation. Final capable-control scores are also
reported per family. This is coverage for loop behavior, task separation and
retention, not a model-quality result, statistical study or proof of unseen-task
generalization. Memory expiry/pruning and production rollback remain separate
existing mechanisms; this stage does not add autonomous memory deletion.

Claude generation stays paused; this work uses none of the API budget.
