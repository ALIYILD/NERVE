# Bounded NERVE policy research loop

Implemented and locally tested on 12 October 2026. This extends the existing verified outcome learner and actual registered agent tools. It does not train model weights, generate executable source, or deploy a policy.

## Execution and measured result

The first v2 run executed **188 trials / 4,700 actual tool calls**, stopping after **two generations without an accepted improvement**. Eight configurations (including the cached baseline) were evaluated. Four remaining configurations were deliberately not evaluated after the patience limit. Baseline window=3, relevance tie breaking, no decay was retained.

| Frozen holdout arm | Correct / probes |
| --- | --- |
| Selected policy (unchanged baseline) | 75 / 100 |
| Current baseline | 75 / 100 |
| Fixed lower-only tool | 48 / 100 |
| Fixed trim-and-lower tool | 52 / 100 |

The selected and baseline rows reuse the identical trial results because their configurations are identical. Their zero difference, zero-width descriptive interval and p=1 are therefore tautological, not independent evidence of equivalence or improvement. Comparisons with fixed tools are limited to this synthetic strategy-selection fixture. No new policy improvement was demonstrated.

Three first-generation alternatives improved validation from 30/40 to 31/40, but reduced training from 30/40 to 29/40; the frozen nonregression gate rejected them. The second generation produced no acceptable gain. Rejections and trial evidence are preserved in [the full report](evidence/policy-loop-v2.json).

Measured wall time was 117.185 seconds on Python 3.10.0, macOS 26.5.2 x86_64. Regression tests ran concurrently, so this is execution duration, not a comparative performance benchmark. Monetary cost, GPU energy, model inference latency and real KV restoration were not measured.

## Loop and learning boundaries

`policy_research_loop.py` uses at most three generations, four candidates per generation, two stalled generations,272 trials and 6,800 tool executions. The frozen candidate grid varies window 3/5/10, relevance/least-recent tie breaking, and disabled/three-observation utility decay. Candidates need strict validation gain, aggregate training nonregression, and per-scenario validation nonregression against both incumbent and baseline.

Each trial performs 20 verified feedback executions followed by five probes with no feedback writes. Utility-state digests must remain unchanged during probes. Fixtures cover stationary, abrupt, recurrent and mixed requirements. v2 train seeds 1001/1002, validation 2001/2002, and holdout 3001–3005 are distinct from v1. Selection is persisted before the one final holdout comparison. Even a passing candidate is only recommended for review; promotion remains disabled.

Optional decay moves old utility toward the neutral prior. Age counts only judged observations in the same tenant, agent, context and evaluator revision. Activity in another scope cannot age this scope's history. Default behavior is unchanged. Existing durable automatic runs migrate missing default configuration fields without resetting consumed budgets; enabling decay requires a distinct configuration/run.

SQLite atomically claims both protocol and dataset before evaluation. Renaming a run or changing source does not permit the same dataset to be reused in that ledger. Failure or interruption consumes the claim; generation decisions persist. Do not delete the ledger to repeat tuning against observed holdout answers. This is an operator-owned database and public synthetic corpus, not independently sealed holdout custody. Changing the database can bypass operational replay protection.

## Reproduction

From the repository root, using its installed virtual environment:

```sh
.venv/bin/python scripts/verify_galahad.py baseline
.venv/bin/python scripts/verify_galahad.py cpu
PYTHONPATH=src .venv/bin/python scripts/run_memory_research_loop.py --database /tmp/nerve-policy-reproduction.sqlite --run-id reproduction-v2 --output /tmp/nerve-policy-reproduction.json
git diff --check
```

Use unused paths for independent reproduction; output overwrite is refused. A reproduction of this published dataset is not a fresh confirmatory experiment. A failed CLI run can leave an empty reserved output file; inspect the durable ledger's `policy_research_runs_v2` status and `policy_research_cycles_v2` evidence. Do not retry a consumed research dataset as a new experiment.

Full regression: **1,114 tests passed, zero failures/errors**, 60.703 seconds. New tests cover selection, budgets, interruptions, concurrent claims, holdout isolation, dataset replay, configuration migration and scope-local decay. Orchestration edge cases use injected test evaluators; the reported study executes the actual synthetic registered tools. [Validation metadata](evidence/policy-loop-v2-validation.json).

## Remaining work and status

This is local synthetic memory-policy adaptation, not improvement of underlying LLM weights or demonstrated scientific discovery. The failed candidate search is a valid research result. Broader tasks require new preregistered hypotheses and untouched evaluation data, not repeated tuning on this holdout. Real model evaluation, compatible licensed Galahad GPU restoration, independent holdout custody and clinical governance remain unresolved. No PR, deployment, default-policy promotion or clinical action occurred.
