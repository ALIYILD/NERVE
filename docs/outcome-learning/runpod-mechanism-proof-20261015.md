# Runpod persisted selection and adaptation mechanism proof

**Correction: the 8/8 result is selection among prewritten handlers, NOT evidence of learning. The best fixed handler also scored 8/8.** Historical receipt keys such as `feedback_learning` are labels, not validated learning claims; original evidence is preserved unchanged.

The aggregate receipt was read back and confirms the existing NERVE implementation passes a synthetic end-to-end proof of
outcome-driven selection, persistence, bounded adaptation and rollback. All
execution occurred on the existing Runpod A40 pod `lg0svvuenxvbno`, with zero
model calls. This is a measured mechanism demonstration, not evidence that NERVE
invented a new skill or improved model weights.

## Capability verdicts

| Capability | Result | Evidence and boundary |
|---|---|---|
| Persisted selection among prewritten handlers | PASS, synthetic; NOT learning evidence | 16 executed strategy episodes produce independently checked rewards; SQLite utility selection changes from lowercase to trim-lowercase. |
| Behavioral reuse after process restart | PASS, synthetic | 8/8 novel strings correct after reload, versus frozen empty-memory 0/8; known best registered handler also gets 8/8. Evaluation writes no feedback. |
| Workload adaptation | PASS, synthetic | Both domain fixtures achieve 28/36 vs fixed controls 24/36 and 12/36, with two switches each. |
| Regression protection | PASS, fixture tests | Retained-task regression and forged/stale evaluations are rejected. |
| Canary rollback | PASS, synthetic | Actual fixture environment reversal causes two failures, rollback, then six successes; each reversal trial scores 6/8. |
| Persisted goal recovery | PASS | Stop after nine ticks, resume in a fresh process, reach completion; a further fresh process returns byte-identical completed state/receipt. |
| Missing/invalid feedback handling | PASS, fixture tests | Missing labels do not trigger drift; invalid rewards and foreign/stale/conflicting feedback rejected. Semantically false labels from a trusted judge are not detected automatically. |
| Unsigned retention | Correctly refused | Incumbent preserved; no production authorization. Existing contract tests use explicitly synthetic HMAC fixtures, never a real signature or registry. |
| Deterministic candidate-rule improvement | NOT MEASURED HERE | Galahad stopped at `no_failure_supported_hypothesis` in `5a60102`; no v4 was designed or tested. |
| Weight training | NOT PERFORMED | No model used, loaded or invoked by this proof. |
| Autonomous new-skill invention | NOT DEMONSTRATED | All strategy handlers and adaptation thresholds were written in advance. |
| Signed retained skill / activation | NOT AUTHORIZED | No live registry writes, promotion, real signing, holdout opening or activation. |

## What the numbers mean

`FeedbackAgentCoordinator` averages trusted rewards for registered handlers.
The proof executes each handler on eight training strings, derives correctness
from separate expected outputs, then launches a new process over the same SQLite
memory to evaluate eight distinct test strings. The empty-memory control defaults
to the first handler, intentionally inferior on whitespace-bearing inputs. The
best fixed handler solves all eight too: this demonstrates selection from known
handlers, not a new algorithm. These fixtures do not establish learning or an advantage over the best fixed handler. The 16 training executions are additional to the
eight evaluations per policy. The strings are novel identities from the same
simple template, not an unseen real-world distribution.

`auto_adaptation_goal` drives the existing deterministic A→B→A fixture protocol.
The controller sees outcomes and policy versions, not the phase label. Four
failures after a successful baseline trigger comparison of prewritten strategies
on separate selection and retained tasks. It switches, monitors eight canary
items, and rolls back after two failures. The synthetic retrieval and compute
fixtures intentionally favor different strategies by phase. Each domain includes
eight pre-recovery failures and **32 additional evaluation calls**. Therefore
28/36 versus 24/36 is not an equal-total-compute superiority claim. The domain
names `clinical_os` and `perfflux` do not establish clinical efficacy or measured
GPU savings.

The completed-state restart check proves persisted-state consistency and that
completion is not rerun. It is not an independent replay of every execution.
The separate tests check observational idempotency, temporal isolation, scoped
feedback, retained-task regressions, stale evaluation binding, missing outcomes,
canary reversal and fail-closed retention.

## Execution and evidence

- Base: `c165779`, isolated branch `codex/nerve-pod-mechanism-proof-20261015`.
- Remote targeted suite: **49 passed in 1.863 seconds**. Modules:
  `test_agent_learning_v12`, `test_auto_adaptation`, `test_goal_orchestrator`,
  `test_retained_skill_contract`, `test_outcome_forecast`.
- First proof: 2.153 seconds. Review then required measured GPU identity,
  refusal of local macOS execution, and full source-tree pinning before/after.
  The same fixture design reran in **2.587 seconds**; results unchanged.
  Both attempts are retained. No outcome-based tuning occurred.
- GPU identity measured with `nvidia-smi`; pod identity verified by live Runpod
  API and existing SSH mapping. This pod does not export `RUNPOD_POD_ID`.
- Available model catalog: `qwen2.5-coder:7b`, digest
  `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.
  Obtained by read-only `/api/tags`, **model_used=false**, **model_calls=0**.
  The inner report's null model digest means no execution model; the outer
  manifest records the available model identity separately.
- Live pod rate: **$0.59/hour**. Reviewed proof allocation about **$0.000424**;
  tests plus both proof execution intervals about **$0.001082**. These are
  pro-rated allocations of an already-running shared pod, not incremental
  infrastructure charges or the full bill. Transfer/coordination time excluded.
- Private execution state lives under `/root/nerve-outcome-mechanism-proof-*`,
  with verified mode 0700, and was archived before completion to
  `/Users/aliyildirim/nerve-research-runs/outcome-mechanism-proof-20261015/` (0700).
  No private state was placed under the pod's permissive `/workspace` mount.
- Initial archive extraction warned that network storage cannot restore macOS
  owner IDs. Files were readable; full source hashes bind the actual executed
  bytes and remained unchanged through the reviewed run. No application code
  was changed to work around filesystem ownership.

Aggregate receipts, registration, manifest and full test log are committed under
[`evidence/mechanism-proof-20261015`](evidence/mechanism-proof-20261015).
The archive contains full synthetic SQLite/checkpoint state; no real holdout or
patient data was involved. Independent read-only review cleared these narrow
claims. Existing modules were not changed; the addition is the reproducible
proof runner and evidence.

Remote commands, from the isolated uploaded code directory:

```sh
PYTHONPATH=src:tests OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nice -n 10 python -m unittest test_agent_learning_v12 test_auto_adaptation test_goal_orchestrator test_retained_skill_contract test_outcome_forecast -v
umask 077
PYTHONPATH=src OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nice -n 10 python scripts/prove_outcome_mechanisms.py --directory /root/nerve-outcome-mechanism-proof-evidence-v2 --pod-id lg0svvuenxvbno --hourly-rate-usd 0.59
```

Use a fresh output directory for reproduction; the runner refuses to overwrite
an existing proof. It requires Linux and measures an A40 before execution.
No tests or inference were executed on the laptop for this task.
